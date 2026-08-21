// DART Workforce Intelligence demo capture.
// The capture pattern follows Kminer2053/demo-video-skill:
// real headless browser interaction + html overlay + ffmpeg post-processing.
// Usage:
//   node tools/capture_dart_demo.js 0
//   node tools/capture_dart_demo.js all
//
// Environment:
//   APP=http://127.0.0.1:8768
//   SCR=C:\workspace\dart\video_work
//   CHROME_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
const fs = require("fs");
const path = require("path");

const SCR = process.env.SCR || path.resolve(__dirname, "..", "video_work");
const PLAYWRIGHT_CORE = process.env.PLAYWRIGHT_CORE || path.join(SCR, "node_modules", "playwright-core");
const { chromium } = require(PLAYWRIGHT_CORE);
const APP = process.env.APP || "http://127.0.0.1:8768";
const RAW = path.join(SCR, "clips_raw");
fs.mkdirSync(RAW, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function resolveChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) || null;
}

async function installOverlay(page, label) {
  await page.evaluate((initialLabel) => {
    const html = document.documentElement;
    const make = (id) => {
      const node = document.createElement("div");
      node.id = id;
      html.appendChild(node);
      return node;
    };
    make("__cap");
    const labelNode = make("__lbl");
    labelNode.textContent = initialLabel;
    make("__cur");
    const style = document.createElement("style");
    style.textContent = `
      #__cap{position:fixed;left:50%;bottom:54px;transform:translateX(-50%);background:rgba(15,18,28,.88);color:#fff;font:600 30px/1.45 -apple-system,'Apple SD Gothic Neo','Malgun Gothic',Segoe UI,Roboto,sans-serif;padding:16px 34px;border-radius:12px;z-index:2147483646;max-width:80%;text-align:center;opacity:0;transition:opacity .35s;box-shadow:0 8px 28px rgba(0,0,0,.35);letter-spacing:-.02em}
      #__cap.on{opacity:1}
      #__lbl{position:fixed;left:36px;bottom:36px;background:rgba(37,99,235,.96);color:#fff;font:700 24px -apple-system,'Malgun Gothic',Segoe UI,Roboto,sans-serif;padding:9px 18px;border-radius:9px;z-index:2147483646;box-shadow:0 6px 18px rgba(37,99,235,.24)}
      #__cur{position:fixed;left:960px;top:540px;width:30px;height:30px;z-index:2147483647;pointer-events:none;transition:left .7s cubic-bezier(.4,0,.2,1),top .7s cubic-bezier(.4,0,.2,1);background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M5 2l15 9-7 1 4 8-3 1-4-8-5 5z' fill='black' stroke='white' stroke-width='1.4'/></svg>") no-repeat;filter:drop-shadow(0 2px 3px rgba(0,0,0,.5))}
      body{transition:transform .8s cubic-bezier(.4,0,.2,1)}
    `;
    html.appendChild(style);
    window.__cap = (text) => { const node = document.getElementById("__cap"); node.textContent = text; node.classList.add("on"); };
    window.__capOff = () => document.getElementById("__cap").classList.remove("on");
    window.__capLabel = (text) => { document.getElementById("__lbl").textContent = text; };
    window.__cur = (x, y) => { const node = document.getElementById("__cur"); node.style.left = `${x - 4}px`; node.style.top = `${y - 2}px`; };
    window.__zoom = (scale, x, y) => { document.body.style.transformOrigin = `${x}px ${y}px`; document.body.style.transform = `scale(${scale})`; };
    window.__unzoom = () => { document.body.style.transform = "none"; };
  }, label);
}

function helpers(page) {
  const box = (selector, text) => page.evaluate(({ selector, text }) => {
    const nodes = [...document.querySelectorAll(selector)];
    const node = text ? nodes.find((item) => (item.textContent || "").includes(text)) : nodes[0];
    if (!node) return null;
    const rect = node.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  }, { selector, text });
  const move = async (point) => {
    if (!point) throw new Error("Demo target was not found");
    await page.evaluate(({ x, y }) => window.__cur(x, y), point);
    await sleep(820);
  };
  const moveClick = async (point) => {
    await move(point);
    await page.mouse.click(point.x, point.y);
    await sleep(380);
  };
  const subtitle = async (text, ms = 2600) => {
    await page.evaluate((value) => window.__cap(value), text);
    await sleep(ms);
  };
  const off = async () => {
    await page.evaluate(() => window.__capOff());
    await sleep(700);
  };
  const zoom = async (scale, x, y, ms = 2200) => {
    await page.evaluate(({ scale, x, y }) => window.__zoom(scale, x, y), { scale, x, y });
    await sleep(ms);
  };
  const unzoom = async () => {
    await page.evaluate(() => window.__unzoom());
    await sleep(900);
  };
  return { box, move, moveClick, subtitle, off, zoom, unzoom };
}

