const { chromium } = require("../video_work/node_modules/playwright-core");
const fs = require("fs");
const path = require("path");

const appUrl = process.env.DART_QA_URL || "http://127.0.0.1:8765";
const edgePath = process.env.DART_QA_BROWSER
  || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const outputDir = process.env.DART_QA_OUTPUT_DIR
  || "training_deck/assets/screenshots";
const viewport = { width: 1280, height: 720 };
const qaDeadlineMs = 350;
const delayedResponseMs = 1_100;
const delayedHealthMs = 5_000;
const requestId = "qa-json-request-503";
const policyRequestId = "qa-policy-fallback-001";
const unsafeProviderDraft = "보호 특성을 근거로 직원을 자동 해고해야 합니다.";
const dummyApiKey = "sk-qa-dummy-key";
const forbiddenResponseText = [
  "sk-qa-dummy-private-key-must-not-render",
  "Traceback: internal only",
  "OPENAI_API_KEY",
];
const companies = [
  { corp_code: "00126380", corp_name: "QA 알파전자", stock_code: "005930" },
  { corp_code: "00164779", corp_name: "QA 베타모빌리티", stock_code: "005380" },
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function companyForCode(corpCode, stale = false) {
  const company = companies.find((item) => item.corp_code === corpCode)
    || { corp_code: corpCode, corp_name: `QA 기업 ${corpCode}`, stock_code: "" };
  return stale ? { ...company, corp_name: "폐기되어야 하는 지연 응답" } : { ...company };
}

function financialResult(company, year, stale = false) {
  const multiplier = company.corp_code === companies[0].corp_code ? 1 : 0.72;
  const yearFactor = Number(year) >= 2025 ? 1 : 0.91;
  return {
    company: companyForCode(company.corp_code, stale),
    year: String(year),
    report_code: "11011",
    financials: {
      assets: 510_000_000_000_000 * multiplier * yearFactor,
      liabilities: 140_000_000_000_000 * multiplier * yearFactor,
      equity: 370_000_000_000_000 * multiplier * yearFactor,
      cash: 48_000_000_000_000 * multiplier * yearFactor,
      revenue: 300_000_000_000_000 * multiplier * yearFactor,
      operating_profit: 31_000_000_000_000 * multiplier * yearFactor,
      operating_margin: 10.3,
      debt_ratio: 37.8,
      current_ratio: 2.14,
    },
    source_urls: [],
  };
}

function peopleResult(company, year, stale = false) {
  return {
    company: companyForCode(company.corp_code, stale),
    year: String(year),
    report_code: "11011",
    people: {
      employees_total: company.corp_code === companies[0].corp_code ? 124_000 : 72_000,
      regular_employees: company.corp_code === companies[0].corp_code ? 119_000 : 69_000,
      contract_employees: company.corp_code === companies[0].corp_code ? 5_000 : 3_000,
      average_tenure_years: 11.2,
      average_salary: 128_000_000,
      executives_total: 29,
    },
    source_urls: [],
  };
}

function codesFrom(url) {
  const requested = url.searchParams.get("corp_codes") || "";
  return requested.split(",").filter(Boolean).map((corpCode) => companyForCode(corpCode));
}

async function fulfillJson(route, body, status = 200, headers = {}) {
  try {
    await route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      headers,
      body: JSON.stringify(body),
    });
  } catch (_) {
    // An expected AbortController cancellation can dispose the intercepted route.
  }
}

async function delayedFulfill(route, callback) {
  await new Promise((resolve) => setTimeout(resolve, delayedResponseMs));
  await callback();
}

