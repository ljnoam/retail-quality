from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_dataset import run_pipeline
from verify_outputs import verify
from quality_rules import (ACCEPTED, EXCLUDED, REJECTED, REVIEW, RATES_REQUIRED,
                           SALES_REQUIRED, SchemaError, read_csv)

REAL_SALES = ROOT / "data/frozen/thelook_sales.csv"
REAL_RATES = ROOT / "data/frozen/ecb_rates.csv"
FIXTURE_SALES = ROOT / "tests/fixtures/sales_artificial.csv"
FIXTURE_RATES = ROOT / "tests/fixtures/rates_artificial.csv"
MANIFEST = ROOT / "evidence/mesures_des_requetes/extractions_integrity.json"
START, END = date(2024, 1, 1), date(2024, 2, 1)


def csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestSchemas(unittest.TestCase):
    def test_sales_missing_column_is_clear_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sales.csv"
            path.write_text("order_id,order_item_id\n1,2\n")
            with self.assertRaisesRegex(SchemaError, "sale_price"):
                read_csv(path, SALES_REQUIRED)

    def test_rates_missing_column_is_clear_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rates.csv"
            path.write_text("rate_date,usd_per_eur\n2024-01-05,1.2\n")
            with self.assertRaisesRegex(SchemaError, "series_key"):
                read_csv(path, RATES_REQUIRED)

    def test_duplicate_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sales.csv"
            path.write_text("order_id,order_id,order_item_id\n1,1,2\n")
            with self.assertRaisesRegex(SchemaError, "dupliquées"):
                read_csv(path, SALES_REQUIRED)

    def test_missing_file_has_actionable_message(self):
        with self.assertRaisesRegex(FileNotFoundError, "Refaire l'extraction"):
            read_csv(Path("missing_sales.csv"), SALES_REQUIRED)


