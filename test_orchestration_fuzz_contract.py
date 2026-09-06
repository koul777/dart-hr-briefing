from __future__ import annotations

import json
import random
import re
import unittest

from agent_orchestration import WorkforceAgentOrchestrator


class OrchestrationFuzzContractTests(unittest.TestCase):
    def test_seeded_malformed_field_matrix_is_fail_safe_and_standard_json(self) -> None:
        randomizer = random.Random(20260830)
        scalar_pool = (
            None,
            "",
            "-",
            "NaN",
            "Infinity",
            "-1",
            "1.5",
            "0",
            "1",
            "1e308",
            True,
            {"unexpected": "mapping"},
            ["unexpected", "list"],
            "홍길동",
        )

        for index in range(120):
            employee = {
                "sexdstn": "전체",
                "sm": randomizer.choice(scalar_pool),
                "rgllbr_co": randomizer.choice(scalar_pool),
                "cnttk_co": randomizer.choice(scalar_pool),
                "avrg_cnwk_sdytrn": randomizer.choice(scalar_pool),
                "fyer_salary_totamt": randomizer.choice(scalar_pool),
                "jan_salary_am": randomizer.choice(scalar_pool),
            }
            executive = {
                "nm": "홍길동",
                "sexdstn": randomizer.choice(scalar_pool),
                "ofcps": randomizer.choice(scalar_pool),
                "rgist_exctv_at": randomizer.choice(scalar_pool),
                "fte_at": randomizer.choice(scalar_pool),
                "hffc_pd": randomizer.choice(scalar_pool),
                "tenure_end_on": randomizer.choice(scalar_pool),
            }
            unregistered_pay = {
                "nmpr": randomizer.choice(scalar_pool),
                "fyer_salary_totamt": randomizer.choice(scalar_pool),
                "jan_salary_am": randomizer.choice(scalar_pool),
                "rm": "홍길동 개인 메모",
            }
            item = {
                "company": {
                    "corp_code": f"{index:08d}",
                    "corp_name": f"변이기업{index}",
                },
                "year": "2024",
                "report_code": "11011",
                "employee_rows": [employee],
                "executive_rows": [executive],
                "unregistered_pay_rows": [unregistered_pay],
                "financials": {
                    "revenue": randomizer.choice(scalar_pool),
                    "operating_profit": randomizer.choice(scalar_pool),
                    "assets": randomizer.choice(scalar_pool),
                },
                "source_urls": [
                    "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20240000000001",
                    "https://attacker.example/fake",
                ],
                "errors": (
                    [{"source": "fuzz", "message": "sk-fuzz-secret"}]
                    if index % 7 == 0
                    else []
                ),
            }

            with self.subTest(index=index):
                result = WorkforceAgentOrchestrator().run([item])
                serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)

                self.assertIn(result["status"], {"completed", "partial", "no_data", "error"})
                self.assertRegex(result["run_id"], r"^RUN-[0-9a-f]{12}$")
                self.assertNotIn("홍길동", serialized)
                self.assertNotIn("sk-fuzz-secret", serialized)
                self.assertNotIn("attacker.example", serialized)
                self.assertTrue(all(
                    re.fullmatch(r"EV-[0-9a-f]{12}", evidence["evidence_id"])
                    for evidence in result["evidence"]["ledger"]
                ))
                ledger_by_id = {
                    evidence["evidence_id"]: evidence
                    for evidence in result["evidence"]["ledger"]
                }
                for readiness in result["decision_support"]["readiness"]:
                    assessments = readiness["metric_assessments"]
                    self.assertEqual(
                        set(readiness["metric_ids"]),
                        {assessment["metric_id"] for assessment in assessments},
                    )
                    self.assertEqual(
                        set(readiness["evidence_ids"]),
                        {
                            evidence_id
                            for assessment in assessments
                            for evidence_id in assessment["evidence_ids"]
                        },
                    )
                    for assessment in assessments:
                        observations = {
                            ledger_by_id[evidence_id]["observation_id"]
                            for evidence_id in assessment["evidence_ids"]
                        }
                        count = len(observations)
                        expected_status = (
                            "ready" if count >= 2
                            else "directional_only" if count == 1
                            else "blocked"
                        )
                        self.assertEqual(assessment["status"], expected_status)
                        self.assertEqual(
                            assessment["coverage"]["comparable_observation_count"],
                            count,
                        )
                for brief in result["decision_support"]["briefs"]:
                    selected = next(
                        assessment
                        for assessment in brief["metric_assessments"]
                        if assessment["metric_id"] == brief["selected_metric_id"]
                    )
                    self.assertEqual(
                        brief["selected_metric_label"],
                        selected["metric_label"],
                    )
                    self.assertEqual(brief["signal_type"], selected["signal_type"])
                    self.assertIn("history_not_in_readiness", brief["reason_codes"])
                self.assertIsNone(result["provider_result"])


if __name__ == "__main__":
    unittest.main()
