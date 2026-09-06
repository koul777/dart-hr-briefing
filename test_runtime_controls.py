from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor

from runtime_controls import (
    BoundedTTLCache,
    OrchestrationTelemetry,
    SlidingWindowRateLimiter,
    StripedLockPool,
    anonymized_client_key,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RuntimeControlTests(unittest.TestCase):
    def test_striped_lock_pool_is_bounded_and_key_stable(self) -> None:
        pool = StripedLockPool(8)

        self.assertIs(pool.lock_for("same"), pool.lock_for("same"))
        self.assertEqual(pool.stripes, 8)
        with self.assertRaises(ValueError):
            StripedLockPool(0)

    def test_cache_expires_and_returns_defensive_copies(self) -> None:
        clock = FakeClock()
        cache = BoundedTTLCache(max_entries=2, ttl_seconds=10, clock=clock)
        cache.set("a", {"values": [1]})

        found, value = cache.get("a")
        value["values"].append(2)
        found_again, value_again = cache.get("a")
        clock.advance(11)
        found_expired, _ = cache.get("a")

        self.assertTrue(found and found_again)
        self.assertEqual(value_again, {"values": [1]})
        self.assertFalse(found_expired)
        self.assertEqual(cache.stats()["entries"], 0)

    def test_cache_uses_lru_eviction_and_stays_bounded(self) -> None:
        cache = BoundedTTLCache(max_entries=2, ttl_seconds=10)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)

        found_a, _ = cache.get("a")
        found_b, _ = cache.get("b")
        found_c, _ = cache.get("c")

        self.assertTrue(found_a and found_c)
        self.assertFalse(found_b)
        self.assertEqual(cache.stats()["evictions"], 1)

    def test_cache_enforces_aggregate_weight_and_skips_oversize_values(self) -> None:
        cache = BoundedTTLCache(max_entries=10, max_weight=5, ttl_seconds=10)
        cache.set("a", {"value": "a"}, weight=3)
        cache.set("b", {"value": "b"}, weight=3)

        found_a, _ = cache.get("a")
        found_b, _ = cache.get("b")
        self.assertFalse(found_a)
        self.assertTrue(found_b)
        self.assertEqual(cache.stats()["weight"], 3)

        cache.set("too-large", {"value": "x"}, weight=6)
        found_oversize, _ = cache.get("too-large")
        self.assertFalse(found_oversize)
        self.assertEqual(cache.stats()["oversize_rejections"], 1)

    def test_cache_replacement_and_expiry_release_weight(self) -> None:
        clock = FakeClock()
        cache = BoundedTTLCache(
            max_entries=2,
            max_weight=10,
            ttl_seconds=10,
            clock=clock,
        )
        cache.set("a", 1, weight=7)
        cache.set("a", 2, weight=2)
        self.assertEqual(cache.stats()["weight"], 2)
        clock.advance(11)
        self.assertEqual(cache.stats()["weight"], 0)

    def test_rate_limiter_releases_client_after_window(self) -> None:
        clock = FakeClock()
        limiter = SlidingWindowRateLimiter(
            limit=2,
            window_seconds=60,
            max_clients=2,
            clock=clock,
        )

        first = limiter.allow("client")
        second = limiter.allow("client")
        rejected = limiter.allow("client")
        clock.advance(61)
        released = limiter.allow("client")

        self.assertTrue(first.allowed and second.allowed)
        self.assertEqual(second.remaining, 0)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.retry_after_seconds, 60)
        self.assertTrue(released.allowed)
        self.assertEqual(limiter.stats()["rejected"], 1)

    def test_client_keys_are_anonymized_and_salt_scoped(self) -> None:
        first = anonymized_client_key("127.0.0.1", salt="a")
        same = anonymized_client_key("127.0.0.1", salt="a")
        different = anonymized_client_key("127.0.0.1", salt="b")

        self.assertEqual(first, same)
        self.assertNotEqual(first, different)
        self.assertNotIn("127.0.0.1", first)

    def test_orchestration_telemetry_retains_only_bounded_aggregate_labels(self) -> None:
        telemetry = OrchestrationTelemetry()
        telemetry.record({
            "run_id": "RUN-secret",
            "question": "sensitive question",
            "status": "partial",
            "policy": {"status": "allowed", "reason": "private"},
            "provider": {"status": "rejected", "result": "private result"},
            "provider_validation": {"status": "rejected"},
            "evidence": {"ledger": [{
                "evidence_id": "EV-secret",
                "source_coverage_complete": True,
            }]},
            "trace": [{"agent": "x", "status": "error", "error": "secret"}],
        })
        telemetry.record({
            "status": "attacker-controlled-label",
            "provider_validation": {"status": "skipped"},
        })

        stats = telemetry.stats()

        self.assertEqual(stats["runs"], 2)
        self.assertEqual(stats["status_counts"], {"other": 1, "partial": 1})
        self.assertEqual(stats["evidence_total"], 1)
        self.assertEqual(stats["source_complete_evidence_total"], 1)
        self.assertEqual(stats["trace_error_total"], 1)
        self.assertEqual(
            stats["provider_validation_counts"],
            {"rejected": 1, "skipped": 1},
        )
        self.assertFalse(stats["contains_user_content"])
        serialized = str(stats)
        for secret in ("RUN-secret", "sensitive question", "private result", "EV-secret"):
            self.assertNotIn(secret, serialized)

    def test_orchestration_telemetry_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            OrchestrationTelemetry().record([])

    def test_orchestration_telemetry_updates_are_thread_safe(self) -> None:
        telemetry = OrchestrationTelemetry()
        result = {
            "status": "completed",
            "policy": {"status": "allowed"},
            "provider": {"status": "not_configured"},
            "provider_validation": {"status": "skipped"},
            "evidence": {"ledger": [
                {"source_coverage_complete": True},
                {"source_coverage_complete": False},
            ]},
            "trace": [],
        }

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _index: telemetry.record(result), range(200)))

        stats = telemetry.stats()
        self.assertEqual(stats["runs"], 200)
        self.assertEqual(stats["status_counts"], {"completed": 200})
        self.assertEqual(stats["evidence_total"], 400)
        self.assertEqual(stats["evidence_average"], 2.0)
        self.assertEqual(stats["source_complete_evidence_total"], 200)
        self.assertEqual(stats["source_complete_evidence_average"], 1.0)


if __name__ == "__main__":
    unittest.main()
