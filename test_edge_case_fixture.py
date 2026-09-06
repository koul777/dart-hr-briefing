from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from agent_orchestration import WorkforceAgentOrchestrator
from orchestration_evaluation import evaluate_orchestration_result


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "workforce" / "edge_cases_2024_11011.json"
SCHEMA = ROOT / "schemas" / "workforce_orchestration_v2.schema.json"


class EdgeCaseFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_fixture_is_synthetic_and_contains_no_person_fields(self) -> None:
        serialized = json.dumps(self.document, ensure_ascii=False)
        self.assertTrue(all(
            item["company"]["corp_code"].startswith("9")
            for item in self.document["observations"]
        ))
        for forbidden_key in ('"nm"', '"birth_ym"', '"main_career"'):
            self.assertNotIn(forbidden_key, serialized)

    def test_mixed_failure_run_matches_declared_contract(self) -> None:
        result = WorkforceAgentOrchestrator().run(self.document["observations"])
        expected = self.document["expectations"]

        self.assertEqual(result["status"], expected["status"])
        self.assertEqual(result["policy"]["status"], expected["policy_status"])
        self.assertEqual(result["policy"]["mode"], expected["policy_mode"])
        observation_to_code = {
            record["observation_id"]: record["company"]["corp_code"]
            for record in result["facts"]["records"]
        }
        actual_quality = {
            observation_to_code[item["observation_id"]]: item["status"]
            for item in result["quality"]["records"]
        }
        eligible_codes = sorted(
            observation_to_code[observation_id]
            for observation_id in result["policy"]["eligible_observation_ids"]
        )
        self.assertEqual(actual_quality, expected["quality_by_corp_code"])
        self.assertEqual(eligible_codes, expected["eligible_corp_codes"])
        self.assertEqual(result["provider"]["status"], "not_configured")
        self.assertNotEqual(evaluate_orchestration_result(result)["status"], "failed")

        schema_errors = list(Draft202012Validator(self.schema).iter_errors(result))
        self.assertEqual(schema_errors, [], "\n".join(error.message for error in schema_errors))


if __name__ == "__main__":
    unittest.main()
