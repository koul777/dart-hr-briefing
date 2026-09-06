const { chromium } = require("../video_work/node_modules/playwright-core");
const fs = require("fs");
const path = require("path");

const appUrl = process.env.DART_QA_URL || "http://127.0.0.1:8765";
const edgePath = process.env.DART_QA_BROWSER
  || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const outputDir = process.env.DART_QA_OUTPUT_DIR || "docs/assets";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function readSampleContract(page) {
  return page.evaluate(() => ({
    banner: document.querySelector("#sampleBanner")?.textContent?.trim() || "",
    bannerHidden: document.querySelector("#sampleBanner")?.classList.contains("hidden"),
    selectedCompanies: [...document.querySelectorAll("#selectedChips .company-row")]
      .map((node) => node.textContent.trim()),
    year: document.querySelector("#yearSelect")?.value || "",
    reportCode: document.querySelector("#reportSelect")?.value || "",
    source: document.querySelector("#dataSourceLabel")?.textContent?.trim() || "",
    apiStatus: document.querySelector("#apiStatus")?.textContent?.trim() || "",
    runLabel: document.querySelector("#runAiButton")?.textContent?.trim() || "",
    searchDisabled: document.querySelector("#companySearch")?.disabled,
    yearDisabled: document.querySelector("#yearSelect")?.disabled,
    reportDisabled: document.querySelector("#reportSelect")?.disabled,
    aiKeyDisabled: document.querySelector("#openAiApiKey")?.disabled,
    consentDisabled: document.querySelector("#aiTransferConsent")?.disabled,
    externalEvidenceLinks: [...document.querySelectorAll("#dashboard a[href]")]
      .filter((node) => /^https?:/i.test(node.href)).length,
    dashboardVisible: !document.querySelector("#dashboard")?.classList.contains("hidden"),
    bodySampleMode: document.body.classList.contains("sample-mode"),
  }));
}

async function desktopQa(browser, network) {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1050 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => network.push(request.url()));

  await page.goto(appUrl, { waitUntil: "networkidle", timeout: 60_000 });
  assert(await page.locator("#loadClassroomButton").isVisible(), "sample start button is not visible");
  fs.mkdirSync(outputDir, { recursive: true });
  const entryPath = path.join(outputDir, "classroom-sample-entry.png");
  await page.screenshot({ path: entryPath, fullPage: false });
  await page.locator("#loadClassroomButton").click();
  await page.locator("#dashboard:not(.hidden)").waitFor({ timeout: 60_000 });
  await page.waitForTimeout(1_200);

  const contract = await readSampleContract(page);
  const focusAfterLoad = await page.evaluate(() => document.activeElement?.id || "");
  assert(contract.bannerHidden === false, "sample banner is hidden");
  assert(contract.banner.includes("SAMPLE — SYNTHETIC DATA"), "sample watermark is missing");
  assert(contract.selectedCompanies.length === 2, "sample must select exactly two companies");
  assert(contract.selectedCompanies.every((name) => name.includes("샘플")), "sample company label is ambiguous");
  assert(contract.year === "2024" && contract.reportCode === "11011", "sample period is not deterministic");
  assert(contract.source.includes("합성 fixture"), "sample source label is missing");
  assert(contract.apiStatus.includes("외부 호출 없음"), "zero-network status is missing");
  assert(contract.runLabel === "합성 결정 브리핑 만들기", "deterministic brief label is missing");
  assert(contract.searchDisabled && contract.yearDisabled && contract.reportDisabled, "sample inputs are not locked");
  assert(contract.aiKeyDisabled && contract.consentDisabled, "provider controls must be disabled in sample mode");
  assert(contract.externalEvidenceLinks === 0, "sample mode exposed a network evidence link");
  assert(contract.dashboardVisible && contract.bodySampleMode, "sample dashboard state is inconsistent");
  assert(focusAfterLoad === "sampleBanner", "sample entry did not announce the mode boundary");

  await page.locator("#sampleBanner").scrollIntoViewIfNeeded();
  const bannerRect = await page.locator("#sampleBanner").boundingBox();
  assert(bannerRect && bannerRect.y >= 0 && bannerRect.y < 1050, "sample banner is outside the desktop viewport");
  const headerPath = path.join(outputDir, "classroom-sample-header.png");
  await page.screenshot({ path: headerPath, fullPage: false });
  const desktopPath = path.join(outputDir, "classroom-sample-ui.png");
  await page.screenshot({ path: desktopPath, fullPage: false });

  const requestsBeforeCompare = network.length;
  await page.locator("#compareButton").click();
  await page.waitForTimeout(250);
  assert(network.length === requestsBeforeCompare, "sample compare unexpectedly made a network request");

  const requestsBeforeBrief = network.length;
  await page.locator('#tabs [data-tab="strategy"]').click();
  await page.locator(".strategy-brief").waitFor({ timeout: 30_000 });
  await page.locator("#analysisPrompt").fill("두 가상 기업의 인당 생산성을 근거와 한계로 구분해줘");
  await page.locator("#runAiButton").click();
  await page.locator("#aiResult .ai-chat-message.assistant").waitFor({ timeout: 10_000 });
  const answer = await page.locator("#aiResult").textContent();
  assert(answer.includes("결정론적 브리핑"), "deterministic brief identity is missing");
  assert(answer.includes("외부 AI가 생성한 답변이 아닙니다"), "external-AI boundary is missing");
  assert(network.length === requestsBeforeBrief, "sample brief unexpectedly made a network request");

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#exportButton").click();
  const download = await downloadPromise;
  assert(download.suggestedFilename() === "classroom-synthetic-2024.csv", "sample export filename is unsafe");
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const csv = Buffer.concat(chunks).toString("utf8");
  assert(csv.startsWith("\ufeff"), "sample CSV must include a UTF-8 BOM");
  assert(csv.includes("SAMPLE — SYNTHETIC DATA"), "sample CSV watermark is missing");
  assert(csv.includes("샘플전자") && csv.includes("샘플플랫폼"), "sample CSV companies are missing");
  await download.delete();

  const evidencePath = path.join(outputDir, "classroom-sample-strategy.png");
  await page.locator(".strategy-evidence").scrollIntoViewIfNeeded();
  await page.screenshot({ path: evidencePath, fullPage: false });

  await page.locator("#exitClassroomButton").click();
  const reset = await page.evaluate(() => ({
    bannerHidden: document.querySelector("#sampleBanner")?.classList.contains("hidden"),
    selectedCount: document.querySelectorAll("#selectedChips .company-row").length,
    searchDisabled: document.querySelector("#companySearch")?.disabled,
    dashboardHidden: document.querySelector("#dashboard")?.classList.contains("hidden"),
    welcomeVisible: !document.querySelector("#welcome")?.classList.contains("hidden"),
    focusedElement: document.activeElement?.id || "",
  }));
  assert(reset.bannerHidden && reset.selectedCount === 0 && !reset.searchDisabled, "sample exit did not reset live inputs");
  assert(reset.dashboardHidden && reset.welcomeVisible, "sample exit did not restore welcome screen");
  assert(reset.focusedElement === "loadClassroomButton", "sample exit did not restore keyboard focus");
  await page.locator("#openAiApiKey").scrollIntoViewIfNeeded();
  const liveAiPath = path.join(outputDir, "ai-live-consent-disconnect.png");
  await page.locator(".prompt-box").screenshot({ path: liveAiPath });
  assert(errors.length === 0, `browser errors: ${errors.join(" | ")}`);
  await page.close();
  return { contract, reset, entryPath, headerPath, desktopPath, evidencePath, liveAiPath };
}