class TestRealSnapshots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text())

    def test_frozen_sales_are_the_recorded_bigquery_extraction(self):
        info = self.manifest["sales"]
        self.assertEqual(hashlib.sha256(REAL_SALES.read_bytes()).hexdigest(), info["sha256"])
        rows = read_csv(REAL_SALES, SALES_REQUIRED)
        self.assertEqual(len(rows), 2131)
        self.assertEqual(info["row_count"], 2131)
        self.assertEqual(info["duplicate_key_count"], 0)
        self.assertEqual({row["sale_date_utc"][:7] for row in rows}, {"2024-01"})
        self.assertTrue(all(not any(key in row for key in ("customer_name", "email", "address")) for row in rows))

    def test_frozen_rates_are_the_recorded_postgres_extraction(self):
        info = self.manifest["rates"]
        self.assertEqual(hashlib.sha256(REAL_RATES.read_bytes()).hexdigest(), info["sha256"])
        rows = read_csv(REAL_RATES, RATES_REQUIRED)
        self.assertEqual(len(rows), 25)
        self.assertEqual(info["row_count"], 25)
        self.assertEqual(info["duplicate_key_count"], 0)
        self.assertEqual({(row["quote_currency"], row["base_currency"]) for row in rows}, {("USD", "EUR")})
        self.assertTrue(all(Decimal(row["usd_per_eur"]) > 0 for row in rows))

    def test_end_to_end_real_data_all_lines_counted_and_money_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            report = run_pipeline(REAL_SALES, REAL_RATES, output, START, END)
            final = csv_rows(output / "ventes_fiables.csv")
            quarantine = csv_rows(output / "quarantaine.csv")
            saved = json.loads((output / "rapport_qualite.json").read_text())
            self.assertEqual(saved, report)
            self.assertFalse(saved["fixtures_applied"])
            self.assertEqual(saved["input_sales_rows"], 2131)
            self.assertEqual(saved["input_rate_rows"], 25)
            self.assertEqual(saved["usable_rate_rows"], 25)
            self.assertEqual(saved["volume_check"], "PASSED")
            self.assertEqual(saved["final_key_uniqueness_check"], "PASSED")
            self.assertEqual(sum(saved["status_counts"].values()), 2131)
            self.assertEqual(saved["accounted_rows"], 2131)
            self.assertEqual(len(final) + len(quarantine), 2131)
            self.assertEqual(len(final), saved["status_counts"][ACCEPTED])
            self.assertEqual(len(quarantine), sum(saved["status_counts"][state] for state in (REJECTED, REVIEW, EXCLUDED)))
            self.assertEqual(sum(saved["reason_counts"].values()), len(quarantine))
            self.assertEqual(len({row["order_item_id"] for row in final}), len(final))
            self.assertTrue((output / "statuts.svg").read_text().startswith("<svg"))
            raw_sales = {row["order_item_id"]: row for row in csv_rows(REAL_SALES)}
            for row in final:
                with self.subTest(line=row["order_item_id"]):
                    self.assertGreater(Decimal(row["amount_source_usd"]), 0)
                    self.assertGreater(Decimal(row["usd_per_eur"]), 0)
                    self.assertGreater(Decimal(row["amount_eur"]), 0)
                    self.assertIn(row["order_status"], {"COMPLETE", "SHIPPED"})
                    self.assertEqual(row["source_currency_assumption"], "USD (POC assumption, unverified)")
                    self.assertLessEqual(date.fromisoformat(row["rate_date"]), date.fromisoformat(row["sale_date_utc"]))
                    self.assertLessEqual(int(row["rate_age_days"]), 7)
                    expected_source = Decimal(raw_sales[row["order_item_id"]]["sale_price"]).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP)
                    self.assertEqual(Decimal(row["amount_source_usd"]), expected_source)
                    expected_eur = (expected_source / Decimal(row["usd_per_eur"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP)
                    self.assertEqual(Decimal(row["amount_eur"]), expected_eur)
            self.assertEqual(sum(Decimal(row["amount_eur"]) for row in final), Decimal(saved["accepted_amount_eur_sum"]))

    def test_real_data_output_is_byte_identical_on_second_run(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            first = run_pipeline(REAL_SALES, REAL_RATES, output, START, END)
            names = ("ventes_fiables.csv", "quarantaine.csv", "rapport_qualite.json", "statuts.svg")
            before = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in names}
            second = run_pipeline(REAL_SALES, REAL_RATES, output, START, END)
            after = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in names}
            self.assertEqual(first, second)
            self.assertEqual(before, after)

    def test_independent_verifier_passes_and_detects_tampered_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            evidence = Path(temp) / "verify.json"
            run_pipeline(REAL_SALES, REAL_RATES, output, START, END)
            result = verify(REAL_SALES, REAL_RATES, output, evidence)
            self.assertTrue(all(value == "PASSED" for value in result["checks"].values()))
            rows = csv_rows(output / "ventes_fiables.csv")
            rows[0]["amount_eur"] = "0.01"
            with (output / "ventes_fiables.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(AssertionError, "Conversion EUR incorrecte"):
                verify(REAL_SALES, REAL_RATES, output, evidence)


class TestArtificialFixtures(unittest.TestCase):
    def test_fixture_inputs_cannot_be_mislabelled_as_real(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "--fixture-mode"):
                run_pipeline(FIXTURE_SALES, FIXTURE_RATES, Path(temp), START, END)

    def test_fixture_run_cannot_overwrite_published_output(self):
        with self.assertRaisesRegex(ValueError, "ne peut pas écrire dans output"):
            run_pipeline(FIXTURE_SALES, FIXTURE_RATES, ROOT / "output", START, END, fixture_mode=True)

    def test_fixture_end_to_end_is_explicitly_artificial(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            report = run_pipeline(FIXTURE_SALES, FIXTURE_RATES, output, START, END, fixture_mode=True)
            final = csv_rows(output / "ventes_fiables.csv")
            quarantine = csv_rows(output / "quarantaine.csv")
            self.assertTrue(report["fixtures_applied"])
            self.assertEqual(report["data_origin"], "artificial test fixtures")
            self.assertEqual(report["input_sales_rows"], 7)
            self.assertEqual(report["status_counts"], {ACCEPTED: 1, REJECTED: 3, REVIEW: 2, EXCLUDED: 1})
            self.assertEqual(report["reason_counts"], {"CANCELLED_ORDER": 1, "DUPLICATE_LINE_ID": 2,
                                                       "NON_POSITIVE_PRICE": 1, "PROCESSING_ORDER": 1,
                                                       "RATE_TOO_OLD": 1})
            self.assertEqual(len(final), 1)
            self.assertEqual(len(quarantine), 6)
            self.assertEqual(final[0]["amount_eur"], "10.00")

    def test_cli_runs_real_snapshot_and_reports_success(self):
        with tempfile.TemporaryDirectory() as temp:
            process = subprocess.run([sys.executable, str(ROOT / "src/build_dataset.py"),
                                      "--sales", str(REAL_SALES), "--rates", str(REAL_RATES),
                                      "--output-dir", temp], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            printed = json.loads(process.stdout)
            self.assertEqual(printed["input_sales_rows"], 2131)
            self.assertTrue((Path(temp) / "ventes_fiables.csv").is_file())

    def test_cli_missing_source_fails_without_partial_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out"
            process = subprocess.run([sys.executable, str(ROOT / "src/build_dataset.py"),
                                      "--sales", str(Path(temp) / "missing.csv"),
                                      "--rates", str(REAL_RATES), "--output-dir", str(output)],
                                     cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 2)
            self.assertIn("Source introuvable", process.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
