"""AI analysis orchestration for normalized OpenDART results.

The module intentionally has no network or provider-specific implementation.
The server can inject any configured analysis provider.  Without one,
``AnalysisOrchestrator`` returns a structured prompt handoff and leaves
``provider_result`` as ``None``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol, Sequence


MAX_CORP_CODES = 8
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 500


class ClaudeMCPAdapter(Protocol):
    """Backward-compatible provider boundary for an AI integration.

    The adapter owns authentication, transport, and provider-specific response
    parsing.  This module only supplies the deterministic prompt and context.
    An adapter may expose ``configured = False`` to make its configuration
    state explicit; the orchestrator will not call it in that state.
    """

    def analyze(self, *, prompt: str, context: Mapping[str, Any]) -> Any:
        """Analyze a prepared prompt and context, returning a provider result."""


class NotConfiguredClaudeMCPAdapter:
    """Explicit no-op adapter for environments without Claude MCP wiring."""

    configured = False

    def analyze(self, *, prompt: str, context: Mapping[str, Any]) -> None:
        """Return no answer; the orchestrator skips this adapter when unconfigured."""

        return None


@dataclass(frozen=True)
class AnalysisRequest:
    """All user-controlled state needed to create an analysis handoff.

    ``year`` is used for a point-in-time view.  ``from_year`` and ``to_year``
    define a range for trend-oriented requests.  A caller may provide both a
    point year and a range; the range is authoritative for the context while
    the original request is preserved in the returned payload.
    """

    question: str = ""
    view: str = "overview"
    corp_codes: tuple[str, ...] = field(default_factory=tuple)
    year: str | int | None = None
    from_year: str | int | None = None
    to_year: str | int | None = None
    report_code: str | None = None
    metric_ids: tuple[str, ...] = field(default_factory=tuple)
    sort: str | Mapping[str, Any] | Sequence[str] | None = None
    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", str(self.question or "").strip())
        object.__setattr__(self, "view", str(self.view or "overview").strip() or "overview")
        object.__setattr__(self, "corp_codes", _normalise_tokens(self.corp_codes))
        object.__setattr__(self, "metric_ids", _normalise_tokens(self.metric_ids))
        object.__setattr__(self, "year", _normalise_year(self.year))
        object.__setattr__(self, "from_year", _normalise_year(self.from_year))
        object.__setattr__(self, "to_year", _normalise_year(self.to_year))
        if self.report_code is not None:
            object.__setattr__(self, "report_code", str(self.report_code).strip() or None)
        try:
            normalised_page = int(self.page)
            normalised_page_size = int(self.page_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("page and page_size must be integers") from exc
        object.__setattr__(self, "page", normalised_page)
        object.__setattr__(self, "page_size", normalised_page_size)
        if len(self.corp_codes) > MAX_CORP_CODES:
            raise ValueError(f"corp_codes must contain at most {MAX_CORP_CODES} companies")
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if self.page_size < 1 or self.page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly copy of the request."""

        payload = asdict(self)
        payload["corp_codes"] = list(self.corp_codes)
        payload["metric_ids"] = list(self.metric_ids)
        if isinstance(self.sort, tuple):
            payload["sort"] = list(self.sort)
        return payload


