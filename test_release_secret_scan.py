from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.release_secret_scan import format_report, main, scan_release, scan_repository


class ReleaseSecretScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative_path: str, content: str | bytes) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def track(self, *relative_paths: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), "add", "--", *relative_paths],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_only_git_tracked_files_are_scanned_and_dotenv_is_blocked(self) -> None:
        self.write("README.md", "safe\n")
        self.write(
            ".env",
            "OPENAI_API_KEY=" + "sk-" + "untracked-value-123456789\n",
        )
        self.track("README.md")

        self.assertTrue(scan_repository(self.root).passed)

        self.track(".env")
        report = scan_repository(self.root)

        self.assertFalse(report.passed)
        self.assertIn("tracked_dotenv", {item.rule_id for item in report.findings})

    def test_realistic_credentials_and_credential_urls_are_blocked(self) -> None:
        values = (
            "sk-" + "prod-A7b9C3d5E7f9G1h3J5k7L9m1",
            "0123456789abcdef0123456789abcdef01234567",
            "anthropic-A7b9C3d5E7f9G1h3J5k7L9m1",
            "operator-A7b9C3d5E7f9G1h3J5k7L9m1",
            "mcp-A7b9C3d5E7f9G1h3J5k7L9m1N3p5",
            "dartqueryA7b9C3d5E7f9G1h3J5k7",
            "bearer.A7b9C3d5E7f9G1h3J5k7L9m1",
            "deploy-A7b9C3d5E7f9G1h3J5k7L9m1",
            "github_" + "pat_prod_A7b9C3d5E7f9G1h3J5k7L9m1",
            "-----BEGIN " + "PRIVATE KEY-----",
        )
        self.write(
            "config.txt",
            "\n".join((
                f"OPENAI_API_KEY={values[0]}",
                f"OPENDART_API_KEY={values[1]}",
                f"ANTHROPIC_API_KEY={values[2]}",
                f"DART_OPERATOR_AI_TOKEN={values[3]}",
                f"CLAUDE_MCP_GATEWAY_TOKEN={values[4]}",
                f"https://example.invalid/api?crtfc_key={values[5]}",
                f"Authorization: Bearer {values[6]}",
                f"VERCEL_TOKEN={values[7]}",
                values[8],
                values[9],
            )),
        )
        self.track("config.txt")

        report = scan_repository(self.root)
        rule_ids = {item.rule_id for item in report.findings}

        self.assertFalse(report.passed)
        self.assertTrue({
            "openai_api_key",
            "opendart_api_key",
            "anthropic_api_key",
            "operator_token",
            "mcp_token",
            "credential_url_query",
            "bearer_token",
            "deployment_token",
            "github_personal_access_token",
            "private_key_material",
        }.issubset(rule_ids))
        rendered = format_report(report)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_obvious_dummy_values_are_allowed_only_in_tests_and_fixtures(self) -> None:
        dummy = "sk-test-dummy-secret-1234567890"
        self.write("test_adapter.py", f'API_KEY = "{dummy}"\n')
        self.write(
            "fixtures/sample.json",
            '{"url":"https://example.invalid?api_key=fixture-secret-key"}\n',
        )
        self.track("test_adapter.py", "fixtures/sample.json")

        self.assertTrue(scan_repository(self.root).passed)

        self.write("production.py", f'API_KEY = "{dummy}"\n')
        self.track("production.py")

        report = scan_repository(self.root)
        self.assertFalse(report.passed)
        self.assertEqual(
            [item.path for item in report.findings if item.rule_id == "openai_api_key"],
            ["production.py"],
        )

    def test_dotenv_templates_may_be_tracked_but_are_still_content_scanned(self) -> None:
        self.write(".env.example", "OPENAI_API_KEY=\nOPENDART_API_KEY=\n")
        self.track(".env.example")

        self.assertTrue(scan_repository(self.root).passed)

        self.write(
            ".env.example",
            "OPENAI_API_KEY=" + "sk-" + "prod-Z9y7X5w3V1u9T7s5R3q1\n",
        )
        self.track(".env.example")

        report = scan_repository(self.root)
        self.assertFalse(report.passed)
        self.assertNotIn("tracked_dotenv", {item.rule_id for item in report.findings})
        self.assertIn("openai_api_key", {item.rule_id for item in report.findings})

    def test_binary_files_are_skipped_without_loading_or_reporting_values(self) -> None:
        secret = b"sk-" + b"prod-A7b9C3d5E7f9G1h3J5k7L9m1"
        self.write("artifact.png", b"\x89PNG\x00" + secret)
        self.track("artifact.png")

        report = scan_repository(self.root)

        self.assertTrue(report.passed)
        self.assertEqual(report.skipped_binary_files, 1)

    def test_untracked_vercel_candidate_is_scanned_and_size_bounded(self) -> None:
        secret = "sk-" + "prod-VercelCandidateA7b9C3d5E7f9"
        self.write(".vercelignore", "*\n!runtime.py\n!large.bin\n")
        self.write("runtime.py", f'API_KEY = "{secret}"\n')
        self.write("large.bin", b"\0" * (2 * 1024 * 1024 + 1))
        self.track(".vercelignore")

        report = scan_repository(self.root)
        rule_ids = {item.rule_id for item in report.findings}

        self.assertFalse(report.passed)
        self.assertEqual(report.vercel_candidate_files, 2)
        self.assertIn("openai_api_key", rule_ids)
        self.assertIn("vercel_single_file_too_large", rule_ids)
        self.assertNotIn(secret, format_report(report))

    def test_dotfile_and_lockfile_can_be_explicit_vercel_candidates(self) -> None:
        self.write(
            ".vercelignore",
            "*\n!.python-version\n!uv.lock\n",
        )
        self.write(".python-version", "3.12\n")
        self.write("uv.lock", "version = 1\n")
        self.track(".vercelignore")

        report = scan_repository(self.root)

        self.assertTrue(report.passed)
        self.assertEqual(report.vercel_candidate_files, 2)

    def test_explicit_binary_artifact_blocks_patterns_and_known_values(self) -> None:
        pattern_secret = b"sk-" + b"prod-BinaryPatternA7b9C3d5E7f9"
        known_secret = "known-dart-value-A7b9C3d5E7f9"
        self.write("README.md", "safe\n")
        self.write("dist/app.exe", b"MZ\0" + pattern_secret + b"\0" + known_secret.encode())
        self.track("README.md")

        opendart_key_name = "OPEN" + "DART_API_KEY"
        with patch.dict("os.environ", {opendart_key_name: known_secret}, clear=False):
            report = scan_release(self.root, [Path("dist/app.exe")])

        rule_ids = {item.rule_id for item in report.findings}
        rendered = format_report(report)
        self.assertFalse(report.passed)
        self.assertEqual(report.scanned_artifact_files, 1)
        self.assertIn("openai_api_key", rule_ids)
        self.assertIn("known_secret_value", rule_ids)
        self.assertNotIn(pattern_secret.decode(), rendered)
        self.assertNotIn(known_secret, rendered)

    def test_binary_artifact_blocks_operator_mcp_and_deployment_assignments(self) -> None:
        assignments = (
            (
                "DART_" + "OPERATOR_AI_TOKEN",
                "operator-secret-prod-A7b9C3d5E7f9",
                "operator_token",
            ),
            (
                "CLAUDE_" + "MCP_GATEWAY_TOKEN",
                "mcp-secret-prod-A7b9C3d5E7f9G1h3",
                "mcp_token",
            ),
            (
                "VERCEL_" + "TOKEN",
                "deploy-secret-prod-A7b9C3d5E7f9",
                "deployment_token",
            ),
        )
        payload = b"MZ\0" + b"\0".join(
            f"{key}={value}".encode() for key, value, _ in assignments
        )
        self.write("README.md", "safe\n")
        self.write("dist/app.exe", payload)
        self.track("README.md")

        report = scan_release(self.root, [Path("dist/app.exe")])

        rule_ids = {item.rule_id for item in report.findings}
        self.assertFalse(report.passed)
        for _, value, rule_id in assignments:
            self.assertIn(rule_id, rule_ids)
            self.assertNotIn(value, format_report(report))

    def test_secret_word_alone_does_not_make_a_realistic_test_token_safe(self) -> None:
        key = "DART_" + "OPERATOR_AI_TOKEN"
        value = "operator-secret-prod-A7b9C3d5E7f9"
        self.write("test_runtime.py", f"{key}={value}\n")
        self.track("test_runtime.py")

        report = scan_repository(self.root)

        self.assertFalse(report.passed)
        self.assertIn("operator_token", {item.rule_id for item in report.findings})
        self.assertNotIn(value, format_report(report))

    def test_cli_output_contains_only_summary_locations_and_rule_ids(self) -> None:
        secret = "sk-" + "prod-Q1w3E5r7T9y1U3i5O7p9A1s3"
        self.write("settings.ini", f"OPENAI_API_KEY={secret}\n")
        self.track("settings.ini")
        stream = io.StringIO()

        with redirect_stdout(stream):
            exit_code = main(["--root", str(self.root)])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertTrue(output.startswith("FAIL tracked="))
        self.assertIn("settings.ini:1 rule=openai_api_key", output)
        self.assertNotIn(secret, output)


if __name__ == "__main__":
    unittest.main()
