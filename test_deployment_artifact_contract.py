from __future__ import annotations

import ast
import fnmatch
import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.vercel_bundle_contract import (
    EXPECTED_APP_PATHS,
    EXPECTED_ARCHITECTURE,
    EXPECTED_ENVIRONMENT,
    EXPECTED_FIRST_ROUTE,
    EXPECTED_HANDLER,
    EXPECTED_MAX_DURATION,
    EXPECTED_RUNTIME,
    MAX_BUNDLE_PATHS,
    MAX_CONFIG_BYTES,
    VercelBundleContractError,
    validate_bundle,
)

ROOT = Path(__file__).resolve().parent
MAX_VERCEL_RUNTIME_BYTES = 6 * 1024 * 1024
MAX_VERCEL_SINGLE_FILE_BYTES = 2 * 1024 * 1024
MAX_FROZEN_EXECUTABLE_BYTES = 64 * 1024 * 1024
REQUIRED_VERCEL_FILES = {
    ".python-version",
    "HR_BRIEFING_RULES.md",
    "agent_orchestration.py",
    "analysis_contract.py",
    "api/__init__.py",
    "api/index.py",
    "claude_mcp_adapter.py",
    "classroom_mode.py",
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
REQUIRED_EXCLUDED_EXAMPLES = {
    ".env",
    ".env.production",
    ".venv/Lib/site-packages/package.py",
    "venv/bin/python",
    "env/Scripts/python.exe",
    "build/intermediate.bin",
    "data/corp_codes.json",
    "dist/DARTStructure.exe",
    "docs/assets/demo.mp4",
    "fixtures/private.json",
    "node_modules/package/index.js",
    "promo_video/out/original.mp4",
    "reports/local-build/audit.json",
    "tools/local-helper.py",
    "training_deck/source.pptx",
    "video_work/raw.mov",
    "credentials-production.json",
    "CLAUDE.md",
    "README.md",
    "DART_WORKFORCE_INTELLIGENCE_PLAN.md",
    "DART_WORKFORCE_INTELLIGENCE_RUNBOOK.md",
    "OpenDART_HR_Analytics_4시간_커리큘럼.md",
    "server-private.pem",
    "local.sqlite3",
    "debug.log",
    "untracked-1.1gb.bin",
    "surprise/untracked-1.1gb.bin",
}
ALLOWED_FROZEN_DATA_SOURCES = {
    "HR_BRIEFING_RULES.md",
    "schemas",
    "seed",
    "static",
}
ALLOWED_SEED_FILES = {
    "classroom_workforce_2024_11011.json",
    "corp_codes.json.gz",
}
SENSITIVE_ENV_KEYS = {
    "CLAUDE_MCP_GATEWAY_TOKEN",
    "DART_OPERATOR_AI_TOKEN",
    "OPENAI_API_KEY",
    "OPENDART_API_KEY",
}


def _write_bundle_fixture(root: Path) -> tuple[Path, dict[str, object]]:
    config = root / ".vercel" / "output" / "functions" / "api" / "index.func" / ".vc-config.json"
    config.parent.mkdir(parents=True)
    file_map = {path: path for path in EXPECTED_APP_PATHS}
    vendor_paths = {
        "_vendor/jsonschema/__init__.py": (
            ".vercel/python/.venv/Lib/site-packages/jsonschema/__init__.py"
        ),
        "_vendor/vercel_runtime/__init__.py": (
            ".vercel/python/.venv/Lib/site-packages/vercel_runtime/__init__.py"
        ),
    }
    file_map.update(vendor_paths)

    for relative in sorted(
        path for path in EXPECTED_APP_PATHS if not path.startswith("build/lib/")
    ):
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"fixture:{relative}\n", encoding="utf-8")
    for relative in sorted(path for path in EXPECTED_APP_PATHS if path.startswith("build/lib/")):
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        source = root.joinpath(*relative.removeprefix("build/lib/").split("/"))
        target.write_bytes(source.read_bytes())
    for relative in vendor_paths.values():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# fixture vendor\n", encoding="utf-8")

    payload: dict[str, object] = {
        "handler": EXPECTED_HANDLER,
        "runtime": EXPECTED_RUNTIME,
        "architecture": EXPECTED_ARCHITECTURE,
        "maxDuration": EXPECTED_MAX_DURATION,
        "environment": dict(EXPECTED_ENVIRONMENT),
        "supportsResponseStreaming": True,
        "filePathMap": file_map,
    }
    config.write_text(json.dumps(payload), encoding="utf-8")
    (root / ".vercel" / "output" / "config.json").write_text(
        json.dumps(
            {
                "version": 3,
                "routes": [
                    EXPECTED_FIRST_ROUTE,
                    {"handle": "filesystem"},
                ],
                "crons": [],
            }
        ),
        encoding="utf-8",
    )
    return config, payload