def build_analysis_context(
    request: AnalysisRequest,
    dart_results: Any,
    metric_catalog: Any,
) -> dict[str, Any]:
    """Build a deterministic, provider-neutral analysis context.

    The function accepts the result shapes currently emitted by the DART
    server, including a single result, a ``{"results": [...]}`` envelope, and
    history results containing ``years``.  It also accepts already-normalized
    records with ``metrics`` or ``values`` mappings.

    ``missing`` describes an expected observation or metric value that was not
    returned.  ``errors`` describes a failed DART request or an explicit error
    supplied by the data source.  A failed request is never silently converted
    into a missing numeric value.
    """

    if not isinstance(request, AnalysisRequest):
        raise TypeError("request must be an AnalysisRequest")

    catalog = _normalise_metric_catalog(metric_catalog)
    source_keys = _metric_source_keys(catalog)

    flattened = list(_flatten_result_items(dart_results))
    observed_metric_ids = _observed_metric_ids(flattened)
    requested_metric_ids = _requested_metric_ids(request, catalog, observed_metric_ids)

    missing: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    seen_observation_keys: set[tuple[str, str | None, str | None]] = set()
    errored_observation_keys: set[tuple[str, str | None, str | None]] = set()

    for item, inherited in flattened:
        company = _company_payload(item, inherited)
        corp_code = _first_text(
            item.get("corp_code"),
            inherited.get("corp_code"),
            company.get("corp_code"),
        )
        company_name = _first_text(
            company.get("corp_name"),
            item.get("corp_name"),
            inherited.get("corp_name"),
        )
        if company_name and "corp_name" not in company:
            company["corp_name"] = company_name
        if corp_code and "corp_code" not in company:
            company["corp_code"] = corp_code

        year = _first_text(item.get("year"), inherited.get("year"), request.year)
        report_code = _first_text(
            item.get("report_code"), inherited.get("report_code"), request.report_code
        )
        observation_key = (corp_code or company_name or "unknown", year, report_code)
        seen_observation_keys.add(observation_key)

        item_errors = _normalise_errors(item, company, year, report_code)
        if item_errors:
            errored_observation_keys.add(observation_key)
            errors.extend(item_errors)

        raw_metrics = _extract_metric_mapping(item)
        metrics: dict[str, Any] = {}
        for metric_id in requested_metric_ids:
            value, found = _lookup_metric(raw_metrics, metric_id, source_keys.get(metric_id, ()))
            metrics[metric_id] = value if found else None
            if not item_errors and (not found or value is None):
                missing.append(
                    _missing_record(
                        company=company,
                        year=year,
                        report_code=report_code,
                        metric_id=metric_id,
                        reason="null_value" if found else "not_returned",
                    )
                )

        if not raw_metrics and not item_errors and requested_metric_ids:
            for metric_id in requested_metric_ids:
                _remove_duplicate_missing(
                    missing,
                    company=company,
                    year=year,
                    report_code=report_code,
                    metric_id=metric_id,
                )
                missing.append(
                    _missing_record(
                        company=company,
                        year=year,
                        report_code=report_code,
                        metric_id=metric_id,
                        reason="no_metric_payload",
                    )
                )

        observation: dict[str, Any] = {
            "company": company,
            "corp_code": corp_code,
            "company_name": company_name,
            "year": year,
            "report_code": report_code,
            "metrics": metrics,
        }
        for field_name in ("currency", "statement", "source_url"):
            value = _first_present(item, inherited, field_name)
            if value is not None:
                observation[field_name] = value
        if item_errors:
            observation["has_error"] = True
        observations.append(observation)

    expected_years = _request_years(request)
    expected_codes = request.corp_codes
    if expected_codes and expected_years:
        known_keys = seen_observation_keys | errored_observation_keys
        for corp_code in expected_codes:
            for year in expected_years:
                key_candidates = {
                    key for key in known_keys if key[0] == corp_code and key[1] == year
                }
                if key_candidates:
                    continue
                if requested_metric_ids:
                    for metric_id in requested_metric_ids:
                        missing.append(
                            _missing_record(
                                company={"corp_code": corp_code},
                                year=year,
                                report_code=request.report_code,
                                metric_id=metric_id,
                                reason="observation_not_returned",
                            )
                        )
                else:
                    missing.append(
                        _missing_record(
                            company={"corp_code": corp_code},
                            year=year,
                            report_code=request.report_code,
                            metric_id=None,
                            reason="observation_not_returned",
                        )
                    )

    observations.sort(key=_observation_sort_key(request.corp_codes))
    missing = _deduplicate_records(missing)
    errors = _deduplicate_records(errors)

    sort_spec = _normalise_sort(request.sort)
    return {
        "schema_version": 1,
        "request": request.to_dict(),
        "view": request.view,
        "query": {
            "question": request.question,
            "year": request.year,
            "from_year": request.from_year,
            "to_year": request.to_year,
            "report_code": request.report_code,
            "corp_codes": list(request.corp_codes),
            "metric_ids": list(requested_metric_ids),
            "sort": sort_spec,
            "page": request.page,
            "page_size": request.page_size,
        },
        "metric_catalog": catalog,
        "observations": observations,
        "missing": missing,
        "errors": errors,
        "view_state": {
            "view": request.view,
            "metric_ids": list(requested_metric_ids),
            "sort": sort_spec,
            "page": request.page,
            "page_size": request.page_size,
        },
    }


