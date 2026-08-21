"""A conservative boundary for handing work to Claude Code MCP.

Claude Code MCP tools belong to the host session.  They are not implicitly a
public HTTP API for a Python process running beside that session.  Therefore
the default adapter in this module is unavailable and returns a structured
result; it never pretends that an in-process MCP tool was called.

An independently provisioned gateway may be connected later by setting
``CLAUDE_MCP_GATEWAY_URL``.  The gateway contract is documented by
``MCP_GATEWAY_CALL_CONTRACT`` and implemented by
``HttpMCPGatewayAdapter``.  ``CLAUDE_MCP_GATEWAY_TOKEN`` is read only for the
outgoing Authorization header and is deliberately excluded from all public
payloads, results, and diagnostic representations.
"""

from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


# Public configuration names.  The URL is for a separately deployed gateway,
# not for the Claude Code host session itself.
MCP_GATEWAY_URL_ENV = "CLAUDE_MCP_GATEWAY_URL"
MCP_GATEWAY_TOKEN_ENV = "CLAUDE_MCP_GATEWAY_TOKEN"
MCP_GATEWAY_TIMEOUT_ENV = "CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS"

MCP_GATEWAY_CALL_PATH = "/v1/mcp/call"
MCP_GATEWAY_CONTRACT_VERSION = "1"
DEFAULT_GATEWAY_TIMEOUT_SECONDS = 20.0

MCP_GATEWAY_CALL_CONTRACT: Mapping[str, Any] = {
    "transport": "HTTP gateway explicitly provisioned outside the Claude Code session",
    "method": "POST",
    "path": MCP_GATEWAY_CALL_PATH,
    "request_content_type": "application/json",
    "authorization": "optional Bearer token from CLAUDE_MCP_GATEWAY_TOKEN",
    "request_body": {
        "contract_version": "string, currently '1'",
        "request_id": "string, caller-generated correlation id",
        "server": "string, gateway-routable MCP server identifier",
        "tool": "string, MCP tool name",
        "arguments": "JSON object",
    },
    "success_response": {
        "ok": True,
        "request_id": "string, optional echo",
        "result": "any JSON value",
    },
    "error_response": {
        "ok": False,
        "request_id": "string, optional echo",
        "error": {"code": "string", "message": "string"},
    },
}


class MCPUnavailable(RuntimeError):
    """Raised when a caller explicitly asks an unavailable MCP boundary to fail."""

    code = "mcp_unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        # Keep the exception text free of configuration values and response
        # bodies, either of which could contain credentials or other secrets.
        super().__init__(reason)


class MCPCallError(RuntimeError):
    """Raised by ``MCPCallResult.raise_for_status`` for a non-availability error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass(frozen=True, slots=True)
class MCPCallRequest:
    """A transport-neutral MCP tool call request."""

    server: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: _new_id("mcp"))

    def __post_init__(self) -> None:
        if not self.server.strip():
            raise ValueError("server must not be empty")
        if not self.tool.strip():
            raise ValueError("tool must not be empty")
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")

    def to_wire_dict(self) -> dict[str, Any]:
        """Return the gateway request body, without authentication material."""

        return {
            "contract_version": MCP_GATEWAY_CONTRACT_VERSION,
            "request_id": self.request_id,
            "server": self.server,
            "tool": self.tool,
            "arguments": dict(self.arguments),
        }


@dataclass(frozen=True, slots=True)
class PromptHandoffPayload:
    """A payload an outer orchestrator can pass to Claude Code for MCP work.

    This is intentionally a handoff description, not an attempted transport
    into the current Claude Code session.
    """

    prompt: str
    context: Mapping[str, Any] = field(default_factory=dict)
    requested_server: str | None = None
    requested_tool: str | None = None
    expected_output: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    handoff_id: str = field(default_factory=lambda: _new_id("handoff"))

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.requested_server is not None and not self.requested_server.strip():
            raise ValueError("requested_server must not be blank when provided")
        if self.requested_tool is not None and not self.requested_tool.strip():
            raise ValueError("requested_tool must not be blank when provided")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the handoff for a host/orchestrator boundary."""

        requested_capability: dict[str, str] = {}
        if self.requested_server is not None:
            requested_capability["server"] = self.requested_server
        if self.requested_tool is not None:
            requested_capability["tool"] = self.requested_tool

        payload: dict[str, Any] = {
            "kind": "claude_code_mcp_prompt_handoff",
            "contract_version": MCP_GATEWAY_CONTRACT_VERSION,
            "handoff_id": self.handoff_id,
            "transport": "host_session_prompt_handoff",
            "direct_local_mcp_call": False,
            "prompt": self.prompt,
            "context": dict(self.context),
            "metadata": dict(self.metadata),
        }
        if requested_capability:
            payload["requested_capability"] = requested_capability
        if self.expected_output is not None:
            payload["expected_output"] = self.expected_output
        return payload


