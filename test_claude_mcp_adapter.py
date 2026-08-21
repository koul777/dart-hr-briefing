from __future__ import annotations

import unittest

from claude_mcp_adapter import (
    MCPCallRequest,
    MCPGatewayConfig,
    UnavailableClaudeCodeMCPAdapter,
    create_claude_code_mcp_adapter,
)


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


if __name__ == "__main__":
    unittest.main()
