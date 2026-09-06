from __future__ import annotations

import json
import unittest

from tools.post_deploy_smoke import (
    PROTECTED_RUNTIME_PATHS,
    HTTPResult,
    PostDeploySmokeError,
    validate_deployment,
)


def _headers(cache_control: str) -> dict[str, str]:
    return {
        "Cache-Control": cache_control,
        "Strict-Transport-Security": "max-age=31536000",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }


def _json_response(payload: dict, cache_control: str = "no-store") -> HTTPResult:
    return HTTPResult(
        200,
        _headers(cache_control),
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


class PostDeploySmokeTests(unittest.TestCase):
    def responses(self, sha: str = "a" * 40) -> dict[str, HTTPResult]:
        base = "https://release.example"
        health = {
            "ok": True,
            "api_key_configured": True,
            "app": {
                "id": "kr.opendart.dart-hr-briefing",
                "version": "0.2.0",
                "build_id": f"git-{sha[:12]}",
            },
            "strict_schema_enabled": True,
            "strict_schema_validator_ready": True,
            "classroom_sample": {
                "available": True,
                "endpoint": "/api/classroom/bootstrap",
                "network_requests": 0,
            },
            "operator_ai_access": {"authentication_required": True},
        }
        classroom = {
            "sample": {
                "enabled": True,
                "network_requests": 0,
                "contains_real_company_data": False,
                "contains_personal_data": False,
                "watermark": "SAMPLE — SYNTHETIC DATA",
                "outbound_evidence_links": False,
                "receipt_numbers_exposed": False,
            }
        }
        responses = {
            f"{base}/": HTTPResult(
                200,
                _headers("no-cache"),
                b'<button id="loadClassroomButton">sample</button>',
            ),
            f"{base}/static/app.js": HTTPResult(
                200,
                _headers("no-cache"),
                b"const API_REQUEST_TIMEOUT_MS = 45_000;",
            ),
            f"{base}/api/health": _json_response(health),
            f"{base}/api/classroom/bootstrap": _json_response(classroom),
        }
        responses.update(
            {
                f"{base}{path}": HTTPResult(404, _headers("no-store"), b'{"error":"not found"}')
                for path in PROTECTED_RUNTIME_PATHS
            }
        )
        return responses

    @staticmethod
    def fetcher(responses: dict[str, HTTPResult]):
        def fetch(url: str, _timeout_seconds: float) -> HTTPResult:
            return responses[url]

        return fetch

    def test_expected_commit_and_classroom_contract_pass(self) -> None:
        sha = "a" * 40
        summary = validate_deployment(
            "https://release.example/",
            sha,
            fetcher=self.fetcher(self.responses(sha)),
        )

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["expected_build_id"], "git-aaaaaaaaaaaa")
        self.assertEqual(summary["protected_path_count"], len(PROTECTED_RUNTIME_PATHS))

    def test_public_runtime_source_is_a_release_blocker(self) -> None:
        responses = self.responses()
        responses["https://release.example/server.py"] = HTTPResult(
            200,
            {"Content-Type": "text/x-python"},
            b"APP_VERSION = 'operator-secret-value'",
        )

        with self.assertRaises(PostDeploySmokeError) as caught:
            validate_deployment(
                "https://release.example",
                "a" * 40,
                fetcher=self.fetcher(responses),
            )

        self.assertEqual(caught.exception.code, "runtime_source_public")
        self.assertNotIn("operator-secret-value", str(caught.exception))

    def test_wrong_build_is_rejected_without_returning_response_content(self) -> None:
        responses = self.responses("b" * 40)
        health_result = responses["https://release.example/api/health"]
        health_payload = json.loads(health_result.body)
        health_payload["private_detail"] = "operator-secret-value"
        responses["https://release.example/api/health"] = _json_response(health_payload)
        with self.assertRaises(PostDeploySmokeError) as caught:
            validate_deployment(
                "https://release.example",
                "a" * 40,
                fetcher=self.fetcher(responses),
            )

        self.assertEqual(caught.exception.code, "health_build_id_mismatch")
        self.assertNotIn("operator-secret-value", str(caught.exception))

    def test_missing_security_header_is_rejected(self) -> None:
        responses = self.responses()
        root = responses["https://release.example/"]
        responses["https://release.example/"] = HTTPResult(
            root.status,
            {"Cache-Control": "no-cache"},
            root.body,
        )
        with self.assertRaises(PostDeploySmokeError) as caught:
            validate_deployment(
                "https://release.example",
                "a" * 40,
                fetcher=self.fetcher(responses),
            )
        self.assertEqual(caught.exception.code, "header_x-content-type-options_invalid")

    def test_missing_opendart_configuration_is_rejected(self) -> None:
        responses = self.responses()
        health_result = responses["https://release.example/api/health"]
        health_payload = json.loads(health_result.body)
        health_payload["api_key_configured"] = False
        responses["https://release.example/api/health"] = _json_response(health_payload)

        with self.assertRaises(PostDeploySmokeError) as caught:
            validate_deployment(
                "https://release.example",
                "a" * 40,
                fetcher=self.fetcher(responses),
            )
        self.assertEqual(caught.exception.code, "health_opendart_key_not_configured")

    def test_base_url_cannot_contain_credentials_or_query(self) -> None:
        for url in (
            "http://release.example",
            "https://user:secret@release.example",
            "https://release.example?token=secret",
        ):
            with self.subTest(url=url), self.assertRaises(PostDeploySmokeError):
                validate_deployment(url, "a" * 40, fetcher=self.fetcher({}))


if __name__ == "__main__":
    unittest.main()
