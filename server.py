from __future__ import annotations

import errno
import gzip
import hashlib
import io
import json
import math
import os
import re
import secrets
import socket
import sys
import threading
import time
import unicodedata
import webbrowser
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from claude_mcp_adapter import (
    MCPCallRequest,
    UnavailableClaudeCodeMCPAdapter,
    create_claude_code_mcp_adapter,
)
from classroom_mode import build_classroom_payload
from analysis_contract import AnalysisRequest, MAX_CORP_CODES
from agent_orchestration import (
    ALLOWED_REQUEST_METRICS,
    ALLOWED_REQUEST_VIEWS,
    WorkforceAgentOrchestrator,
    WorkforceObservation,
)
from openai_responses_adapter import OpenAIResponsesError, OpenAIResponsesProvider
from runtime_controls import (
    BoundedTTLCache,
    OrchestrationTelemetry,
    SlidingWindowRateLimiter,
    StripedLockPool,
    anonymized_client_key,
)
from workforce_analytics import (
    MAX_REASONABLE_ABSOLUTE_VALUE,
    MAX_REASONABLE_HEADCOUNT,
    MAX_REASONABLE_TENURE_MONTHS,
    build_workforce_summary,
    parse_months,
    select_employee_rows,
)


SOURCE_ROOT = Path(__file__).resolve().parent
FROZEN_RUNTIME = bool(getattr(sys, "frozen", False))
DEPLOYED_ON_VERCEL = bool(os.environ.get("VERCEL"))
if FROZEN_RUNTIME:
    # In a PyInstaller one-file build, bundled static assets are extracted to
    # _MEIPASS while .env and the cache live beside the executable.
    ROOT = Path(sys.executable).resolve().parent
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", ROOT)) / "static"
else:
    ROOT = SOURCE_ROOT
    STATIC_DIR = ROOT / "static"


