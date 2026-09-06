#!/usr/bin/env python3
"""Verify a deployed release against an expected immutable Git commit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

APP_ID = "kr.opendart.dart-hr-briefing"
APP_VERSION = "0.2.0"
MAX_RESPONSE_BYTES = 512 * 1024
PROTECTED_RUNTIME_PATHS = (
    "/.env",
    "/.git/config",
    "/server.py",
    "/agent_orchestration.py",
    "/analysis_contract.py",
    "/claude_mcp_adapter.py",
    "/classroom_mode.py",
    "/openai_responses_adapter.py",
    "/orchestration_evaluation.py",
    "/orchestrator.py",
    "/pyproject.toml",
    "/runtime_controls.py",
    "/uv.lock",
    "/vercel.json",
    "/workforce_analytics.py",
    "/.python-version",
    "/api/index.py",
    "/HR_BRIEFING_RULES.md",
    "/schemas/workforce_orchestration_v2.schema.json",
    "/seed/classroom_workforce_2024_11011.json",
    "/seed/corp_codes.json.gz",
)


class PostDeploySmokeError(RuntimeError):
    """A public release response violates a stable smoke-test contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HTTPResult:
    status: int
    headers: Mapping[str, str]
    body: bytes


Fetcher = Callable[[str, float], HTTPResult]


def _fetch(url: str, timeout_seconds: float) -> HTTPResult:
    request = Request(url, headers={"User-Agent": "dart-release-smoke/1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            return HTTPResult(int(response.status), dict(response.headers.items()), body)
    except HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES + 1)
        return HTTPResult(int(exc.code), dict(exc.headers.items()), body)


def _headers(result: HTTPResult) -> dict[str, str]:
    return {str(name).casefold(): str(value) for name, value in result.headers.items()}


def _require_headers(result: HTTPResult, *, cache_control: str) -> None:
    headers = _headers(result)
    exact = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
    }
    for name, expected in exact.items():
        if headers.get(name) != expected:
            raise PostDeploySmokeError(f"header_{name}_invalid")
    if not headers.get("strict-transport-security", "").startswith("max-age=31536000"):
        raise PostDeploySmokeError("header_hsts_invalid")
    permissions = headers.get("permissions-policy", "")
    if not all(
        marker in permissions for marker in ("camera=()", "microphone=()", "geolocation=()")
    ):
        raise PostDeploySmokeError("header_permissions_policy_invalid")
    if cache_control not in headers.get("cache-control", ""):
        raise PostDeploySmokeError("header_cache_control_invalid")


