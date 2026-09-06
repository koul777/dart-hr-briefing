from __future__ import annotations

import ast
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _module_string_constant(relative_path: str, name: str) -> str:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    raise AssertionError(f"missing string constant: {relative_path}:{name}")


class PackagingContractTests(unittest.TestCase):
    def test_release_version_is_consistent_across_package_runtime_and_smoke(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(
            {
                project["project"]["version"],
                _module_string_constant("server.py", "APP_VERSION"),
                _module_string_constant("tools/post_deploy_smoke.py", "APP_VERSION"),
            },
            {"0.2.0"},
        )

    def test_frozen_bundle_includes_v2_schema_and_frontend_assets(self) -> None:
        spec = (ROOT / "DARTStructure.spec").read_text(encoding="utf-8")
        self.assertIn("('static', 'static')", spec)
        self.assertIn("('schemas', 'schemas')", spec)
        self.assertIn("('seed', 'seed')", spec)
        self.assertIn("('HR_BRIEFING_RULES.md', '.')", spec)
        self.assertNotIn(".env", spec)
        self.assertNotIn("data/corp_codes.json", spec)

    def test_build_extra_includes_strict_schema_runtime(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        runtime_dependencies = project["project"]["dependencies"]
        build_dependencies = project["project"]["optional-dependencies"]["build"]
        dev_dependencies = project["project"]["optional-dependencies"]["dev"]
        setuptools_config = project["tool"]["setuptools"]

        self.assertTrue(
            any(requirement.startswith("jsonschema") for requirement in runtime_dependencies)
        )
        self.assertTrue(
            any(requirement.startswith("jsonschema") for requirement in build_dependencies)
        )
        self.assertEqual(project["build-system"]["build-backend"], "setuptools.build_meta")
        self.assertIn("server", setuptools_config["py-modules"])
        self.assertIn("agent_orchestration", setuptools_config["py-modules"])
        self.assertIn("classroom_mode", setuptools_config["py-modules"])
        self.assertIn("api", setuptools_config["packages"])
        workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
        self.assertEqual(
            workflow.count('python -m pip install --upgrade "pip>=26.2.1,<27"'),
            2,
        )
        self.assertTrue(
            any(requirement.startswith("pip-audit") for requirement in dev_dependencies)
        )
        self.assertEqual(workflow.count("uv sync --locked"), 2)
        self.assertIn("uv sync --locked --extra dev", workflow)
        self.assertIn("uv sync --locked --extra build", workflow)
        self.assertIn(
            'uv sync --locked --extra dev --python "${{ matrix.python-version }}"',
            workflow,
        )
        self.assertIn("Verify matrix interpreter was not replaced by .python-version", workflow)
        self.assertIn("sys.version_info[:2]", workflow)
        self.assertIn('uv sync --locked --extra build --python "3.12"', workflow)
        for version in ("3.11", "3.12", "3.13", "3.14"):
            self.assertIn(f'"{version}"', workflow)
        self.assertIn("ruff check . --select E4,E7,E9,F", workflow)
        self.assertIn("python -m pip_audit --local", workflow)
        self.assertIn(
            'RUNTIME_ENV.get("DART_STRICT_ORCHESTRATION_SCHEMA", "true")',
            (ROOT / "server.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "DART_STRICT_ORCHESTRATION_SCHEMA=true",
            (ROOT / ".env.example").read_text(encoding="utf-8"),
        )

    def test_headless_runtime_can_disable_browser_launch(self) -> None:
        server_source = (ROOT / "server.py").read_text(encoding="utf-8")
        example_environment = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn('RUNTIME_ENV.get("DART_OPEN_BROWSER", "true")', server_source)
        self.assertIn("if OPEN_BROWSER_ON_START:", server_source)
        self.assertIn("open_browser_when_ready", server_source)
        self.assertIn("ExclusiveThreadingHTTPServer", server_source)
        self.assertIn("DART_BUILD_ID=", example_environment)
        self.assertIn('Path(local_app_data) / "DART-HR-Briefing"', server_source)
        self.assertIn("DART_OPEN_BROWSER=true", example_environment)

    def test_bundled_hr_rules_preserve_decision_support_boundaries(self) -> None:
        rules = (ROOT / "HR_BRIEFING_RULES.md").read_text(encoding="utf-8")
        for marker in (
            "의사결정의 성공 확률이나 실행 권고",
            "산업·규모·사업모델을 보정한 외부 벤치마크가 아니며",
            "채용·평가·보상·감축 등 인사조치를 자동 제안",
            "단일연도 readiness와 confidence의 근거로 사용하지 않습니다",
            "restatement_verification=not_performed",
            "승계 준비도, 이사회 실효성, 임원 개인 성과를 판정하지 않습니다",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rules)


if __name__ == "__main__":
    unittest.main()
