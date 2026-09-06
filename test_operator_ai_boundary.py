from __future__ import annotations

import io
import json
import unittest
from http import HTTPStatus
from unittest.mock import patch

from agent_orchestration import WorkforceObservation
from server import DashboardHandler, _valid_operator_ai_token


def _observation() -> WorkforceObservation:
    return WorkforceObservation.from_mapping({
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
        "financials": {"revenue": 10_000_000_000},
        "source_urls": [
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250000000001"
        ],
    })


def _analysis_handler(headers: dict[str, str] | None = None) -> tuple[DashboardHandler, list]:
    body = json.dumps({
        "question": "비교해줘",
        "view": "strategy",
        "corp_codes": ["001"],
        "year": "2024",
        "report_code": "11011",
    }).encode("utf-8")
    handler = DashboardHandler.__new__(DashboardHandler)
    handler.path = "/api/analysis"
    handler.headers = {
        "Content-Length": str(len(body)),
        "Content-Type": "application/json",
        "Host": "localhost",
        **(headers or {}),
    }
    handler.rfile = io.BytesIO(body)
    handler.enforce_rate_limit = lambda: True
    responses: list = []
    handler.send_json = lambda payload, status=HTTPStatus.OK: responses.append(
        (status, payload)
    )
    return handler, responses


class OperatorAIBoundaryTests(unittest.TestCase):
    def test_token_contract_rejects_short_or_unsafe_values(self) -> None:
        self.assertFalse(_valid_operator_ai_token("short"))
        self.assertFalse(_valid_operator_ai_token("x" * 31))
        self.assertFalse(_valid_operator_ai_token("x" * 31 + "\n"))
        self.assertTrue(_valid_operator_ai_token("x" * 32))

    def test_server_provider_is_not_anonymous_fallback(self) -> None:
        class CountingProvider:
            configured = True
            calls = 0

            def analyze(self, *, prompt, context):
                self.calls += 1
                return "must not run"

        provider = CountingProvider()
        handler, responses = _analysis_handler()
        with (
            patch("server.ALLOW_OPERATOR_AI_PROVIDER", False),
            patch("server.WORKFORCE_AI_PROVIDER", provider),
            patch("server.fetch_workforce_observations", return_value=[_observation()]),
        ):
            handler.do_POST()

        self.assertEqual(responses[-1][0], HTTPStatus.OK)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(responses[-1][1]["provider"]["status"], "not_configured")

    def test_user_provider_requires_explicit_data_consent_before_dart_fetch(self) -> None:
        handler, responses = _analysis_handler({
            "X-OpenAI-API-Key": "sk-user-test-key",
        })
        with patch("server.fetch_workforce_observations") as fetch:
            handler.do_POST()

        fetch.assert_not_called()
        self.assertEqual(responses[-1][0], HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            responses[-1][1]["error_code"],
            "provider_data_consent_required",
        )

    def test_operator_provider_requires_matching_header_token(self) -> None:
        class Provider:
            configured = True

        provider = Provider()
        secret = "operator-token-" + "x" * 24
        handler, _ = _analysis_handler({"X-DART-Operator-Token": secret})
        with (
            patch("server.ALLOW_OPERATOR_AI_PROVIDER", True),
            patch("server.OPERATOR_AI_TOKEN", secret),
            patch("server.WORKFORCE_AI_PROVIDER", provider),
        ):
            self.assertIs(handler.request_operator_ai_provider(), provider)
            handler.headers["X-DART-Operator-Token"] = "wrong-" + "x" * 32
            self.assertIsNone(handler.request_operator_ai_provider())

    def test_malformed_numeric_fields_do_not_echo_user_content(self) -> None:
        private_marker = "private-user-request-marker"
        handler, responses = _analysis_handler()
        body = json.dumps({
            "question": "compare",
            "view": "strategy",
            "corp_codes": ["001"],
            "year": "2024",
            "report_code": "11011",
            "page": private_marker,
        }).encode("utf-8")
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)

        handler.do_POST()

        self.assertEqual(responses[-1][0], HTTPStatus.BAD_REQUEST)
        self.assertNotIn(
            private_marker,
            json.dumps(responses[-1][1], ensure_ascii=False),
        )


if __name__ == "__main__":
    unittest.main()
