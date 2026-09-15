"""Execute the versioned C2 PostgreSQL query and save a reproducible CSV + evidence."""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from import_ecb import connection_kwargs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/raw/ecb_rates.csv"))
    parser.add_argument("--evidence", type=Path, default=Path("evidence/mesures_des_requetes/postgres_job.json"))
    args = parser.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start >= end:
        parser.error("--start doit précéder --end")
    sql = Path("sql/postgres_rates.sql").read_text().replace(":'start_date'", "%(start_date)s").replace(":'end_date'", "%(end_date)s")
    params = {"start_date": str(start), "end_date": str(end)}
    with psycopg.connect(**connection_kwargs(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(sql, params)
            result = cur.fetchall()
            duration_ms = round((time.perf_counter() - t0) * 1000, 3)
            cur.execute("SELECT version() AS version")
            server_version = cur.fetchone()["version"]
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
            plan = cur.fetchone()["QUERY PLAN"][0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    columns = ["rate_date", "quote_currency", "base_currency", "usd_per_eur", "observation_status", "series_key", "source_url"]
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps({"system": "PostgreSQL", "server_version": server_version,
        "period_start_inclusive": str(start), "period_end_exclusive": str(end),
        "rate_window_start": str(start - timedelta(days=7)),
        "result_rows": len(result), "first_date": str(result[0]["rate_date"]) if result else None,
        "last_date": str(result[-1]["rate_date"]) if result else None,
        "client_fetch_duration_ms": duration_ms, "explain_analyze": plan}, indent=2, default=str) + "\n")
    excerpt = Path("evidence/extraits_des_resultats_sql/postgres_rates.csv")
    excerpt.parent.mkdir(parents=True, exist_ok=True)
    with excerpt.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result[:10])
    print(f"PostgreSQL: {len(result)} rows; output {args.output}; evidence {args.evidence}")


if __name__ == "__main__":
    main()