def _ignore_patterns() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _is_ignored(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/").rstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    name = normalized.rsplit("/", 1)[-1]
    ignored = False
    for raw_pattern in patterns:
        negated = raw_pattern.startswith("!")
        pattern = raw_pattern[1:] if negated else raw_pattern
        anchored = pattern.startswith("/")
        pattern = pattern.lstrip("/")
        directory_pattern = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        matched = (
            (
                directory_pattern
                and (
                    normalized == pattern or (not negated and normalized.startswith(f"{pattern}/"))
                )
            )
            or fnmatch.fnmatchcase(normalized, pattern)
            or (not anchored and "/" not in pattern and fnmatch.fnmatchcase(name, pattern))
        )
        if matched:
            ignored = not negated
    return ignored


def _may_include_descendant(relative_directory: str, patterns: list[str]) -> bool:
    normalized = relative_directory.replace("\\", "/").strip("/")
    prefix = f"{normalized}/" if normalized else ""
    return any(
        raw_pattern.startswith("!") and raw_pattern[1:].lstrip("/").rstrip("/").startswith(prefix)
        for raw_pattern in patterns
    )


def _working_tree_vercel_candidates(patterns: list[str]) -> list[Path]:
    candidates: list[Path] = []
    for directory, child_directories, filenames in os.walk(ROOT):
        current = Path(directory)
        kept_directories: list[str] = []
        for name in child_directories:
            relative = (current / name).relative_to(ROOT).as_posix()
            if not _is_ignored(relative, patterns) or _may_include_descendant(relative, patterns):
                kept_directories.append(name)
        child_directories[:] = kept_directories
        for name in filenames:
            target = current / name
            relative = target.relative_to(ROOT).as_posix()
            if not _is_ignored(relative, patterns):
                candidates.append(target)
    return sorted(candidates)


def _frozen_data_sources() -> set[str]:
    source = (ROOT / "DARTStructure.spec").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "Analysis":
            continue
        datas = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "datas"),
            None,
        )
        if not isinstance(datas, (ast.List, ast.Tuple)):
            raise AssertionError(  # noqa: TRY004 - this is a test contract assertion
                "PyInstaller datas must be a static list"
            )
        sources: set[str] = set()
        for item in datas.elts:
            if not isinstance(item, (ast.List, ast.Tuple)) or not item.elts:
                raise AssertionError("PyInstaller data entry must be a static tuple")
            value = item.elts[0]
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise AssertionError(  # noqa: TRY004 - this is a test contract assertion
                    "PyInstaller data source must be a string literal"
                )
            sources.add(value.value.replace("\\", "/"))
        return sources
    raise AssertionError("PyInstaller Analysis configuration is missing")


def _dotenv_secret_values() -> dict[str, bytes]:
    dotenv = ROOT / ".env"
    if not dotenv.is_file():
        return {}
    values: dict[str, bytes] = {}
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        rendered = value.strip().strip("\"'")
        if key in SENSITIVE_ENV_KEYS and len(rendered) >= 8:
            values[key] = rendered.encode("utf-8")
    return values


def _binary_contains(path: Path, needle: bytes) -> bool:
    overlap = max(0, len(needle) - 1)
    previous = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            combined = previous + chunk
            if needle in combined:
                return True
            previous = combined[-overlap:] if overlap else b""
    return False


