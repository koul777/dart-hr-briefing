from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from agent_orchestration import WorkforceAgentOrchestrator


ROOT = Path(__file__).resolve().parent


def schema_observation() -> dict:
    return {
        "company": {"corp_code": "001", "corp_name": "A사", "stock_code": "000001"},
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
        "executive_rows": [],
        "unregistered_pay_rows": [],
        "financials": {"revenue": 10000000000, "operating_profit": 1000000000},
        "source_urls": [
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250000000001"
        ],
    }


class OrchestrationSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schemas" / "workforce_orchestration_v2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.validator = Draft202012Validator(cls.schema)

    def test_v2_response_matches_published_json_schema(self) -> None:
        result = WorkforceAgentOrchestrator().run([schema_observation()])

        errors = sorted(self.validator.iter_errors(result), key=lambda error: list(error.path))

        self.assertEqual(errors, [], "\n".join(error.message for error in errors))
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_schema_rejects_wrong_version_and_missing_evidence(self) -> None:
        result = WorkforceAgentOrchestrator().run([schema_observation()])
        result["schema_version"] = 1
        result.pop("evidence")

        messages = [error.message for error in self.validator.iter_errors(result)]

        self.assertTrue(any("evidence" in message for message in messages))
        self.assertTrue(any("2 was expected" in message for message in messages))

        unknown = WorkforceAgentOrchestrator().run([schema_observation()])
        unknown["unexpected_top_level_field"] = True
        unknown_messages = [
            error.message for error in self.validator.iter_errors(unknown)
        ]
        self.assertTrue(any("Additional properties" in message for message in unknown_messages))

        invalid_context = WorkforceAgentOrchestrator().run([schema_observation()])
        invalid_context["provider"]["context_summary"]["included_evidence_ids"] = [
            "EV-not-a-valid-id"
        ]
        context_messages = [
            error.message for error in self.validator.iter_errors(invalid_context)
        ]
        self.assertTrue(any("does not match" in message for message in context_messages))

    def test_schema_separates_readiness_and_brief_properties(self) -> None:
        result = WorkforceAgentOrchestrator().run([schema_observation()])

        readiness_tamper = copy.deepcopy(result)
        readiness_tamper["decision_support"]["readiness"][0][
            "decision_action"
        ] = "readiness에는 허용되지 않는 필드"
        readiness_messages = [
            error.message for error in self.validator.iter_errors(readiness_tamper)
        ]

        brief_tamper = copy.deepcopy(result)
        brief_tamper["decision_support"]["briefs"][0]["unexpected"] = True
        brief_messages = [
            error.message for error in self.validator.iter_errors(brief_tamper)
        ]

        self.assertTrue(any("Unevaluated properties" in message for message in readiness_messages))
        self.assertTrue(any("Unevaluated properties" in message for message in brief_messages))

    def test_no_data_invalid_input_and_rejected_provider_are_schema_valid(self) -> None:
        no_data = schema_observation()
        no_data.update({
            "employee_rows": [],
            "executive_rows": [],
            "unregistered_pay_rows": [],
            "financials": {},
        })

        class InvalidCitationProvider:
            configured = True

            def analyze(self, *, prompt, context):
                return "잘못된 근거 [EV-hallucinated]"

        results = [
            WorkforceAgentOrchestrator().run([no_data]),
            WorkforceAgentOrchestrator().run([
                schema_observation(),
                schema_observation(),
            ]),
            WorkforceAgentOrchestrator(provider=InvalidCitationProvider()).run([
                schema_observation()
            ]),
        ]

        for result in results:
            with self.subTest(status=result["status"]):
                errors = list(self.validator.iter_errors(result))
                self.assertEqual(errors, [], "\n".join(error.message for error in errors))
                json.dumps(result, ensure_ascii=False, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
