from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from claude_mcp_adapter import (
    MCPCallRequest,
    MCPCallError,
    MCPCallResult,
    MCPGatewayConfig,
    MCPUnavailable,
    HttpMCPGatewayAdapter,
    MAX_GATEWAY_REQUEST_BYTES,
    MAX_GATEWAY_RESPONSE_BYTES,
    MAX_GATEWAY_TIMEOUT_SECONDS,
    PromptHandoffPayload,
    UnavailableClaudeCodeMCPAdapter,
    build_prompt_handoff,
    create_claude_code_mcp_adapter,
)


class FakeGatewayResponse:
    status = 200

    def __init__(self, body) -> None:
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self.body[:size]


class ClaudeMCPAdapterTests(unittest.TestCase):
    def test_unconfigured_environment_is_explicitly_unavailable(self) -> None:
        adapter = create_claude_code_mcp_adapter({})
        self.assertIsInstance(adapter, UnavailableClaudeCodeMCPAdapter)
        result = adapter.call_tool(MCPCallRequest(server="claude-code", tool="analyze"))
        self.assertEqual(result.status, "unavailable")
        self.assertNotIn("CLAUDE_MCP_GATEWAY", str(result.to_dict()))

    def test_wire_request_excludes_authentication_material(self) -> None:
        request = MCPCallRequest(
            server="claude-code",
            tool="analyze_workforce_strategy",
            arguments={"prompt": "질문", "context": {"source": "OpenDART"}},
        )
        wire = request.to_wire_dict()
        self.assertEqual(wire["contract_version"], "1")
        self.assertNotIn("token", wire)
        self.assertNotIn("Authorization", wire)

    def test_gateway_url_rejects_userinfo(self) -> None:
        with self.assertRaises(ValueError):
            MCPGatewayConfig(base_url="https://user:secret@example.com")

    def test_remote_gateway_requires_https_but_loopback_http_is_allowed(self) -> None:
        with self.assertRaises(ValueError):
            MCPGatewayConfig(base_url="http://example.com")
        config = MCPGatewayConfig(base_url="http://127.0.0.1:9000")
        self.assertEqual(config.call_url, "http://127.0.0.1:9000/v1/mcp/call")

    def test_gateway_config_rejects_header_and_path_injection(self) -> None:
        for token in ("secret\r\nInjected: yes", "secret\x00Injected"):
            with self.subTest(token=repr(token)), self.assertRaises(ValueError):
                MCPGatewayConfig(
                    base_url="https://example.com",
                    token=token,
                )
        with self.assertRaises(ValueError):
            MCPGatewayConfig(
                base_url="https://example.com",
                call_path="/v1/mcp/call?redirect=unsafe",
            )

    def test_gateway_config_rejects_invalid_port_path_and_excessive_timeout(self) -> None:
        for kwargs in (
            {"base_url": "https://example.com:not-a-port"},
            {"base_url": "https://example.com", "call_path": "/v1\\unsafe"},
            {"base_url": "https://example.com", "call_path": "/v1/mcp\r\nunsafe"},
            {
                "base_url": "https://example.com",
                "timeout_seconds": MAX_GATEWAY_TIMEOUT_SECONDS + 1,
            },
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MCPGatewayConfig(**kwargs)

    def test_mcp_identifiers_must_be_strings(self) -> None:
        for kwargs in (
            {"server": 7, "tool": "safe"},
            {"server": "safe", "tool": 7},
            {"server": "safe", "tool": "tool", "request_id": 7},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MCPCallRequest(**kwargs)

    def test_gateway_response_is_bounded_and_request_id_must_match(self) -> None:
        adapter = HttpMCPGatewayAdapter(MCPGatewayConfig(base_url="https://example.com"))
        request = MCPCallRequest(server="safe", tool="analyze", request_id="mcp_expected")

        oversized = FakeGatewayResponse(b"x" * (MAX_GATEWAY_RESPONSE_BYTES + 1))
        with patch("claude_mcp_adapter.urlopen", return_value=oversized):
            result = adapter.call_tool(request)
        self.assertEqual(result.error_code, "gateway_response_too_large")

        mismatch = FakeGatewayResponse(
            b'{"ok":true,"request_id":"mcp_other","result":{}}'
        )
        with patch("claude_mcp_adapter.urlopen", return_value=mismatch):
            result = adapter.call_tool(request)
        self.assertEqual(result.error_code, "gateway_request_id_mismatch")

    def test_gateway_success_uses_token_only_on_wire(self) -> None:
        adapter = HttpMCPGatewayAdapter(MCPGatewayConfig(
            base_url="https://example.com",
            token="gateway-secret",
        ))
        request = MCPCallRequest(server="safe", tool="analyze", request_id="mcp_expected")
        response = FakeGatewayResponse({
            "ok": True,
            "request_id": request.request_id,
            "result": {"answer": "근거 기반 결과"},
        })

        with patch("claude_mcp_adapter.urlopen", return_value=response) as mocked:
            result = adapter.call_tool(request)

        self.assertTrue(result.ok)
        self.assertEqual(result.result, {"answer": "근거 기반 결과"})
        wire_request = mocked.call_args.args[0]
        self.assertEqual(wire_request.get_header("Authorization"), "Bearer gateway-secret")
        self.assertNotIn("gateway-secret", str(result.to_dict()))

    def test_gateway_error_paths_are_generic_and_bounded(self) -> None:
        adapter = HttpMCPGatewayAdapter(MCPGatewayConfig(base_url="https://example.com"))
        request = MCPCallRequest(server="safe", tool="analyze", request_id="mcp_expected")

        cases = (
            (
                FakeGatewayResponse(b"not-json"),
                "invalid_gateway_response",
            ),
            (
                FakeGatewayResponse({"result": {}}),
                "invalid_gateway_response",
            ),
            (
                FakeGatewayResponse({
                    "ok": False,
                    "request_id": request.request_id,
                    "error": {"code": "rate_limited", "message": "secret detail"},
                }),
                "rate_limited",
            ),
            (
                FakeGatewayResponse({
                    "ok": False,
                    "request_id": request.request_id,
                    "error": {"code": "BAD SECRET CODE", "message": "secret detail"},
                }),
                "gateway_error",
            ),
        )
        for response, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with patch("claude_mcp_adapter.urlopen", return_value=response):
                    result = adapter.call_tool(request)
                self.assertEqual(result.error_code, expected_code)
                self.assertNotIn("secret detail", str(result.to_dict()))

        for status, expected_status in ((400, "error"), (503, "unavailable")):
            with self.subTest(http_status=status):
                error = HTTPError("https://example.com", status, "secret", {}, None)
                with patch("claude_mcp_adapter.urlopen", side_effect=error):
                    result = adapter.call_tool(request)
                self.assertEqual(result.status, expected_status)
                self.assertNotIn("secret", result.error_message or "")
                self.assertTrue(error.closed)

        with patch(
            "claude_mcp_adapter.urlopen",
            side_effect=URLError("gateway-secret connection detail"),
        ):
            result = adapter.call_tool(request)
        self.assertEqual(result.status, "unavailable")
        self.assertNotIn("gateway-secret", result.error_message or "")

    def test_gateway_rejects_unserializable_and_oversized_requests_before_network(self) -> None:
        adapter = HttpMCPGatewayAdapter(MCPGatewayConfig(base_url="https://example.com"))
        cases = (
            (
                MCPCallRequest(server="safe", tool="analyze", arguments={"bad": object()}),
                "invalid_request",
            ),
            (
                MCPCallRequest(server="safe", tool="analyze", arguments={"bad": float("nan")}),
                "invalid_request",
            ),
            (
                MCPCallRequest(server="safe", tool="analyze", arguments={"bad": "\ud800"}),
                "invalid_request",
            ),
            (
                MCPCallRequest(
                    server="safe",
                    tool="analyze",
                    arguments={"text": "x" * (MAX_GATEWAY_REQUEST_BYTES + 1)},
                ),
                "request_too_large",
            ),
        )
        for request, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with patch("claude_mcp_adapter.urlopen") as mocked:
                    result = adapter.call_tool(request)
                self.assertEqual(result.error_code, expected_code)
                mocked.assert_not_called()

        request = MCPCallRequest(server="safe", tool="analyze", arguments={})
        with (
            patch("claude_mcp_adapter.json.dumps", side_effect=RecursionError),
            patch("claude_mcp_adapter.urlopen") as mocked,
        ):
            result = adapter.call_tool(request)
        self.assertEqual(result.error_code, "invalid_request")
        mocked.assert_not_called()

    def test_gateway_rejects_nonfinite_json_response(self) -> None:
        adapter = HttpMCPGatewayAdapter(MCPGatewayConfig(base_url="https://example.com"))
        request = MCPCallRequest(server="safe", tool="analyze", request_id="mcp_expected")
        response = FakeGatewayResponse({
            "ok": True,
            "request_id": request.request_id,
            "result": {"value": float("nan")},
        })

        with patch("claude_mcp_adapter.urlopen", return_value=response):
            result = adapter.call_tool(request)

        self.assertEqual(result.error_code, "invalid_gateway_response")

        surrogate_response = FakeGatewayResponse(
            b'{"ok":true,"request_id":"mcp_expected","result":"\\ud800"}'
        )
        with patch("claude_mcp_adapter.urlopen", return_value=surrogate_response):
            result = adapter.call_tool(request)
        self.assertEqual(result.error_code, "invalid_gateway_response")

    def test_prompt_handoff_and_raise_for_status_paths(self) -> None:
        payload = build_prompt_handoff(
            "근거를 확인해줘",
            context={"source": "OpenDART"},
            requested_server="claude-code",
            requested_tool="analyze",
            expected_output="요약",
            metadata={"scope": "audit"},
        )
        self.assertIsInstance(payload, PromptHandoffPayload)
        rendered = payload.to_dict()
        self.assertEqual(rendered["kind"], "claude_code_mcp_prompt_handoff")
        self.assertFalse(rendered["direct_local_mcp_call"])
        self.assertEqual(rendered["requested_capability"]["server"], "claude-code")
        self.assertEqual(rendered["requested_capability"]["tool"], "analyze")
        self.assertEqual(rendered["expected_output"], "요약")

        success = MCPCallResult.success({"ok": True}, request_id="mcp_test")
        self.assertIs(success.raise_for_status(), success)

        unavailable = MCPCallResult.unavailable("gateway offline", request_id="mcp_test")
        with self.assertRaises(MCPUnavailable):
            unavailable.raise_for_status()

        failure = MCPCallResult.failure("bad_contract", "contract failed", request_id="mcp_test")
        with self.assertRaises(MCPCallError) as raised:
            failure.raise_for_status()
        self.assertEqual(raised.exception.code, "bad_contract")

    def test_gateway_config_from_environment_and_optional_request_id_echo(self) -> None:
        config = MCPGatewayConfig.from_environment({
            "CLAUDE_MCP_GATEWAY_URL": "https://example.com/",
            "CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS": "45",
            "CLAUDE_MCP_GATEWAY_TOKEN": "",
        })
        self.assertEqual(config.call_url, "https://example.com/v1/mcp/call")
        self.assertEqual(config.timeout_seconds, 45)
        self.assertFalse(config.has_token)

        adapter = HttpMCPGatewayAdapter(config)
        request = MCPCallRequest(server="safe", tool="analyze", request_id="mcp_expected")
        response = FakeGatewayResponse({"ok": True, "result": {"answer": "ok"}})
        response.status = 204
        with patch("claude_mcp_adapter.urlopen", return_value=response):
            result = adapter.call_tool(request)
        self.assertTrue(result.ok)
        self.assertEqual(result.request_id, request.request_id)
        self.assertEqual(result.http_status, 204)

    def test_invalid_gateway_environment_falls_back_to_unavailable_adapter(self) -> None:
        adapter = create_claude_code_mcp_adapter({
            "CLAUDE_MCP_GATEWAY_URL": "http://example.com",
            "CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS": "not-a-number",
        })
        self.assertIsInstance(adapter, UnavailableClaudeCodeMCPAdapter)
        result = adapter.call_tool(MCPCallRequest(server="safe", tool="analyze"))
        self.assertEqual(result.status, "unavailable")
        self.assertNotIn("http://example.com", result.error_message or "")


if __name__ == "__main__":
    unittest.main()
