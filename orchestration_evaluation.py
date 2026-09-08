"""Deterministic quality evaluation for orchestration v2 responses.

The runtime guards prevent unsafe provider output.  This module adds an
offline-friendly scorecard for CI, smoke tests, and pilot monitoring without
calling an AI provider or OpenDART.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_orchestration import (
    DECISION_COHORT_LIMIT,
    DECISION_DIMENSION_SPECS,
    DECISION_METRIC_SPECS,
    PERSON_REFERENCE_CONTEXT_PATTERN,
    _addressed_question_metric_ids,
    _claim_clauses,
    _claim_text_segments,
    _citation_company_mismatches,
    _contains_automated_hr_action_recommendation,
    _contains_credential_literal,
    _contains_explicit_credential_literal,
    _contains_direct_identifier_literal,
    _contains_direct_personal_identifier_literal,
    _contains_fabricated_person_judgment,
    _direct_comparison_summary_supported,
    _is_grounded_report_year_claim,
    _contains_protected_characteristic_judgment,
    _contains_prompt_personal_identifier_literal,
    _contains_structured_hr_action_recommendation,
    _contains_unsupported_causal_assertion,
    _decision_action,
    _build_strategy_context,
    _decision_peer_positions,
    _decision_position_conclusion,
    _possible_fabricated_person_reference,
    _possible_named_person_reference,
    _question_required_metric_groups,
    _uncited_factual_claims,
    _without_safe_public_provider_literals,
)


EXPECTED_AGENTS = (
    "source_snapshot",
    "input_validator",
    "employee_normalizer",
    "executive_normalizer",
    "compensation_normalizer",
    "quality_auditor",
    "benchmark_calculator",
    "privacy_guard",
    "evidence_ledger",
    "decision_support",
    "provider_policy",
    "strategy_interpreter",
    "provider_output_guard",
    "response_guard",
)
EXPECTED_DECISION_DIMENSIONS = {
    "productivity",
    "compensation_sustainability",
    "workforce_structure",
    "governance_continuity",
    "data_completeness",
}
EXPECTED_PRIMARY_BRIEFS = {
    "productivity",
    "compensation_sustainability",
    "workforce_structure",
}
QUALITY_COMPONENT_BY_SOURCE = {
    "financial_status": "financials",
    "employee_status": "employees",
    "executive_status": "executives",
    "unregistered_executive_pay": "unregistered_pay",
}
EVIDENCE_PATTERN = re.compile(r"EV-[0-9a-f]{12}", re.IGNORECASE)
EVIDENCE_TOKEN_PATTERN = re.compile(r"EV-[A-Za-z0-9_-]{4,64}", re.IGNORECASE)
NUMERIC_CLAIM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(-?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*"
    r"(조\s*원|억\s*원|천만\s*원|백만\s*원|만\s*원|천\s*원|원|명|%|퍼센트|프로|년|개월|"
    r"배(?![가-힣A-Za-z]))"
)


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _provider_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        allow_nan=False,
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _assessment_count(assessment: Mapping[str, Any]) -> int:
    coverage = assessment.get("coverage")
    if not isinstance(coverage, Mapping):
        return -1
    value = coverage.get("comparable_observation_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _claim_segments(value: Any) -> list[str]:
    return _claim_text_segments(value)


def _numeric_claims(text: str) -> list[tuple[float, str, float]]:
    claims = []
    without_ids = EVIDENCE_TOKEN_PATTERN.sub("", text)
    compound_money_pattern = re.compile(
        r"(?<!\d)(\d[\d,]*)\s*억\s*(\d[\d,]*)\s*만\s*원"
    )
    for match in compound_money_pattern.finditer(without_ids):
        major = float(match.group(1).replace(",", ""))
        minor = float(match.group(2).replace(",", ""))
        claims.append((major * 100_000_000 + minor * 10_000, "원", 10_000.0))
    without_ids = compound_money_pattern.sub("", without_ids)
    for raw_value, raw_unit in NUMERIC_CLAIM_PATTERN.findall(without_ids):
        normalized_value = raw_value.replace(",", "")
        try:
            value = float(normalized_value)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        mantissa = normalized_value.lower().split("e", 1)[0]
        decimals = len(mantissa.rsplit(".", 1)[1]) if "." in mantissa else 0
        unit = re.sub(r"\s+", "", raw_unit)
        if unit in {"퍼센트", "프로"}:
            unit = "%"
        multiplier = {
            "조원": 1_000_000_000_000,
            "억원": 100_000_000,
            "천만원": 10_000_000,
            "백만원": 1_000_000,
            "만원": 10_000,
            "천원": 1_000,
            "원": 1,
            "배": 100,
        }.get(unit, 1)
        scaled = value * multiplier
        if math.isfinite(scaled):
            claims.append((scaled, unit, multiplier * 0.5 * (10 ** -decimals)))
    return claims


def _claim_matches_evidence(
    claim: float,
    unit: str,
    rounding_tolerance: float,
    evidence: Mapping[str, Any],
) -> bool:
    if unit == "년" and claim.is_integer() and 2000 <= claim <= 2099:
        return str(int(claim)) == str(evidence.get("year") or "")
    evidence_unit = str(evidence.get("unit") or "")
    if unit in {"조원", "억원", "천만원", "백만원", "만원", "천원", "원"}:
        unit_matches = evidence_unit == "원"
        floor = 1.0
    elif unit == "배":
        unit_matches = evidence_unit == "%"
        floor = 0.01
    else:
        unit_matches = evidence_unit == unit
        floor = 0.01
    value = evidence.get("value")
    if not unit_matches or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(numeric_value):
        return False
    tolerance = min(
        rounding_tolerance + floor * 1e-6,
        max(floor, abs(numeric_value) * 0.005),
    )
    return abs(claim - numeric_value) <= tolerance


def evaluate_orchestration_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return a machine-readable scorecard without mutating the response."""

    failures: list[str] = []
    warnings: list[str] = []
    if not isinstance(result, Mapping):
        failures.append("invalid_result_shape")
        result = {}
    if result.get("schema_version") != 2:
        failures.append("schema_version_not_v2")

    facts = result.get("facts") if isinstance(result.get("facts"), Mapping) else {}
    raw_records = facts.get("records")
    records = [
        item for item in raw_records if isinstance(item, Mapping)
    ] if isinstance(raw_records, (list, tuple)) else []
    if raw_records is not None and (
        not isinstance(raw_records, (list, tuple)) or len(records) != len(raw_records)
    ):
        failures.append("invalid_record_shape")
    observation_ids = {
        str(record.get("observation_id"))
        for record in records
        if record.get("observation_id")
    }
    evidence_section = (
        result.get("evidence") if isinstance(result.get("evidence"), Mapping) else {}
    )
    raw_evidence = evidence_section.get("ledger")
    evidence = [
        item for item in raw_evidence if isinstance(item, Mapping)
    ] if isinstance(raw_evidence, (list, tuple)) else []
    if raw_evidence is not None and (
        not isinstance(raw_evidence, (list, tuple)) or len(evidence) != len(raw_evidence)
    ):
        failures.append("invalid_evidence_shape")
    evidence_ids = [str(item.get("evidence_id")) for item in evidence if item.get("evidence_id")]
    unique_evidence_ids = set(evidence_ids)
    if len(evidence_ids) != len(unique_evidence_ids):
        failures.append("duplicate_evidence_ids")
    orphaned_evidence = [
        item.get("evidence_id")
        for item in evidence
        if item.get("observation_id") not in observation_ids
    ]
    if orphaned_evidence:
        failures.append("orphaned_evidence")

    decision_support = (
        result.get("decision_support")
        if isinstance(result.get("decision_support"), Mapping)
        else {}
    )
    if not isinstance(result.get("decision_support"), Mapping):
        failures.append("invalid_decision_support_shape")
    raw_readiness = decision_support.get("readiness")
    raw_briefs = decision_support.get("briefs")
    raw_data_gaps = decision_support.get("data_gaps")
    raw_signal_catalog = decision_support.get("signal_catalog")
    readiness = [
        item for item in raw_readiness if isinstance(item, Mapping)
    ] if isinstance(raw_readiness, (list, tuple)) else []
    briefs = [
        item for item in raw_briefs if isinstance(item, Mapping)
    ] if isinstance(raw_briefs, (list, tuple)) else []
    data_gaps = [
        item for item in raw_data_gaps if isinstance(item, Mapping)
    ] if isinstance(raw_data_gaps, (list, tuple)) else []
    signal_catalog = [
        item for item in raw_signal_catalog if isinstance(item, Mapping)
    ] if isinstance(raw_signal_catalog, (list, tuple)) else []
    if (
        not isinstance(raw_readiness, (list, tuple))
        or len(readiness) != len(raw_readiness)
        or not isinstance(raw_briefs, (list, tuple))
        or len(briefs) != len(raw_briefs)
        or not isinstance(raw_data_gaps, (list, tuple))
        or len(data_gaps) != len(raw_data_gaps)
        or not isinstance(raw_signal_catalog, (list, tuple))
        or len(signal_catalog) != len(raw_signal_catalog)
    ):
        failures.append("invalid_decision_support_shape")
    if (
        len(readiness) != len(EXPECTED_DECISION_DIMENSIONS)
        or {item.get("dimension_id") for item in readiness}
        != EXPECTED_DECISION_DIMENSIONS
        or len(briefs) != len(EXPECTED_PRIMARY_BRIEFS)
        or {item.get("brief_id") for item in briefs} != EXPECTED_PRIMARY_BRIEFS
    ):
        failures.append("invalid_decision_support_dimensions")
    signal_by_metric = {
        str(item.get("metric_id")): {
            "signal_type": item.get("signal_type"),
            "interpretation_limit": item.get("interpretation_limit"),
        }
        for item in signal_catalog
        if item.get("metric_id")
    }
    if (
        len(signal_by_metric) != len(signal_catalog)
        or signal_by_metric != {
            metric_id: {
                "signal_type": DECISION_METRIC_SPECS[metric_id]["signal_type"],
                "interpretation_limit": dimension_spec["interpretation_limit"],
            }
            for dimension_spec in DECISION_DIMENSION_SPECS
            for metric_id in dimension_spec["metric_ids"]
        }
    ):
        failures.append("invalid_decision_support_signal_catalog")
    ledger_by_id = {
        str(item.get("evidence_id")): item
        for item in evidence
        if item.get("evidence_id")
    }
    quality_section = (
        result.get("quality") if isinstance(result.get("quality"), Mapping) else {}
    )
    raw_quality_records = quality_section.get("records")
    quality_records = (
        [item for item in raw_quality_records if isinstance(item, Mapping)]
        if isinstance(raw_quality_records, (list, tuple))
        else []
    )
    quality_by_observation = {
        str(item.get("observation_id")): item
        for item in quality_records
        if item.get("observation_id")
    }
    if (
        not isinstance(raw_quality_records, (list, tuple))
        or len(quality_records) != len(raw_quality_records)
        or set(quality_by_observation) != observation_ids
    ):
        failures.append("invalid_quality_shape")
    decision_evidence_ids: set[str] = set()
    invalid_decision_evidence_ids: list[str] = []
    invalid_peer_contexts: list[str] = []
    invalid_metric_assessments: list[str] = []
    invalid_confidence_items: list[str] = []
    invalid_action_briefs: list[str] = []
    dimension_spec_by_id = {
        spec["dimension_id"]: spec for spec in DECISION_DIMENSION_SPECS
    }
    for item in [*readiness, *briefs]:
        raw_ids = item.get("evidence_ids")
        if not isinstance(raw_ids, (list, tuple)) or any(
            not isinstance(evidence_id, str) for evidence_id in raw_ids
        ):
            failures.append("invalid_decision_support_evidence_ids")
            continue
        if len(set(raw_ids)) != len(raw_ids):
            failures.append("duplicate_decision_support_evidence_ids")
        decision_evidence_ids.update(raw_ids)
        invalid_decision_evidence_ids.extend(
            evidence_id
            for evidence_id in raw_ids
            if evidence_id not in ledger_by_id
            or ledger_by_id[evidence_id].get("source_coverage_complete") is not True
        )
        raw_assessments = item.get("metric_assessments")
        assessments = (
            [assessment for assessment in raw_assessments if isinstance(assessment, Mapping)]
            if isinstance(raw_assessments, (list, tuple))
            else []
        )
        if (
            not isinstance(raw_assessments, (list, tuple))
            or len(assessments) != len(raw_assessments)
        ):
            invalid_metric_assessments.append("invalid_shape")
        dimension_id = item.get("dimension_id") or item.get("brief_id")
        dimension_spec = dimension_spec_by_id.get(dimension_id)
        assessment_by_metric = {}
        assessment_ids: list[str] = []
        for assessment in assessments:
            metric_id = assessment.get("metric_id")
            assessment_evidence_ids = assessment.get("evidence_ids")
            if (
                not isinstance(metric_id, str)
                or metric_id in assessment_by_metric
                or not isinstance(assessment_evidence_ids, (list, tuple))
            ):
                invalid_metric_assessments.append(str(metric_id or "missing_metric"))
                continue
            assessment_by_metric[metric_id] = assessment
            coverage = assessment.get("coverage")
            if not isinstance(coverage, Mapping):
                invalid_metric_assessments.append(f"{metric_id}:coverage")
                coverage = {}
            if coverage.get("total_observation_count") != len(records):
                invalid_metric_assessments.append(f"{metric_id}:total_count")
            assessment_observation_ids: set[str] = set()
            quality_flags = []
            for evidence_id in assessment_evidence_ids:
                source = ledger_by_id.get(evidence_id)
                if (
                    not isinstance(evidence_id, str)
                    or evidence_id not in raw_ids
                    or source is None
                    or source.get("metric_id") != metric_id
                ):
                    invalid_metric_assessments.append(str(evidence_id or metric_id))
                else:
                    assessment_ids.append(evidence_id)
                    assessment_observation_ids.add(str(source.get("observation_id")))
                    observation_quality = quality_by_observation.get(
                        str(source.get("observation_id")), {}
                    )
                    components = observation_quality.get("components") or {}
                    relevant_components = [
                        components.get(component_key, {})
                        for source_component in source.get("source_components") or []
                        if (
                            component_key := QUALITY_COMPONENT_BY_SOURCE.get(
                                source_component
                            )
                        )
                    ]
                    quality_flags.append(
                        bool(relevant_components)
                        and all(
                            component.get("status") == "complete"
                            for component in relevant_components
                        )
                    )
            comparable_count = len(assessment_observation_ids)
            expected_quality_complete = bool(quality_flags) and all(quality_flags)
            expected_assessment_status = (
                "ready" if comparable_count >= 2
                else "directional_only" if comparable_count == 1
                else "blocked"
            )
            if (
                coverage.get("comparable_observation_count") != comparable_count
                or assessment.get("status") != expected_assessment_status
                or assessment.get("metric_label")
                != DECISION_METRIC_SPECS.get(metric_id, {}).get("label")
                or assessment.get("signal_type")
                != signal_by_metric.get(metric_id, {}).get("signal_type")
                or assessment.get("interpretation_limit")
                != (dimension_spec or {}).get("interpretation_limit")
                or assessment.get("quality_complete") is not expected_quality_complete
                or assessment.get("uses_fallback_metric") is not False
            ):
                invalid_metric_assessments.append(f"{metric_id}:semantics")
        metric_ids = item.get("metric_ids")
        metric_id_sequence = (
            list(metric_ids) if isinstance(metric_ids, (list, tuple)) else []
        )
        metric_id_set = set(metric_id_sequence)
        if (
            not isinstance(metric_ids, (list, tuple))
            or metric_id_set != set(assessment_by_metric)
        ):
            invalid_metric_assessments.append("metric_set_mismatch")
        if dimension_spec is not None and (
            metric_id_sequence != list(dimension_spec["metric_ids"])
            or item.get("interpretation_limit")
            != dimension_spec["interpretation_limit"]
            or item.get("next_data") != list(dimension_spec["next_data"])
        ):
            invalid_metric_assessments.append(f"{dimension_id}:dimension_semantics")
        if item.get("brief_id") and (
            dimension_spec is None
            or item.get("question") != dimension_spec["question"]
            or item.get("cannot_tell") != list(dimension_spec["cannot_tell"])
            or item.get("self_trajectory") != {
                "status": "not_available",
                "reason_code": "single_period_orchestration_input",
            }
        ):
            invalid_metric_assessments.append(f"{dimension_id}:brief_semantics")
        if set(assessment_ids) != set(raw_ids):
            invalid_metric_assessments.append("evidence_union_mismatch")
        selected_metric_id = item.get("selected_metric_id")
        selected = assessment_by_metric.get(selected_metric_id)
        if selected_metric_id is None:
            if assessments or item.get("selected_metric_label") is not None:
                invalid_metric_assessments.append("unexpected_selected_metric")
        elif (
            selected is None
            or item.get("selected_metric_label") != selected.get("metric_label")
            or item.get("signal_type") != selected.get("signal_type")
        ):
            invalid_metric_assessments.append(str(selected_metric_id))
        else:
            selection_candidates = [
                assessment
                for assessment in assessments
                if assessment.get("metric_id") in metric_id_sequence
                and isinstance(assessment.get("coverage"), Mapping)
                and _assessment_count(assessment) >= 0
            ]
            expected_selected_metric_id = (
                max(
                    selection_candidates,
                    key=lambda assessment: (
                        _assessment_count(assessment),
                        -metric_id_sequence.index(assessment["metric_id"]),
                    ),
                ).get("metric_id")
                if len(selection_candidates) == len(assessments)
                else None
            )
            maximum_coverage = max(
                (
                    _assessment_count(assessment)
                    for assessment in assessments
                ),
                default=-1,
            )
            assessment_statuses = {
                assessment.get("status") for assessment in assessments
            }
            expected_item_status = (
                "ready" if assessment_statuses == {"ready"}
                and _assessment_count(selected) >= 4
                else "blocked" if assessment_statuses == {"blocked"}
                else "directional_only"
            )
            if (
                _assessment_count(selected)
                != maximum_coverage
                or selected_metric_id != expected_selected_metric_id
                or item.get("coverage") != selected.get("coverage")
                or item.get("status") != expected_item_status
            ):
                invalid_metric_assessments.append(
                    f"{selected_metric_id}:selection_semantics"
                )
            selected_count = _assessment_count(selected)
            expected_confidence = (
                "medium" if expected_item_status == "ready"
                and selected.get("quality_complete") is True
                and selected.get("uses_fallback_metric") is False
                else "low"
            )
            expected_selection_reason = (
                f"{selected.get('metric_label')}이(가) {len(records)}개 선택 기업 중 "
                f"{selected_count}개에서 원문 연결되어 대표 지표로 선택됐습니다. "
                "동률이면 사전 정의된 지표 우선순위를 사용하며 나머지 지표도 readiness에 함께 반영합니다."
            )
            expected_reason_codes = set()
            if assessment_statuses == {"ready"}:
                expected_reason_codes.add("peer_benchmark_available")
            elif any(
                assessment.get("status") in {"ready", "directional_only"}
                for assessment in assessments
            ):
                expected_reason_codes.add("partial_metric_coverage")
                if selected_count >= 2:
                    expected_reason_codes.add("peer_benchmark_available")
                elif selected_count == 1:
                    expected_reason_codes.add("single_usable_observation")
            else:
                expected_reason_codes.add("required_metric_missing")
                if any(
                    evidence_item.get("metric_id") in metric_id_set
                    and evidence_item.get("source_coverage_complete") is False
                    for evidence_item in evidence
                ):
                    expected_reason_codes.add("source_link_gap")
            available_assessments = [
                assessment
                for assessment in assessments
                if assessment.get("status") != "blocked"
            ]
            if available_assessments and not all(
                assessment.get("quality_complete") is True
                for assessment in available_assessments
            ):
                expected_reason_codes.add("quality_limit_present")
            if selected_count and selected_count < 4:
                expected_reason_codes.add("small_peer_sample")
            expected_reason_codes.add("history_not_in_readiness")
            if selected.get("uses_fallback_metric") is True:
                expected_reason_codes.add("fallback_metric_used")
            raw_reason_codes = item.get("reason_codes")
            if (
                item.get("confidence") != expected_confidence
                or item.get("selection_reason") != expected_selection_reason
                or not isinstance(raw_reason_codes, (list, tuple))
                or len(raw_reason_codes) != len(set(raw_reason_codes))
                or set(raw_reason_codes) != expected_reason_codes
            ):
                invalid_confidence_items.append(
                    str(item.get("dimension_id") or item.get("brief_id") or selected_metric_id)
                )
        peer_context = item.get("peer_context") or []
        if not isinstance(peer_context, (list, tuple)):
            failures.append("invalid_decision_support_peer_context")
            continue
        for peer in peer_context:
            if not isinstance(peer, Mapping):
                invalid_peer_contexts.append("invalid_shape")
                continue
            evidence_id = str(peer.get("evidence_id") or "")
            source = ledger_by_id.get(evidence_id)
            if (
                evidence_id not in raw_ids
                or source is None
                or peer.get("observation_id") != source.get("observation_id")
                or peer.get("value") != source.get("value")
                or source.get("metric_id") != selected_metric_id
            ):
                invalid_peer_contexts.append(evidence_id or "missing_evidence_id")
    readiness_by_dimension = {
        item.get("dimension_id"): item for item in readiness
    }
    for brief in briefs:
        next_data = brief.get("next_data")
        brief_id = str(brief.get("brief_id") or "missing_brief")
        matching_readiness = readiness_by_dimension.get(brief.get("brief_id"))
        brief_spec = dimension_spec_by_id.get(brief.get("brief_id"))
        raw_brief_assessments = brief.get("metric_assessments")
        brief_assessments = [
            assessment
            for assessment in raw_brief_assessments
            if isinstance(assessment, Mapping)
        ] if isinstance(raw_brief_assessments, (list, tuple)) else []
        selected_assessment = next(
            (
                assessment
                for assessment in brief_assessments
                if assessment.get("metric_id") == brief.get("selected_metric_id")
            ),
            None,
        )
        expected_peer_context = None
        expected_brief_status = None
        if selected_assessment is not None:
            raw_selected_evidence_ids = selected_assessment.get("evidence_ids")
            selected_evidence_ids = (
                list(raw_selected_evidence_ids)
                if isinstance(raw_selected_evidence_ids, (list, tuple))
                else []
            )
            selected_evidence = [
                ledger_by_id[evidence_id]
                for evidence_id in selected_evidence_ids
                if evidence_id in ledger_by_id
            ]
            if len(selected_evidence) == len(selected_evidence_ids):
                try:
                    expected_peer_context = _decision_peer_positions(selected_evidence)
                except (KeyError, TypeError, ValueError, OverflowError):
                    expected_peer_context = None
            assessment_statuses = {
                assessment.get("status") for assessment in brief_assessments
            }
            selected_count = _assessment_count(selected_assessment)
            expected_brief_status = (
                "ready" if assessment_statuses == {"ready"} and selected_count >= 4
                else "blocked" if assessment_statuses == {"blocked"}
                else "directional_only"
            )
        if (
            not isinstance(matching_readiness, Mapping)
            or any(
                brief.get(key) != value
                for key, value in matching_readiness.items()
            )
            or not isinstance(brief.get("decision_action"), str)
            or not isinstance(next_data, (list, tuple))
            or not next_data
            or brief_spec is None
            or expected_peer_context is None
            or expected_brief_status is None
            or brief.get("peer_context") != expected_peer_context
            or brief.get("conclusion") != _decision_position_conclusion(
                str(brief.get("selected_metric_label") or ""),
                expected_peer_context or [],
                expected_brief_status or "blocked",
            )
            or brief["decision_action"]
            != _decision_action(expected_brief_status or "blocked", brief_spec["next_data"])
            or brief.get("cohort_limit") != DECISION_COHORT_LIMIT
        ):
            invalid_action_briefs.append(brief_id)
    linked_observations = {
        str(item.get("observation_id"))
        for item in evidence
        if item.get("source_coverage_complete") is True
    }
    all_complete = bool(records) and all(
        item.get("status") == "complete" for item in quality_records
    ) and len(quality_records) == len(records)
    evidence_summary = (
        evidence_section.get("summary")
        if isinstance(evidence_section.get("summary"), Mapping)
        else {}
    )
    quality_counts: dict[str, int] = {}
    for quality in quality_records:
        status = str(quality.get("status") or "unknown")
        quality_counts[status] = quality_counts.get(status, 0) + 1
    source_complete_count = sum(
        item.get("source_coverage_complete") is True for item in evidence
    )
    expected_summary_values = {
        "observation_count": len(records),
        "evidence_count": len(evidence),
        "source_complete_evidence_count": source_complete_count,
        "source_incomplete_evidence_count": len(evidence) - source_complete_count,
        "linked_observation_count": len(linked_observations),
        "quality_counts": quality_counts,
    }
    if (
        any(
            evidence_summary.get(key) != value
            for key, value in expected_summary_values.items()
        )
        or evidence_summary.get("restatement_verification")
        not in {"not_performed", "verified_current"}
        or set(evidence_summary) != {
            *expected_summary_values,
            "restatement_verification",
        }
    ):
        failures.append("invalid_evidence_summary_contract")
    restatement_verified = (
        evidence_summary.get("restatement_verification") == "verified_current"
    )
    if records and len(linked_observations) == len(records) and all_complete:
        completeness_status = "ready"
        completeness_reasons = ["all_observations_source_complete"]
        completeness_confidence = "high"
    elif linked_observations:
        completeness_status = "directional_only"
        completeness_reasons = ["partial_decision_coverage"]
        completeness_confidence = "medium"
    else:
        completeness_status = "blocked"
        completeness_reasons = ["no_source_complete_evidence"]
        completeness_confidence = "low"
    if not restatement_verified:
        completeness_reasons.append("restatement_not_verified")
        if completeness_confidence == "high":
            completeness_confidence = "medium"
        elif completeness_confidence == "medium":
            completeness_confidence = "low"
    expected_completeness = {
        "dimension_id": "data_completeness",
        "status": completeness_status,
        "reason_codes": completeness_reasons,
        "metric_ids": [],
        "selected_metric_id": None,
        "selected_metric_label": None,
        "selection_reason": "근거 연결 완전성은 특정 대표 지표를 선택하지 않고 전체 원문 연결과 품질 상태를 평가하며, 정정공시 최신성은 별도 확인합니다.",
        "metric_assessments": [],
        "signal_type": "data_gap",
        "evidence_ids": [],
        "coverage": {
            "comparable_observation_count": len(linked_observations),
            "total_observation_count": len(records),
        },
        "confidence": completeness_confidence,
        "interpretation_limit": "공시와 원문 연결의 완전성만 나타내며 정정공시 최신성이나 내부 HR 데이터의 정확성·충분성을 보증하지 않습니다.",
        "next_data": ["정정공시 최신성 대조", "미공시 항목의 내부 집계", "원문 접수번호 대조"],
    }
    if readiness_by_dimension.get("data_completeness") != expected_completeness:
        failures.append("invalid_decision_support_completeness_contract")
    if invalid_decision_evidence_ids:
        failures.append("invalid_decision_support_evidence_ids")
    if invalid_peer_contexts:
        failures.append("invalid_decision_support_peer_context")
    if invalid_metric_assessments:
        failures.append("invalid_decision_support_metric_assessments")
    if invalid_confidence_items:
        failures.append("invalid_decision_support_confidence_contract")
    if invalid_action_briefs:
        failures.append("invalid_decision_support_action_contract")
    invalid_data_gap_observations = sorted({
        str(item.get("observation_id") or "")
        for item in data_gaps
        if item.get("observation_id") not in observation_ids
    })
    if invalid_data_gap_observations:
        failures.append("invalid_decision_support_data_gaps")

    raw_trace = result.get("trace")
    trace = [
        item for item in raw_trace if isinstance(item, Mapping)
    ] if isinstance(raw_trace, (list, tuple)) else []
    if raw_trace is not None and (
        not isinstance(raw_trace, (list, tuple)) or len(trace) != len(raw_trace)
    ):
        failures.append("invalid_trace_shape")
    trace_names = [str(item.get("agent") or "") for item in trace]
    missing_agents = [agent for agent in EXPECTED_AGENTS if agent not in trace_names]
    if missing_agents:
        failures.append("incomplete_trace")
    failed_agents = [item.get("agent") for item in trace if item.get("status") == "error"]
    blocked_agents = [item.get("agent") for item in trace if item.get("status") == "blocked"]

    privacy = result.get("privacy") if isinstance(result.get("privacy"), Mapping) else {}
    if result.get("privacy") is not None and not isinstance(result.get("privacy"), Mapping):
        failures.append("invalid_privacy_shape")
    privacy_status = str(privacy.get("status") or "not_run")
    if records and privacy_status != "passed":
        failures.append("privacy_not_passed")

    policy = result.get("policy") if isinstance(result.get("policy"), Mapping) else {}
    provider = result.get("provider") if isinstance(result.get("provider"), Mapping) else {}
    provider_status = str(provider.get("status") or "skipped")
    if policy.get("status") == "blocked" and provider_status == "completed":
        failures.append("provider_bypassed_policy")
    provider_validation = (
        result.get("provider_validation")
        if isinstance(result.get("provider_validation"), Mapping)
        else {}
    )
    provider_validation_status = str(provider_validation.get("status") or "not_run")
    if provider_status == "completed" and provider_validation_status != "passed":
        failures.append("completed_provider_without_passed_validation")
    if provider_status == "rejected" and provider.get("result") is not None:
        failures.append("rejected_provider_retained_result")
    elif provider_status != "completed" and provider.get("result") is not None:
        failures.append("noncompleted_provider_retained_result")
    if result.get("provider_result") is not None:
        try:
            provider_result_matches = (
                _provider_text(result.get("provider_result"))
                == _provider_text(provider.get("result"))
            )
        except (TypeError, ValueError, RecursionError):
            provider_result_matches = False
        if not provider_result_matches:
            failures.append("provider_result_alias_mismatch")
    if provider_validation_status == "rejected" and provider_status != "rejected":
        failures.append("provider_validation_status_mismatch")
    response_validation = (
        result.get("validation")
        if isinstance(result.get("validation"), Mapping)
        else {}
    )
    if str(response_validation.get("status") or "not_run") != "passed":
        failures.append("response_validation_not_passed")

    try:
        if not isinstance(provider.get("result"), str):
            json.dumps(
                provider.get("result"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        provider_text = _provider_text(provider.get("result"))
    except (TypeError, ValueError, RecursionError):
        provider_text = ""
        failures.append("invalid_provider_output_shape")
    privacy_surfaces = (
        result.get("request"),
        provider.get("result"),
        provider.get("error"),
        result.get("provider_result"),
        result.get("prompt_handoff"),
    )
    try:
        privacy_literal_exposed = any(
            _contains_direct_personal_identifier_literal(privacy_surface)
            for privacy_surface in privacy_surfaces
        )
    except RecursionError:
        privacy_literal_exposed = False
    for is_provider_result, privacy_surface in (
        (False, result.get("request")),
        (True, provider.get("result")),
    ):
        try:
            privacy_surface_text = _provider_text(privacy_surface)
        except (TypeError, ValueError, RecursionError):
            continue
        privacy_scan_surface = (
            _without_safe_public_provider_literals(privacy_surface)
            if is_provider_result
            else privacy_surface
        )
        if _contains_direct_identifier_literal(privacy_scan_surface):
            privacy_literal_exposed = True
        if (
            PERSON_REFERENCE_CONTEXT_PATTERN.search(privacy_surface_text)
            and _possible_named_person_reference(privacy_surface_text, records)
        ):
            privacy_literal_exposed = True
    for privacy_surface in (
        result.get("provider_result"),
        result.get("prompt_handoff"),
        provider.get("error"),
    ):
        try:
            if (
                _contains_direct_personal_identifier_literal(privacy_surface)
                or _contains_explicit_credential_literal(privacy_surface)
                or _contains_credential_literal(privacy_surface)
            ):
                privacy_literal_exposed = True
        except RecursionError:
            continue
    if (
        _contains_prompt_personal_identifier_literal(result.get("prompt"))
        or _contains_explicit_credential_literal(result.get("prompt"))
    ):
        privacy_literal_exposed = True
    if privacy_literal_exposed:
        failures.append("privacy_literal_exposed")
    if provider_status == "completed" and provider_text:
        if _contains_unsupported_causal_assertion(provider_text):
            failures.append("provider_causal_policy_mismatch")
        if (
            _contains_automated_hr_action_recommendation(provider_text)
            or _contains_structured_hr_action_recommendation(provider.get("result"))
        ):
            failures.append("provider_automated_hr_action_policy_mismatch")
        if _contains_protected_characteristic_judgment(provider_text):
            failures.append("provider_protected_characteristic_policy_mismatch")
        if _contains_fabricated_person_judgment(provider_text, records):
            failures.append("provider_person_judgment_policy_mismatch")
        elif _possible_fabricated_person_reference(provider_text, records):
            failures.append("provider_person_reference_policy_mismatch")
    evidence_tokens = sorted(set(EVIDENCE_TOKEN_PATTERN.findall(provider_text)))
    cited_ids = sorted(set(EVIDENCE_PATTERN.findall(provider_text)))
    malformed_citations = sorted(set(evidence_tokens) - set(cited_ids))
    cited_keys = {citation.casefold() for citation in cited_ids}
    ledger_evidence_keys = {evidence_id.casefold() for evidence_id in evidence_ids}
    raw_eligible_observations = policy.get("eligible_observation_ids")
    valid_eligible_observations = [
        observation_id
        for observation_id in raw_eligible_observations
        if isinstance(observation_id, str)
    ] if isinstance(raw_eligible_observations, (list, tuple)) else []
    if raw_eligible_observations is not None and (
        not isinstance(raw_eligible_observations, (list, tuple))
        or len(valid_eligible_observations) != len(raw_eligible_observations)
    ):
        failures.append("invalid_provider_policy_observation_ids")
    eligible_observations = set(valid_eligible_observations)
    context_summary = (
        provider.get("context_summary")
        if isinstance(provider.get("context_summary"), Mapping)
        else {}
    )
    if policy.get("status") == "allowed":
        benchmarks = (
            result.get("benchmarks")
            if isinstance(result.get("benchmarks"), Mapping)
            else {}
        )
        rankings = (
            benchmarks.get("rankings")
            if isinstance(benchmarks.get("rankings"), Mapping)
            else {}
        )
        request_context = (
            result.get("request")
            if isinstance(result.get("request"), Mapping)
            else {}
        )
        try:
            expected_context = _build_strategy_context({
                "records": records,
                "rankings": rankings,
                "quality_results": quality_records,
                "evidence_ledger": evidence,
                "evidence_summary": evidence_summary,
                "decision_support": decision_support,
                "privacy": privacy,
                "provider_policy": policy,
                "request_context": request_context,
            })
            expected_context_summary = {
                **expected_context["context_selection"],
                "included_evidence_ids": [
                    item["evidence_id"] for item in expected_context["evidence"]
                ],
            }
            if dict(context_summary) != expected_context_summary:
                failures.append("provider_context_selection_mismatch")
        except (KeyError, TypeError, ValueError):
            failures.append("provider_context_selection_unverifiable")
    unknown_context_evidence_ids: list[str] = []
    incomplete_context_evidence_ids: list[str] = []
    raw_context_evidence_ids = context_summary.get("included_evidence_ids")
    if isinstance(raw_context_evidence_ids, (list, tuple)):
        valid_context_ids = [
            evidence_id
            for evidence_id in raw_context_evidence_ids
            if isinstance(evidence_id, str)
            and EVIDENCE_PATTERN.fullmatch(evidence_id)
        ]
        if len(valid_context_ids) != len(raw_context_evidence_ids):
            failures.append("invalid_provider_context_evidence_ids")
        context_evidence_keys = {
            evidence_id.casefold() for evidence_id in valid_context_ids
        }
        if len(context_evidence_keys) != len(valid_context_ids):
            failures.append("duplicate_provider_context_evidence_ids")
        reported_context_count = context_summary.get("evidence_count")
        if (
            isinstance(reported_context_count, bool)
            or not isinstance(reported_context_count, int)
            or reported_context_count != len(raw_context_evidence_ids)
        ):
            failures.append("provider_context_evidence_count_mismatch")
        unknown_context_evidence_ids = sorted(
            evidence_id
            for evidence_id in valid_context_ids
            if evidence_id.casefold() not in ledger_evidence_keys
        )
        if unknown_context_evidence_ids:
            failures.append("unknown_provider_context_evidence_ids")
        incomplete_context_evidence_ids = sorted(
            str(item.get("evidence_id"))
            for item in evidence
            if str(item.get("evidence_id") or "").casefold() in context_evidence_keys
            and item.get("source_coverage_complete") is not True
        )
        if incomplete_context_evidence_ids:
            failures.append("incomplete_provider_context_evidence")
        expected_decision_support_status = (
            "limited"
            if policy.get("excluded_observations")
            else "available"
        )
        if (
            context_summary.get("decision_support_status")
            != expected_decision_support_status
        ):
            failures.append("invalid_provider_decision_support_context_status")
        decision_evidence_keys = {
            str(evidence_id).casefold()
            for brief in briefs
            if isinstance(brief, Mapping)
            for evidence_id in (brief.get("evidence_ids") or [])
            if isinstance(evidence_id, str)
        }
        if (
            expected_decision_support_status == "available"
            and not decision_evidence_keys.issubset(context_evidence_keys)
        ):
            failures.append("decision_support_evidence_outside_provider_context")
        provider_evidence = [
            item
            for item in evidence
            if str(item.get("evidence_id") or "").casefold() in context_evidence_keys
            and item.get("source_coverage_complete") is True
        ]
    else:
        if raw_context_evidence_ids is not None:
            failures.append("invalid_provider_context_evidence_ids")
        raw_included_metrics = context_summary.get("included_metric_ids")
        included_metrics = set(
            raw_included_metrics
            if isinstance(raw_included_metrics, (list, tuple))
            else []
        )
        provider_evidence = [
            item
            for item in evidence
            if (
                not eligible_observations
                or item.get("observation_id") in eligible_observations
            )
            and (not included_metrics or item.get("metric_id") in included_metrics)
            and item.get("source_coverage_complete") is True
        ]
    provider_evidence_keys = {
        str(item.get("evidence_id")).casefold()
        for item in provider_evidence
        if item.get("evidence_id")
    }
    try:
        unsupported_factual_claims = _uncited_factual_claims(
            provider.get("result"),
            provider_evidence_keys,
        )
    except RecursionError:
        unsupported_factual_claims = []
        if "invalid_provider_output_shape" not in failures:
            failures.append("invalid_provider_output_shape")
    unknown_citations = sorted(
        citation for citation in cited_ids if citation.casefold() not in ledger_evidence_keys
    )
    outside_context_citations = sorted(
        citation
        for citation in cited_ids
        if citation.casefold() in ledger_evidence_keys
        and citation.casefold() not in provider_evidence_keys
    )
    if malformed_citations:
        failures.append("malformed_evidence_citations")
    if unknown_citations:
        failures.append("unknown_evidence_citations")
    if outside_context_citations:
        failures.append("citations_outside_provider_context")
    try:
        provider_claim_segments = [
            clause
            for segment in _claim_segments(provider.get("result"))
            for clause in (_claim_clauses(segment) or [segment])
        ]
    except RecursionError:
        provider_claim_segments = []
        failures.append("invalid_provider_output_shape")
    evidence_by_id = {
        str(item.get("evidence_id") or "").casefold(): item
        for item in provider_evidence
        if item.get("evidence_id")
    }
    globally_cited_evidence = [
        evidence_by_id[citation.casefold()]
        for citation in cited_ids
        if citation.casefold() in evidence_by_id
    ]
    uncited_numeric_lines = [
        index
        for index, line in enumerate(provider_claim_segments, start=1)
        if (
            NUMERIC_CLAIM_PATTERN.search(line)
            and not EVIDENCE_PATTERN.search(line)
            and not all(
                _is_grounded_report_year_claim(
                    line,
                    claim,
                    unit,
                    globally_cited_evidence,
                )
                for claim, unit, _tolerance in _numeric_claims(line)
            )
        )
    ]
    try:
        evidence_company_mismatches = _citation_company_mismatches(
            provider.get("result"),
            evidence_by_id,
        )
    except RecursionError:
        evidence_company_mismatches = []
        if "invalid_provider_output_shape" not in failures:
            failures.append("invalid_provider_output_shape")
    request_context = (
        result.get("request") if isinstance(result.get("request"), Mapping) else {}
    )
    required_metric_groups = _question_required_metric_groups(
        request_context.get("question"),
        request_context.get("metric_ids") or (),
    )
    available_metric_ids = {
        str(item.get("metric_id") or "") for item in provider_evidence
    }
    required_metric_ids = list(dict.fromkeys(
        metric_id for group in required_metric_groups for metric_id in group
    ))
    if (
        unsupported_factual_claims == [{"segment_index": 1, "claim_type": "factual"}]
        and _direct_comparison_summary_supported(
            provider.get("result"),
            evidence_by_id,
            required_metric_ids,
        )
    ):
        unsupported_factual_claims = []
    try:
        addressed_metric_ids = _addressed_question_metric_ids(
            provider.get("result"),
            evidence_by_id,
            required_metric_ids,
        )
    except RecursionError:
        addressed_metric_ids = set()
        if "invalid_provider_output_shape" not in failures:
            failures.append("invalid_provider_output_shape")
    required_available_groups = [
        tuple(metric_id for metric_id in group if metric_id in available_metric_ids)
        for group in required_metric_groups
    ]
    required_available_groups = [group for group in required_available_groups if group]
    unaddressed_metric_groups = [
        list(group)
        for group in required_available_groups
        if not addressed_metric_ids.intersection(group)
    ]
    unsupported_numeric_claims = []
    for segment_index, segment in enumerate(provider_claim_segments, start=1):
        segment_ids = {
            token.casefold()
            for token in EVIDENCE_PATTERN.findall(segment)
            if token.casefold() in evidence_by_id
        }
        cited_evidence = [evidence_by_id[evidence_id] for evidence_id in segment_ids]
        for claim, unit, tolerance in _numeric_claims(segment):
            if _is_grounded_report_year_claim(
                segment,
                claim,
                unit,
                globally_cited_evidence,
            ):
                continue
            if not any(
                _claim_matches_evidence(claim, unit, tolerance, item)
                for item in cited_evidence
            ):
                unsupported_numeric_claims.append({
                    "segment": segment_index,
                    "claim": f"{claim:g}{unit}",
                    "cited_evidence_ids": sorted(segment_ids),
                })
    if provider_status == "completed":
        if evidence_company_mismatches:
            failures.append("provider_evidence_company_mismatch")
        if unaddressed_metric_groups:
            failures.append("provider_question_metric_not_addressed")
        if unsupported_factual_claims:
            failures.append("provider_factual_claim_without_citation")
        if uncited_numeric_lines:
            failures.append("provider_numeric_claim_without_citation")
        if unsupported_numeric_claims:
            failures.append("provider_numeric_claim_not_grounded")
        elif not cited_ids:
            warnings.append("provider_completed_without_evidence_citation")

    linked_observations = {
        item.get("observation_id")
        for item in evidence
        if item.get("source_coverage_complete") is True
    }
    quality_counts: dict[str, int] = {}
    quality = result.get("quality") if isinstance(result.get("quality"), Mapping) else {}
    quality_records = quality.get("records")
    quality_records = quality_records if isinstance(quality_records, (list, tuple)) else []
    for item in quality_records:
        if not isinstance(item, Mapping):
            failures.append("invalid_quality_shape")
            continue
        status = str(item.get("status") or "unknown")
        quality_counts[status] = quality_counts.get(status, 0) + 1

    if failures:
        status = "failed"
    elif warnings or failed_agents or blocked_agents or result.get("status") == "partial":
        status = "warning"
    else:
        status = "passed"
    return {
        "evaluation_version": 1,
        "run_id": result.get("run_id"),
        "status": status,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "metrics": {
            "observation_count": len(observation_ids),
            "evidence_count": len(evidence),
            "unique_evidence_count": len(unique_evidence_ids),
            "linked_observation_count": len(linked_observations),
            "source_link_rate": _ratio(len(linked_observations), len(observation_ids)),
            "provider_citation_count": len(cited_ids),
            "provider_context_evidence_count": len(provider_evidence_keys),
            "provider_citation_coverage": _ratio(
                len(cited_keys & provider_evidence_keys), len(provider_evidence_keys)
            ),
            "unknown_provider_citation_count": len(unknown_citations),
            "outside_context_citation_count": len(outside_context_citations),
            "malformed_provider_citation_count": len(malformed_citations),
            "trace_agent_count": len(trace_names),
            "failed_agent_count": len(failed_agents),
            "blocked_agent_count": len(blocked_agents),
            "quality_counts": quality_counts,
            "decision_brief_count": len(briefs),
            "decision_ready_count": sum(
                item.get("status") == "ready" for item in readiness
            ),
            "decision_directional_count": sum(
                item.get("status") == "directional_only" for item in readiness
            ),
            "decision_blocked_count": sum(
                item.get("status") == "blocked" for item in readiness
            ),
            "decision_evidence_count": len(decision_evidence_ids),
            "data_gap_count": len(data_gaps),
        },
        "details": {
            "missing_agents": missing_agents,
            "failed_agents": failed_agents,
            "blocked_agents": blocked_agents,
            "unknown_evidence_ids": unknown_citations,
            "outside_context_evidence_ids": outside_context_citations,
            "malformed_evidence_ids": malformed_citations,
            "unknown_provider_context_evidence_ids": unknown_context_evidence_ids,
            "incomplete_provider_context_evidence_ids": incomplete_context_evidence_ids,
            "orphaned_evidence_ids": orphaned_evidence,
            "uncited_numeric_line_numbers": uncited_numeric_lines,
            "unsupported_numeric_claims": unsupported_numeric_claims,
            "unsupported_factual_claims": unsupported_factual_claims,
            "evidence_company_mismatches": evidence_company_mismatches,
            "unaddressed_question_metric_groups": unaddressed_metric_groups,
            "invalid_decision_support_evidence_ids": sorted(set(invalid_decision_evidence_ids)),
            "invalid_decision_support_peer_contexts": sorted(set(invalid_peer_contexts)),
            "invalid_decision_support_metric_assessments": sorted(set(invalid_metric_assessments)),
            "invalid_decision_support_confidence_items": sorted(set(invalid_confidence_items)),
            "invalid_decision_support_action_briefs": sorted(set(invalid_action_briefs)),
            "invalid_decision_support_data_gap_observations": invalid_data_gap_observations,
        },
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a DART orchestration v2 JSON response")
    parser.add_argument("result", type=Path, help="Path to an orchestration response JSON file")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = json.loads(
        args.result.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite_json,
    )
    evaluation = evaluate_orchestration_result(result)
    rendered = json.dumps(evaluation, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 1 if evaluation["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
