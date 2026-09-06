from __future__ import annotations

import unittest
from pathlib import Path

from server import _runtime_build_id


class ReleaseIdentityTests(unittest.TestCase):
    def test_explicit_build_id_has_precedence_outside_vercel(self) -> None:
        self.assertEqual(
            _runtime_build_id(
                {
                    "DART_BUILD_ID": "classroom-rc1",
                    "VERCEL_GIT_COMMIT_SHA": "a" * 40,
                },
                frozen=False,
                executable=Path("missing.exe"),
            ),
            "classroom-rc1",
        )

    def test_vercel_commit_precedes_operator_build_label(self) -> None:
        self.assertEqual(
            _runtime_build_id(
                {
                    "VERCEL": "1",
                    "DART_BUILD_ID": "stale-release",
                    "VERCEL_GIT_COMMIT_SHA": "b" * 40,
                },
                frozen=False,
                executable=Path("missing.exe"),
            ),
            "git-bbbbbbbbbbbb",
        )

    def test_vercel_commit_is_exposed_as_bounded_release_identity(self) -> None:
        self.assertEqual(
            _runtime_build_id(
                {"VERCEL_GIT_COMMIT_SHA": "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678"},
                frozen=False,
                executable=Path("missing.exe"),
            ),
            "git-a1b2c3d4e5f6",
        )

    def test_untrusted_commit_value_falls_back_to_source(self) -> None:
        self.assertEqual(
            _runtime_build_id(
                {"VERCEL_GIT_COMMIT_SHA": "not-a-commit;token=secret"},
                frozen=False,
                executable=Path("missing.exe"),
            ),
            "source",
        )


if __name__ == "__main__":
    unittest.main()
