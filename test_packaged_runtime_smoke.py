from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from classroom_mode import build_classroom_payload


ROOT = Path(__file__).resolve().parent
MODULE_PATH = ROOT / "tools" / "packaged_runtime_smoke.py"
SPEC = importlib.util.spec_from_file_location("packaged_runtime_smoke", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"failed to load module from {MODULE_PATH}")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class PackagedRuntimeSmokeTests(unittest.TestCase):
    def test_terminate_process_tree_uses_taskkill_on_windows(self) -> None:
        class FakeProcess:
            pid = 1234

            def poll(self):
                return None

            def wait(self, timeout=None):
                return 0

        with (
            patch.object(smoke.os, "name", "nt"),
            patch.object(smoke.subprocess, "run") as run_mock,
        ):
            smoke._terminate_process_tree(FakeProcess())

        run_mock.assert_called_once_with(
            ["taskkill", "/PID", "1234", "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def test_terminate_process_tree_noops_for_exited_process(self) -> None:
        class FakeProcess:
            pid = 1234

            def poll(self):
                return 0

        with patch.object(smoke.subprocess, "run") as run_mock:
            smoke._terminate_process_tree(FakeProcess())

        run_mock.assert_not_called()

    def test_validate_health_payload_requires_ok(self) -> None:
        with self.assertRaisesRegex(ValueError, "ok=true"):
            smoke.validate_health_payload({"ok": False, "runtime": {}})

    def test_validate_health_payload_returns_runtime_summary(self) -> None:
        summary = smoke.validate_health_payload(
            {
                "ok": True,
                "app": {
                    "id": "kr.opendart.dart-hr-briefing",
                    "version": "0.2.0",
                    "build_id": "test-build",
                    "instance_id": "test-instance",
                    "port": 8782,
                },
                "api_key_configured": True,
                "strict_schema_enabled": True,
                "strict_schema_validator_ready": True,
                "classroom_sample": {
                    "available": True,
                    "endpoint": "/api/classroom/bootstrap",
                    "network_requests": 0,
                },
                "runtime": {
                    "dart_cache": {},
                    "rate_limiter": {},
                },
            }
        )

        self.assertTrue(summary["health_ok"])
        self.assertEqual(summary["app_id"], "kr.opendart.dart-hr-briefing")
        self.assertEqual(summary["port"], 8782)
        self.assertTrue(summary["api_key_configured"])
        self.assertTrue(summary["strict_schema_enabled"])
        self.assertTrue(summary["strict_schema_validator_ready"])
        self.assertTrue(summary["classroom_sample_available"])
        self.assertEqual(summary["runtime_keys"], ["dart_cache", "rate_limiter"])

    def test_validate_static_html_requires_bundled_application_assets(self) -> None:
        summary = smoke.validate_static_html(
            '<title>DART HR Briefing — test</title>'
            '<link href="/static/styles.css">'
            '<script src="/static/app.js"></script>'
        )

        self.assertTrue(summary["root_html_ok"])
        with self.assertRaisesRegex(ValueError, "required application assets"):
            smoke.validate_static_html("<title>wrong app</title>")
        assets = smoke.validate_static_assets(
            "averageSalaryAggregateLabel strategyMetricQualityDetail 평균 급여 계산 기준 "
            "setActiveSearchOption relativeComparisonBoundary strategy-load-notice safeStorageGet "
            "loadClassroomMode /api/classroom/bootstrap provider_data_consent",
            ".strategy-metric-quality .people-salary-basis .comparison-boundary "
            ".strategy-load-notice .result-item.active .sample-banner .ai-transfer-notice",
        )
        self.assertTrue(assets["app_js_ok"])
        self.assertTrue(assets["styles_css_ok"])
        with self.assertRaisesRegex(ValueError, "app.js"):
            smoke.validate_static_assets(
                "old bundle",
                ".strategy-metric-quality .people-salary-basis .comparison-boundary "
                ".strategy-load-notice .result-item.active .sample-banner .ai-transfer-notice",
            )
        security_headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=()",
        }
        security = smoke.validate_security_headers(security_headers)
        self.assertTrue(security["security_headers_ok"])
        security_headers.pop("Strict-Transport-Security")
        with self.assertRaisesRegex(ValueError, "HSTS"):
            smoke.validate_security_headers(security_headers)

    def test_validate_orchestration_payload_requires_schema_v2(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema_version=2"):
            smoke.validate_orchestration_payload(
                {
                    "schema_version": 1,
                    "facts": {"records": [{"company": {"corp_name": "A사"}}]},
                    "evidence": {"ledger": [{"evidence_id": "EV-1"}]},
                }
            )

    def test_validate_classroom_payload_uses_synthetic_zero_network_contract(self) -> None:
        summary = smoke.validate_classroom_payload(build_classroom_payload())

        self.assertTrue(summary["sample_enabled"])
        self.assertEqual(summary["fixture_id"], "dart-hr-briefing-classroom-v1")
        self.assertEqual(summary["network_requests"], 0)
        self.assertEqual(summary["company_count"], 2)
        self.assertEqual(summary["source"], "synthetic_fixture")
        self.assertEqual(summary["reference_mode"], "synthetic_fixture_urn")
        self.assertFalse(summary["external_source_links"])
        self.assertEqual(summary["orchestration"]["provider_status"], "not_configured")

        invalid = build_classroom_payload()
        invalid["sample"]["network_requests"] = 1
        with self.assertRaisesRegex(ValueError, "synthetic and zero-network"):
            smoke.validate_classroom_payload(invalid)

        untrusted_provenance = build_classroom_payload()
        untrusted_provenance["sample"]["provenance"]["source_data_used"] = True
        with self.assertRaisesRegex(ValueError, "synthetic and zero-network"):
            smoke.validate_classroom_payload(untrusted_provenance)

        leaked = build_classroom_payload()
        leaked["results"][0]["source_url"] = (
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20991231999999"
        )
        with self.assertRaisesRegex(ValueError, "filing URLs or receipt numbers"):
            smoke.validate_classroom_payload(leaked)

    def test_validate_orchestration_payload_requires_non_empty_ledger(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty evidence ledger"):
            smoke.validate_orchestration_payload(
                {
                    "schema_version": 2,
                    "facts": {"records": [{"company": {"corp_name": "A사"}}]},
                    "evidence": {"ledger": []},
                }
            )

    def test_validate_orchestration_payload_returns_summary(self) -> None:
        brief = {
            "selected_metric_id": "employees_total",
            "selected_metric_label": "총 직원 수",
            "selection_reason": "총 직원 수가 대표 지표로 선택됐습니다.",
            "conclusion": "총 직원 수는 선택 기업 중앙값 부근입니다.",
            "decision_action": "검증 질문 설정 · 직무별 인원을 먼저 확인합니다.",
            "cohort_limit": "산업·규모·사업모델을 보정한 외부 벤치마크가 아닙니다.",
            "next_data": ["직무별 인원"],
            "signal_type": "lagging",
            "evidence_ids": ["EV-000000000001"],
            "reason_codes": ["history_not_in_readiness"],
            "self_trajectory": {"status": "not_available"},
            "metric_assessments": [{
                "metric_id": "employees_total",
                "metric_label": "총 직원 수",
                "signal_type": "lagging",
                "evidence_ids": ["EV-000000000001"],
            }],
        }
        summary = smoke.validate_orchestration_payload(
            {
                "schema_version": 2,
                "run_id": "RUN-123",
                "facts": {
                    "records": [
                        {
                            "company": {"corp_name": "삼성전자"},
                        }
                    ]
                },
                "evidence": {"ledger": [
                    {
                        "evidence_id": "EV-000000000001",
                        "source_coverage_complete": True,
                    },
                    {
                        "evidence_id": "EV-000000000002",
                        "source_coverage_complete": True,
                    },
                ]},
                "validation": {"status": "passed"},
                "provider": {"status": "not_configured"},
                "decision_support": {
                    "briefs": [dict(brief) for _ in range(3)],
                    "readiness": [{} for _ in range(5)],
                },
            }
        )

        self.assertEqual(summary["schema_version"], 2)
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["evidence_count"], 2)
        self.assertEqual(summary["source_complete_evidence_count"], 2)
        self.assertEqual(summary["validation_status"], "passed")
        self.assertEqual(summary["provider_status"], "not_configured")
        self.assertEqual(summary["decision_brief_count"], 3)
        self.assertEqual(summary["readiness_dimension_count"], 5)
        self.assertEqual(summary["decision_metric_assessment_count"], 3)
        self.assertEqual(summary["company"], "삼성전자")
        self.assertEqual(summary["run_id"], "RUN-123")

    def test_build_orchestration_url_uses_expected_query(self) -> None:
        url = smoke._build_orchestration_url(
            8776,
            corp_code="00126380",
            year="2024",
            report_code="11011",
        )

        self.assertEqual(
            url,
            "http://127.0.0.1:8776/api/workforce/orchestration?corp_codes=00126380&year=2024&report_code=11011",
        )

    def test_default_startup_timeout_is_sixty_seconds(self) -> None:
        args = smoke.build_argument_parser().parse_args(["--exe", "candidate.exe"])

        self.assertEqual(args.startup_timeout_seconds, 60.0)
        self.assertEqual(args.working_directory, Path.cwd())
        self.assertFalse(args.health_only)

    def test_console_json_falls_back_to_ascii_when_codepage_cannot_encode(self) -> None:
        payload = {"watermark": "SAMPLE — SYNTHETIC DATA", "company": "샘플전자"}

        rendered = smoke._console_safe_json(payload, "cp949")

        self.assertIn("SAMPLE \\u2014 SYNTHETIC DATA", rendered)
        self.assertIn("\\uc0d8\\ud50c\\uc804\\uc790", rendered)
        self.assertEqual(json.loads(rendered), payload)

    def test_invalid_runtime_options_fail_before_process_start(self) -> None:
        executable = ROOT / "tools" / "packaged_runtime_smoke.py"
        cases = (
            {"port": 0, "startup_timeout_seconds": 1, "request_timeout_seconds": 1},
            {"port": 8776, "startup_timeout_seconds": 0, "request_timeout_seconds": 1},
            {"port": 8776, "startup_timeout_seconds": 1, "request_timeout_seconds": float("nan")},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), patch.object(
                smoke.subprocess, "Popen"
            ) as popen, self.assertRaises(ValueError):
                smoke.run_packaged_smoke(
                    executable,
                    working_directory=ROOT,
                    corp_code="00126380",
                    year="2024",
                    report_code="11011",
                    strict_schema=True,
                    **overrides,
                )
            popen.assert_not_called()

    def test_occupied_port_fails_before_process_start(self) -> None:
        executable = ROOT / "tools" / "packaged_runtime_smoke.py"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            with patch.object(smoke.subprocess, "Popen") as popen, self.assertRaises(
                OSError
            ):
                smoke.run_packaged_smoke(
                    executable,
                    working_directory=ROOT,
                    port=port,
                    corp_code="00126380",
                    year="2024",
                    report_code="11011",
                    startup_timeout_seconds=1,
                    request_timeout_seconds=1,
                    strict_schema=True,
                )
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
