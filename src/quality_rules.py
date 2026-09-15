"""Deterministic Retail Quality rules for frozen public sales and ECB rates."""
from __future__ import annotations

import csv
import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

SALES_REQUIRED = {"order_id", "order_item_id", "product_id", "sale_date_utc",
                  "order_status", "item_status", "sale_price", "product_category"}
RATES_REQUIRED = {"rate_date", "quote_currency", "base_currency", "usd_per_eur",
                  "observation_status", "series_key", "source_url"}
RATE_SERIES = "EXR.D.USD.EUR.SP00.A"
CENT = Decimal("0.01")
ACCEPTED = "ACCEPTÉE"
REJECTED = "REJETÉE"
REVIEW = "À VÉRIFIER"
EXCLUDED = "EXCLUE PAR RÈGLE MÉTIER"
STATUSES = (ACCEPTED, REJECTED, REVIEW, EXCLUDED)

REASONS = {
    "DUPLICATE_LINE_ID": "Identifiant de ligne présent plusieurs fois ; aucune occurrence n'est choisie arbitrairement.",
    "MISSING_LINE_ID": "Identifiant de ligne absent.",
    "INVALID_LINE_ID": "Identifiant de ligne non entier positif.",
    "MISSING_ORDER_ID": "Identifiant de commande absent.",
    "INVALID_ORDER_ID": "Identifiant de commande non entier positif.",
    "MISSING_PRODUCT_ID": "Identifiant de produit absent.",
    "INVALID_PRODUCT_ID": "Identifiant de produit non entier positif.",
    "INVALID_SALE_DATE": "Date de vente impossible ou sans fuseau pour un horodatage.",
    "SALE_OUTSIDE_PERIOD": "Date de vente hors de la période commerciale documentée.",
    "MISSING_PRICE": "Prix de vente absent.",
    "INVALID_PRICE": "Prix de vente non numérique ou non fini.",
    "NON_POSITIVE_PRICE": "Prix de vente nul ou négatif.",
    "PRICE_ROUNDS_TO_ZERO": "Prix positif mais nul après normalisation au centime.",
    "MISSING_ORDER_STATUS": "État de commande absent.",
    "MISSING_ITEM_STATUS": "État de ligne absent.",
    "STATUS_CONFLICT": "États de commande et de ligne contradictoires.",
    "CANCELLED_ORDER": "Commande annulée : exclusion métier du chiffre d'affaires.",
    "RETURNED_ORDER": "Commande retournée : exclusion métier du chiffre d'affaires.",
    "PROCESSING_ORDER": "Commande encore en traitement : chiffre d'affaires à vérifier.",
    "UNKNOWN_ORDER_STATUS": "État commercial inconnu : décision métier à vérifier.",
    "MISSING_PRODUCT_CATEGORY": "Catégorie de produit absente ; référence produit à vérifier.",
    "NO_PRIOR_RATE": "Aucun taux BCE publié à la date de vente ou avant elle.",
    "RATE_TOO_OLD": "Dernier taux BCE antérieur trop ancien pour la fenêtre autorisée.",
}
RATE_ISSUE_EXPLANATIONS = {
    "INVALID_RATE_DATE": "Date de taux impossible ; observation ignorée.",
    "INVALID_RATE_SERIES_OR_PAIR": "Série ou paire autre que USD/EUR quotidienne BCE ; observation ignorée.",
    "RATE_NOT_PUBLISHED_AS_VALID": "Statut d'observation autre que A ; observation ignorée.",
    "MISSING_RATE_SOURCE": "Référence source du taux absente ; observation ignorée.",
    "INVALID_RATE_VALUE": "Valeur du taux non numérique ; observation ignorée.",
    "NON_POSITIVE_RATE": "Valeur du taux nulle, négative ou non finie ; observation ignorée.",
    "DUPLICATE_RATE_DATE": "Plusieurs valeurs candidates pour cette date ; toutes ignorées.",
}


class SchemaError(ValueError):
    """A required input column is absent or ambiguous."""


@dataclass(frozen=True)
class Rate:
    day: date
    value: Decimal
    source_url: str


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Source introuvable : {path}. Refaire l'extraction ou vérifier --sales/--rates.")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise SchemaError(f"Colonnes CSV dupliquées dans {path} : {columns}")
        missing = required - set(columns)
        if missing:
            raise SchemaError(f"Colonnes indispensables absentes dans {path} : {', '.join(sorted(missing))}")
        return list(reader)


def positive_id(value: object) -> str | None:
    text = str(value if value is not None else "").strip()
    if not re.fullmatch(r"[0-9]+", text) or int(text) <= 0:
        return None
    return str(int(text))


