"""Read-only classroom readiness checks for DART HR Briefing.

The command reports whether a secret is configured, never the secret value.
It may inspect the local app health endpoint, but never contacts OpenDART,
OpenAI, GitHub, Vercel, or any other remote service.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import socket
import subprocess
import sys
from typing import Mapping, Sequence
from urllib.request import Request, urlopen


DEFAULT_PORT = 8765
MAX_ENV_BYTES = 64 * 1024
MAX_HEALTH_BYTES = 16 * 1024
EXPECTED_APP_ID = "kr.opendart.dart-hr-briefing"
REQUIRED_FILES = (
    "server.py",
    "classroom_mode.py",
    "static/index.html",
    "static/app.js",
    ".env.example",
    "seed/classroom_workforce_2024_11011.json",
    "fixtures/workforce/representative_2024_11011.json",
    "fixtures/workforce/edge_cases_2024_11011.json",
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str
    detail: str


def _read_env(path: Path) -> dict[str, str]:
    """Read a small dotenv file without expanding or executing values."""

    if not path.is_file():
        return {}
    if path.stat().st_size > MAX_ENV_BYTES:
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def check_python(version: Sequence[int] | None = None) -> Check:
    current = tuple(version or sys.version_info[:3])
    rendered = ".".join(str(part) for part in current[:3])
    if current[:2] < (3, 11):
        return Check("Python", "FAIL", f"{rendered}; Python 3.11 이상이 필요합니다.")
    if current[:2] > (3, 14):
        return Check("Python", "WARN", f"{rendered}; 검증 범위는 Python 3.11~3.14입니다.")
    return Check("Python", "PASS", f"{rendered}; 지원 범위입니다.")


def check_required_files(root: Path) -> Check:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        return Check("필수 파일", "FAIL", "누락: " + ", ".join(missing))
    return Check("필수 파일", "PASS", f"필수 파일 {len(REQUIRED_FILES)}개를 확인했습니다.")


def check_runtime_dependency() -> Check:
    if importlib.util.find_spec("jsonschema") is None:
        return Check(
            "런타임 의존성",
            "FAIL",
            'jsonschema가 없습니다. python -m pip install -e ".[dev]"를 실행하세요.',
        )
    return Check("런타임 의존성", "PASS", "jsonschema를 사용할 수 있습니다.")


def check_quality_tools() -> Check:
    missing = [name for name in ("coverage", "ruff") if importlib.util.find_spec(name) is None]
    if missing:
        return Check(
            "품질 도구",
            "WARN",
            "없음: " + ", ".join(missing) + '; 전체 검증 전 .[dev] 설치가 필요합니다.',
        )
    return Check("품질 도구", "PASS", "coverage와 ruff를 사용할 수 있습니다.")


def check_dart_key(root: Path, environ: Mapping[str, str] | None = None) -> Check:
    environment = os.environ if environ is None else environ
    environment_value = str(environment.get("OPENDART_API_KEY", "")).strip()
    dotenv_value = _read_env(root / ".env").get("OPENDART_API_KEY", "").strip()
    value = environment_value or dotenv_value
    source = "프로세스 환경변수" if environment_value else "로컬 .env"
    if not value:
        return Check(
            "OpenDART 키",
            "WARN",
            "설정되지 않았습니다. 합성 데이터 실습은 가능하지만 실제 조회는 사용할 수 없습니다.",
        )
    if len(value) != 40:
        return Check(
            "OpenDART 키",
            "WARN",
            f"{source}에 값이 있으나 예상 길이와 다릅니다. 값은 출력하지 않았습니다.",
        )
    return Check(
        "OpenDART 키",
        "PASS",
        f"{source}에 설정되어 있습니다. 값은 출력하지 않았습니다.",
    )


def check_env_git_safety(root: Path) -> Check:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", ".env"],
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return Check(".env Git 제외", "WARN", "Git으로 .env 제외 여부를 확인하지 못했습니다.")
    if result.returncode == 0:
        return Check(".env Git 제외", "PASS", ".env가 Git 제외 규칙에 포함됩니다.")
    return Check(".env Git 제외", "FAIL", ".env가 Git 제외 규칙에 포함되지 않습니다.")


def _local_health(port: int) -> dict[str, object] | None:
    request = Request(
        f"http://127.0.0.1:{port}/api/health",
        headers={"User-Agent": "dart-classroom-preflight/1"},
    )
    try:
        with urlopen(request, timeout=0.5) as response:
            payload = response.read(MAX_HEALTH_BYTES + 1)
    except (OSError, TimeoutError, ValueError):
        return None
    if len(payload) > MAX_HEALTH_BYTES:
        return None
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def check_port(port: int = DEFAULT_PORT) -> Check:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))
    except OSError:
        health = _local_health(port)
        app = health.get("app") if isinstance(health, dict) else None
        if (
            health is not None
            and health.get("ok") is True
            and isinstance(app, dict)
            and app.get("id") == EXPECTED_APP_ID
        ):
            return Check(
                "기본 포트",
                "PASS",
                f"127.0.0.1:{port}에서 현재 DART HR Briefing이 이미 실행 중입니다.",
            )
        return Check(
            "기본 포트",
            "FAIL",
            f"127.0.0.1:{port}를 다른 프로그램 또는 식별할 수 없는 서버가 사용 중입니다.",
        )
    finally:
        probe.close()
    return Check("기본 포트", "PASS", f"127.0.0.1:{port}를 사용할 수 있습니다.")


def check_test_readiness(root: Path) -> Check:
    tests = sorted(root.glob("test_*.py"))
    if not tests:
        return Check("테스트 준비", "FAIL", "루트에서 test_*.py 파일을 찾지 못했습니다.")
    return Check(
        "테스트 준비",
        "PASS",
        f"테스트 파일 {len(tests)}개를 발견했습니다. 이 점검은 테스트를 실행하지 않습니다.",
    )


def run_checks(
    root: Path,
    *,
    port: int = DEFAULT_PORT,
    environ: Mapping[str, str] | None = None,
) -> list[Check]:
    resolved = root.resolve()
    return [
        check_python(),
        check_required_files(resolved),
        check_runtime_dependency(),
        check_quality_tools(),
        check_dart_key(resolved, environ),
        check_env_git_safety(resolved),
        check_port(port),
        check_test_readiness(resolved),
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DART HR Briefing 강의 사전점검")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="프로젝트 루트(기본값: 이 스크립트의 상위 프로젝트)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="확인할 로컬 포트")
    parser.add_argument("--json", action="store_true", help="비밀값이 없는 JSON 결과 출력")
    parser.add_argument("--strict", action="store_true", help="WARN도 종료 코드 1로 처리")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.port < 1 or args.port > 65535:
        print("포트는 1~65535 범위여야 합니다.", file=sys.stderr)
        return 2

    checks = run_checks(args.root, port=args.port)
    counts = {status: sum(check.status == status for check in checks) for status in ("PASS", "WARN", "FAIL")}
    if args.json:
        print(
            json.dumps(
                {"checks": [asdict(check) for check in checks], "summary": counts},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print("DART HR Briefing 강의 사전점검 - 비밀값은 출력하지 않습니다.")
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
        print(
            "요약: "
            + ", ".join(f"{status} {counts[status]}" for status in ("PASS", "WARN", "FAIL"))
        )

    if counts["FAIL"] or (args.strict and counts["WARN"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
