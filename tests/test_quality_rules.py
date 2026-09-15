from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from quality_rules import (ACCEPTED, EXCLUDED, REJECTED, REVIEW, RATE_SERIES, Rate,
                           choose_rate, classify_sales, load_rates, money, positive_id, sale_day)

START, END = date(2024, 1, 1), date(2024, 2, 1)


def sale(**changes):
    row = {"order_id": "10", "order_item_id": "20", "product_id": "30",
           "sale_date_utc": "2024-01-06", "order_status": "Complete", "item_status": "Complete",
           "order_disposition": "CANDIDATE_CA", "sale_price": "12.00", "product_category": "Tops"}
    row.update(changes)
    return row


def rate_row(**changes):
    row = {"rate_date": "2024-01-05", "quote_currency": "USD", "base_currency": "EUR",
           "usd_per_eur": "1.20000000", "observation_status": "A", "series_key": RATE_SERIES,
           "source_url": "https://example.test/artificial-rate"}
    row.update(changes)
    return row


def classify(rows, rate_rows=None):
    rates, _ = load_rates(rate_rows if rate_rows is not None else [rate_row()])
    return classify_sales(rows, rates, START, END)


class TestNormalization(unittest.TestCase):
    def test_positive_ids_are_stable(self):
        self.assertEqual(positive_id("00042"), "42")
        for value in ("", "0", "-1", "1.5", "abc"):
            with self.subTest(value=value):
                self.assertIsNone(positive_id(value))

    def test_dates_accept_utc_date_and_zoned_timestamp_only(self):
        self.assertEqual(sale_day("2024-01-06"), date(2024, 1, 6))
        self.assertEqual(sale_day("2024-01-01T23:30:00-01:00"), date(2024, 1, 2))
        self.assertEqual(sale_day("2024-01-06T10:00:00Z"), date(2024, 1, 6))
        for value in ("2024-02-30", "2024/01/06", "2024-01-06T10:00:00", ""):
            with self.subTest(value=value):
                self.assertIsNone(sale_day(value))

    def test_price_float_approximation_and_half_up(self):
        self.assertEqual(money("99.94999694824217"), (Decimal("99.95"), None))
        self.assertEqual(money("0.005"), (Decimal("0.01"), None))
        self.assertEqual(money("0.004"), (None, "PRICE_ROUNDS_TO_ZERO"))
        self.assertEqual(money("0"), (None, "NON_POSITIVE_PRICE"))
        self.assertEqual(money("-5"), (None, "NON_POSITIVE_PRICE"))
        self.assertEqual(money("NaN"), (None, "INVALID_PRICE"))
        self.assertEqual(money("inf"), (None, "INVALID_PRICE"))
        self.assertEqual(money("x"), (None, "INVALID_PRICE"))
        self.assertEqual(money(""), (None, "MISSING_PRICE"))


