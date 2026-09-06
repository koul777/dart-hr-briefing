#!/usr/bin/env python3
"""Validate a clean Vercel Python function bundle without exposing values."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

EXPECTED_CONFIG_SUFFIX = (
    ".vercel",
    "output",
    "functions",
    "api",
    "index.func",
    ".vc-config.json",
)
EXPECTED_RUNTIME = "python3.12"
EXPECTED_HANDLER = "vc__handler__python.vc_handler"
EXPECTED_ARCHITECTURE = "x86_64"
EXPECTED_MAX_DURATION = 120
EXPECTED_ENVIRONMENT = {
    "PYTHONPATH": "_vendor",
    "PYTHONDONTWRITEBYTECODE": "1",
}
EXPECTED_CONFIG_KEYS = {
    "architecture",
    "environment",
    "filePathMap",
    "handler",
    "maxDuration",
    "runtime",
    "supportsResponseStreaming",
}
MAX_CONFIG_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_PATHS = 2_000
MAX_PATH_CHARACTERS = 1_024
EXPECTED_FIRST_ROUTE = {
    "src": "^/(.*)$",
    "dest": "/api/index?__route=$1",
}

ROOT_APP_PATHS = {
    ".python-version",
    "HR_BRIEFING_RULES.md",
    "agent_orchestration.py",
    "analysis_contract.py",
    "api/__init__.py",
    "api/index.py",
    "classroom_mode.py",
    "claude_mcp_adapter.py",
    "openai_responses_adapter.py",
    "orchestration_evaluation.py",
    "orchestrator.py",
    "pyproject.toml",
    "runtime_controls.py",
    "schemas/workforce_orchestration_v2.schema.json",
    "seed/classroom_workforce_2024_11011.json",
    "seed/corp_codes.json.gz",
    "server.py",
    "static/app.js",
    "static/index.html",
    "static/styles.css",
    "uv.lock",
    "vercel.json",
    "workforce_analytics.py",
}
BUILD_LIB_PATHS = {
    f"build/lib/{path}"
    for path in ROOT_APP_PATHS
    if path.endswith(".py") and not path.startswith("schemas/")
}
EGG_INFO_PATHS = {
    "dart_hr_briefing.egg-info/PKG-INFO",
    "dart_hr_briefing.egg-info/SOURCES.txt",
    "dart_hr_briefing.egg-info/dependency_links.txt",
    "dart_hr_briefing.egg-info/requires.txt",
    "dart_hr_briefing.egg-info/top_level.txt",
}
EXPECTED_APP_PATHS = ROOT_APP_PATHS | BUILD_LIB_PATHS | EGG_INFO_PATHS
REQUIRED_VENDOR_PREFIXES = (
    "_vendor/jsonschema/",
    "_vendor/vercel_runtime/",
)
VENDOR_SOURCE_PATTERN = re.compile(
    r"^\.vercel/python/\.venv/(?:Lib|lib/python3\.\d+)/site-packages/(?P<tail>.+)$"
)


class VercelBundleContractError(RuntimeError):
    """The built function bundle violates the release allowlist contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateJSONKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey
        result[key] = value
    return result


def _canonical_relative_path(raw_path: object) -> str:
    if not isinstance(raw_path, str):
        raise VercelBundleContractError("bundle_path_invalid")
    if (
        not raw_path
        or len(raw_path) > MAX_PATH_CHARACTERS
        or raw_path != raw_path.strip()
        or "\\" in raw_path
        or ":" in raw_path
        or any(ord(character) < 32 for character in raw_path)
    ):
        raise VercelBundleContractError("bundle_path_invalid")
    parts = raw_path.split("/")
    pure = PurePosixPath(raw_path)
    if (
        raw_path.startswith("/")
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or pure.as_posix() != raw_path
    ):
        raise VercelBundleContractError("bundle_path_invalid")
    return raw_path


def _project_root(config_path: Path) -> Path:
    absolute = config_path.absolute()
    if len(absolute.parts) < len(EXPECTED_CONFIG_SUFFIX):
        raise VercelBundleContractError("bundle_config_location_invalid")
    suffix = absolute.parts[-len(EXPECTED_CONFIG_SUFFIX) :]
    if tuple(suffix) != EXPECTED_CONFIG_SUFFIX:
        raise VercelBundleContractError("bundle_config_location_invalid")
    return absolute.parents[len(EXPECTED_CONFIG_SUFFIX) - 1]


def _reject_symlink_components(root: Path, path: Path) -> None:
    current = root
    if current.is_symlink():
        raise VercelBundleContractError("bundle_source_symlink")
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise VercelBundleContractError("bundle_source_outside_root") from exc
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise VercelBundleContractError("bundle_source_symlink")


