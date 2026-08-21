from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import time
import webbrowser
import zipfile
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from claude_mcp_adapter import (
    MCPCallRequest,
    UnavailableClaudeCodeMCPAdapter,
    create_claude_code_mcp_adapter,
)
from agent_orchestration import WorkforceAgentOrchestrator, WorkforceObservation
from orchestrator import AnalysisOrchestrator, AnalysisRequest, MAX_CORP_CODES
from workforce_analytics import build_workforce_summary


SOURCE_ROOT = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    # In a PyInstaller one-file build, bundled static assets are extracted to
    # _MEIPASS while .env and the cache live beside the executable.
    ROOT = Path(sys.executable).resolve().parent
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", ROOT)) / "static"
else:
    ROOT = SOURCE_ROOT
    STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
CORP_CACHE = DATA_DIR / "corp_codes.json"
DART_BASE = "https://opendart.fss.or.kr/api"
PORT = int(os.environ.get("PORT", "8765"))
DART_CACHEABLE_ENDPOINTS = {
    "fnlttSinglAcnt.json",
    "empSttus.json",
    "unrstExctvMendngSttus.json",
}
DART_RESPONSE_CACHE: dict[str, tuple[float, Any]] = {}
DART_RESPONSE_CACHE_LOCK = threading.Lock()
DART_RESPONSE_CACHE_TTL_SECONDS = 300


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


DOTENV = load_dotenv(ROOT / ".env")
API_KEY = DOTENV.get("OPENDART_API_KEY") or os.environ.get("OPENDART_API_KEY", "")
CORP_LOCK = threading.Lock()
MAX_COMPANIES = MAX_CORP_CODES

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


class MCPProviderFacade:
    """Adapt the transport-neutral Claude MCP client to the orchestrator protocol."""

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
ORCHESTRATOR = AnalysisOrchestrator(MCP_ADAPTER)
WORKFORCE_MCP_ADAPTER = MCPProviderFacade(
    create_claude_code_mcp_adapter(),
    tool="analyze_workforce_strategy",
)
WORKFORCE_ORCHESTRATOR = WorkforceAgentOrchestrator(provider=WORKFORCE_MCP_ADAPTER)


class DARTError(Exception):
    pass


def dart_request(endpoint: str, params: dict[str, str], binary: bool = False) -> Any:
    if not API_KEY:
        raise DARTError("OPENDART_API_KEY가 .env에 설정되지 않았습니다.")
    cache_key = None
    if not binary and endpoint in DART_CACHEABLE_ENDPOINTS:
        cache_key = f"{endpoint}?{urlencode(sorted(params.items()))}"
        now = time.time()
        with DART_RESPONSE_CACHE_LOCK:
            cached = DART_RESPONSE_CACHE.get(cache_key)
            if cached:
                expires_at, cached_result = cached
                if expires_at > now:
                    return deepcopy(cached_result)
                DART_RESPONSE_CACHE.pop(cache_key, None)
    query = {**params, "crtfc_key": API_KEY}
    url = f"{DART_BASE}/{endpoint}?{urlencode(query)}"
    request = Request(url, headers={"User-Agent": "dart-financial-dashboard/0.1"})
    try:
        with urlopen(request, timeout=40) as response:
            payload = response.read()
    except Exception as exc:
        raise DARTError(f"OpenDART 연결에 실패했습니다: {exc}") from exc

    if binary:
        return payload
    try:
        result = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DARTError("OpenDART 응답을 해석하지 못했습니다.") from exc
    if result.get("status") not in (None, "000"):
        raise DARTError(f"{result.get('message', 'OpenDART 요청 오류')} ({result.get('status')})")
    if cache_key:
        with DART_RESPONSE_CACHE_LOCK:
            DART_RESPONSE_CACHE[cache_key] = (time.time() + DART_RESPONSE_CACHE_TTL_SECONDS, deepcopy(result))
    return result