def _runtime_data_dir(
    root: Path,
    *,
    frozen: bool,
    environ: Mapping[str, str],
) -> Path:
    override = str(environ.get("DART_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    if environ.get("VERCEL"):
        return Path("/tmp/dart-workforce")
    local_app_data = str(environ.get("LOCALAPPDATA") or "").strip()
    if frozen and local_app_data:
        return Path(local_app_data) / "DART-HR-Briefing"
    return root / "data"


DART_BASE = "https://opendart.fss.or.kr/api"
APP_ID = "kr.opendart.dart-hr-briefing"
APP_NAME = "DART HR Briefing"
APP_VERSION = "0.2.0"
DEFAULT_PORT = 8765
MAX_PORT_FALLBACK_ATTEMPTS = 20
MAX_HEALTH_RESPONSE_BYTES = 64 * 1024
MAX_DOTENV_BYTES = 64 * 1024
MAX_DOTENV_VALUE_CHARS = 4096
HSTS_HEADER = "max-age=31536000"
DEFAULT_HR_ANALYSIS_QUESTION = (
    "선택 기업의 인력 생산성·보상 지속가능성·인력구조 차이를 비교하고, "
    "판단 한계와 다음 내부 데이터를 설명해줘"
)


def _effective_request_target(
    raw_target: str,
    *,
    deployed_on_vercel: bool | None = None,
) -> str:
    """Restore the public path forwarded through the single Vercel function."""

    deployed = DEPLOYED_ON_VERCEL if deployed_on_vercel is None else deployed_on_vercel
    if not deployed:
        return raw_target
    parsed = urlparse(raw_target)
    if parsed.path != "/api/index":
        return raw_target
    route = ""
    route_present = False
    remaining: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "__route" and not route_present:
            route = value
            route_present = True
        else:
            remaining.append((key, value))
    if not route_present:
        return raw_target
    public_path = "/" if route in {"", "root"} else f"/{route.lstrip('/')}"
    return urlunsplit(("", "", public_path, urlencode(remaining, doseq=True), ""))


def _runtime_port(environ: Mapping[str, str] | None = None) -> int:
    source = os.environ if environ is None else environ
    try:
        port = int(source.get("PORT", str(DEFAULT_PORT)))
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


def _explicit_runtime_port(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    raw = str(source.get("PORT", "")).strip()
    try:
        port = int(raw)
    except ValueError:
        return False
    return bool(raw) and 1 <= port <= 65535


def _runtime_build_id(
    environ: Mapping[str, str],
    *,
    frozen: bool,
    executable: Path,
) -> str:
    vercel_commit = str(environ.get("VERCEL_GIT_COMMIT_SHA", "")).strip().lower()
    if environ.get("VERCEL") and re.fullmatch(r"[0-9a-f]{7,64}", vercel_commit):
        # A deployment-scoped Vercel commit is the freshness identity.  An
        # operator-supplied label must never hide which revision is serving.
        return f"git-{vercel_commit[:12]}"
    configured = str(environ.get("DART_BUILD_ID", "")).strip()
    if configured and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", configured):
        return configured
    for variable in ("VERCEL_GIT_COMMIT_SHA", "GITHUB_SHA"):
        commit_sha = str(environ.get(variable, "")).strip().lower()
        if re.fullmatch(r"[0-9a-f]{7,64}", commit_sha):
            return f"git-{commit_sha[:12]}"
    if not frozen:
        return "source"
    try:
        digest = hashlib.sha256()
        with executable.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256-{digest.hexdigest()[:12]}"
    except OSError:
        return "frozen-unknown"


PORT = _runtime_port()
PORT_EXPLICITLY_CONFIGURED = _explicit_runtime_port()
DART_CACHEABLE_ENDPOINTS = {
    "fnlttSinglAcnt.json",
    "empSttus.json",
    "exctvSttus.json",
    "unrstExctvMendngSttus.json",
}
DART_STATUS_MESSAGES = {
    "010": "OpenDART 인증키가 등록되지 않았습니다.",
    "011": "OpenDART 인증키를 사용할 수 없습니다.",
    "012": "OpenDART에 접근할 수 없는 IP입니다.",
    "014": "OpenDART 파일이 존재하지 않습니다.",
    "020": "OpenDART 요청 제한을 초과했습니다.",
    "021": "OpenDART 조회 가능 회사 수를 초과했습니다.",
    "100": "OpenDART 요청 필드 값이 올바르지 않습니다.",
    "101": "OpenDART에 부적절한 접근입니다.",
    "800": "OpenDART가 시스템 점검 중입니다.",
    "900": "OpenDART에서 정의되지 않은 오류가 발생했습니다.",
    "901": "OpenDART 계정의 개인정보 보유기간이 만료되었습니다.",
}


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_DOTENV_BYTES + 1)
    except OSError:
        return values
    if len(raw) > MAX_DOTENV_BYTES:
        return values
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if (
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", key)
            or len(value) > MAX_DOTENV_VALUE_CHARS
            or any(
                unicodedata.category(character) in {"Cc", "Cf", "Cs"}
                for character in value
            )
        ):
            continue
        values[key] = value
    return values


def _runtime_environment(
    dotenv: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, str]:
    """Use dotenv as local defaults while preserving deployment overrides."""

    return {**dotenv, **environ}


def _trusted_dotenv_paths(root: Path, *, frozen: bool) -> tuple[Path, ...]:
    paths = [root / ".env"]
    standard_source_dist = (
        frozen
        and root.name.casefold() == "dist"
        and (root.parent / "DARTStructure.spec").is_file()
    )
    if standard_source_dist:
        paths.append(root.parent / ".env")
    return tuple(paths)


DOTENV: dict[str, str] = {}
for dotenv_path in _trusted_dotenv_paths(ROOT, frozen=FROZEN_RUNTIME):
    for dotenv_key, dotenv_value in load_dotenv(dotenv_path).items():
        DOTENV.setdefault(dotenv_key, dotenv_value)
RUNTIME_ENV = _runtime_environment(DOTENV, os.environ)
BUILD_ID = _runtime_build_id(
    RUNTIME_ENV,
    frozen=FROZEN_RUNTIME,
    executable=Path(sys.executable).resolve(),
)
INSTANCE_ID = secrets.token_hex(12)
API_KEY = str(RUNTIME_ENV.get("OPENDART_API_KEY", "")).strip()
DATA_DIR = _runtime_data_dir(
    ROOT,
    frozen=FROZEN_RUNTIME,
    environ={**RUNTIME_ENV, "VERCEL": os.environ.get("VERCEL", "")},
)
CORP_CACHE = DATA_DIR / "corp_codes.json"
BUNDLED_CORP_CATALOG = SOURCE_ROOT / "seed" / "corp_codes.json.gz"
OPEN_BROWSER_ON_START = str(RUNTIME_ENV.get("DART_OPEN_BROWSER", "true")).strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
STRICT_ORCHESTRATION_SCHEMA = str(
    RUNTIME_ENV.get("DART_STRICT_ORCHESTRATION_SCHEMA", "true")
).strip().lower() in {"1", "true", "yes", "on"}
ALLOW_OPERATOR_AI_PROVIDER = str(
    RUNTIME_ENV.get("DART_ALLOW_OPERATOR_AI_PROVIDER", "false")
).strip().lower() in {"1", "true", "yes", "on"}
OPERATOR_AI_TOKEN = str(RUNTIME_ENV.get("DART_OPERATOR_AI_TOKEN", "")).strip()


def _valid_operator_ai_token(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._~-]{32,512}", value))


def _bounded_environment_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = str(RUNTIME_ENV.get(name, "")).strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


DART_RESPONSE_CACHE_TTL_SECONDS = _bounded_environment_int(
    "DART_CACHE_TTL_SECONDS", 300, 30, 3600
)
DART_RESPONSE_CACHE_MAX_ENTRIES = _bounded_environment_int(
    "DART_CACHE_MAX_ENTRIES", 512, 16, 5000
)
DART_RESPONSE_CACHE_MAX_BYTES = _bounded_environment_int(
    "DART_CACHE_MAX_BYTES", 64 * 1024 * 1024, 1024 * 1024, 1024 * 1024 * 1024
)
MAX_DART_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_CORP_XML_BYTES = 100 * 1024 * 1024
MAX_CORP_CACHE_BYTES = 40 * 1024 * 1024
MAX_COMPANY_CATALOG_ENTRIES = 200_000
MAX_COMPANY_SEARCH_CHARS = 100
MAX_DART_LIST_ROWS = 10_000
MAX_PUBLIC_LABEL_CHARS = 500
MAX_FINANCIAL_HISTORY_OBSERVATIONS = 48
MAX_PEOPLE_HISTORY_OBSERVATIONS = 32
DART_RETRY_ATTEMPTS = _bounded_environment_int("DART_RETRY_ATTEMPTS", 3, 1, 3)
DART_RETRY_BASE_DELAY_MS = _bounded_environment_int(
    "DART_RETRY_BASE_DELAY_MS", 250, 50, 2000
)
DART_REQUEST_TIMEOUT_SECONDS = _bounded_environment_int(
    "DART_REQUEST_TIMEOUT_SECONDS", 10, 3, 10
)
DART_OUTBOUND_DEADLINE_SECONDS = _bounded_environment_int(
    "DART_OUTBOUND_DEADLINE_SECONDS", 35, 10, 90
)
DART_OUTBOUND_ATTEMPT_BUDGET = _bounded_environment_int(
    "DART_OUTBOUND_ATTEMPT_BUDGET", 48, 8, 96
)
DART_RESPONSE_CACHE = BoundedTTLCache(
    max_entries=DART_RESPONSE_CACHE_MAX_ENTRIES,
    max_weight=DART_RESPONSE_CACHE_MAX_BYTES,
    ttl_seconds=DART_RESPONSE_CACHE_TTL_SECONDS,
)
DART_REQUEST_LOCKS = StripedLockPool(64)
REQUEST_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=_bounded_environment_int("DART_RATE_LIMIT_PER_MINUTE", 30, 5, 600),
    window_seconds=60,
    max_clients=_bounded_environment_int("DART_RATE_LIMIT_MAX_CLIENTS", 4096, 128, 20000),
)
ORCHESTRATION_TELEMETRY = OrchestrationTelemetry()
RATE_LIMIT_SALT = secrets.token_hex(16)
RATE_LIMITED_POST_PATHS = {"/api/analysis", "/api/analysis/context", "/api/ai/connect"}
RATE_LIMITED_GET_PATHS = {
    "/api/companies",
    "/api/financials",
    "/api/financials/history",
    "/api/people",
    "/api/people/history",
    "/api/executives",
    "/api/executives/history",
    "/api/workforce/orchestration",
}
CORP_LOCK = threading.Lock()
MAX_COMPANIES = MAX_CORP_CODES


def enforce_history_observation_budget(
    codes: list[str],
    start_year: int,
    end_year: int,
    *,
    maximum: int,
) -> int:
    observations = len(codes) * (end_year - start_year + 1)
    if observations > maximum:
        raise ValueError(
            f"기업×연도 요청 예산은 최대 {maximum}개 관측입니다. 기업 수나 기간을 줄여 주세요."
        )
    return observations


_ORCHESTRATION_VALIDATOR: Any | None = None


def _load_orchestration_validator() -> Any:
    """Load and validate the bundled schema before accepting strict traffic."""

    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError(
            "Orchestration strict schema validation requires jsonschema."
        ) from exc
    schema_path = SOURCE_ROOT / "schemas" / "workforce_orchestration_v2.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except Exception as exc:
        raise RuntimeError("Orchestration strict schema could not be initialized.") from exc


def validate_orchestration_response(payload: Mapping[str, Any]) -> None:
    """Optionally enforce the published v2 schema at an orchestration boundary."""
    if not STRICT_ORCHESTRATION_SCHEMA:
        return
    if payload.get("schema_version") != 2:
        raise RuntimeError("Orchestration response failed strict schema validation.")
    global _ORCHESTRATION_VALIDATOR
    try:
        if _ORCHESTRATION_VALIDATOR is None:
            _ORCHESTRATION_VALIDATOR = _load_orchestration_validator()
        _ORCHESTRATION_VALIDATOR.validate(payload)
    except Exception as exc:
        raise RuntimeError("Orchestration response failed strict schema validation.") from exc


if STRICT_ORCHESTRATION_SCHEMA:
    _ORCHESTRATION_VALIDATOR = _load_orchestration_validator()


def load_briefing_rules() -> str | None:
    candidates = (
        ROOT / "HR_BRIEFING_RULES.md",
        STATIC_DIR.parent / "HR_BRIEFING_RULES.md",
        SOURCE_ROOT / "HR_BRIEFING_RULES.md",
    )
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig").strip()
        except OSError:
            continue
        if text:
            return text[:20_000]
    return None

DART_METRIC_CATALOG: list[dict[str, Any]] = [
    {"metric_id": "assets", "label": "자산총계", "group": "규모", "unit": "억원", "source_key": "assets"},
    {"metric_id": "liabilities", "label": "부채총계", "group": "구조", "unit": "억원", "source_key": "liabilities"},
    {"metric_id": "equity", "label": "자본총계", "group": "구조", "unit": "억원", "source_key": "equity"},
    {"metric_id": "cash", "label": "현금및현금성자산", "group": "유동성", "unit": "억원", "source_key": "cash"},
    {"metric_id": "revenue", "label": "매출액", "group": "손익", "unit": "억원", "source_key": "revenue"},
    {"metric_id": "operating_profit", "label": "영업이익", "group": "손익", "unit": "억원", "source_key": "operating_profit"},
    {"metric_id": "net_income", "label": "당기순이익", "group": "손익", "unit": "억원", "source_key": "net_income"},
    {"metric_id": "operating_margin", "label": "영업이익률", "group": "수익성", "unit": "%", "source_key": "operating_margin"},
    {"metric_id": "net_margin", "label": "순이익률", "group": "수익성", "unit": "%", "source_key": "net_margin"},
    {"metric_id": "debt_ratio", "label": "부채비율", "group": "안정성", "unit": "%", "source_key": "debt_ratio"},
    {"metric_id": "current_ratio", "label": "유동비율", "group": "유동성", "unit": "%", "source_key": "current_ratio"},
]

PEOPLE_METRIC_CATALOG: list[dict[str, Any]] = [
    {"metric_id": "employees_total", "label": "총 직원 수", "group": "인력 규모", "unit": "명", "source_key": "employees_total"},
    {"metric_id": "regular_employees", "label": "정규직 수", "group": "인력 구성", "unit": "명", "source_key": "regular_employees"},
    {"metric_id": "contract_employees", "label": "계약직 수", "group": "인력 구성", "unit": "명", "source_key": "contract_employees"},
    {"metric_id": "average_tenure_years", "label": "평균 근속 연수", "group": "인력 경험", "unit": "년", "source_key": "average_tenure_years"},
    {"metric_id": "average_salary", "label": "1인 평균 급여", "group": "보상", "unit": "원", "source_key": "average_salary"},
    {"metric_id": "executives_total", "label": "임원 수", "group": "리더십", "unit": "명", "source_key": "executives_total"},
    {"metric_id": "unregistered_pay_total", "label": "미등기임원 급여 총액", "group": "보상", "unit": "원", "source_key": "unregistered_pay_total"},
]

EXECUTIVE_METRIC_CATALOG: list[dict[str, Any]] = [
    {"metric_id": "executives_total", "label": "전체 임원 수", "group": "임원 구조", "unit": "명", "source_key": "executives_total"},
    {"metric_id": "registered_executives", "label": "등기임원 수", "group": "임원 구조", "unit": "명", "source_key": "registered_executives"},
    {"metric_id": "unregistered_executives", "label": "미등기임원 수", "group": "임원 구조", "unit": "명", "source_key": "unregistered_executives"},
    {"metric_id": "inside_directors", "label": "사내이사 수", "group": "이사회", "unit": "명", "source_key": "inside_directors"},
    {"metric_id": "outside_directors", "label": "사외이사 수", "group": "이사회", "unit": "명", "source_key": "outside_directors"},
    {"metric_id": "ceo_count", "label": "대표이사 수", "group": "리더십", "unit": "명", "source_key": "ceo_count"},
    {"metric_id": "female_executives", "label": "여성 임원 수", "group": "다양성", "unit": "명", "source_key": "female_executives"},
    {"metric_id": "average_tenure_months", "label": "평균 재직기간", "group": "임기", "unit": "개월", "source_key": "average_tenure_months"},
    {"metric_id": "term_expiring_within_12_months", "label": "12개월 이내 임기 만료", "group": "승계", "unit": "명", "source_key": "term_expiring_within_12_months"},
    {"metric_id": "outside_director_share", "label": "사외이사 비율", "group": "이사회", "unit": "%", "source_key": "outside_director_share"},
    {"metric_id": "female_share", "label": "여성 임원 비율", "group": "다양성", "unit": "%", "source_key": "female_share"},
]

DECISION_METRIC_CATALOG: list[dict[str, Any]] = [
    {
        "metric_id": "employees_total",
        "label": "총 직원 수",
        "unit": "명",
        "signal_type": "lagging",
        "formula": None,
        "source_components": ["employee_status"],
        "interpretation_limit": "기준일의 기업 전체 공시 인원이며 FTE·직무별 수요나 이탈 원인을 설명하지 않습니다.",
    },
    {
        "metric_id": "average_salary",
        "label": "1인 평균 급여",
        "unit": "원",
        "signal_type": "lagging",
        "formula": "공시 평균의 인원 가중 또는 급여총액 / 직원 수",
        "source_components": ["employee_status"],
        "interpretation_limit": "집계 급여이며 개인별 보상, 직무가치, 성과급 산식 또는 보상 공정성을 판정하지 않습니다.",
    },
    {
        "metric_id": "annual_salary_total",
        "label": "연간 급여 총액",
        "unit": "원",
        "signal_type": "lagging",
        "formula": "공시된 사업부·성별 급여총액의 합계",
        "source_components": ["employee_status"],
        "interpretation_limit": "공시 집계범위 차이가 있을 수 있으며 총 인건비·복리후생비 전체와 같지 않습니다.",
    },
    {
        "metric_id": "revenue_per_employee",
        "label": "인당 매출",
        "unit": "원",
        "signal_type": "benchmark",
        "formula": "매출액 / 총 직원 수",
        "source_components": ["financial_status", "employee_status"],
        "interpretation_limit": "기업 전체 비교 지표이며 개인·팀 생산성이나 차이의 원인을 설명하지 않습니다.",
    },
    {
        "metric_id": "operating_profit_per_employee",
        "label": "인당 영업이익",
        "unit": "원",
        "signal_type": "benchmark",
        "formula": "영업이익 / 총 직원 수",
        "source_components": ["financial_status", "employee_status"],
        "interpretation_limit": "사업모델·자본집약도·외주 구조 차이의 영향을 받으므로 업종·규모 보정 없는 인과 해석을 금지합니다.",
    },
    {
        "metric_id": "salary_to_revenue",
        "label": "급여총액 / 매출",
        "unit": "%",
        "signal_type": "early_warning_proxy",
        "formula": "연간 급여 총액 / 매출액 × 100",
        "source_components": ["financial_status", "employee_status"],
        "interpretation_limit": "보상 지속가능성의 방향성 점검용 대리 지표이며 성과급 재원이나 적정 보상을 확정하지 않습니다.",
    },
    {
        "metric_id": "operating_margin",
        "label": "영업이익률",
        "unit": "%",
        "signal_type": "lagging",
        "formula": "영업이익 / 매출액 × 100",
        "source_components": ["financial_status"],
        "interpretation_limit": "이미 실현된 기업 전체 재무성과이며 보상정책의 효과나 인력 생산성의 원인을 설명하지 않습니다.",
    },
    {
        "metric_id": "contract_share",
        "label": "계약직 비중",
        "unit": "%",
        "signal_type": "early_warning_proxy",
        "formula": "계약직 수 / 총 직원 수 × 100",
        "source_components": ["employee_status"],
        "interpretation_limit": "공시 고용형태 비중이며 고용 안정성, 이탈 위험 또는 선택 원인을 직접 측정하지 않습니다.",
    },
    {
        "metric_id": "average_tenure_years",
        "label": "평균 근속",
        "unit": "년",
        "signal_type": "lagging",
        "formula": "공시 평균 근속의 인원 가중",
        "source_components": ["employee_status"],
        "interpretation_limit": "기준일 집계 평균이며 이탈 위험, 몰입 또는 장기근속의 원인을 설명하지 않습니다.",
    },
    {
        "metric_id": "term_expiring_within_12_months",
        "label": "12개월 내 임기 만료 임원",
        "unit": "명",
        "signal_type": "early_warning_proxy",
        "formula": "결산일 다음날부터 달력 기준 12개월 내 임기 종료 인원",
        "source_components": ["executive_status"],
        "interpretation_limit": "임기 일정 신호일 뿐 승계 준비도, 이사회 실효성 또는 개인 성과를 판정하지 않습니다.",
    },
    {
        "metric_id": "outside_director_share",
        "label": "사외이사 비중",
        "unit": "%",
        "signal_type": "benchmark",
        "formula": "사외이사 수 / 전체 임원 수 × 100",
        "source_components": ["executive_status"],
        "interpretation_limit": "선택 기업 간 구성 비교이며 이사회 독립성이나 실효성을 직접 판정하지 않습니다.",
    },
    {
        "metric_id": "ceo_count",
        "label": "대표이사 수",
        "unit": "명",
        "signal_type": "benchmark",
        "formula": "직위에 대표이사가 공시된 임원 행 수",
        "source_components": ["executive_status"],
        "interpretation_limit": "공시 직위 구성의 비교값이며 리더십 품질, 권한 배분 또는 승계 준비도를 판정하지 않습니다.",
    },
]

DECISION_DIMENSION_CATALOG: list[dict[str, Any]] = [
    {"dimension_id": "productivity", "label": "인력 생산성", "metric_ids": ["operating_profit_per_employee", "revenue_per_employee"]},
    {"dimension_id": "compensation_sustainability", "label": "보상 지속가능성", "metric_ids": ["salary_to_revenue", "operating_margin"]},
    {"dimension_id": "workforce_structure", "label": "인력구조 변화", "metric_ids": ["contract_share", "average_tenure_years"]},
    {"dimension_id": "governance_continuity", "label": "리더십·이사회 연속성", "metric_ids": ["term_expiring_within_12_months", "outside_director_share", "ceo_count"]},
    {"dimension_id": "data_completeness", "label": "판단 근거 완전성", "metric_ids": []},
]


class MCPProviderFacade:
    """Adapt the transport-neutral Claude MCP client to the orchestrator protocol."""

    provider_id = "claude_mcp"
    provider_label = "Claude MCP"

    def __init__(self, adapter: Any, tool: str = "analyze_financial_structure") -> None:
        self.adapter = adapter
        self.tool = tool
        self.configured = not isinstance(adapter, UnavailableClaudeCodeMCPAdapter)

    def analyze(self, *, prompt: str, context: dict[str, Any]) -> Any:
        call = self.adapter.call_tool(MCPCallRequest(
            server="claude-code",
            tool=self.tool,
            arguments={"prompt": prompt, "context": context},
        ))
        if not call.ok:
            return {
                "status": "not_configured" if call.status == "unavailable" else "error",
                "error_code": call.error_code,
                "error_message": call.error_message,
            }
        return call.result


MCP_ADAPTER = MCPProviderFacade(create_claude_code_mcp_adapter())
OPENAI_PROVIDER = OpenAIResponsesProvider.from_environment(RUNTIME_ENV)
CUSTOM_BRIEFING_RULES = load_briefing_rules()
if CUSTOM_BRIEFING_RULES:
    OPENAI_PROVIDER.instructions = CUSTOM_BRIEFING_RULES
ACTIVE_AI_PROVIDER = OPENAI_PROVIDER if OPENAI_PROVIDER.configured else MCP_ADAPTER
WORKFORCE_MCP_ADAPTER = MCPProviderFacade(
    create_claude_code_mcp_adapter(),
    tool="analyze_workforce_strategy",
)
WORKFORCE_AI_PROVIDER = (
    OPENAI_PROVIDER if OPENAI_PROVIDER.configured else WORKFORCE_MCP_ADAPTER
)


class DARTError(Exception):
    pass


class MalformedContentLength(ValueError):
    """A request length header that cannot be parsed without reflecting its value."""


class DARTBudgetExceeded(DARTError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        message = (
            "OpenDART 조회 제한 시간을 초과했습니다. 일부 결과만 표시합니다. "
            "조회 기업 또는 연도 범위를 줄이고 다시 시도해 주세요."
            if reason == "deadline"
            else "OpenDART 요청 예산을 초과했습니다. 일부 결과만 표시합니다. "
            "조회 기업 또는 연도 범위를 줄이고 다시 시도해 주세요."
        )
        super().__init__(message)


class DARTRequestBudget:
    """Thread-safe outbound attempt and wall-clock budget for one HTTP request."""

    def __init__(
        self,
        *,
        deadline_seconds: float = DART_OUTBOUND_DEADLINE_SECONDS,
        attempt_limit: int = DART_OUTBOUND_ATTEMPT_BUDGET,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.deadline_seconds = max(0.1, float(deadline_seconds))
        self.attempt_limit = max(1, int(attempt_limit))
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._deadline = self._clock() + self.deadline_seconds
        self._attempts = 0
        self._exhausted_reason: str | None = None
        self._lock = threading.Lock()

    def timeout_for_attempt(self, attempt_timeout: float) -> float:
        """Claim one real network attempt and return its remaining-safe timeout."""

        with self._lock:
            remaining = self._deadline - self._clock()
            if remaining <= 0.1:
                self._exhausted_reason = "deadline"
                raise DARTBudgetExceeded("deadline")
            if self._attempts >= self.attempt_limit:
                self._exhausted_reason = "attempt_limit"
                raise DARTBudgetExceeded("attempt_limit")
            self._attempts += 1
            return min(float(attempt_timeout), remaining)

    def sleep_before_retry(self, delay_seconds: float) -> None:
        delay = max(0.0, float(delay_seconds))
        with self._lock:
            if self._deadline - self._clock() <= delay + 0.1:
                self._exhausted_reason = "deadline"
                raise DARTBudgetExceeded("deadline")
        self._sleeper(delay)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "attempts": self._attempts,
                "attempt_limit": self.attempt_limit,
                "deadline_seconds": self.deadline_seconds,
                "remaining_seconds": max(0.0, self._deadline - self._clock()),
                "exhausted": self._exhausted_reason is not None,
                "exhausted_reason": self._exhausted_reason,
            }


def new_dart_request_budget() -> DARTRequestBudget:
    return DARTRequestBudget()


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def user_openai_provider(api_key: str) -> OpenAIResponsesProvider:
    """Create a request-scoped provider without retaining the user's key."""

    key = api_key.strip()
    if not key:
        raise ValueError("OpenAI API Key를 입력해 주세요.")
    if not key.startswith("sk-"):
        raise ValueError("OpenAI API Key는 sk-로 시작해야 합니다.")
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{4,509}", key):
        raise ValueError("OpenAI API Key 형식이 올바르지 않습니다.")
    return replace(OPENAI_PROVIDER, api_key=key)


def dart_request(
    endpoint: str,
    params: dict[str, str],
    binary: bool = False,
    *,
    budget: DARTRequestBudget | None = None,
) -> Any:
    if not API_KEY:
        raise DARTError("OPENDART_API_KEY가 .env에 설정되지 않았습니다.")
    cache_key = None
    if not binary and endpoint in DART_CACHEABLE_ENDPOINTS:
        cache_key = f"{endpoint}?{urlencode(sorted(params.items()))}"
        found, cached_result = DART_RESPONSE_CACHE.get(cache_key)
        if found:
            return cached_result
        with DART_REQUEST_LOCKS.lock_for(cache_key):
            found, cached_result = DART_RESPONSE_CACHE.get(cache_key)
            if found:
                return cached_result
            return _perform_dart_request(
                endpoint,
                params,
                binary=False,
                cache_key=cache_key,
                budget=budget,
            )
    return _perform_dart_request(
        endpoint,
        params,
        binary=binary,
        cache_key=None,
        budget=budget,
    )


def _perform_dart_request(
    endpoint: str,
    params: dict[str, str],
    *,
    binary: bool,
    cache_key: str | None,
    budget: DARTRequestBudget | None,
) -> Any:
    query = {**params, "crtfc_key": API_KEY}
    url = f"{DART_BASE}/{endpoint}?{urlencode(query)}"
    request = Request(url, headers={"User-Agent": "dart-financial-dashboard/0.1"})
    payload: bytes | None = None
    last_error: Exception | None = None
    for attempt in range(DART_RETRY_ATTEMPTS):
        try:
            attempt_timeout = (
                budget.timeout_for_attempt(DART_REQUEST_TIMEOUT_SECONDS)
                if budget is not None
                else DART_REQUEST_TIMEOUT_SECONDS
            )
            with urlopen(request, timeout=attempt_timeout) as response:
                payload = response.read(MAX_DART_RESPONSE_BYTES + 1)
                if len(payload) > MAX_DART_RESPONSE_BYTES:
                    raise DARTError("OpenDART 응답이 허용된 크기를 초과했습니다.")
            break
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            exc.close()
            if not retryable or attempt + 1 >= DART_RETRY_ATTEMPTS:
                if retryable:
                    raise DARTError(
                        f"OpenDART가 일시적으로 응답하지 않습니다 (HTTP {exc.code})."
                    ) from exc
                raise DARTError(f"OpenDART가 요청을 거부했습니다 (HTTP {exc.code}).") from exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 >= DART_RETRY_ATTEMPTS:
                raise DARTError("OpenDART 연결에 일시적인 문제가 발생했습니다.") from exc
        retry_delay = (DART_RETRY_BASE_DELAY_MS / 1000) * (2 ** attempt)
        if budget is not None:
            budget.sleep_before_retry(retry_delay)
        else:
            time.sleep(retry_delay)
    if payload is None:
        raise DARTError("OpenDART 연결에 실패했습니다.") from last_error

    if binary:
        return payload
    try:
        result = json.loads(
            payload.decode("utf-8-sig"),
            parse_constant=_reject_nonfinite_json,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise DARTError("OpenDART 응답을 해석하지 못했습니다.") from exc
    if not isinstance(result, dict):
        raise DARTError("OpenDART 응답 형식이 올바르지 않습니다.")
    dart_status = result.get("status")
    if not isinstance(dart_status, str) or not re.fullmatch(r"\d{3}", dart_status):
        raise DARTError("OpenDART 응답 상태 형식이 올바르지 않습니다.")
    if dart_status == "013":
        if cache_key:
            DART_RESPONSE_CACHE.set(cache_key, result, weight=len(payload))
        return result
    if dart_status != "000":
        message = DART_STATUS_MESSAGES.get(
            str(dart_status), "OpenDART 요청을 처리하지 못했습니다."
        )
        raise DARTError(f"{message} ({dart_status})")
    if cache_key:
        DART_RESPONSE_CACHE.set(cache_key, result, weight=len(payload))
    return result


def _budgeted_dart_request(
    endpoint: str,
    params: dict[str, str],
    budget: DARTRequestBudget | None,
) -> Any:
    if budget is None:
        return dart_request(endpoint, params)
    return dart_request(endpoint, params, budget=budget)


def load_corp_codes() -> list[dict[str, str]]:
    with CORP_LOCK:
        try:
            cache_stat = CORP_CACHE.stat()
            cache_is_fresh = (
                cache_stat.st_size <= MAX_CORP_CACHE_BYTES
                and time.time() - cache_stat.st_mtime < 24 * 60 * 60
            )
        except OSError:
            cache_is_fresh = False
        if cache_is_fresh:
            try:
                cached = _normalise_company_catalog(
                    json.loads(
                        CORP_CACHE.read_text(encoding="utf-8"),
                        parse_constant=_reject_nonfinite_json,
                    )
                )
                if cached:
                    return cached
            except (OSError, UnicodeDecodeError, ValueError):
                pass

        bundled_companies = _load_bundled_corp_catalog()
        # Downloading and parsing the complete OpenDART catalog can exceed a
        # serverless cold-start window. The bundled, validated snapshot keeps
        # company search responsive; data APIs still query OpenDART live.
        if bundled_companies and (DEPLOYED_ON_VERCEL or not API_KEY):
            return bundled_companies

        try:
            payload = dart_request("corpCode.xml", {}, binary=True)
        except DARTError:
            if bundled_companies:
                return bundled_companies
            raise
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                member = archive.getinfo("CORPCODE.xml")
                if member.file_size > MAX_CORP_XML_BYTES:
                    raise DARTError("기업 고유번호 파일이 허용된 크기를 초과했습니다.")
                xml_bytes = archive.read("CORPCODE.xml")
            lowered_xml = xml_bytes.lower()
            if b"<!doctype" in lowered_xml or b"<!entity" in lowered_xml:
                raise DARTError("기업 고유번호 XML에 허용되지 않은 선언이 포함되어 있습니다.")
            root = ET.fromstring(xml_bytes)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            raise DARTError("기업 고유번호 파일을 해석하지 못했습니다.") from exc

        companies: list[dict[str, str]] = []
        for item in root.findall("list"):
            corp_code = (item.findtext("corp_code") or "").strip()
            corp_name = (item.findtext("corp_name") or "").strip()
            stock_code = (item.findtext("stock_code") or "").strip()
            if corp_code and corp_name:
                companies.append(
                    {
                        "corp_code": corp_code,
                        "corp_name": corp_name,
                        "stock_code": stock_code,
                    }
                )

        companies = _normalise_company_catalog(companies)
        if not companies:
            raise DARTError("기업 고유번호 목록이 비어 있거나 올바르지 않습니다.")
        rendered = json.dumps(companies, ensure_ascii=False)
        if len(rendered.encode("utf-8")) > MAX_CORP_CACHE_BYTES:
            raise DARTError("기업 고유번호 캐시가 허용된 크기를 초과했습니다.")
        temporary_cache = CORP_CACHE.with_name(
            f".{CORP_CACHE.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
        )
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temporary_cache.write_text(rendered, encoding="utf-8")
            os.replace(temporary_cache, CORP_CACHE)
        except OSError:
            # A valid in-memory catalog is still useful when a read-only or
            # full cache directory prevents persistence.
            pass
        finally:
            try:
                temporary_cache.unlink(missing_ok=True)
            except OSError:
                pass
        return companies


def _load_bundled_corp_catalog() -> list[dict[str, str]]:
    try:
        with gzip.open(BUNDLED_CORP_CATALOG, "rb") as compressed:
            raw_catalog = compressed.read(MAX_CORP_CACHE_BYTES + 1)
        if len(raw_catalog) > MAX_CORP_CACHE_BYTES:
            return []
        return _normalise_company_catalog(
            json.loads(
                raw_catalog.decode("utf-8"),
                parse_constant=_reject_nonfinite_json,
            )
        )
    except (OSError, EOFError, UnicodeDecodeError, ValueError):
        return []


def _normalise_company_catalog(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > MAX_COMPANY_CATALOG_ENTRIES:
        return []
    companies: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        corp_code = str(item.get("corp_code") or "").strip()
        corp_name = str(item.get("corp_name") or "").strip()
        stock_code = str(item.get("stock_code") or "").strip()
        try:
            corp_name.encode("utf-8")
        except UnicodeEncodeError:
            continue
        if (
            not re.fullmatch(r"\d{8}", corp_code)
            or not corp_name
            or len(corp_name) > 200
            or any(
                unicodedata.category(character) in {"Cc", "Cf", "Cs"}
                for character in corp_name
            )
            or (stock_code and not re.fullmatch(r"\d{6}", stock_code))
            or corp_code in seen_codes
        ):
            continue
        seen_codes.add(corp_code)
        companies.append({
            "corp_code": corp_code,
            "corp_name": corp_name,
            "stock_code": stock_code,
        })
    return companies


def search_companies(query: str, limit: int = 12) -> list[dict[str, str]]:
    query = query.strip().lower()
    if not query:
        return []
    if len(query) > MAX_COMPANY_SEARCH_CHARS:
        raise ValueError(f"기업 검색어는 {MAX_COMPANY_SEARCH_CHARS}자 이하여야 합니다.")
    companies = load_corp_codes()

    def score(company: dict[str, str]) -> tuple[int, int, str]:
        name = company["corp_name"].lower()
        stock = company["stock_code"]
        corp_code = company["corp_code"]
        exact = 0 if name == query or stock == query or corp_code == query else 1
        starts = 0 if name.startswith(query) or stock.startswith(query) or corp_code.startswith(query) else 1
        return exact, starts, name

    matches = [
        company
        for company in companies
        if query in company["corp_name"].lower() or (company["stock_code"] and query in company["stock_code"]) or query in company["corp_code"]
    ]
    matches.sort(key=score)
    return matches[:limit]


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if len(text) > 128:
        return None
    if not text or text in {"-", "–", "-0"}:
        return None
    negative = False
    if "(" in text or ")" in text:
        if not (
            text.startswith("(")
            and text.endswith(")")
            and text.count("(") == 1
            and text.count(")") == 1
        ):
            return None
        negative = True
        text = text[1:-1].strip()
        if text.startswith(("+", "-")):
            return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number) or abs(number) > MAX_REASONABLE_ABSOLUTE_VALUE:
        return None
    return -number if negative else number


def _dart_list_rows(payload: Any, source: str) -> list[dict[str, Any]]:
    """Validate a DART ``list`` payload before any domain parsing."""

    if not isinstance(payload, Mapping):
        raise DARTError(f"OpenDART {source} 응답 형식이 올바르지 않습니다.")
    rows = payload.get("list")
    if rows is None:
        if payload.get("status") == "013":
            return []
        raise DARTError(f"OpenDART {source} 응답 목록이 없습니다.")
    if (
        not isinstance(rows, list)
        or len(rows) > MAX_DART_LIST_ROWS
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise DARTError(f"OpenDART {source} 응답 목록 형식이 올바르지 않습니다.")
    return [dict(row) for row in rows]


def first_value(rows: list[dict[str, Any]], names: list[str], section: str) -> float | None:
    consolidated = [row for row in rows if row.get("fs_div") == "CFS"]
    candidates = consolidated or rows
    section_rows = [row for row in candidates if row.get("sj_div") == section]
    candidates = section_rows or candidates

    for name in names:
        normalized_name = re.sub(r"\s+", "", name)
        matching_rows = [
            row
            for row in candidates
            if re.sub(r"\s+", "", _clean_text(row.get("account_nm")))
            == normalized_name
        ]
        if not matching_rows:
            continue
        amounts = [parse_amount(row.get("thstrm_amount")) for row in matching_rows]
        if any(amount is None for amount in amounts):
            return None
        distinct_amounts = {float(amount) for amount in amounts if amount is not None}
        return amounts[0] if len(distinct_amounts) == 1 else None
    return None


def ratio(
    numerator: float | None,
    denominator: float | None,
    *,
    require_nonnegative_numerator: bool = False,
) -> float | None:
    if (
        numerator is None
        or denominator is None
        or isinstance(numerator, bool)
        or isinstance(denominator, bool)
    ):
        return None
    try:
        numeric_numerator = float(numerator)
        numeric_denominator = float(denominator)
        if (
            not math.isfinite(numeric_numerator)
            or not math.isfinite(numeric_denominator)
            or numeric_denominator <= 0
            or (require_nonnegative_numerator and numeric_numerator < 0)
        ):
            return None
        value = numeric_numerator / numeric_denominator * 100
    except (OverflowError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def fetch_company_financials(
    company: dict[str, str],
    year: str,
    report_code: str,
    *,
    budget: DARTRequestBudget | None = None,
) -> dict[str, Any]:
    base = {"company": company, "year": year, "report_code": report_code}
    try:
        result = _budgeted_dart_request(
            "fnlttSinglAcnt.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
            budget,
        )
        rows = _dart_list_rows(result, "financial_status")
        if not rows:
            return {
                **base,
                "financials": {},
                "status": "no_data",
                "message": "해당 연도·보고서의 재무 데이터가 없습니다.",
            }

        revenue = first_value(rows, ["매출액", "수익(매출액)", "영업수익", "매출"], "IS")
        operating_profit = first_value(rows, ["영업이익", "영업이익(손실)"], "IS")
        net_income = first_value(rows, ["당기순이익", "당기순이익(손실)", "분기순이익"], "IS")
        assets = first_value(rows, ["자산총계"], "BS")
        liabilities = first_value(rows, ["부채총계"], "BS")
        equity = first_value(rows, ["자본총계"], "BS")
        cash = first_value(rows, ["현금및현금성자산", "현금 및 현금성자산"], "BS")
        current_assets = first_value(rows, ["유동자산"], "BS")
        current_liabilities = first_value(rows, ["유동부채"], "BS")

        financials = {
            "revenue": revenue,
            "operating_profit": operating_profit,
            "net_income": net_income,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "cash": cash,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "operating_margin": ratio(operating_profit, revenue),
            "net_margin": ratio(net_income, revenue),
            "debt_ratio": ratio(
                liabilities,
                equity,
                require_nonnegative_numerator=True,
            ),
            "current_ratio": ratio(
                current_assets,
                current_liabilities,
                require_nonnegative_numerator=True,
            ),
        }
        valid_receipts = sorted({
            receipt
            for row in rows
            if re.fullmatch(
                r"\d{14}",
                receipt := str(row.get("rcept_no") or "").strip(),
            )
        })
        receipt = valid_receipts[0] if len(valid_receipts) == 1 else ""
        currency = _clean_text(rows[0].get("currency") or "KRW").upper()
        return {
            **base,
            "financials": financials,
            "currency": currency if re.fullmatch(r"[A-Z]{3}", currency) else "KRW",
            "statement": "연결재무제표" if any(row.get("fs_div") == "CFS" for row in rows) else "재무제표",
            "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}" if receipt else None,
        }
    except DARTError as exc:
        return {**base, "financials": None, "error": str(exc)}


def _clean_text(value: Any) -> str:
    text = str("" if value is None else value)[:10_000]
    text = "".join(
        character
        for character in text
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )
    return re.sub(r"\s+", " ", text).strip()[:MAX_PUBLIC_LABEL_CHARS]


def _people_number(value: Any) -> float | None:
    number = parse_amount(value)
    return number if number is not None and number >= 0 else None


def _people_count(value: Any) -> int | None:
    number = _people_number(value)
    return (
        int(number)
        if number is not None
        and number <= MAX_REASONABLE_HEADCOUNT
        and number.is_integer()
        else None
    )


def _people_tenure_years(value: Any) -> float | None:
    numeric_years = _people_number(value)
    if numeric_years is not None:
        return (
            numeric_years
            if numeric_years <= MAX_REASONABLE_TENURE_MONTHS / 12
            else None
        )
    months = parse_months(value)
    return months / 12 if months is not None else None


def _unregistered_pay_category(value: Any) -> str:
    text = _clean_text(value)
    return text if text in {"미등기임원", "미등기 임원", "임원", "전체"} else "미등기임원"


def _report_as_of(year: str, report_code: str) -> date | None:
    try:
        normalized_year = int(year)
    except (TypeError, ValueError):
        return None
    month, day = {
        "11013": (3, 31),
        "11012": (6, 30),
        "11014": (9, 30),
        "11011": (12, 31),
    }.get(report_code, (12, 31))
    return date(normalized_year, month, day)


def _employee_summary_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Choose non-overlapping employee rows before aggregating.

    empSttus returns both business-unit rows and gender-total rows. When gender
    totals exist, only those rows are used; otherwise all returned rows are a
    documented fallback and the response exposes the source mode.
    """
    selected, mode = select_employee_rows(rows)
    return [dict(row) for row in selected], mode


def fetch_company_people(
    company: dict[str, str],
    year: str,
    report_code: str,
    *,
    budget: DARTRequestBudget | None = None,
) -> dict[str, Any]:
    base = {"company": company, "year": year, "report_code": report_code}
    employee_rows: list[dict[str, Any]] = []
    executive_rows: list[dict[str, Any]] = []
    unregistered_pay_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        employee_payload = _budgeted_dart_request(
            "empSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
            budget,
        )
        employee_rows = _dart_list_rows(employee_payload, "employee_status")
    except DARTError as exc:
        errors.append({"source": "employee_status", "message": str(exc)})
    try:
        executive_payload = _budgeted_dart_request(
            "exctvSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
            budget,
        )
        executive_rows = _dart_list_rows(executive_payload, "executive_status")
    except DARTError as exc:
        errors.append({"source": "executive_status", "message": str(exc)})
    try:
        unregistered_pay_payload = _budgeted_dart_request(
            "unrstExctvMendngSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
            budget,
        )
        unregistered_pay_rows = _dart_list_rows(
            unregistered_pay_payload,
            "unregistered_executive_pay",
        )
    except DARTError as exc:
        errors.append({"source": "unregistered_executive_pay", "message": str(exc)})

    selected_rows, aggregation_mode = _employee_summary_rows(employee_rows)
    employee_breakdown = [
        {
            "sex": _clean_text(row.get("sexdstn")) or None,
            "business_unit": _clean_text(row.get("fo_bbm")) or None,
            "regular": _people_count(row.get("rgllbr_co")),
            "contract": _people_count(row.get("cnttk_co")),
            "total": _people_count(row.get("sm")),
            "average_tenure": _people_tenure_years(row.get("avrg_cnwk_sdytrn")),
            "annual_salary_total": _people_number(row.get("fyer_salary_totamt")),
            "average_salary": _people_number(row.get("jan_salary_am")),
        }
        for row in selected_rows
    ]

    workforce_summary = build_workforce_summary(
        employee_rows=employee_rows,
        executive_rows=executive_rows,
        unregistered_pay_rows=unregistered_pay_rows,
        as_of=_report_as_of(year, report_code),
    )
    receipts = sorted({
        str(row.get("rcept_no") or "").strip()
        for rows in (employee_rows, executive_rows, unregistered_pay_rows)
        for row in rows
        if re.fullmatch(r"\d{14}", str(row.get("rcept_no") or "").strip())
    })
    component_receipts = {
        "employee_status": sorted({
            str(row.get("rcept_no") or "").strip()
            for row in employee_rows
            if re.fullmatch(r"\d{14}", str(row.get("rcept_no") or "").strip())
        }),
        "executive_status": sorted({
            str(row.get("rcept_no") or "").strip()
            for row in executive_rows
            if re.fullmatch(r"\d{14}", str(row.get("rcept_no") or "").strip())
        }),
        "unregistered_executive_pay": sorted({
            str(row.get("rcept_no") or "").strip()
            for row in unregistered_pay_rows
            if re.fullmatch(r"\d{14}", str(row.get("rcept_no") or "").strip())
        }),
    }
    result = {
        **base,
        "people": {
            "employee_row_count": len(employee_rows),
            "employee_aggregation": aggregation_mode,
            "average_salary_basis": workforce_summary["metric_basis"]["average_salary"],
            **workforce_summary["metrics"],
        },
        "workforce_quality": workforce_summary["quality"],
        "component_quality": workforce_summary["component_quality"],
        "_raw_employee_rows": employee_rows,
        "_raw_executive_rows": executive_rows,
        "_raw_unregistered_pay_rows": unregistered_pay_rows,
        "executive_metrics": {
            key: value
            for key, value in workforce_summary["metrics"].items()
            if key in {
                "executives_total",
                "registered_executives",
                "unregistered_executives",
                "inside_directors",
                "outside_directors",
                "ceo_count",
                "full_time_executives",
                "part_time_executives",
                "female_executives",
                "average_tenure_months",
                "long_tenure_executives",
                "term_expiring_within_12_months",
                "registered_share",
                "outside_director_share",
                "female_share",
            }
        },
        "employee_breakdown": employee_breakdown,
        "executives": executive_rows,
        "unregistered_pay_breakdown": [
            {
                "category": _unregistered_pay_category(row.get("se")),
                "count": _people_count(row.get("nmpr")),
                "annual_salary_total": _people_number(row.get("fyer_salary_totamt")),
                "average_salary": _people_number(row.get("jan_salary_am")),
            }
            for row in unregistered_pay_rows
        ],
        "source_urls": [
            f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"
            for receipt in receipts
        ],
        "source_by_component": {
            component: [
                f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"
                for receipt in component_values
            ]
            for component, component_values in component_receipts.items()
        },
    }
    if errors:
        result["errors"] = errors
    if not employee_rows and not executive_rows and not unregistered_pay_rows:
        result["error"] = "직원·임원 현황 공시 데이터가 없습니다."
    return result


def selected_companies(codes: list[str]) -> list[dict[str, str]]:
    if len(codes) != len(set(codes)):
        raise ValueError("기업 코드는 중복해서 선택할 수 없습니다.")
    companies = {company["corp_code"]: company for company in load_corp_codes()}
    selected = [companies[code] for code in codes if code in companies]
    if len(selected) != len(codes):
        raise ValueError("선택한 기업 코드 중 존재하지 않는 코드가 포함되어 있습니다.")
    return selected


def _financial_pipeline_failure(
    company: dict[str, str],
    year: str,
    report_code: str,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "company": company,
        "year": year,
        "report_code": report_code,
        "financials": None,
        "error": f"Financial pipeline failed ({type(exc).__name__}).",
    }


def _people_pipeline_failure(
    company: dict[str, str],
    year: str,
    report_code: str,
    exc: Exception,
) -> dict[str, Any]:
    message = f"People pipeline failed ({type(exc).__name__})."
    return {
        "company": company,
        "year": year,
        "report_code": report_code,
        "errors": [{"source": "people_pipeline", "message": message}],
        "error": "People pipeline failed.",
    }


def _submit_with_budget(
    executor: ThreadPoolExecutor,
    function: Callable[..., Any],
    *args: Any,
    budget: DARTRequestBudget | None,
) -> Any:
    if budget is None:
        return executor.submit(function, *args)
    return executor.submit(function, *args, budget=budget)


def fetch_financial_results(
    codes: list[str],
    year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(MAX_COMPANIES, len(selected))) as executor:
        futures = {
            _submit_with_budget(
                executor,
                fetch_company_financials,
                company,
                year,
                report_code,
                budget=budget,
            ): company
            for company in selected
        }
        for future in as_completed(futures):
            company = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(_financial_pipeline_failure(company, year, report_code, exc))
    results.sort(key=lambda item: codes.index(item["company"]["corp_code"]))
    return results


def fetch_history_results(
    codes: list[str],
    from_year: str,
    to_year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    enforce_history_observation_budget(
        codes,
        int(from_year),
        int(to_year),
        maximum=MAX_FINANCIAL_HISTORY_OBSERVATIONS,
    )
    selected = selected_companies(codes)
    jobs = [(company, str(year)) for company in selected for year in range(int(from_year), int(to_year) + 1)]
    by_code: dict[str, dict[str, Any]] = {company["corp_code"]: {"company": company, "years": []} for company in selected}
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as executor:
        futures = {
            _submit_with_budget(
                executor,
                fetch_company_financials,
                company,
                year,
                report_code,
                budget=budget,
            ): (company, year)
            for company, year in jobs
        }
        for future in as_completed(futures):
            company, year = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = _financial_pipeline_failure(company, year, report_code, exc)
            by_code[result["company"]["corp_code"]]["years"].append(result)
    history = list(by_code.values())
    for item in history:
        item["years"].sort(key=lambda value: int(value.get("year", from_year)))
    return history


def fetch_people_results(
    codes: list[str],
    year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    with ThreadPoolExecutor(max_workers=min(MAX_COMPANIES, len(selected))) as executor:
        futures = {
            _submit_with_budget(
                executor,
                fetch_company_people,
                company,
                year,
                report_code,
                budget=budget,
            ): company
            for company in selected
        }
        results = []
        for future in as_completed(futures):
            company = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(_people_pipeline_failure(company, year, report_code, exc))
    results.sort(key=lambda item: codes.index(item["company"]["corp_code"]))
    return [_public_people_result(item) for item in results]


def fetch_people_history_results(
    codes: list[str],
    from_year: str,
    to_year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    enforce_history_observation_budget(
        codes,
        int(from_year),
        int(to_year),
        maximum=MAX_PEOPLE_HISTORY_OBSERVATIONS,
    )
    selected = selected_companies(codes)
    jobs = [(company, str(year)) for company in selected for year in range(int(from_year), int(to_year) + 1)]
    by_code: dict[str, dict[str, Any]] = {company["corp_code"]: {"company": company, "years": []} for company in selected}
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as executor:
        futures = {
            _submit_with_budget(
                executor,
                fetch_company_people,
                company,
                year,
                report_code,
                budget=budget,
            ): (company, year)
            for company, year in jobs
        }
        for future in as_completed(futures):
            company, year = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = _people_pipeline_failure(company, year, report_code, exc)
            by_code[result["company"]["corp_code"]]["years"].append(result)
    history = list(by_code.values())
    for item in history:
        item["years"].sort(key=lambda value: int(value.get("year", from_year)))
        item["years"] = [_public_people_result(value) for value in item["years"]]
    return history


def _public_people_result(item: dict[str, Any]) -> dict[str, Any]:
    """Remove personal executive rows from the regular People API response."""

    result = dict(item)
    result.pop("executives", None)
    result.pop("_raw_employee_rows", None)
    result.pop("_raw_executive_rows", None)
    result.pop("_raw_unregistered_pay_rows", None)
    return result


def fetch_workforce_observations(
    codes: list[str],
    year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[WorkforceObservation]:
    """Fetch DART rows once and convert them into orchestration inputs."""

    selected = selected_companies(codes)
    people_by_code: dict[str, dict[str, Any]] = {}
    financials_by_code: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(selected) * 2))) as executor:
        people_futures = {
            _submit_with_budget(
                executor,
                fetch_company_people,
                company,
                year,
                report_code,
                budget=budget,
            ): company
            for company in selected
        }
        financial_futures = {
            _submit_with_budget(
                executor,
                fetch_company_financials,
                company,
                year,
                report_code,
                budget=budget,
            ): company
            for company in selected
        }
        for future in as_completed(people_futures):
            company = people_futures[future]
            try:
                people_by_code[company["corp_code"]] = future.result()
            except Exception as exc:
                people_by_code[company["corp_code"]] = _people_pipeline_failure(
                    company, year, report_code, exc
                )
        for future in as_completed(financial_futures):
            company = financial_futures[future]
            try:
                financials_by_code[company["corp_code"]] = future.result()
            except Exception as exc:
                financials_by_code[company["corp_code"]] = _financial_pipeline_failure(
                    company, year, report_code, exc
                )

    observations: list[WorkforceObservation] = []
    for company in selected:
        code = company["corp_code"]
        people = people_by_code.get(code, {})
        financial = financials_by_code.get(code, {})
        errors = list(people.get("errors") or [])
        if financial.get("error"):
            errors.append({"source": "financial_status", "message": financial["error"]})
        source_urls = list(people.get("source_urls") or [])
        if financial.get("source_url"):
            source_urls.append(financial["source_url"])
        source_by_component = dict(people.get("source_by_component") or {})
        source_by_component["financial_status"] = (
            [financial["source_url"]] if financial.get("source_url") else []
        )
        observations.append(WorkforceObservation(
            company=company,
            year=year,
            report_code=report_code,
            employee_rows=people.get("_raw_employee_rows") or (),
            executive_rows=people.get("_raw_executive_rows") or (),
            unregistered_pay_rows=people.get("_raw_unregistered_pay_rows") or (),
            financials=financial.get("financials") or {},
            source_urls=source_urls,
            source_by_component=source_by_component,
            errors=errors,
        ))
    return observations


def _executive_only_result(item: dict[str, Any]) -> dict[str, Any]:
    """Return executive analytics without exposing personal executive rows."""

    component_quality = item.get("component_quality") or {}
    result = {
        "company": item.get("company"),
        "year": item.get("year"),
        "report_code": item.get("report_code"),
        "executive_metrics": item.get("executive_metrics") or {},
        "quality": component_quality.get("executives") or {},
        "source_urls": item.get("source_urls") or [],
    }
    if item.get("errors"):
        result["errors"] = [
            error for error in item["errors"]
            if error.get("source") == "executive_status"
        ]
    if item.get("error"):
        result["error"] = item["error"]
    return result


def fetch_executive_results(
    codes: list[str],
    year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    return [
        _executive_only_result(item)
        for item in fetch_people_results(codes, year, report_code, budget)
    ]


def fetch_executive_history_results(
    codes: list[str],
    from_year: str,
    to_year: str,
    report_code: str,
    budget: DARTRequestBudget | None = None,
) -> list[dict[str, Any]]:
    history = fetch_people_history_results(
        codes,
        from_year,
        to_year,
        report_code,
        budget,
    )
    return [
        {
            "company": item.get("company"),
            "years": [_executive_only_result(year) for year in item.get("years", [])],
        }
        for item in history
    ]


def analysis_request_from_payload(payload: dict[str, Any]) -> AnalysisRequest:
    raw_codes = payload.get("corp_codes", ())
    if isinstance(raw_codes, str):
        raw_codes = raw_codes.split(",")
    elif not isinstance(raw_codes, (list, tuple)):
        raise ValueError("corp_codes는 문자열 또는 배열이어야 합니다.")
    raw_metrics = payload.get("metric_ids", ())
    if isinstance(raw_metrics, str):
        raw_metrics = raw_metrics.split(",")
    elif not isinstance(raw_metrics, (list, tuple)):
        raise ValueError("metric_ids는 문자열 또는 배열이어야 합니다.")
    try:
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 40))
    except (TypeError, ValueError) as exc:
        raise ValueError("page와 page_size는 숫자여야 합니다.") from exc
    sort_by = str(payload.get("sort_by") or "")
    sort_direction = str(payload.get("sort_direction") or "desc")
    return AnalysisRequest(
        question=str(payload.get("question") or DEFAULT_HR_ANALYSIS_QUESTION),
        view=str(payload.get("view") or "overview"),
        corp_codes=tuple(str(code).strip() for code in raw_codes if str(code).strip()),
        year=payload.get("year"),
        from_year=payload.get("from_year"),
        to_year=payload.get("to_year"),
        report_code=payload.get("report_code") or "11011",
        metric_ids=tuple(str(metric).strip() for metric in raw_metrics if str(metric).strip()),
        sort={"by": sort_by or None, "direction": sort_direction},
        page=page,
        page_size=page_size,
    )


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded localhost server that never shares a listening port."""

    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Ignore expected client disconnects without hiding server failures."""

        error = sys.exc_info()[1]
        if isinstance(
            error,
            (BrokenPipeError, ConnectionAbortedError, ConnectionResetError),
        ):
            return
        super().handle_error(request, client_address)


def _application_identity(server: Any | None = None) -> dict[str, Any]:
    port = PORT
    address = getattr(server, "server_address", None)
    if isinstance(address, tuple) and len(address) >= 2:
        try:
            candidate = int(address[1])
        except (TypeError, ValueError):
            candidate = PORT
        if 1 <= candidate <= 65535:
            port = candidate
    return {
        "id": APP_ID,
        "name": APP_NAME,
        "version": APP_VERSION,
        "build_id": BUILD_ID,
        "instance_id": INSTANCE_ID,
        "port": port,
    }


def _port_conflict(exc: OSError) -> bool:
    return exc.errno in {errno.EACCES, errno.EADDRINUSE, 10013, 10048} or getattr(
        exc, "winerror", None
    ) in {10013, 10048}


def _fallback_ports(preferred_port: int) -> tuple[int, ...]:
    candidates = [preferred_port]
    for offset in range(1, MAX_PORT_FALLBACK_ATTEMPTS + 1):
        candidate = preferred_port + offset
        if candidate <= 65535:
            candidates.append(candidate)
    candidates.append(0)
    return tuple(candidates)


def create_local_http_server(
    handler_class: type[BaseHTTPRequestHandler],
    *,
    preferred_port: int,
    allow_fallback: bool,
) -> ExclusiveThreadingHTTPServer:
    ports = _fallback_ports(preferred_port) if allow_fallback else (preferred_port,)
    last_conflict: OSError | None = None
    for candidate in ports:
        try:
            return ExclusiveThreadingHTTPServer(("127.0.0.1", candidate), handler_class)
        except OSError as exc:
            if not _port_conflict(exc):
                raise
            last_conflict = exc
    message = (
        f"127.0.0.1:{preferred_port} 포트를 사용할 수 없습니다. "
        "해당 포트를 사용 중인 프로그램을 종료하거나 PORT 값을 변경해 주세요."
    )
    raise OSError(getattr(last_conflict, "errno", errno.EADDRINUSE), message) from last_conflict


def _health_matches_instance(payload: Any, *, instance_id: str) -> bool:
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        return False
    app = payload.get("app")
    return (
        isinstance(app, Mapping)
        and app.get("id") == APP_ID
        and app.get("instance_id") == instance_id
    )


def open_browser_when_ready(
    base_url: str,
    *,
    instance_id: str,
    timeout_seconds: float = 8.0,
    opener: Any | None = None,
    browser_open: Any | None = None,
) -> bool:
    """Open only after the bound URL identifies this exact server instance."""

    fetch = opener or urlopen
    launch = browser_open or webbrowser.open
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    health_url = f"{base_url}/api/health"
    while time.monotonic() < deadline:
        try:
            request = Request(
                health_url,
                headers={"User-Agent": "dart-workforce-startup/1.0"},
            )
            with fetch(request, timeout=1.0) as response:
                raw = response.read(MAX_HEALTH_RESPONSE_BYTES + 1)
            if len(raw) <= MAX_HEALTH_RESPONSE_BYTES:
                payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite_json)
                if _health_matches_instance(payload, instance_id=instance_id):
                    launch(base_url)
                    return True
        except (OSError, TimeoutError, URLError, UnicodeDecodeError, ValueError, RecursionError):
            pass
        time.sleep(0.05)
    print(
        f"DART HR Briefing 시작 확인 실패: {base_url}",
        file=sys.stderr,
    )
    return False


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "DARTWorkforceIntelligence"
    sys_version = ""

    def version_string(self) -> str:
        return self.server_version

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(
        self,
        payload: dict[str, Any],
        status: int = HTTPStatus.OK,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        request_id = self.request_correlation_id()
        if int(status) >= 400 and "request_id" not in payload:
            payload = {**payload, "request_id": request_id}
        try:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError):
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            headers = None
            payload = {
                "error": "서버 응답을 안전한 JSON으로 직렬화하지 못했습니다.",
                "request_id": request_id,
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Strict-Transport-Security", HSTS_HEADER)
        self.send_header("X-Request-ID", request_id)
        for key, value in (headers or {}).items():
            self.send_header(str(key), str(value))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def request_correlation_id(self) -> str:
        request_id = getattr(self, "_request_id", "")
        if not request_id:
            request_id = secrets.token_hex(8)
            self._request_id = request_id
        return request_id

    def log_internal_error(self, exc: Exception) -> None:
        try:
            path = urlparse(getattr(self, "path", "")).path or "unknown"
        except ValueError:
            path = "invalid"
        print(
            f"[{self.request_correlation_id()}] internal_error "
            f"type={type(exc).__name__} path={path}",
            file=sys.stderr,
        )

    def record_orchestration_telemetry(self, result: Mapping[str, Any]) -> None:
        try:
            ORCHESTRATION_TELEMETRY.record(result)
        except Exception as exc:
            print(
                f"[{self.request_correlation_id()}] telemetry_error "
                f"type={type(exc).__name__}",
                file=sys.stderr,
            )

    def rate_limit_key(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        remote = ""
        client_address = getattr(self, "client_address", None)
        if isinstance(client_address, tuple) and client_address:
            remote = str(client_address[0])
        source = forwarded if DEPLOYED_ON_VERCEL and forwarded else remote or "unknown"
        return anonymized_client_key(source, salt=RATE_LIMIT_SALT)

    def enforce_rate_limit(self) -> bool:
        decision = REQUEST_RATE_LIMITER.allow(self.rate_limit_key())
        if decision.allowed:
            return True
        self.send_json(
            {
                "error": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                "retry_after_seconds": decision.retry_after_seconds,
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
        return False

    def origin_allowed(self) -> bool:
        request_host = self.headers.get("Host", "").strip().lower()
        try:
            request_host_parts = urlparse(f"//{request_host}")
            request_hostname = request_host_parts.hostname
            # Accessing ``port`` validates both its syntax and range.
            request_host_parts.port
        except ValueError:
            return False
        if (
            not request_host
            or not request_hostname
            or request_host_parts.username is not None
            or request_host_parts.password is not None
            or request_host_parts.path
            or request_host_parts.query
            or request_host_parts.fragment
        ):
            return False
        local_hosts = {"127.0.0.1", "localhost", "::1"}
        if not DEPLOYED_ON_VERCEL and request_hostname not in local_hosts:
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site", "").strip().lower()
        if fetch_site and fetch_site not in {"same-origin", "same-site", "none"}:
            try:
                navigation_path = urlparse(_effective_request_target(self.path)).path
            except (AttributeError, ValueError):
                return False
            is_root_document_navigation = (
                fetch_site == "cross-site"
                and getattr(self, "command", "").upper() in {"GET", "HEAD"}
                and self.headers.get("Sec-Fetch-Mode", "").strip().lower() == "navigate"
                and self.headers.get("Sec-Fetch-Dest", "").strip().lower() == "document"
                and navigation_path == "/"
            )
            if not is_root_document_navigation:
                return False
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return True
        try:
            origin_parts = urlparse(origin)
            origin_parts.port
        except ValueError:
            return False
        if (
            origin_parts.username is None
            and origin_parts.password is None
            and not origin_parts.path
            and not origin_parts.params
            and not origin_parts.query
            and not origin_parts.fragment
            and origin_parts.netloc.lower() == request_host
            and origin_parts.scheme in {"http", "https"}
        ):
            return True
        return False

    def read_json_body(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("요청 Content-Type은 application/json이어야 합니다.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError) as exc:
            raise MalformedContentLength(
                "Content-Length 헤더 형식이 올바르지 않습니다."
            ) from exc
        if length <= 0 or length > 2_000_000:
            raise ValueError("요청 본문이 비어 있거나 너무 큽니다.")
        raw = self.rfile.read(length)
        payload = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_nonfinite_json,
        )
        if not isinstance(payload, dict):
            raise ValueError("요청 본문은 JSON 객체여야 합니다.")
        return payload

    def request_openai_provider(self) -> OpenAIResponsesProvider | None:
        api_key = self.headers.get("X-OpenAI-API-Key", "")
        return user_openai_provider(api_key) if api_key.strip() else None

    def request_operator_ai_provider(self) -> Any | None:
        """Return the operator-funded provider only across an explicit auth boundary."""

        if (
            not ALLOW_OPERATOR_AI_PROVIDER
            or not _valid_operator_ai_token(OPERATOR_AI_TOKEN)
            or not getattr(WORKFORCE_AI_PROVIDER, "configured", False)
        ):
            return None
        supplied = self.headers.get("X-DART-Operator-Token", "").strip()
        if not _valid_operator_ai_token(supplied):
            return None
        return (
            WORKFORCE_AI_PROVIDER
            if secrets.compare_digest(supplied, OPERATOR_AI_TOKEN)
            else None
        )

    def do_POST(self) -> None:
        self._request_id = secrets.token_hex(8)
        if not self.origin_allowed():
            self.send_json({"error": "허용되지 않은 Origin입니다."}, HTTPStatus.FORBIDDEN)
            return
        try:
            try:
                parsed = urlparse(_effective_request_target(self.path))
            except ValueError as exc:
                raise ValueError("요청 경로가 올바르지 않습니다.") from exc
            if parsed.path not in {"/api/analysis", "/api/analysis/context", "/api/ai/connect"}:
                self.send_json({"error": "POST 경로를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
                return
            if parsed.path in RATE_LIMITED_POST_PATHS and not self.enforce_rate_limit():
                return
            if parsed.path == "/api/ai/connect":
                provider = self.request_openai_provider()
                if provider is None:
                    raise ValueError("OpenAI API Key를 입력해 주세요.")
                provider.validate_connection()
                self.send_json({
                    "ok": True,
                    "provider": provider.provider_id,
                    "provider_name": provider.provider_label,
                    "model": provider.model,
                    "stored": False,
                })
                return
            payload = self.read_json_body()
            request = analysis_request_from_payload(payload)
            if not request.corp_codes or len(request.corp_codes) > MAX_COMPANIES:
                self.send_json({"error": f"비교 기업은 1~{MAX_COMPANIES}개까지 선택해 주세요."}, HTTPStatus.BAD_REQUEST)
                return
            if request.report_code not in {"11011", "11012", "11013", "11014"}:
                self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                return
            if request.view not in ALLOWED_REQUEST_VIEWS:
                self.send_json({"error": "분석 화면 값이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                return
            unknown_metrics = sorted(set(request.metric_ids) - ALLOWED_REQUEST_METRICS)
            if unknown_metrics:
                self.send_json({"error": "분석 지표 값이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                return
            if request.from_year or request.to_year:
                self.send_json(
                    {
                        "error": (
                            "연도 범위 AI 분석은 evidence ledger 기반 v2가 준비될 때까지 "
                            "비활성화되어 있습니다. 단일 연도를 선택해 주세요."
                        ),
                        "error_code": "range_ai_requires_orchestration_v2",
                    },
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            year = request.year or str(time.localtime().tm_year - 1)
            if not re.fullmatch(r"20\d{2}", year):
                self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                return
            request = replace(request, year=year)
            provider = (
                None
                if parsed.path == "/api/analysis/context"
                else self.request_openai_provider() or self.request_operator_ai_provider()
            )
            if provider is not None and payload.get("provider_data_consent") is not True:
                self.send_json(
                    {
                        "error": (
                            "질문과 공개 기업 집계의 AI provider 전송 안내에 "
                            "동의한 뒤 다시 실행해 주세요."
                        ),
                        "error_code": "provider_data_consent_required",
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return
            budget = new_dart_request_budget()
            observations = fetch_workforce_observations(
                list(request.corp_codes),
                year,
                request.report_code,
                budget,
            )
            response = WorkforceAgentOrchestrator(provider=provider).run(
                observations,
                request_context={
                    "question": request.question,
                    "view": request.view,
                    "metric_ids": request.metric_ids,
                },
            )
            response["selection"] = {
                "count": len(request.corp_codes),
                "max": MAX_COMPANIES,
            }
            response["source"] = "OpenDART"
            response["evidence"]["reference_mode"] = "opendart_receipt"
            response["evidence"]["external_source_links"] = True
            response["evidence"]["source_notice"] = (
                "OpenDART 공시 접수번호로 검증할 수 있는 원문 링크입니다."
            )
            validate_orchestration_response(response)
            self.record_orchestration_telemetry(response)
            self.send_json(response)
        except MalformedContentLength as exc:
            self.log_internal_error(exc)
            self.send_json(
                {"error": "Content-Length 헤더 형식이 올바르지 않습니다."},
                HTTPStatus.BAD_REQUEST,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except DARTError as exc:
            self.log_internal_error(exc)
            self.send_json(
                {"error": "OpenDART API에 연결하지 못했습니다."},
                HTTPStatus.BAD_GATEWAY,
            )
        except OpenAIResponsesError as exc:
            self.log_internal_error(exc)
            self.send_json(
                {"error": "OpenAI API에 연결하지 못했습니다."},
                HTTPStatus.BAD_GATEWAY,
            )
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
        except Exception as exc:
            self.log_internal_error(exc)
            self.send_json({"error": "서버 처리 중 오류가 발생했습니다."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_HEAD(self) -> None:
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_GET(self) -> None:
        self._request_id = secrets.token_hex(8)
        if not self.origin_allowed():
            self.send_json({"error": "허용되지 않은 Origin입니다."}, HTTPStatus.FORBIDDEN)
            return
        try:
            try:
                parsed = urlparse(_effective_request_target(self.path))
            except ValueError as exc:
                raise ValueError("요청 경로가 올바르지 않습니다.") from exc
            if parsed.path in RATE_LIMITED_GET_PATHS and not self.enforce_rate_limit():
                return
            if parsed.path == "/api/health":
                self.send_json({
                    "ok": True,
                    "app": _application_identity(getattr(self, "server", None)),
                    "api_key_configured": len(API_KEY) == 40,
                    "strict_schema_enabled": STRICT_ORCHESTRATION_SCHEMA,
                    "strict_schema_validator_ready": (
                        not STRICT_ORCHESTRATION_SCHEMA
                        or _ORCHESTRATION_VALIDATOR is not None
                    ),
                    "classroom_sample": {
                        "available": True,
                        "endpoint": "/api/classroom/bootstrap",
                        "network_requests": 0,
                    },
                    "ai_provider_configured": bool(getattr(ACTIVE_AI_PROVIDER, "configured", False)),
                    "ai_provider": getattr(ACTIVE_AI_PROVIDER, "provider_id", "not_configured"),
                    "ai_provider_name": getattr(ACTIVE_AI_PROVIDER, "provider_label", type(ACTIVE_AI_PROVIDER).__name__),
                    "operator_ai_access": {
                        "enabled": ALLOW_OPERATOR_AI_PROVIDER,
                        "authentication_required": True,
                        "ready": bool(
                            ALLOW_OPERATOR_AI_PROVIDER
                            and _valid_operator_ai_token(OPERATOR_AI_TOKEN)
                            and getattr(WORKFORCE_AI_PROVIDER, "configured", False)
                        ),
                    },
                    "runtime": {
                        "dart_cache": {
                            **DART_RESPONSE_CACHE.stats(),
                            "scope": "per_process",
                        },
                        "rate_limiter": {
                            **REQUEST_RATE_LIMITER.stats(),
                            "scope": "per_process",
                            "distributed_enforcement": False,
                        },
                        "orchestration_telemetry": {
                            **ORCHESTRATION_TELEMETRY.stats(),
                            "scope": "per_process",
                        },
                        "outbound_deadline": {
                            "attempt_timeout_seconds": DART_REQUEST_TIMEOUT_SECONDS,
                            "retry_attempts": DART_RETRY_ATTEMPTS,
                            "shared_deadline_seconds": DART_OUTBOUND_DEADLINE_SECONDS,
                            "max_attempts_per_request": DART_OUTBOUND_ATTEMPT_BUDGET,
                            "cache_hits_consume_attempts": False,
                            "people_endpoints_per_company": 3,
                        },
                    },
                })
                return
            if parsed.path == "/api/metadata":
                current_year = time.localtime().tm_year
                self.send_json({
                    "max_companies": MAX_COMPANIES,
                    "years": list(range(current_year - 1, 2014, -1)),
                    "reports": [
                        {"code": "11011", "label": "사업보고서"},
                        {"code": "11012", "label": "반기보고서"},
                        {"code": "11013", "label": "1분기보고서"},
                        {"code": "11014", "label": "3분기보고서"},
                    ],
                    "metrics": DART_METRIC_CATALOG,
                    "people_metrics": PEOPLE_METRIC_CATALOG,
                    "executive_metrics": EXECUTIVE_METRIC_CATALOG,
                    "decision_metrics": DECISION_METRIC_CATALOG,
                    "decision_dimensions": DECISION_DIMENSION_CATALOG,
                    "views": sorted(ALLOWED_REQUEST_VIEWS),
                    "source": "OpenDART",
                    "classroom_sample_available": True,
                })
                return
            if parsed.path == "/api/classroom/bootstrap":
                payload = build_classroom_payload()
                validate_orchestration_response(payload["orchestration"])
                self.record_orchestration_telemetry(payload["orchestration"])
                self.send_json(payload)
                return
            if parsed.path == "/api/companies":
                query = parse_qs(parsed.query).get("q", [""])[0]
                self.send_json({"companies": search_companies(query)})
                return
            if parsed.path == "/api/financials/history":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                from_year = params.get("from_year", [str(time.localtime().tm_year - 5)])[0]
                to_year = params.get("to_year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > 8:
                    self.send_json({"error": "추이를 조회할 기업은 1~8개까지 선택해주세요."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", from_year) or not re.fullmatch(r"20\d{2}", to_year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                start_year, end_year = int(from_year), int(to_year)
                if start_year > end_year or end_year - start_year > 10:
                    self.send_json({"error": "추이 조회 범위는 최대 11개 연도입니다."}, HTTPStatus.BAD_REQUEST)
                    return
                enforce_history_observation_budget(
                    codes,
                    start_year,
                    end_year,
                    maximum=MAX_FINANCIAL_HISTORY_OBSERVATIONS,
                )
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                history = fetch_history_results(
                    codes,
                    from_year,
                    to_year,
                    report_code,
                    budget,
                )
                self.send_json({"from_year": from_year, "to_year": to_year, "report_code": report_code, "results": history})
                return
            if parsed.path == "/api/workforce/orchestration":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                year = params.get("year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > MAX_COMPANIES:
                    self.send_json({"error": f"기업은 1~{MAX_COMPANIES}개까지 선택할 수 있습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 코드가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                observations = fetch_workforce_observations(
                    codes,
                    year,
                    report_code,
                    budget,
                )
                result = WorkforceAgentOrchestrator(provider=None).run(observations)
                result["selection"] = {"count": len(codes), "max": MAX_COMPANIES}
                result["source"] = "OpenDART"
                result["evidence"]["reference_mode"] = "opendart_receipt"
                result["evidence"]["external_source_links"] = True
                result["evidence"]["source_notice"] = (
                    "OpenDART 공시 접수번호로 검증할 수 있는 원문 링크입니다."
                )
                validate_orchestration_response(result)
                self.record_orchestration_telemetry(result)
                self.send_json(result)
                return
            if parsed.path == "/api/executives/history":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                from_year = params.get("from_year", [str(time.localtime().tm_year - 5)])[0]
                to_year = params.get("to_year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > MAX_COMPANIES:
                    self.send_json({"error": f"기업은 1~{MAX_COMPANIES}개까지 선택할 수 있습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", from_year) or not re.fullmatch(r"20\d{2}", to_year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                start_year, end_year = int(from_year), int(to_year)
                if start_year > end_year or end_year - start_year > 10:
                    self.send_json({"error": "조회 기간은 최대 11개 연도입니다."}, HTTPStatus.BAD_REQUEST)
                    return
                enforce_history_observation_budget(
                    codes,
                    start_year,
                    end_year,
                    maximum=MAX_PEOPLE_HISTORY_OBSERVATIONS,
                )
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 코드가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                self.send_json({
                    "from_year": from_year,
                    "to_year": to_year,
                    "report_code": report_code,
                    "results": fetch_executive_history_results(
                        codes,
                        from_year,
                        to_year,
                        report_code,
                        budget,
                    ),
                })
                return
            if parsed.path == "/api/executives":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                year = params.get("year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > MAX_COMPANIES:
                    self.send_json({"error": f"기업은 1~{MAX_COMPANIES}개까지 선택할 수 있습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", year) or report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "연도 또는 보고서 코드가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                self.send_json({
                    "year": year,
                    "report_code": report_code,
                    "results": fetch_executive_results(
                        codes,
                        year,
                        report_code,
                        budget,
                    ),
                })
                return
            if parsed.path == "/api/people/history":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                from_year = params.get("from_year", [str(time.localtime().tm_year - 5)])[0]
                to_year = params.get("to_year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > MAX_COMPANIES:
                    self.send_json({"error": f"People 추이를 조회할 기업은 1~{MAX_COMPANIES}개까지 선택해주세요."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", from_year) or not re.fullmatch(r"20\d{2}", to_year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                start_year, end_year = int(from_year), int(to_year)
                if start_year > end_year or end_year - start_year > 10:
                    self.send_json({"error": "People 추이 조회 범위는 최대 11개 연도입니다."}, HTTPStatus.BAD_REQUEST)
                    return
                enforce_history_observation_budget(
                    codes,
                    start_year,
                    end_year,
                    maximum=MAX_PEOPLE_HISTORY_OBSERVATIONS,
                )
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                self.send_json({
                    "from_year": from_year,
                    "to_year": to_year,
                    "report_code": report_code,
                    "results": fetch_people_history_results(
                        codes,
                        from_year,
                        to_year,
                        report_code,
                        budget,
                    ),
                })
                return
            if parsed.path == "/api/people":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                year = params.get("year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > MAX_COMPANIES:
                    self.send_json({"error": f"People을 조회할 기업은 1~{MAX_COMPANIES}개까지 선택해주세요."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", year) or report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "연도 또는 보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                self.send_json({
                    "year": year,
                    "report_code": report_code,
                    "results": fetch_people_results(
                        codes,
                        year,
                        report_code,
                        budget,
                    ),
                })
                return
            if parsed.path == "/api/financials":
                params = parse_qs(parsed.query)
                raw_codes = params.get("corp_codes", [""])[0]
                year = params.get("year", [str(time.localtime().tm_year - 1)])[0]
                report_code = params.get("report_code", ["11011"])[0]
                codes = [code.strip() for code in raw_codes.split(",") if code.strip()]
                if not codes or len(codes) > 8:
                    self.send_json({"error": "비교할 기업을 1~8개 선택해주세요."}, HTTPStatus.BAD_REQUEST)
                    return
                if not re.fullmatch(r"20\d{2}", year) or report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "연도 또는 보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                budget = new_dart_request_budget()
                results = fetch_financial_results(
                    codes,
                    year,
                    report_code,
                    budget,
                )
                self.send_json({"year": year, "report_code": report_code, "results": results})
                return
            if parsed.path == "/" or parsed.path == "/index.html":
                self.serve_static("index.html", "text/html; charset=utf-8")
                return
            if parsed.path.startswith("/static/"):
                relative = parsed.path.removeprefix("/static/")
                self.serve_static(relative)
                return
            self.send_json({"error": "페이지를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        except DARTError as exc:
            self.log_internal_error(exc)
            self.send_json(
                {"error": "OpenDART API에 연결하지 못했습니다."},
                HTTPStatus.BAD_GATEWAY,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
        except Exception as exc:
            self.log_internal_error(exc)
            self.send_json({"error": "서버 처리 중 오류가 발생했습니다."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, relative: str, content_type: str | None = None) -> None:
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_json({"error": "잘못된 파일 경로입니다."}, HTTPStatus.BAD_REQUEST)
            return
        if not target.exists() or not target.is_file():
            self.send_json({"error": "파일을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
            return
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or types.get(target.suffix, "application/octet-stream"))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Strict-Transport-Security", HSTS_HEADER)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Request-ID", self.request_correlation_id())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)


def run_local_server() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    http_server = create_local_http_server(
        DashboardHandler,
        preferred_port=PORT,
        allow_fallback=not PORT_EXPLICITLY_CONFIGURED,
    )
    actual_port = int(http_server.server_address[1])
    base_url = f"http://127.0.0.1:{actual_port}"
    print(
        f"{APP_NAME} {APP_VERSION} ({BUILD_ID}): {base_url}",
        flush=True,
    )
    if OPEN_BROWSER_ON_START:
        threading.Thread(
            target=open_browser_when_ready,
            kwargs={"base_url": base_url, "instance_id": INSTANCE_ID},
            daemon=True,
            name="dart-browser-launch",
        ).start()
    try:
        http_server.serve_forever()
    finally:
        http_server.server_close()


def _show_startup_error(message: str) -> None:
    if os.name != "nt" or not FROZEN_RUNTIME:
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except (AttributeError, OSError):
        pass


def main() -> int:
    try:
        run_local_server()
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        message = f"{APP_NAME}을 시작하지 못했습니다.\n\n{exc}"
        print(message, file=sys.stderr)
        _show_startup_error(message)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
