"""Agent DAG for DART Workforce Intelligence.

The pipeline is deterministic until the optional strategy interpretation step.
It accepts already-fetched OpenDART rows, runs independent normalizers in
parallel, then gates benchmarking and provider handoff behind quality and
privacy checks.  It never requires Claude MCP to produce facts or metrics.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from workforce_analytics import (
    summarize_employees,
    summarize_executives,
    summarize_unregistered_pay,
)


ORCHESTRATION_SCHEMA_VERSION = 1
SENSITIVE_KEYS = {
    "nm",
    "name",
    "birth_ym",
    "main_career",
    "career",
    "resident_registration_number",
}
BENCHMARK_KEYS = (
    "employees_total",
    "regular_share",
    "contract_share",
    "average_salary",
    "average_tenure_years",
    "executives_total",
    "outside_director_share",
    "female_share",
    "average_tenure_months",
    "term_expiring_within_12_months",
    "revenue_per_employee",
    "operating_profit_per_employee",
    "salary_to_revenue",
)


class StrategyProvider(Protocol):
    """Minimal provider contract for an optional Claude MCP interpretation."""

    configured: bool

    def analyze(self, *, prompt: str, context: Mapping[str, Any]) -> Any:
        """Interpret a sanitized, deterministic context."""


@dataclass(frozen=True, slots=True)
class WorkforceObservation:
    """One company-period input containing only DART-derived raw rows."""

    company: Mapping[str, Any]
    year: str
    report_code: str
    employee_rows: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    executive_rows: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    unregistered_pay_rows: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    financials: Mapping[str, Any] = field(default_factory=dict)
    source_urls: Sequence[str | None] = field(default_factory=tuple)
    errors: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkforceObservation":
        company = value.get("company") or {
            "corp_code": value.get("corp_code"),
            "corp_name": value.get("corp_name"),
        }
        return cls(
            company=company,
            year=str(value.get("year") or ""),
            report_code=str(value.get("report_code") or "11011"),
            employee_rows=tuple(value.get("employee_rows") or ()),
            executive_rows=tuple(value.get("executive_rows") or ()),
            unregistered_pay_rows=tuple(value.get("unregistered_pay_rows") or ()),
            financials=value.get("financials") or {},
            source_urls=tuple(value.get("source_urls") or ()),
            errors=tuple(value.get("errors") or ()),
        )


@dataclass
class AgentTrace:
    agent: str
    status: str
    duration_ms: int = 0
    error: str | None = None
    depends_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "agent": self.agent,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "depends_on": list(self.depends_on),
        }
        if self.error:
            payload["error"] = self.error
        return payload


class AgentFailure(RuntimeError):
    """Raised when an agent cannot produce its declared output."""


class WorkforceAgent(Protocol):
    name: str
    depends_on: tuple[str, ...]

    def run(self, observations: Sequence[WorkforceObservation], state: Mapping[str, Any]) -> Mapping[str, Any]:
        """Run the agent against immutable inputs and prior state."""


class SourceSnapshotAgent:
    name = "source_snapshot"
    depends_on = ()

    def run(self, observations, state):
        snapshots = []
        for item in observations:
            snapshots.append({
                "company": dict(item.company),
                "year": item.year,
                "report_code": item.report_code,
                "source_urls": [url for url in item.source_urls if url],
                "raw_row_counts": {
                    "employees": len(item.employee_rows),
                    "executives": len(item.executive_rows),
                    "unregistered_pay": len(item.unregistered_pay_rows),
                },
                "errors": [dict(error) for error in item.errors],
            })
        return {"source_snapshots": snapshots}


class EmployeeNormalizerAgent:
    name = "employee_normalizer"
    depends_on = ("source_snapshot",)

    def run(self, observations, state):
        return {
            "employee_results": [summarize_employees(item.employee_rows) for item in observations]
        }


class ExecutiveNormalizerAgent:
    name = "executive_normalizer"
    depends_on = ("source_snapshot",)

    def run(self, observations, state):
        return {
            "executive_results": [summarize_executives(item.executive_rows) for item in observations]
        }


class CompensationNormalizerAgent:
    name = "compensation_normalizer"
    depends_on = ("source_snapshot",)

    def run(self, observations, state):
        return {
            "compensation_results": [summarize_unregistered_pay(item.unregistered_pay_rows) for item in observations]
        }


def _safe_ratio(numerator: Any, denominator: Any, multiplier: float = 1.0) -> float | None:
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator) * multiplier
    except (TypeError, ValueError):
        return None


class QualityAuditorAgent:
    name = "quality_auditor"
    depends_on = ("employee_normalizer", "executive_normalizer", "compensation_normalizer")

    def run(self, observations, state):
        records = []
        for index, item in enumerate(observations):
            components = {
                "employees": state["employee_results"][index]["quality"],
                "executives": state["executive_results"][index]["quality"],
                "unregistered_pay": state["compensation_results"][index]["quality"],
            }
            missing = sorted({field for value in components.values() for field in value["missing_fields"]})
            warnings = sorted({warning for value in components.values() for warning in value["warnings"]})
            source_errors = [dict(error) for error in item.errors]
            status = "error" if source_errors else "complete"
            if any(value["status"] == "error" for value in components.values()):
                status = "error"
            elif any(value["status"] == "partial" for value in components.values()) or missing or warnings:
                status = "partial"
            elif all(value["status"] == "no_data" for value in components.values()):
                status = "no_data"
            records.append({
                "status": status,
                "missing_fields": missing,
                "warnings": warnings,
                "source_errors": source_errors,
                "components": components,
            })
        return {"quality_results": records}


class BenchmarkCalculatorAgent:
    name = "benchmark_calculator"
    depends_on = ("employee_normalizer", "executive_normalizer", "compensation_normalizer", "quality_auditor")

    def run(self, observations, state):
        records = []
        for index, item in enumerate(observations):
            employee_metrics = state["employee_results"][index]["metrics"]
            executive_metrics = state["executive_results"][index]["metrics"]
            compensation_metrics = state["compensation_results"][index]["metrics"]
            metrics = {
                **employee_metrics,
                **executive_metrics,
                **compensation_metrics,
            }
            revenue = item.financials.get("revenue")
            operating_profit = item.financials.get("operating_profit")
            metrics.update({
                "revenue_per_employee": _safe_ratio(revenue, employee_metrics.get("employees_total")),
                "operating_profit_per_employee": _safe_ratio(operating_profit, employee_metrics.get("employees_total")),
                "salary_to_revenue": _safe_ratio(employee_metrics.get("annual_salary_total"), revenue, 100),
            })
            records.append({
                "company": dict(item.company),
                "year": item.year,
                "report_code": item.report_code,
                "metrics": metrics,
                "source": {
                    "source_urls": [url for url in item.source_urls if url],
                },
                "quality": state["quality_results"][index],
            })

        rankings: dict[str, list[dict[str, Any]]] = {}
        for metric in BENCHMARK_KEYS:
            values = [
                {
                    "company": record["company"],
                    "value": record["metrics"].get(metric),
                }
                for record in records
                if record["metrics"].get(metric) is not None
            ]
            values.sort(key=lambda row: row["value"], reverse=True)
            rankings[metric] = [
                {"rank": rank, **row}
                for rank, row in enumerate(values, start=1)
            ]
        return {"records": records, "rankings": rankings}


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(key in SENSITIVE_KEYS or _contains_sensitive_key(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(child) for child in value)
    return False


class PrivacyGuardAgent:
    name = "privacy_guard"
    depends_on = ("benchmark_calculator",)

    def run(self, observations, state):
        if _contains_sensitive_key(state["records"]) or _contains_sensitive_key(state["rankings"]):
            raise AgentFailure("sensitive executive fields reached the normalized output")
        return {"privacy": {"status": "passed", "removed_fields": sorted(SENSITIVE_KEYS)}}


def _build_strategy_context(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "records": state["records"],
        "rankings": state["rankings"],
        "quality": state["quality_results"],
        "privacy": state["privacy"],
    }


def _build_strategy_prompt(context: Mapping[str, Any]) -> str:
    return (
        "다음은 OpenDART 공시에서 정규화한 기업 수준 Workforce Analytics입니다.\n"
        "수치에 없는 개인 성과, 이직 원인, 조직문화, 인과관계를 추론하지 마세요.\n"
        "확인된 사실, 전략 가설, 추가 검증 데이터, KPI, 제한사항을 구분하세요.\n"
        "개인별 임원 정보나 이름을 생성하지 마세요.\n\n"
        "[WORKFORCE_CONTEXT]\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n"
        "[/WORKFORCE_CONTEXT]"
    )


class StrategyInterpreterAgent:
    name = "strategy_interpreter"
    depends_on = ("privacy_guard",)

    def __init__(self, provider: StrategyProvider | None = None) -> None:
        self.provider = provider

    def run(self, observations, state):
        context = _build_strategy_context(state)
        prompt = _build_strategy_prompt(context)
        provider = self.provider
        provider_meta = {
            "id": str(getattr(provider, "provider_id", "not_configured")),
            "name": str(getattr(provider, "provider_label", type(provider).__name__ if provider else "미설정")),
        }
        if provider is None or not getattr(provider, "configured", False):
            return {
                "provider": {
                    **provider_meta,
                    "status": "not_configured",
                    "prompt": prompt,
                    "result": None,
                }
            }
        try:
            result = provider.analyze(prompt=prompt, context=context)
        except Exception as exc:
            return {
                "provider": {
                    **provider_meta,
                    "status": "error",
                    "prompt": prompt,
                    "result": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            }
        if isinstance(result, Mapping) and result.get("status") in {"not_configured", "unavailable"}:
            return {
                "provider": {
                    **provider_meta,
                    "status": "not_configured",
                    "prompt": prompt,
                    "result": None,
                }
            }
        if isinstance(result, Mapping) and str(result.get("status", "")).lower() in {"error", "failed", "failure"}:
            error = result.get("error_message") or result.get("error") or result.get("message")
            return {
                "provider": {
                    **provider_meta,
                    "status": "error",
                    "prompt": prompt,
                    "result": None,
                    "error": str(error or "AI provider returned an error."),
                }
            }
        return {
            "provider": {
                **provider_meta,
                "status": "completed" if result is not None else "no_result",
                "prompt": prompt,
                "result": result,
            }
        }


class ResponseGuardAgent:
    name = "response_guard"
    depends_on = ("privacy_guard", "strategy_interpreter")

    def run(self, observations, state):
        required = ("records", "rankings", "quality_results", "privacy", "provider")
        missing = [key for key in required if key not in state]
        if missing:
            raise AgentFailure(f"response is missing required sections: {', '.join(missing)}")
        if _contains_sensitive_key(state["provider"].get("result")):
            raise AgentFailure("provider result contains sensitive executive fields")
        return {"response_validation": {"status": "passed", "missing_sections": []}}


class WorkforceAgentOrchestrator:
    """Execute the Workforce Intelligence agent DAG and return a trace."""

    def __init__(self, provider: StrategyProvider | None = None, max_workers: int = 3) -> None:
        self.provider = provider
        self.max_workers = max(1, int(max_workers))

    def run(self, observations: Sequence[WorkforceObservation | Mapping[str, Any]]) -> dict[str, Any]:
        normalized = [
            item if isinstance(item, WorkforceObservation) else WorkforceObservation.from_mapping(item)
            for item in observations
        ]
        state: dict[str, Any] = {}
        traces: list[AgentTrace] = []

        self._run_one(SourceSnapshotAgent(), normalized, state, traces)
        parallel_agents = [
            EmployeeNormalizerAgent(),
            ExecutiveNormalizerAgent(),
            CompensationNormalizerAgent(),
        ]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(parallel_agents))) as executor:
            futures = {
                executor.submit(agent.run, normalized, dict(state)): agent
                for agent in parallel_agents
            }
            for future in as_completed(futures):
                agent = futures[future]
                started = time.perf_counter()
                try:
                    state.update(future.result())
                except Exception as exc:
                    traces.append(AgentTrace(agent.name, "error", int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}", agent.depends_on))
                else:
                    traces.append(AgentTrace(agent.name, "completed", int((time.perf_counter() - started) * 1000), depends_on=agent.depends_on))

        for agent in (QualityAuditorAgent(), BenchmarkCalculatorAgent(), PrivacyGuardAgent()):
            self._run_one(agent, normalized, state, traces)
        self._run_one(StrategyInterpreterAgent(self.provider), normalized, state, traces)
        self._run_one(ResponseGuardAgent(), normalized, state, traces)

        errors = [trace for trace in traces if trace.status == "error"]
        status = "error" if errors else "completed"
        if not normalized:
            status = "no_data"
        elif any(record.get("status") in {"partial", "no_data", "error"} for record in state.get("quality_results", [])):
            status = "partial" if not errors else "error"
        return {
            "schema_version": ORCHESTRATION_SCHEMA_VERSION,
            "status": status,
            "facts": {"records": state.get("records", [])},
            "benchmarks": {"rankings": state.get("rankings", {})},
            "quality": {"records": state.get("quality_results", [])},
            "privacy": state.get("privacy", {"status": "not_run"}),
            "provider": state.get("provider", {"status": "skipped", "result": None}),
            "validation": state.get("response_validation", {"status": "not_run"}),
            "trace": [trace.to_dict() for trace in traces],
        }

    @staticmethod
    def _run_one(agent, observations, state, traces) -> None:
        started = time.perf_counter()
        try:
            state.update(agent.run(observations, state))
        except Exception as exc:
            traces.append(AgentTrace(agent.name, "error", int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}", agent.depends_on))
        else:
            traces.append(AgentTrace(agent.name, "completed", int((time.perf_counter() - started) * 1000), depends_on=agent.depends_on))


__all__ = [
    "AgentFailure",
    "BENCHMARK_KEYS",
    "ORCHESTRATION_SCHEMA_VERSION",
    "StrategyProvider",
    "WorkforceAgentOrchestrator",
    "WorkforceObservation",
]
