from __future__ import annotations

import copy
import io
import json
import re
import unittest
from contextlib import redirect_stderr
from http import HTTPStatus
from unittest.mock import patch

from agent_orchestration import WorkforceAgentOrchestrator
from openai_responses_adapter import OpenAIResponsesError
from orchestration_evaluation import evaluate_orchestration_result
from server import DARTError, DashboardHandler


SECRET_AND_PII_CASES = (
    ("user_openai_key", "sk-user-secret-redteam-123456"),
    ("operator_token", "operator-token-redteam-abcdefghijklmnopqrstuvwxyz"),
    ("email", "privacy.person@example.com"),
    ("phone", "010-2468-1357"),
    ("employee_id", "EMP-SECRET-77"),
    ("resident_number", "900101-1234567"),
    ("korean_name", "홍길동"),
    ("english_name", "John Smith"),
)
EXTENDED_PERSONAL_IDENTIFIER_CASES = (
    (
        "synthetic_070_phone",
        "070-0000-0000",
        "070-0000-0000 직원의 승진 검토",
        "담당자 전화번호는 070-0000-0000 입니다.",
    ),
    (
        "synthetic_e164_phone",
        "+1 202-555-0142",
        "+1 202-555-0142 employee promotion review",
        "Employee contact phone is +1 202-555-0142.",
    ),
    (
        "synthetic_idn_email",
        "테스트@예시.테스트",
        "테스트@예시.테스트 직원의 채용 검토",
        "담당자 이메일은 테스트@예시.테스트 입니다.",
    ),
    (
        "synthetic_punycode_email",
        "dummy@sample.xn--9t4b11yi5a",
        "dummy@sample.xn--9t4b11yi5a 직원의 채용 검토",
        "담당자 이메일은 dummy@sample.xn--9t4b11yi5a 입니다.",
    ),
    (
        "synthetic_lowercase_name",
        "alex example",
        "employee alex example promotion review",
        "employee alex example is the contact.",
    ),
    (
        "synthetic_initial_name",
        "q. example",
        "q. example should be promoted",
        "q. example is the employee contact.",
    ),
    (
        "synthetic_two_syllable_name",
        "김봄",
        "김봄 직원의 승진 검토",
        "김봄 직원의 연락처입니다.",
    ),
    (
        "synthetic_compound_surname",
        "남궁봄",
        "남궁봄 직원의 승진 검토",
        "남궁봄 직원의 연락처입니다.",
    ),
    (
        "synthetic_00_international_phone",
        "0044 20 7946 0958",
        "0044 20 7946 0958 employee promotion review",
        "Employee contact phone is 0044 20 7946 0958.",
    ),
    (
        "synthetic_grouped_phone",
        "202-555-0142",
        "202-555-0142 employee promotion review",
        "Employee contact phone is 202-555-0142.",
    ),
    (
        "synthetic_contextual_lowercase_name",
        "alex example",
        "alex example should be promoted",
        "alex example's performance is poor.",
    ),
    (
        "synthetic_slash_phone",
        "010/1234/5678",
        "010/1234/5678 employee promotion review",
        "Employee contact phone is 010/1234/5678.",
    ),
    (
        "synthetic_parenthesized_phone",
        "(202) 555-0142",
        "(202) 555-0142 employee promotion review",
        "Employee contact phone is (202) 555-0142.",
    ),
    (
        "synthetic_employee_identifier",
        "HR2048",
        "employee identifier: HR2048 compensation review",
        "Employee identifier: HR2048.",
    ),
)


def privacy_observation(*, errors: list[dict] | None = None) -> dict:
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
        "financials": {
            "revenue": 10000000000,
            "operating_profit": 1000000000,
        },
        "source_urls": [
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250000000001"
        ],
        "errors": errors or [],
    }


def personnel_question(label: str, value: str) -> str:
    if label == "email":
        return f"{value} 직원의 보상 검토"
    if label == "phone":
        return f"{value} 직원의 승진 검토"
    if label == "employee_id":
        return f"사번: {value} 직원의 평가 검토"
    if label == "resident_number":
        return f"{value} 직원의 해고 검토"
    if label in {"korean_name", "english_name"}:
        return f"{value} 직원의 승진 검토"
    if label == "operator_token":
        return f"token={value} 직원의 보상 검토"
    return f"API key={value} 직원의 보상 검토"


class RaisingProvider:
    configured = True
    provider_id = "redteam"
    provider_label = "Redteam Provider"

    def __init__(self, error: str) -> None:
        self.error = error

    def analyze(self, *, prompt, context):
        raise RuntimeError(self.error)