def _json(result: HTTPResult, *, limit: int, status_code: str) -> Mapping[str, object]:
    if result.status != 200:
        raise PostDeploySmokeError(status_code)
    if len(result.body) > limit:
        raise PostDeploySmokeError(f"{status_code}_body_too_large")
    try:
        payload = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PostDeploySmokeError(f"{status_code}_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise PostDeploySmokeError(f"{status_code}_invalid_json")
    return payload


def _validated_base_url(base_url: str) -> str:
    rendered = str(base_url).strip().rstrip("/")
    parsed = urlsplit(rendered)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise PostDeploySmokeError("invalid_base_url")
    return rendered


def validate_deployment(
    base_url: str,
    expected_sha: str,
    *,
    fetcher: Fetcher = _fetch,
    timeout_seconds: float = 15.0,
) -> dict[str, object]:
    normalized_sha = str(expected_sha).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{7,64}", normalized_sha):
        raise PostDeploySmokeError("invalid_expected_sha")
    if timeout_seconds <= 0:
        raise PostDeploySmokeError("invalid_timeout")
    base = _validated_base_url(base_url)
    expected_build_id = f"git-{normalized_sha[:12]}"

    for protected_path in PROTECTED_RUNTIME_PATHS:
        protected_result = fetcher(f"{base}{protected_path}", timeout_seconds)
        if protected_result.status != 404:
            raise PostDeploySmokeError("runtime_source_public")
        if len(protected_result.body) > 16 * 1024:
            raise PostDeploySmokeError("runtime_source_error_body_too_large")

    root = fetcher(f"{base}/", timeout_seconds)
    if root.status != 200:
        raise PostDeploySmokeError("root_status")
    if len(root.body) > 128 * 1024:
        raise PostDeploySmokeError("root_body_too_large")
    try:
        root_text = root.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PostDeploySmokeError("root_invalid_utf8") from exc
    if "loadClassroomButton" not in root_text:
        raise PostDeploySmokeError("root_classroom_marker_missing")
    _require_headers(root, cache_control="no-cache")

    static_result = fetcher(f"{base}/static/app.js", timeout_seconds)
    if static_result.status != 200:
        raise PostDeploySmokeError("static_app_status")
    if not static_result.body or len(static_result.body) > MAX_RESPONSE_BYTES:
        raise PostDeploySmokeError("static_app_body_invalid")
    try:
        static_text = static_result.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PostDeploySmokeError("static_app_invalid_utf8") from exc
    if "API_REQUEST_TIMEOUT_MS" not in static_text:
        raise PostDeploySmokeError("static_app_marker_missing")
    _require_headers(static_result, cache_control="no-cache")

    health_result = fetcher(f"{base}/api/health", timeout_seconds)
    health = _json(health_result, limit=16 * 1024, status_code="health_status")
    _require_headers(health_result, cache_control="no-store")
    app = health.get("app")
    classroom_health = health.get("classroom_sample")
    operator = health.get("operator_ai_access")
    if not isinstance(app, Mapping) or app.get("id") != APP_ID:
        raise PostDeploySmokeError("health_app_id_mismatch")
    if app.get("version") != APP_VERSION:
        raise PostDeploySmokeError("health_app_version_mismatch")
    if app.get("build_id") != expected_build_id:
        raise PostDeploySmokeError("health_build_id_mismatch")
    if health.get("ok") is not True:
        raise PostDeploySmokeError("health_not_ok")
    if health.get("api_key_configured") is not True:
        raise PostDeploySmokeError("health_opendart_key_not_configured")
    if health.get("strict_schema_enabled") is not True:
        raise PostDeploySmokeError("health_strict_schema_disabled")
    if health.get("strict_schema_validator_ready") is not True:
        raise PostDeploySmokeError("health_schema_validator_not_ready")
    if (
        not isinstance(classroom_health, Mapping)
        or classroom_health.get("available") is not True
        or classroom_health.get("endpoint") != "/api/classroom/bootstrap"
        or classroom_health.get("network_requests") != 0
    ):
        raise PostDeploySmokeError("health_classroom_contract_mismatch")
    if not isinstance(operator, Mapping) or operator.get("authentication_required") is not True:
        raise PostDeploySmokeError("health_operator_auth_not_required")

    sample_result = fetcher(f"{base}/api/classroom/bootstrap", timeout_seconds)
    sample = _json(sample_result, limit=512 * 1024, status_code="classroom_status")
    _require_headers(sample_result, cache_control="no-store")
    sample_meta = sample.get("sample")
    if not isinstance(sample_meta, Mapping):
        raise PostDeploySmokeError("classroom_sample_metadata_missing")
    expected_sample = {
        "enabled": True,
        "network_requests": 0,
        "contains_real_company_data": False,
        "contains_personal_data": False,
        "watermark": "SAMPLE — SYNTHETIC DATA",
        "outbound_evidence_links": False,
        "receipt_numbers_exposed": False,
    }
    if any(sample_meta.get(key) != value for key, value in expected_sample.items()):
        raise PostDeploySmokeError("classroom_sample_contract_mismatch")

    return {
        "ok": True,
        "base_url": base,
        "expected_build_id": expected_build_id,
        "root_bytes": len(root.body),
        "static_bytes": len(static_result.body),
        "protected_path_count": len(PROTECTED_RUNTIME_PATHS),
        "health_bytes": len(health_result.body),
        "classroom_bytes": len(sample_result.body),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        summary = validate_deployment(
            args.base_url,
            args.expected_sha,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, PostDeploySmokeError) as exc:
        reason = exc.code if isinstance(exc, PostDeploySmokeError) else "network_error"
        print(f"FAIL post-deploy-smoke reason={reason}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