def build_prompt_handoff(
    prompt: str,
    *,
    context: Mapping[str, Any] | None = None,
    requested_server: str | None = None,
    requested_tool: str | None = None,
    expected_output: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> PromptHandoffPayload:
    """Build a prompt handoff without attempting to contact MCP."""

    return PromptHandoffPayload(
        prompt=prompt,
        context={} if context is None else context,
        requested_server=requested_server,
        requested_tool=requested_tool,
        expected_output=expected_output,
        metadata={} if metadata is None else metadata,
    )


@dataclass(frozen=True, slots=True)
class MCPCallResult:
    """Structured outcome of an adapter call."""

    ok: bool
    status: str
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None
    request_id: str | None = None
    http_status: int | None = None

    @classmethod
    def success(
        cls,
        result: Any,
        *,
        request_id: str | None = None,
        http_status: int | None = None,
    ) -> MCPCallResult:
        return cls(
            ok=True,
            status="ok",
            result=result,
            request_id=request_id,
            http_status=http_status,
        )

    @classmethod
    def failure(
        cls,
        error_code: str,
        error_message: str,
        *,
        request_id: str | None = None,
        http_status: int | None = None,
        status: str = "error",
    ) -> MCPCallResult:
        return cls(
            ok=False,
            status=status,
            error_code=error_code,
            error_message=error_message,
            request_id=request_id,
            http_status=http_status,
        )

    @classmethod
    def unavailable(
        cls,
        reason: str,
        *,
        request_id: str | None = None,
    ) -> MCPCallResult:
        return cls.failure(
            MCPUnavailable.code,
            reason,
            request_id=request_id,
            status="unavailable",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result without adapter configuration or credentials."""

        payload: dict[str, Any] = {"ok": self.ok, "status": self.status}
        if self.ok:
            payload["result"] = self.result
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        if self.error_message is not None:
            payload["error_message"] = self.error_message
        if self.request_id is not None:
            payload["request_id"] = self.request_id
        if self.http_status is not None:
            payload["http_status"] = self.http_status
        return payload

    def raise_for_status(self) -> MCPCallResult:
        if self.ok:
            return self
        if self.status == "unavailable":
            raise MCPUnavailable(self.error_message or "MCP is unavailable")
        raise MCPCallError(
            self.error_code or "mcp_call_error",
            self.error_message or "MCP call failed",
        )


class ClaudeCodeMCPAdapter(Protocol):
    """Interface consumed by the local Python application."""

    def call_tool(self, request: MCPCallRequest) -> MCPCallResult:
        """Call a tool through an explicitly available boundary."""

    def create_prompt_handoff(self, payload: PromptHandoffPayload) -> PromptHandoffPayload:
        """Prepare a host-session handoff; this method does not send it."""


@dataclass(frozen=True, slots=True)
class UnavailableClaudeCodeMCPAdapter:
    """Default adapter when no separately provisioned MCP gateway exists."""

    reason: str = (
        "Claude Code MCP is available only in the host session; "
        "no local MCP gateway is configured."
    )

    def call_tool(self, request: MCPCallRequest) -> MCPCallResult:
        return MCPCallResult.unavailable(self.reason, request_id=request.request_id)

    def create_prompt_handoff(self, payload: PromptHandoffPayload) -> PromptHandoffPayload:
        return payload


@dataclass(frozen=True, slots=True)
class MCPGatewayConfig:
    """Non-secret gateway configuration loaded from explicit environment values."""

    base_url: str
    timeout_seconds: float = DEFAULT_GATEWAY_TIMEOUT_SECONDS
    token: str | None = field(default=None, repr=False)
    call_path: str = MCP_GATEWAY_CALL_PATH

    def __post_init__(self) -> None:
        _validate_gateway_url(self.base_url)
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        if not self.call_path.startswith("/"):
            raise ValueError("call_path must start with '/'")

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> MCPGatewayConfig:
        values = os.environ if environ is None else environ
        raw_url = values.get(MCP_GATEWAY_URL_ENV, "").strip()
        if not raw_url:
            raise MCPUnavailable(
                "No MCP gateway is configured; Claude Code's in-session MCP is not a local HTTP API."
            )

        raw_timeout = values.get(MCP_GATEWAY_TIMEOUT_ENV, "")
        timeout = DEFAULT_GATEWAY_TIMEOUT_SECONDS
        if raw_timeout.strip():
            try:
                timeout = float(raw_timeout)
            except ValueError as exc:
                raise MCPUnavailable("MCP gateway timeout configuration is invalid.") from exc
            if not math.isfinite(timeout) or timeout <= 0:
                raise MCPUnavailable("MCP gateway timeout configuration is invalid.")

        token = values.get(MCP_GATEWAY_TOKEN_ENV, "").strip() or None
        try:
            return cls(base_url=raw_url.rstrip("/"), timeout_seconds=timeout, token=token)
        except ValueError as exc:
            raise MCPUnavailable("MCP gateway URL configuration is invalid.") from exc

    @property
    def call_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.call_path}"

    @property
    def has_token(self) -> bool:
        return bool(self.token)


def _validate_gateway_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain userinfo")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain a query or fragment")


@dataclass(frozen=True, slots=True)
class HttpMCPGatewayAdapter:
    """Real HTTP adapter for a separately provisioned gateway.

    This class is never selected unless ``CLAUDE_MCP_GATEWAY_URL`` is set.
    It does not attempt to discover, introspect, or call the current Claude
    Code session's internal MCP transport.
    """

    config: MCPGatewayConfig

    def call_tool(self, request: MCPCallRequest) -> MCPCallResult:
        try:
            body = json.dumps(
                request.to_wire_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            return MCPCallResult.failure(
                "invalid_request",
                "MCP arguments are not JSON serializable.",
                request_id=request.request_id,
            )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "dart-claude-mcp-adapter/1",
        }
        if self.config.token:
            # The token is used only on the wire and is never included in a
            # result, exception, payload, or diagnostic string.
            headers["Authorization"] = f"Bearer {self.config.token}"

        http_request = Request(
            self.config.call_url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                raw_response = response.read()
                http_status = getattr(response, "status", None)
        except HTTPError as exc:
            status = int(exc.code)
            if status >= 500:
                return MCPCallResult.unavailable(
                    "MCP gateway is unavailable.",
                    request_id=request.request_id,
                )
            return MCPCallResult.failure(
                "gateway_http_error",
                "MCP gateway rejected the request.",
                request_id=request.request_id,
                http_status=status,
            )
        except (OSError, TimeoutError, URLError):
            return MCPCallResult.unavailable(
                "MCP gateway could not be reached.",
                request_id=request.request_id,
            )

        if http_status is not None and not 200 <= http_status < 300:
            return MCPCallResult.failure(
                "gateway_http_error",
                "MCP gateway returned a non-success HTTP status.",
                request_id=request.request_id,
                http_status=http_status,
            )

        try:
            document = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return MCPCallResult.failure(
                "invalid_gateway_response",
                "MCP gateway returned a non-JSON response.",
                request_id=request.request_id,
                http_status=http_status,
            )

        if not isinstance(document, dict) or not isinstance(document.get("ok"), bool):
            return MCPCallResult.failure(
                "invalid_gateway_response",
                "MCP gateway response does not match the documented contract.",
                request_id=request.request_id,
                http_status=http_status,
            )

        response_request_id = document.get("request_id")
        request_id = response_request_id if isinstance(response_request_id, str) else request.request_id
        if document["ok"]:
            return MCPCallResult.success(
                document.get("result"),
                request_id=request_id,
                http_status=http_status,
            )

        error = document.get("error")
        error_code = "gateway_error"
        if isinstance(error, dict) and isinstance(error.get("code"), str) and error["code"].strip():
            error_code = error["code"]
        return MCPCallResult.failure(
            error_code,
            "MCP gateway reported an error.",
            request_id=request_id,
            http_status=http_status,
        )

    def create_prompt_handoff(self, payload: PromptHandoffPayload) -> PromptHandoffPayload:
        # Prompt handoff remains a host/orchestrator concern.  There is no
        # implied gateway endpoint for sending prompts in this contract.
        return payload


def create_claude_code_mcp_adapter(
    environ: Mapping[str, str] | None = None,
) -> ClaudeCodeMCPAdapter:
    """Create the safe default adapter or an explicitly configured gateway adapter."""

    values = os.environ if environ is None else environ
    if not values.get(MCP_GATEWAY_URL_ENV, "").strip():
        return UnavailableClaudeCodeMCPAdapter()
    try:
        config = MCPGatewayConfig.from_environment(values)
    except MCPUnavailable as exc:
        return UnavailableClaudeCodeMCPAdapter(reason=exc.reason)
    return HttpMCPGatewayAdapter(config=config)


def call_tool_or_raise(
    adapter: ClaudeCodeMCPAdapter,
    request: MCPCallRequest,
) -> MCPCallResult:
    """Convenience wrapper for callers that prefer exceptions to result checks."""

    result = adapter.call_tool(request)
    return result.raise_for_status()


__all__ = [
    "ClaudeCodeMCPAdapter",
    "HttpMCPGatewayAdapter",
    "MCPCallError",
    "MCPCallRequest",
    "MCPCallResult",
    "MCPGatewayConfig",
    "MCP_GATEWAY_CALL_CONTRACT",
    "MCP_GATEWAY_CALL_PATH",
    "MCP_GATEWAY_CONTRACT_VERSION",
    "MCP_GATEWAY_TIMEOUT_ENV",
    "MCP_GATEWAY_TOKEN_ENV",
    "MCP_GATEWAY_URL_ENV",
    "MCPUnavailable",
    "PromptHandoffPayload",
    "UnavailableClaudeCodeMCPAdapter",
    "build_prompt_handoff",
    "call_tool_or_raise",
    "create_claude_code_mcp_adapter",
]
