from __future__ import annotations

import unittest
from pathlib import Path

from tools.repository_size_contract import (
    MAX_CANDIDATE_FILE_BYTES,
    MAX_CANDIDATE_TOTAL_BYTES,
    evaluate_entries,
    evaluate_repository,
)

ROOT = Path(__file__).resolve().parent


class RepositorySizeContractTests(unittest.TestCase):
    def test_current_commit_candidates_stay_within_release_budget(self) -> None:
        report = evaluate_repository(ROOT)

        self.assertTrue(report.passed, report.findings)
        self.assertLessEqual(report.candidate_bytes, MAX_CANDIDATE_TOTAL_BYTES)

    def test_oversized_untracked_style_file_fails_closed(self) -> None:
        report = evaluate_entries(
            [("unexpected-export.bin", MAX_CANDIDATE_FILE_BYTES + 1)]
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "candidate_file_too_large",
            {finding.rule_id for finding in report.findings},
        )

    def test_generated_directories_and_aggregate_bloat_are_blocked(self) -> None:
        report = evaluate_entries(
            [
                ("reports/local-build/output.dat", MAX_CANDIDATE_FILE_BYTES),
                ("docs/another.dat", MAX_CANDIDATE_TOTAL_BYTES),
            ]
        )

        self.assertEqual(
            {finding.rule_id for finding in report.findings},
            {
                "candidate_file_too_large",
                "candidate_total_too_large",
                "generated_path_in_commit_candidates",
            },
        )

    def test_gitignore_covers_known_heavy_local_artifacts(self) -> None:
        patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
        self.assertTrue(
            {
                "/reports/*/",
                ".venv/",
                "node_modules/",
                "*.bin",
                "*.zip",
                "*.7z",
                "*.pptx",
                "*.exe",
                "/dist/*.release.json",
            }.issubset(patterns)
        )


if __name__ == "__main__":
    unittest.main()