def load_corp_codes() -> list[dict[str, str]]:
    with CORP_LOCK:
        if CORP_CACHE.exists() and time.time() - CORP_CACHE.stat().st_mtime < 24 * 60 * 60:
            try:
                return json.loads(CORP_CACHE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        payload = dart_request("corpCode.xml", {}, binary=True)
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                xml_bytes = archive.read("CORPCODE.xml")
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

        DATA_DIR.mkdir(exist_ok=True)
        CORP_CACHE.write_text(json.dumps(companies, ensure_ascii=False), encoding="utf-8")
        return companies


def search_companies(query: str, limit: int = 12) -> list[dict[str, str]]:
    query = query.strip().lower()
    if not query:
        return []
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
    if not text or text in {"-", "–", "-0"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def first_value(rows: list[dict[str, Any]], names: list[str], section: str) -> float | None:
    consolidated = [row for row in rows if row.get("fs_div") == "CFS"]
    candidates = consolidated or rows
    section_rows = [row for row in candidates if row.get("sj_div") == section]
    candidates = section_rows or candidates

    for name in names:
        for row in candidates:
            if (row.get("account_nm") or "").strip() == name:
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    return amount
    for name in names:
        for row in candidates:
            if name in (row.get("account_nm") or ""):
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    return amount
    return None


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def fetch_company_financials(company: dict[str, str], year: str, report_code: str) -> dict[str, Any]:
    base = {"company": company, "year": year, "report_code": report_code}
    try:
        result = dart_request(
            "fnlttSinglAcnt.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
        )
        rows = result.get("list", [])
        if not rows:
            raise DARTError("해당 연도·보고서의 재무 데이터가 없습니다.")

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
            "debt_ratio": ratio(liabilities, equity),
            "current_ratio": ratio(current_assets, current_liabilities),
        }
        receipt = rows[0].get("rcept_no", "")
        return {
            **base,
            "financials": financials,
            "currency": rows[0].get("currency", "KRW"),
            "statement": "연결재무제표" if any(row.get("fs_div") == "CFS" for row in rows) else "재무제표",
            "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}" if receipt else None,
        }
    except DARTError as exc:
        return {**base, "financials": None, "error": str(exc)}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _people_number(value: Any) -> float | None:
    return parse_amount(value)


def _people_count(value: Any) -> int | None:
    number = _people_number(value)
    return int(number) if number is not None else None


def _employee_summary_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Choose non-overlapping employee rows before aggregating.

    empSttus returns both business-unit rows and gender-total rows. When gender
    totals exist, only those rows are used; otherwise all returned rows are a
    documented fallback and the response exposes the source mode.
    """
    gender_totals = [
        row for row in rows
        if "성별합계" in _clean_text(row.get("fo_bbm"))
        or _clean_text(row.get("sexdstn")) in {"합계", "전체"}
    ]
    if gender_totals:
        unique: dict[str, dict[str, Any]] = {}
        for row in gender_totals:
            key = _clean_text(row.get("sexdstn")) or str(len(unique))
            unique[key] = row
        return list(unique.values()), "gender_total"
    return rows, "all_rows_fallback"


def fetch_company_people(company: dict[str, str], year: str, report_code: str) -> dict[str, Any]:
    base = {"company": company, "year": year, "report_code": report_code}
    employee_payload: dict[str, Any] | None = None
    executive_payload: dict[str, Any] | None = None
    unregistered_pay_payload: dict[str, Any] | None = None
    errors: list[dict[str, str]] = []
    try:
        employee_payload = dart_request(
            "empSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
        )
    except DARTError as exc:
        errors.append({"source": "employee_status", "message": str(exc)})
    try:
        executive_payload = dart_request(
            "exctvSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
        )
    except DARTError as exc:
        errors.append({"source": "executive_status", "message": str(exc)})
    try:
        unregistered_pay_payload = dart_request(
            "unrstExctvMendngSttus.json",
            {"corp_code": company["corp_code"], "bsns_year": year, "reprt_code": report_code},
        )
    except DARTError as exc:
        errors.append({"source": "unregistered_executive_pay", "message": str(exc)})

    employee_rows = (employee_payload or {}).get("list", []) if employee_payload else []
    employee_rows = [row for row in employee_rows if isinstance(row, dict)]
    selected_rows, aggregation_mode = _employee_summary_rows(employee_rows)
    employees_total = sum((_people_count(row.get("sm")) or 0) for row in selected_rows) or None
    regular_employees = sum((_people_count(row.get("rgllbr_co")) or 0) for row in selected_rows) or None
    contract_employees = sum((_people_count(row.get("cnttk_co")) or 0) for row in selected_rows) or None
    regular_short_time = sum((_people_count(row.get("rgllbr_abacpt_labrr_co")) or 0) for row in selected_rows) or None
    contract_short_time = sum((_people_count(row.get("cnttk_abacpt_labrr_co")) or 0) for row in selected_rows) or None
    salary_total = sum((_people_number(row.get("fyer_salary_totamt")) or 0) for row in selected_rows) or None
    tenure_weighted = sum(
        (_people_number(row.get("avrg_cnwk_sdytrn")) or 0) * (_people_count(row.get("sm")) or 0)
        for row in selected_rows
    )
    salary_weighted = sum(
        (_people_number(row.get("jan_salary_am")) or 0) * (_people_count(row.get("sm")) or 0)
        for row in selected_rows
    )
    avg_tenure = tenure_weighted / employees_total if employees_total else None
    average_salary = (
        salary_total / employees_total
        if salary_total and employees_total
        else salary_weighted / employees_total
        if salary_weighted and employees_total
        else None
    )
    employee_breakdown = [
        {
            "sex": _clean_text(row.get("sexdstn")) or None,
            "business_unit": _clean_text(row.get("fo_bbm")) or None,
            "regular": _people_count(row.get("rgllbr_co")),
            "contract": _people_count(row.get("cnttk_co")),
            "total": _people_count(row.get("sm")),
            "average_tenure": _people_number(row.get("avrg_cnwk_sdytrn")),
            "annual_salary_total": _people_number(row.get("fyer_salary_totamt")),
            "average_salary": _people_number(row.get("jan_salary_am")),
        }
        for row in selected_rows
    ]

    executive_rows = (executive_payload or {}).get("list", []) if executive_payload else []
    executive_rows = [row for row in executive_rows if isinstance(row, dict)]
    registered = sum(1 for row in executive_rows if "등기" in _clean_text(row.get("rgist_exctv_at")) and "미등기" not in _clean_text(row.get("rgist_exctv_at")))
    unregistered = sum(1 for row in executive_rows if "미등기" in _clean_text(row.get("rgist_exctv_at")))
    full_time = sum(1 for row in executive_rows if _clean_text(row.get("fte_at")) == "상근")
    part_time = sum(1 for row in executive_rows if _clean_text(row.get("fte_at")) == "비상근")
    unregistered_pay_rows = (unregistered_pay_payload or {}).get("list", []) if unregistered_pay_payload else []
    unregistered_pay_rows = [row for row in unregistered_pay_rows if isinstance(row, dict)]
    workforce_summary = build_workforce_summary(
        employee_rows=employee_rows,
        executive_rows=executive_rows,
        unregistered_pay_rows=unregistered_pay_rows,
    )
    unregistered_pay_count = sum((_people_count(row.get("nmpr")) or 0) for row in unregistered_pay_rows) or None
    unregistered_pay_total = sum((_people_number(row.get("fyer_salary_totamt")) or 0) for row in unregistered_pay_rows) or None
    unregistered_average_source = sum(
        (_people_number(row.get("jan_salary_am")) or 0) * (_people_count(row.get("nmpr")) or 0)
        for row in unregistered_pay_rows
    )
    unregistered_average_salary = (
        unregistered_average_source / unregistered_pay_count
        if unregistered_average_source and unregistered_pay_count
        else unregistered_pay_total / unregistered_pay_count
        if unregistered_pay_total and unregistered_pay_count
        else None
    )
    receipt = (employee_rows or executive_rows or unregistered_pay_rows or [{}])[0].get("rcept_no", "")
    result = {
        **base,
        "people": {
            "employees_total": employees_total,
            "regular_employees": regular_employees,
            "contract_employees": contract_employees,
            "regular_short_time": regular_short_time,
            "contract_short_time": contract_short_time,
            "average_tenure_years": avg_tenure,
            "annual_salary_total": salary_total,
            "average_salary": average_salary,
            "employee_row_count": len(employee_rows),
            "employee_aggregation": aggregation_mode,
            "executives_total": len(executive_rows) or None,
            "registered_executives": registered or None,
            "unregistered_executives": unregistered or None,
            "full_time_executives": full_time or None,
            "part_time_executives": part_time or None,
            "unregistered_pay_count": unregistered_pay_count,
            "unregistered_pay_total": unregistered_pay_total,
            "unregistered_average_salary": unregistered_average_salary,
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
                "category": _clean_text(row.get("se")) or "미등기임원",
                "count": _people_count(row.get("nmpr")),
                "annual_salary_total": _people_number(row.get("fyer_salary_totamt")),
                "average_salary": _people_number(row.get("jan_salary_am")),
                "note": _clean_text(row.get("rm")) or None,
            }
            for row in unregistered_pay_rows
        ],
        "source_urls": [f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}" if receipt else None],
    }
    if errors:
        result["errors"] = errors
    if not employee_rows and not executive_rows and not unregistered_pay_rows:
        result["error"] = "직원·임원 현황 공시 데이터가 없습니다."
    return result


def selected_companies(codes: list[str]) -> list[dict[str, str]]:
    companies = {company["corp_code"]: company for company in load_corp_codes()}
    selected = [companies[code] for code in codes if code in companies]
    if len(selected) != len(codes):
        raise DARTError("선택한 기업 코드 중 존재하지 않는 코드가 포함되어 있습니다.")
    return selected


def fetch_financial_results(codes: list[str], year: str, report_code: str) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(MAX_COMPANIES, len(selected))) as executor:
        futures = [executor.submit(fetch_company_financials, company, year, report_code) for company in selected]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: codes.index(item["company"]["corp_code"]))
    return results


def fetch_history_results(codes: list[str], from_year: str, to_year: str, report_code: str) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    jobs = [(company, str(year)) for company in selected for year in range(int(from_year), int(to_year) + 1)]
    by_code: dict[str, dict[str, Any]] = {company["corp_code"]: {"company": company, "years": []} for company in selected}
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as executor:
        futures = [executor.submit(fetch_company_financials, company, year, report_code) for company, year in jobs]
        for future in as_completed(futures):
            result = future.result()
            by_code[result["company"]["corp_code"]]["years"].append(result)
    history = list(by_code.values())
    for item in history:
        item["years"].sort(key=lambda value: int(value.get("year", from_year)))
    return history


def fetch_people_results(codes: list[str], year: str, report_code: str) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    with ThreadPoolExecutor(max_workers=min(MAX_COMPANIES, len(selected))) as executor:
        futures = [executor.submit(fetch_company_people, company, year, report_code) for company in selected]
    results = [future.result() for future in as_completed(futures)]
    results.sort(key=lambda item: codes.index(item["company"]["corp_code"]))
    return [_public_people_result(item) for item in results]


def fetch_people_history_results(codes: list[str], from_year: str, to_year: str, report_code: str) -> list[dict[str, Any]]:
    selected = selected_companies(codes)
    jobs = [(company, str(year)) for company in selected for year in range(int(from_year), int(to_year) + 1)]
    by_code: dict[str, dict[str, Any]] = {company["corp_code"]: {"company": company, "years": []} for company in selected}
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as executor:
        futures = [executor.submit(fetch_company_people, company, year, report_code) for company, year in jobs]
        for future in as_completed(futures):
            result = future.result()
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


def fetch_workforce_observations(codes: list[str], year: str, report_code: str) -> list[WorkforceObservation]:
    """Fetch DART rows once and convert them into orchestration inputs."""

    selected = selected_companies(codes)
    people_by_code: dict[str, dict[str, Any]] = {}
    financials_by_code: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(selected) * 2))) as executor:
        people_futures = {
            executor.submit(fetch_company_people, company, year, report_code): company
            for company in selected
        }
        financial_futures = {
            executor.submit(fetch_company_financials, company, year, report_code): company
            for company in selected
        }
        for future in as_completed(people_futures):
            company = people_futures[future]
            people_by_code[company["corp_code"]] = future.result()
        for future in as_completed(financial_futures):
            company = financial_futures[future]
            financials_by_code[company["corp_code"]] = future.result()

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
        observations.append(WorkforceObservation(
            company=company,
            year=year,
            report_code=report_code,
            employee_rows=people.get("_raw_employee_rows") or (),
            executive_rows=people.get("_raw_executive_rows") or (),
            unregistered_pay_rows=people.get("_raw_unregistered_pay_rows") or (),
            financials=financial.get("financials") or {},
            source_urls=source_urls,
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


def fetch_executive_results(codes: list[str], year: str, report_code: str) -> list[dict[str, Any]]:
    return [
        _executive_only_result(item)
        for item in fetch_people_results(codes, year, report_code)
    ]


def fetch_executive_history_results(codes: list[str], from_year: str, to_year: str, report_code: str) -> list[dict[str, Any]]:
    history = fetch_people_history_results(codes, from_year, to_year, report_code)
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
    raw_metrics = payload.get("metric_ids", ())
    if isinstance(raw_metrics, str):
        raw_metrics = raw_metrics.split(",")
    try:
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 40))
    except (TypeError, ValueError) as exc:
        raise ValueError("page와 page_size는 숫자여야 합니다.") from exc
    sort_by = str(payload.get("sort_by") or "")
    sort_direction = str(payload.get("sort_direction") or "desc")
    return AnalysisRequest(
        question=str(payload.get("question") or "기업 간 재무구조 차이를 비교해줘"),
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


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "DARTWorkforceIntelligence/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return True
        return origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise ValueError("요청 본문이 비어 있거나 너무 큽니다.")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("요청 본문은 JSON 객체여야 합니다.")
        return payload

    def do_POST(self) -> None:
        if not self.origin_allowed():
            self.send_json({"error": "허용되지 않은 Origin입니다."}, HTTPStatus.FORBIDDEN)
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path not in {"/api/analysis", "/api/analysis/context"}:
                self.send_json({"error": "POST 경로를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
                return
            payload = self.read_json_body()
            request = analysis_request_from_payload(payload)
            if not request.corp_codes or len(request.corp_codes) > MAX_COMPANIES:
                self.send_json({"error": f"비교 기업은 1~{MAX_COMPANIES}개까지 선택해 주세요."}, HTTPStatus.BAD_REQUEST)
                return
            if request.report_code not in {"11011", "11012", "11013", "11014"}:
                self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                return
            if request.from_year or request.to_year:
                from_year = request.from_year or str(time.localtime().tm_year - 5)
                to_year = request.to_year or str(time.localtime().tm_year - 1)
                if not re.fullmatch(r"20\d{2}", from_year) or not re.fullmatch(r"20\d{2}", to_year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                if int(from_year) > int(to_year) or int(to_year) - int(from_year) > 10:
                    self.send_json({"error": "추이 조회 범위는 최대 11개 연도입니다."}, HTTPStatus.BAD_REQUEST)
                    return
                results = fetch_history_results(list(request.corp_codes), from_year, to_year, request.report_code)
                request = replace(request, from_year=from_year, to_year=to_year)
                response = ORCHESTRATOR.run(request, results, DART_METRIC_CATALOG)
            else:
                year = request.year or str(time.localtime().tm_year - 1)
                if not re.fullmatch(r"20\d{2}", year):
                    self.send_json({"error": "조회 연도가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                results = fetch_financial_results(list(request.corp_codes), year, request.report_code)
                request = replace(request, year=year)
                response = ORCHESTRATOR.run(request, results, DART_METRIC_CATALOG)
            people_context = str(payload.get("people_context") or "").strip()
            if people_context:
                people_context = people_context[:50_000]
                context = response.get("context")
                if isinstance(context, dict):
                    context["people_analytics"] = {
                        "source": "OpenDART",
                        "metric_catalog": PEOPLE_METRIC_CATALOG,
                        "summary": people_context,
                    }
                response["prompt"] = f"{response.get('prompt', '').rstrip()}\n\n[People Analytics]\n{people_context}\n\n[HR 해석 규칙]\n직원·임원·보상 수치는 공시된 집계값으로만 해석하고, 인과관계나 개인별 성과를 단정하지 마세요."
                prompt_handoff = response.get("prompt_handoff")
                if isinstance(prompt_handoff, dict):
                    prompt_handoff["prompt"] = response["prompt"]
                    prompt_handoff["context"] = response.get("context")
            response["selection"] = {"count": len(request.corp_codes), "max": MAX_COMPANIES}
            response["source"] = "OpenDART"
            self.send_json(response)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except DARTError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except Exception as exc:
            self.send_json({"error": f"서버 처리 중 오류가 발생했습니다: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self) -> None:
        if not self.origin_allowed():
            self.send_json({"error": "허용되지 않은 Origin입니다."}, HTTPStatus.FORBIDDEN)
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self.send_json({"ok": True, "api_key_configured": len(API_KEY) == 40})
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
                    "views": ["overview", "compare", "trend", "people", "executives", "strategy", "radar", "scatter", "rank"],
                    "source": "OpenDART",
                })
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
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                companies = {company["corp_code"]: company for company in load_corp_codes()}
                selected = [companies[code] for code in codes if code in companies]
                if len(selected) != len(codes):
                    self.send_json({"error": "알 수 없는 기업 코드가 포함되어 있습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                jobs = [(company, str(year)) for company in selected for year in range(start_year, end_year + 1)]
                by_code: dict[str, dict[str, Any]] = {
                    company["corp_code"]: {"company": company, "years": []} for company in selected
                }
                with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as executor:
                    futures = [executor.submit(fetch_company_financials, company, year, report_code) for company, year in jobs]
                    for future in as_completed(futures):
                        result = future.result()
                        by_code[result["company"]["corp_code"]]["years"].append(result)
                history = list(by_code.values())
                for item in history:
                    item["years"].sort(key=lambda value: int(value.get("year", from_year)))
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
                observations = fetch_workforce_observations(codes, year, report_code)
                result = WORKFORCE_ORCHESTRATOR.run(observations)
                result["source"] = "OpenDART"
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
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 코드가 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                self.send_json({
                    "from_year": from_year,
                    "to_year": to_year,
                    "report_code": report_code,
                    "results": fetch_executive_history_results(codes, from_year, to_year, report_code),
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
                self.send_json({
                    "year": year,
                    "report_code": report_code,
                    "results": fetch_executive_results(codes, year, report_code),
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
                if report_code not in {"11011", "11012", "11013", "11014"}:
                    self.send_json({"error": "보고서 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                self.send_json({
                    "from_year": from_year,
                    "to_year": to_year,
                    "report_code": report_code,
                    "results": fetch_people_history_results(codes, from_year, to_year, report_code),
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
                self.send_json({"year": year, "report_code": report_code, "results": fetch_people_results(codes, year, report_code)})
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
                companies = {company["corp_code"]: company for company in load_corp_codes()}
                selected = [companies[code] for code in codes if code in companies]
                if len(selected) != len(codes):
                    self.send_json({"error": "알 수 없는 기업 코드가 포함되어 있습니다."}, HTTPStatus.BAD_REQUEST)
                    return
                results: list[dict[str, Any]] = []
                with ThreadPoolExecutor(max_workers=min(5, len(selected))) as executor:
                    futures = [executor.submit(fetch_company_financials, company, year, report_code) for company in selected]
                    for future in as_completed(futures):
                        results.append(future.result())
                results.sort(key=lambda item: codes.index(item["company"]["corp_code"]))
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
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except Exception as exc:
            self.send_json({"error": f"서버 처리 중 오류가 발생했습니다: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    STATIC_DIR.mkdir(exist_ok=True)
    print(f"DART Workforce Intelligence: http://127.0.0.1:{PORT}")
    http_server = ThreadingHTTPServer(("127.0.0.1", PORT), DashboardHandler)
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:
        pass
    http_server.serve_forever()
