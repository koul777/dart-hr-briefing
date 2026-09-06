from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from classroom_mode import (
    CLASSROOM_FIXTURE,
    CLASSROOM_FIXTURE_ID,
    CLASSROOM_WATERMARK,
    _load_fixture,
    build_classroom_payload,
)
from server import DashboardHandler


class ClassroomModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_classroom_payload()

    def test_payload_is_explicitly_synthetic_and_zero_network(self) -> None:
        sample = self.payload["sample"]
        self.assertTrue(sample["enabled"])
        self.assertEqual(sample["watermark"], CLASSROOM_WATERMARK)
        self.assertEqual(sample["fixture_id"], CLASSROOM_FIXTURE_ID)
        self.assertEqual(
            sample["provenance"],
            {
                "authoring_method": "hand-authored synthetic scenario",
                "source_data_used": False,
                "third_party_content_used": False,
                "intended_use": "education_and_software_testing_only",
                "contains_real_company_data": False,
                "contains_personal_data": False,
            },
        )
        self.assertEqual(sample["network_requests"], 0)
        self.assertFalse(sample["contains_real_company_data"])
        self.assertFalse(sample["contains_personal_data"])
        self.assertEqual(sample["evidence_references"], "synthetic_contract_only")
        self.assertFalse(sample["outbound_evidence_links"])
        self.assertEqual(
            sample["reference_scheme"],
            "urn:dart-hr-briefing:synthetic",
        )
        self.assertFalse(sample["receipt_numbers_exposed"])
        self.assertTrue(all(
            item["corp_code"].startswith("9")
            for item in self.payload["companies"]
        ))

    def test_bootstrap_covers_the_classroom_golden_path(self) -> None:
        count = len(self.payload["companies"])
        self.assertGreaterEqual(count, 2)
        self.assertEqual(len(self.payload["results"]), count)
        self.assertEqual(len(self.payload["previous"]), count)
        self.assertEqual(len(self.payload["history"]), count)
        self.assertEqual(len(self.payload["people"]), count)
        self.assertEqual(len(self.payload["people_history"]), count)
        self.assertEqual(
            self.payload["orchestration"]["source"],
            "synthetic_fixture",
        )
        self.assertEqual(
            self.payload["orchestration"]["request"]["data_mode"],
            "synthetic_classroom",
        )
        self.assertIn(self.payload["orchestration"]["status"], {"completed", "partial"})
        self.assertTrue(all(len(item["years"]) == 4 for item in self.payload["history"]))
        self.assertTrue(all(
            item["financials"]["operating_margin"] is not None
            for item in self.payload["results"]
        ))
        briefs = self.payload["orchestration"]["decision_support"]["briefs"]
        self.assertEqual(
            {
                item["dimension_id"]: item["selected_metric_id"]
                for item in briefs
            },
            {
                "productivity": "operating_profit_per_employee",
                "compensation_sustainability": "salary_to_revenue",
                "workforce_structure": "contract_share",
            },
        )
        self.assertTrue(all(item["status"] == "directional_only" for item in briefs))
        self.assertTrue(all(item["evidence_ids"] for item in briefs))

    def test_repeated_builds_are_byte_for_byte_deterministic(self) -> None:
        first = json.dumps(self.payload, ensure_ascii=False, sort_keys=True)
        second = json.dumps(
            build_classroom_payload(),
            ensure_ascii=False,
            sort_keys=True,
        )

        self.assertEqual(first, second)

    def test_fixture_contains_no_person_identifiers_or_real_company_names(self) -> None:
        serialized = CLASSROOM_FIXTURE.read_text(encoding="utf-8")
        for forbidden in (
            '"nm"',
            '"birth_ym"',
            '"main_career"',
            '"rcept_no"',
            '"source_urls"',
            "http://",
            "https://",
            "dart.fss.or.kr",
            "삼성",
            "SK하이닉스",
        ):
            self.assertNotIn(forbidden, serialized)
        fixture = json.loads(serialized)
        self.assertEqual(fixture["fixture_id"], CLASSROOM_FIXTURE_ID)
        self.assertFalse(fixture["provenance"]["source_data_used"])
        self.assertFalse(fixture["provenance"]["third_party_content_used"])
        self.assertTrue(all(
            str(item.get("synthetic_reference_id", "")).startswith("CLASSROOM-9")
            for item in fixture["observations"]
        ))

    def test_fixture_provenance_cannot_claim_real_or_third_party_source_data(self) -> None:
        fixture = json.loads(CLASSROOM_FIXTURE.read_text(encoding="utf-8"))
        tampered_documents = []
        for key in ("source_data_used", "third_party_content_used"):
            tampered = json.loads(json.dumps(fixture))
            tampered["provenance"][key] = True
            tampered_documents.append(tampered)
        wrong_id = json.loads(json.dumps(fixture))
        wrong_id["fixture_id"] = "unreviewed-classroom-data"
        tampered_documents.append(wrong_id)

        for document in tampered_documents:
            with self.subTest(document=document):
                fixture_path = Mock()
                fixture_path.read_text.return_value = json.dumps(document)
                with self.assertRaisesRegex(ValueError, "fixture contract"):
                    _load_fixture(fixture_path)

    def test_public_payload_exposes_only_non_network_synthetic_references(self) -> None:
        serialized = json.dumps(
            self.payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("http://", serialized.lower())
        self.assertNotIn("https://", serialized.lower())
        self.assertNotIn("dart.fss.or.kr", serialized.lower())
        self.assertNotIn("20991231", serialized)

        evidence = self.payload["orchestration"]["evidence"]
        self.assertEqual(evidence["reference_mode"], "synthetic_fixture_urn")
        self.assertFalse(evidence["external_source_links"])
        self.assertIn("실제 OpenDART 공시", evidence["source_notice"])
        self.assertTrue(evidence["ledger"])
        for item in evidence["ledger"]:
            self.assertTrue(item["source_coverage_complete"])
            self.assertEqual(item["receipt_numbers"], [])
            self.assertTrue(item["source_urls"])
            self.assertTrue(all(
                source.startswith("urn:dart-hr-briefing:synthetic:classroom-9")
                for source in item["source_urls"]
            ))

        for snapshot in evidence["snapshots"]:
            self.assertEqual(snapshot["receipt_numbers"], [])
            self.assertTrue(all(
                source.startswith("urn:dart-hr-briefing:synthetic:classroom-9")
                for source in snapshot["source_urls"]
            ))

    def test_http_bootstrap_never_calls_opendart(self) -> None:
        handler = DashboardHandler.__new__(DashboardHandler)
        handler.path = "/api/classroom/bootstrap"
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 44000)
        handler.origin_allowed = lambda: True
        handler.record_orchestration_telemetry = lambda payload: None
        captured: dict[str, object] = {}
        handler.send_json = lambda payload, status=200: captured.update(
            payload=payload, status=status
        )

        with patch("server.dart_request") as dart_request:
            handler.do_GET()

        dart_request.assert_not_called()
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["sample"]["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