class AnalysisOrchestrator:
    """Prepare analysis context and optionally delegate to Claude MCP."""

    def __init__(self, adapter: ClaudeMCPAdapter | None = None) -> None:
        self.adapter = adapter

    def build_context(
        self,
        request: AnalysisRequest,
        dart_results: Any,
        metric_catalog: Any,
    ) -> dict[str, Any]:
        """Expose context building for servers that need a data-only path."""

        return build_analysis_context(request, dart_results, metric_catalog)

    def run(
        self,
        request: AnalysisRequest,
        dart_results: Any,
        metric_catalog: Any,
        *,
        adapter: ClaudeMCPAdapter | None = None,
        extra_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a handoff and call only an explicitly configured adapter.

        ``adapter`` can be supplied per call; otherwise the adapter injected at
        construction time is used.  The method never fabricates an AI answer.
        If no configured adapter is available, ``provider_result`` is ``None``
        and the caller receives the complete prompt handoff instead.
        """

        context = self.build_context(request, dart_results, metric_catalog)
        if extra_context:
            context.update(dict(extra_context))
        prompt = build_structured_prompt(context)
        active_adapter = adapter if adapter is not None else self.adapter
        provider_name = type(active_adapter).__name__ if active_adapter is not None else None
        provider_id = str(getattr(active_adapter, "provider_id", "not_configured"))
        provider_label = str(getattr(active_adapter, "provider_label", provider_name or "미설정"))
        provider_status = "not_configured"
        provider_result: Any = None
        provider_error: str | None = None

        if _adapter_is_configured(active_adapter):
            try:
                provider_result = active_adapter.analyze(prompt=prompt, context=context)  # type: ignore[union-attr]
            except Exception as exc:  # Provider failures must not become fake answers.
                provider_status = "error"
                provider_error = f"{type(exc).__name__}: {exc}"
            else:
                if _is_not_configured_result(provider_result):
                    provider_result = None
                    provider_status = "not_configured"
                elif _is_provider_error_result(provider_result):
                    provider_error = _provider_error_message(provider_result)
                    provider_result = None
                    provider_status = "error"
                elif provider_result is None:
                    provider_status = "no_result"
                else:
                    provider_status = "completed"

        prompt_handoff: dict[str, Any] = {
            "provider": provider_id,
            "provider_name": provider_name,
            "status": provider_status,
            "prompt": prompt,
            "context": context,
        }
        if provider_error is not None:
            prompt_handoff["error"] = provider_error

        provider_payload = {
            "id": provider_id,
            "name": provider_label,
            "status": provider_status,
            "result": provider_result,
            "prompt": prompt,
        }
        if provider_error is not None:
            provider_payload["error"] = provider_error

        return {
            "context": context,
            "prompt": prompt,
            "prompt_handoff": prompt_handoff,
            "provider": provider_payload,
            "provider_status": provider_status,
            "provider_result": provider_result,
        }


def build_structured_prompt(context: Mapping[str, Any]) -> str:
    """Render a provider-neutral prompt handoff from structured context."""

    payload = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    return (
        "You are an analysis provider receiving a structured OpenDART handoff.\n"
        "Answer the user's question using only the supplied observations. Do not invent\n"
        "values, missing data, sources, or provider results. Distinguish missing values\n"
        "from request errors, cite the relevant company/year/metric evidence, and state\n"
        "important limitations. Do not provide a buy, sell, or investment recommendation.\n\n"
        "[STRUCTURED_ANALYSIS_CONTEXT]\n"
        f"{payload}\n"
        "[/STRUCTURED_ANALYSIS_CONTEXT]"
    )


def _normalise_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.split(",")
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    result: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _normalise_year(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def _normalise_metric_catalog(raw_catalog: Any) -> list[dict[str, Any]]:
    if raw_catalog is None:
        return []

    entries: list[Any]
    if isinstance(raw_catalog, Mapping):
        if isinstance(raw_catalog.get("metrics"), Sequence) and not isinstance(
            raw_catalog.get("metrics"), (str, bytes)
        ):
            entries = list(raw_catalog["metrics"])
        else:
            entries = []
            for metric_id, metadata in raw_catalog.items():
                if metric_id in {"schema_version", "version", "metadata"}:
                    continue
                if isinstance(metadata, Mapping):
                    item = dict(metadata)
                else:
                    item = {"label": str(metadata)}
                item.setdefault("metric_id", str(metric_id))
                entries.append(item)
    elif isinstance(raw_catalog, Sequence) and not isinstance(raw_catalog, (str, bytes)):
        entries = list(raw_catalog)
    else:
        entries = [raw_catalog]

    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if isinstance(entry, Mapping):
            item = dict(entry)
            metric_id = _first_text(
                item.get("metric_id"), item.get("id"), item.get("key"), item.get("name")
            )
        else:
            metric_id = str(entry).strip()
            item = {"label": metric_id}
        if not metric_id or metric_id in seen:
            continue
        item["metric_id"] = metric_id
        item.setdefault("label", metric_id)
        normalised.append(item)
        seen.add(metric_id)
    return normalised


def _metric_source_keys(catalog: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for item in catalog:
        metric_id = str(item["metric_id"])
        candidates = [
            metric_id,
            item.get("source_key"),
            item.get("field"),
            item.get("data_key"),
        ]
        result[metric_id] = tuple(
            value for value in (str(candidate).strip() if candidate is not None else "" for candidate in candidates) if value
        )
    return result


def _requested_metric_ids(
    request: AnalysisRequest,
    catalog: Sequence[Mapping[str, Any]],
    observed_metric_ids: Sequence[str],
) -> tuple[str, ...]:
    if request.metric_ids:
        return request.metric_ids
    catalog_ids = tuple(str(item["metric_id"]) for item in catalog)
    if catalog_ids:
        return catalog_ids
    return tuple(observed_metric_ids)


def _flatten_result_items(
    raw_results: Any,
    inherited: Mapping[str, Any] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    inherited_values = dict(inherited or {})
    if raw_results is None:
        return []
    if isinstance(raw_results, Sequence) and not isinstance(raw_results, (str, bytes)):
        flattened: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for item in raw_results:
            flattened.extend(_flatten_result_items(item, inherited_values))
        return flattened
    if not isinstance(raw_results, Mapping):
        return []

    inherited_next = dict(inherited_values)
    for key in (
        "company",
        "corp_code",
        "corp_name",
        "stock_code",
        "year",
        "report_code",
        "currency",
        "statement",
        "source_url",
    ):
        if key in raw_results:
            inherited_next[key] = raw_results[key]

    for child_key in ("results", "years"):
        child_values = raw_results.get(child_key)
        if isinstance(child_values, Sequence) and not isinstance(child_values, (str, bytes)):
            flattened = []
            for child in child_values:
                flattened.extend(_flatten_result_items(child, inherited_next))
            return flattened
    return [(dict(raw_results), inherited_next)]


def _observed_metric_ids(flattened: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> tuple[str, ...]:
    result: list[str] = []
    for item, _ in flattened:
        for metric_id in _extract_metric_mapping(item):
            if metric_id not in result:
                result.append(metric_id)
        direct_metric = _first_text(item.get("metric_id"), item.get("metric"))
        if direct_metric and direct_metric not in result:
            result.append(direct_metric)
    return tuple(result)


def _extract_metric_mapping(item: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("financials", "metrics", "values"):
        value = item.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    direct_metric = _first_text(item.get("metric_id"), item.get("metric"))
    if direct_metric and "value" in item:
        return {direct_metric: item.get("value")}
    return {}


def _lookup_metric(
    raw_metrics: Mapping[str, Any],
    metric_id: str,
    source_keys: Sequence[str],
) -> tuple[Any, bool]:
    for key in (metric_id, *source_keys):
        if key in raw_metrics:
            return raw_metrics[key], True
    return None, False


def _company_payload(item: Mapping[str, Any], inherited: Mapping[str, Any]) -> dict[str, Any]:
    raw_company = item.get("company", inherited.get("company"))
    if isinstance(raw_company, Mapping):
        company = dict(raw_company)
    elif raw_company is not None:
        company = {"corp_name": str(raw_company)}
    else:
        company = {}
    for key in ("corp_code", "corp_name", "stock_code"):
        value = _first_present(item, inherited, key)
        if value is not None:
            company.setdefault(key, value)
    return company


def _normalise_errors(
    item: Mapping[str, Any],
    company: Mapping[str, Any],
    year: str | None,
    report_code: str | None,
) -> list[dict[str, Any]]:
    raw_errors: Any = item.get("errors")
    if raw_errors is None and item.get("error") is not None:
        raw_errors = item.get("error")
    if raw_errors is None:
        return []
    if isinstance(raw_errors, Sequence) and not isinstance(raw_errors, (str, bytes)):
        values = list(raw_errors)
    else:
        values = [raw_errors]

    result: list[dict[str, Any]] = []
    for raw_error in values:
        if isinstance(raw_error, Mapping):
            error = dict(raw_error)
            message = _first_text(error.get("message"), error.get("error"), error.get("detail"))
        else:
            error = {}
            message = str(raw_error)
        error.update(
            {
                "scope": error.get("scope", "company_year"),
                "corp_code": error.get("corp_code", company.get("corp_code")),
                "company_name": error.get("company_name", company.get("corp_name")),
                "year": error.get("year", year),
                "report_code": error.get("report_code", report_code),
                "code": error.get("code", "dart_error"),
                "message": message or "Unknown DART error",
            }
        )
        result.append(error)
    return result


def _missing_record(
    *,
    company: Mapping[str, Any],
    year: str | None,
    report_code: str | None,
    metric_id: str | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "scope": "metric" if metric_id else "observation",
        "corp_code": company.get("corp_code"),
        "company_name": company.get("corp_name"),
        "year": year,
        "report_code": report_code,
        "metric_id": metric_id,
        "reason": reason,
    }


def _remove_duplicate_missing(
    records: list[dict[str, Any]],
    *,
    company: Mapping[str, Any],
    year: str | None,
    report_code: str | None,
    metric_id: str,
) -> None:
    identity = (
        company.get("corp_code"),
        year,
        report_code,
        metric_id,
    )
    records[:] = [
        record
        for record in records
        if (
            record.get("corp_code"),
            record.get("year"),
            record.get("report_code"),
            record.get("metric_id"),
        )
        != identity
    ]


def _deduplicate_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        item = dict(record)
        identity = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if identity not in seen:
            result.append(item)
            seen.add(identity)
    return result


def _request_years(request: AnalysisRequest) -> tuple[str, ...]:
    if request.from_year is not None and request.to_year is not None:
        try:
            start = int(request.from_year)
            end = int(request.to_year)
        except ValueError:
            return (request.from_year, request.to_year)
        if start <= end and end - start <= 50:
            return tuple(str(year) for year in range(start, end + 1))
    if request.year is not None:
        return (request.year,)
    return ()


def _observation_sort_key(corp_codes: Sequence[str]):
    order = {code: index for index, code in enumerate(corp_codes)}

    def key(item: Mapping[str, Any]) -> tuple[Any, str, str]:
        corp_code = str(item.get("corp_code") or "")
        year = str(item.get("year") or "")
        return order.get(corp_code, len(order)), corp_code, year

    return key


def _normalise_sort(sort: Any) -> dict[str, Any]:
    if sort is None or sort == "":
        return {"by": None, "direction": "desc"}
    if isinstance(sort, Mapping):
        metric = _first_text(sort.get("by"), sort.get("metric_id"), sort.get("field"))
        direction = _normalise_direction(sort.get("direction", sort.get("dir")))
        return {"by": metric, "direction": direction}
    if isinstance(sort, Sequence) and not isinstance(sort, (str, bytes)):
        values = list(sort)
        metric = _first_text(values[0] if values else None)
        direction = _normalise_direction(values[1] if len(values) > 1 else None)
        return {"by": metric, "direction": direction}
    text = str(sort).strip()
    direction = "desc"
    if text.startswith("-"):
        text, direction = text[1:].strip(), "desc"
    elif ":" in text:
        text, raw_direction = text.rsplit(":", 1)
        direction = _normalise_direction(raw_direction)
    elif " " in text:
        parts = text.split()
        if parts[-1].lower() in {"asc", "desc"}:
            text, direction = " ".join(parts[:-1]), parts[-1].lower()
    return {"by": text or None, "direction": direction}


def _normalise_direction(value: Any) -> str:
    return "asc" if str(value or "desc").lower() == "asc" else "desc"


def _adapter_is_configured(adapter: ClaudeMCPAdapter | None) -> bool:
    if adapter is None:
        return False
    configured = getattr(adapter, "configured", True)
    if callable(configured):
        configured = configured()
    return bool(configured)


def _is_not_configured_result(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    status = str(result.get("status", "")).lower()
    return status in {"not_configured", "unconfigured", "disabled"}


def _is_provider_error_result(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    return str(result.get("status", "")).lower() in {"error", "failed", "failure"}


def _provider_error_message(result: Mapping[str, Any]) -> str:
    for key in ("error_message", "error", "message"):
        value = result.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "Claude MCP provider returned an error."


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _first_present(item: Mapping[str, Any], inherited: Mapping[str, Any], key: str) -> Any:
    if key in item:
        return item[key]
    return inherited.get(key)


__all__ = [
    "AnalysisOrchestrator",
    "AnalysisRequest",
    "ClaudeMCPAdapter",
    "MAX_CORP_CODES",
    "NotConfiguredClaudeMCPAdapter",
    "build_analysis_context",
    "build_structured_prompt",
]
