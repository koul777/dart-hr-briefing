from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import urlencode

from runtime_controls import BoundedTTLCache
from server import (
    DARTBudgetExceeded,
    DARTError,
    DARTRequestBudget,
    dart_request,
    fetch_financial_results,
)


class _FakeResponse:
    def __init__(self, body: bytes = b'{"status":"000","list":[]}') -> None:
        self.body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body[:size]


class DARTRequestBudgetTests(unittest.TestCase):
    def test_transient_failure_then_success_consumes_two_attempts(self) -> None:
        sleeps: list[float] = []
        budget = DARTRequestBudget(
            deadline_seconds=5,
            attempt_limit=3,
            clock=lambda: 0.0,
            sleeper=sleeps.append,
        )

        with (
            patch("server.API_KEY", "test-key"),
            patch("server.DART_RETRY_ATTEMPTS", 3),
            patch("server.DART_RETRY_BASE_DELAY_MS", 250),
            patch(
                "server.urlopen",
                side_effect=[URLError("temporary"), _FakeResponse()],
            ) as mocked,
        ):
            result = dart_request(
                "not-cacheable.json",
                {"corp_code": "001"},
                budget=budget,
            )

        self.assertEqual(result["status"], "000")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(budget.stats()["attempts"], 2)

    def test_attempt_budget_stops_before_a_third_network_attempt(self) -> None:
        budget = DARTRequestBudget(
            deadline_seconds=5,
            attempt_limit=2,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )

        with (
            patch("server.API_KEY", "test-key"),
            patch("server.DART_RETRY_ATTEMPTS", 3),
            patch("server.urlopen", side_effect=URLError("temporary")) as mocked,
        ):
            with self.assertRaises(DARTBudgetExceeded) as raised:
                dart_request("not-cacheable.json", {}, budget=budget)

        self.assertEqual(raised.exception.reason, "attempt_limit")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(budget.stats()["attempts"], 2)
        self.assertIn("범위를 줄이고", str(raised.exception))

    def test_shared_deadline_stops_retry_sleep_and_followup_attempt(self) -> None:
        budget = DARTRequestBudget(
            deadline_seconds=0.3,
            attempt_limit=10,
            clock=lambda: 0.0,
            sleeper=lambda _delay: self.fail("deadline must reject the retry sleep"),
        )

        with (
            patch("server.API_KEY", "test-key"),
            patch("server.DART_RETRY_ATTEMPTS", 3),
            patch("server.DART_RETRY_BASE_DELAY_MS", 250),
            patch("server.urlopen", side_effect=URLError("temporary")) as mocked,
        ):
            with self.assertRaises(DARTBudgetExceeded) as raised:
                dart_request("not-cacheable.json", {}, budget=budget)

        self.assertEqual(raised.exception.reason, "deadline")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(budget.stats()["attempts"], 1)

    def test_retry_ceiling_is_three_even_when_request_budget_is_larger(self) -> None:
        sleeps: list[float] = []
        budget = DARTRequestBudget(
            deadline_seconds=5,
            attempt_limit=10,
            clock=lambda: 0.0,
            sleeper=sleeps.append,
        )

        with (
            patch("server.API_KEY", "test-key"),
            patch("server.DART_RETRY_ATTEMPTS", 3),
            patch("server.DART_RETRY_BASE_DELAY_MS", 250),
            patch("server.urlopen", side_effect=URLError("temporary")) as mocked,
        ):
            with self.assertRaises(DARTError) as raised:
                dart_request("not-cacheable.json", {}, budget=budget)

        self.assertNotIsInstance(raised.exception, DARTBudgetExceeded)
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(budget.stats()["attempts"], 3)
        self.assertEqual(sleeps, [0.25, 0.5])

    def test_cache_hit_does_not_consume_request_attempt_budget(self) -> None:
        endpoint = "fnlttSinglAcnt.json"
        params = {"corp_code": "001", "bsns_year": "2024", "reprt_code": "11011"}
        cache_key = f"{endpoint}?{urlencode(sorted(params.items()))}"
        cache = BoundedTTLCache(max_entries=4, ttl_seconds=60)
        cache.set(cache_key, {"status": "000", "list": []})
        budget = DARTRequestBudget(
            deadline_seconds=5,
            attempt_limit=1,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )

        with (
            patch("server.API_KEY", "test-key"),
            patch("server.DART_RESPONSE_CACHE", cache),
            patch("server.urlopen") as mocked,
        ):
            result = dart_request(endpoint, params, budget=budget)

        self.assertEqual(result["status"], "000")
        mocked.assert_not_called()
        self.assertEqual(budget.stats()["attempts"], 0)

    def test_fanout_returns_partial_results_after_budget_exhaustion(self) -> None:
        companies = [
            {"corp_code": "001", "corp_name": "A사", "stock_code": ""},
            {"corp_code": "002", "corp_name": "B사", "stock_code": ""},
        ]
        budget = DARTRequestBudget(
            deadline_seconds=5,
            attempt_limit=1,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )

        def fake_fetch(
            company: dict[str, str],
            year: str,
            report_code: str,
            *,
            budget: DARTRequestBudget,
        ) -> dict[str, object]:
            base: dict[str, object] = {
                "company": company,
                "year": year,
                "report_code": report_code,
            }
            try:
                budget.timeout_for_attempt(1)
            except DARTBudgetExceeded as exc:
                return {**base, "financials": None, "error": str(exc)}
            return {**base, "financials": {"revenue": 1}}

        with (
            patch("server.selected_companies", return_value=companies),
            patch("server.fetch_company_financials", side_effect=fake_fetch),
        ):
            results = fetch_financial_results(
                ["001", "002"],
                "2024",
                "11011",
                budget,
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(
            sum(result.get("financials") is not None for result in results),
            1,
        )
        errors = [str(result.get("error") or "") for result in results]
        self.assertEqual(sum("범위를 줄이고" in error for error in errors), 1)


if __name__ == "__main__":
    unittest.main()
