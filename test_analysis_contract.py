from __future__ import annotations

import unittest

from analysis_contract import AnalysisRequest, MAX_CORP_CODES, MAX_PAGE_SIZE


class AnalysisRequestContractTests(unittest.TestCase):
    def test_normalizes_tokens_years_and_json_shape(self) -> None:
        request = AnalysisRequest(
            question="  질문  ",
            view="  strategy ",
            corp_codes=(" 001 ", "001", "002"),
            metric_ids=" employees_total, employees_total, average_salary ",
            year=2024,
            report_code=" 11011 ",
            sort=("employees_total", "desc"),
            page="2",
            page_size="40",
        )

        self.assertEqual(request.question, "질문")
        self.assertEqual(request.corp_codes, ("001", "002"))
        self.assertEqual(request.metric_ids, ("employees_total", "average_salary"))
        self.assertEqual(request.year, "2024")
        self.assertEqual(request.to_dict()["sort"], ["employees_total", "desc"])

    def test_rejects_pagination_and_company_bounds(self) -> None:
        invalid = (
            {"page": 0},
            {"page_size": 0},
            {"page_size": MAX_PAGE_SIZE + 1},
            {"page": "not-a-number"},
            {"corp_codes": tuple(str(index) for index in range(MAX_CORP_CODES + 1))},
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                AnalysisRequest(**arguments)

    def test_rejects_excessive_raw_or_unique_token_lists(self) -> None:
        with self.assertRaisesRegex(ValueError, "corp_codes contains too many raw values"):
            AnalysisRequest(corp_codes=("00000001",) * 33)
        with self.assertRaisesRegex(ValueError, "metric_ids must contain at most 100"):
            AnalysisRequest(metric_ids=tuple(f"metric_{index}" for index in range(101)))


if __name__ == "__main__":
    unittest.main()