function installApiMock(page, scenario) {
  return page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    scenario.apiRequests.push(`${route.request().method()} ${url.pathname}${url.search}`);
    if (url.pathname === "/api/health") {
      if (scenario.mode === "health-delay-error") {
        await new Promise((resolve) => setTimeout(resolve, delayedHealthMs));
        await fulfillJson(route, {
          error: "QA health failure",
          request_id: "qa-health-race",
        }, 200, { "X-QA-HTTP-STATUS": "503" });
        return;
      }
      await fulfillJson(route, {
        ok: true,
        app: {
          id: "kr.opendart.dart-hr-briefing",
          name: "DART HR Briefing",
          version: "0.2.0-qa",
          build_id: "failure-recovery-qa",
          instance_id: "qa-browser",
          port: 8765,
        },
        api_key_configured: true,
      });
      return;
    }
    if (url.pathname === "/api/companies") {
      await fulfillJson(route, { companies });
      return;
    }
    if (url.pathname === "/api/classroom/bootstrap") {
      try {
        const response = await route.fetch();
        await route.fulfill({ response });
      } catch (_) {
        await fulfillJson(route, { error: "local classroom fixture unavailable" }, 503);
      }
      return;
    }
    if (scenario.mode === "stale-context" && url.pathname === "/api/analysis/context") {
      await delayedFulfill(route, () => fulfillJson(route, {
        prompt: "폐기되어야 하는 QA 알파전자 stale prompt",
      }));
      return;
    }
    if (scenario.mode === "ai-policy-rejected" && url.pathname === "/api/analysis") {
      const requestPayload = JSON.parse(route.request().postData() || "{}");
      scenario.analysisRequests.push({
        providerDataConsent: requestPayload.provider_data_consent,
        apiKey: route.request().headers()["x-openai-api-key"] || "",
      });
      await fulfillJson(route, {
        request: { metric_ids: ["revenue", "operating_profit"] },
        provider: {
          status: "rejected",
          name: "QA Mock Provider",
          result: unsafeProviderDraft,
        },
        provider_validation: {
          status: "rejected",
          violation_codes: [
            "automated_hr_action_recommendation",
            "protected_characteristic_judgment",
          ],
        },
        evidence: {
          ledger: [
            {
              evidence_id: "EV-111111111111",
              company: companies[0],
              metric_id: "revenue",
              value: 300_000_000_000_000,
              unit: "KRW",
              quality_status: "complete",
              source_coverage_complete: true,
              source_urls: ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250301000001"],
            },
            {
              evidence_id: "EV-222222222222",
              company: companies[1],
              metric_id: "operating_profit",
              value: 22_000_000_000_000,
              unit: "KRW",
              quality_status: "complete",
              source_coverage_complete: true,
              source_urls: ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250301000002"],
            },
          ],
        },
      }, 200, { "X-Request-ID": policyRequestId });
      return;
    }

    const requestedCompanies = codesFrom(url);
    if (scenario.mode === "timeout" && [
      "/api/financials",
      "/api/financials/history",
      "/api/people",
    ].includes(url.pathname)) {
      await delayedFulfill(route, () => fulfillJson(route, { error: "late timeout response" }));
      return;
    }
    if (scenario.mode === "request-id-error" && url.pathname === "/api/financials") {
      await fulfillJson(route, {
        error: "요청을 안전하게 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        request_id: requestId,
        detail: forbiddenResponseText[1],
        api_key: forbiddenResponseText[0],
        environment: forbiddenResponseText[2],
      }, 200, {
        "X-Request-ID": "qa-header-request-503",
        "X-QA-HTTP-STATUS": "503",
      });
      return;
    }
    if (scenario.mode === "stale-delay" && [
      "/api/financials",
      "/api/people",
    ].includes(url.pathname)) {
      await delayedFulfill(route, () => {
        if (url.pathname === "/api/financials") {
          const year = url.searchParams.get("year") || "2025";
          return fulfillJson(route, {
            results: requestedCompanies.map((company) => financialResult(company, year, true)),
          });
        }
        const year = url.searchParams.get("year") || "2025";
        return fulfillJson(route, {
          results: requestedCompanies.map((company) => peopleResult(company, year, true)),
        });
      });
      return;
    }

    if (url.pathname === "/api/financials") {
      const year = url.searchParams.get("year") || "2025";
      await fulfillJson(route, {
        results: requestedCompanies.map((company) => financialResult(company, year)),
      });
      return;
    }
    if (url.pathname === "/api/financials/history") {
      const fromYear = Number(url.searchParams.get("from_year") || 2020);
      const toYear = Number(url.searchParams.get("to_year") || 2025);
      await fulfillJson(route, {
        results: requestedCompanies.map((company) => ({
          company,
          years: Array.from({ length: toYear - fromYear + 1 }, (_, index) => {
            const year = String(fromYear + index);
            return financialResult(company, year);
          }),
        })),
      });
      return;
    }
    if (url.pathname === "/api/people") {
      const year = url.searchParams.get("year") || "2025";
      await fulfillJson(route, {
        results: requestedCompanies.map((company) => peopleResult(company, year)),
      });
      return;
    }
    if (url.pathname === "/api/people/history") {
      const fromYear = Number(url.searchParams.get("from_year") || 2022);
      const toYear = Number(url.searchParams.get("to_year") || 2025);
      await fulfillJson(route, {
        results: requestedCompanies.map((company) => ({
          company,
          years: Array.from({ length: toYear - fromYear + 1 }, (_, index) => {
            const year = String(fromYear + index);
            return peopleResult(company, year);
          }),
        })),
      });
      return;
    }
    if (url.pathname === "/api/workforce/orchestration") {
      await fulfillJson(route, { status: "partial", evidence: { ledger: [], summary: {} } });
      return;
    }
    await fulfillJson(route, { error: `unmocked QA endpoint: ${url.pathname}` }, 501);
  });
}

