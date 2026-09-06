from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.benchmark_orchestration import _percentile, run_benchmark


ROOT = Path(__file__).resolve().parent


class OrchestrationBenchmarkContractTests(unittest.TestCase):
    def test_percentile_and_argument_validation(self) -> None:
        self.assertEqual(_percentile([4.0, 1.0, 3.0, 2.0], 0.5), 3.0)
        with self.assertRaises(ValueError):
            _percentile([], 0.95)
        with self.assertRaises(ValueError):
            run_benchmark([], iterations=0, warmups=0, max_p95_ms=1, max_response_bytes=1)

    def test_synthetic_fixture_meets_generous_contract_budgets(self) -> None:
        document = json.loads(
            (ROOT / "fixtures" / "workforce" / "representative_2024_11011.json").read_text(
                encoding="utf-8"
            )
        )

        report = run_benchmark(
            document["observations"],
            iterations=2,
            warmups=0,
            max_p95_ms=5_000,
            max_response_bytes=1_000_000,
        )

        self.assertEqual(report["status"], "passed")
        self.assertTrue(all(report["checks"].values()))
        self.assertGreater(report["evidence_count"], 0)


if __name__ == "__main__":
    unittest.main()
