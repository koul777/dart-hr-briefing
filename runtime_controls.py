"""Thread-safe bounded runtime controls for the local and serverless API."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import Counter, OrderedDict, deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping


Clock = Callable[[], float]


class BoundedTTLCache:
    """In-memory TTL cache with LRU eviction and aggregate-only metrics."""

    def __init__(
        self,
        *,
        max_entries: int = 512,
        max_weight: int | None = None,
        ttl_seconds: float = 300,
        clock: Clock = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        if max_weight is not None and max_weight < 1:
            raise ValueError("max_weight must be positive when provided")
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be finite and positive")
        self.max_entries = int(max_entries)
        self.max_weight = int(max_weight) if max_weight is not None else None
        self.ttl_seconds = float(ttl_seconds)
        self.clock = clock
        self._entries: OrderedDict[str, tuple[float, Any, int]] = OrderedDict()
        self._total_weight = 0
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._oversize_rejections = 0

    def get(self, key: str) -> tuple[bool, Any]:
        now = self.clock()
        with self._lock:
            self._prune_expired(now)
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return False, None
            expires_at, value, _weight = entry
            if expires_at <= now:
                self._remove(key)
                self._misses += 1
                return False, None
            self._entries.move_to_end(key)
            self._hits += 1
            return True, deepcopy(value)

    def set(self, key: str, value: Any, *, weight: int = 1) -> None:
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
            raise ValueError("weight must be a positive integer")
        now = self.clock()
        with self._lock:
            self._prune_expired(now)
            self._remove(key)
            if self.max_weight is not None and weight > self.max_weight:
                self._oversize_rejections += 1
                return
            self._entries[key] = (now + self.ttl_seconds, deepcopy(value), weight)
            self._total_weight += weight
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries or (
                self.max_weight is not None and self._total_weight > self.max_weight
            ):
                _evicted_key, (_expires_at, _value, evicted_weight) = self._entries.popitem(
                    last=False
                )
                self._total_weight -= evicted_weight
                self._evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._total_weight = 0

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            self._prune_expired(self.clock())
            return {
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "weight": self._total_weight,
                "max_weight": self.max_weight or 0,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "oversize_rejections": self._oversize_rejections,
            }

    def _prune_expired(self, now: float) -> None:
        expired = [
            key
            for key, (expires_at, _value, _weight) in self._entries.items()
            if expires_at <= now
        ]
        for key in expired:
            self._remove(key)

    def _remove(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._total_weight -= entry[2]


class StripedLockPool:
    """A fixed-size lock set for bounded same-key request coalescing."""

    def __init__(self, stripes: int = 64) -> None:
        if stripes < 1:
            raise ValueError("stripes must be positive")
        self.stripes = int(stripes)
        self._locks = tuple(threading.Lock() for _ in range(self.stripes))

    def lock_for(self, key: str) -> Any:
        digest = hashlib.sha256(str(key).encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % self.stripes
        return self._locks[index]


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    """Best-effort per-process limiter with bounded anonymized client state."""

    def __init__(
        self,
        *,
        limit: int = 30,
        window_seconds: float = 60,
        max_clients: int = 4096,
        clock: Clock = time.monotonic,
    ) -> None:
        if limit < 1 or max_clients < 1:
            raise ValueError("limit and max_clients must be positive")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("window_seconds must be finite and positive")
        self.limit = int(limit)
        self.window_seconds = float(window_seconds)
        self.max_clients = int(max_clients)
        self.clock = clock
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._allowed = 0
        self._rejected = 0

    def allow(self, key: str) -> RateLimitDecision:
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            requests = self._requests.setdefault(key, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()
            self._requests.move_to_end(key)
            while len(self._requests) > self.max_clients:
                self._requests.popitem(last=False)
            if len(requests) >= self.limit:
                retry_after = max(1, math.ceil(requests[0] + self.window_seconds - now))
                self._rejected += 1
                return RateLimitDecision(False, 0, retry_after)
            requests.append(now)
            self._allowed += 1
            return RateLimitDecision(True, self.limit - len(requests))

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            return {
                "clients": len(self._requests),
                "max_clients": self.max_clients,
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "allowed": self._allowed,
                "rejected": self._rejected,
            }


class OrchestrationTelemetry:
    """Thread-safe bounded-label metrics that never retain request content or IDs."""

    _RUN_STATUSES = {"completed", "partial", "no_data", "error"}
    _POLICY_STATUSES = {"allowed", "blocked", "not_run"}
    _PROVIDER_STATUSES = {
        "completed",
        "rejected",
        "skipped",
        "not_configured",
        "unavailable",
        "error",
    }
    _VALIDATION_STATUSES = {"passed", "rejected", "skipped", "not_run"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs = 0
        self._status_counts: Counter[str] = Counter()
        self._policy_counts: Counter[str] = Counter()
        self._provider_counts: Counter[str] = Counter()
        self._provider_validation_counts: Counter[str] = Counter()
        self._evidence_total = 0
        self._source_complete_evidence_total = 0
        self._trace_error_total = 0

    @staticmethod
    def _bucket(value: Any, allowed: set[str], default: str) -> str:
        normalized = str(value or default).strip().lower() or default
        return normalized if normalized in allowed else "other"

    def record(self, result: Mapping[str, Any]) -> None:
        if not isinstance(result, Mapping):
            raise TypeError("orchestration telemetry requires a mapping")
        status = self._bucket(result.get("status"), self._RUN_STATUSES, "error")
        policy = result.get("policy") if isinstance(result.get("policy"), Mapping) else {}
        provider = result.get("provider") if isinstance(result.get("provider"), Mapping) else {}
        validation = (
            result.get("provider_validation")
            if isinstance(result.get("provider_validation"), Mapping)
            else {}
        )
        policy_status = self._bucket(
            policy.get("status"), self._POLICY_STATUSES, "not_run"
        )
        provider_status = self._bucket(
            provider.get("status"), self._PROVIDER_STATUSES, "skipped"
        )
        validation_status = self._bucket(
            validation.get("status"), self._VALIDATION_STATUSES, "not_run"
        )
        evidence = result.get("evidence") if isinstance(result.get("evidence"), Mapping) else {}
        ledger = evidence.get("ledger")
        evidence_count = len(ledger) if isinstance(ledger, (list, tuple)) else 0
        source_complete_evidence_count = sum(
            1
            for item in ledger
            if isinstance(item, Mapping) and item.get("source_coverage_complete") is True
        ) if isinstance(ledger, (list, tuple)) else 0
        trace = result.get("trace")
        trace_errors = sum(
            1
            for item in trace
            if isinstance(item, Mapping) and item.get("status") == "error"
        ) if isinstance(trace, (list, tuple)) else 0

        with self._lock:
            self._runs += 1
            self._status_counts[status] += 1
            self._policy_counts[policy_status] += 1
            self._provider_counts[provider_status] += 1
            self._provider_validation_counts[validation_status] += 1
            self._evidence_total += evidence_count
            self._source_complete_evidence_total += source_complete_evidence_count
            self._trace_error_total += trace_errors

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "runs": self._runs,
                "status_counts": dict(sorted(self._status_counts.items())),
                "policy_counts": dict(sorted(self._policy_counts.items())),
                "provider_counts": dict(sorted(self._provider_counts.items())),
                "provider_validation_counts": dict(
                    sorted(self._provider_validation_counts.items())
                ),
                "evidence_total": self._evidence_total,
                "evidence_average": round(self._evidence_total / self._runs, 2)
                if self._runs
                else 0.0,
                "source_complete_evidence_total": self._source_complete_evidence_total,
                "source_complete_evidence_average": round(
                    self._source_complete_evidence_total / self._runs,
                    2,
                ) if self._runs else 0.0,
                "trace_error_total": self._trace_error_total,
                "contains_user_content": False,
            }


def anonymized_client_key(value: str, *, salt: str) -> str:
    """Create a process-local identifier without retaining the source address."""

    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:24]


__all__ = [
    "BoundedTTLCache",
    "RateLimitDecision",
    "OrchestrationTelemetry",
    "SlidingWindowRateLimiter",
    "StripedLockPool",
    "anonymized_client_key",
]
