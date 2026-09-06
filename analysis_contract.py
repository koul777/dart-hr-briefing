"""Provider-neutral HTTP analysis request contract shared by server generations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


MAX_CORP_CODES = 8
MAX_METRIC_IDS = 100
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 500


def _normalise_tokens(
    value: Any,
    *,
    field_name: str,
    max_items: int,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.split(",")
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    raw_limit = max(32, max_items * 4)
    if len(values) > raw_limit:
        raise ValueError(f"{field_name} contains too many raw values")
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip()
        if text and text not in seen:
            if len(result) >= max_items:
                raise ValueError(f"{field_name} must contain at most {max_items} values")
            seen.add(text)
            result.append(text)
    return tuple(result)


def _normalise_year(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """Validated, normalized user-controlled state for an analysis handoff."""

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
        object.__setattr__(
            self,
            "corp_codes",
            _normalise_tokens(
                self.corp_codes,
                field_name="corp_codes",
                max_items=MAX_CORP_CODES,
            ),
        )
        object.__setattr__(
            self,
            "metric_ids",
            _normalise_tokens(
                self.metric_ids,
                field_name="metric_ids",
                max_items=MAX_METRIC_IDS,
            ),
        )
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
        payload = asdict(self)
        payload["corp_codes"] = list(self.corp_codes)
        payload["metric_ids"] = list(self.metric_ids)
        if isinstance(self.sort, tuple):
            payload["sort"] = list(self.sort)
        return payload


__all__ = [
    "AnalysisRequest",
    "DEFAULT_PAGE",
    "DEFAULT_PAGE_SIZE",
    "MAX_CORP_CODES",
    "MAX_METRIC_IDS",
    "MAX_PAGE_SIZE",
]