class DeploymentArtifactContractTests(unittest.TestCase):
    def test_clean_vercel_bundle_contract_blocks_workspace_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            summary = validate_bundle(config)

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["app_path_count"], 40)
            self.assertEqual(summary["vendor_path_count"], 2)
            self.assertEqual(summary["routing_contract"], "function_first")

            payload["filePathMap"]["reports/private.json"] = "reports/private.json"
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_forbidden_app_path",
            ):
                validate_bundle(config)

    def test_vercel_bundle_rejects_noncanonical_or_forbidden_logical_paths(self) -> None:
        cases = {
            "/absolute.py": "bundle_path_invalid",
            "C:/absolute.py": "bundle_path_invalid",
            "C:drive-relative.py": "bundle_path_invalid",
            "../traversal.py": "bundle_path_invalid",
            "./server.py": "bundle_path_invalid",
            "static//app.js": "bundle_path_invalid",
            "server.py ": "bundle_path_invalid",
            "nested/.env": "bundle_forbidden_app_path",
            "Tools/release.py": "bundle_forbidden_app_path",
        }
        for logical_path, reason in cases.items():
            with (
                self.subTest(logical_path=logical_path),
                tempfile.TemporaryDirectory() as directory,
            ):
                config, payload = _write_bundle_fixture(Path(directory))
                payload["filePathMap"][logical_path] = logical_path
                config.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(VercelBundleContractError, reason):
                    validate_bundle(config)

    def test_vercel_bundle_rejects_source_redirection_and_vendor_aliases(self) -> None:
        cases = (
            ("server.py", ".env", "bundle_app_source_mismatch"),
            ("server.py", "../server.py", "bundle_path_invalid"),
            ("server.py", "C:/server.py", "bundle_path_invalid"),
            (
                "_vendor/jsonschema/__init__.py",
                ".vercel/python/.venv/Lib/site-packages/vercel_runtime/__init__.py",
                "bundle_vendor_source_mismatch",
            ),
        )
        for logical_path, source_path, reason in cases:
            with self.subTest(source_path=source_path), tempfile.TemporaryDirectory() as directory:
                config, payload = _write_bundle_fixture(Path(directory))
                payload["filePathMap"][logical_path] = source_path
                config.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(VercelBundleContractError, reason):
                    validate_bundle(config)

    def test_vercel_bundle_runtime_and_environment_are_exact(self) -> None:
        cases = (
            ("runtime", "python3.13", "bundle_runtime_mismatch"),
            ("handler", "api.index.handler", "bundle_handler_mismatch"),
            ("architecture", "arm64", "bundle_architecture_mismatch"),
            ("maxDuration", 121, "bundle_duration_mismatch"),
            ("supportsResponseStreaming", False, "bundle_streaming_contract_mismatch"),
            (
                "environment",
                {**EXPECTED_ENVIRONMENT, "OPENAI_API_KEY": "redacted"},
                "bundle_environment_mismatch",
            ),
        )
        for field, value, reason in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                config, payload = _write_bundle_fixture(Path(directory))
                payload[field] = value
                config.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(VercelBundleContractError, reason):
                    validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            payload["credential"] = "not-allowed-even-if-redacted"
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_config_keys_mismatch",
            ):
                validate_bundle(config)

    def test_vercel_bundle_requires_function_first_output_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _write_bundle_fixture(root)
            output_config = root / ".vercel" / "output" / "config.json"
            output_config.write_text(
                json.dumps(
                    {
                        "version": 3,
                        "routes": [
                            {"handle": "filesystem"},
                            EXPECTED_FIRST_ROUTE,
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_route_precedence_mismatch",
            ):
                validate_bundle(config)

    def test_vercel_bundle_rejects_duplicate_keys_collisions_and_oversized_maps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, _ = _write_bundle_fixture(Path(directory))
            config.write_text(
                '{"runtime":"python3.12","runtime":"python3.13"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_duplicate_json_key",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            payload["filePathMap"]["_vendor/JSONSCHEMA/__init__.py"] = (
                ".vercel/python/.venv/Lib/site-packages/JSONSCHEMA/__init__.py"
            )
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(VercelBundleContractError, "bundle_path_collision"):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            payload["filePathMap"] = {
                f"_vendor/package_{index}/module.py": (
                    f".vercel/python/.venv/Lib/site-packages/package_{index}/module.py"
                )
                for index in range(MAX_BUNDLE_PATHS + 1)
            }
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_file_map_too_large",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, _ = _write_bundle_fixture(Path(directory))
            config.write_bytes(b" " * (MAX_CONFIG_BYTES + 1))
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_config_too_large",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            payload["filePathMap"]["server.py"] = None
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(VercelBundleContractError, "bundle_path_invalid"):
                validate_bundle(config)

    def test_vercel_bundle_rejects_missing_paths_and_stale_build_copies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            del payload["filePathMap"]["server.py"]
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_required_path_missing",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            config, payload = _write_bundle_fixture(Path(directory))
            del payload["filePathMap"]["_vendor/vercel_runtime/__init__.py"]
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_required_vendor_missing",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _write_bundle_fixture(root)
            (root / "build" / "lib" / "server.py").write_text(
                "# stale copy\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_build_copy_mismatch",
            ):
                validate_bundle(config)

    def test_vercel_bundle_rejects_unexpected_location_and_symlinked_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".vc-config.json"
            config.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_config_location_invalid",
            ):
                validate_bundle(config)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _write_bundle_fixture(root)
            relative_parts = config.relative_to(root).parts
            wrong_case_config = root.joinpath(".VERCEL", *relative_parts[1:])
            with self.assertRaisesRegex(
                VercelBundleContractError,
                "bundle_config_location_invalid",
            ):
                validate_bundle(wrong_case_config)

        with tempfile.TemporaryDirectory() as directory:
            config, _ = _write_bundle_fixture(Path(directory))
            with (
                patch(
                    "pathlib.Path.is_symlink",
                    lambda candidate: candidate.name == "server.py",
                ),
                self.assertRaisesRegex(
                    VercelBundleContractError,
                    "bundle_source_symlink",
                ),
            ):
                validate_bundle(config)

    def test_vercel_ignore_and_function_exclusions_cover_local_artifacts(self) -> None:
        patterns = _ignore_patterns()
        for relative_path in REQUIRED_EXCLUDED_EXAMPLES:
            with self.subTest(relative_path=relative_path):
                self.assertTrue(_is_ignored(relative_path, patterns))

        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        function = config["functions"]["api/index.py"]
        excluded = function["excludeFiles"]
        self.assertLessEqual(len(excluded), 256)
        for fragment in (
            ".env*",
            "dist/**",
            "docs/**",
            "reports/**",
            "*.mp4",
            "*.pptx",
            "training_deck/**",
            "test_*.py",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, excluded)

    def test_required_vercel_files_exist_and_are_not_ignored(self) -> None:
        patterns = _ignore_patterns()
        for relative_path in REQUIRED_VERCEL_FILES:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())
                self.assertFalse(_is_ignored(relative_path, patterns))

    def test_vercel_allowlist_contains_all_declared_python_modules(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared_modules = {f"{name}.py" for name in project["tool"]["setuptools"]["py-modules"]}
        patterns = _ignore_patterns()

        self.assertTrue(declared_modules.issubset(REQUIRED_VERCEL_FILES))
        for relative_path in declared_modules:
            with self.subTest(relative_path=relative_path):
                self.assertFalse(_is_ignored(relative_path, patterns))

    def test_actual_working_tree_vercel_candidates_are_allowlisted_and_bounded(self) -> None:
        patterns = _ignore_patterns()
        candidates = _working_tree_vercel_candidates(patterns)
        relative_candidates = {path.relative_to(ROOT).as_posix() for path in candidates}
        total_bytes = sum(path.stat().st_size for path in candidates)
        largest_bytes = max((path.stat().st_size for path in candidates), default=0)

        self.assertEqual(relative_candidates, REQUIRED_VERCEL_FILES)
        for path in candidates:
            with self.subTest(candidate=path.relative_to(ROOT).as_posix()):
                self.assertFalse(path.is_symlink())
                path.resolve(strict=True).relative_to(ROOT.resolve(strict=True))
        self.assertLessEqual(total_bytes, MAX_VERCEL_RUNTIME_BYTES)
        self.assertLessEqual(largest_bytes, MAX_VERCEL_SINGLE_FILE_BYTES)

    def test_vercel_upload_is_default_deny_with_explicit_runtime_exceptions(self) -> None:
        patterns = _ignore_patterns()
        self.assertEqual(patterns[0], "/*")
        self.assertTrue(_is_ignored("untracked-1.1gb.bin", patterns))
        self.assertTrue(_is_ignored("unexpected/path/payload.bin", patterns))
        self.assertFalse(_is_ignored("server.py", patterns))
        self.assertFalse(_is_ignored("static/app.js", patterns))
        for nested_lookalike in (
            "api/server.py",
            "seed/uv.lock",
            "static/pyproject.toml",
            "static/nested/app.js",
        ):
            with self.subTest(nested_lookalike=nested_lookalike):
                self.assertTrue(_is_ignored(nested_lookalike, patterns))

    def test_vercel_routes_function_before_any_filesystem_serving(self) -> None:
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertNotIn("rewrites", config)
        self.assertEqual(
            config["routes"],
            [{"src": "/(.*)", "dest": "/api/index?__route=$1"}],
        )
        self.assertNotIn("handle", config["routes"][0])

    def test_ci_scans_fresh_executable_before_smoke_and_upload(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
        build_marker = "Build isolated Windows executable"
        manifest_marker = "Bind executable to source commit and release inputs"
        scan_marker = "Release secret scan built executable"
        smoke_marker = "Smoke packaged health and static assets"
        upload_marker = "actions/upload-artifact@v7"

        self.assertIn("--binary reports/ci-build/dist/DARTStructure.exe", workflow)
        self.assertIn("DARTStructure.release.json", workflow)
        self.assertIn("DARTStructure-windows-${{ github.sha }}", workflow)
        self.assertLess(workflow.index(build_marker), workflow.index(manifest_marker))
        self.assertLess(workflow.index(manifest_marker), workflow.index(scan_marker))
        self.assertLess(workflow.index(scan_marker), workflow.index(smoke_marker))
        self.assertLess(workflow.index(scan_marker), workflow.rindex(upload_marker))

    def test_ci_uses_lockfile_and_exposes_expected_sha_post_deploy_smoke(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")

        self.assertEqual(workflow.count("actions/checkout@v7"), 3)
        self.assertEqual(workflow.count("actions/setup-python@v7"), 3)
        self.assertEqual(workflow.count("actions/setup-node@v7"), 1)
        self.assertEqual(workflow.count("actions/upload-artifact@v7"), 1)
        self.assertIn('node-version: "24"', workflow)
        self.assertIn("package-manager-cache: false", workflow)
        self.assertEqual(workflow.count("uv sync --locked"), 2)
        self.assertIn('python -m pip install "uv==0.11.2"', workflow)
        self.assertIn("python -m pip_audit --local", workflow)
        self.assertIn("tools/post_deploy_smoke.py", workflow)
        self.assertIn("--expected-sha", workflow)

    def test_release_documentation_forbids_prebuilt_and_matches_retry_contract(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "PRODUCTION_RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

        self.assertIn("최초 호출 포함 최대 3회(재시도 최대 2회)", readme)
        self.assertIn("`vercel deploy --prebuilt`는 금지", readme)
        self.assertIn("`uv.lock`", readme)
        self.assertIn("vercel deploy --prebuilt`는 사용하지 않는다", checklist)
        self.assertIn("tools/post_deploy_smoke.py", checklist)

    def test_frozen_bundle_data_manifest_is_a_static_allowlist(self) -> None:
        self.assertEqual(_frozen_data_sources(), ALLOWED_FROZEN_DATA_SOURCES)
        seed_files = {path.name for path in (ROOT / "seed").iterdir() if path.is_file()}
        self.assertEqual(seed_files, ALLOWED_SEED_FILES)

        spec = (ROOT / "DARTStructure.spec").read_text(encoding="utf-8")
        for forbidden in (
            ".env",
            "credential",
            "collect_data_files",
            "Tree(",
            "reports",
            "video_work",
            "promo_video",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, spec)

    def test_frozen_executable_size_and_local_secret_values_are_bounded(self) -> None:
        executable = ROOT / "dist" / "DARTStructure.exe"
        self.assertTrue(executable.is_file())
        self.assertLessEqual(executable.stat().st_size, MAX_FROZEN_EXECUTABLE_BYTES)
        for key, secret in _dotenv_secret_values().items():
            with self.subTest(key=key):
                self.assertFalse(
                    _binary_contains(executable, secret),
                    f"local credential value was embedded for {key}",
                )


if __name__ == "__main__":
    unittest.main()
