"""Summarize frozen public C2 extractions without inventing observations."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def summarize(path: Path, id_field: str, date_field: str) -> tuple[list[dict[str, str]], dict]:
    raw = path.read_bytes()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates = [row[date_field] for row in rows]
    ids = Counter(row[id_field] for row in rows)
    return rows, {"file": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                  "row_count": len(rows), "first_date": min(dates) if dates else None,
                  "last_date": max(dates) if dates else None,
                  "duplicate_key_count": sum(count - 1 for count in ids.values() if count > 1)}


def main() -> None:
    sales, sales_info = summarize(Path("data/frozen/thelook_sales.csv"), "order_item_id", "sale_date_utc")
    rates, rates_info = summarize(Path("data/frozen/ecb_rates.csv"), "rate_date", "rate_date")
    sales_info["order_disposition_counts"] = dict(sorted(Counter(row["order_disposition"] for row in sales).items()))
    sales_info["order_status_counts"] = dict(sorted(Counter(row["order_status"] for row in sales).items()))
    sales_info["missing_order_status_count"] = sum(not row["order_status"] for row in sales)
    sales_info["missing_product_category_count"] = sum(not row["product_category"] for row in sales)
    rates_info["currency_pairs"] = dict(sorted(Counter(f"{row['quote_currency']}/{row['base_currency']}" for row in rates).items()))
    output = Path("evidence/mesures_des_requetes/extractions_integrity.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"sales": sales_info, "rates": rates_info}, indent=2) + "\n")
    print(f"Sales {len(sales)} rows; rates {len(rates)} rows; evidence {output}")


if __name__ == "__main__":
    main()
