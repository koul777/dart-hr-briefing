from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from agent_orchestration import WorkforceAgentOrchestrator


SOURCE_ROOT = Path(__file__).resolve().parent
CLASSROOM_FIXTURE = SOURCE_ROOT / "seed" / "classroom_workforce_2024_11011.json"
CLASSROOM_WATERMARK = "SAMPLE — SYNTHETIC DATA"
CLASSROOM_FIXTURE_ID = "dart-hr-briefing-classroom-v1"
SYNTHETIC_REFERENCE_SCHEME = "urn:dart-hr-briefing:synthetic"
_SYNTHETIC_REFERENCE_PATTERN = re.compile(r"CLASSROOM-9\d{7}")
_INTERNAL_RECEIPT_PREFIX = "20991231"

FINANCIAL_METRICS = {
    "assets",
    "liabilities",
    "equity",
    "current_assets",
    "current_liabilities",
    "cash",
    "revenue",
    "operating_profit",
    "net_income",
    "operating_margin",
    "net_margin",
    "debt_ratio",
    "current_ratio",
}
PEOPLE_METRICS = {
    "employees_total",
    "regular_employees",
    "contract_employees",
    "regular_short_time",
    "contract_short_time",
    "average_tenure_years",
    "annual_salary_total",
    "average_salary",
    "regular_share",
    "contract_share",
    "executives_total",
    "registered_executives",
    "unregistered_executives",
    "inside_directors",
    "outside_directors",
    "ceo_count",
    "full_time_executives",
    "part_time_executives",
    "female_executives",
    "average_tenure_months",
    "long_tenure_executives",
    "term_expiring_within_12_months",
    "registered_share",
    "outside_director_share",
    "female_share",
    "unregistered_pay_count",
    "unregistered_pay_total",
    "unregistered_average_salary",
}
EXECUTIVE_METRICS = {
    "executives_total",
    "registered_executives",
    "unregistered_executives",
    "inside_directors",
    "outside_directors",
    "ceo_count",
    "full_time_executives",
    "part_time_executives",
    "female_executives",
    "average_tenure_months",
    "long_tenure_executives",
    "term_expiring_within_12_months",
    "registered_share",
    "outside_director_share",
    "female_share",
}
COUNT_METRICS = {
    "employees_total",
    "regular_employees",
    "contract_employees",
    "regular_short_time",
    "contract_short_time",
}
MONEY_METRICS = {
    "annual_salary_total",
    "average_salary",
    "unregistered_pay_total",
    "unregistered_average_salary",
}


def _load_fixture(path: Path = CLASSROOM_FIXTURE) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    observations = document.get("observations")
    provenance = document.get("provenance")
    expected_provenance = {
        "authoring_method": "hand-authored synthetic scenario",
        "source_data_used": False,
        "third_party_content_used": False,
        "intended_use": "education_and_software_testing_only",
        "contains_real_company_data": False,
        "contains_personal_data": False,
    }
    if (
        document.get("fixture_version") != 1
        or document.get("fixture_id") != CLASSROOM_FIXTURE_ID
        or provenance != expected_provenance
        or not isinstance(observations, list)
    ):
        raise ValueError("Classroom fixture contract is invalid.")
    if not observations or any(
        not str(item.get("company", {}).get("corp_code", "")).startswith("9")
        for item in observations
    ):
        raise ValueError("Classroom fixture must contain synthetic company codes.")
    reference_ids = [str(item.get("synthetic_reference_id") or "") for item in observations]
    if (
        any(not _SYNTHETIC_REFERENCE_PATTERN.fullmatch(value) for value in reference_ids)
        or len(reference_ids) != len(set(reference_ids))
    ):
        raise ValueError("Classroom fixture must contain unique synthetic references.")
    serialized = json.dumps(document, ensure_ascii=False)
    if (
        re.search(r"https?://", serialized, flags=re.IGNORECASE)
        or "dart.fss.or.kr" in serialized.lower()
        or any(key in serialized for key in ('"rcept_no"', '"source_urls"'))
    ):
        raise ValueError("Classroom fixture must not contain external filing references.")
    return document


def _synthetic_reference_urn(reference_id: str) -> str:
    if not _SYNTHETIC_REFERENCE_PATTERN.fullmatch(reference_id):
        raise ValueError("Classroom synthetic reference is invalid.")
    return f"{SYNTHETIC_REFERENCE_SCHEME}:{reference_id.lower()}"