def sale_day(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).date()
    except ValueError:
        return None


def money(value: object) -> tuple[Decimal | None, str | None]:
    text = str(value if value is not None else "").strip()
    if not text:
        return None, "MISSING_PRICE"
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None, "INVALID_PRICE"
    if not amount.is_finite():
        return None, "INVALID_PRICE"
    if amount <= 0:
        return None, "NON_POSITIVE_PRICE"
    try:
        rounded = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, "INVALID_PRICE"
    if rounded <= 0:
        return None, "PRICE_ROUNDS_TO_ZERO"
    return rounded, None


def load_rates(rows: list[dict[str, str]]) -> tuple[list[Rate], list[dict[str, object]]]:
    candidates: list[tuple[int, Rate]] = []
    issues: list[dict[str, object]] = []
    for number, row in enumerate(rows, 2):
        try:
            day = date.fromisoformat(str(row.get("rate_date") or "").strip())
        except ValueError:
            issues.append({"source_row": number, "code": "INVALID_RATE_DATE"})
            continue
        if (str(row.get("quote_currency") or "").strip().upper() != "USD"
                or str(row.get("base_currency") or "").strip().upper() != "EUR"
                or str(row.get("series_key") or "").strip() != RATE_SERIES):
            issues.append({"source_row": number, "code": "INVALID_RATE_SERIES_OR_PAIR", "rate_date": str(day)})
            continue
        if str(row.get("observation_status") or "").strip().upper() != "A":
            issues.append({"source_row": number, "code": "RATE_NOT_PUBLISHED_AS_VALID", "rate_date": str(day)})
            continue
        source_url = str(row.get("source_url") or "").strip()
        if not source_url:
            issues.append({"source_row": number, "code": "MISSING_RATE_SOURCE", "rate_date": str(day)})
            continue
        try:
            raw_value = row.get("usd_per_eur")
            value = Decimal(str(raw_value if raw_value is not None else "").strip())
        except InvalidOperation:
            issues.append({"source_row": number, "code": "INVALID_RATE_VALUE", "rate_date": str(day)})
            continue
        if not value.is_finite() or value <= 0:
            issues.append({"source_row": number, "code": "NON_POSITIVE_RATE", "rate_date": str(day)})
            continue
        candidates.append((number, Rate(day, value, source_url)))
    counts = Counter(rate.day for _, rate in candidates)
    usable = []
    for number, rate in candidates:
        if counts[rate.day] > 1:
            issues.append({"source_row": number, "code": "DUPLICATE_RATE_DATE", "rate_date": str(rate.day)})
        else:
            usable.append(rate)
    issues.sort(key=lambda issue: issue["source_row"])
    for issue in issues:
        issue["explanation"] = RATE_ISSUE_EXPLANATIONS[issue["code"]]
    return sorted(usable, key=lambda rate: rate.day), issues


def choose_rate(day: date, rates: list[Rate], max_age_days: int = 7) -> tuple[Rate | None, str | None, int | None]:
    if not 0 <= max_age_days <= 7:
        raise ValueError("La fenêtre BCE doit être entre 0 et 7 jours calendaires.")
    dates = [rate.day for rate in rates]
    index = bisect_right(dates, day) - 1
    if index < 0:
        return None, "NO_PRIOR_RATE", None
    candidate = rates[index]
    age = (day - candidate.day).days
    if age > max_age_days:
        return None, "RATE_TOO_OLD", age
    return candidate, None, age


