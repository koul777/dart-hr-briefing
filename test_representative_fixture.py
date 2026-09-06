from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent_orchestration import WorkforceAgentOrchestrator


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "workforce" / "representative_2024_11011.json"


class RepresentativeFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_is_synthetic_and_contains_no_personal_executive_fields(self) -> None:
        self.assertEqual(self.document["fixture_version"], 1)
        self.assertTrue(all(
            item["company"]["corp_code"].startswith("9")
            for item in self.document["observations"]
        ))
        serialized = json.dumps(self.document, ensure_ascii=False)
        for forbidden_key in ('"nm"', '"birth_ym"', '"main_career"'):
            self.assertNotIn(forbidden_key, serialized)

    def test_fixture_runs_end_to_end_with_stable_evidence(self) -> None:
        first = WorkforceAgentOrchestrator().run(self.document["observations"])
        second = WorkforceAgentOrchestrator().run(self.document["observations"])

        self.assertEqual(first["status"], "partial")
        self.assertEqual(first["policy"]["status"], "allowed")
        self.assertEqual(first["policy"]["mode"], "limited")
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["evidence"]["ledger"], second["evidence"]["ledger"])
        by_code = {
            item["company"]["corp_code"]: item
            for item in first["facts"]["records"]
        }
        self.assertEqual(by_code["90000001"]["metrics"]["employees_total"], 1500)
        self.assertEqual(by_code["90000002"]["metrics"]["employees_total"], 700)
        self.assertTrue(all(
            item["source_urls"] for item in first["evidence"]["ledger"]
        ))


if __name__ == "__main__":
    unittest.main()
