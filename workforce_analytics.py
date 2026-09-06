"""Deterministic normalization for DART workforce analytics.

The module converts OpenDART employee and executive rows into company-level
metrics.  It deliberately does not return executive names, birth months, or
career text in the normalized result.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import date
from typing import Any, Mapping, Sequence


MAX_SOURCE_TEXT_CHARS = 10_000
MAX_NUMERIC_TEXT_CHARS = 128
MAX_REASONABLE_HEADCOUNT = 1_000_000_000
MAX_REASONABLE_ABSOLUTE_VALUE = 1e21
MAX_REASONABLE_TENURE_MONTHS = 1_200


_MISSING = {"", "-", "–", "—", "-0", "N/A", "NA", "null", "None"}


def clean_text(value: Any) -> str:
    text = str("" if value is None else value)[:MAX_SOURCE_TEXT_CHARS]
    safe = "".join(
        " " if character.isspace() else character
        for character in text
        if character.isspace()
        or unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )
    return re.sub(
        r"\s+",
        " ",
        safe,
    ).strip()


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = clean_text(value).replace(",", "")
    if len(text) > MAX_NUMERIC_TEXT_CHARS:
        return None
    if text in _MISSING:
        return None
    negative = False
    if "(" in text or ")" in text:
        if not (
            text.startswith("(")
            and text.endswith(")")
            and text.count("(") == 1
            and text.count(")") == 1
        ):
            return None
        negative = True
        text = text[1:-1].strip()
        if text.startswith(("+", "-")):
            return None
    try:
        result = float(text)
    except ValueError:
        return None
    if not math.isfinite(result) or abs(result) > MAX_REASONABLE_ABSOLUTE_VALUE:
        return None
    return -result if negative else result


def parse_count(value: Any) -> int | None:
    number = parse_number(value)
    return (
        int(number)
        if number is not None
        and 0 <= number <= MAX_REASONABLE_HEADCOUNT
        and number.is_integer()
        else None
    )


def _parse_nonnegative_number(value: Any) -> float | None:
    number = parse_number(value)
    return number if number is not None and number >= 0 else None


def _parse_tenure_years(value: Any) -> float | None:
    number = parse_number(value)
    if number is not None:
        return (
            number
            if 0 <= number <= MAX_REASONABLE_TENURE_MONTHS / 12
            else None
        )
    months = parse_months(value)
    return months / 12 if months is not None and months >= 0 else None


def parse_months(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    year_match = re.search(r"(?<![0-9A-Za-z.])(-?\d+(?:\.\d+)?)\s*년", text)
    month_match = re.search(r"(?<![0-9A-Za-z.])(-?\d+(?:\.\d+)?)\s*개월", text)
    if year_match and month_match:
        years = parse_number(year_match.group(1))
        months = parse_number(month_match.group(1))
        total = (
            years * 12 + months
            if years is not None
            and months is not None
            and years >= 0
            and months >= 0
            else None
        )
        return total if total is not None and total <= MAX_REASONABLE_TENURE_MONTHS else None
    if month_match:
        months = parse_number(month_match.group(1))
        return (
            months
            if months is not None and 0 <= months <= MAX_REASONABLE_TENURE_MONTHS
            else None
        )
    if year_match:
        years = parse_number(year_match.group(1))
        months = years * 12 if years is not None and years >= 0 else None
        return months if months is not None and months <= MAX_REASONABLE_TENURE_MONTHS else None
    months = parse_number(text)
    return (
        months
        if months is not None and 0 <= months <= MAX_REASONABLE_TENURE_MONTHS
        else None
    )


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


def _sum_complete(rows: Sequence[Mapping[str, Any]], key: str, parser) -> float | int | None:
    """Sum an additive disclosure only when every selected row is covered."""

    if not rows:
        return None
    values = [parser(row.get(key)) for row in rows]
    if any(value is None for value in values):
        return None
    try:
        total = sum(value for value in values if value is not None)
    except OverflowError:
        return None
    return total if not isinstance(total, float) or math.isfinite(total) else None


def _weighted_average(pairs: Sequence[tuple[float, int]]) -> float | None:
    total_weight = sum(weight for _, weight in pairs)
    if not total_weight:
        return None
    try:
        result = math.fsum(value * (weight / total_weight) for value, weight in pairs)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _finite_average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    try:
        result = math.fsum(value / len(values) for value in values)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) else None


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
        key = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str)
        unique[key] = row
    return list(unique.values()), "gender_total"


def summarize_employees(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected, aggregation_mode = select_employee_rows(rows)
    total = _sum_complete(selected, "sm", parse_count)
    regular = _sum_complete(selected, "rgllbr_co", parse_count)
    contract = _sum_complete(selected, "cnttk_co", parse_count)
    short_time_regular = _sum_complete(
        selected, "rgllbr_abacpt_labrr_co", parse_count
    )
    short_time_contract = _sum_complete(
        selected, "cnttk_abacpt_labrr_co", parse_count
    )
    annual_salary_total = _sum_complete(
        selected, "fyer_salary_totamt", _parse_nonnegative_number
    )

    tenure_pairs = [
        (value, count)
        for row in selected
        if (value := _parse_tenure_years(row.get("avrg_cnwk_sdytrn"))) is not None
        and (count := parse_count(row.get("sm"))) is not None
    ]
    salary_pairs = [
        (value, count)
        for row in selected
        if (value := _parse_nonnegative_number(row.get("jan_salary_am"))) is not None
        and (count := parse_count(row.get("sm"))) is not None
    ]
    tenure_covered = sum(count for _, count in tenure_pairs)
    salary_covered = sum(count for _, count in salary_pairs)
    tenure_complete = bool(selected) and len(tenure_pairs) == len(selected)
    salary_complete = bool(selected) and len(salary_pairs) == len(selected)
    average_tenure_years = (
        _weighted_average(tenure_pairs) if tenure_complete and tenure_covered else None
    )
    average_salary = (
        _weighted_average(salary_pairs)
        if salary_complete and salary_covered
        else annual_salary_total / total
        if annual_salary_total is not None and total
        else None
    )
    average_salary_basis = (
        "disclosed_average_headcount_weighted"
        if salary_complete and salary_covered
        else "annual_salary_total_per_employee_fallback"
        if annual_salary_total is not None and total
        else "not_available"
    )

    missing = []
    field_parsers = {
        "sm": parse_count,
        "rgllbr_co": parse_count,
        "cnttk_co": parse_count,
        "avrg_cnwk_sdytrn": _parse_tenure_years,
        "jan_salary_am": _parse_nonnegative_number,
    }
    for field, parser in field_parsers.items():
        if not any(parser(row.get(field)) is not None for row in selected):
            missing.append(field)
    warnings = []
    invalid_field_parsers = {
        **field_parsers,
        "fyer_salary_totamt": _parse_nonnegative_number,
    }
    for field, parser in invalid_field_parsers.items():
        if any(
            clean_text(row.get(field)) and parser(row.get(field)) is None
            for row in selected
        ):
            warnings.append(f"{field}_invalid_rows")
    if aggregation_mode == "all_rows_fallback" and len(selected) > 1:
        warnings.append("gender_total_not_returned_all_rows_used")
    additive_fields = {
        "sm": parse_count,
        "rgllbr_co": parse_count,
        "cnttk_co": parse_count,
        "fyer_salary_totamt": _parse_nonnegative_number,
    }
    for field, parser in additive_fields.items():
        coverage = sum(parser(row.get(field)) is not None for row in selected)
        if 0 < coverage < len(selected):
            warnings.append(f"{field}_partial_rows")
    if selected and not tenure_complete and tenure_pairs:
        warnings.append("average_tenure_partial_headcount")
    if selected and not salary_complete and salary_pairs:
        warnings.append("average_salary_partial_headcount")
    if tenure_complete and not tenure_covered:
        warnings.append("average_tenure_zero_headcount")
    if salary_complete and not salary_covered:
        warnings.append("average_salary_zero_headcount")
    if any(
        _parse_nonnegative_number(row.get("fyer_salary_totamt")) is not None
        for row in selected
    ) and annual_salary_total is None:
        warnings.append("annual_salary_total_not_finite")
    if tenure_covered and average_tenure_years is None:
        warnings.append("average_tenure_not_finite")
    if salary_covered and average_salary is None:
        warnings.append("average_salary_not_finite")
    employment_counts_consistent = not (
        total is not None
        and (
            (regular is not None and regular > total)
            or (contract is not None and contract > total)
            or (
                regular is not None
                and contract is not None
                and regular + contract > total
            )
        )
    )
    if not employment_counts_consistent:
        warnings.append("employment_type_counts_exceed_total")
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
            "metric_basis": {"average_salary": "not_available"},
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
            "regular_share": (
                regular / total * 100
                if employment_counts_consistent and regular is not None and total
                else None
            ),
            "contract_share": (
                contract / total * 100
                if employment_counts_consistent and contract is not None and total
                else None
            ),
        },
        "metric_basis": {"average_salary": average_salary_basis},
        "aggregation_mode": aggregation_mode,
        "quality": _quality("partial" if missing or warnings else "complete", missing, warnings),
    }


def summarize_unregistered_pay(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row, Mapping)]
    count = _sum_complete(valid, "nmpr", parse_count)
    total = _sum_complete(valid, "fyer_salary_totamt", _parse_nonnegative_number)
    average_pairs = [
        (average, row_count)
        for row in valid
        if (average := _parse_nonnegative_number(row.get("jan_salary_am"))) is not None
        and (row_count := parse_count(row.get("nmpr"))) is not None
    ]
    covered_count = sum(row_count for _, row_count in average_pairs)
    average_complete = bool(valid) and len(average_pairs) == len(valid)
    average = (
        _weighted_average(average_pairs)
        if average_complete and covered_count
        else total / count
        if total is not None and count
        else None
    )
    missing = []
    if not valid:
        missing.append("unregistered_pay_rows")
    if count is None:
        missing.append("nmpr")
    warnings = []
    for field, parser in (
        ("nmpr", parse_count),
        ("fyer_salary_totamt", _parse_nonnegative_number),
    ):
        coverage = sum(parser(row.get(field)) is not None for row in valid)
        if 0 < coverage < len(valid):
            warnings.append(f"{field}_partial_rows")
    if valid and not average_complete and average_pairs:
        warnings.append("average_salary_partial_headcount")
    if average_complete and not covered_count:
        warnings.append("average_salary_zero_headcount")
    if any(
        _parse_nonnegative_number(row.get("fyer_salary_totamt")) is not None
        for row in valid
    ) and total is None:
        warnings.append("unregistered_pay_total_not_finite")
    if covered_count and average is None:
        warnings.append("unregistered_average_salary_not_finite")
    return {
        "metrics": {
            "unregistered_pay_count": count,
            "unregistered_pay_total": total,
            "unregistered_average_salary": average,
        },
        "quality": _quality(
            "no_data" if not valid else "partial" if missing or warnings else "complete",
            missing,
            warnings,
        ),
    }


def _is_registered(value: Any) -> bool:
    text = clean_text(value)
    return "미등기" not in text and (
        "등기" in text
        or any(
            category in text
            for category in ("사내이사", "사외이사", "기타비상무이사")
        )
    )


def _is_unregistered(value: Any) -> bool:
    return "미등기" in clean_text(value)


def _registration_kind_known(row: Mapping[str, Any]) -> bool:
    value = row.get("rgist_exctv_at")
    return _is_registered(value) or _is_unregistered(value)


def _executive_role_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        clean_text(row.get(key))
        for key in ("rgist_exctv_at", "ofcps", "chrg_job")
    )


def _is_outside_director(row: Mapping[str, Any]) -> bool:
    return "사외이사" in _executive_role_text(row)


def _is_inside_director(row: Mapping[str, Any]) -> bool:
    role = _executive_role_text(row)
    return "사내이사" in role or "대표이사" in role


def _registered_director_role_known(row: Mapping[str, Any]) -> bool:
    return (
        _is_inside_director(row)
        or _is_outside_director(row)
        or "기타비상무이사" in _executive_role_text(row)
    )


def _is_ceo(row: Mapping[str, Any]) -> bool:
    return "대표이사" in clean_text(row.get("ofcps")) or "대표이사" in clean_text(row.get("chrg_job"))


def _is_female(row: Mapping[str, Any]) -> bool:
    return clean_text(row.get("sexdstn")).casefold() in {
        "f",
        "female",
        "여",
        "여성",
        "여자",
    }


def _gender_kind_known(row: Mapping[str, Any]) -> bool:
    return clean_text(row.get("sexdstn")).casefold() in {
        "f",
        "female",
        "m",
        "male",
        "남",
        "남성",
        "남자",
        "여",
        "여성",
        "여자",
    }


def _is_full_time(row: Mapping[str, Any]) -> bool:
    value = clean_text(row.get("fte_at"))
    return "상근" in value and "비상근" not in value


def _is_part_time(row: Mapping[str, Any]) -> bool:
    return "비상근" in clean_text(row.get("fte_at"))


def _employment_kind_known(row: Mapping[str, Any]) -> bool:
    return _is_full_time(row) or _is_part_time(row)


def summarize_executives(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row, Mapping)]
    if as_of is None:
        as_of = parse_date(_first_value(valid, "stlm_dt"))

    registration_complete = bool(valid) and all(_registration_kind_known(row) for row in valid)
    role_complete = bool(valid) and all(
        clean_text(row.get("ofcps")) or clean_text(row.get("chrg_job"))
        for row in valid
    )
    employment_complete = bool(valid) and all(
        _employment_kind_known(row) for row in valid
    )
    gender_complete = bool(valid) and all(_gender_kind_known(row) for row in valid)
    registered_rows = [row for row in valid if _is_registered(row.get("rgist_exctv_at"))]
    tenure_values = [parse_months(row.get("hffc_pd")) for row in valid]
    tenure_values = [value for value in tenure_values if value is not None and value >= 0]
    term_end_dates = [parse_date(row.get("tenure_end_on")) for row in valid]
    parsed_term_end_dates = [value for value in term_end_dates if value is not None]
    try:
        twelve_month_limit = as_of.replace(year=as_of.year + 1) if as_of else None
    except ValueError:
        twelve_month_limit = as_of.replace(year=as_of.year + 1, day=28) if as_of else None
    expiring = [
        end_date
        for end_date in parsed_term_end_dates
        if as_of and twelve_month_limit and as_of <= end_date <= twelve_month_limit
    ]
    tenure_complete = bool(valid) and len(tenure_values) == len(valid)
    term_end_complete = bool(valid) and len(parsed_term_end_dates) == len(valid)
    registered_roles_complete = registration_complete and all(
        _registered_director_role_known(row) for row in registered_rows
    )

    missing = []
    for field in (
        "rgist_exctv_at",
        "fte_at",
        "ofcps",
        "sexdstn",
        "hffc_pd",
        "tenure_end_on",
    ):
        if field == "ofcps":
            covered = any(
                clean_text(row.get("ofcps")) or clean_text(row.get("chrg_job"))
                for row in valid
            )
        else:
            covered = any(clean_text(row.get(field)) for row in valid)
        if not covered:
            missing.append(field)
    warnings = []
    if valid and not tenure_values:
        warnings.append("tenure_not_parseable")
    elif valid and not tenure_complete:
        warnings.append("tenure_partial_executive_count")
    if tenure_values and _finite_average(tenure_values) is None:
        warnings.append("average_tenure_not_finite")
    if valid and not parsed_term_end_dates:
        warnings.append("term_end_not_parseable")
    elif valid and not term_end_complete:
        warnings.append("term_end_partial_executive_count")
    if valid and not registration_complete and any(
        clean_text(row.get("rgist_exctv_at")) for row in valid
    ):
        warnings.append("registration_partial_executive_count")
    if valid and not role_complete and any(
        clean_text(row.get("ofcps")) or clean_text(row.get("chrg_job"))
        for row in valid
    ):
        warnings.append("role_partial_executive_count")
    if valid and not employment_complete and any(
        clean_text(row.get("fte_at")) for row in valid
    ):
        warnings.append("employment_partial_executive_count")
    if valid and not gender_complete and any(
        clean_text(row.get("sexdstn")) for row in valid
    ):
        warnings.append("gender_partial_executive_count")
    if valid and as_of is None:
        warnings.append("as_of_missing")

    def count_if(predicate) -> int | None:
        return sum(1 for row in valid if predicate(row)) if valid else None

    metrics = {
        "executives_total": len(valid) if valid else None,
        "registered_executives": len(registered_rows) if registration_complete else None,
        "unregistered_executives": (
            count_if(lambda row: _is_unregistered(row.get("rgist_exctv_at")))
            if registration_complete
            else None
        ),
        "inside_directors": (
            sum(1 for row in registered_rows if _is_inside_director(row))
            if registered_roles_complete
            else None
        ),
        "outside_directors": (
            sum(1 for row in registered_rows if _is_outside_director(row))
            if registered_roles_complete
            else None
        ),
        "ceo_count": count_if(_is_ceo) if role_complete else None,
        "full_time_executives": count_if(_is_full_time) if employment_complete else None,
        "part_time_executives": count_if(_is_part_time) if employment_complete else None,
        "female_executives": count_if(_is_female) if gender_complete else None,
        "average_tenure_months": (
            _finite_average(tenure_values) if tenure_complete else None
        ),
        "long_tenure_executives": (
            sum(1 for value in tenure_values if value >= 60) if tenure_complete else None
        ),
        "term_expiring_within_12_months": (
            len(expiring) if term_end_complete and as_of else None
        ),
        "registered_share": (
            len(registered_rows) / len(valid) * 100 if registration_complete else None
        ),
        "outside_director_share": (
            len([row for row in registered_rows if _is_outside_director(row)])
            / len(registered_rows)
            * 100
            if registered_roles_complete and registered_rows
            else None
        ),
        "female_share": (
            sum(1 for row in valid if _is_female(row)) / len(valid) * 100
            if gender_complete
            else None
        ),
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
        "metric_basis": employees["metric_basis"],
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
    "MAX_REASONABLE_TENURE_MONTHS",
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