def classify_sales(
    rows: list[dict[str, str]], rates: list[Rate], start: date, end: date, max_age_days: int = 7
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    if start >= end:
        raise ValueError("La fin de période doit suivre le début.")
    if not 0 <= max_age_days <= 7:
        raise ValueError("La fenêtre BCE doit être entre 0 et 7 jours calendaires.")
    ids = Counter(normalized for row in rows if (normalized := positive_id(row.get("order_item_id"))))
    accepted: list[dict[str, str]] = []
    quarantine: list[dict[str, str]] = []
    status_counts = Counter({status: 0 for status in STATUSES})
    reason_counts = Counter()
    total_eur = Decimal("0.00")

    for source_row, row in enumerate(rows, 2):
        normalized: dict[str, str] = {"source_row": str(source_row)}
        reason = None
        line_id = positive_id(row.get("order_item_id"))
        if not str(row.get("order_item_id") or "").strip():
            reason = "MISSING_LINE_ID"
        elif line_id is None:
            reason = "INVALID_LINE_ID"
        elif ids[line_id] > 1:
            reason = "DUPLICATE_LINE_ID"
        if reason is None:
            normalized["order_item_id"] = line_id  # type: ignore[assignment]
            for key, missing_code, invalid_code in (
                ("order_id", "MISSING_ORDER_ID", "INVALID_ORDER_ID"),
                ("product_id", "MISSING_PRODUCT_ID", "INVALID_PRODUCT_ID"),
            ):
                raw = str(row.get(key) or "").strip()
                parsed = positive_id(raw)
                if not raw:
                    reason = missing_code
                    break
                if parsed is None:
                    reason = invalid_code
                    break
                normalized[key] = parsed
        if reason is None:
            day = sale_day(row.get("sale_date_utc"))
            if day is None:
                reason = "INVALID_SALE_DATE"
            elif not start <= day < end:
                reason = "SALE_OUTSIDE_PERIOD"
            else:
                normalized["sale_date_utc"] = str(day)
        if reason is None:
            amount, price_reason = money(row.get("sale_price"))
            if price_reason:
                reason = price_reason
            else:
                normalized["amount_source_usd"] = format(amount, ".2f")  # type: ignore[arg-type]

        if reason is not None:
            status = REJECTED
        else:
            order_status = str(row.get("order_status") or "").strip().casefold()
            item_status = str(row.get("item_status") or "").strip().casefold()
            if not order_status:
                reason, status = "MISSING_ORDER_STATUS", REVIEW
            elif not item_status:
                reason, status = "MISSING_ITEM_STATUS", REVIEW
            elif order_status != item_status:
                reason, status = "STATUS_CONFLICT", REVIEW
            elif order_status == "cancelled":
                reason, status = "CANCELLED_ORDER", EXCLUDED
            elif order_status == "returned":
                reason, status = "RETURNED_ORDER", EXCLUDED
            elif order_status == "processing":
                reason, status = "PROCESSING_ORDER", REVIEW
            elif order_status not in {"complete", "shipped"}:
                reason, status = "UNKNOWN_ORDER_STATUS", REVIEW
            elif not str(row.get("product_category") or "").strip():
                reason, status = "MISSING_PRODUCT_CATEGORY", REVIEW
            else:
                rate, rate_reason, age = choose_rate(day, rates, max_age_days)  # type: ignore[arg-type]
                if rate_reason:
                    reason, status = rate_reason, REVIEW
                else:
                    status = ACCEPTED
                    eur = (amount / rate.value).quantize(CENT, rounding=ROUND_HALF_UP)  # type: ignore[operator,union-attr]
                    total_eur += eur
                    accepted.append({
                        "order_id": normalized["order_id"],
                        "order_item_id": normalized["order_item_id"],
                        "product_id": normalized["product_id"],
                        "product_category": str(row["product_category"]).strip(),
                        "sale_date_utc": normalized["sale_date_utc"],
                        "order_status": order_status.upper(),
                        "amount_source_usd": normalized["amount_source_usd"],
                        "source_currency_assumption": "USD (POC assumption, unverified)",
                        "rate_date": str(rate.day),  # type: ignore[union-attr]
                        "usd_per_eur": format(rate.value, "f"),  # type: ignore[union-attr]
                        "rate_age_days": str(age),
                        "amount_eur": format(eur, ".2f"),
                        "rate_source_url": rate.source_url,  # type: ignore[union-attr]
                    })
        status_counts[status] += 1
        if status != ACCEPTED:
            reason_counts[reason] += 1
            quarantine.append({"source_row": str(source_row), **{key: str(value or "") for key, value in row.items()},
                               "normalized_order_id": normalized.get("order_id", ""),
                               "normalized_order_item_id": normalized.get("order_item_id", ""),
                               "normalized_product_id": normalized.get("product_id", ""),
                               "normalized_sale_date_utc": normalized.get("sale_date_utc", ""),
                               "normalized_amount_source_usd": normalized.get("amount_source_usd", ""),
                               "status": status, "reason_code": reason,
                               "reason_explanation": REASONS[reason]})
    accepted.sort(key=lambda row: int(row["order_item_id"]))
    if len({row["order_item_id"] for row in accepted}) != len(accepted):
        raise AssertionError("Le jeu final contient une clé de ligne doublonnée")
    if sum(status_counts.values()) != len(rows) or len(accepted) + len(quarantine) != len(rows):
        raise AssertionError("Les volumes ne comptabilisent pas chaque ligne une fois")
    report = {"input_sales_rows": len(rows), "status_counts": {status: status_counts[status] for status in STATUSES},
              "reason_counts": dict(sorted(reason_counts.items())), "final_rows": len(accepted),
              "quarantine_rows": len(quarantine), "accounted_rows": sum(status_counts.values()),
              "accepted_amount_eur_sum": format(total_eur, ".2f")}
    return accepted, quarantine, report