class TestRates(unittest.TestCase):
    def test_valid_rate_and_weekend_fallback(self):
        rates, issues = load_rates([rate_row()])
        self.assertEqual(issues, [])
        chosen, reason, age = choose_rate(date(2024, 1, 6), rates)
        self.assertEqual((chosen.day, reason, age), (date(2024, 1, 5), None, 1))

    def test_seven_days_inclusive_eight_days_excluded(self):
        rates, _ = load_rates([rate_row()])
        chosen, reason, age = choose_rate(date(2024, 1, 12), rates)
        self.assertEqual((chosen.day, reason, age), (date(2024, 1, 5), None, 7))
        chosen, reason, age = choose_rate(date(2024, 1, 13), rates)
        self.assertIsNone(chosen)
        self.assertEqual((reason, age), ("RATE_TOO_OLD", 8))

    def test_future_rate_is_never_used_and_no_prior_is_reviewed(self):
        rates, _ = load_rates([rate_row(rate_date="2024-01-07")])
        self.assertEqual(choose_rate(date(2024, 1, 6), rates), (None, "NO_PRIOR_RATE", None))

    def test_latest_valid_prior_rate_wins(self):
        rates, _ = load_rates([rate_row(rate_date="2024-01-04", usd_per_eur="1.1"), rate_row()])
        self.assertEqual(choose_rate(date(2024, 1, 6), rates)[0].day, date(2024, 1, 5))

    def test_rate_corruption_and_wrong_series_are_reported(self):
        rows = [rate_row(rate_date="2024-13-05"), rate_row(usd_per_eur="0"),
                rate_row(usd_per_eur="-1"), rate_row(usd_per_eur="NaN"),
                rate_row(quote_currency="GBP"), rate_row(observation_status="P"),
                rate_row(source_url=""), rate_row(usd_per_eur="abc")]
        usable, issues = load_rates(rows)
        self.assertEqual(usable, [])
        self.assertEqual([issue["code"] for issue in issues],
                         ["INVALID_RATE_DATE", "NON_POSITIVE_RATE", "NON_POSITIVE_RATE",
                          "NON_POSITIVE_RATE", "INVALID_RATE_SERIES_OR_PAIR",
                          "RATE_NOT_PUBLISHED_AS_VALID", "MISSING_RATE_SOURCE", "INVALID_RATE_VALUE"])
        self.assertTrue(all(issue["explanation"] for issue in issues))

    def test_duplicate_rate_day_is_not_arbitrarily_selected(self):
        usable, issues = load_rates([rate_row(), rate_row(usd_per_eur="1.3")])
        self.assertEqual(usable, [])
        self.assertEqual([issue["code"] for issue in issues], ["DUPLICATE_RATE_DATE"] * 2)

    def test_window_cannot_exceed_prd_limit(self):
        with self.assertRaises(ValueError):
            choose_rate(date(2024, 1, 6), [], 8)


