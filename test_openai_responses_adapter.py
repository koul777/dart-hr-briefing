from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from openai_responses_adapter import OpenAIResponsesProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


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
        provider = OpenAIResponsesProvider(api_key="test-key", model="test-model")
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
        self.assertNotIn("test-key", request.data.decode("utf-8"))
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_validate_connection_uses_models_endpoint_without_generation(self):
        provider = OpenAIResponsesProvider(api_key="sk-test-key", model="test-model")

        with patch(
            "openai_responses_adapter.urlopen",
            return_value=FakeResponse({"object": "list", "data": []}),
        ) as mocked:
            provider.validate_connection()

        request = mocked.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test-key")
        self.assertIsNone(request.data)


if __name__ == "__main__":
    unittest.main()
