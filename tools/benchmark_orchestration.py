"""Repeatable latency and payload budget check for orchestration v2.

This benchmark is deliberately provider-free and network-free.  It measures the
deterministic fact, policy, evidence, and response-guard path against the public
synthetic fixture so results can be compared in CI or release preparation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "fixtures" / "workforce" / "representative_2024_11011.json"

try:
    from agent_orchestration import WorkforceAgentOrchestrator
    from orchestration_evaluation import evaluate_orchestration_result
except ModuleNotFoundError as exc:
    if exc.name not in {"agent_orchestration", "orchestration_evaluation"}:
        raise
    sys.path.insert(0, str(ROOT))
    from agent_orchestration import WorkforceAgentOrchestrator
    from orchestration_evaluation import evaluate_orchestration_result


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.5)))
    return ordered[rank]


def run_benchmark(
    observations: Sequence[dict[str, Any]],
    *,
    iterations: int,
    warmups: int,
    max_p95_ms: float,
    max_response_bytes: int,
) -> dict[str, Any]:
    if iterations < 1 or warmups < 0:
        raise ValueError("iterations must be positive and warmups must be non-negative")
    if max_p95_ms <= 0 or max_response_bytes < 1:
        raise ValueError("budgets must be positive")

    orchestrator = WorkforceAgentOrchestrator(provider=None)
    for _ in range(warmups):
        orchestrator.run(observations)

    durations_ms: list[float] = []
    run_ids: set[str] = set()
    response_sizes: list[int] = []
    evidence_counts: list[int] = []
    evaluation_statuses: set[str] = set()
    for _ in range(iterations):
        started = time.perf_counter()
        result = orchestrator.run(observations)
        durations_ms.append((time.perf_counter() - started) * 1000)
        serialized = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        run_ids.add(str(result.get("run_id") or ""))
        response_sizes.append(len(serialized))
        evidence_counts.append(len((result.get("evidence") or {}).get("ledger") or []))
        evaluation_statuses.add(str(evaluate_orchestration_result(result).get("status")))

    p95_ms = _percentile(durations_ms, 0.95)
    max_bytes = max(response_sizes)
    checks = {
        "stable_run_id": len(run_ids) == 1 and "" not in run_ids,
        "stable_evidence_count": len(set(evidence_counts)) == 1,
        "evaluation_not_failed": bool(evaluation_statuses)
        and evaluation_statuses <= {"passed", "warning"},
        "p95_within_budget": p95_ms <= max_p95_ms,
        "response_within_budget": max_bytes <= max_response_bytes,
    }
    return {
        "benchmark_version": 1,
        "provider_mode": "disabled",
        "network_mode": "disabled",
        "iterations": iterations,
        "warmups": warmups,
        "observation_count": len(observations),
        "latency_ms": {
            "min": round(min(durations_ms), 3),
            "p50": round(statistics.median(durations_ms), 3),
            "p95": round(p95_ms, 3),
            "max": round(max(durations_ms), 3),
            "mean": round(statistics.fmean(durations_ms), 3),
        },
        "response_bytes": {
            "min": min(response_sizes),
            "max": max_bytes,
        },
        "evidence_count": evidence_counts[0],
        "evaluation_statuses": sorted(evaluation_statuses),
        "budgets": {
            "max_p95_ms": max_p95_ms,
            "max_response_bytes": max_response_bytes,
        },
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=100.0)
    parser.add_argument("--max-response-bytes", type=int, default=1_000_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    document = json.loads(args.fixture.read_text(encoding="utf-8"))
    observations = document.get("observations")
    if not isinstance(observations, list):
        raise ValueError("fixture observations must be a list")
    report = run_benchmark(
        observations,
        iterations=args.iterations,
        warmups=args.warmups,
        max_p95_ms=args.max_p95_ms,
        max_response_bytes=args.max_response_bytes,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
