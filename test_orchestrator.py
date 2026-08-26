import unittest

from orchestrator import AnalysisOrchestrator, AnalysisRequest


METRICS = [
    {
        "metric_id": "operating_profit",
        "label": "영업이익",
        "source_key": "operating_profit",
    }
]


def dart_result():
    return {
        "results": [
            {
                "company": {"corp_code": "001", "corp_name": "A사"},
                "year": "2024",
                "report_code": "11011",
                "metrics": {"operating_profit": 100},
                "source_url": "https://dart.fss.or.kr/example",
            }
        ]
    }


class FailingAdapter:
    configured = True

    def analyze(self, *, prompt, context):
        raise RuntimeError("provider unavailable")


class ErrorResultAdapter:
    configured = True

    def analyze(self, *, prompt, context):
        return {"status": "error", "error_message": "gateway rejected request"}


class CapturingAdapter:
    configured = True
    provider_id = "test_provider"
    provider_label = "Test Provider"

    def __init__(self):
        self.context = None

    def analyze(self, *, prompt, context):
        self.context = context
        return "briefing"


class AnalysisOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.request = AnalysisRequest(
            question="영업이익과 HR 시사점을 설명해줘",
            view="strategy",
            corp_codes=("001",),
            year="2024",
            report_code="11011",
            metric_ids=("operating_profit",),
        )

    def test_context_preserves_observation_and_source(self):
        result = AnalysisOrchestrator().build_context(self.request, dart_result(), METRICS)
        self.assertEqual(result["observations"][0]["metrics"]["operating_profit"], 100)
        self.assertEqual(result["observations"][0]["source_url"], "https://dart.fss.or.kr/example")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["errors"], [])

    def test_unconfigured_provider_returns_prompt_handoff(self):
        result = AnalysisOrchestrator().run(self.request, dart_result(), METRICS)
        self.assertEqual(result["provider_status"], "not_configured")
        self.assertIsNone(result["provider_result"])
        self.assertIn("STRUCTURED_ANALYSIS_CONTEXT", result["prompt"])

    def test_provider_failure_is_explicit(self):
        result = AnalysisOrchestrator(adapter=FailingAdapter()).run(self.request, dart_result(), METRICS)
        self.assertEqual(result["provider_status"], "error")
        self.assertIsNone(result["provider_result"])
        self.assertIn("provider unavailable", result["prompt_handoff"]["error"])

    def test_provider_error_result_is_not_marked_completed(self):
        result = AnalysisOrchestrator(adapter=ErrorResultAdapter()).run(self.request, dart_result(), METRICS)
        self.assertEqual(result["provider_status"], "error")
        self.assertIsNone(result["provider_result"])
        self.assertIn("gateway rejected request", result["prompt_handoff"]["error"])

    def test_extra_people_context_reaches_provider_before_generation(self):
        adapter = CapturingAdapter()
        result = AnalysisOrchestrator(adapter=adapter).run(
            self.request,
            dart_result(),
            METRICS,
            extra_context={"people_analytics": {"summary": "직원 100명"}},
        )
        self.assertEqual(result["provider_status"], "completed")
        self.assertEqual(result["provider"]["id"], "test_provider")
        self.assertEqual(adapter.context["people_analytics"]["summary"], "직원 100명")
        self.assertIn("직원 100명", result["prompt"])


if __name__ == "__main__":
    unittest.main()
