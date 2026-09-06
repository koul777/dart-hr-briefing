from __future__ import annotations

import json
import unittest
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

from openai_responses_adapter import (
    MAX_RESPONSE_BYTES,
    OpenAIResponsesError,
    OpenAIResponsesProvider,
    _extract_output_text,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")[:size]


class OpenAIResponsesProviderTests(unittest.TestCase):
    def test_environment_configuration_is_explicit(self):
        provider = OpenAIResponsesProvider.from_environment({
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
            "OPENAI_TIMEOUT_SECONDS": "45",
            "OPENAI_MAX_OUTPUT_TOKENS": "900",
        })
        self.assertTrue(provider.configured)
        self.assertEqual(provider.model, "test-model")
        self.assertEqual(provider.timeout_seconds, 45)
        self.assertEqual(provider.max_output_tokens, 900)

    def test_analyze_calls_responses_api_without_storing(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key", model="test-model")
        response_document = {
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "근거 기반 HR 브리핑"}],
            }],
        }

        with patch("openai_responses_adapter.urlopen", return_value=FakeResponse(response_document)) as mocked:
            result = provider.analyze(prompt="DART context", context={"records": []})

        self.assertEqual(result, "근거 기반 HR 브리핑")
        request = mocked.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(body["input"], "DART context")
        self.assertFalse(body["store"])
        self.assertNotIn("sk-test-key", request.data.decode("utf-8"))
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test-key")

    def test_validate_connection_uses_models_endpoint_without_generation(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key", model="test-model")

        with patch(
            "openai_responses_adapter.urlopen",
            return_value=FakeResponse({"object": "list", "data": [{"id": "test-model"}]}),
        ) as mocked:
            provider.validate_connection()

        request = mocked.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test-key")
        self.assertIsNone(request.data)

    def test_validate_connection_requires_access_to_configured_model(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key", model="configured-model")
        with patch(
            "openai_responses_adapter.urlopen",
            return_value=FakeResponse({"object": "list", "data": [{"id": "other-model"}]}),
        ):
            with self.assertRaisesRegex(OpenAIResponsesError, "configured-model"):
                provider.validate_connection()

    def test_provider_error_body_is_not_reflected(self):
        provider = OpenAIResponsesProvider(api_key="sk-secret")
        error = HTTPError(
            provider.endpoint,
            401,
            "upstream reason sk-secret",
            {},
            BytesIO(b'{"error":{"message":"echo sk-secret"}}'),
        )

        with patch("openai_responses_adapter.urlopen", side_effect=error):
            with self.assertRaises(OpenAIResponsesError) as raised:
                provider.analyze(prompt="test", context={})

        self.assertNotIn("sk-secret", str(raised.exception))
        self.assertIn("인증", str(raised.exception))
        self.assertTrue(error.fp.closed)

    def test_missing_model_error_is_specific_without_reflecting_provider_body(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key", model="missing-model")
        error = HTTPError(
            provider.endpoint,
            404,
            "secret upstream detail",
            {},
            BytesIO(b'{"error":{"message":"secret upstream detail"}}'),
        )

        with patch("openai_responses_adapter.urlopen", side_effect=error):
            with self.assertRaises(OpenAIResponsesError) as raised:
                provider.analyze(prompt="test", context={})

        self.assertIn("missing-model", str(raised.exception))
        self.assertIn("모델명", str(raised.exception))
        self.assertNotIn("secret upstream detail", str(raised.exception))
        self.assertTrue(error.fp.closed)

    def test_oversized_provider_response_is_rejected(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key")
        response = FakeResponse({"output_text": "x" * MAX_RESPONSE_BYTES})

        with patch("openai_responses_adapter.urlopen", return_value=response):
            with self.assertRaisesRegex(OpenAIResponsesError, "크기"):
                provider.analyze(prompt="test", context={})

    def test_nonfinite_provider_json_is_rejected(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key")
        response = FakeResponse({"output_text": float("nan")})

        with patch("openai_responses_adapter.urlopen", return_value=response):
            with self.assertRaisesRegex(OpenAIResponsesError, "해석"):
                provider.analyze(prompt="test", context={})

    def test_excessively_nested_provider_json_is_a_safe_adapter_error(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key")

        with (
            patch("openai_responses_adapter.urlopen", return_value=FakeResponse({})),
            patch(
                "openai_responses_adapter._read_json_response",
                side_effect=RecursionError,
            ),
        ):
            with self.assertRaisesRegex(OpenAIResponsesError, "해석"):
                provider.analyze(prompt="test", context={})

    def test_success_status_error_and_invalid_shape_do_not_reflect_provider_details(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key")
        cases = (
            ({"error": {"message": "secret upstream detail"}}, "처리하지 못했습니다"),
            ([], "형식"),
            ({"status": "secret upstream status", "output": []}, "텍스트"),
        )
        for document, expected in cases:
            with self.subTest(document_type=type(document).__name__):
                with patch(
                    "openai_responses_adapter.urlopen",
                    return_value=FakeResponse(document),
                ):
                    with self.assertRaises(OpenAIResponsesError) as raised:
                        provider.analyze(prompt="test", context={})
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn("secret upstream detail", str(raised.exception))
                self.assertNotIn("secret upstream status", str(raised.exception))

    def test_invalid_authorization_value_is_rejected_before_network(self):
        for api_key in (
            "sk-secret\r\nInjected: yes",
            "sk-secret\x00Injected",
            "sk-비ASCII키",
        ):
            with self.subTest(api_key=repr(api_key)):
                provider = OpenAIResponsesProvider(api_key=api_key)
                with patch("openai_responses_adapter.urlopen") as mocked:
                    with self.assertRaisesRegex(OpenAIResponsesError, "형식"):
                        provider.analyze(prompt="test", context={})
                mocked.assert_not_called()

    def test_invalid_model_value_is_rejected_before_network(self):
        provider = OpenAIResponsesProvider(
            api_key="sk-test-key",
            model="unsafe/model\r\nInjected: yes",
        )
        with patch("openai_responses_adapter.urlopen") as mocked:
            with self.assertRaisesRegex(OpenAIResponsesError, "OPENAI_MODEL 형식"):
                provider.analyze(prompt="test", context={})
        mocked.assert_not_called()

    def test_output_extraction_prefers_direct_text_and_joins_blocks(self):
        direct = {"output_text": "  직접 응답  ", "output": []}
        nested = {
            "output": [
                {"content": [{"type": "output_text", "text": "첫 줄"}, {"type": "ignored"}]},
                {"content": [{"type": "output_text", "text": "둘째 줄"}]},
            ]
        }
        self.assertEqual(_extract_output_text(direct), "직접 응답")
        self.assertEqual(_extract_output_text(nested), "첫 줄\n\n둘째 줄")

    def test_environment_clamps_numeric_configuration(self):
        provider = OpenAIResponsesProvider.from_environment({
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_TIMEOUT_SECONDS": "999",
            "OPENAI_MAX_OUTPUT_TOKENS": "0",
        })
        self.assertEqual(provider.timeout_seconds, 180)
        self.assertEqual(provider.max_output_tokens, 1)

    def test_validate_connection_rejects_unconfigured_and_invalid_shape(self):
        with self.assertRaisesRegex(OpenAIResponsesError, "입력되지 않았습니다"):
            OpenAIResponsesProvider().validate_connection()

        provider = OpenAIResponsesProvider(api_key="sk-test-key")
        with patch(
            "openai_responses_adapter.urlopen",
            return_value=FakeResponse({"object": "list", "data": {}}),
        ):
            with self.assertRaisesRegex(OpenAIResponsesError, "형식"):
                provider.validate_connection()


if __name__ == "__main__":
    unittest.main()