async function newQaPage(
  browser,
  name,
  { mode = "success", waitForHealth = true, deadlineMs = qaDeadlineMs } = {},
) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const scenario = {
    name,
    mode,
    apiRequests: [],
    analysisRequests: [],
    consoleErrors: [],
    pageErrors: [],
    externalRequests: [],
  };
  const appOrigin = new URL(appUrl).origin;
  page.on("console", (message) => {
    if (message.type() === "error") scenario.consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => scenario.pageErrors.push(error.message));
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== appOrigin) scenario.externalRequests.push(request.url());
  });
  await page.addInitScript((deadlineMs) => {
    window.__failureRecoveryQa = { abortedRequests: [], clipboardWrites: [] };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value) => {
          window.__failureRecoveryQa.clipboardWrites.push(String(value));
        },
      },
    });
    const nativeSetTimeout = window.setTimeout.bind(window);
    window.setTimeout = (callback, delay, ...args) => nativeSetTimeout(
      callback,
      delay === 45_000 ? deadlineMs : delay,
      ...args,
    );
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (resource, options = {}) => {
      try {
        const response = await nativeFetch(resource, options);
        const qaHttpStatus = Number(response.headers.get("X-QA-HTTP-STATUS") || 0);
        if (qaHttpStatus >= 400 && qaHttpStatus <= 599) {
          const headers = new Headers(response.headers);
          headers.delete("X-QA-HTTP-STATUS");
          return new Response(await response.text(), {
            status: qaHttpStatus,
            statusText: "QA synthetic HTTP error",
            headers,
          });
        }
        return response;
      } catch (error) {
        if (options.signal?.aborted) {
          window.__failureRecoveryQa.abortedRequests.push(String(resource));
        }
        throw error;
      }
    };
  }, deadlineMs);
  await installApiMock(page, scenario);
  await page.goto(appUrl, {
    waitUntil: waitForHealth ? "networkidle" : "domcontentloaded",
    timeout: 30_000,
  });
  if (waitForHealth) {
    await page.locator("#appBuildInfo").filter({ hasText: "failure-recovery-qa" }).waitFor();
  }
  return { page, scenario };
}

async function addComparisonCompanies(page) {
  for (const company of companies) {
    await page.locator("#companySearch").fill(company.corp_name);
    const option = page.locator("#searchResults [role=option]", { hasText: company.corp_name });
    await option.waitFor();
    await option.click();
  }
  await page.locator("#selectedChips .company-row").nth(1).waitFor();
  assert(await page.locator("#selectedChips .company-row").count() === 2, "two QA companies were not selected");
}

async function runSuccessfulComparison(page) {
  await page.locator("#compareButton").click();
  await page.locator("#dashboard:not(.hidden)").waitFor({ timeout: 5_000 });
  await page.locator("#compareButton:not([disabled])").waitFor({ timeout: 5_000 });
  await page.locator("#dataCoverage").filter({ hasText: "2 / 2" }).waitFor({ timeout: 5_000 });
}

async function captureFailureState(page, fileName) {
  const message = page.locator("#message");
  await message.scrollIntoViewIfNeeded();
  const box = await message.boundingBox();
  assert(box && box.y >= 0 && box.y < viewport.height, `${fileName}: recovery message is outside viewport`);
  const outputPath = path.resolve(outputDir, fileName);
  await page.screenshot({ path: outputPath, fullPage: false });
  const image = fs.readFileSync(outputPath);
  assert(image.length > 10_000, `${fileName}: screenshot is unexpectedly small`);
  return outputPath;
}

async function verifyNoBrowserErrors(scenario) {
  assert(scenario.consoleErrors.length === 0, `${scenario.name}: console errors: ${scenario.consoleErrors.join(" | ")}`);
  assert(scenario.pageErrors.length === 0, `${scenario.name}: page errors: ${scenario.pageErrors.join(" | ")}`);
  assert(scenario.externalRequests.length === 0, `${scenario.name}: external requests: ${scenario.externalRequests.join(" | ")}`);
}

