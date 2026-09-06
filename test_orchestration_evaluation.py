from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from agent_orchestration import WorkforceAgentOrchestrator
from orchestration_evaluation import EXPECTED_AGENTS, evaluate_orchestration_result


def evaluation_observation() -> dict:
    return {
        "company": {"corp_code": "001", "corp_name": "A사"},
        "year": "2024",
        "report_code": "11011",
        "employee_rows": [{
            "sexdstn": "전체",
            "sm": "100",
            "rgllbr_co": "90",
            "cnttk_co": "10",
            "avrg_cnwk_sdytrn": "5",
            "jan_salary_am": "50000000",
            "rcept_no": "20250000000001",
        }],
        "executive_rows": [{
            "sexdstn": "남",
            "ofcps": "사내이사",
            "rgist_exctv_at": "등기임원",
            "fte_at": "상근",
            "hffc_pd": "24개월",
            "tenure_end_on": "2027년 12월 31일",
            "rcept_no": "20250000000001",
        }],
        "unregistered_pay_rows": [{
            "nmpr": "1",
            "fyer_salary_totamt": "100000000",
            "jan_salary_am": "100000000",
            "rcept_no": "20250000000001",
        }],
        "financials": {"revenue": 10000000000, "operating_profit": 1000000000},
        "source_urls": [
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250000000001"
        ],
    }


