"""Run TheLook discovery/extraction jobs and record real BigQuery job metadata."""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

from google.cloud import bigquery

DATASET = "bigquery-public-data.thelook_ecommerce"
REQUIRED = {
    "orders": {"order_id", "status"},
    "order_items": {"id", "order_id", "product_id", "created_at", "status", "sale_price"},
    "products": {"id", "category"},
}
EXPECTED_TYPES = {
    "orders": {"order_id": {"INTEGER", "INT64"}, "status": {"STRING"}},
    "order_items": {"id": {"INTEGER", "INT64"}, "order_id": {"INTEGER", "INT64"},
                    "product_id": {"INTEGER", "INT64"}, "created_at": {"TIMESTAMP"},
                    "status": {"STRING"}, "sale_price": {"FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}},
    "products": {"id": {"INTEGER", "INT64"}, "category": {"STRING"}},
}


def metadata(job: bigquery.job.QueryJob) -> dict:
    return {"job_id": job.job_id, "project": job.project, "location": job.location,
        "state": job.state, "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": job.total_bytes_processed,
        "total_bytes_billed": job.total_bytes_billed,
        "slot_millis": job.slot_millis,
        "cache_hit": job.cache_hit,
        "statement_type": job.statement_type}


def run_sql(client: bigquery.Client, path: str, dry_run: bool = False):
    config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(Path(path).read_text(), job_config=config, location=os.getenv("BIGQUERY_LOCATION", "US"))
    result = [] if dry_run else list(job.result())
    return result, metadata(job)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def discover(client: bigquery.Client) -> None:
    tables = {}
    for name, fields in REQUIRED.items():
        table = client.get_table(f"{DATASET}.{name}")
        schema = [{"name": field.name, "type": field.field_type, "mode": field.mode,
                   "description": field.description} for field in table.schema]
        missing = fields - {field["name"] for field in schema}
        if missing:
            raise ValueError(f"TheLook {name}: colonnes absentes: {sorted(missing)}")
        actual_types = {field["name"]: field["type"] for field in schema}
        mismatches = {column: actual_types[column] for column, allowed in EXPECTED_TYPES[name].items()
                      if actual_types[column] not in allowed}
        if mismatches:
            raise ValueError(f"TheLook {name}: types inattendus: {mismatches}")
        tables[name] = {"table_id": table.full_table_id, "num_rows_metadata": table.num_rows,
                        "num_bytes_metadata": table.num_bytes, "modified": table.modified,
                        "time_partitioning": str(table.time_partitioning) if table.time_partitioning else None,
                        "range_partitioning": str(table.range_partitioning) if table.range_partitioning else None,
                        "clustering_fields": table.clustering_fields, "schema": schema}
    schema_rows, schema_job = run_sql(client, "sql/bigquery_schema.sql")
    schema_columns = [dict(row.items()) for row in schema_rows]
    rows, job = run_sql(client, "sql/bigquery_period.sql")
    period = [dict(row.items()) for row in rows]
    status_rows, status_job = run_sql(client, "sql/bigquery_statuses.sql")
    statuses = [dict(row.items()) for row in status_rows]
    write_json(Path("evidence/mesures_des_requetes/bigquery_discovery.json"),
               {"tables": tables, "schema_columns": schema_columns, "schema_job": schema_job,
                "period_diagnostics": period, "period_job": job,
                "status_diagnostics": statuses, "status_job": status_job})
    print("BigQuery discovery:", json.dumps({"period": period, "statuses": statuses}, default=str))


def extract(client: bigquery.Client) -> None:
    discovery = Path("evidence/mesures_des_requetes/bigquery_discovery.json")
    if not discovery.exists():
        raise RuntimeError("Exécuter d’abord `python src/extract_bigquery.py discover` pour vérifier les schémas et périodes")
    diagnostics = json.loads(discovery.read_text())
    item_period = next((row["rows_in_candidate_period"] for row in diagnostics["period_diagnostics"]
                        if row["source_table"] == "order_items"), 0)
    if not item_period:
        raise RuntimeError("Aucune ligne TheLook observée dans la période candidate ; choisir et documenter une autre période")
    rows, job = run_sql(client, "sql/bigquery_sales.sql")
    ids = Counter(row["order_item_id"] for row in rows)
    duplicates = [item_id for item_id, count in ids.items() if count > 1]
    if duplicates or len(rows) != item_period:
        write_json(Path("evidence/mesures_des_requetes/bigquery_sales_job.json"),
                   {"job": job, "result_rows": len(rows), "period_source_rows": item_period,
                    "duplicate_line_ids": duplicates[:20], "validation": "FAILED"})
        raise ValueError(f"Cardinalité inattendue : extraction={len(rows)}, lignes source={item_period}, doublons={len(duplicates)}")
    columns = ["order_id", "order_item_id", "product_id", "sale_date_utc", "order_status",
               "item_status", "order_disposition", "sale_price", "product_category"]
    output = Path("data/frozen/thelook_sales.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row.items()) for row in rows)
    excerpt = Path("evidence/extraits_des_resultats_sql/bigquery_sales.csv")
    excerpt.parent.mkdir(parents=True, exist_ok=True)
    with excerpt.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row.items()) for row in rows[:10])
    write_json(Path("evidence/mesures_des_requetes/bigquery_sales_job.json"),
               {"query_file": "sql/bigquery_sales.sql", "period_start_inclusive": "2024-01-01",
                "period_end_exclusive": "2024-02-01", "result_rows": len(rows),
                "period_source_rows": item_period, "duplicate_line_ids": 0,
                "validation": "PASSED", "job": job})
    print(f"BigQuery extraction: {len(rows)} rows; job {job['job_id']}")


def compare(client: bigquery.Client) -> None:
    runs = {}
    for name, path in (("baseline", "sql/bigquery_sales_baseline.sql"),
                       ("final", "sql/bigquery_sales.sql")):
        _, runs[name] = run_sql(client, path, dry_run=True)
    write_json(Path("evidence/mesures_des_requetes/bigquery_dry_runs.json"), runs)
    print(json.dumps(runs, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["discover", "extract", "compare"])
    args = parser.parse_args()
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        parser.error("Définir GOOGLE_CLOUD_PROJECT avec un projet Google Cloud autorisé pour les jobs")
    client = bigquery.Client(project=project)
    {"discover": discover, "extract": extract, "compare": compare}[args.action](client)


if __name__ == "__main__":
    main()
