#!/usr/bin/env python3
"""Fail closed when commit candidates contain oversized or generated artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_CANDIDATE_FILE_BYTES = 50 * 1024 * 1024
MAX_CANDIDATE_TOTAL_BYTES = 100 * 1024 * 1024
FORBIDDEN_PREFIXES = (
    ".venv/",
    ".vercel/",
    "build/",
    "env/",
    "node_modules/",
    "promo_video/.remotion/",
    "promo_video/node_modules/",
    "promo_video/out/",
    "reports/local-build/",
    "reports/overnight_sessions/",
    "training_deck/",
    "venv/",
    "video_work/",
)


@dataclass(frozen=True)
class SizeFinding:
    path: str
    rule_id: str


@dataclass(frozen=True)
class SizeReport:
    candidate_files: int
    candidate_bytes: int
    findings: tuple[SizeFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


class RepositorySizeError(RuntimeError):
    """Raised when Git candidates cannot be enumerated safely."""


def git_candidate_paths(root: Path) -> tuple[str, ...]:
    """Return tracked plus non-ignored untracked files without shell quoting."""

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RepositorySizeError("unable to enumerate Git candidates") from exc
    return tuple(
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in completed.stdout.split(b"\0")
        if item
    )


def evaluate_entries(
    entries: Sequence[tuple[str, int]],
    *,
    max_file_bytes: int = MAX_CANDIDATE_FILE_BYTES,
    max_total_bytes: int = MAX_CANDIDATE_TOTAL_BYTES,
) -> SizeReport:
    findings: set[SizeFinding] = set()
    total_bytes = 0
    for raw_path, raw_size in entries:
        path = raw_path.replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        path = path.lstrip("/")
        size = max(0, int(raw_size))
        total_bytes += size
        lowered = path.casefold()
        if any(lowered.startswith(prefix.casefold()) for prefix in FORBIDDEN_PREFIXES):
            findings.add(SizeFinding(path, "generated_path_in_commit_candidates"))
        if size > max_file_bytes:
            findings.add(SizeFinding(path, "candidate_file_too_large"))
    if total_bytes > max_total_bytes:
        findings.add(SizeFinding(".git/index", "candidate_total_too_large"))
    return SizeReport(
        candidate_files=len(entries),
        candidate_bytes=total_bytes,
        findings=tuple(sorted(findings, key=lambda item: (item.path.casefold(), item.rule_id))),
    )


def evaluate_repository(root: Path | str) -> SizeReport:
    repository = Path(root).resolve()
    entries: list[tuple[str, int]] = []
    for relative_path in git_candidate_paths(repository):
        target = repository / relative_path
        try:
            target.resolve().relative_to(repository)
        except ValueError as exc:
            raise RepositorySizeError("Git candidate escapes repository") from exc
        if not target.exists():
            continue
        try:
            size = target.lstat().st_size
        except OSError as exc:
            raise RepositorySizeError("unable to inspect Git candidate") from exc
        entries.append((relative_path, size))
    return evaluate_entries(entries)


def format_report(report: SizeReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"{status} candidates={report.candidate_files} bytes={report.candidate_bytes} "
        f"findings={len(report.findings)}"
    ]
    lines.extend(f"- {item.path} rule={item.rule_id}" for item in report.findings)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate tracked and non-ignored Git candidate sizes."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        report = evaluate_repository(args.root)
    except RepositorySizeError:
        print("ERROR repository size contract could not be completed", file=sys.stderr)
        return 2
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
