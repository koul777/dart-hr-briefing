import unittest

from agent_orchestration import WorkforceAgentOrchestrator


class FakeProvider:
    configured = True

    def __init__(self):
        self.context = None

    def analyze(self, *, prompt, context):
        self.context = context
        return {"summary": "검증된 집계 지표 기반 해석"}


def observation(code, name, employee_total, outside_directors, revenue):
    return {
        "company": {"corp_code": code, "corp_name": name},
        "year": "2024",
        "report_code": "11011",
        "employee_rows": [
            {
                "fo_bbm": "성별합계",
                "sexdstn": "전체",
                "sm": str(employee_total),
                "rgllbr_co": str(employee_total - 10),
                "cnttk_co": "10",
                "avrg_cnwk_sdytrn": "5.0",
                "fyer_salary_totamt": "1000000",
                "jan_salary_am": "10000",
            }
        ],
        "executive_rows": [
            {
                "nm": "개인 이름은 결과에 없어야 함",
                "sexdstn": "여",
                "ofcps": "대표이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "상근",
                "hffc_pd": "66개월",
                "tenure_end_on": "2026년 06월 30일",
                "stlm_dt": "2024-12-31",
            },
            *[
                {
                    "sexdstn": "남",
                    "ofcps": "사외이사",
                    "rgist_exctv_at": "등기임원",
                    "fte_at": "비상근",
                    "hffc_pd": "10개월",
                    "tenure_end_on": "2026년 06월 30일",
                    "stlm_dt": "2024-12-31",
                }
                for _ in range(outside_directors)
            ],
        ],
        "unregistered_pay_rows": [
            {"nmpr": "2", "fyer_salary_totamt": "200000", "jan_salary_am": "100000"}
        ],
        "financials": {"revenue": revenue, "operating_profit": 100},
        "source_urls": [f"https://dart.fss.or.kr/{code}"],
    }


class AgentOrchestrationTests(unittest.TestCase):
    def test_dag_runs_normalizers_and_provider_after_privacy_guard(self):
        provider = FakeProvider()
        result = WorkforceAgentOrchestrator(provider=provider).run([
            observation("001", "A사", 100, 1, 10000),
            observation("002", "B사", 200, 2, 30000),
        ])

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["privacy"]["status"], "passed")
        self.assertEqual(result["validation"]["status"], "passed")
        self.assertEqual(result["provider"]["status"], "completed")
        self.assertEqual(result["benchmarks"]["rankings"]["employees_total"][0]["company"]["corp_code"], "002")
        self.assertNotIn("개인 이름은 결과에 없어야 함", str(result))
        trace_names = {item["agent"] for item in result["trace"]}
        self.assertIn("employee_normalizer", trace_names)
        self.assertIn("executive_normalizer", trace_names)
        self.assertIn("privacy_guard", trace_names)
        self.assertIn("strategy_interpreter", trace_names)

    def test_without_provider_facts_still_return(self):
        result = WorkforceAgentOrchestrator().run([observation("001", "A사", 100, 1, 10000)])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["provider"]["status"], "not_configured")
        self.assertEqual(result["facts"]["records"][0]["metrics"]["employees_total"], 100)


if __name__ == "__main__":
    unittest.main()
