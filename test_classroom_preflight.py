from __future__ import annotations

import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from tools import classroom_preflight


class ClassroomPreflightTests(unittest.TestCase):
    def test_supported_and_unsupported_python_versions(self) -> None:
        self.assertEqual(classroom_preflight.check_python((3, 12, 4)).status, "PASS")
        self.assertEqual(classroom_preflight.check_python((3, 10, 9)).status, "FAIL")
        self.assertEqual(classroom_preflight.check_python((3, 15, 0)).status, "WARN")

    def test_dart_key_reports_configuration_without_disclosing_value(self) -> None:
        secret = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            result = classroom_preflight.check_dart_key(
                Path(temporary), {"OPENDART_API_KEY": secret}
            )
        self.assertEqual(result.status, "PASS")
        self.assertNotIn(secret, result.detail)
        self.assertIn("값은 출력하지 않았습니다", result.detail)

    def test_dotenv_key_is_not_disclosed_for_unexpected_length(self) -> None:
        secret = "unexpected-secret"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text(
                f"# local only\nOPENDART_API_KEY={secret}\n", encoding="utf-8"
            )
            result = classroom_preflight.check_dart_key(root, {})
        self.assertEqual(result.status, "WARN")
        self.assertNotIn(secret, result.detail)

    def test_missing_required_files_are_named_without_reading_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = classroom_preflight.check_required_files(Path(temporary))
        self.assertEqual(result.status, "FAIL")
        self.assertIn("server.py", result.detail)

    def test_main_rejects_invalid_port_before_checks(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            exit_code = classroom_preflight.main(["--port", "70000"])
        self.assertEqual(exit_code, 2)
        self.assertIn("1~65535", stderr.getvalue())

    def test_port_in_use_by_unknown_server_is_a_failure(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            with patch("tools.classroom_preflight._local_health", return_value=None):
                result = classroom_preflight.check_port(port)
        finally:
            listener.close()
        self.assertEqual(result.status, "FAIL")
        self.assertIn(str(port), result.detail)

    def test_port_in_use_by_expected_app_is_ready(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            health = {
                "ok": True,
                "app": {"id": classroom_preflight.EXPECTED_APP_ID},
            }
            with patch("tools.classroom_preflight._local_health", return_value=health):
                result = classroom_preflight.check_port(port)
        finally:
            listener.close()
        self.assertEqual(result.status, "PASS")
        self.assertIn("이미 실행 중", result.detail)


if __name__ == "__main__":
    unittest.main()