class OrchestrationEvaluationTests(unittest.TestCase):
    def test_scorecard_fails_safely_on_malformed_privacy_and_deep_provider_output(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        result["privacy"] = ["not-a-mapping"]
        result["policy"] = {
            **result["policy"],
            "eligible_observation_ids": [{}],
        }
        result["provider"] = {
            **result["provider"],
            "status": "completed",
            "result": "검증 대상",
        }
        result["provider_validation"] = {"status": "passed"}

        with patch(
            "orchestration_evaluation._claim_segments",
            side_effect=RecursionError,
        ):
            evaluation = evaluate_orchestration_result(result)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("invalid_privacy_shape", evaluation["failures"])
        self.assertIn(
            "invalid_provider_policy_observation_ids",
            evaluation["failures"],
        )
        self.assertIn("invalid_provider_output_shape", evaluation["failures"])

    def test_scorecard_accepts_grounded_common_korean_salary_unit(self) -> None:
        class Provider:
            configured = True

            def analyze(self, *, prompt, context):
                evidence = next(
                    item for item in context["evidence"]
                    if item["metric_id"] == "average_salary"
                )
                return f"평균 급여는 5천만원 [{evidence['evidence_id']}]"

        result = WorkforceAgentOrchestrator(provider=Provider()).run(
            [evaluation_observation()]
        )

        evaluation = evaluate_orchestration_result(result)

        self.assertEqual(result["provider_validation"]["status"], "passed")
        self.assertEqual(evaluation["status"], "passed")

    def test_scorecard_accepts_grounded_ratio_expressed_as_multiple(self) -> None:
        class Provider:
            configured = True

            def analyze(self, *, prompt, context):
                evidence = next(
                    item for item in context["evidence"]
                    if item["metric_id"] == "current_ratio"
                )
                return f"유동비율은 2배 [{evidence['evidence_id']}]"

        item = evaluation_observation()
        item["financials"].update({
            "current_assets": 200,
            "current_liabilities": 100,
            "current_ratio": 200,
        })
        result = WorkforceAgentOrchestrator(provider=Provider()).run(
            [item], request_context={"metric_ids": ["current_ratio"]}
        )

        evaluation = evaluate_orchestration_result(result)

        self.assertEqual(result["provider_validation"]["status"], "passed")
        self.assertEqual(evaluation["status"], "passed")

    def test_scorecard_returns_failures_for_malformed_shapes(self) -> None:
        malformed_results = (
            None,
            [],
            {
                "schema_version": 2,
                "facts": {"records": ["bad-record"]},
                "evidence": {"ledger": {"bad": "shape"}},
                "trace": "bad-trace",
                "policy": {"eligible_observation_ids": 7},
                "provider": {
                    "status": "completed",
                    "result": {"value": float("inf")},
                    "context_summary": {"included_metric_ids": 7},
                },
                "quality": {"records": ["bad-quality"]},
            },
        )

        for malformed in malformed_results:
            with self.subTest(malformed=malformed):
                evaluation = evaluate_orchestration_result(malformed)
                self.assertEqual(evaluation["status"], "failed")
                self.assertTrue(evaluation["failures"])

    def test_scorecard_fails_safely_on_malformed_decision_semantics(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])

        def mutate_metric_ids(candidate):
            candidate["decision_support"]["briefs"][0]["metric_ids"] = 7

        def mutate_assessments(candidate):
            candidate["decision_support"]["briefs"][0]["metric_assessments"] = 7

        def mutate_coverage(candidate):
            candidate["decision_support"]["briefs"][0]["metric_assessments"][0]["coverage"] = "bad"

        def mutate_evidence_ids(candidate):
            candidate["decision_support"]["briefs"][0]["metric_assessments"][0]["evidence_ids"] = 7

        def mutate_peer(candidate):
            candidate["decision_support"]["briefs"][0]["peer_context"] = 7

        def mutate_signal_catalog(candidate):
            candidate["decision_support"]["signal_catalog"] = 7

        def mutate_evidence_value(candidate):
            evidence_id = candidate["decision_support"]["briefs"][0]["peer_context"][0]["evidence_id"]
            next(
                item for item in candidate["evidence"]["ledger"]
                if item["evidence_id"] == evidence_id
            )["value"] = "not-a-number"

        for mutate in (
            mutate_metric_ids,
            mutate_assessments,
            mutate_coverage,
            mutate_evidence_ids,
            mutate_peer,
            mutate_signal_catalog,
            mutate_evidence_value,
        ):
            with self.subTest(mutation=mutate.__name__):
                candidate = copy.deepcopy(result)
                mutate(candidate)

                evaluation = evaluate_orchestration_result(candidate)

                self.assertEqual(evaluation["status"], "failed")
                self.assertTrue(evaluation["failures"])

    def test_complete_deterministic_result_passes_scorecard(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])

        evaluation = evaluate_orchestration_result(result)

        self.assertEqual(evaluation["status"], "passed")
        self.assertEqual(evaluation["failures"], [])
        self.assertEqual(evaluation["metrics"]["source_link_rate"], 1.0)
        self.assertEqual(evaluation["metrics"]["trace_agent_count"], len(EXPECTED_AGENTS))
        self.assertEqual(evaluation["metrics"]["decision_brief_count"], 3)
        self.assertGreaterEqual(evaluation["metrics"]["decision_evidence_count"], 3)

    def test_scorecard_detects_tampered_decision_support_evidence(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["decision_support"]["briefs"][0]["evidence_ids"][0] = (
            "EV-deadbeefdead"
        )
        tampered["decision_support"]["data_gaps"].append({
            "observation_id": "OBS-deadbeefdead",
            "gap_type": "source_link_gap",
            "details": ["tampered"],
        })

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "invalid_decision_support_evidence_ids",
            evaluation["failures"],
        )
        self.assertIn(
            "invalid_decision_support_data_gaps",
            evaluation["failures"],
        )

    def test_scorecard_rejects_tampered_evidence_summary(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["evidence"]["summary"].pop("restatement_verification")

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("invalid_evidence_summary_contract", evaluation["failures"])

    def test_scorecard_detects_tampered_decision_support_semantics(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        brief = tampered["decision_support"]["briefs"][0]
        assessment = brief["metric_assessments"][0]
        assessment["coverage"]["comparable_observation_count"] = 99
        assessment["status"] = "ready"
        assessment["signal_type"] = "lagging"
        brief["selected_metric_id"] = brief["metric_assessments"][-1]["metric_id"]
        tampered["decision_support"]["signal_catalog"][0]["signal_type"] = "lagging"

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "invalid_decision_support_signal_catalog",
            evaluation["failures"],
        )
        self.assertIn(
            "invalid_decision_support_metric_assessments",
            evaluation["failures"],
        )

    def test_scorecard_detects_tampered_decision_dimensions(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["decision_support"]["readiness"].pop()

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "invalid_decision_support_dimensions",
            evaluation["failures"],
        )

    def test_scorecard_detects_tampered_decision_action_contract(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        brief = tampered["decision_support"]["briefs"][0]
        brief["decision_action"] = "즉시 인력을 감축합니다."
        brief["cohort_limit"] = "업계 표준 벤치마크입니다."

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "invalid_decision_support_action_contract",
            evaluation["failures"],
        )

    def test_scorecard_detects_tampered_decision_confidence_contract(self) -> None:
        result = WorkforceAgentOrchestrator().run([
            evaluation_observation(),
            {**evaluation_observation(), "company": {"corp_code": "002", "corp_name": "B사"}},
        ])

        for tamper in ("confidence", "quality", "reasons"):
            with self.subTest(tamper=tamper):
                candidate = copy.deepcopy(result)
                readiness = next(
                    item for item in candidate["decision_support"]["readiness"]
                    if item["dimension_id"] == "productivity"
                )
                brief = next(
                    item for item in candidate["decision_support"]["briefs"]
                    if item["brief_id"] == "productivity"
                )
                if tamper == "confidence":
                    readiness["confidence"] = brief["confidence"] = "high"
                elif tamper == "quality":
                    for item in (readiness, brief):
                        item["metric_assessments"][0]["quality_complete"] = False
                else:
                    readiness["reason_codes"] = brief["reason_codes"] = [
                        "peer_benchmark_available"
                    ]

                evaluation = evaluate_orchestration_result(candidate)

                self.assertEqual(evaluation["status"], "failed")
                self.assertTrue({
                    "invalid_decision_support_confidence_contract",
                    "invalid_decision_support_metric_assessments",
                }.intersection(evaluation["failures"]))

    def test_scorecard_detects_tampered_decision_narrative_semantics(self) -> None:
        result = WorkforceAgentOrchestrator().run([
            evaluation_observation(),
            {**evaluation_observation(), "company": {"corp_code": "002", "corp_name": "B사"}},
        ])

        for tamper in ("dimension", "peer", "conclusion", "action", "completeness"):
            with self.subTest(tamper=tamper):
                candidate = copy.deepcopy(result)
                readiness = next(
                    item for item in candidate["decision_support"]["readiness"]
                    if item["dimension_id"] == "productivity"
                )
                brief = next(
                    item for item in candidate["decision_support"]["briefs"]
                    if item["brief_id"] == "productivity"
                )
                if tamper == "dimension":
                    readiness["metric_ids"].reverse()
                elif tamper == "peer":
                    brief["peer_context"][0]["peer_delta"] = 999
                elif tamper == "conclusion":
                    brief["conclusion"] = "A사가 우월하므로 즉시 인력을 감축합니다."
                elif tamper == "action":
                    brief["decision_action"] = (
                        f"즉시 감축 · {brief['next_data'][0]}도 나중에 확인합니다."
                    )
                else:
                    completeness = next(
                        item for item in candidate["decision_support"]["readiness"]
                        if item["dimension_id"] == "data_completeness"
                    )
                    completeness["confidence"] = (
                        "low" if completeness["confidence"] == "high" else "high"
                    )

                evaluation = evaluate_orchestration_result(candidate)

                self.assertEqual(evaluation["status"], "failed")
                self.assertTrue({
                    "invalid_decision_support_metric_assessments",
                    "invalid_decision_support_action_contract",
                    "invalid_decision_support_completeness_contract",
                }.intersection(evaluation["failures"]))

    def test_scorecard_detects_tampered_trace_and_unknown_citation(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["trace"] = tampered["trace"][:-1]
        tampered["provider"] = {
            "status": "completed",
            "result": "확인된 값 [EV-deadbeefdead]",
        }

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("incomplete_trace", evaluation["failures"])
        self.assertIn("unknown_evidence_citations", evaluation["failures"])

    def test_scorecard_detects_duplicate_and_orphaned_evidence(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        duplicate = copy.deepcopy(tampered["evidence"]["ledger"][0])
        tampered["evidence"]["ledger"].append(duplicate)
        tampered["evidence"]["ledger"][1]["observation_id"] = "OBS-deadbeefdead"

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("duplicate_evidence_ids", evaluation["failures"])
        self.assertIn("orphaned_evidence", evaluation["failures"])

    def test_scorecard_rejects_citation_not_in_provider_handoff(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        included = set(tampered["provider"]["context_summary"]["included_metric_ids"])
        excluded = next(
            item
            for item in tampered["evidence"]["ledger"]
            if item["metric_id"] not in included
        )
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": f"전달되지 않은 근거 [{excluded['evidence_id']}]",
        }

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("citations_outside_provider_context", evaluation["failures"])

    def test_scorecard_uses_exact_provider_evidence_ids_within_same_metric(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        included_ids = tampered["provider"]["context_summary"][
            "included_evidence_ids"
        ]
        excluded_id = included_ids[0]
        tampered["provider"]["context_summary"]["included_evidence_ids"] = (
            included_ids[1:]
        )
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": f"Provider handoff outside-context citation [{excluded_id}]",
        }
        tampered["provider_output_validation"] = {
            "status": "passed",
            "reason_codes": [],
        }

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("citations_outside_provider_context", evaluation["failures"])

    def test_scorecard_rejects_invalid_provider_context_evidence_shape(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"]["context_summary"]["included_evidence_ids"] = "invalid"

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("invalid_provider_context_evidence_ids", evaluation["failures"])

    def test_scorecard_audits_provider_context_metadata_integrity(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        included_ids = tampered["provider"]["context_summary"][
            "included_evidence_ids"
        ]
        included_ids.extend([included_ids[0].upper(), "EV-deadbeefdead"])

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("duplicate_provider_context_evidence_ids", evaluation["failures"])
        self.assertIn("unknown_provider_context_evidence_ids", evaluation["failures"])
        self.assertIn("provider_context_evidence_count_mismatch", evaluation["failures"])
        self.assertEqual(
            evaluation["details"]["unknown_provider_context_evidence_ids"],
            ["EV-deadbeefdead"],
        )

    def test_scorecard_rejects_provider_context_missing_decision_evidence(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        omitted = tampered["decision_support"]["briefs"][0]["evidence_ids"][0]
        context_summary = tampered["provider"]["context_summary"]
        context_summary["included_evidence_ids"] = [
            evidence_id
            for evidence_id in context_summary["included_evidence_ids"]
            if evidence_id != omitted
        ]
        context_summary["evidence_count"] = len(context_summary["included_evidence_ids"])
        context_summary["truncated"] = (
            context_summary["candidate_evidence_count"]
            > context_summary["evidence_count"]
        )

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "decision_support_evidence_outside_provider_context",
            evaluation["failures"],
        )

    def test_scorecard_rejects_exact_provider_context_subset_omission(self) -> None:
        healthy = evaluation_observation()
        healthy["company"] = {"corp_code": "002", "corp_name": "B사"}
        failed = evaluation_observation()
        failed["errors"] = [{"source": "people_pipeline", "message": "failed"}]

        for items in ([healthy], [failed, healthy]):
            with self.subTest(limited=len(items) == 2):
                result = WorkforceAgentOrchestrator().run(items)
                tampered = copy.deepcopy(result)
                context_summary = tampered["provider"]["context_summary"]
                included_ids = context_summary["included_evidence_ids"]
                omitted = next(
                    item["evidence_id"]
                    for item in tampered["evidence"]["ledger"]
                    if item["metric_id"] == "revenue"
                    and item["evidence_id"] in included_ids
                )
                context_summary["included_evidence_ids"] = [
                    evidence_id for evidence_id in included_ids
                    if evidence_id != omitted
                ]
                context_summary["evidence_count"] = len(
                    context_summary["included_evidence_ids"]
                )
                context_summary["truncated"] = (
                    context_summary["candidate_evidence_count"]
                    > context_summary["evidence_count"]
                )

                evaluation = evaluate_orchestration_result(tampered)

                self.assertEqual(evaluation["status"], "failed")
                self.assertIn(
                    "provider_context_selection_mismatch",
                    evaluation["failures"],
                )

    def test_scorecard_rejects_malformed_citation_token(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "형식이 틀린 근거 [EV-hallucinated]",
        }

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn("malformed_evidence_citations", evaluation["failures"])

    def test_scorecard_detects_provider_validation_state_mismatch(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "검증 전 결과",
        }
        tampered["provider_validation"] = {"status": "skipped"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn(
            "completed_provider_without_passed_validation",
            evaluation["failures"],
        )

    def test_scorecard_rechecks_completed_provider_causal_policy(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "이직률 증가로 인해 생산성이 하락했습니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("provider_causal_policy_mismatch", evaluation["failures"])

    def test_scorecard_rechecks_completed_provider_person_policy(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "홍길동 대표이사는 성과가 부족합니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "provider_person_judgment_policy_mismatch",
            evaluation["failures"],
        )

    def test_scorecard_rechecks_tampered_automated_hr_action_policy(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "정규직을 줄이고 계약직 채용을 확대해야 합니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "provider_automated_hr_action_policy_mismatch",
            evaluation["failures"],
        )

    def test_scorecard_rechecks_tampered_protected_characteristic_policy(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "여성 직원은 성과가 낮으므로 채용 우선순위를 낮춰야 합니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "provider_protected_characteristic_policy_mismatch",
            evaluation["failures"],
        )

    def test_scorecard_rechecks_tampered_uncited_factual_claim(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "이사회의 사내이사 비중이 감소했습니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn(
            "provider_factual_claim_without_citation",
            evaluation["failures"],
        )
        self.assertEqual(
            evaluation["details"]["unsupported_factual_claims"],
            [{"segment_index": 1, "claim_type": "factual"}],
        )

    def test_scorecard_allows_explicit_hr_policy_limits_after_recheck(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": [
                "성별만으로 개인 성과를 평가할 수 없습니다.",
                "Gender must not be used as a basis for hiring decisions.",
            ],
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertNotEqual(evaluation["status"], "failed")
        self.assertNotIn(
            "provider_automated_hr_action_policy_mismatch",
            evaluation["failures"],
        )
        self.assertNotIn(
            "provider_protected_characteristic_policy_mismatch",
            evaluation["failures"],
        )
        self.assertNotIn(
            "provider_factual_claim_without_citation",
            evaluation["failures"],
        )

    def test_scorecard_rejects_uncited_numeric_provider_claim(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": "직원 수는 999명입니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn(
            "provider_numeric_claim_without_citation",
            evaluation["failures"],
        )

    def test_scorecard_rejects_uncited_numeric_line_among_cited_lines(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        evidence_id = tampered["evidence"]["ledger"][0]["evidence_id"]
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": f"근거가 있는 설명 [{evidence_id}]\n직원 수는 999명입니다.",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn(
            "provider_numeric_claim_without_citation",
            evaluation["failures"],
        )
        self.assertEqual(
            evaluation["details"]["uncited_numeric_line_numbers"],
            [2],
        )

    def test_scorecard_rejects_structured_cross_field_citation(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        salary = next(
            item for item in tampered["evidence"]["ledger"]
            if item["metric_id"] == "average_salary"
        )
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": {
                "claim": "평균 급여는 5,000만원입니다.",
                "citation": salary["evidence_id"],
            },
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn("provider_numeric_claim_without_citation", evaluation["failures"])
        self.assertIn("provider_numeric_claim_not_grounded", evaluation["failures"])

    def test_scorecard_rejects_coarsely_rounded_contradictory_claim(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        revenue = next(
            item for item in tampered["evidence"]["ledger"]
            if item["metric_id"] == "revenue"
        )
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": f"매출은 1조원입니다 [{revenue['evidence_id']}]",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn("provider_numeric_claim_not_grounded", evaluation["failures"])

    def test_scorecard_rejects_scientific_notation_contradiction(self) -> None:
        result = WorkforceAgentOrchestrator().run([evaluation_observation()])
        tampered = copy.deepcopy(result)
        revenue = next(
            item for item in tampered["evidence"]["ledger"]
            if item["metric_id"] == "revenue"
        )
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": f"매출은 1e15원입니다 [{revenue['evidence_id']}]",
        }
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertIn("provider_numeric_claim_not_grounded", evaluation["failures"])


if __name__ == "__main__":
    unittest.main()