async function timeoutScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "comparison-timeout");
  try {
    await addComparisonCompanies(page);
    scenario.mode = "timeout";
    await page.locator("#compareButton").click();
    await page.locator("#message").filter({ hasText: "요청 시간이 초과되었습니다." }).waitFor({ timeout: 5_000 });
    await page.locator("#compareButton:not([disabled])").waitFor({ timeout: 5_000 });
    const message = (await page.locator("#message").textContent()) || "";
    assert(message.includes("다시 시도"), "timeout recovery guidance is missing");
    const screenshot = await captureFailureState(page, "comparison-timeout.png");

    scenario.mode = "success";
    await runSuccessfulComparison(page);
    assert(!await page.locator("#dashboard").evaluate((node) => node.classList.contains("hidden")), "timeout retry did not recover");
    await verifyNoBrowserErrors(scenario);
    return { screenshot, message, retrySucceeded: true, ...scenario };
  } finally {
    await page.close();
  }
}

async function requestIdScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "request-id-error");
  try {
    await addComparisonCompanies(page);
    scenario.mode = "request-id-error";
    await page.locator("#compareButton").click();
    await page.locator("#message").filter({ hasText: requestId }).waitFor({ timeout: 5_000 });
    await page.locator("#compareButton:not([disabled])").waitFor({ timeout: 5_000 });
    const message = (await page.locator("#message").textContent()) || "";
    const bodyText = (await page.locator("body").textContent()) || "";
    assert(message.includes("요청 ID"), "request ID label is missing from the recovery message");
    assert(!message.includes("qa-header-request-503"), "lower-priority header request ID leaked into the message");
    for (const forbidden of forbiddenResponseText) {
      assert(!bodyText.includes(forbidden), `internal response detail rendered: ${forbidden}`);
    }
    const screenshot = await captureFailureState(page, "request-id-error.png");
    await verifyNoBrowserErrors(scenario);
    return { screenshot, message, safeDetailsHidden: true, ...scenario };
  } finally {
    await page.close();
  }
}

async function staleSelectionScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "selection-aborted");
  try {
    await addComparisonCompanies(page);
    await runSuccessfulComparison(page);
    scenario.mode = "stale-delay";
    await page.locator("#compareButton").click();
    await page.locator("#compareButton[disabled]").waitFor();
    await page.locator("#selectedChips .remove-company").last().click();
    await page.locator("#message").filter({ hasText: "기업 선택이 바뀌었습니다." }).waitFor();
    await page.waitForTimeout(delayedResponseMs + 250);
    await page.locator("#compareButton:not([disabled])").waitFor();
    const abortedRequests = await page.evaluate(() => window.__failureRecoveryQa.abortedRequests);
    const bodyText = (await page.locator("body").textContent()) || "";
    assert(abortedRequests.length >= 3, `expected at least three aborted requests, got ${abortedRequests.length}`);
    assert(await page.locator("#selectedChips .company-row").count() === 1, "changed selection was not preserved");
    assert(!bodyText.includes("폐기되어야 하는 지연 응답"), "stale response changed the rendered dashboard");
    const screenshot = await captureFailureState(page, "selection-aborted.png");
    await verifyNoBrowserErrors(scenario);
    return {
      screenshot,
      message: (await page.locator("#message").textContent()) || "",
      abortedRequests,
      staleResponseDiscarded: true,
      ...scenario,
    };
  } finally {
    await page.close();
  }
}

async function healthClassroomRaceScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "health-classroom-race", {
    mode: "health-delay-error",
    waitForHealth: false,
    deadlineMs: 10_000,
  });
  try {
    await page.locator("#loadClassroomButton").click();
    await page.locator("#sampleBanner:not(.hidden)").waitFor({ timeout: 5_000 });
    await page.waitForTimeout(delayedHealthMs + 250);
    const sampleState = await page.evaluate(() => ({
      sampleMode: document.body.classList.contains("sample-mode"),
      status: document.querySelector("#apiStatus")?.textContent?.trim() || "",
      message: document.querySelector("#message")?.textContent?.trim() || "",
    }));
    assert(sampleState.sampleMode, "health failure unexpectedly exited sample mode");
    assert(sampleState.status.includes("SAMPLE"), "late health failure overwrote the sample status");
    assert(sampleState.message.includes("SAMPLE — SYNTHETIC DATA"), "late health failure overwrote the sample guidance");

    await page.locator("#exitClassroomButton").click();
    const restoredState = await page.evaluate(() => ({
      sampleMode: document.body.classList.contains("sample-mode"),
      status: document.querySelector("#apiStatus")?.textContent?.trim() || "",
      message: document.querySelector("#message")?.textContent?.trim() || "",
    }));
    assert(!restoredState.sampleMode, "sample exit did not restore live mode");
    assert(restoredState.status === "서버 연결 필요", "live health failure status was not restored");
    assert(restoredState.message.includes("qa-health-race"), "restored health failure omitted the request ID");
    await verifyNoBrowserErrors(scenario);
    return { sampleState, restoredState, ...scenario };
  } finally {
    await page.close();
  }
}

