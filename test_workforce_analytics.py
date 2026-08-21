import unittest
from datetime import date

from workforce_analytics import build_workforce_summary, parse_months, summarize_executives


class WorkforceAnalyticsTests(unittest.TestCase):
    def test_parse_months_supports_months_and_years(self):
        self.assertEqual(parse_months("66개월"), 66)
        self.assertEqual(parse_months("2년 3개월"), 27)

    def test_executive_metrics_are_aggregated_without_personal_fields(self):
        result = summarize_executives(
            [
                {
                    "nm": "홍길동",
                    "sexdstn": "여",
                    "ofcps": "대표이사",
                    "rgist_exctv_at": "등기임원",
                    "fte_at": "상근",
                    "hffc_pd": "66개월",
                    "tenure_end_on": "2025년 12월 31일",
                    "stlm_dt": "2024-12-31",
                },
                {
                    "nm": "김철수",
                    "sexdstn": "남",
                    "ofcps": "사외이사",
                    "rgist_exctv_at": "등기임원",
                    "fte_at": "비상근",
                    "hffc_pd": "10개월",
                    "tenure_end_on": "2026년 06월 30일",
                    "stlm_dt": "2024-12-31",
                },
            ],
            as_of=date(2024, 12, 31),
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["executives_total"], 2)
        self.assertEqual(metrics["registered_executives"], 2)
        self.assertEqual(metrics["outside_directors"], 1)
        self.assertEqual(metrics["ceo_count"], 1)
        self.assertEqual(metrics["female_executives"], 1)
        self.assertEqual(metrics["term_expiring_within_12_months"], 1)
        self.assertNotIn("nm", result)
        self.assertNotIn("홍길동", str(result))

    def test_employee_and_executive_metrics_merge(self):
        result = build_workforce_summary(
            employee_rows=[
                {
                    "fo_bbm": "성별합계",
                    "sexdstn": "전체",
                    "sm": "100",
                    "rgllbr_co": "80",
                    "cnttk_co": "20",
                    "avrg_cnwk_sdytrn": "5.0",
                    "fyer_salary_totamt": "1000000",
                    "jan_salary_am": "10000",
                }
            ],
            executive_rows=[],
            unregistered_pay_rows=[],
        )
        self.assertEqual(result["metrics"]["employees_total"], 100)
        self.assertEqual(result["metrics"]["regular_share"], 80.0)
        self.assertIsNone(result["metrics"]["executives_total"])
        self.assertEqual(result["quality"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