class ErrorMappingProvider:
    configured = True
    provider_id = "redteam"
    provider_label = "Redteam Provider"

    def __init__(self, error: str) -> None:
        self.error = error

    def analyze(self, *, prompt, context):
        return {"status": "error", "error": self.error}


class OutputProvider:
    configured = True
    provider_id = "redteam"
    provider_label = "Redteam Provider"

    def __init__(self, output: str) -> None:
        self.output = output
        self.context: dict | None = None

    def analyze(self, *, prompt, context):
        self.context = context
        return self.output


class MetadataProvider(OutputProvider):
    def __init__(self, secret: str) -> None:
        super().__init__("추가 검증이 필요합니다.")
        self.provider_id = f"provider-token={secret}"
        self.provider_label = f"Provider error owner {secret}"


def analysis_handler(
    *,
    path: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[DashboardHandler, list[tuple[HTTPStatus, dict]]]:
    encoded = json.dumps(body or {}).encode("utf-8")
    handler = object.__new__(DashboardHandler)
    handler.path = path
    handler.headers = {
        "Content-Length": str(len(encoded)),
        "Content-Type": "application/json",
        "Host": "localhost",
        **(headers or {}),
    }
    handler.rfile = io.BytesIO(encoded)
    handler.enforce_rate_limit = lambda: True
    responses: list[tuple[HTTPStatus, dict]] = []

    def capture(payload, status=HTTPStatus.OK):
        if int(status) >= 400 and "request_id" not in payload:
            payload = {**payload, "request_id": handler.request_correlation_id()}
        responses.append((status, payload))

    handler.send_json = capture
    return handler, responses


class SecretPrivacyRedTeamTests(unittest.TestCase):
    def test_question_mappings_redact_identifiers_and_secrets_before_handoff(self) -> None:
        cases = (
            ({"operator_token": "short-secret-redteam-123"}, "short-secret-redteam-123"),
            ({"openai_key": "short-secret-redteam-456"}, "short-secret-redteam-456"),
            ({"authorization": "short-secret-redteam-789"}, "short-secret-redteam-789"),
            (
                {"employee_id": "HR2048", "context": "직원 승진 검토"},
                "HR2048",
            ),
            (
                {"worker_identifier": "HR3072", "context": "employee review"},
                "HR3072",
            ),
            (
                {"phone": 12025550142, "context": "employee promotion review"},
                "12025550142",
            ),
        )
        for question, raw_identifier in cases:
            with self.subTest(question=question):
                provider = OutputProvider("추가 검증이 필요합니다.")
                result = WorkforceAgentOrchestrator(provider=provider).run(
                    [privacy_observation()],
                    request_context={"question": question},
                )
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(result, ensure_ascii=False),
                )
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(provider.context, ensure_ascii=False),
                )

    def test_natural_language_credential_labels_are_redacted_before_handoff(self) -> None:
        cases = (
            "openai_api_key=short-redteam-secret",
            "api key=short-redteam-secret",
            "DART OPERATOR AI TOKEN=short-redteam-secret",
            "credential=short-redteam-secret",
            "Authorization=short-redteam-secret",
            "Authorization=Basic short-redteam-secret",
            "OpenAI key=short-redteam-secret",
            "api\u200b_key=short-redteam-secret",
        )
        for credential in cases:
            with self.subTest(credential=credential):
                provider = OutputProvider("추가 검증이 필요합니다.")
                result = WorkforceAgentOrchestrator(provider=provider).run(
                    [privacy_observation()],
                    request_context={
                        "question": f"{credential} employee promotion review"
                    },
                )
                self.assertNotIn(
                    "short-redteam-secret",
                    json.dumps(result, ensure_ascii=False),
                )
                self.assertNotIn(
                    "short-redteam-secret",
                    json.dumps(provider.context, ensure_ascii=False),
                )

    def test_structured_provider_identifiers_and_secrets_fail_closed(self) -> None:
        cases = (
            {"api_key": "short-secret-redteam-123"},
            {"openai_key": "short-secret-redteam-456"},
            {"authorization": "short-secret-redteam-789"},
            {"employee_id": "HR2048"},
            {"worker_identifier": "HR3072"},
            {"phone": "0044 20 7946 0958"},
            {"email": "user@[192.0.2.1]"},
        )
        base = WorkforceAgentOrchestrator().run([privacy_observation()])
        for output in cases:
            raw_identifier = next(iter(output.values()))
            with self.subTest(output=output, path="runtime"):
                runtime = WorkforceAgentOrchestrator(
                    provider=OutputProvider(output)
                ).run([privacy_observation()])
                self.assertEqual(runtime["provider"]["status"], "rejected")
                self.assertIsNone(runtime["provider"]["result"])
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(runtime["provider_validation"], ensure_ascii=False),
                )

            with self.subTest(output=output, path="offline"):
                tampered = copy.deepcopy(base)
                tampered["provider"] = {
                    **tampered["provider"],
                    "status": "completed",
                    "result": output,
                }
                tampered["provider_result"] = output
                tampered["provider_validation"] = {"status": "passed"}
                evaluation = evaluate_orchestration_result(tampered)
                self.assertEqual(evaluation["status"], "failed")
                self.assertIn("privacy_literal_exposed", evaluation["failures"])
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(evaluation, ensure_ascii=False),
                )

    def test_offline_recheck_covers_alias_prompt_and_noncompleted_results(self) -> None:
        base = WorkforceAgentOrchestrator().run([privacy_observation()])
        private_surfaces = (
            ("provider_result", {"employee_id": "HR2048"}),
            ("prompt", "api_key=short-secret-redteam-123"),
        )
        for field, unsafe_value in private_surfaces:
            with self.subTest(field=field):
                tampered = copy.deepcopy(base)
                tampered[field] = unsafe_value
                evaluation = evaluate_orchestration_result(tampered)
                self.assertEqual(evaluation["status"], "failed")
                self.assertIn("privacy_literal_exposed", evaluation["failures"])
                self.assertNotIn(
                    str(unsafe_value),
                    json.dumps(evaluation, ensure_ascii=False),
                )

        tampered = copy.deepcopy(base)
        unlabeled_secret = "A" * 40
        tampered["prompt_handoff"]["error"] = f"upstream {unlabeled_secret}"
        evaluation = evaluate_orchestration_result(tampered)
        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("privacy_literal_exposed", evaluation["failures"])
        self.assertNotIn(unlabeled_secret, json.dumps(evaluation, ensure_ascii=False))

        for status in ("error", "not_configured", "skipped", "no_result"):
            with self.subTest(status=status):
                tampered = copy.deepcopy(base)
                retained = "승진을 보류하는 편이 좋겠습니다."
                tampered["provider"] = {
                    **tampered["provider"],
                    "status": status,
                    "result": retained,
                }
                tampered["provider_result"] = retained
                evaluation = evaluate_orchestration_result(tampered)
                self.assertEqual(evaluation["status"], "failed")
                self.assertIn(
                    "noncompleted_provider_retained_result",
                    evaluation["failures"],
                )

    def test_offline_non_json_provider_output_fails_closed(self) -> None:
        base = WorkforceAgentOrchestrator().run([privacy_observation()])
        secret = "api_key=short-secret-redteam-123"
        tampered = copy.deepcopy(base)
        tampered["provider"] = {
            **tampered["provider"],
            "status": "completed",
            "result": {secret},
        }
        tampered["provider_result"] = {secret}
        tampered["provider_validation"] = {"status": "passed"}

        evaluation = evaluate_orchestration_result(tampered)

        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("invalid_provider_output_shape", evaluation["failures"])
        self.assertNotIn(secret, json.dumps(evaluation, ensure_ascii=False))

    def test_extended_identifiers_never_reach_provider_or_final_response(self) -> None:
        for label, raw_identifier, question, _ in EXTENDED_PERSONAL_IDENTIFIER_CASES:
            with self.subTest(label=label):
                provider = OutputProvider("추가 검증이 필요합니다.")
                result = WorkforceAgentOrchestrator(provider=provider).run(
                    [privacy_observation()],
                    request_context={"question": question},
                )

                self.assertNotIn(
                    raw_identifier,
                    json.dumps(result, ensure_ascii=False),
                )
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(provider.context, ensure_ascii=False),
                )

    def test_extended_provider_identifiers_fail_closed_at_runtime_and_offline(
        self,
    ) -> None:
        base_result = WorkforceAgentOrchestrator().run([privacy_observation()])
        for label, raw_identifier, _, provider_output in (
            EXTENDED_PERSONAL_IDENTIFIER_CASES
        ):
            with self.subTest(label=label, path="runtime"):
                runtime = WorkforceAgentOrchestrator(
                    provider=OutputProvider(provider_output)
                ).run([privacy_observation()])

                self.assertEqual(runtime["provider"]["status"], "rejected")
                self.assertIsNone(runtime["provider"]["result"])
                self.assertIn(
                    "sensitive_literal",
                    runtime["provider_validation"]["violation_codes"],
                )
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(runtime, ensure_ascii=False),
                )

            with self.subTest(label=label, path="offline"):
                tampered = copy.deepcopy(base_result)
                tampered["provider"] = {
                    **tampered["provider"],
                    "status": "completed",
                    "result": provider_output,
                }
                tampered["provider_validation"] = {"status": "passed"}

                evaluation = evaluate_orchestration_result(tampered)

                self.assertEqual(evaluation["status"], "failed")
                self.assertIn("privacy_literal_exposed", evaluation["failures"])
                self.assertNotIn(
                    raw_identifier,
                    json.dumps(evaluation, ensure_ascii=False),
                )

    def test_provider_exceptions_and_error_mappings_never_echo_raw_values(self) -> None:
        for label, secret in SECRET_AND_PII_CASES:
            error = f"upstream failure for {label}: {secret}"
            for provider in (RaisingProvider(error), ErrorMappingProvider(error)):
                with self.subTest(label=label, provider=type(provider).__name__):
                    result = WorkforceAgentOrchestrator(provider=provider).run(
                        [privacy_observation()]
                    )
                    serialized = json.dumps(result, ensure_ascii=False)

                    self.assertEqual(result["provider"]["status"], "error")
                    self.assertFalse(secret in serialized, f"{label} leaked")
                    self.assertNotIn(secret, result["prompt_handoff"].get("error", ""))

    def test_provider_errors_do_not_echo_arbitrary_user_content(self) -> None:
        user_marker = "private-user-request-marker-redteam"
        for provider in (
            RaisingProvider(f"upstream failed for {user_marker}"),
            ErrorMappingProvider(f"provider rejected {user_marker}"),
        ):
            with self.subTest(provider=type(provider).__name__):
                result = WorkforceAgentOrchestrator(provider=provider).run(
                    [privacy_observation()],
                    request_context={"question": user_marker},
                )
                self.assertNotIn(user_marker, result["provider"].get("error", ""))
                self.assertNotIn(
                    user_marker,
                    result["prompt_handoff"].get("error", ""),
                )

    def test_attacker_controlled_exception_type_names_are_not_exposed(self) -> None:
        private_marker = "PrivateUserRequestMarkerError"
        private_exception = type(private_marker, (Exception,), {})

        class AnalyzeFailureProvider:
            configured = True
            provider_id = "redteam"
            provider_label = "Redteam Provider"

            def analyze(self, *, prompt, context):
                raise private_exception("private detail")

        class MetadataFailureProvider:
            configured = True

            @property
            def provider_id(self):
                raise private_exception("private detail")

        for provider in (AnalyzeFailureProvider(), MetadataFailureProvider()):
            with self.subTest(provider=type(provider).__name__):
                result = WorkforceAgentOrchestrator(provider=provider).run(
                    [privacy_observation()]
                )
                self.assertNotIn(
                    private_marker,
                    json.dumps(result, ensure_ascii=False),
                )

    def test_request_pii_and_secrets_are_absent_from_prompt_handoff_and_json(self) -> None:
        for label, secret in SECRET_AND_PII_CASES:
            with self.subTest(label=label):
                result = WorkforceAgentOrchestrator().run(
                    [privacy_observation()],
                    request_context={"question": personnel_question(label, secret)},
                )
                serialized = json.dumps(result, ensure_ascii=False)

                self.assertFalse(secret in serialized, f"{label} leaked")
                self.assertNotIn(secret, result.get("prompt", ""))
                self.assertNotIn(secret, result["prompt_handoff"].get("prompt") or "")

    def test_source_errors_are_redacted_before_json_prompt_or_fallback(self) -> None:
        for label, secret in SECRET_AND_PII_CASES:
            with self.subTest(label=label):
                item = privacy_observation(errors=[{
                    "source": "employee_status",
                    "message": f"source failure for {label}: {secret} 직원",
                }])
                result = WorkforceAgentOrchestrator().run([item])
                serialized = json.dumps(result, ensure_ascii=False)

                self.assertFalse(secret in serialized, f"{label} leaked")
                self.assertNotIn(secret, result.get("prompt") or "")

    def test_provider_metadata_is_bounded_and_redacted(self) -> None:
        for label, secret in SECRET_AND_PII_CASES:
            with self.subTest(label=label):
                result = WorkforceAgentOrchestrator(
                    provider=MetadataProvider(secret)
                ).run([privacy_observation()])
                serialized = json.dumps(result, ensure_ascii=False)

                self.assertFalse(secret in serialized, f"{label} leaked")

    def test_provider_generated_direct_identifiers_are_removed_with_output(self) -> None:
        outputs = (
            ("email", "담당자 이메일은 privacy.person@example.com 입니다."),
            ("phone", "담당자 전화번호는 010-2468-1357 입니다."),
            ("employee_id", "담당 직원의 사번은 EMP-SECRET-77 입니다."),
            ("resident_number", "담당 직원의 주민번호는 900101-1234567 입니다."),
            ("korean_name", "홍길동 직원의 연락처입니다."),
            ("english_name", "John Smith is the employee contact."),
        )
        for label, output in outputs:
            with self.subTest(label=label):
                result = WorkforceAgentOrchestrator(
                    provider=OutputProvider(output)
                ).run([privacy_observation()])

                self.assertEqual(result["provider"]["status"], "rejected")
                self.assertIsNone(result["provider"]["result"])
                self.assertIn(
                    "sensitive_literal",
                    result["provider_validation"]["violation_codes"],
                )
                self.assertNotIn(
                    output,
                    json.dumps(result["provider_validation"], ensure_ascii=False),
                )

    def test_server_log_and_request_id_do_not_reflect_headers_query_or_exception(self) -> None:
        combined = "|".join(secret for _, secret in SECRET_AND_PII_CASES)
        handler = object.__new__(DashboardHandler)
        handler.path = f"/api/health?token={combined}"
        handler.headers = {"X-Request-ID": combined}
        stream = io.StringIO()

        with redirect_stderr(stream):
            handler.log_internal_error(RuntimeError(combined))

        rendered = stream.getvalue()
        request_id = handler.request_correlation_id()
        self.assertRegex(request_id, r"^[0-9a-f]{16}$")
        for _, secret in SECRET_AND_PII_CASES:
            self.assertNotIn(secret, rendered)
            self.assertNotIn(secret, request_id)

    def test_server_json_serialization_fallback_discards_unsafe_payload(self) -> None:
        secret = "sk-json-redteam-fallback-secret-123456"
        handler = object.__new__(DashboardHandler)
        handler._request_id = "0123456789abcdef"
        handler.send_response = lambda status: None
        sent_headers: list[tuple[str, str]] = []
        handler.send_header = lambda key, value: sent_headers.append((key, value))
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()

        handler.send_json({"unsafe": object(), "secret": secret})

        body = handler.wfile.getvalue().decode("utf-8")
        self.assertNotIn(secret, body)
        self.assertIn("안전한 JSON", body)
        self.assertIn(("X-Request-ID", "0123456789abcdef"), sent_headers)

    def test_server_provider_error_response_does_not_echo_untrusted_detail(self) -> None:
        leak = "sk-provider-error-secret privacy.person@example.com 010-2468-1357"
        handler, responses = analysis_handler(path="/api/ai/connect")

        class FailingConnectionProvider:
            provider_id = "openai_responses"
            provider_label = "OpenAI Responses API"
            model = "test-model"

            def validate_connection(self):
                raise OpenAIResponsesError(leak)

        handler.request_openai_provider = lambda: FailingConnectionProvider()
        handler.do_POST()

        status, payload = responses[-1]
        self.assertEqual(status, HTTPStatus.BAD_GATEWAY)
        serialized = json.dumps(payload, ensure_ascii=False)
        for secret in leak.split():
            self.assertNotIn(secret, serialized)

    def test_server_dart_error_response_does_not_echo_untrusted_detail(self) -> None:
        leak = "operator-token-secret privacy.person@example.com 900101-1234567"
        handler, responses = analysis_handler(
            path="/api/analysis/context",
            body={
                "question": "근거 컨텍스트",
                "view": "strategy",
                "corp_codes": ["001"],
                "year": "2024",
                "report_code": "11011",
            },
        )

        with patch(
            "server.fetch_workforce_observations",
            side_effect=DARTError(leak),
        ):
            handler.do_POST()

        status, payload = responses[-1]
        self.assertEqual(status, HTTPStatus.BAD_GATEWAY)
        serialized = json.dumps(payload, ensure_ascii=False)
        for secret in leak.split():
            self.assertNotIn(secret, serialized)

    def test_safe_public_provider_error_remains_actionable(self) -> None:
        handler, responses = analysis_handler(path="/api/ai/connect")

        class SafeFailureProvider:
            def validate_connection(self):
                raise OpenAIResponsesError("OpenAI API에 연결하지 못했습니다.")

        handler.request_openai_provider = lambda: SafeFailureProvider()
        handler.do_POST()

        status, payload = responses[-1]
        self.assertEqual(status, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(payload["error"], "OpenAI API에 연결하지 못했습니다.")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{16}", payload["request_id"]))


if __name__ == "__main__":
    unittest.main()
