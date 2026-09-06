import unittest
from datetime import date

from workforce_analytics import (
    build_workforce_summary,
    clean_text,
    parse_count,
    parse_months,
    parse_number,
    summarize_employees,
    summarize_executives,
    summarize_unregistered_pay,
)


class WorkforceAnalyticsTests(unittest.TestCase):
    def test_parse_months_supports_months_and_years(self):
        self.assertEqual(parse_months("66개월"), 66)
        self.assertEqual(parse_months("2년 3개월"), 27)
        self.assertIsNone(parse_months("-1년 24개월"))
        self.assertIsNone(parse_months("-3개월"))
        self.assertIsNone(parse_months("-12"))
        self.assertIsNone(parse_months("1e309년"))
        self.assertIsNone(parse_months("9" * 1000 + "년"))
        self.assertEqual(parse_months("약 2년"), 24)
        self.assertIsNone(parse_months("1201개월"))
        self.assertEqual(parse_months("100년"), 1200)

    def test_non_finite_and_negative_counts_are_rejected(self):
        self.assertEqual(parse_number(0), 0)
        self.assertEqual(parse_count(0), 0)
        self.assertIsNone(parse_number("NaN"))
        self.assertIsNone(parse_number("Infinity"))
        self.assertIsNone(parse_number("1e22"))
        self.assertEqual(parse_number("1e21"), 1e21)
        self.assertIsNone(parse_count("-1"))
        self.assertIsNone(parse_count("1.5"))
        self.assertIsNone(parse_count("1000000001"))
        self.assertEqual(parse_count("1000000000"), 1000000000)
        self.assertIsNone(parse_number("9" * 1000))
        self.assertIsNone(parse_number("(100"))
        self.assertIsNone(parse_number("(-100)"))
        self.assertEqual(parse_number("(100)"), -100)
        self.assertEqual(clean_text("A\u202eB\x00C\nD"), "ABC D")

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

    def test_average_salary_prefers_weighted_disclosed_average(self):
        result = summarize_employees([
            {
                "fo_bbm": "반도체",
                "sexdstn": "남",
                "sm": "200",
                "rgllbr_co": "190",
                "cnttk_co": "10",
                "avrg_cnwk_sdytrn": "10",
                "fyer_salary_totamt": "18,000,000,000",
                "jan_salary_am": "100,000,000",
            },
            {
                "fo_bbm": "반도체",
                "sexdstn": "여",
                "sm": "100",
                "rgllbr_co": "95",
                "cnttk_co": "5",
                "avrg_cnwk_sdytrn": "8",
                "fyer_salary_totamt": "7,000,000,000",
                "jan_salary_am": "80,000,000",
            },
        ])

        self.assertAlmostEqual(result["metrics"]["average_salary"], 93_333_333.33333333)
        self.assertNotEqual(
            result["metrics"]["average_salary"],
            result["metrics"]["annual_salary_total"] / result["metrics"]["employees_total"],
        )
        self.assertEqual(
            result["metric_basis"]["average_salary"],
            "disclosed_average_headcount_weighted",
        )

    def test_average_salary_fallback_basis_is_explicit(self):
        result = summarize_employees([{
            "sexdstn": "전체",
            "sm": "10",
            "rgllbr_co": "9",
            "cnttk_co": "1",
            "avrg_cnwk_sdytrn": "5",
            "fyer_salary_totamt": "900000000",
            "jan_salary_am": "",
        }])

        self.assertEqual(result["metrics"]["average_salary"], 90_000_000)
        self.assertEqual(
            result["metric_basis"]["average_salary"],
            "annual_salary_total_per_employee_fallback",
        )

    def test_finite_inputs_cannot_overflow_aggregate_metrics(self):
        employees = summarize_employees([
            {
                "sexdstn": "남",
                "sm": "1",
                "rgllbr_co": "1",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "1e308",
                "fyer_salary_totamt": "1e308",
                "jan_salary_am": "1e308",
            },
            {
                "sexdstn": "여",
                "sm": "1",
                "rgllbr_co": "1",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "1e308",
                "fyer_salary_totamt": "1e308",
                "jan_salary_am": "1e308",
            },
        ])
        executives = summarize_executives([
            {
                "sexdstn": "남",
                "ofcps": "사내이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "상근",
                "hffc_pd": "1e308",
                "tenure_end_on": "2028년 12월 31일",
            },
            {
                "sexdstn": "여",
                "ofcps": "사외이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "비상근",
                "hffc_pd": "1e308",
                "tenure_end_on": "2028년 12월 31일",
            },
        ], as_of=date(2024, 12, 31))

        self.assertIsNone(employees["metrics"]["annual_salary_total"])
        self.assertIn(
            "fyer_salary_totamt_invalid_rows",
            employees["quality"]["warnings"],
        )
        self.assertIn(
            "avrg_cnwk_sdytrn_invalid_rows",
            employees["quality"]["warnings"],
        )
        self.assertIn(
            "jan_salary_am_invalid_rows",
            employees["quality"]["warnings"],
        )
        self.assertIsNone(employees["metrics"]["average_salary"])
        self.assertIsNone(employees["metrics"]["average_tenure_years"])
        self.assertIsNone(executives["metrics"]["average_tenure_months"])

    def test_gender_total_rows_from_multiple_business_units_are_not_dropped(self):
        result = summarize_employees([
            {
                "fo_bbm": "A사업부",
                "sexdstn": "전체",
                "sm": "60",
                "rgllbr_co": "50",
                "cnttk_co": "10",
                "avrg_cnwk_sdytrn": "5",
                "jan_salary_am": "50,000,000",
            },
            {
                "fo_bbm": "B사업부",
                "sexdstn": "전체",
                "sm": "40",
                "rgllbr_co": "35",
                "cnttk_co": "5",
                "avrg_cnwk_sdytrn": "4",
                "jan_salary_am": "40,000,000",
            },
        ])

        self.assertEqual(result["aggregation_mode"], "gender_total")
        self.assertEqual(result["metrics"]["employees_total"], 100)

    def test_disclosed_zero_counts_are_not_converted_to_missing(self):
        employees = summarize_employees([{
            "sexdstn": "전체",
            "sm": "10",
            "rgllbr_co": "10",
            "cnttk_co": "0",
            "rgllbr_abacpt_labrr_co": "0",
            "cnttk_abacpt_labrr_co": "0",
            "avrg_cnwk_sdytrn": "5",
            "jan_salary_am": "50000000",
        }])
        executives = summarize_executives([{
            "sexdstn": "남",
            "ofcps": "사내이사",
            "rgist_exctv_at": "등기임원",
            "fte_at": "상근",
            "hffc_pd": "12개월",
            "tenure_end_on": "2028년 12월 31일",
        }], as_of=date(2024, 12, 31))

        self.assertEqual(employees["metrics"]["contract_employees"], 0)
        self.assertEqual(employees["metrics"]["contract_short_time"], 0)
        self.assertEqual(executives["metrics"]["female_executives"], 0)
        self.assertEqual(executives["metrics"]["outside_directors"], 0)
        self.assertEqual(executives["metrics"]["term_expiring_within_12_months"], 0)

    def test_employee_tenure_supports_korean_year_month_text(self):
        result = summarize_employees([{
            "sexdstn": "전체",
            "sm": "10",
            "rgllbr_co": "10",
            "cnttk_co": "0",
            "avrg_cnwk_sdytrn": "6년 3개월",
            "jan_salary_am": "50000000",
        }])

        self.assertEqual(result["metrics"]["average_tenure_years"], 6.25)

    def test_inconsistent_employment_counts_do_not_create_over_100_percent_shares(self):
        result = summarize_employees([{
            "sexdstn": "전체",
            "sm": "10",
            "rgllbr_co": "9",
            "cnttk_co": "3",
            "avrg_cnwk_sdytrn": "5",
            "jan_salary_am": "50000000",
        }])

        self.assertIsNone(result["metrics"]["regular_share"])
        self.assertIsNone(result["metrics"]["contract_share"])
        self.assertIn(
            "employment_type_counts_exceed_total",
            result["quality"]["warnings"],
        )

    def test_missing_report_date_does_not_fall_back_to_wall_clock(self):
        result = summarize_executives([{
            "sexdstn": "남",
            "ofcps": "사내이사",
            "rgist_exctv_at": "등기임원",
            "fte_at": "상근",
            "hffc_pd": "12개월",
            "tenure_end_on": "2028년 12월 31일",
        }])

        self.assertIsNone(result["metrics"]["term_expiring_within_12_months"])
        self.assertIn("as_of_missing", result["quality"]["warnings"])

    def test_partial_executive_fields_do_not_become_false_zero_totals(self):
        result = summarize_executives([
            {
                "sexdstn": "여",
                "ofcps": "사내이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "상근",
                "hffc_pd": "12개월",
                "tenure_end_on": "2025년 6월 30일",
            },
            {
                "rgist_exctv_at": "미등기임원",
            },
        ], as_of=date(2024, 12, 31))

        metrics = result["metrics"]
        self.assertEqual(metrics["executives_total"], 2)
        self.assertEqual(metrics["registered_executives"], 1)
        self.assertEqual(metrics["unregistered_executives"], 1)
        self.assertIsNone(metrics["ceo_count"])
        self.assertIsNone(metrics["female_executives"])
        self.assertIsNone(metrics["female_share"])
        self.assertIsNone(metrics["full_time_executives"])
        self.assertIsNone(metrics["long_tenure_executives"])
        self.assertIsNone(metrics["term_expiring_within_12_months"])
        self.assertIsNone(metrics["average_tenure_months"])
        for warning in (
            "role_partial_executive_count",
            "gender_partial_executive_count",
            "employment_partial_executive_count",
            "tenure_partial_executive_count",
            "term_end_partial_executive_count",
        ):
            with self.subTest(warning=warning):
                self.assertIn(warning, result["quality"]["warnings"])

    def test_inside_director_role_can_come_from_assigned_job(self):
        result = summarize_executives(
            [
                {
                    "sexdstn": "남",
                    "ofcps": "",
                    "chrg_job": "사내이사",
                    "rgist_exctv_at": "등기임원",
                    "fte_at": "상근",
                    "hffc_pd": "12개월",
                    "tenure_end_on": "2026년 12월 31일",
                }
            ],
            as_of=date(2024, 12, 31),
        )

        self.assertEqual(result["metrics"]["inside_directors"], 1)
        self.assertEqual(result["quality"]["status"], "complete")

    def test_open_dart_director_categories_are_registered_roles(self):
        result = summarize_executives(
            [
                {
                    "sexdstn": "남",
                    "ofcps": "회장",
                    "chrg_job": "대표이사",
                    "rgist_exctv_at": "사내이사",
                    "fte_at": "상근",
                    "hffc_pd": "58개월",
                    "tenure_end_on": "2026년 3월 17일",
                },
                {
                    "sexdstn": "여",
                    "ofcps": "이사",
                    "chrg_job": "감사위원회 위원",
                    "rgist_exctv_at": "사외이사",
                    "fte_at": "비상근",
                    "hffc_pd": "34개월",
                    "tenure_end_on": "2025년 3월 15일",
                },
            ],
            as_of=date(2024, 12, 31),
        )

        self.assertEqual(result["metrics"]["registered_executives"], 2)
        self.assertEqual(result["metrics"]["inside_directors"], 1)
        self.assertEqual(result["metrics"]["outside_directors"], 1)
        self.assertEqual(result["metrics"]["outside_director_share"], 50)

    def test_unknown_registration_category_is_not_reported_as_zero(self):
        result = summarize_executives(
            [
                {
                    "sexdstn": "남",
                    "ofcps": "고문",
                    "rgist_exctv_at": "확인불가",
                    "fte_at": "상근",
                    "hffc_pd": "12개월",
                    "tenure_end_on": "2026년 12월 31일",
                }
            ],
            as_of=date(2024, 12, 31),
        )

        self.assertIsNone(result["metrics"]["registered_executives"])
        self.assertIsNone(result["metrics"]["unregistered_executives"])
        self.assertIn(
            "registration_partial_executive_count",
            result["quality"]["warnings"],
        )

    def test_fully_missing_executive_gender_is_visible_in_quality(self):
        result = summarize_executives([{
            "chrg_job": "대표이사",
            "rgist_exctv_at": "등기임원",
            "fte_at": "상근",
            "hffc_pd": "12개월",
            "tenure_end_on": "2026년 12월 31일",
        }], as_of=date(2024, 12, 31))

        self.assertIsNone(result["metrics"]["female_executives"])
        self.assertIsNone(result["metrics"]["female_share"])
        self.assertIn("sexdstn", result["quality"]["missing_fields"])
        self.assertNotIn("ofcps", result["quality"]["missing_fields"])
        self.assertEqual(result["quality"]["status"], "partial")

    def test_twelve_month_expiry_uses_calendar_boundary(self):
        result = summarize_executives([
            {
                "sexdstn": "남",
                "ofcps": "사내이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "상근",
                "hffc_pd": "12개월",
                "tenure_end_on": "2025년 12월 31일",
            },
            {
                "sexdstn": "여",
                "ofcps": "사외이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "비상근",
                "hffc_pd": "12개월",
                "tenure_end_on": "2026년 1월 1일",
            },
        ], as_of=date(2024, 12, 31))

        self.assertEqual(result["metrics"]["term_expiring_within_12_months"], 1)

        leap_result = summarize_executives([
            {
                "sexdstn": "남",
                "ofcps": "사내이사",
                "rgist_exctv_at": "등기임원",
                "fte_at": "상근",
                "hffc_pd": "12개월",
                "tenure_end_on": "2025년 2월 28일",
            },
        ], as_of=date(2024, 2, 29))
        self.assertEqual(leap_result["metrics"]["term_expiring_within_12_months"], 1)

    def test_unregistered_pay_uses_only_covered_average_headcount(self):
        result = summarize_unregistered_pay([
            {"nmpr": "2", "jan_salary_am": "100000000"},
            {"nmpr": "3", "fyer_salary_totamt": "240000000"},
        ])

        self.assertEqual(result["metrics"]["unregistered_pay_count"], 5)
        self.assertIsNone(result["metrics"]["unregistered_average_salary"])
        self.assertIn(
            "average_salary_partial_headcount",
            result["quality"]["warnings"],
        )

    def test_additive_totals_require_all_selected_rows(self):
        employees = summarize_employees([
            {
                "sexdstn": "남",
                "sm": "10",
                "rgllbr_co": "10",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "5",
                "jan_salary_am": "50000000",
            },
            {
                "sexdstn": "여",
                "rgllbr_co": "5",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "4",
                "jan_salary_am": "40000000",
            },
        ])
        pay = summarize_unregistered_pay([
            {"nmpr": "2", "fyer_salary_totamt": "200000000"},
            {"fyer_salary_totamt": "100000000"},
        ])

        self.assertIsNone(employees["metrics"]["employees_total"])
        self.assertIn("sm_partial_rows", employees["quality"]["warnings"])
        self.assertIsNone(pay["metrics"]["unregistered_pay_count"])
        self.assertIn("nmpr_partial_rows", pay["quality"]["warnings"])

    def test_complete_totals_can_supply_average_when_row_averages_are_partial(self):
        employees = summarize_employees([
            {
                "sexdstn": "남",
                "sm": "2",
                "rgllbr_co": "2",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "5",
                "fyer_salary_totamt": "200000000",
                "jan_salary_am": "100000000",
            },
            {
                "sexdstn": "여",
                "sm": "3",
                "rgllbr_co": "3",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "4",
                "fyer_salary_totamt": "240000000",
            },
        ])
        pay = summarize_unregistered_pay([
            {
                "nmpr": "2",
                "fyer_salary_totamt": "200000000",
                "jan_salary_am": "100000000",
            },
            {"nmpr": "3", "fyer_salary_totamt": "240000000"},
        ])

        self.assertEqual(employees["metrics"]["average_salary"], 88000000)
        self.assertEqual(pay["metrics"]["unregistered_average_salary"], 88000000)
        self.assertIn(
            "average_salary_partial_headcount",
            employees["quality"]["warnings"],
        )
        self.assertIn(
            "average_salary_partial_headcount",
            pay["quality"]["warnings"],
        )

    def test_zero_covered_headcount_is_still_reported_as_partial(self):
        employees = summarize_employees([
            {
                "sexdstn": "남",
                "sm": "0",
                "rgllbr_co": "0",
                "cnttk_co": "0",
                "avrg_cnwk_sdytrn": "5",
                "jan_salary_am": "50000000",
            },
            {
                "sexdstn": "여",
                "sm": "10",
                "rgllbr_co": "10",
                "cnttk_co": "0",
            },
        ])
        pay = summarize_unregistered_pay([
            {"nmpr": "0", "jan_salary_am": "100000000"},
            {"nmpr": "5"},
        ])

        self.assertIsNone(employees["metrics"]["average_tenure_years"])
        self.assertIsNone(employees["metrics"]["average_salary"])
        self.assertIn(
            "average_tenure_partial_headcount",
            employees["quality"]["warnings"],
        )
        self.assertIn(
            "average_salary_partial_headcount",
            employees["quality"]["warnings"],
        )
        self.assertIsNone(pay["metrics"]["unregistered_average_salary"])
        self.assertIn("average_salary_partial_headcount", pay["quality"]["warnings"])


if __name__ == "__main__":
    unittest.main()
