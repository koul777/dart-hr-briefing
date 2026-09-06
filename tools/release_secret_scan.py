#!/usr/bin/env python3
"""Scan release source and binary artifacts for release-blocking credentials.

The report intentionally contains only file locations, line numbers, and rule
identifiers. Matched values are never returned or printed.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from re import Pattern

BINARY_SUFFIXES = {
    ".7z",
    ".avi",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pptx",
    ".pyc",
    ".webm",
    ".webp",
    ".zip",
}
ALLOWED_DOTENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}
TEST_FIXTURE_PREFIXES = ("test_", "tests/")
TEST_FIXTURE_PARTS = {"fixture", "fixtures", "test", "tests"}
SYNTHETIC_MARKERS = {
    "browser",
    "contract",
    "deployment",
    "dummy",
    "dotenv",
    "fake",
    "fixture",
    "gateway",
    "history",
    "placeholder",
    "redteam",
    "sample",
    "test",
}
SHORT_SYNTHETIC_VALUES = {"secret-key", "secret-value"}
SYNTHETIC_CONTEXT_MARKERS = {
    "browser",
    "contract",
    "deployment",
    "dotenv",
    "gateway",
    "header",
    "history",
    "key",
    "provider",
    "request",
    "secret",
    "value",
}
DOCUMENT_PLACEHOLDER_MARKERS = {
    "<your",
    "changeme",
    "example",
    "placeholder",
    "replace-me",
    "your_",
    "발급받은",
    "입력",
}
MAX_VERCEL_RUNTIME_BYTES = 6 * 1024 * 1024
MAX_VERCEL_SINGLE_FILE_BYTES = 2 * 1024 * 1024
SENSITIVE_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "CLAUDE_MCP_GATEWAY_TOKEN",
    "DART_OPERATOR_AI_TOKEN",
    "OPENAI_API_KEY",
    "OPENDART_API_KEY",
}


@dataclass(frozen=True)
class SecretRule:
    rule_id: str
    pattern: Pattern[str]
    value_group: int = 1


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str


@dataclass(frozen=True)
class ScanReport:
    tracked_files: int
    scanned_text_files: int
    skipped_binary_files: int
    vercel_candidate_files: int
    vercel_candidate_bytes: int
    scanned_artifact_files: int
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


SECRET_RULES = (
    SecretRule(
        "openai_api_key",
        re.compile(r"(?<![A-Za-z0-9])((?:sk-(?:proj-|svcacct-)?)[A-Za-z0-9_-]{16,})"),
    ),
    SecretRule(
        "opendart_api_key",
        re.compile(
            r"(?i)(?:^|[\"'])OPENDART_API_KEY[\"']?\s*[:=]\s*[\"']?"
            r"([^\s\"',#}]{8,})"
        ),
    ),
    SecretRule(
        "anthropic_api_key",
        re.compile(
            r"(?i)(?:^|[\"'])ANTHROPIC_API_KEY[\"']?\s*[:=]\s*[\"']?"
            r"([^\s\"',#}]{16,})"
        ),
    ),
    SecretRule(
        "operator_token",
        re.compile(
            r"(?i)(?:^|[\"'])(?:DART_OPERATOR_AI_TOKEN|X-DART-Operator-Token)"
            r"[\"']?\s*[:=]\s*[\"']?([^\s\"',#}]{12,})"
        ),
    ),
    SecretRule(
        "mcp_token",
        re.compile(
            r"(?i)(?:^|[\"'])CLAUDE_MCP_GATEWAY_TOKEN[\"']?\s*[:=]\s*[\"']?"
            r"([^\s\"',#}]{12,})"
        ),
    ),
    SecretRule(
        "credential_url_query",
        re.compile(r"(?i)[?&](?:crtfc_key|api_key|apikey)=([^&#\s\"']{8,})"),
    ),
    SecretRule(
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{20,})"),
    ),
    SecretRule(
        "deployment_token",
        re.compile(
            r"(?i)(?:^|[\"'])(?:GITHUB_TOKEN|GH_TOKEN|VERCEL_TOKEN)"
            r"[\"']?\s*[:=]\s*[\"']?([^\s\"',#}]{16,})"
        ),
    ),
    SecretRule(
        "github_personal_access_token",
        re.compile(r"(?<![A-Za-z0-9])((?:ghp_|github_pat_)[A-Za-z0-9_]{20,})"),
    ),
    SecretRule(
        "private_key_material",
        re.compile(
            r"(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
            re.IGNORECASE,
        ),
    ),
)

BINARY_SECRET_RULES = (
    (
        "openai_api_key",
        re.compile(rb"(?<![A-Za-z0-9])(?:sk-(?:proj-|svcacct-)?)[A-Za-z0-9_-]{16,}"),
    ),
    (
        "opendart_api_key",
        re.compile(
            rb"(?i)(?<![A-Za-z0-9_])OPENDART_API_KEY[\"']?\s*[:=]\s*"
            rb"[\"']?[^\s\"',#}]{8,}"
        ),
    ),
    (
        "anthropic_api_key",
        re.compile(
            rb"(?i)(?<![A-Za-z0-9_])ANTHROPIC_API_KEY[\"']?\s*[:=]\s*"
            rb"[\"']?[^\s\"',#}]{16,}"
        ),
    ),
    (
        "operator_token",
        re.compile(
            rb"(?i)(?<![A-Za-z0-9_])(?:DART_OPERATOR_AI_TOKEN|X-DART-Operator-Token)"
            rb"[\"']?\s*[:=]\s*[\"']?[^\s\"',#}]{12,}"
        ),
    ),
    (
        "mcp_token",
        re.compile(
            rb"(?i)(?<![A-Za-z0-9_])CLAUDE_MCP_GATEWAY_TOKEN[\"']?\s*[:=]\s*"
            rb"[\"']?[^\s\"',#}]{12,}"
        ),
    ),
    (
        "credential_url_query",
        re.compile(rb"(?i)[?&](?:crtfc_key|api_key|apikey)=[^&#\s\"']{8,}"),
    ),
    (
        "bearer_token",
        re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "deployment_token",
        re.compile(
            rb"(?i)(?<![A-Za-z0-9_])(?:GITHUB_TOKEN|GH_TOKEN|VERCEL_TOKEN)"
            rb"[\"']?\s*[:=]\s*[\"']?[^\s\"',#}]{16,}"
        ),
    ),
    (
        "github_personal_access_token",
        re.compile(rb"(?<![A-Za-z0-9])(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    ),
    (
        "private_key_material",
        re.compile(
            rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
)


class SecretScanError(RuntimeError):
    """Raised when a repository cannot be scanned safely."""


def _git_tracked_files(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SecretScanError("unable to enumerate Git-tracked files") from exc
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def _vercel_ignore_patterns(root: Path) -> list[str]:
    ignore_file = root / ".vercelignore"
    if not ignore_file.is_file():
        return []
    try:
        lines = ignore_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SecretScanError("unable to read Vercel ignore rules") from exc
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _is_vercel_ignored(relative_path: str, patterns: Sequence[str]) -> bool:
    normalized = relative_path.replace("\\", "/").rstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    name = normalized.rsplit("/", 1)[-1]
    ignored = False
    for raw_pattern in patterns:
        negated = raw_pattern.startswith("!")
        pattern = raw_pattern[1:] if negated else raw_pattern
        pattern = pattern.lstrip("/")
        directory_pattern = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        matched = (
            (
                directory_pattern
                and (
                    normalized == pattern
                    or (not negated and normalized.startswith(f"{pattern}/"))
                )
            )
            or fnmatch.fnmatchcase(normalized, pattern)
            or ("/" not in pattern and fnmatch.fnmatchcase(name, pattern))
        )
        if matched:
            ignored = not negated
    return ignored


def _may_include_vercel_descendant(
    relative_directory: str,
    patterns: Sequence[str],
) -> bool:
    normalized = relative_directory.replace("\\", "/").strip("/")
    prefix = f"{normalized}/" if normalized else ""
    return any(
        raw_pattern.startswith("!")
        and raw_pattern[1:].lstrip("/").rstrip("/").startswith(prefix)
        for raw_pattern in patterns
    )


def _vercel_candidates(root: Path, patterns: Sequence[str]) -> list[tuple[str, Path]]:
    if not patterns:
        return []
    candidates: list[tuple[str, Path]] = []
    for directory, child_directories, filenames in os.walk(root):
        current = Path(directory)
        kept_directories: list[str] = []
        for name in child_directories:
            relative = (current / name).relative_to(root).as_posix()
            if not _is_vercel_ignored(
                relative, patterns
            ) or _may_include_vercel_descendant(relative, patterns):
                kept_directories.append(name)
        child_directories[:] = kept_directories
        for name in filenames:
            target = current / name
            relative = target.relative_to(root).as_posix()
            if not _is_vercel_ignored(relative, patterns):
                candidates.append((relative, target))
    return sorted(candidates, key=lambda item: item[0].casefold())


def _is_tracked_dotenv(relative_path: str) -> bool:
    name = Path(relative_path).name
    return name == ".env" or (
        name.startswith(".env.") and name not in ALLOWED_DOTENV_TEMPLATES
    )


def _is_test_or_fixture(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").casefold()
    parts = set(normalized.split("/"))
    name = normalized.rsplit("/", 1)[-1]
    return (
        name.startswith(TEST_FIXTURE_PREFIXES[0])
        or normalized.startswith((TEST_FIXTURE_PREFIXES[1], "tools/qa_"))
        or bool(parts & TEST_FIXTURE_PARTS)
    )


def _is_obviously_synthetic(relative_path: str, value: str) -> bool:
    lowered = value.casefold()
    if "{" in value or "$" in value:
        return True
    stripped = lowered.strip().strip("\"'")
    if any(
        stripped == marker
        or stripped.startswith((f"{marker}-", f"{marker}_"))
        for marker in DOCUMENT_PLACEHOLDER_MARKERS
    ):
        return True
    if not _is_test_or_fixture(relative_path):
        return False
    if stripped in SHORT_SYNTHETIC_VALUES:
        return True
    tokens = set(re.findall(r"[a-z가-힣]+", lowered))
    if tokens & {"live", "prod", "production"}:
        return False
    if {"provider", "secret"}.issubset(tokens) or {
        "header",
        "request",
        "secret",
    }.issubset(tokens):
        return True
    if tokens & SYNTHETIC_MARKERS:
        return True
    if len(tokens & SYNTHETIC_CONTEXT_MARKERS) >= 2:
        return True
    repeated = lowered.strip("-_.~")
    return bool(repeated) and len(set(repeated)) <= 2


def _read_release_text(path: Path) -> str | None:
    if path.suffix.casefold() in BINARY_SUFFIXES or path.is_symlink():
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SecretScanError("unable to read a release file") from exc
    if b"\0" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_repository(root: Path | str) -> ScanReport:
    repository = Path(root).resolve()
    tracked = _git_tracked_files(repository)
    tracked_set = set(tracked)
    patterns = _vercel_ignore_patterns(repository)
    candidate_items = _vercel_candidates(repository, patterns)
    candidate_paths = {relative for relative, _target in candidate_items}
    findings: list[Finding] = []
    scanned = 0
    skipped = 0
    candidate_bytes = 0
    for relative_path, candidate in candidate_items:
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(repository)
        except ValueError as exc:
            raise SecretScanError("Vercel candidate escapes the repository") from exc
        size = resolved_candidate.stat().st_size
        candidate_bytes += size
        if size > MAX_VERCEL_SINGLE_FILE_BYTES:
            findings.append(
                Finding(relative_path, 0, "vercel_single_file_too_large")
            )
    if candidate_bytes > MAX_VERCEL_RUNTIME_BYTES:
        findings.append(Finding(".vercelignore", 0, "vercel_total_too_large"))

    for relative_path in sorted(tracked_set | candidate_paths, key=str.casefold):
        if relative_path in tracked_set and _is_tracked_dotenv(relative_path):
            findings.append(Finding(relative_path, 0, "tracked_dotenv"))
        target = (repository / relative_path).resolve()
        try:
            target.relative_to(repository)
        except ValueError as exc:
            raise SecretScanError("tracked path escapes the repository") from exc
        if not target.exists():
            continue
        text = _read_release_text(target)
        if text is None:
            skipped += 1
            continue
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in SECRET_RULES:
                for match in rule.pattern.finditer(line):
                    value = match.group(rule.value_group)
                    if not _is_obviously_synthetic(relative_path, value):
                        findings.append(
                            Finding(relative_path, line_number, rule.rule_id)
                        )
    unique_findings = tuple(sorted(
        set(findings),
        key=lambda item: (item.path.casefold(), item.line, item.rule_id),
    ))
    return ScanReport(
        len(tracked),
        scanned,
        skipped,
        len(candidate_items),
        candidate_bytes,
        0,
        unique_findings,
    )


def _known_secret_values(root: Path) -> tuple[bytes, ...]:
    values: set[bytes] = set()
    for key in SENSITIVE_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if len(value) >= 8:
            values.add(value.encode("utf-8"))

    dotenv = root / ".env"
    if dotenv.is_file():
        try:
            lines = dotenv.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise SecretScanError("unable to read local credential values") from exc
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            rendered = value.strip().strip("\"'")
            if key.strip() in SENSITIVE_ENV_KEYS and len(rendered) >= 8:
                values.add(rendered.encode("utf-8"))
    return tuple(sorted(values))


def _artifact_display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _scan_binary_artifact(
    root: Path,
    artifact: Path,
    known_values: Sequence[bytes],
) -> tuple[Finding, ...]:
    target = artifact if artifact.is_absolute() else root / artifact
    target = target.resolve()
    if not target.is_file():
        raise SecretScanError("binary artifact is missing or is not a file")
    display_path = _artifact_display_path(root, target)
    rule_ids: set[str] = set()
    overlap = max((len(value) - 1 for value in known_values), default=0)
    overlap = max(overlap, 4096)
    previous = b""
    try:
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                combined = previous + chunk
                for rule_id, pattern in BINARY_SECRET_RULES:
                    if rule_id not in rule_ids and pattern.search(combined):
                        rule_ids.add(rule_id)
                if any(value in combined for value in known_values):
                    rule_ids.add("known_secret_value")
                previous = combined[-overlap:]
    except OSError as exc:
        raise SecretScanError("unable to read binary artifact") from exc
    return tuple(Finding(display_path, 0, rule_id) for rule_id in sorted(rule_ids))


def scan_release(
    root: Path | str,
    binary_artifacts: Sequence[Path | str] = (),
) -> ScanReport:
    repository = Path(root).resolve()
    report = scan_repository(repository)
    known_values = _known_secret_values(repository)
    artifact_findings: list[Finding] = []
    for artifact in binary_artifacts:
        artifact_findings.extend(
            _scan_binary_artifact(repository, Path(artifact), known_values)
        )
    findings = tuple(
        sorted(
            {*report.findings, *artifact_findings},
            key=lambda item: (item.path.casefold(), item.line, item.rule_id),
        )
    )
    return ScanReport(
        report.tracked_files,
        report.scanned_text_files,
        report.skipped_binary_files,
        report.vercel_candidate_files,
        report.vercel_candidate_bytes,
        len(binary_artifacts),
        findings,
    )


def format_report(report: ScanReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        (
            f"{status} tracked={report.tracked_files} "
            f"scanned={report.scanned_text_files} "
            f"skipped_binary={report.skipped_binary_files} "
            f"vercel_candidates={report.vercel_candidate_files} "
            f"vercel_bytes={report.vercel_candidate_bytes} "
            f"artifacts={report.scanned_artifact_files} findings={len(report.findings)}"
        )
    ]
    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        lines.append(f"- {location} rule={finding.rule_id}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan release source and binaries without printing secret values."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--binary",
        action="append",
        default=[],
        type=Path,
        help="Binary release artifact to scan; may be repeated.",
    )
    args = parser.parse_args(argv)
    try:
        report = scan_release(args.root, args.binary)
    except SecretScanError:
        print("ERROR release secret scan could not be completed", file=sys.stderr)
        return 2
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
