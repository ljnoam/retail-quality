"""Independent release check of generated C3 files against frozen C2 inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal("0.01")
ACCEPTED = "ACCEPTÉE"
NON_ACCEPTED = {"REJETÉE", "À VÉRIFIER", "EXCLUE PAR RÈGLE MÉTIER"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(sales_path: Path, rates_path: Path, output_dir: Path, evidence_path: Path) -> dict:
    sales = read_rows(sales_path)
    rates = read_rows(rates_path)
    final_path = output_dir / "ventes_fiables.csv"
    quarantine_path = output_dir / "quarantaine.csv"
    report_path = output_dir / "rapport_qualite.json"
    chart_path = output_dir / "statuts.svg"
    final, quarantine = read_rows(final_path), read_rows(quarantine_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["fixtures_applied"]:
        raise AssertionError("Le rapport publié doit provenir des snapshots réels, pas des fixtures.")
    if report["sales_input_sha256"] != digest(sales_path) or report["rates_input_sha256"] != digest(rates_path):
        raise AssertionError("Les empreintes d'entrée du rapport ne correspondent pas aux snapshots.")
    if (report["input_sales_rows"] != len(sales) or report["input_rate_rows"] != len(rates)
            or len(final) != report["final_rows"] or len(quarantine) != report["quarantine_rows"]):
        raise AssertionError("Les nombres de lignes entrée/sortie divergent du rapport.")
    if (sum(report["status_counts"].values()) != len(sales)
            or report["status_counts"][ACCEPTED] != len(final)
            or sum(report["reason_counts"].values()) != len(quarantine)):
        raise AssertionError("La ventilation statut/raison ne comptabilise pas toutes les lignes.")
    if len({row["order_item_id"] for row in final}) != len(final):
        raise AssertionError("Clé de ligne dupliquée dans le jeu final.")
    source_rows_by_id: dict[str, list[int]] = {}
    for source_row, sale in enumerate(sales, 2):
        raw_id = str(sale["order_item_id"]).strip()
        key = str(int(raw_id)) if raw_id.isdigit() and int(raw_id) > 0 else raw_id
        source_rows_by_id.setdefault(key, []).append(source_row)
    final_source_rows = []
    total = Decimal("0.00")
    for row in final:
        source_ids = source_rows_by_id.get(row["order_item_id"], [])
        if len(source_ids) != 1:
            raise AssertionError(f"Ligne finale {row['order_item_id']} absente ou dupliquée dans la source.")
        final_source_rows.append(source_ids[0])
        amount = Decimal(row["amount_source_usd"])
        rate = Decimal(row["usd_per_eur"])
        eur = Decimal(row["amount_eur"])
        if amount <= 0 or rate <= 0 or eur <= 0:
            raise AssertionError(f"Montant ou taux invalide dans la ligne finale {row['order_item_id']}.")
        if (amount / rate).quantize(CENT, rounding=ROUND_HALF_UP) != eur:
            raise AssertionError(f"Conversion EUR incorrecte dans la ligne finale {row['order_item_id']}.")
        age = (date.fromisoformat(row["sale_date_utc"]) - date.fromisoformat(row["rate_date"])).days
        if age < 0 or age > 7 or age != int(row["rate_age_days"]):
            raise AssertionError(f"Taux BCE hors fenêtre pour {row['order_item_id']}.")
        if not row["rate_source_url"] or row["source_currency_assumption"] != "USD (POC assumption, unverified)":
            raise AssertionError("Provenance du taux ou hypothèse de devise absente.")
        total += eur
    if total != Decimal(report["accepted_amount_eur_sum"]):
        raise AssertionError("Somme EUR différente du rapport.")
    nonaccepted_source_rows = [int(row["source_row"]) for row in quarantine]
    if (len(set(final_source_rows + nonaccepted_source_rows)) != len(sales)
            or set(final_source_rows + nonaccepted_source_rows) != set(range(2, len(sales) + 2))):
        raise AssertionError("Une ligne source manque ou est comptée plusieurs fois.")
    for row in quarantine:
        if row["status"] not in NON_ACCEPTED or not row["reason_code"] or not row["reason_explanation"]:
            raise AssertionError("Ligne de quarantaine sans décision ou raison traçable.")
    if dict(sorted(Counter(row["reason_code"] for row in quarantine).items())) != report["reason_counts"]:
        raise AssertionError("Les codes de raisons du rapport ne correspondent pas à la quarantaine.")
    if not chart_path.read_text(encoding="utf-8").startswith("<svg"):
        raise AssertionError("Graphique des statuts absent ou invalide.")
    evidence = {"checks": {"input_hashes": "PASSED", "volume_conservation": "PASSED",
                           "source_line_partition": "PASSED", "final_key_uniqueness": "PASSED",
                           "positive_money_and_rates": "PASSED", "rate_age_0_to_7_days": "PASSED",
                           "eur_conversion": "PASSED", "reason_traceability": "PASSED",
                           "fixture_separation": "PASSED"},
                "input_sales_rows": len(sales), "input_rate_rows": len(rates),
                "status_counts": report["status_counts"], "accepted_amount_eur_sum": str(total),
                "output_sha256": {path.name: digest(path) for path in (final_path, quarantine_path, report_path, chart_path)}}
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Vérifier indépendamment les sorties C3")
    parser.add_argument("--sales", type=Path, default=Path("data/frozen/thelook_sales.csv"))
    parser.add_argument("--rates", type=Path, default=Path("data/frozen/ecb_rates.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--evidence", type=Path, default=Path("evidence/rapport_de_tests/c3_output_verification.json"))
    args = parser.parse_args()
    try:
        evidence = verify(args.sales, args.rates, args.output_dir, args.evidence)
    except (AssertionError, OSError, ValueError) as error:
        parser.exit(2, f"Vérification C3 échouée : {error}\n")
    print(json.dumps(evidence["checks"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