def _materialize_orchestration_observations(
    document: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Create private DART-shaped references required by the v2 evidence engine.

    The compatibility references exist only during orchestration. The public
    payload replaces them with non-network synthetic URNs and removes receipt
    numbers before serialization.
    """

    observations = copy.deepcopy(document["observations"])
    public_references: dict[str, str] = {}
    for observation in observations:
        reference_id = str(observation.pop("synthetic_reference_id", ""))
        urn = _synthetic_reference_urn(reference_id)
        corp_code = str(observation.get("company", {}).get("corp_code", ""))
        if not re.fullmatch(r"9\d{7}", corp_code):
            raise ValueError("Classroom company code is invalid.")
        stock_code = str(observation.get("company", {}).get("stock_code", ""))
        if not re.fullmatch(r"9\d{5}", stock_code):
            raise ValueError("Classroom stock code is invalid.")
        receipt = f"{_INTERNAL_RECEIPT_PREFIX}{stock_code}"
        source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"
        observation["source_urls"] = [source_url]
        for row_collection in (
            "employee_rows",
            "executive_rows",
            "unregistered_pay_rows",
        ):
            for row in observation.get(row_collection, []):
                row["rcept_no"] = receipt
        public_references[source_url] = urn
        public_references[receipt] = urn
    return observations, public_references


def _public_classroom_references(
    value: Any,
    public_references: dict[str, str],
) -> Any:
    """Replace private compatibility references with explicit synthetic URNs."""

    if isinstance(value, list):
        return [_public_classroom_references(item, public_references) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "rcept_no":
            continue
        if key == "receipt_numbers":
            result[key] = []
            continue
        if key == "source_url":
            result[key] = public_references.get(str(item)) if item else None
            continue
        if key == "source_urls":
            mapped = [
                public_references[url]
                for url in item or []
                if url in public_references
            ]
            result[key] = list(dict.fromkeys(mapped))
            continue
        result[key] = _public_classroom_references(item, public_references)
    return result


def _assert_public_payload_has_no_network_references(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if re.search(r"https?://|dart\.fss\.or\.kr", serialized, flags=re.IGNORECASE):
        raise ValueError("Classroom payload contains an external network reference.")
    if re.search(rf'"{_INTERNAL_RECEIPT_PREFIX}\d{{6}}"', serialized):
        raise ValueError("Classroom payload contains an internal receipt number.")


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _tenure_years(value: Any) -> float | None:
    numeric = _number(value)
    if numeric is not None:
        return numeric
    text = str(value or "")
    years = re.search(r"(\d+(?:\.\d+)?)\s*년", text)
    months = re.search(r"(\d+(?:\.\d+)?)\s*개월", text)
    if not years and not months:
        return None
    return (float(years.group(1)) if years else 0.0) + (
        float(months.group(1)) / 12 if months else 0.0
    )


def _employee_breakdown(observation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sex": row.get("sexdstn") or None,
            "business_unit": row.get("fo_bbm") or None,
            "regular": _number(row.get("rgllbr_co")),
            "contract": _number(row.get("cnttk_co")),
            "total": _number(row.get("sm")),
            "average_tenure": _tenure_years(row.get("avrg_cnwk_sdytrn")),
            "annual_salary_total": _number(row.get("fyer_salary_totamt")),
            "average_salary": _number(row.get("jan_salary_am")),
        }
        for row in observation.get("employee_rows", [])
    ]


def _scaled_metrics(
    metrics: dict[str, Any],
    *,
    scale: float,
    allowed: set[str],
) -> dict[str, Any]:
    scaled: dict[str, Any] = {}
    for key in allowed:
        value = metrics.get(key)
        if value is None or isinstance(value, bool):
            scaled[key] = value
        elif key in COUNT_METRICS:
            scaled[key] = round(float(value) * scale)
        elif key in MONEY_METRICS or key in FINANCIAL_METRICS - {
            "operating_margin",
            "net_margin",
            "debt_ratio",
            "current_ratio",
        }:
            scaled[key] = float(value) * scale
        else:
            scaled[key] = value
    return scaled


def _scaled_breakdown(rows: list[dict[str, Any]], scale: float) -> list[dict[str, Any]]:
    result = copy.deepcopy(rows)
    for row in result:
        for key in ("regular", "contract", "total"):
            if row.get(key) is not None:
                row[key] = round(float(row[key]) * scale)
        for key in ("annual_salary_total", "average_salary"):
            if row.get(key) is not None:
                row[key] = float(row[key]) * scale
    return result


def _financials(observation: dict[str, Any], scale: float) -> dict[str, Any]:
    source = observation.get("financials", {})
    result = {
        key: (float(value) * scale if value is not None else None)
        for key, value in source.items()
    }

    def percent(numerator: str, denominator: str) -> float | None:
        top = result.get(numerator)
        bottom = result.get(denominator)
        if top is None or bottom is None or bottom <= 0:
            return None
        return top / bottom * 100

    result["operating_margin"] = percent("operating_profit", "revenue")
    result["net_margin"] = percent("net_income", "revenue")
    result["debt_ratio"] = percent("liabilities", "equity")
    result["current_ratio"] = percent("current_assets", "current_liabilities")
    return result


def build_classroom_payload() -> dict[str, Any]:
    """Build a deterministic, zero-network workshop dataset.

    The fixture is deliberately synthetic and contains no filing URLs or
    receipt numbers. Private compatibility references exercise the evidence
    engine, then are replaced with non-network synthetic URNs before return.
    """

    document = _load_fixture()
    observations, public_references = _materialize_orchestration_observations(
        document
    )
    orchestration = WorkforceAgentOrchestrator(provider=None).run(observations)
    records = {
        item["company"]["corp_code"]: item
        for item in orchestration.get("facts", {}).get("records", [])
    }
    current: list[dict[str, Any]] = []
    people: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    people_history: list[dict[str, Any]] = []
    previous: list[dict[str, Any]] = []
    history_scales = (("2021", 0.82), ("2022", 0.88), ("2023", 0.94), ("2024", 1.0))

    for observation in observations:
        company = observation["company"]
        record = records[company["corp_code"]]
        metrics = record.get("metrics", {})
        source_urls = list(observation.get("source_urls") or [])
        financials = _financials(observation, 1.0)
        people_metrics = _scaled_metrics(metrics, scale=1.0, allowed=PEOPLE_METRICS)
        breakdown = _employee_breakdown(observation)
        base = {
            "company": company,
            "year": "2024",
            "report_code": "11011",
            "sample": True,
        }
        current.append({
            **base,
            "financials": financials,
            "currency": "KRW",
            "statement": "합성 교실 데이터",
            "source_url": source_urls[0] if source_urls else None,
        })
        previous.append({
            **base,
            "year": "2023",
            "financials": _financials(observation, 0.94),
            "currency": "KRW",
            "statement": "합성 교실 데이터",
            "source_url": source_urls[0] if source_urls else None,
        })
        people_item = {
            **base,
            "people": {
                "employee_row_count": len(observation.get("employee_rows", [])),
                "employee_aggregation": "synthetic_fixture_rows",
                "average_salary_basis": record.get("metric_basis", {}).get("average_salary"),
                **people_metrics,
            },
            "workforce_quality": record.get("quality", {}),
            "component_quality": record.get("quality", {}).get("components", {}),
            "executive_metrics": {
                key: metrics.get(key) for key in EXECUTIVE_METRICS
            },
            "employee_breakdown": breakdown,
            "unregistered_pay_breakdown": [],
            "source_urls": source_urls,
        }
        people.append(people_item)
        financial_years: list[dict[str, Any]] = []
        people_years: list[dict[str, Any]] = []
        for history_year, scale in history_scales:
            financial_years.append({
                **base,
                "year": history_year,
                "financials": _financials(observation, scale),
                "currency": "KRW",
                "statement": "합성 교실 데이터",
                "source_url": source_urls[0] if source_urls else None,
            })
            people_years.append({
                **base,
                "year": history_year,
                "people": {
                    **people_item["people"],
                    **_scaled_metrics(metrics, scale=scale, allowed=PEOPLE_METRICS),
                },
                "component_quality": people_item["component_quality"],
                "executive_metrics": people_item["executive_metrics"],
                "employee_breakdown": _scaled_breakdown(breakdown, scale),
                "source_urls": source_urls,
            })
        history.append({"company": company, "years": financial_years, "sample": True})
        people_history.append({"company": company, "years": people_years, "sample": True})

    orchestration["selection"] = {"count": len(current), "max": len(current)}
    orchestration["source"] = "synthetic_fixture"
    orchestration["request"] = {
        **orchestration.get("request", {}),
        "data_mode": "synthetic_classroom",
    }
    orchestration["prompt"] = None
    orchestration["prompt_handoff"] = {
        **orchestration.get("prompt_handoff", {}),
        "status": "not_applicable_synthetic_classroom",
        "prompt": None,
        "prompt_location": None,
        "data_mode": "synthetic_classroom",
    }
    orchestration["evidence"] = {
        **orchestration.get("evidence", {}),
        "reference_mode": "synthetic_fixture_urn",
        "external_source_links": False,
        "source_notice": (
            "강의용 합성 fixture 근거이며 실제 OpenDART 공시 또는 접수번호가 아닙니다."
        ),
    }
    # Runtime timing is intentionally normalized so repeated classroom loads
    # produce byte-for-byte equivalent JSON once encoded with stable options.
    orchestration["execution"]["duration_ms"] = 0
    for trace in orchestration.get("trace", []):
        trace["duration_ms"] = 0
    payload = {
        "sample": {
            "enabled": True,
            "watermark": CLASSROOM_WATERMARK,
            "fixture_version": document["fixture_version"],
            "fixture_id": document["fixture_id"],
            "description": document["description"],
            "provenance": copy.deepcopy(document["provenance"]),
            "network_requests": 0,
            "contains_real_company_data": False,
            "contains_personal_data": False,
            "evidence_references": "synthetic_contract_only",
            "outbound_evidence_links": False,
            "reference_scheme": SYNTHETIC_REFERENCE_SCHEME,
            "receipt_numbers_exposed": False,
        },
        "year": "2024",
        "report_code": "11011",
        "companies": [item["company"] for item in observations],
        "results": current,
        "previous": previous,
        "history": history,
        "people": people,
        "people_history": people_history,
        "orchestration": orchestration,
    }
    public_payload = _public_classroom_references(payload, public_references)
    _assert_public_payload_has_no_network_references(public_payload)
    return public_payload
