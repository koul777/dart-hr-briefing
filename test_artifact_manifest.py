from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tools.artifact_manifest import build_manifest, collect_session_artifacts


class ArtifactManifestTests(unittest.TestCase):
    def test_manifest_is_sorted_deduplicated_and_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.txt").write_text("beta", encoding="utf-8")
            (root / "a.txt").write_text("alpha", encoding="utf-8")

            manifest = build_manifest(
                [Path("b.txt"), Path("a.txt"), Path("b.txt")],
                root=root,
            )

        self.assertEqual(manifest["artifact_count"], 2)
        self.assertEqual(
            [item["path"] for item in manifest["artifacts"]],
            ["a.txt", "b.txt"],
        )
        self.assertEqual(
            manifest["artifacts"][0]["sha256"],
            "8ed3f6ad685b959ead7022518e1af76cd816f8e8ec7ccdda1ed4018e8f2223f8",
        )

    def test_manifest_rejects_missing_and_outside_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            outside = Path(directory) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")

            with self.assertRaises(ValueError):
                build_manifest([outside], root=root)
            with self.assertRaises(FileNotFoundError):
                build_manifest([Path("missing.txt")], root=root)

    def test_collect_session_artifacts_uses_latest_candidate_and_latest_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_dir = root / "reports" / "overnight_sessions"
            session_dir.mkdir(parents=True)
            build_root = session_dir / "build-candidate-20260830-1933"
            (build_root / "dist").mkdir(parents=True)
            executable = build_root / "dist" / "DARTStructure.exe"
            executable.write_text("binary", encoding="utf-8")
            (session_dir / "latest-candidate-build-path.txt").write_text(
                str(build_root),
                encoding="utf-8",
            )
            old_benchmark = session_dir / "orchestration-benchmark-20260830-1919.json"
            old_benchmark.write_text("{}", encoding="utf-8")
            legacy_benchmark = session_dir / "orchestration-benchmark-20260830-1933.json"
            legacy_benchmark.write_text("{}", encoding="utf-8")
            latest_benchmark = session_dir / "benchmark-hr-max-final-release.json"
            latest_benchmark.write_text("{}", encoding="utf-8")
            os.utime(old_benchmark, ns=(1_000_000_000, 1_000_000_000))
            os.utime(legacy_benchmark, ns=(1_500_000_000, 1_500_000_000))
            os.utime(latest_benchmark, ns=(2_000_000_000, 2_000_000_000))
            coverage = session_dir / "coverage-hr-max-final-release.json"
            coverage.write_text("{}", encoding="utf-8")
            browser_qa = session_dir / "browser-qa-four-company-final.json"
            browser_qa.write_text("{}", encoding="utf-8")
            dependency_audit = session_dir / "pip-audit-final.json"
            dependency_audit.write_text("{}", encoding="utf-8")
            sbom = session_dir / "sbom-cyclonedx-final.json"
            sbom.write_text("{}", encoding="utf-8")
            smoke = session_dir / "packaged-smoke-hr-max-final.json"
            smoke.write_text(
                '{"build_path": "' + str(executable).replace("\\", "\\\\") + '"}',
                encoding="utf-8",
            )
            latest_smoke = session_dir / "smoke-final-candidate.json"
            latest_smoke.write_text(
                '{"build_path": "' + str(executable).replace("\\", "\\\\") + '"}',
                encoding="utf-8",
            )
            os.utime(smoke, ns=(1_000_000_000, 1_000_000_000))
            os.utime(latest_smoke, ns=(2_000_000_000, 2_000_000_000))
            unrelated_smoke = session_dir / "packaged-runtime-smoke-20260830-2049.json"
            unrelated_smoke.write_text(
                '{"build_path": "C:\\\\elsewhere\\\\other.exe"}',
                encoding="utf-8",
            )
            audit = session_dir / "runtime-audit-20260830-1928.md"
            audit.write_text("# audit", encoding="utf-8")

            artifacts = collect_session_artifacts(root=root)

        self.assertEqual(
            artifacts,
            (
                executable,
                latest_benchmark,
                coverage,
                browser_qa,
                dependency_audit,
                sbom,
                audit,
                latest_smoke,
            ),
        )


if __name__ == "__main__":
    unittest.main()
