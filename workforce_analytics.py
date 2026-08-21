"""Deterministic normalization for DART workforce analytics.

The module converts OpenDART employee and executive rows into company-level
metrics.  It deliberately does not return executive names, birth months, or
career text in the normalized result.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Mapping, Sequence


_MISSING = {"", "-", "–", "—", "-0", "N/A", "NA", "null", "None"}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = clean_text(value).replace(",", "")
    if text in _MISSING:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        result = float(text)
    except ValueError:
        return None
    return -result if negative else result


def parse_count(value: Any) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_months(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    year_match = re.search(r"(-?\d+(?:\.\d+)?)\s*년", text)
    month_match = re.search(r"(-?\d+(?:\.\d+)?)\s*개월", text)
    if year_match and month_match:
        return float(year_match.group(1)) * 12 + float(month_match.group(1))
    if month_match:
        return float(month_match.group(1))
    if year_match:
        return float(year_match.group(1)) * 12
    return parse_number(text)


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"(20\d{2})[년.\-/ ]+(\d{1,2})[월.\-/ ]+(\d{1,2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _first_value(rows: Sequence[Mapping[str, Any]], key: str) -> Any:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _quality(status: str, missing_fields: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "missing_fields": sorted(set(missing_fields)),
        "warnings": sorted(set(warnings)),
    }


def select_employee_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], str]:
    """Prefer non-overlapping gender-total rows when the API returns them."""

    valid = [row for row in rows if isinstance(row, Mapping)]
    totals = [
        row
        for row in valid
        if "성별합계" in clean_text(row.get("fo_bbm"))
        or clean_text(row.get("sexdstn")) in {"합계", "전체"}
    ]
    if not totals:
        return valid, "all_rows_fallback"

    unique: dict[str, Mapping[str, Any]] = {}
    for row in totals:
        key = clean_text(row.get("sexdstn")) or str(len(unique))
        unique[key] = row
    return list(unique.values()), "gender_total"


def summarize_employees(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected, aggregation_mode = select_employee_rows(rows)
    total = sum(parse_count(row.get("sm")) or 0 for row in selected) or None
    regular = sum(parse_count(row.get("rgllbr_co")) or 0 for row in selected) or None
    contract = sum(parse_count(row.get("cnttk_co")) or 0 for row in selected) or None
    short_time_regular = sum(parse_count(row.get("rgllbr_abacpt_labrr_co")) or 0 for row in selected) or None
    short_time_contract = sum(parse_count(row.get("cnttk_abacpt_labrr_co")) or 0 for row in selected) or None
    annual_salary_total = sum(parse_number(row.get("fyer_salary_totamt")) or 0 for row in selected) or None

    tenure_weight = sum(
        (parse_number(row.get("avrg_cnwk_sdytrn")) or 0) * (parse_count(row.get("sm")) or 0)
        for row in selected
    )
    salary_weight = sum(
        (parse_number(row.get("jan_salary_am")) or 0) * (parse_count(row.get("sm")) or 0)
        for row in selected
    )
    average_tenure_years = tenure_weight / total if total else None
    average_salary = (
        annual_salary_total / total
        if annual_salary_total is not None and total
        else salary_weight / total
        if salary_weight and total
        else None
    )

    missing = []
    for field in ("sm", "rgllbr_co", "cnttk_co", "avrg_cnwk_sdytrn", "jan_salary_am"):
        if not any(parse_number(row.get(field)) is not None for row in selected):
            missing.append(field)
    warnings = []
    if aggregation_mode == "all_rows_fallback" and len(selected) > 1:
        warnings.append("gender_total_not_returned_all_rows_used")
    if not selected:
        return {
            "metrics": {
                "employees_total": None,
                "regular_employees": None,
                "contract_employees": None,
                "regular_short_time": None,
                "contract_short_time": None,
                "average_tenure_years": None,
                "annual_salary_total": None,
                "average_salary": None,
                "regular_share": None,
                "contract_share": None,
            },
            "aggregation_mode": aggregation_mode,
            "quality": _quality("no_data", ["employee_rows"], []),
        }

    return {
        "metrics": {
            "employees_total": total,
            "regular_employees": regular,
            "contract_employees": contract,
            "regular_short_time": short_time_regular,
            "contract_short_time": short_time_contract,
            "average_tenure_years": average_tenure_years,
            "annual_salary_total": annual_salary_total,
            "average_salary": average_salary,
            "regular_share": regular / total * 100 if regular is not None and total else None,
            "contract_share": contract / total * 100 if contract is not None and total else None,
        },
        "aggregation_mode": aggregation_mode,
        "quality": _quality("partial" if missing else "complete", missing, warnings),
    }


def summarize_unregistered_pay(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row, Mapping)]
    count = sum(parse_count(row.get("nmpr")) or 0 for row in valid) or None
    total = sum(parse_number(row.get("fyer_salary_totamt")) or 0 for row in valid) or None
    average_source = sum(
        (parse_number(row.get("jan_salary_am")) or 0) * (parse_count(row.get("nmpr")) or 0)
        for row in valid
    )
    average = average_source / count if average_source and count else total / count if total and count else None
    missing = []
    if not valid:
        missing.append("unregistered_pay_rows")
    if count is None:
        missing.append("nmpr")
    return {
        "metrics": {
            "unregistered_pay_count": count,
            "unregistered_pay_total": total,
            "unregistered_average_salary": average,
        },
        "quality": _quality("no_data" if not valid else "partial" if missing else "complete", missing, []),
    }


def _is_registered(value: Any) -> bool:
    text = clean_text(value)
    return "등기" in text and "미등기" not in text


def _is_unregistered(value: Any) -> bool:
    return "미등기" in clean_text(value)


def _is_outside_director(row: Mapping[str, Any]) -> bool:
    return "사외이사" in clean_text(row.get("ofcps")) or "사외이사" in clean_text(row.get("chrg_job"))


def _is_inside_director(row: Mapping[str, Any]) -> bool:
    return "사내이사" in clean_text(row.get("ofcps"))


def _is_ceo(row: Mapping[str, Any]) -> bool:
    return "대표이사" in clean_text(row.get("ofcps")) or "대표이사" in clean_text(row.get("chrg_job"))


def _is_female(row: Mapping[str, Any]) -> bool:
    return clean_text(row.get("sexdstn")) in {"여", "여성", "female"}


def _is_full_time(row: Mapping[str, Any]) -> bool:
    value = clean_text(row.get("fte_at"))
    return "상근" in value and "비상근" not in value


def _is_part_time(row: Mapping[str, Any]) -> bool:
    return "비상근" in clean_text(row.get("fte_at"))


def summarize_executives(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row, Mapping)]
    if as_of is None:
        as_of = parse_date(_first_value(valid, "stlm_dt")) or date.today()

    registered_rows = [row for row in valid if _is_registered(row.get("rgist_exctv_at"))]
    tenure_values = [parse_months(row.get("hffc_pd")) for row in valid]
    tenure_values = [value for value in tenure_values if value is not None and value >= 0]
    expiring = []
    for row in valid:
        end_date = parse_date(row.get("tenure_end_on"))
        if end_date and as_of <= end_date <= as_of + timedelta(days=366):
            expiring.append(row)

    missing = []
    for field in ("rgist_exctv_at", "fte_at", "ofcps", "hffc_pd", "tenure_end_on"):
        if not any(clean_text(row.get(field)) for row in valid):
            missing.append(field)
    warnings = []
    if valid and not tenure_values:
        warnings.append("tenure_not_parseable")
    if valid and not any(parse_date(row.get("tenure_end_on")) for row in valid):
        warnings.append("term_end_not_parseable")

    metrics = {
        "executives_total": len(valid) or None,
        "registered_executives": len(registered_rows) or None,
        "unregistered_executives": sum(1 for row in valid if _is_unregistered(row.get("rgist_exctv_at"))) or None,
        "inside_directors": sum(1 for row in registered_rows if _is_inside_director(row)) or None,
        "outside_directors": sum(1 for row in registered_rows if _is_outside_director(row)) or None,
        "ceo_count": sum(1 for row in valid if _is_ceo(row)) or None,
        "full_time_executives": sum(1 for row in valid if _is_full_time(row)) or None,
        "part_time_executives": sum(1 for row in valid if _is_part_time(row)) or None,
        "female_executives": sum(1 for row in valid if _is_female(row)) or None,
        "average_tenure_months": sum(tenure_values) / len(tenure_values) if tenure_values else None,
        "long_tenure_executives": sum(1 for value in tenure_values if value >= 60) or None,
        "term_expiring_within_12_months": len(expiring) or None,
        "registered_share": len(registered_rows) / len(valid) * 100 if valid else None,
        "outside_director_share": len([row for row in registered_rows if _is_outside_director(row)]) / len(registered_rows) * 100 if registered_rows else None,
        "female_share": sum(1 for row in valid if _is_female(row)) / len(valid) * 100 if valid else None,
    }
    if not valid:
        return {
            "metrics": {key: None for key in metrics},
            "quality": _quality("no_data", ["executive_rows"], []),
        }
    return {
        "metrics": metrics,
        "quality": _quality("partial" if missing or warnings else "complete", missing, warnings),
    }


def build_workforce_summary(
    *,
    employee_rows: Sequence[Mapping[str, Any]],
    executive_rows: Sequence[Mapping[str, Any]],
    unregistered_pay_rows: Sequence[Mapping[str, Any]],
    as_of: date | None = None,
) -> dict[str, Any]:
    employees = summarize_employees(employee_rows)
    executives = summarize_executives(executive_rows, as_of=as_of)
    pay = summarize_unregistered_pay(unregistered_pay_rows)
    metrics = {**employees["metrics"], **executives["metrics"], **pay["metrics"]}
    qualities = [employees["quality"], executives["quality"], pay["quality"]]
    statuses = {quality["status"] for quality in qualities}
    status = "error" if "error" in statuses else "complete" if statuses == {"complete"} else "no_data" if statuses == {"no_data"} else "partial"
    return {
        "metrics": metrics,
        "aggregation_mode": employees["aggregation_mode"],
        "quality": {
            "status": status,
            "missing_fields": sorted({field for quality in qualities for field in quality["missing_fields"]}),
            "warnings": sorted({warning for quality in qualities for warning in quality["warnings"]}),
        },
        "component_quality": {
            "employees": employees["quality"],
            "executives": executives["quality"],
            "unregistered_pay": pay["quality"],
        },
    }


__all__ = [
    "build_workforce_summary",
    "clean_text",
    "parse_count",
    "parse_date",
    "parse_months",
    "parse_number",
    "select_employee_rows",
    "summarize_employees",
    "summarize_executives",
    "summarize_unregistered_pay",
]
