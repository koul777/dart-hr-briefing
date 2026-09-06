"""Create a deterministic SHA-256 manifest for release and audit artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = (
    ROOT / "agent_orchestration.py",
    ROOT / "analysis_contract.py",
    ROOT / "classroom_mode.py",
    ROOT / "runtime_controls.py",
    ROOT / "schemas" / "workforce_orchestration_v2.schema.json",
    ROOT / "seed" / "classroom_workforce_2024_11011.json",
    ROOT / "fixtures" / "workforce" / "representative_2024_11011.json",
    ROOT / "fixtures" / "workforce" / "edge_cases_2024_11011.json",
    ROOT / "orchestration.workflow.json",
    ROOT / "orchestration-dart-claude.html",
    ROOT / "reports" / "ai_agent_orchestration_v2_20260830.md",
    ROOT / "dist" / "DARTStructure.exe",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_matching_artifact(root: Path, pattern: str) -> Path | None:
    matches = sorted(
        (root / "reports" / "overnight_sessions").glob(pattern),
        key=lambda path: (path.stat().st_mtime_ns, path.as_posix()),
    )
    return matches[-1] if matches else None


def _read_latest_candidate_executable(root: Path) -> Path | None:
    session_dir = root / "reports" / "overnight_sessions"
    latest_candidate_marker = session_dir / "latest-candidate-build-path.txt"
    if not latest_candidate_marker.is_file():
        return None
    build_root = Path(latest_candidate_marker.read_text(encoding="utf-8").strip())
    if not build_root.is_absolute():
        build_root = (root / build_root).resolve()
    return build_root / "dist" / "DARTStructure.exe"


def _latest_smoke_for_build(root: Path, executable: Path | None) -> Path | None:
    session_dir = root / "reports" / "overnight_sessions"
    smoke_candidates = (
        *session_dir.glob("packaged-runtime-smoke-*.json"),
        *session_dir.glob("packaged-smoke-*.json"),
        *session_dir.glob("smoke-final-*.json"),
        *session_dir.glob("smoke-release-*.json"),
    )
    if executable is None:
        matches = sorted(
            smoke_candidates,
            key=lambda path: (path.stat().st_mtime_ns, path.as_posix()),
        )
        return matches[-1] if matches else None
    matches: list[Path] = []
    for candidate in smoke_candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if Path(str(payload.get("build_path") or "")).resolve() == executable.resolve():
            matches.append(candidate)
    if not matches:
        return None
    matches.sort(key=lambda path: (path.stat().st_mtime_ns, path.as_posix()))
    return matches[-1]


def collect_session_artifacts(*, root: Path = ROOT) -> tuple[Path, ...]:
    artifacts: list[Path] = []
    executable = _read_latest_candidate_executable(root)
    if executable is not None:
        artifacts.append(executable)
    for patterns in (
        ("orchestration-benchmark-*.json", "benchmark-*.json"),
        ("coverage-*.json",),
        ("browser-qa-*.json",),
        ("pip-audit-*.json",),
        ("sbom-*.json",),
        ("runtime-audit-*.md",),
    ):
        candidates = [
            candidate
            for pattern in patterns
            for candidate in (root / "reports" / "overnight_sessions").glob(pattern)
        ]
        latest = max(
            candidates,
            key=lambda path: (path.stat().st_mtime_ns, path.as_posix()),
            default=None,
        )
        if latest is not None:
            artifacts.append(latest)
    smoke = _latest_smoke_for_build(root, executable)
    if smoke is not None:
        artifacts.append(smoke)
    return tuple(artifacts)


def build_manifest(paths: Sequence[Path], *, root: Path = ROOT) -> dict:
    resolved_root = root.resolve()
    artifacts = []
    seen: set[str] = set()
    for candidate in paths:
        path = candidate if candidate.is_absolute() else resolved_root / candidate
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"artifact must stay inside workspace: {candidate}") from exc
        if relative in seen:
            continue
        if not resolved.is_file():
            raise FileNotFoundError(f"artifact file not found: {relative}")
        seen.add(relative)
        artifacts.append({
            "path": relative,
            "bytes": resolved.stat().st_size,
            "sha256": _sha256(resolved),
        })
    artifacts.sort(key=lambda item: item["path"])
    return {
        "manifest_version": 1,
        "hash_algorithm": "SHA-256",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", type=Path, default=[])
    parser.add_argument("--include-session-artifacts", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = [
        *DEFAULT_ARTIFACTS,
        *(collect_session_artifacts() if args.include_session_artifacts else ()),
        *args.artifact,
    ]
    manifest = build_manifest(paths)
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
