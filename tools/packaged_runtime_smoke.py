"""Run a packaged DART runtime smoke test with deterministic cleanup."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import urlopen


MAX_SMOKE_RESPONSE_BYTES = 2 * 1024 * 1024


def _console_safe_json(result: Mapping[str, Any], encoding: str | None) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    try:
        rendered.encode(encoding or "utf-8")
    except (LookupError, UnicodeEncodeError):
        return json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    return rendered


def _reject_nonfinite_json(token: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {token}")


def _fetch_json(url: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:
        raw = response.read(MAX_SMOKE_RESPONSE_BYTES + 1)
        if len(raw) > MAX_SMOKE_RESPONSE_BYTES:
            raise ValueError("smoke response exceeds the size limit")
        payload = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_nonfinite_json,
        )
    if not isinstance(payload, Mapping):
        raise ValueError("expected a JSON object response")
    return payload


def _fetch_text(url: str, *, timeout_seconds: float) -> str:
    value, _ = _fetch_text_response(url, timeout_seconds=timeout_seconds)
    return value


def _fetch_text_response(
    url: str,
    *,
    timeout_seconds: float,
) -> tuple[str, dict[str, str]]:
    with urlopen(url, timeout=timeout_seconds) as response:
        raw = response.read(MAX_SMOKE_RESPONSE_BYTES + 1)
        if len(raw) > MAX_SMOKE_RESPONSE_BYTES:
            raise ValueError("smoke response exceeds the size limit")
        headers = {key.lower(): value for key, value in response.headers.items()}
    return raw.decode("utf-8"), headers


def validate_health_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("ok") is not True:
        raise ValueError("health payload must include ok=true")
    app = payload.get("app")
    if (
        not isinstance(app, Mapping)
        or app.get("id") != "kr.opendart.dart-hr-briefing"
        or not str(app.get("version") or "").strip()
        or not str(app.get("build_id") or "").strip()
        or not str(app.get("instance_id") or "").strip()
        or not isinstance(app.get("port"), int)
    ):
        raise ValueError("health payload must identify the DART application build and instance")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("health payload must include runtime metrics")
    classroom = payload.get("classroom_sample")
    if (
        not isinstance(classroom, Mapping)
        or classroom.get("available") is not True
        or classroom.get("endpoint") != "/api/classroom/bootstrap"
        or classroom.get("network_requests") != 0
    ):
        raise ValueError("health payload must expose the zero-network classroom sample")
    return {
        "health_ok": True,
        "app_id": str(app["id"]),
        "app_version": str(app["version"]),
        "build_id": str(app["build_id"]),
        "instance_id": str(app["instance_id"]),
        "port": int(app["port"]),
        "api_key_configured": bool(payload.get("api_key_configured")),
        "strict_schema_enabled": bool(payload.get("strict_schema_enabled")),
        "strict_schema_validator_ready": bool(
            payload.get("strict_schema_validator_ready")
        ),
        "runtime_keys": sorted(str(key) for key in runtime.keys()),
        "classroom_sample_available": True,
    }


def validate_static_html(value: str) -> dict[str, Any]:
    if (
        "<title>DART HR Briefing" not in value
        or 'src="/static/app.js"' not in value
        or 'href="/static/styles.css"' not in value
    ):
        raise ValueError("packaged root HTML is missing required application assets")
    return {"root_html_ok": True, "response_bytes": len(value.encode("utf-8"))}


def validate_static_assets(app_js: str, styles_css: str) -> dict[str, Any]:
    app_markers = (
        "averageSalaryAggregateLabel",
        "strategyMetricQualityDetail",
        "평균 급여 계산 기준",
        "setActiveSearchOption",
        "relativeComparisonBoundary",
        "strategy-load-notice",
        "safeStorageGet",
        "loadClassroomMode",
        "/api/classroom/bootstrap",
        "provider_data_consent",
    )
    style_markers = (
        ".strategy-metric-quality",
        ".people-salary-basis",
        ".comparison-boundary",
        ".strategy-load-notice",
        ".result-item.active",
        ".sample-banner",
        ".ai-transfer-notice",
    )
    if any(marker not in app_js for marker in app_markers):
        raise ValueError("packaged app.js is missing HR decision-support markers")
    if any(marker not in styles_css for marker in style_markers):
        raise ValueError("packaged styles.css is missing HR decision-support styles")
    return {
        "app_js_ok": True,
        "styles_css_ok": True,
        "app_js_bytes": len(app_js.encode("utf-8")),
        "styles_css_bytes": len(styles_css.encode("utf-8")),
    }


def validate_classroom_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sample = payload.get("sample")
    provenance = sample.get("provenance") if isinstance(sample, Mapping) else None
    if (
        not isinstance(sample, Mapping)
        or sample.get("enabled") is not True
        or sample.get("watermark") != "SAMPLE — SYNTHETIC DATA"
        or sample.get("fixture_id") != "dart-hr-briefing-classroom-v1"
        or sample.get("network_requests") != 0
        or sample.get("contains_real_company_data") is not False
        or sample.get("contains_personal_data") is not False
        or sample.get("evidence_references") != "synthetic_contract_only"
        or sample.get("outbound_evidence_links") is not False
        or sample.get("receipt_numbers_exposed") is not False
        or not isinstance(provenance, Mapping)
        or provenance.get("source_data_used") is not False
        or provenance.get("third_party_content_used") is not False
        or provenance.get("contains_real_company_data") is not False
        or provenance.get("contains_personal_data") is not False
    ):
        raise ValueError("classroom payload must be explicitly synthetic and zero-network")
    companies = payload.get("companies")
    if (
        not isinstance(companies, list)
        or len(companies) < 2
        or any(
            not isinstance(company, Mapping)
            or not str(company.get("corp_code") or "").startswith("9")
            for company in companies
        )
    ):
        raise ValueError("classroom payload must include synthetic comparison companies")
    count = len(companies)
    for key in ("results", "previous", "history", "people", "people_history"):
        rows = payload.get(key)
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError(f"classroom payload has an invalid {key} collection")
    orchestration = payload.get("orchestration")
    if (
        not isinstance(orchestration, Mapping)
        or orchestration.get("source") != "synthetic_fixture"
    ):
        raise ValueError("classroom payload must include deterministic orchestration")
    evidence = orchestration.get("evidence")
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("reference_mode") != "synthetic_fixture_urn"
        or evidence.get("external_source_links") is not False
        or "합성" not in str(evidence.get("source_notice") or "")
    ):
        raise ValueError("classroom evidence must identify synthetic non-network references")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if (
        re.search(r"https?://|dart\.fss\.or\.kr", serialized, flags=re.IGNORECASE)
        or "20991231" in serialized
        or '"rcept_no"' in serialized
    ):
        raise ValueError("classroom payload must not expose filing URLs or receipt numbers")
    orchestration_summary = validate_orchestration_payload(orchestration)
    return {
        "sample_enabled": True,
        "fixture_id": str(sample["fixture_id"]),
        "watermark": str(sample["watermark"]),
        "network_requests": 0,
        "company_count": count,
        "year": str(payload.get("year") or ""),
        "report_code": str(payload.get("report_code") or ""),
        "source": "synthetic_fixture",
        "reference_mode": "synthetic_fixture_urn",
        "external_source_links": False,
        "orchestration": orchestration_summary,
    }


def validate_security_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    required_exact = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
    }
    for name, expected in required_exact.items():
        if normalized.get(name) != expected:
            raise ValueError(f"packaged static response has invalid {name}")
    if not normalized.get("strict-transport-security", "").startswith("max-age=31536000"):
        raise ValueError("packaged static response is missing HSTS")
    if "default-src 'self'" not in normalized.get("content-security-policy", ""):
        raise ValueError("packaged static response is missing CSP")
    if "camera=()" not in normalized.get("permissions-policy", ""):
        raise ValueError("packaged static response is missing Permissions-Policy")
    return {"security_headers_ok": True}


def validate_orchestration_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if int(payload.get("schema_version") or 0) != 2:
        raise ValueError("orchestration payload must include schema_version=2")
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        raise ValueError("orchestration payload must include facts")
    records = facts.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("orchestration payload must include at least one fact record")
    evidence = payload.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("orchestration payload must include evidence")
    ledger = evidence.get("ledger")
    if not isinstance(ledger, list) or not ledger:
        raise ValueError("orchestration payload must include a non-empty evidence ledger")
    evidence_ids = [
        item.get("evidence_id") if isinstance(item, Mapping) else None
        for item in ledger
    ]
    if (
        any(not isinstance(value, str) or not re.fullmatch(r"EV-[0-9a-f]{12}", value) for value in evidence_ids)
        or len(set(evidence_ids)) != len(evidence_ids)
    ):
        raise ValueError("orchestration evidence IDs must be unique and well formed")
    source_complete_count = sum(
        1
        for item in ledger
        if isinstance(item, Mapping) and item.get("source_coverage_complete") is True
    )
    if source_complete_count != len(ledger):
        raise ValueError("orchestration evidence must have complete source coverage")
    validation = payload.get("validation")
    if not isinstance(validation, Mapping) or validation.get("status") != "passed":
        raise ValueError("orchestration response guard must pass")
    provider = payload.get("provider")
    provider_status = provider.get("status") if isinstance(provider, Mapping) else None
    if provider_status not in {"not_configured", "skipped"}:
        raise ValueError("deterministic GET orchestration must not execute an AI provider")
    decision_support = payload.get("decision_support")
    if not isinstance(decision_support, Mapping):
        raise ValueError("orchestration payload must include decision support")
    briefs = decision_support.get("briefs")
    readiness = decision_support.get("readiness")
    if not isinstance(briefs, list) or len(briefs) != 3:
        raise ValueError("decision support must include exactly three primary briefs")
    if not isinstance(readiness, list) or len(readiness) != 5:
        raise ValueError("decision support must include five readiness dimensions")
    assessment_count = 0
    for brief in briefs:
        if not isinstance(brief, Mapping):
            raise ValueError("decision brief must be an object")
        selected_metric_id = brief.get("selected_metric_id")
        selected_metric_label = brief.get("selected_metric_label")
        assessments = brief.get("metric_assessments")
        brief_evidence_ids = brief.get("evidence_ids")
        if (
            not isinstance(selected_metric_id, str)
            or not isinstance(selected_metric_label, str)
            or selected_metric_label not in str(brief.get("selection_reason") or "")
            or not isinstance(brief.get("conclusion"), str)
            or "중앙값" not in brief["conclusion"]
            or not isinstance(brief.get("decision_action"), str)
            or not (brief.get("next_data") or [])
            or str(brief["next_data"][0]) not in brief["decision_action"]
            or "산업·규모·사업모델" not in str(brief.get("cohort_limit") or "")
            or "외부 벤치마크가 아닙니다" not in str(brief.get("cohort_limit") or "")
            or not isinstance(assessments, list)
            or not assessments
            or not isinstance(brief_evidence_ids, list)
        ):
            raise ValueError("decision brief is missing representative-metric transparency")
        selected_assessments = [
            item for item in assessments
            if isinstance(item, Mapping)
            and item.get("metric_id") == selected_metric_id
        ]
        assessment_evidence_ids = {
            evidence_id
            for item in assessments
            if isinstance(item, Mapping)
            and isinstance(item.get("evidence_ids"), list)
            for evidence_id in item["evidence_ids"]
        }
        if (
            len(selected_assessments) != 1
            or selected_assessments[0].get("metric_label") != selected_metric_label
            or selected_assessments[0].get("signal_type") != brief.get("signal_type")
            or assessment_evidence_ids != set(brief_evidence_ids)
            or not assessment_evidence_ids.issubset(set(evidence_ids))
            or (brief.get("self_trajectory") or {}).get("status") != "not_available"
            or "history_not_in_readiness" not in (brief.get("reason_codes") or [])
        ):
            raise ValueError("decision brief metric assessment contract is inconsistent")
        assessment_count += len(assessments)
    first_record = records[0]
    company = first_record.get("company") if isinstance(first_record, Mapping) else {}
    if not isinstance(company, Mapping) or not str(company.get("corp_name") or "").strip():
        raise ValueError("orchestration payload must expose the first company name")
    return {
        "schema_version": 2,
        "record_count": len(records),
        "evidence_count": len(ledger),
        "source_complete_evidence_count": source_complete_count,
        "validation_status": "passed",
        "provider_status": provider_status,
        "decision_brief_count": len(briefs),
        "readiness_dimension_count": len(readiness),
        "decision_metric_assessment_count": assessment_count,
        "company": str(company.get("corp_name")),
        "run_id": str(payload.get("run_id") or ""),
    }


def _build_orchestration_url(
    port: int,
    *,
    corp_code: str,
    year: str,
    report_code: str,
) -> str:
    query = urlencode(
        {
            "corp_codes": corp_code,
            "year": year,
            "report_code": report_code,
        }
    )
    return f"http://127.0.0.1:{port}/api/workforce/orchestration?{query}"


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _assert_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))


def run_packaged_smoke(
    exe_path: Path,
    *,
    working_directory: Path,
    port: int,
    corp_code: str,
    year: str,
    report_code: str,
    startup_timeout_seconds: float,
    request_timeout_seconds: float,
    strict_schema: bool,
    health_only: bool = False,
) -> dict[str, Any]:
    resolved_exe = exe_path.resolve()
    resolved_working_directory = working_directory.resolve()
    if not resolved_exe.is_file():
        raise FileNotFoundError(f"packaged executable not found: {resolved_exe}")
    if not resolved_working_directory.is_dir():
        raise NotADirectoryError(
            f"packaged runtime working directory not found: {resolved_working_directory}"
        )
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if (
        not math.isfinite(startup_timeout_seconds)
        or startup_timeout_seconds <= 0
        or not math.isfinite(request_timeout_seconds)
        or request_timeout_seconds <= 0
    ):
        raise ValueError("smoke timeouts must be finite and positive")
    _assert_port_available(port)
    environment = dict(os.environ)
    environment["PORT"] = str(port)
    environment["DART_OPEN_BROWSER"] = "false"
    environment["DART_STRICT_ORCHESTRATION_SCHEMA"] = (
        "true" if strict_schema else "false"
    )

    process = subprocess.Popen(
        [str(resolved_exe)],
        cwd=resolved_working_directory,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + startup_timeout_seconds
        health_payload: Mapping[str, Any] | None = None
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"packaged runtime exited before becoming healthy ({process.returncode})"
                )
            try:
                health_payload = _fetch_json(
                    f"http://127.0.0.1:{port}/api/health",
                    timeout_seconds=request_timeout_seconds,
                )
                break
            except (OSError, ValueError) as exc:
                last_error = exc
                time.sleep(0.5)
        if health_payload is None:
            raise RuntimeError(
                "packaged runtime did not become healthy"
            ) from last_error

        health_summary = validate_health_payload(health_payload)
        if strict_schema and (
            not health_summary["strict_schema_enabled"]
            or not health_summary["strict_schema_validator_ready"]
        ):
            raise RuntimeError("packaged strict schema validator is not ready")
        if process.poll() is not None:
            raise RuntimeError(
                f"packaged runtime exited after health check ({process.returncode})"
            )
        root_html, root_headers = _fetch_text_response(
            f"http://127.0.0.1:{port}/",
            timeout_seconds=request_timeout_seconds,
        )
        static_summary = validate_static_html(root_html)
        static_summary.update(validate_security_headers(root_headers))
        static_summary.update(validate_static_assets(
            _fetch_text(
                f"http://127.0.0.1:{port}/static/app.js",
                timeout_seconds=request_timeout_seconds,
            ),
            _fetch_text(
                f"http://127.0.0.1:{port}/static/styles.css",
                timeout_seconds=request_timeout_seconds,
            ),
        ))
        if process.poll() is not None:
            raise RuntimeError(
                f"packaged runtime exited after static asset check ({process.returncode})"
            )
        classroom_payload = _fetch_json(
            f"http://127.0.0.1:{port}/api/classroom/bootstrap",
            timeout_seconds=request_timeout_seconds,
        )
        classroom_summary = validate_classroom_payload(classroom_payload)
        if process.poll() is not None:
            raise RuntimeError(
                f"packaged runtime exited after classroom check ({process.returncode})"
            )
        base_result = {
            "build_path": str(resolved_exe),
            "working_directory": str(resolved_working_directory),
            "pid": process.pid,
            "port": port,
            "health": health_summary,
            "static": static_summary,
            "classroom": classroom_summary,
        }
        if health_only:
            return {**base_result, "mode": "health_only", "orchestration": None}
        if not health_summary["api_key_configured"]:
            raise RuntimeError(
                "packaged runtime is healthy but OPENDART_API_KEY is not configured "
                "in the process environment or a supported .env location"
            )
        orchestration_payload = _fetch_json(
            _build_orchestration_url(
                port,
                corp_code=corp_code,
                year=year,
                report_code=report_code,
            ),
            timeout_seconds=request_timeout_seconds,
        )
        orchestration_summary = validate_orchestration_payload(orchestration_payload)
        if process.poll() is not None:
            raise RuntimeError(
                f"packaged runtime exited after orchestration check ({process.returncode})"
            )
        return {
            **base_result,
            "mode": "live_dart",
            "orchestration": orchestration_summary,
            "request_id": orchestration_payload.get("request_id"),
        }
    finally:
        _terminate_process_tree(process)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--working-directory", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8776)
    parser.add_argument("--corp-code", default="00126380")
    parser.add_argument("--year", default="2024")
    parser.add_argument("--report-code", default="11011")
    parser.add_argument("--startup-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--strict-schema", action="store_true")
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Validate startup, health, and bundled static assets without OpenDART.",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()

    result = run_packaged_smoke(
        args.exe,
        working_directory=args.working_directory,
        port=args.port,
        corp_code=args.corp_code,
        year=args.year,
        report_code=args.report_code,
        startup_timeout_seconds=args.startup_timeout_seconds,
        request_timeout_seconds=args.request_timeout_seconds,
        strict_schema=args.strict_schema,
        health_only=args.health_only,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(_console_safe_json(result, getattr(sys.stdout, "encoding", None)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
