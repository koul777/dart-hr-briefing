from __future__ import annotations

import json
import unittest
from pathlib import Path

from api.index import handler as VercelHandler
from server import DashboardHandler, user_openai_provider


ROOT = Path(__file__).resolve().parent


class ServerDeploymentTests(unittest.TestCase):
    def test_vercel_entrypoint_reuses_dashboard_handler(self):
        self.assertTrue(issubclass(VercelHandler, DashboardHandler))
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["rewrites"][0]["destination"], "/api/index")
        self.assertGreaterEqual(config["functions"]["api/index.py"]["maxDuration"], 60)

    def test_same_origin_https_request_is_allowed(self):
        request_handler = object.__new__(DashboardHandler)
        request_handler.headers = {
            "Origin": "https://dart-hr-briefing.vercel.app",
            "Host": "dart-hr-briefing.vercel.app",
        }
        self.assertTrue(request_handler.origin_allowed())

        request_handler.headers = {
            "Origin": "https://untrusted.example",
            "Host": "dart-hr-briefing.vercel.app",
        }
        self.assertFalse(request_handler.origin_allowed())

    def test_user_openai_key_creates_request_scoped_provider(self):
        provider = user_openai_provider("sk-user-test-key")
        self.assertTrue(provider.configured)
        self.assertEqual(provider.api_key, "sk-user-test-key")

        with self.assertRaisesRegex(ValueError, "sk-"):
            user_openai_provider("invalid-key")


if __name__ == "__main__":
    unittest.main()