async function stalePromptScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "stale-prompt-aborted");
  try {
    await addComparisonCompanies(page);
    scenario.mode = "stale-context";
    await page.locator("#copyPromptButton").click();
    await page.waitForTimeout(100);
    await page.locator("#selectedChips .remove-company").last().click();
    await page.waitForTimeout(delayedResponseMs + 250);
    const contract = await page.evaluate(() => ({
      clipboardWrites: window.__failureRecoveryQa.clipboardWrites,
      abortedRequests: window.__failureRecoveryQa.abortedRequests,
      message: document.querySelector("#message")?.textContent?.trim() || "",
      selectedCount: document.querySelectorAll("#selectedChips .company-row").length,
    }));
    assert(contract.selectedCount === 1, "prompt cancellation did not preserve the changed selection");
    assert(contract.clipboardWrites.length === 0, "stale context response updated the clipboard");
    assert(contract.abortedRequests.some((url) => url.includes("/api/analysis/context")), "context request was not aborted");
    assert(!contract.message.includes("복사했습니다"), "stale context response displayed a false success message");
    await verifyNoBrowserErrors(scenario);
    return { ...contract, ...scenario };
  } finally {
    await page.close();
  }
}

async function aiPolicyFallbackScenario(browser) {
  const { page, scenario } = await newQaPage(browser, "ai-policy-fallback");
  try {
    await addComparisonCompanies(page);
    await runSuccessfulComparison(page);
    scenario.mode = "ai-policy-rejected";
    await page.locator("#openAiApiKey").fill(dummyApiKey);
    await page.locator("#aiTransferConsent").check();
    await page.locator("#analysisPrompt").fill("근거가 확인된 집계 지표만 요약해줘");
    await page.locator("#runAiButton").click();
    const fallback = page.locator("#aiResult");
    await fallback.filter({ hasText: "AI 초안은 안전 검증에서 차단" }).waitFor({ timeout: 5_000 });
    const fallbackText = (await fallback.textContent()) || "";
    const bodyText = (await page.locator("body").textContent()) || "";
    for (const marker of (
      ["자동 인사조치 권고", "보호 특성에 근거한 개인 판단", policyRequestId, "EV-111111111111"]
    )) {
      assert(fallbackText.includes(marker), `policy fallback is missing: ${marker}`);
    }
    assert(!bodyText.includes(unsafeProviderDraft), "unsafe rejected provider draft rendered in the UI");
    assert(!bodyText.includes(dummyApiKey), "dummy API key rendered as visible text");
    assert(scenario.analysisRequests.length === 1, "AI policy fallback did not make exactly one mocked analysis request");
    assert(scenario.analysisRequests[0].providerDataConsent === true, "provider consent was not sent");
    assert(scenario.analysisRequests[0].apiKey === dummyApiKey, "dummy API key was not confined to the mocked request header");
    await fallback.scrollIntoViewIfNeeded();
    const screenshot = await captureFailureState(page, "ai-policy-fallback.png");
    await verifyNoBrowserErrors(scenario);
    return { screenshot, fallbackText, unsafeDraftHidden: true, ...scenario };
  } finally {
    await page.close();
  }
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: edgePath, headless: true });
  try {
    const timeout = await timeoutScenario(browser);
    const requestIdError = await requestIdScenario(browser);
    const selectionAborted = await staleSelectionScenario(browser);
    const healthClassroomRace = await healthClassroomRaceScenario(browser);
    const stalePromptAborted = await stalePromptScenario(browser);
    const aiPolicyFallback = await aiPolicyFallbackScenario(browser);
    process.stdout.write(`${JSON.stringify({
      ok: true,
      appUrl,
      viewport,
      apiIsolation: "Playwright mocks plus local zero-network classroom fixture",
      consoleErrors: 0,
      pageErrors: 0,
      timeout,
      requestIdError,
      selectionAborted,
      healthClassroomRace,
      stalePromptAborted,
      aiPolicyFallback,
    }, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
