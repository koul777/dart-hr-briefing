from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class FrontendVisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

    def test_strategy_visual_layers_remain_wired(self) -> None:
        required_app_markers = (
            "renderStrategyProfitChart",
            "strategy-salary-chart",
            "FORECAST RANGE",
            "strategy-equity-ratio",
            "strategy-hero-companies",
            "DART / WORKFORCE INTELLIGENCE",
            "themeMeta",
            "strategy-ai-brief",
            "openAiConnected",
        )
        for marker in required_app_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        required_style_markers = (
            "#0e1218",
            "#151b24",
            "#242d3a",
            "body.strategy-mode",
            ".strategy-profit-column.forecast",
            ".strategy-equity-ratio-track",
            ".ai-result[data-state=\"ready\"]",
        )
        for marker in required_style_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.styles)

    def test_ai_entrypoint_and_reference_values_are_not_hardcoded(self) -> None:
        self.assertIn('id="runAiButton"', self.index)
        self.assertIn('id="analysisPrompt"', self.index)
        self.assertIn('id="openAiApiKey"', self.index)
        self.assertIn('id="clearAiButton"', self.index)
        self.assertNotIn('id="connectApiButton"', self.index)
        self.assertNotIn('class="api-connect-box"', self.index)
        self.assertGreater(self.index.index('id="openAiApiKey"'), self.index.index("AI HR 브리핑"))
        self.assertIn("DART HR Briefing", self.index)
        self.assertIn("AI에게 질문하기", self.index)
        self.assertIn('"X-OpenAI-API-Key"', self.app)
        self.assertIn("conversationQuestion", self.app)
        self.assertNotIn('localstorage.setitem("openai', self.app.lower())
        for forbidden in ("삼성전자", "SK하이닉스", "43.6", "47.2", "1.58", "1.85"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.app)


if __name__ == "__main__":
    unittest.main()
