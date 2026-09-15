"""Build the single C3 reliable-sales dataset and its fully counted quarantine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from quality_rules import (ACCEPTED, EXCLUDED, REJECTED, REVIEW, RATES_REQUIRED, REASONS,
                           SALES_REQUIRED, classify_sales, load_rates, read_csv)

FINAL_FIELDS = ["order_id", "order_item_id", "product_id", "product_category", "sale_date_utc",
                "order_status", "amount_source_usd", "source_currency_assumption", "rate_date",
                "usd_per_eur", "rate_age_days", "amount_eur", "rate_source_url"]
QUARANTINE_FIELDS = ["source_row", "order_id", "order_item_id", "product_id", "sale_date_utc",
                     "order_status", "item_status", "order_disposition", "sale_price", "product_category",
                     "normalized_order_id", "normalized_order_item_id", "normalized_product_id",
                     "normalized_sale_date_utc", "normalized_amount_source_usd", "status",
                     "reason_code", "reason_explanation"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests/fixtures"
PUBLISHED_OUTPUT_ROOT = PROJECT_ROOT / "output"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def status_chart(counts: dict[str, int]) -> str:
    labels = [(ACCEPTED, "#177245"), (REJECTED, "#b42318"),
              (REVIEW, "#b76e00"), (EXCLUDED, "#52657a")]
    maximum = max(counts.values(), default=0) or 1
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="300" viewBox="0 0 760 300">',
             '<rect width="760" height="300" fill="#ffffff"/>',
             '<text x="24" y="28" font-family="Arial" font-size="18" fill="#1b2633">Statuts des lignes extraites</text>']
    for index, (status, color) in enumerate(labels):
        y = 58 + index * 58
        width = round(390 * counts[status] / maximum)
        parts.append(f'<text x="24" y="{y + 17}" font-family="Arial" font-size="14" fill="#1b2633">{escape(status)}</text>')
        parts.append(f'<rect x="245" y="{y}" width="{width}" height="26" fill="{color}"/>')
        parts.append(f'<text x="{260 + width}" y="{y + 18}" font-family="Arial" font-size="14" fill="#1b2633">{counts[status]}</text>')
    parts.append('</svg>\n')
    return "\n".join(parts)


def run_pipeline(sales_path: Path, rates_path: Path, output_dir: Path,
                 start: date, end: date, max_age_days: int = 7,
                 fixture_mode: bool = False) -> dict[str, object]:
    fixture_input = sales_path.resolve().is_relative_to(FIXTURE_ROOT) or rates_path.resolve().is_relative_to(FIXTURE_ROOT)
    if fixture_input and not fixture_mode:
        raise ValueError("Les fixtures artificielles exigent --fixture-mode et un répertoire de sortie séparé.")
    if fixture_mode and output_dir.resolve().is_relative_to(PUBLISHED_OUTPUT_ROOT):
        raise ValueError("Une exécution de fixture ne peut pas écrire dans output/ du projet.")
    sales_rows = read_csv(sales_path, SALES_REQUIRED)
    rate_rows = read_csv(rates_path, RATES_REQUIRED)
    rates, rate_issues = load_rates(rate_rows)
    accepted, quarantine, report = classify_sales(sales_rows, rates, start, end, max_age_days)
    report.update({
        "data_origin": ("artificial test fixtures" if fixture_mode else
                        "frozen public TheLook BigQuery and ECB PostgreSQL extractions"),
        "fixtures_applied": fixture_mode,
        "sales_input": str(sales_path), "sales_input_sha256": sha256(sales_path),
        "rates_input": str(rates_path), "rates_input_sha256": sha256(rates_path),
        "period_start_inclusive": str(start), "period_end_exclusive": str(end),
        "rate_max_age_calendar_days": max_age_days,
        "source_currency_assumption": "USD (POC assumption, unverified)",
        "normalization_timezone": "UTC", "money_rounding": "ROUND_HALF_UP to 0.01 source units, then 0.01 EUR per line",
        "conversion_formula": "amount_eur = amount_source_usd / usd_per_eur",
        "input_rate_rows": len(rate_rows), "usable_rate_rows": len(rates),
        "rate_issue_counts": dict(sorted(Counter(issue["code"] for issue in rate_issues).items())),
        "rate_issues": rate_issues,
        "reason_explanations": {code: REASONS[code] for code in report["reason_counts"]},
        "volume_check": "PASSED" if report["accounted_rows"] == len(sales_rows) else "FAILED",
        "final_key_uniqueness_check": "PASSED" if len({row["order_item_id"] for row in accepted}) == len(accepted) else "FAILED",
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "ventes_fiables.csv", accepted, FINAL_FIELDS)
    write_csv(output_dir / "quarantaine.csv", quarantine, QUARANTINE_FIELDS)
    (output_dir / "rapport_qualite.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "statuts.svg").write_text(status_chart(report["status_counts"]), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Construire les ventes fiables en euros depuis les extractions C2 figées")
    parser.add_argument("--sales", type=Path, default=Path("data/frozen/thelook_sales.csv"))
    parser.add_argument("--rates", type=Path, default=Path("data/frozen/ecb_rates.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--start", default=os.getenv("RQ_START_DATE", "2024-01-01"))
    parser.add_argument("--end", default=os.getenv("RQ_END_DATE", "2024-02-01"))
    parser.add_argument("--rate-max-age-days", type=int, default=int(os.getenv("RQ_RATE_MAX_AGE_DAYS", "7")))
    parser.add_argument("--fixture-mode", action="store_true", help="Marquer la sortie comme données artificielles de test")
    args = parser.parse_args()
    try:
        report = run_pipeline(args.sales, args.rates, args.output_dir,
                              date.fromisoformat(args.start), date.fromisoformat(args.end),
                              args.rate_max_age_days, args.fixture_mode)
    except (ValueError, FileNotFoundError) as error:
        parser.exit(2, f"Erreur Retail Quality : {error}\n")
    print(json.dumps({"input_sales_rows": report["input_sales_rows"],
                      "status_counts": report["status_counts"],
                      "final_rows": report["final_rows"],
                      "quarantine_rows": report["quarantine_rows"],
                      "accepted_amount_eur_sum": report["accepted_amount_eur_sum"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