async function mobileQa(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(appUrl, { waitUntil: "networkidle", timeout: 60_000 });
  await page.locator("#loadClassroomButton").click();
  await page.locator("#dashboard:not(.hidden)").waitFor({ timeout: 60_000 });
  await page.waitForTimeout(1_200);
  await page.locator("#sampleBanner").scrollIntoViewIfNeeded();
  const mobileControlsPath = path.join(outputDir, "classroom-sample-mobile-controls.png");
  await page.screenshot({ path: mobileControlsPath, fullPage: false });
  const layout = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
    bannerVisible: !document.querySelector("#sampleBanner")?.classList.contains("hidden"),
    exitVisible: Boolean(document.querySelector("#exitClassroomButton")?.getBoundingClientRect().width),
    exitHeight: document.querySelector("#exitClassroomButton")?.getBoundingClientRect().height || 0,
    bannerColumns: getComputedStyle(document.querySelector("#sampleBanner")).gridTemplateColumns,
  }));
  assert(layout.documentWidth <= layout.viewportWidth + 1, `mobile horizontal overflow: ${JSON.stringify(layout)}`);
  assert(layout.bannerVisible && layout.exitVisible, "mobile sample controls are not visible");
  assert(layout.exitHeight >= 44, "sample exit button touch target is below 44px");
  assert(!layout.bannerColumns.includes(" "), "sample banner did not collapse to one column on mobile");
  assert(errors.length === 0, `mobile browser errors: ${errors.join(" | ")}`);
  const mobilePath = path.join(outputDir, "classroom-sample-mobile.png");
  await page.screenshot({ path: mobilePath, fullPage: false });
  await page.close();
  return { layout, mobileControlsPath, mobilePath };
}

async function main() {
  const browser = await chromium.launch({ executablePath: edgePath, headless: true });
  const network = [];
  try {
    const desktop = await desktopQa(browser, network);
    const mobile = await mobileQa(browser);
    const localOrigin = new URL(appUrl).origin;
    const externalRequests = network.filter((url) => new URL(url).origin !== localOrigin);
    const forbiddenSampleRequests = network.filter((url) => /\/api\/(financials|people|analysis|workforce)/.test(url));
    assert(externalRequests.length === 0, `external request observed: ${externalRequests.join(", ")}`);
    assert(forbiddenSampleRequests.length === 0, `live API request observed: ${forbiddenSampleRequests.join(", ")}`);
    process.stdout.write(`${JSON.stringify({
      ok: true,
      appUrl,
      networkRequests: network,
      externalRequests,
      forbiddenSampleRequests,
      desktop,
      mobile,
    }, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
