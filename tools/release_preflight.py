#!/usr/bin/env python3
"""Validate a standard release and create a content-addressed EXE manifest.

Repository policy deliberately forbids ``vercel deploy --prebuilt``.  A stale
``.vercel/output`` may remain on a developer machine, but it is never treated
as a release input by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_MTIME_TOLERANCE_SECONDS = 5.0
EXPLICIT_RELEASE_INPUTS = (
    ".python-version",
    "DARTStructure.spec",
    "HR_BRIEFING_RULES.md",
    "pyproject.toml",
    "uv.lock",
)
RELEASE_INPUT_DIRECTORIES = ("schemas", "seed", "static")


class ReleaseGateError(RuntimeError):
    """A release candidate violates a deterministic release contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside_root(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ReleaseGateError("path_outside_repository") from exc
    return resolved


def collect_release_inputs(root: Path | str) -> tuple[Path, ...]:
    """Return every source/configuration file that determines the frozen app."""

    repository = Path(root).resolve()
    project_path = repository / "pyproject.toml"
    try:
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))
        setuptools = project["tool"]["setuptools"]
        modules = tuple(str(name) for name in setuptools["py-modules"])
        packages = tuple(str(name) for name in setuptools["packages"])
    except (OSError, KeyError, tomllib.TOMLDecodeError, TypeError) as exc:
        raise ReleaseGateError("invalid_pyproject_release_manifest") from exc

    candidates = [repository / relative for relative in EXPLICIT_RELEASE_INPUTS]
    candidates.extend(repository / f"{name}.py" for name in modules)
    for package in packages:
        package_root = repository.joinpath(*package.split("."))
        candidates.extend(
            path
            for path in package_root.rglob("*")
            if path.is_file() and path.suffix == ".py"
        )
    for relative in RELEASE_INPUT_DIRECTORIES:
        directory = repository / relative
        candidates.extend(path for path in directory.rglob("*") if path.is_file())

    unique: dict[str, Path] = {}
    for candidate in candidates:
        resolved = _inside_root(repository, candidate)
        if not resolved.is_file():
            raise ReleaseGateError("release_input_missing")
        relative = resolved.relative_to(repository).as_posix()
        unique[relative] = resolved
    return tuple(unique[path] for path in sorted(unique, key=str.casefold))


def validate_standard_deployment(root: Path | str, deployment_mode: str) -> bool:
    """Reject prebuilt deploys and report whether an ignored stale output exists."""

    repository = Path(root).resolve()
    if deployment_mode != "standard":
        raise ReleaseGateError("prebuilt_deploy_forbidden")
    return (repository / ".vercel" / "output").exists()


def validate_executable_freshness(
    root: Path | str,
    executable: Path | str,
    *,
    tolerance_seconds: float = DEFAULT_MTIME_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    target = Path(executable)
    if not target.is_absolute():
        target = repository / target
    target = _inside_root(repository, target)
    if not target.is_file():
        raise ReleaseGateError("release_executable_missing")
    if tolerance_seconds < 0:
        raise ReleaseGateError("invalid_mtime_tolerance")

    inputs = collect_release_inputs(repository)
    newest = max(inputs, key=lambda path: path.stat().st_mtime_ns)
    tolerance_ns = int(tolerance_seconds * 1_000_000_000)
    if newest.stat().st_mtime_ns > target.stat().st_mtime_ns + tolerance_ns:
        raise ReleaseGateError("release_executable_stale")
    return {
        "executable": target.relative_to(repository).as_posix(),
        "executable_bytes": target.stat().st_size,
        "newest_input": newest.relative_to(repository).as_posix(),
        "input_count": len(inputs),
    }


def build_release_manifest(
    root: Path | str,
    executable: Path | str,
    *,
    commit_sha: str,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    normalized_commit = str(commit_sha).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{7,64}", normalized_commit):
        raise ReleaseGateError("invalid_release_commit_sha")

    target = Path(executable)
    if not target.is_absolute():
        target = repository / target
    target = _inside_root(repository, target)
    if not target.is_file():
        raise ReleaseGateError("release_executable_missing")

    source_items = []
    fingerprint = hashlib.sha256()
    for path in collect_release_inputs(repository):
        relative = path.relative_to(repository).as_posix()
        digest = _sha256(path)
        size = path.stat().st_size
        source_items.append({"path": relative, "bytes": size, "sha256": digest})
        fingerprint.update(relative.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(digest.encode("ascii"))
        fingerprint.update(b"\n")

    executable_sha256 = _sha256(target)
    return {
        "manifest_version": 1,
        "commit_sha": normalized_commit,
        "source_commit_build_id": f"git-{normalized_commit[:12]}",
        "build_id": f"sha256-{executable_sha256[:12]}",
        "source_fingerprint_sha256": fingerprint.hexdigest(),
        "executable": {
            "path": target.relative_to(repository).as_posix(),
            "bytes": target.stat().st_size,
            "sha256": executable_sha256,
        },
        "sources": source_items,
    }


def _write_manifest(root: Path, output: Path, manifest: dict[str, Any]) -> None:
    target = output if output.is_absolute() else root / output
    target = _inside_root(root, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--exe", type=Path, default=Path("dist/DARTStructure.exe"))
    parser.add_argument(
        "--deployment-mode",
        choices=("standard", "prebuilt"),
        default="standard",
    )
    parser.add_argument(
        "--mtime-tolerance-seconds",
        type=float,
        default=DEFAULT_MTIME_TOLERANCE_SECONDS,
    )
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        stale_prebuilt_present = validate_standard_deployment(root, args.deployment_mode)
        summary = validate_executable_freshness(
            root,
            args.exe,
            tolerance_seconds=args.mtime_tolerance_seconds,
        )
        if args.manifest_output:
            manifest = build_release_manifest(
                root,
                args.exe,
                commit_sha=args.commit_sha,
            )
            _write_manifest(root, args.manifest_output, manifest)
            summary["manifest"] = args.manifest_output.as_posix()
        summary.update({
            "ok": True,
            "deployment_mode": "standard",
            "stale_prebuilt_output_ignored": stale_prebuilt_present,
        })
    except ReleaseGateError as exc:
        print(f"FAIL release-preflight reason={exc.code}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