class TestSalesDecisions(unittest.TestCase):
    def one(self, row, rate_rows=None):
        accepted, quarantine, report = classify([row], rate_rows)
        return accepted, quarantine, report

    def test_normal_complete_and_shipped_are_accepted(self):
        for state in ("Complete", " shipped "):
            with self.subTest(state=state):
                row = sale(order_status=state, item_status=state)
                accepted, quarantine, report = self.one(row)
                self.assertEqual((len(accepted), len(quarantine)), (1, 0))
                self.assertEqual(report["status_counts"][ACCEPTED], 1)
                self.assertEqual(accepted[0]["rate_date"], "2024-01-05")
                self.assertEqual(accepted[0]["rate_age_days"], "1")
                self.assertEqual(accepted[0]["amount_eur"], "10.00")

    def test_corrupt_ids_dates_and_prices_are_rejected(self):
        cases = [("order_item_id", "", "MISSING_LINE_ID"),
                 ("order_item_id", "x", "INVALID_LINE_ID"),
                 ("order_id", "", "MISSING_ORDER_ID"),
                 ("order_id", "0", "INVALID_ORDER_ID"),
                 ("product_id", "", "MISSING_PRODUCT_ID"),
                 ("product_id", "-3", "INVALID_PRODUCT_ID"),
                 ("sale_date_utc", "2024-02-30", "INVALID_SALE_DATE"),
                 ("sale_date_utc", "2024-02-01", "SALE_OUTSIDE_PERIOD"),
                 ("sale_price", "", "MISSING_PRICE"),
                 ("sale_price", "abc", "INVALID_PRICE"),
                 ("sale_price", "0", "NON_POSITIVE_PRICE"),
                 ("sale_price", "-1", "NON_POSITIVE_PRICE"),
                 ("sale_price", "0.004", "PRICE_ROUNDS_TO_ZERO")]
        for field, value, reason in cases:
            with self.subTest(field=field, value=value):
                accepted, quarantine, report = self.one(sale(**{field: value}))
                self.assertEqual(accepted, [])
                self.assertEqual(quarantine[0]["status"], REJECTED)
                self.assertEqual(quarantine[0]["reason_code"], reason)
                self.assertEqual(report["accounted_rows"], 1)

    def test_duplicate_normalized_line_id_rejects_all_occurrences(self):
        accepted, quarantine, report = classify([sale(order_item_id="020"),
                                                  sale(order_item_id="20", order_id="11")])
        self.assertEqual(accepted, [])
        self.assertEqual([row["reason_code"] for row in quarantine], ["DUPLICATE_LINE_ID"] * 2)
        self.assertEqual(report["status_counts"][REJECTED], 2)

    def test_business_exclusion_is_distinct_from_quality_rejection(self):
        rows = [sale(order_status="Cancelled", item_status="Cancelled"),
                sale(order_item_id="21", order_status="Returned", item_status="Returned")]
        accepted, quarantine, report = classify(rows)
        self.assertEqual(accepted, [])
        self.assertEqual([row["status"] for row in quarantine], [EXCLUDED, EXCLUDED])
        self.assertEqual([row["reason_code"] for row in quarantine], ["CANCELLED_ORDER", "RETURNED_ORDER"])
        self.assertEqual(report["status_counts"][REJECTED], 0)

    def test_invalid_cancelled_price_is_rejected_by_precedence(self):
        _, quarantine, _ = self.one(sale(order_status="Cancelled", item_status="Cancelled", sale_price="-1"))
        self.assertEqual((quarantine[0]["status"], quarantine[0]["reason_code"]),
                         (REJECTED, "NON_POSITIVE_PRICE"))

    def test_pending_unknown_and_conflicting_statuses_are_reviewed(self):
        cases = [(dict(order_status="Processing", item_status="Processing"), "PROCESSING_ORDER"),
                 (dict(order_status="Pending", item_status="Pending"), "UNKNOWN_ORDER_STATUS"),
                 (dict(order_status="", item_status="Complete"), "MISSING_ORDER_STATUS"),
                 (dict(order_status="Complete", item_status=""), "MISSING_ITEM_STATUS"),
                 (dict(order_status="Complete", item_status="Cancelled"), "STATUS_CONFLICT")]
        for changes, reason in cases:
            with self.subTest(reason=reason):
                _, quarantine, _ = self.one(sale(**changes))
                self.assertEqual((quarantine[0]["status"], quarantine[0]["reason_code"]), (REVIEW, reason))

    def test_missing_category_or_rate_is_reviewed(self):
        cases = [(sale(product_category=""), None, "MISSING_PRODUCT_CATEGORY"),
                 (sale(), [], "NO_PRIOR_RATE"),
                 (sale(sale_date_utc="2024-01-13"), None, "RATE_TOO_OLD")]
        for row, rates, reason in cases:
            with self.subTest(reason=reason):
                _, quarantine, _ = self.one(row, rates)
                self.assertEqual((quarantine[0]["status"], quarantine[0]["reason_code"]), (REVIEW, reason))

    def test_corrupt_rate_causes_review_without_fabricated_fallback(self):
        _, quarantine, _ = self.one(sale(), [rate_row(usd_per_eur="-1")])
        self.assertEqual(quarantine[0]["reason_code"], "NO_PRIOR_RATE")

    def test_monies_are_divided_and_rounded_per_line(self):
        rates = [rate_row(usd_per_eur="2")]
        accepted, _, report = classify([sale(sale_price="0.03"),
                                        sale(order_item_id="21", sale_price="0.03")], rates)
        self.assertEqual([row["amount_eur"] for row in accepted], ["0.02", "0.02"])
        self.assertEqual(report["accepted_amount_eur_sum"], "0.04")
        self.assertEqual(accepted[0]["source_currency_assumption"], "USD (POC assumption, unverified)")

    def test_every_input_line_is_accounted_once(self):
        rows = [sale(), sale(order_item_id="21", sale_price="-1"),
                sale(order_item_id="22", order_status="Cancelled", item_status="Cancelled"),
                sale(order_item_id="23", order_status="Processing", item_status="Processing")]
        accepted, quarantine, report = classify(rows)
        self.assertEqual(report["accounted_rows"], len(rows))
        self.assertEqual(len(accepted) + len(quarantine), len(rows))
        self.assertEqual(sum(report["status_counts"].values()), len(rows))
        self.assertEqual(sum(report["reason_counts"].values()), len(quarantine))


if __name__ == "__main__":
    unittest.main()
