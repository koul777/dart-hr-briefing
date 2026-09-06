from __future__ import annotations

import re
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
            "AI POLICY",
            "evidence_count",
            "run_id",
            "renderStrategyDecisionBriefs",
            "decision_support?.briefs",
            "선택 기업 중앙값 위치",
            "별도 이력 참고",
            "대표 지표 ·",
            "metric_assessments",
            "strategyMetricQualityDetail",
            "strategy-metric-quality",
            "직원 현황",
            "다음 판단 행동",
            "cohort_limit",
            "산업·규모 보정 벤치마크가 아닙니다",
            "readiness 산정 제외",
            "strategyTrajectoryLabel(brief.selected_metric_id",
            "다음 내부 데이터",
            "NEEDED DATA",
            "average_salary_basis",
            "averageSalaryBasisLabel",
            "averageSalaryAggregateLabel",
            "people-salary-basis",
            "updateCoverageStrip",
            "initializeTabs",
            "aria-labelledby",
            "renderChangeSummary",
            "WHAT CHANGED",
            "전년 대비 가장 큰 사업 여력 변화",
            "근거 준비도 계산 중",
            "근거 신뢰",
            "선택 기업 비교 가능",
        )
        for marker in required_app_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

        required_style_markers = (
            "Unified HR Strategy theme",
            "--ref-bg:var(--paper)",
            "--ref-panel:var(--card)",
            "--ref-sam:var(--teal)",
            ".strategy-profit-column.forecast",
            ".strategy-profit-column.signed-axis i",
            "min-height:0",
            ".strategy-equity-ratio-track",
            ".ai-result[data-state=\"ready\"]",
            ".evidence-run-id",
            ".strategy-decision-grid",
            ".strategy-readiness-badge",
            ".strategy-readiness-matrix",
            ".strategy-decision-limit",
            ".strategy-decision-action",
            ".strategy-cohort-limit",
            ".change-summary-grid",
            ".change-card",
            ".strategy-gap-list",
        )
        for marker in required_style_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.styles)

        self.assertNotIn('classList.toggle("strategy-mode"', self.app)
        self.assertNotIn("LOCKED", self.app)
        self.assertIn('for="analysisPrompt"', self.index)
        self.assertIn('id="tabContent" role="tabpanel" aria-live="polite" tabindex="0"', self.index)
        self.assertLess(
            self.index.index('class="readout-card"'),
            self.index.index('id="tabContent"'),
        )

    def test_overview_preloads_global_decision_readiness(self) -> None:
        compare_start = self.app.index("async function compare()")
        compare_end = self.app.index("function buildPeopleContext()", compare_start)
        compare_function = self.app[compare_start:compare_end]

        self.assertIn("state.strategyLoading = true", compare_function)
        self.assertIn("renderDashboard();", compare_function)
        self.assertIn("loadStrategyData();", compare_function)
        self.assertNotIn('if (state.activeTab === "strategy") loadStrategyData();', compare_function)

    def test_boot_camp_learning_flow_is_visible_and_state_driven(self) -> None:
        for marker in (
            "HR AI AGENT BOOT CAMP",
            'id="workshopProgressSummary"',
            'data-workshop-step="1"',
            'data-workshop-step="4"',
            'data-question="선택 기업의 경쟁사 대비 인당 생산성 차이를 숫자로 비교해줘"',
            "인당 생산성 비교",
            "보상 전략 시사점",
            "공시 근거 확인",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.index)
        for marker in (
            "function comparisonMatchesSelection",
            "function updateWorkshopProgress",
            "state.selected.length >= 2",
            "message.evidence.length > 0",
            'document.querySelectorAll("[data-question]")',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        for marker in (".workshop-badge", ".workshop-progress", ".question-presets"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.styles)

    def test_ai_entrypoint_and_reference_values_are_not_hardcoded(self) -> None:
        self.assertIn('id="runAiButton"', self.index)
        self.assertIn('id="analysisPrompt"', self.index)
        self.assertIn('id="analysisPrompt" rows="3" maxlength="4000"', self.index)
        self.assertIn('id="openAiApiKey"', self.index)
        self.assertIn('id="openAiApiKey" type="password" maxlength="512"', self.index)
        self.assertIn('id="clearAiButton"', self.index)
        self.assertIn('id="appBuildInfo"', self.index)
        self.assertIn('const EXPECTED_APP_ID = "kr.opendart.dart-hr-briefing"', self.app)
        self.assertIn("payload?.app?.id !== EXPECTED_APP_ID", self.app)
        self.assertIn("payload.app.build_id", self.app)
        self.assertNotIn('id="connectApiButton"', self.index)
        self.assertNotIn('class="api-connect-box"', self.index)
        self.assertGreater(self.index.index('id="openAiApiKey"'), self.index.index("AI HR 브리핑"))
        self.assertIn("DART HR Briefing", self.index)
        self.assertIn("AI에게 질문하기", self.index)
        self.assertIn('"X-OpenAI-API-Key"', self.app)
        self.assertIn('return state.openAiKey ?', self.app)
        self.assertNotIn('return state.openAiConnected && state.openAiKey ?', self.app)
        self.assertIn("conversationQuestion", self.app)
        self.assertIn("const redactCredentialText", self.app)
        self.assertIn("const question = redactCredentialText(rawQuestion)", self.app)
        self.assertIn('const question = redactCredentialText($("#analysisPrompt").value.trim())', self.app)
        self.assertIn("function scatterAxisPosition", self.app)
        self.assertIn("const contributing = values.filter((row) => row.weight > 0)", self.app)
        self.assertIn("questionInput.value = question", self.app)
        self.assertIn("redactCredentialText(message.content)", self.app)
        self.assertNotIn('localstorage.setitem("openai', self.app.lower())
        self.assertIn("const safeStorageGet", self.app)
        self.assertIn("const safeStorageSet", self.app)
        self.assertIn('safeStorageGet("dart-theme")', self.app)
        self.assertIn('safeStorageSet("dart-theme"', self.app)
        self.assertNotIn('localStorage.getItem("dart-theme")', self.app)
        self.assertNotIn('localStorage.setItem("dart-theme"', self.app)
        for forbidden in ("삼성전자", "SK하이닉스", "43.6", "47.2", "1.58", "1.85"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.app)

    def test_rejected_ai_output_uses_validated_evidence_fallback(self) -> None:
        for marker in (
            "function buildValidatedFallback",
            'providerStatus === "rejected"',
            "buildValidatedFallback(payload)",
            "payload.provider_validation || payload.provider_output_validation",
            "서버가 검증한 OpenDART 근거만 표시합니다.",
            "인과관계나 개인의 성과·채용·평가 판단을 뜻하지 않습니다.",
            "guardedFallback: true",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        self.assertIn("evidenceSourceUrl(item)", self.app)
        self.assertIn("item.source_coverage_complete === true", self.app)

    def test_people_response_reuses_executive_metrics(self) -> None:
        self.assertIn("executivesFromPeople", self.app)
        self.assertNotIn("/api/executives?", self.app)

    def test_people_summary_uses_partial_coverage_without_hiding_it(self) -> None:
        for marker in (
            "const sumStat = (key)",
            "const weightedStat = (key",
            '.filter((row) => row.value !== null && row.weight > 0)',
            "const coverageLabel = (coverage, suffix)",
            "개 기업 사용 ·",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        self.assertNotIn(
            "rows.some((row) => row.value === null || !row.weight)",
            self.app,
        )
        self.assertIn('return "직원수 가중 · 계산 기준 혼합"', self.app)
        self.assertIn("평균 급여 계산 기준 ${averageSalaryBasisLabel(", self.app)

    def test_strategy_get_is_deterministic_and_evidence_citations_are_linked(self) -> None:
        start = self.app.index("async function requestWorkforceOrchestration")
        end = self.app.index("function renderMetricPills", start)
        request_function = self.app[start:end]

        self.assertNotIn("aiRequestHeaders", request_function)
        self.assertIn("renderProviderEvidenceText", self.app)
        self.assertIn("renderEvidenceText(message.content, message.evidence)", self.app)
        self.assertIn("officialEvidenceUrl", self.app)
        self.assertIn("!url.username", self.app)
        self.assertIn('url.port === "443"', self.app)
        self.assertIn('url.pathname === "/dsaf001/main.do"', self.app)
        self.assertIn('"crtfc_key"', self.app)
        self.assertIn("payload.evidence?.ledger || []", self.app)
        self.assertIn("/^\\d{14}$/.test(receipt)", self.app)
        self.assertIn("evidence-citation", self.app)
        self.assertIn("AI 해석은 자동 실행하지 않습니다.", self.app)
        self.assertIn("item.company?.corp_name", self.app)
        self.assertIn("evidenceLabels[item.metric_id]", self.app)
        self.assertIn("정정공시 최신 여부는 별도 확인이 필요합니다.", self.app)
        self.assertIn('data_completeness: "근거 연결 완전성"', self.app)
        self.assertIn('restatement_not_verified: "정정공시 최신성 미확인"', self.app)
        self.assertIn('class="strategy-readiness-notice" role="note"', self.app)
        self.assertIn("정정공시 최신성 미검증", self.app)
        self.assertIn("최신 정정공시 대조 전 확정 판단에 사용하지 마세요.", self.app)
        self.assertIn("일부 공시 품질 경고로 근거 신뢰를 낮게 두었습니다.", self.app)
        self.assertIn('limited: "보수적 제한"', self.app)
        self.assertIn("선택 기업 ${eligibleObservationCount}개 범위 유지", self.app)
        self.assertIn('decisionSupportScope === "limited"', self.app)
        self.assertIn('term_end_partial_executive_count: "임기 종료일 일부 인원만 확인"', self.app)
        self.assertIn('tenure_not_parseable: "근속기간 일부 해석 불가"', self.app)
        self.assertIn("이익 체력 · 보상 공시 · 급여 지표 · DART 근거", self.app)
        self.assertIn("성과급 연동 산식", self.app)
        self.assertNotIn("이익 → 성과급 → 급여 연동", self.app)
        self.assertIn("어떤 조합으로 공시됐는지 비교", self.app)
        self.assertNotIn("인력 구조가 사업 성과를 얼마나 지지", self.app)
        self.assertIn('class="strategy-representative-notice"', self.app)
        self.assertIn("우선 지표보다 원문 연결 범위가 넓은 보조 지표", self.app)
        self.assertIn('allowed: "허용"', self.app)
        self.assertIn("정정공시 최신성은 아직 검증하지 않았습니다.", self.app)
        self.assertIn('class="strategy-readiness-boundary"', self.app)
        self.assertIn("승계 권고 아님 · 다음 확인", self.app)
        self.assertIn("const DEFAULT_HR_ANALYSIS_QUESTION", self.app)
        self.assertIn("인력 생산성·보상 지속가능성·인력구조 차이", self.app)
        self.assertNotIn("기업별 재무구조의 차이와 주의할 점", self.app)

    def test_async_results_are_context_bound_and_tabs_are_accessible(self) -> None:
        for marker in (
            "compareRequestToken",
            "aiRequestToken",
            "searchRequestToken",
            "dataSelectionKey",
            "cancelAiRequest",
            "resetAiConversationForContextChange",
            "invalidatePeriodRequests",
            "AbortController",
            "previouslyConnected",
            "Number.isFinite(number)",
            'typeof value === "boolean"',
            "Object.values(financials(item)).some",
            "keys.every((key) => valueFor(item, key) !== null)",
            "if (!marginLeader || !debtLeader || !liquidityLeader)",
            "values.every((value) => value !== null)",
            "item.component_quality?.employees?.warnings",
            "actual.length < 2",
            "달력 기준 12개월",
            "이전 응답을 폐기했습니다",
            "const nextResults = currentResult.value",
            "state.results = nextResults",
            ".map(officialEvidenceUrl).filter(Boolean)",
            'event.key === "ArrowRight"',
            "tab.tabIndex = active ? 0 : -1",
            "state.activeTab !== button.dataset.tab",
            "기준연도 또는 보고서가 바뀌었습니다",
            "typeof value === \"string\" && /^[\\t\\r\\n ]*[=+\\-@]/",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        self.assertIn('role="tablist"', self.index)
        self.assertIn('role="tab"', self.index)
        self.assertIn('tabindex="-1"', self.index)
        self.assertIn('role="tabpanel"', self.index)

    def test_search_and_interpretation_boundaries_remain_accessible(self) -> None:
        for marker in (
            'role="combobox"',
            'aria-autocomplete="list"',
            'aria-expanded="false"',
            'role="listbox"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.index)
        for marker in (
            "closeSearchResults",
            "setActiveSearchOption",
            'role="option"',
            'aria-activedescendant',
            'event.key === "ArrowDown"',
            'event.key === "Escape"',
            "relativeComparisonBoundary",
            "선택 기업 내부 상대 비교이며 인과·개인평가·자동 인사조치의 근거가 아닙니다.",
            "직접 알 수 없음:",
            'class="strategy-load-notice" role="alert"',
            "People 추이 실패:",
            "결정 브리프 실패:",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        for marker in (".result-item.active", ".comparison-boundary", ".strategy-load-notice"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.styles)

    def test_text_color_tokens_meet_wcag_aa_contrast(self) -> None:
        def tokens(pattern: str) -> dict[str, str]:
            match = re.search(pattern, self.styles, flags=re.MULTILINE)
            self.assertIsNotNone(match)
            return dict(re.findall(r"(--[a-z0-9-]+):(#(?:[0-9a-fA-F]{3}){1,2})", match.group(1)))

        def luminance(hex_color: str) -> float:
            value = hex_color.removeprefix("#")
            if len(value) == 3:
                value = "".join(character * 2 for character in value)
            channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [
                channel / 12.92
                if channel <= 0.04045
                else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(foreground: str, background: str) -> float:
            values = sorted((luminance(foreground), luminance(background)), reverse=True)
            return (values[0] + 0.05) / (values[1] + 0.05)

        light = tokens(r"^:root\{([^}]+)\}")
        dark = tokens(r'^\[data-theme="dark"\]\{([^}]+)\}')
        strategy = tokens(r"^\.strategy-brief\{(--ref-bg:[^}]+)\}")
        theme_pairs = (
            ("--ink", "--card"),
            ("--muted", "--card"),
            ("--muted", "--paper"),
            ("--faint", "--card"),
            ("--faint", "--paper"),
            ("--teal", "--card"),
            ("--coral", "--card"),
            ("--gold", "--card"),
        )
        for theme_name, theme in (("light", light), ("dark", dark)):
            for foreground, background in theme_pairs:
                with self.subTest(theme=theme_name, pair=(foreground, background)):
                    self.assertGreaterEqual(
                        contrast(theme[foreground], theme[background]),
                        4.5,
                    )
        for foreground in ("--ref-ink", "--ref-ink-dim", "--ref-ink-faint"):
            for background in ("--ref-panel", "--ref-panel-2"):
                with self.subTest(
                    theme="strategy",
                    foreground=foreground,
                    background=background,
                ):
                    self.assertGreaterEqual(
                        contrast(strategy[foreground], strategy[background]),
                        4.5,
                    )


if __name__ == "__main__":
    unittest.main()