async function addCompany(page, h, name) {
  const input = await h.box("#companySearch");
  await h.moveClick(input);
  await page.type("#companySearch", name, { delay: 55 });
  await page.waitForFunction(() => document.querySelectorAll("#searchResults .result-item").length > 0, { timeout: 60000 });
  await h.moveClick(await h.box("#searchResults .result-item", name));
  await sleep(650);
}

async function prepareComparison(page, h) {
  await addCompany(page, h, "삼성전자");
  await addCompany(page, h, "SK하이닉스");
  await page.selectOption("#yearSelect", "2024");
  await h.moveClick(await h.box("#compareButton"));
  const started = Date.now();
  await page.waitForFunction(() => {
    const dashboard = document.querySelector("#dashboard");
    const coverage = document.querySelector("#dataCoverage")?.textContent || "";
    return dashboard && !dashboard.classList.contains("hidden") && coverage.includes("개 기업 수신");
  }, { timeout: 120000 });
  return Date.now() - started;
}

async function openTab(page, h, name, readySelector) {
  const tabKeys = { Overview: "overview", "Strategy Brief": "strategy" };
  const tabKey = tabKeys[name] || name.toLowerCase().replace(/\s+/g, "-");
  const tab = page.locator(`#tabs [data-tab="${tabKey}"]`).first();
  await tab.scrollIntoViewIfNeeded();
  const tabBox = await tab.boundingBox();
  await h.move({ x: tabBox.x + tabBox.width / 2, y: tabBox.y + tabBox.height / 2 });
  await tab.click();
  await sleep(380);
  await page.waitForFunction((key) => [...document.querySelectorAll("#tabs [data-tab]")].some((item) => item.classList.contains("active") && item.dataset.tab === key), tabKey, { timeout: 10000 });
  await page.waitForFunction((selector) => Boolean(document.querySelector(selector)), readySelector, { timeout: 120000 });
  await sleep(900);
}

async function captureScene(number, label, sequence) {
  const executablePath = resolveChrome();
  const browser = await chromium.launch({ ...(executablePath ? { executablePath } : {}), headless: true, args: ["--no-sandbox", "--disable-gpu"] });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();
  const before = new Set(fs.readdirSync(RAW));
  try {
    // Keep every scene in the same visual system as Strategy Brief. The app
    // intentionally switches to its dark strategy theme when that tab opens;
    // setting the persisted theme before navigation prevents a mid-reel jump.
    await context.addInitScript(() => {
      localStorage.setItem("dart-theme", "dark");
    });
    await page.goto(APP, { waitUntil: "networkidle", timeout: 60000 });
    await installOverlay(page, label);
    const h = helpers(page);
    const waitMs = await sequence(page, h);
    await h.off();
    await context.close();
    await browser.close();
    const created = fs.readdirSync(RAW).filter((file) => file.endsWith(".webm") && !before.has(file));
    if (!created.length) throw new Error(`Scene ${number} produced no WebM`);
    const source = path.join(RAW, created.sort().at(-1));
    const target = path.join(RAW, `scene-${String(number).padStart(2, "0")}.webm`);
    if (fs.existsSync(target)) fs.unlinkSync(target);
    fs.renameSync(source, target);
    console.log(JSON.stringify({ scene: number, waitMs, webm: target }));
  } catch (error) {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    throw error;
  }
}