def _validate_source_file(project_root: Path, relative_path: str) -> Path:
    target = project_root.joinpath(*relative_path.split("/"))
    _reject_symlink_components(project_root, target)
    try:
        resolved = target.resolve(strict=True)
        resolved.relative_to(project_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise VercelBundleContractError("bundle_source_missing_or_outside_root") from exc
    if not resolved.is_file():
        raise VercelBundleContractError("bundle_source_missing_or_outside_root")
    return resolved


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _validate_runtime(payload: Mapping[str, object]) -> None:
    if payload.get("runtime") != EXPECTED_RUNTIME:
        raise VercelBundleContractError("bundle_runtime_mismatch")
    if payload.get("handler") != EXPECTED_HANDLER:
        raise VercelBundleContractError("bundle_handler_mismatch")
    if payload.get("architecture") != EXPECTED_ARCHITECTURE:
        raise VercelBundleContractError("bundle_architecture_mismatch")
    if payload.get("maxDuration") != EXPECTED_MAX_DURATION:
        raise VercelBundleContractError("bundle_duration_mismatch")
    if payload.get("supportsResponseStreaming") is not True:
        raise VercelBundleContractError("bundle_streaming_contract_mismatch")
    if payload.get("environment") != EXPECTED_ENVIRONMENT:
        raise VercelBundleContractError("bundle_environment_mismatch")


def _validate_output_routes(project_root: Path) -> None:
    output_config = project_root / ".vercel" / "output" / "config.json"
    _reject_symlink_components(project_root, output_config)
    try:
        if output_config.stat().st_size > MAX_CONFIG_BYTES:
            raise VercelBundleContractError("bundle_route_config_too_large")
        payload = json.loads(
            output_config.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except VercelBundleContractError:
        raise
    except _DuplicateJSONKey as exc:
        raise VercelBundleContractError("bundle_route_config_duplicate_json_key") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VercelBundleContractError("bundle_route_config_unreadable") from exc
    if not isinstance(payload, Mapping) or payload.get("version") != 3:
        raise VercelBundleContractError("bundle_route_config_invalid")
    routes = payload.get("routes")
    if (
        not isinstance(routes, Sequence)
        or isinstance(routes, (str, bytes))
        or not routes
        or routes[0] != EXPECTED_FIRST_ROUTE
    ):
        raise VercelBundleContractError("bundle_route_precedence_mismatch")


def validate_bundle(config_path: Path | str) -> dict[str, object]:
    path = Path(config_path).absolute()
    project_root = _project_root(path)
    _reject_symlink_components(project_root, path)
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise VercelBundleContractError("bundle_config_too_large")
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except VercelBundleContractError:
        raise
    except _DuplicateJSONKey as exc:
        raise VercelBundleContractError("bundle_duplicate_json_key") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VercelBundleContractError("bundle_config_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise VercelBundleContractError("bundle_config_invalid")
    if set(payload) != EXPECTED_CONFIG_KEYS:
        raise VercelBundleContractError("bundle_config_keys_mismatch")
    _validate_output_routes(project_root)
    _validate_runtime(payload)
    file_map = payload.get("filePathMap")
    if not isinstance(file_map, Mapping):
        raise VercelBundleContractError("bundle_file_map_missing")
    if len(file_map) > MAX_BUNDLE_PATHS:
        raise VercelBundleContractError("bundle_file_map_too_large")

    logical_paths: set[str] = set()
    source_paths: set[str] = set()
    for raw_logical_path, raw_source_path in file_map.items():
        logical_path = _canonical_relative_path(raw_logical_path)
        source_path = _canonical_relative_path(raw_source_path)
        logical_casefold = logical_path.casefold()
        source_casefold = source_path.casefold()
        if logical_casefold in logical_paths or source_casefold in source_paths:
            raise VercelBundleContractError("bundle_path_collision")
        logical_paths.add(logical_casefold)
        source_paths.add(source_casefold)

        if logical_path.startswith("_vendor/"):
            match = VENDOR_SOURCE_PATTERN.fullmatch(source_path)
            if match is None or match.group("tail") != logical_path.removeprefix("_vendor/"):
                raise VercelBundleContractError("bundle_vendor_source_mismatch")
        elif logical_path not in EXPECTED_APP_PATHS:
            raise VercelBundleContractError("bundle_forbidden_app_path")
        elif source_path != logical_path:
            raise VercelBundleContractError("bundle_app_source_mismatch")

        source_file = _validate_source_file(project_root, source_path)
        if logical_path.startswith("build/lib/"):
            canonical_source = _validate_source_file(
                project_root,
                logical_path.removeprefix("build/lib/"),
            )
            if _digest(source_file) != _digest(canonical_source):
                raise VercelBundleContractError("bundle_build_copy_mismatch")

    actual_paths = {key for key in file_map if isinstance(key, str)}
    if not EXPECTED_APP_PATHS.issubset(actual_paths):
        raise VercelBundleContractError("bundle_required_path_missing")
    if not all(
        any(path.startswith(prefix) for path in actual_paths) for prefix in REQUIRED_VENDOR_PREFIXES
    ):
        raise VercelBundleContractError("bundle_required_vendor_missing")
    return {
        "ok": True,
        "runtime": payload["runtime"],
        "file_path_count": len(actual_paths),
        "app_path_count": len(EXPECTED_APP_PATHS),
        "vendor_path_count": len(actual_paths) - len(EXPECTED_APP_PATHS),
        "forbidden_app_paths": 0,
        "routing_contract": "function_first",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_bundle(args.config)
    except VercelBundleContractError as exc:
        print(f"FAIL vercel-bundle-contract reason={exc.code}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
