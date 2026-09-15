"""Import a fixed ECB daily USD/EUR series into PostgreSQL, idempotently."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import urlopen

import psycopg

SERIES = "EXR.D.USD.EUR.SP00.A"
BASE_URL = f"https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
SOURCE_ID = "ecb_exr_daily_usd_eur"


def read_observations(raw: bytes, start: date, end: date) -> list[tuple[date, Decimal, str]]:
    text = raw.decode("utf-8-sig")
    rows = csv.DictReader(text.splitlines())
    required = {"KEY", "FREQ", "CURRENCY", "CURRENCY_DENOM", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS"}
    if not rows.fieldnames or not required.issubset(rows.fieldnames):
        raise ValueError(f"BCE CSV: colonnes indispensables absentes: {sorted(required - set(rows.fieldnames or []))}")
    output = []
    seen = set()
    for row in rows:
        if row["KEY"] != SERIES or row["FREQ"] != "D" or row["CURRENCY"] != "USD" or row["CURRENCY_DENOM"] != "EUR":
            raise ValueError("BCE CSV: série ou paire de devises inattendue")
        day = date.fromisoformat(row["TIME_PERIOD"])
        if not start <= day < end:
            continue
        try:
            rate = Decimal(row["OBS_VALUE"])
        except (InvalidOperation, TypeError):
            raise ValueError(f"BCE CSV: taux non numérique le {day}") from None
        if not rate.is_finite() or rate <= 0:
            raise ValueError(f"BCE CSV: taux invalide le {day}")
        if day in seen:
            raise ValueError(f"BCE CSV: date doublonnée {day}")
        seen.add(day)
        output.append((day, rate, row["OBS_STATUS"] or ""))
    if not output:
        raise ValueError("BCE CSV: aucune observation dans la période demandée")
    return sorted(output)


def connection_kwargs() -> dict[str, object]:
    return dict(host=os.getenv("PGHOST", "localhost"), port=int(os.getenv("PGPORT", "5432")),
                dbname=os.getenv("PGDATABASE", "retail_quality"), user=os.getenv("PGUSER") or os.getenv("USER"),
                password=os.getenv("PGPASSWORD") or None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="premier jour inclus, ISO")
    parser.add_argument("--end", required=True, help="premier jour exclu, ISO")
    parser.add_argument("--csv", type=Path, help="snapshot CSV officiel déjà téléchargé")
    parser.add_argument("--evidence", type=Path, default=Path("evidence/mesures_des_requetes/ecb_import.json"))
    args = parser.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start >= end:
        parser.error("--start doit précéder --end")
    url = f"{BASE_URL}?startPeriod={start}&endPeriod={end - timedelta(days=1)}&format=csvdata"
    raw = args.csv.read_bytes() if args.csv else urlopen(url, timeout=30).read()
    observations = read_observations(raw, start, end)
    with psycopg.connect(**connection_kwargs()) as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO rate_sources (source_id, series_key, source_url, quote_currency, base_currency)
                           VALUES (%s, %s, %s, 'USD', 'EUR')
                           ON CONFLICT (source_id) DO UPDATE SET source_url = EXCLUDED.source_url""",
                        (SOURCE_ID, SERIES, BASE_URL))
            cur.executemany("""INSERT INTO exchange_rates (rate_date, source_id, usd_per_eur, observation_status)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (rate_date, source_id) DO UPDATE
                               SET usd_per_eur = EXCLUDED.usd_per_eur,
                                   observation_status = EXCLUDED.observation_status""",
                            [(day, SOURCE_ID, rate, status) for day, rate, status in observations])
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps({"source_url": url, "input_csv": str(args.csv) if args.csv else None,
        "input_sha256": hashlib.sha256(raw).hexdigest(), "series_key": SERIES,
        "period_start_inclusive": str(start), "period_end_exclusive": str(end),
        "observations_imported": len(observations), "first_observation": str(observations[0][0]),
        "last_observation": str(observations[-1][0]), "unit": "USD per 1 EUR"}, indent=2) + "\n")
    print(f"Imported {len(observations)} ECB observations ({observations[0][0]}..{observations[-1][0]})")


if __name__ == "__main__":
    main()