const SCENES = {
  0: {
    label: "DART Workforce Intelligence",
    run: async (page, h) => {
      await h.subtitle("공시 데이터를 HR 전략의 언어로 바꿔 읽습니다.");
      await h.moveClick(await h.box("#companySearch"));
      await page.type("#companySearch", "삼성전자", { delay: 55 });
      await page.waitForFunction(() => document.querySelectorAll("#searchResults .result-item").length > 0, { timeout: 60000 });
      await h.subtitle("기업명·종목코드·DART 고유번호로 비교 대상을 선택합니다.", 1800);
      await h.moveClick(await h.box("#searchResults .result-item", "삼성전자"));
      await sleep(1100);
      await h.zoom(1.2, 680, 430, 1600);
      await h.unzoom();
      return 0;
    },
  },
  1: {
    label: "1. 기업 비교",
    run: async (page, h) => {
      await h.subtitle("같은 기준연도에서 기업의 이익·부채·현금 구조를 비교합니다.");
      const waitMs = await prepareComparison(page, h);
      await h.subtitle("OpenDART 실제값으로 비교 화면을 구성합니다.", 1800);
      await h.zoom(1.22, 1260, 510, 2200);
      await h.unzoom();
      return waitMs;
    },
  },
  2: {
    label: "2. 재무 시각화",
    run: async (page, h) => {
      await h.subtitle("핵심 KPI와 기업별 막대 그래프로 구조 차이를 한눈에 읽습니다.");
      const waitMs = await prepareComparison(page, h);
      await openTab(page, h, "Overview", ".visual-grid");
      await page.evaluate(() => document.querySelector(".visual-grid")?.scrollIntoView({ block: "center" }));
      await h.subtitle("자산 규모·영업이익률을 같은 DART 기준으로 비교합니다.", 1800);
      await h.zoom(1.3, 1220, 480, 2400);
      await h.unzoom();
      return waitMs;
    },
  },
  3: {
    label: "3. Strategy Brief",
    run: async (page, h) => {
      await h.subtitle("이익 체력에서 평균 급여·Pay Equity까지 한 흐름으로 봅니다.");
      const waitMs = await prepareComparison(page, h);
      await openTab(page, h, "Strategy Brief", ".strategy-profit-panel");
      await page.evaluate(() => document.querySelector(".strategy-profit-panel")?.scrollIntoView({ block: "center" }));
      await h.subtitle("실제 공시와 모델 추정을 시각적으로 분리합니다.", 1900);
      await h.zoom(1.28, 1270, 500, 2500);
      await h.unzoom();
      await page.evaluate(() => document.querySelector(".strategy-salary-panel")?.scrollIntoView({ block: "center" }));
      await h.subtitle("평균 급여 추이, 전망 구간, 성별 집계의 한계를 함께 확인합니다.", 2300);
      return waitMs;
    },
  },
  4: {
    label: "4. AI 분석 질문",
    run: async (page, h) => {
      await h.subtitle("DART 근거를 숨기지 않고 HR 전략 질문으로 확장합니다.");
      const waitMs = await prepareComparison(page, h);
      await openTab(page, h, "Strategy Brief", ".strategy-profit-panel");
      const question = "영업이익과 평균 급여 변화가 다른 기업을 구분하고 HR 전략 가설과 KPI를 제안해줘";
      await h.moveClick(await h.box("#analysisPrompt"));
      await page.type("#analysisPrompt", question, { delay: 32 });
      await h.moveClick(await h.box("#runAiButton"));
      await h.subtitle("AI가 분석할 질문을 입력하고 근거 기반 handoff를 생성합니다.", 1700);
      await page.waitForFunction(() => document.querySelector("#aiResult")?.dataset.state && document.querySelector("#aiResult").dataset.state !== "loading", { timeout: 120000 });
      await page.evaluate(() => document.querySelector(".prompt-box")?.scrollIntoView({ block: "center" }));
      await h.zoom(1.25, 360, 650, 2600);
      await h.unzoom();
      return waitMs;
    },
  },
};

async function main() {
  const requested = process.argv[2] || "all";
  const numbers = requested === "all" ? Object.keys(SCENES).map(Number) : [Number(requested)];
  for (const number of numbers) {
    const scene = SCENES[number];
    if (!scene) throw new Error(`Unknown scene: ${number}`);
    await captureScene(number, scene.label, scene.run);
  }
}

main().catch((error) => { console.error("DEMO_CAPTURE_ERROR", error.stack || error.message); process.exit(1); });
