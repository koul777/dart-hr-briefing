from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tools.release_preflight import (
    ReleaseGateError,
    build_release_manifest,
    collect_release_inputs,
    validate_executable_freshness,
    validate_standard_deployment,
)


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        files = {
            ".python-version": "3.12\n",
            "DARTStructure.spec": "# spec\n",
            "HR_BRIEFING_RULES.md": "rules\n",
            "pyproject.toml": (
                "[tool.setuptools]\n"
                "packages = [\"api\"]\n"
                "py-modules = [\"server\"]\n"
            ),
            "uv.lock": "version = 1\n",
            "server.py": "APP = True\n",
            "api/__init__.py": "",
            "static/index.html": "<html></html>\n",
            "schemas/schema.json": "{}\n",
            "seed/sample.json": "{}\n",
            "dist/DARTStructure.exe": "binary\n",
        }
        for relative, content in files.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_prebuilt_deployment_is_forbidden_even_without_cached_output(self) -> None:
        with self.assertRaisesRegex(ReleaseGateError, "prebuilt_deploy_forbidden"):
            validate_standard_deployment(self.root, "prebuilt")

    def test_standard_deployment_ignores_but_reports_stale_prebuilt_output(self) -> None:
        output = self.root / ".vercel" / "output"
        output.mkdir(parents=True)

        self.assertTrue(validate_standard_deployment(self.root, "standard"))

    def test_executable_mtime_must_cover_all_release_inputs(self) -> None:
        executable = self.root / "dist" / "DARTStructure.exe"
        source = self.root / "server.py"
        for release_input in collect_release_inputs(self.root):
            os.utime(release_input, ns=(1_000_000_000, 1_000_000_000))
        os.utime(executable, ns=(2_000_000_000, 2_000_000_000))
        summary = validate_executable_freshness(
            self.root,
            executable,
            tolerance_seconds=0,
        )
        self.assertEqual(summary["executable"], "dist/DARTStructure.exe")

        os.utime(source, ns=(3_000_000_000, 3_000_000_000))
        with self.assertRaisesRegex(ReleaseGateError, "release_executable_stale"):
            validate_executable_freshness(
                self.root,
                executable,
                tolerance_seconds=0,
            )

    def test_manifest_is_deterministic_and_binds_commit_source_and_executable(self) -> None:
        first = build_release_manifest(
            self.root,
            "dist/DARTStructure.exe",
            commit_sha="A" * 40,
        )
        second = build_release_manifest(
            self.root,
            "dist/DARTStructure.exe",
            commit_sha="a" * 40,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["source_commit_build_id"], "git-aaaaaaaaaaaa")
        self.assertEqual(
            first["build_id"],
            f"sha256-{first['executable']['sha256'][:12]}",
        )
        self.assertEqual(first["commit_sha"], "a" * 40)
        self.assertEqual(first["executable"]["path"], "dist/DARTStructure.exe")
        self.assertEqual(len(first["executable"]["sha256"]), 64)
        source_paths = {item["path"] for item in first["sources"]}
        self.assertTrue(
            {".python-version", "static/index.html", "uv.lock"}.issubset(source_paths)
        )


if __name__ == "__main__":
    unittest.main()
