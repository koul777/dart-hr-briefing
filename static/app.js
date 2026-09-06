const MAX_COMPANIES = 8;
const MAX_ANALYSIS_QUESTION_CHARS = 4000;
const EXPECTED_APP_ID = "kr.opendart.dart-hr-briefing";
const DEFAULT_HR_ANALYSIS_QUESTION = "선택 기업의 인력 생산성·보상 지속가능성·인력구조 차이를 비교하고, 판단 한계와 다음 내부 데이터를 설명해줘";

const state = {
  dartApiReady: false,
  appIdentity: null,
  openAiKey: "",
  openAiConnected: false,
  openAiProviderName: "",
  aiMessages: [],
  selected: [],
  results: [],
  previous: [],
  history: [],
  people: [],
  peopleHistory: [],
  executives: [],
  orchestration: null,
  strategyLoading: false,
  strategyLoadedFor: "",
  strategyRequestToken: 0,
  compareRequestToken: 0,
  aiRequestToken: 0,
  aiAbortController: null,
  peopleError: "",
  executivesError: "",
  historyError: "",
  peopleHistoryError: "",
  historyFromYear: "",
  historyToYear: "",
  year: "",
  reportCode: "11011",
  activeTab: "overview",
  selectedMetrics: ["assets", "liabilities", "equity", "cash", "revenue", "operating_profit", "operating_margin", "debt_ratio", "current_ratio"],
};

const $ = (selector) => document.querySelector(selector);
const safeStorageGet = (key) => {
  try { return window.localStorage.getItem(key); } catch (_) { return null; }
};
const safeStorageSet = (key, value) => {
  try { window.localStorage.setItem(key, value); return true; } catch (_) { return false; }
};
const escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const redactCredentialText = (value) => String(value ?? "")
  .replace(/\bsk-[A-Za-z0-9_-]{4,}/g, "[REDACTED]")
  .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]{4,}/gi, "Bearer [REDACTED]")
  .replace(/\b(crtfc_key|api[_-]?key|token)(\s*[:=]\s*)(["']?)[^\s,;&"']+/gi, "$1$2$3[REDACTED]");
const companyName = (item) => item?.company?.corp_name || "알 수 없음";
const numberValue = (value) => {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean" || (typeof value === "string" && !value.trim())) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};
const fmtAmount = (value) => { const n = numberValue(value); return n === null ? "—" : `${(n / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`; };
const fmtPercent = (value) => { const n = numberValue(value); return n === null ? "—" : `${n.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%`; };
const fmtRatio = (value) => { const n = numberValue(value); return n === null ? "—" : `${(n / 100).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}x`; };
const fmtCount = (value) => { const n = numberValue(value); return n === null ? "—" : `${n.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}명`; };
const fmtYears = (value) => { const n = numberValue(value); return n === null ? "—" : `${n.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}년`; };
const fmtSalary = (value) => { const n = numberValue(value); if (n === null) return "—"; if (n >= 100000000) return `${(n / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`; if (n >= 10000) return `${Math.round(n / 10000).toLocaleString("ko-KR")}만원`; return `${Math.round(n).toLocaleString("ko-KR")}원`; };
const fmtNumber = (value, kind) => kind === "amount" ? fmtAmount(value) : kind === "ratio" ? fmtRatio(value) : fmtPercent(value);
const reportLabel = (code) => ({ "11011": "사업보고서", "11012": "반기보고서", "11013": "1분기보고서", "11014": "3분기보고서" }[code] || code);
const metricDefs = {
  assets: { label: "자산총계", group: "재무 규모", kind: "amount" },
  liabilities: { label: "부채총계", group: "재무 규모", kind: "amount" },
  equity: { label: "자본총계", group: "재무 규모", kind: "amount" },
  cash: { label: "현금·현금성자산", group: "재무 규모", kind: "amount" },
  revenue: { label: "매출액", group: "손익", kind: "amount" },
  operating_profit: { label: "영업이익", group: "손익", kind: "amount" },
  operating_margin: { label: "영업이익률", group: "수익성", kind: "percent" },
  net_margin: { label: "순이익률", group: "수익성", kind: "percent" },
  debt_ratio: { label: "부채비율", group: "안정성", kind: "percent" },
  current_ratio: { label: "유동비율", group: "안정성", kind: "ratio" },
};
const allMetricKeys = Object.keys(metricDefs);
const evidenceMetricLabels = {
  assets: "자산총계",
  liabilities: "부채총계",
  equity: "자본총계",
  cash: "현금·현금성자산",
  revenue: "매출",
  operating_profit: "영업이익",
  operating_margin: "영업이익률",
  net_margin: "순이익률",
  debt_ratio: "부채비율",
  current_ratio: "유동비율",
  employees_total: "총 직원",
  average_salary: "평균 급여",
  annual_salary_total: "급여 총액",
  revenue_per_employee: "인당 매출",
  operating_profit_per_employee: "인당 영업이익",
  salary_to_revenue: "급여/매출",
  contract_share: "계약직 비중",
  average_tenure_years: "평균 근속",
  term_expiring_within_12_months: "12개월 내 임기 만료",
};
const providerViolationLabels = {
  sensitive_key: "API 키 등 민감정보 포함",
  sensitive_literal: "개인정보 또는 민감정보 포함",
  unsupported_causal_assertion: "공시 근거만으로 확인할 수 없는 인과 해석",
  fabricated_person_reference: "근거 없는 개인 언급",
  fabricated_person_judgment: "근거 없는 개인 평가",
  malformed_evidence_citation: "잘못된 근거 ID 형식",
  unknown_evidence_citation: "확인되지 않은 근거 ID 인용",
  contradictory_numeric_citation: "수치와 인용 근거 불일치",
  uncited_numeric_claim: "근거 ID 없는 수치 주장",
  invalid_provider_output: "응답 형식 검증 실패",
  provider_guard_incomplete: "안전 검증 절차 미완료",
};

function setMessage(text = "") { $("#message").textContent = text; }
function aiRequestHeaders(headers = {}) { return state.openAiKey ? { ...headers, "X-OpenAI-API-Key": state.openAiKey } : headers; }
function renderApiConnection(message = "", isError = false) {
  const connectionState = $("#apiConnectState");
  const help = $("#apiConnectHelp");
  const connected = state.openAiConnected && Boolean(state.openAiKey);
  connectionState.dataset.state = connected ? "ready" : "idle";
  connectionState.innerHTML = connected ? "<i></i> 연결됨" : "<i></i> API Key";
  help.classList.toggle("error", isError);
  help.textContent = message || (connected
    ? `${state.openAiProviderName || "OpenAI API"} · 이 대화에서만 사용`
    : "키는 저장하지 않고 이 대화에서만 사용합니다.");
  const status = $("#apiStatus");
  status.classList.remove("ready", "error");
  status.classList.add(state.dartApiReady && connected ? "ready" : "error");
  status.innerHTML = `<i></i> ${state.dartApiReady ? "DART" : "DART 키 필요"} · ${connected ? "AI 연결" : "AI 키 입력"}`;
  const appLabel = state.appIdentity
    ? `${state.appIdentity.name || "DART HR Briefing"} ${state.appIdentity.version || ""} · ${state.appIdentity.build_id || "빌드 미상"}`
    : "서버 식별 확인 중";
  status.title = `${connected ? state.openAiProviderName : "AI HR 브리핑에 OpenAI API Key를 입력해 주세요."} · ${appLabel}`;
}
function renderAiConversation(pendingQuestion = "") {
  const resultBox = $("#aiResult");
  const messages = [...state.aiMessages];
  if (pendingQuestion) messages.push({ role: "user", content: pendingQuestion }, { role: "assistant", content: "DART 근거를 확인하고 있습니다…", pending: true });
  if (!messages.length) {
    resultBox.removeAttribute("data-state");
    resultBox.innerHTML = "";
    updateWorkshopProgress();
    return;
  }
  resultBox.dataset.state = pendingQuestion ? "loading" : "ready";
  resultBox.innerHTML = messages.map((message) => {
    const content = message.role === "assistant" && Array.isArray(message.evidence)
      ? renderEvidenceText(message.content, message.evidence)
      : escapeHtml(message.content);
    return `<div class="ai-chat-message ${message.role}${message.pending ? " pending" : ""}"><strong>${message.role === "user" ? "나" : "AI"}</strong><span>${content}</span></div>`;
  }).join("");
  resultBox.scrollTop = resultBox.scrollHeight;
  updateWorkshopProgress();
}
function cancelAiRequest() {
  state.aiRequestToken += 1;
  state.aiAbortController?.abort();
  state.aiAbortController = null;
  const button = $("#runAiButton");
  if (button) {
    button.disabled = false;
    button.textContent = "AI에게 질문하기 ↗";
  }
  renderAiConversation();
  renderApiConnection();
}
function resetAiConversationForContextChange() {
  cancelAiRequest();
  state.aiMessages = [];
  renderAiConversation();
}
function clearAiConversation() {
  resetAiConversationForContextChange();
  $("#analysisPrompt").value = "";
}
function dataSelectionKey(companies = state.selected, year = state.year, reportCode = state.reportCode) {
  return `${companies.map((item) => item.corp_code).join(",")}:${year}:${reportCode}`;
}
function aiContextKey() {
  return `${dataSelectionKey()}:${state.selectedMetrics.join(",")}:${state.activeTab}`;
}
function invalidateSelectionRequests() {
  state.compareRequestToken += 1;
  state.strategyRequestToken += 1;
  resetAiConversationForContextChange();
  state.strategyLoading = false;
  state.strategyLoadedFor = "";
  if (state.results.length) setMessage("기업 선택이 바뀌었습니다. 인력·보상 비교를 다시 실행해 주세요.");
}
function invalidatePeriodRequests(message) {
  state.compareRequestToken += 1;
  state.strategyRequestToken += 1;
  resetAiConversationForContextChange();
  state.strategyLoading = false;
  state.strategyLoadedFor = "";
  if (state.results.length) setMessage(message);
}
function conversationQuestion(question) {
  const latestQuestion = redactCredentialText(question).slice(0, MAX_ANALYSIS_QUESTION_CHARS);
  const history = state.aiMessages.slice(-6).map((message) => `${message.role === "user" ? "사용자" : "AI"}: ${redactCredentialText(message.content)}`).join("\n");
  if (!history) return latestQuestion;
  const historyHeader = "[이전 대화]\n";
  const questionHeader = "\n\n[새 질문]\n";
  const historyBudget = MAX_ANALYSIS_QUESTION_CHARS
    - historyHeader.length
    - questionHeader.length
    - latestQuestion.length;
  if (historyBudget <= 1) return latestQuestion;
  const boundedHistory = history.length > historyBudget
    ? `…${history.slice(-(historyBudget - 1))}`
    : history;
  return `${historyHeader}${boundedHistory}${questionHeader}${latestQuestion}`;
}
function officialEvidenceUrl(value) {
  try {
    const url = new URL(String(value || ""));
    const safeOrigin = url.protocol === "https:"
      && ["dart.fss.or.kr", "opendart.fss.or.kr"].includes(url.hostname)
      && !url.username
      && !url.password
      && (!url.port || url.port === "443")
      && !url.hash;
    if (!safeOrigin) return "";
    const queryKeys = [...url.searchParams.keys()];
    if (queryKeys.some((key) => ["authorization", "crtfc_key", "api_key", "apikey", "token"].includes(key.toLowerCase()))) return "";
    if (url.hostname === "dart.fss.or.kr") {
      const receipts = url.searchParams.getAll("rcpNo");
      return url.pathname === "/dsaf001/main.do"
        && queryKeys.length === 1
        && receipts.length === 1
        && /^\d{14}$/.test(receipts[0])
        ? `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${receipts[0]}`
        : "";
    }
    const allowedGuideKeys = new Set(["apiGrpCd", "apiId"]);
    return url.pathname === "/guide/detail.do"
      && queryKeys.length > 0
      && queryKeys.every((key) => allowedGuideKeys.has(key))
      && [...url.searchParams.values()].every((item) => /^[A-Za-z0-9_-]{1,32}$/.test(item))
      ? url.href
      : "";
  } catch {
    return "";
  }
}
function evidenceSourceUrl(item) {
  const direct = officialEvidenceUrl(item?.source_urls?.[0]);
  if (direct) return direct;
  const receipt = String(item?.receipt_numbers?.[0] || "");
  return /^\d{14}$/.test(receipt)
    ? `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${receipt}`
    : "";
}
function renderEvidenceText(value, ledger = []) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const evidence = new Map(ledger.map((item) => [String(item.evidence_id || "").toLowerCase(), item]));
  return String(text || "").split(/(\[?EV-[0-9a-f]{12}\]?)/ig).map((part) => {
    const match = part.match(/^\[?(EV-[0-9a-f]{12})\]?$/i);
    if (!match) return escapeHtml(part);
    const evidenceId = match[1];
    const item = evidence.get(evidenceId.toLowerCase());
    const url = evidenceSourceUrl(item);
    return item && url
      ? `<a class="evidence-citation" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(item.metric_id || "DART 근거")}">[${escapeHtml(evidenceId)}]↗</a>`
      : escapeHtml(part);
  }).join("");
}
function formatValidatedEvidenceValue(item) {
  const value = numberValue(item?.value);
  if (value === null) return "값 확인 필요";
  if (["assets", "liabilities", "equity", "cash", "revenue", "operating_profit", "annual_salary_total", "revenue_per_employee", "operating_profit_per_employee"].includes(item.metric_id)) return fmtAmount(value);
  if (item.metric_id === "average_salary") return fmtSalary(value);
  if (["operating_margin", "net_margin", "debt_ratio", "salary_to_revenue", "contract_share"].includes(item.metric_id)) return fmtPercent(value);
  if (item.metric_id === "current_ratio") return fmtRatio(value);
  if (["employees_total", "term_expiring_within_12_months"].includes(item.metric_id)) return fmtCount(value);
  if (item.metric_id === "average_tenure_years") return fmtYears(value);
  const unit = String(item.unit || "").trim();
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
}
function buildValidatedFallback(payload) {
  const validation = payload.provider_validation || payload.provider_output_validation || {};
  const violationCodes = [...new Set(validation.violation_codes || [])];
  const violationSummary = violationCodes.length
    ? violationCodes.map((code) => providerViolationLabels[code] || "안전 검증 기준 미충족").join(" · ")
    : "안전 검증 기준 미충족";
  const requestedMetrics = new Set(payload.request?.metric_ids || state.selectedMetrics || []);
  const ledger = (payload.evidence?.ledger || []).filter((item) => (
    item
    && /^EV-[0-9a-f]{12}$/i.test(String(item.evidence_id || ""))
    && numberValue(item.value) !== null
    && ["complete", "partial"].includes(item.quality_status)
    && evidenceSourceUrl(item)
  ));
  const completeEvidence = ledger.filter((item) => item.source_coverage_complete === true);
  const safeEvidence = completeEvidence.length ? completeEvidence : ledger;
  const requestedEvidence = safeEvidence.filter((item) => requestedMetrics.has(item.metric_id));
  const selectedEvidence = (requestedEvidence.length ? requestedEvidence : safeEvidence).slice(0, 8);
  const evidenceLines = selectedEvidence.length
    ? selectedEvidence.map((item) => `- ${item.company?.corp_name || "기업"} · ${evidenceMetricLabels[item.metric_id] || item.metric_id}: ${formatValidatedEvidenceValue(item)} [${item.evidence_id}]`)
    : ["- 현재 질문에 안전하게 표시할 수 있는 공시 수치 근거가 없습니다."];
  return {
    answer: [
      "AI 초안은 안전 검증에서 차단되어, 서버가 검증한 OpenDART 근거만 표시합니다.",
      `차단 사유: ${violationSummary}`,
      "",
      ...evidenceLines,
      "",
      "해석 한계: 위 값은 기업 공시 수준의 비교 근거이며, 인과관계나 개인의 성과·채용·평가 판단을 뜻하지 않습니다.",
      "수치가 필요한 후속 질문에는 표시된 근거 ID를 함께 사용해 주세요.",
    ].join("\n"),
    evidence: selectedEvidence,
  };
}
function renderProviderEvidenceText(value) {
  return renderEvidenceText(value, state.orchestration?.evidence?.ledger || []);
}
function renderEvidenceBadge(evidenceId, ledger = []) {
  const item = ledger.find((row) => String(row.evidence_id || "").toLowerCase() === String(evidenceId || "").toLowerCase());
  const url = evidenceSourceUrl(item);
  return item && url
    ? `<a class="evidence-citation evidence-badge" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(`${item.company?.corp_name || "기업"} · ${item.metric_id || "DART 근거"} · ${evidenceId}`)}">근거↗</a>`
    : `<span class="evidence-badge missing">근거 없음</span>`;
}
function financials(item) { return item?.financials || {}; }
function valueFor(item, key) { return numberValue(financials(item)[key]); }
function people(item) { return item?.people || {}; }
function peopleValue(item, key) { return numberValue(people(item)[key]); }
function averageSalaryBasisLabel(basis) {
  if (basis === "disclosed_average_headcount_weighted") return "공시 평균·인원 가중";
  if (basis === "annual_salary_total_per_employee_fallback") return "급여총액÷직원 수 대체";
  return "계산근거 확인 필요";
}

function averageSalaryAggregateLabel(items) {
  const bases = [...new Set(items
    .filter((item) => peopleValue(item, "average_salary") !== null && peopleValue(item, "employees_total") > 0)
    .map((item) => item.people?.average_salary_basis)
    .filter(Boolean))];
  if (bases.length > 1) return "직원수 가중 · 계산 기준 혼합";
  return `직원수 가중 · ${averageSalaryBasisLabel(bases[0])}`;
}
function metricValue(item, key) { return fmtNumber(valueFor(item, key), metricDefs[key].kind); }
function resultFor(code, source = state.results) { return source.find((item) => item.company?.corp_code === code); }
function chunks(items, size) { const output = []; for (let i = 0; i < items.length; i += size) output.push(items.slice(i, i + size)); return output; }

function setupYears() {
  const select = $("#yearSelect");
  const latest = new Date().getFullYear() - 1;
  for (let year = latest; year >= 2016; year -= 1) {
    const option = document.createElement("option"); option.value = String(year); option.textContent = `${year}년`; select.appendChild(option);
  }
  state.year = select.value;
}

function comparisonMatchesSelection() {
  if (!state.results.length || !state.selected.length) return false;
  if (state.year !== $("#yearSelect").value || state.reportCode !== $("#reportSelect").value) return false;
  const resultCodes = new Set(state.results.map((item) => item?.company?.corp_code).filter(Boolean));
  return state.selected.every((company) => resultCodes.has(company.corp_code));
}

function updateWorkshopProgress() {
  const steps = [...document.querySelectorAll("[data-workshop-step]")];
  if (!steps.length) return;
  const hasAnswer = state.aiMessages.some((message) => (
    message.role === "assistant" && !String(message.content || "").startsWith("오류:")
  ));
  const hasEvidence = hasAnswer && (
    state.aiMessages.some((message) => (
      message.role === "assistant" && Array.isArray(message.evidence) && message.evidence.length > 0
    )) || Boolean(state.orchestration?.evidence?.ledger?.length)
  );
  const completed = [state.selected.length >= 2, comparisonMatchesSelection(), hasAnswer, hasEvidence];
  const nextIndex = completed.findIndex((value) => !value);
  steps.forEach((step, index) => {
    step.classList.toggle("complete", completed[index]);
    const current = index === (nextIndex < 0 ? completed.length - 1 : nextIndex);
    step.classList.toggle("current", current);
    if (current) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
  const done = completed.filter(Boolean).length;
  const summary = $("#workshopProgressSummary");
  summary.textContent = done === completed.length ? "실습 흐름 완료" : `${done + 1}단계 진행 중 · ${done}/4 완료`;
  summary.dataset.complete = String(done === completed.length);
}

function renderSelected() {
  $("#selectionCount").textContent = `${state.selected.length} / ${MAX_COMPANIES}`;
  if (!state.selected.length) {
    $("#selectedChips").innerHTML = '<div class="empty-rail"><span class="empty-rail-icon">＋</span><p>기업을 검색해<br>비교 목록에 추가하세요.</p><small>최대 8개 · DART 공시 기준</small></div>';
    updateWorkshopProgress();
    return;
  }
  $("#selectedChips").innerHTML = state.selected.map((company, index) => `<div class="company-row"><span class="company-avatar">${escapeHtml((company.corp_name || "?").slice(0, 1))}</span><span class="company-info"><strong title="${escapeHtml(company.corp_name)}">${escapeHtml(company.corp_name)}</strong><small>${escapeHtml(company.stock_code || company.corp_code)}</small></span><button class="remove-company" data-remove="${index}" type="button" aria-label="${escapeHtml(company.corp_name)} 제거">×</button></div>`).join("");
  $("#selectedChips").querySelectorAll("[data-remove]").forEach((button) => button.addEventListener("click", () => { state.selected.splice(Number(button.dataset.remove), 1); invalidateSelectionRequests(); renderSelected(); }));
  updateWorkshopProgress();
}

let searchCompanies = [];
let activeSearchIndex = -1;

function closeSearchResults() {
  searchRequestToken += 1;
  searchCompanies = [];
  activeSearchIndex = -1;
  $("#searchResults").innerHTML = "";
  $("#companySearch").setAttribute("aria-expanded", "false");
  $("#companySearch").removeAttribute("aria-activedescendant");
}

function setActiveSearchOption(index) {
  const options = [...$("#searchResults").querySelectorAll('[role="option"]')];
  if (!options.length) return;
  activeSearchIndex = (index + options.length) % options.length;
  options.forEach((option, optionIndex) => {
    const active = optionIndex === activeSearchIndex;
    option.setAttribute("aria-selected", String(active));
    option.classList.toggle("active", active);
  });
  $("#companySearch").setAttribute("aria-activedescendant", options[activeSearchIndex].id);
  options[activeSearchIndex].scrollIntoView({ block: "nearest" });
}

function addCompany(company) {
  if (!company || state.selected.some((item) => item.corp_code === company.corp_code)) { $("#companySearch").value = ""; closeSearchResults(); return; }
  if (state.selected.length >= MAX_COMPANIES) { setMessage(`비교 기업은 최대 ${MAX_COMPANIES}개까지 선택할 수 있습니다.`); return; }
  state.selected.push(company); $("#companySearch").value = ""; closeSearchResults(); invalidateSelectionRequests(); renderSelected();
}

function renderSearchResults(companies) {
  const container = $("#searchResults");
  searchCompanies = companies;
  activeSearchIndex = -1;
  $("#companySearch").setAttribute("aria-expanded", "true");
  $("#companySearch").removeAttribute("aria-activedescendant");
  if (!companies.length) { container.innerHTML = '<div class="result-empty" role="status">검색 결과가 없습니다.</div>'; return; }
  container.innerHTML = companies.map((company, index) => `<button class="result-item" id="company-option-${index}" type="button" role="option" aria-selected="false" tabindex="-1" data-result="${index}"><strong>${escapeHtml(company.corp_name)}</strong><small>${escapeHtml(company.stock_code || company.corp_code)}</small></button>`).join("");
  container.querySelectorAll("[data-result]").forEach((button) => button.addEventListener("click", () => addCompany(companies[Number(button.dataset.result)])));
}

let searchTimer;
let searchRequestToken = 0;
$("#companySearch").addEventListener("input", (event) => {
  clearTimeout(searchTimer); const query = event.target.value.trim(); const requestToken = ++searchRequestToken;
  if (!query) { closeSearchResults(); return; }
  searchTimer = setTimeout(async () => {
    try { const response = await fetch(`/api/companies?q=${encodeURIComponent(query)}`); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "기업 검색에 실패했습니다."); if (requestToken === searchRequestToken && $("#companySearch").value.trim() === query) renderSearchResults(payload.companies || []); }
    catch (error) { setMessage(error.message); }
  }, 250);
});
$("#companySearch").addEventListener("keydown", (event) => {
  if (event.key === "Escape") { closeSearchResults(); return; }
  if (!["ArrowDown", "ArrowUp", "Enter"].includes(event.key) || !searchCompanies.length) return;
  if (event.key === "Enter") {
    if (activeSearchIndex < 0) return;
    event.preventDefault();
    addCompany(searchCompanies[activeSearchIndex]);
    return;
  }
  event.preventDefault();
  setActiveSearchOption(activeSearchIndex + (event.key === "ArrowDown" ? 1 : -1));
});
document.addEventListener("click", (event) => { if (!event.target.closest(".search-wrap") && !event.target.closest("#searchResults")) closeSearchResults(); });

async function requestBatch(companies, year, reportCode) {
  const query = new URLSearchParams({ corp_codes: companies.map((item) => item.corp_code).join(","), year, report_code: reportCode });
  try {
    const response = await fetch(`/api/financials?${query}`); const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "재무 데이터를 불러오지 못했습니다.");
    return payload.results || [];
  } catch (error) {
    return companies.map((company) => ({ company, error: error.message }));
  }
}

async function requestAll(companies, year, reportCode) {
  const responses = await Promise.all(chunks(companies, 5).map((batch) => requestBatch(batch, year, reportCode)));
  const byCode = new Map(responses.flat().map((item) => [item.company?.corp_code, item]));
  return companies.map((company) => byCode.get(company.corp_code) || ({ company, error: "응답 데이터가 없습니다." }));
}

async function requestHistory(companies, fromYear, toYear, reportCode) {
  const query = new URLSearchParams({
    corp_codes: companies.map((item) => item.corp_code).join(","),
    from_year: String(fromYear),
    to_year: String(toYear),
    report_code: reportCode,
  });
  const response = await fetch(`/api/financials/history?${query}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "연도별 재무 데이터를 불러오지 못했습니다.");
  return payload.results || [];
}

async function requestPeople(companies, year, reportCode) {
  const query = new URLSearchParams({
    corp_codes: companies.map((item) => item.corp_code).join(","),
    year: String(year),
    report_code: reportCode,
  });
  const response = await fetch(`/api/people?${query}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "People 데이터를 불러오지 못했습니다.");
  return payload.results || [];
}

function executivesFromPeople(results) {
  return (results || []).map((item) => ({
    company: item.company,
    year: item.year,
    report_code: item.report_code,
    executive_metrics: item.executive_metrics || {},
    quality: item.component_quality?.executives || {},
    source_urls: item.source_urls || [],
    errors: (item.errors || []).filter((error) => error?.source === "executive_status"),
  }));
}

async function requestPeopleHistory(companies, fromYear, toYear, reportCode) {
  const query = new URLSearchParams({
    corp_codes: companies.map((item) => item.corp_code).join(","),
    from_year: String(fromYear),
    to_year: String(toYear),
    report_code: reportCode,
  });
  const response = await fetch(`/api/people/history?${query}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "People 추이 데이터를 불러오지 못했습니다.");
  return payload.results || [];
}

async function requestWorkforceOrchestration(companies, year, reportCode) {
  const query = new URLSearchParams({
    corp_codes: companies.map((item) => item.corp_code).join(","),
    year: String(year),
    report_code: reportCode,
  });
  const response = await fetch(`/api/workforce/orchestration?${query}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Workforce 분석 흐름을 실행하지 못했습니다.");
  return payload;
}

function renderMetricPills() {
  $("#metricPills").innerHTML = allMetricKeys.map((key) => `<button type="button" class="metric-pill ${state.selectedMetrics.includes(key) ? "active" : ""}" data-metric="${key}">${metricDefs[key].label}</button>`).join("");
  $("#metricPills").querySelectorAll("[data-metric]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.metric; const index = state.selectedMetrics.indexOf(key);
    if (index >= 0) { if (state.selectedMetrics.length === 1) return; state.selectedMetrics.splice(index, 1); } else state.selectedMetrics.push(key);
    state.strategyLoadedFor = ""; resetAiConversationForContextChange();
    renderMetricPills(); renderTab();
  }));
}

function availableResults() {
  return state.results.filter((item) => (
    !item.error
    && Object.values(financials(item)).some((value) => numberValue(value) !== null)
  ));
}
function renderEmpty(title, detail) { return `<div class="empty-state"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div></div>`; }

function renderKpis() {
  const valid = availableResults();
  if (!valid.length) return renderEmpty("표시할 재무 데이터가 없습니다.", "선택한 기업에 해당 연도·보고서의 공시 데이터가 없거나 OpenDART 응답을 확인할 수 없습니다.");
  const best = (key, direction = "max") => valid
    .filter((item) => valueFor(item, key) !== null)
    .sort((a, b) => (valueFor(b, key) - valueFor(a, key)) * (direction === "max" ? 1 : -1))[0];
  const highestMargin = best("operating_margin"); const lowestDebt = best("debt_ratio", "min"); const highestCash = best("cash");
  const cards = [["비교 기업", `${valid.length}개`, `${state.results.length - valid.length ? `${state.results.length - valid.length}개 데이터 없음` : "모든 선택 기업 수신"}`], ["영업이익률 최고", highestMargin ? metricValue(highestMargin, "operating_margin") : "—", highestMargin ? companyName(highestMargin) : "데이터 없음"], ["부채비율 최저", lowestDebt ? metricValue(lowestDebt, "debt_ratio") : "—", lowestDebt ? companyName(lowestDebt) : "데이터 없음"], ["현금 규모 최고", highestCash ? metricValue(highestCash, "cash") : "—", highestCash ? companyName(highestCash) : "데이터 없음"]];
  return `<div class="kpi-grid">${cards.map(([label, value, sub]) => `<div class="kpi"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(sub)}</small></div>`).join("")}</div>`;
}

function renderBars(key, title, unit) {
  const valid = state.results; const values = valid.map((item) => valueFor(item, key)).filter((value) => value !== null); const max = Math.max(...values.map((value) => Math.abs(value)), 1);
  return `<article class="panel"><div class="panel-title"><div><span class="kicker">${metricDefs[key].group.toUpperCase()}</span><h3>${title}</h3></div><span>${unit}</span></div><div class="bars">${valid.map((item) => { const value = valueFor(item, key); const height = value === null ? 3 : Math.max(4, Math.round(Math.abs(value) / max * 132)); return `<div class="bar-column"><span class="value">${escapeHtml(metricValue(item, key))}</span><div class="bar" style="height:${height}px"></div><span class="name" title="${escapeHtml(companyName(item))}">${escapeHtml(companyName(item))}</span></div>`; }).join("")}</div></article>`;
}

function renderTable(keys = state.selectedMetrics) {
  const groups = [...new Set(keys.map((key) => metricDefs[key].group))];
  if (!state.results.length) return renderEmpty("비교 테이블이 비어 있습니다.", "먼저 기업을 선택하고 재무구조 비교를 실행하세요.");
  const head = `<thead><tr><th>지표</th>${state.results.map((item) => `<th class="company-head">${escapeHtml(companyName(item))}<br><small>${escapeHtml(item.company?.stock_code || "비상장")}</small></th>`).join("")}</tr></thead>`;
  const body = groups.map((group) => `<tr class="section-row"><td colspan="${state.results.length + 1}">${group}</td></tr>${keys.filter((key) => metricDefs[key].group === group).map((key) => `<tr><td>${metricDefs[key].label}</td>${state.results.map((item) => { const value = valueFor(item, key); return `<td class="number ${value === null ? "na" : ""}">${escapeHtml(value === null ? "데이터 없음" : metricValue(item, key))}</td>`; }).join("")}</tr>`).join("")}`).join("");
  return `<div class="table-panel"><div class="panel-title"><div><span class="kicker">SIDE BY SIDE</span><h3>핵심 재무지표</h3></div><span>단위: 억 원 · 비율 · x</span></div><div class="table-scroll"><table class="data-table">${head}<tbody>${body}</tbody></table></div></div>`;
}

function renderChangeSummary() {
  const candidates = availableResults().map((item) => {
    const previous = resultFor(item.company?.corp_code, state.previous);
    const changes = ["revenue", "operating_profit", "assets"].map((metricId) => {
      const currentValue = valueFor(item, metricId);
      const previousValue = valueFor(previous, metricId);
      const delta = currentValue !== null && previousValue !== null && previousValue !== 0
        ? (currentValue - previousValue) / Math.abs(previousValue) * 100
        : null;
      return { metricId, currentValue, previousValue, delta };
    }).filter((change) => change.delta !== null);
    const largest = changes.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))[0];
    return largest ? { item, ...largest } : { item, delta: null };
  });
  const available = candidates.filter((item) => item.delta !== null).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  if (!available.length) return `<section class="change-summary"><div class="change-summary-head"><div><span class="kicker">WHAT CHANGED</span><h3>전년 대비 사업 여력 변화</h3></div><span>${escapeHtml(String(Number(state.year) - 1))} → ${escapeHtml(state.year)}</span></div><div class="change-summary-empty">양쪽 연도에 같은 지표가 공시된 기업이 없어 변화를 계산하지 않았습니다.</div></section>`;
  const cards = available.slice(0, 4).map(({ item, metricId, currentValue, previousValue, delta }) => `<article class="change-card"><div><span>${escapeHtml(companyName(item))}</span><strong>${escapeHtml(metricDefs[metricId]?.label || metricId)}</strong></div><b class="${delta >= 0 ? "delta-up" : "delta-down"}">${delta >= 0 ? "+" : ""}${escapeHtml(delta.toFixed(1))}%</b><small>${escapeHtml(fmtNumber(previousValue, metricDefs[metricId]?.kind))} → ${escapeHtml(fmtNumber(currentValue, metricDefs[metricId]?.kind))}</small></article>`).join("");
  return `<section class="change-summary"><div class="change-summary-head"><div><span class="kicker">WHAT CHANGED</span><h3>전년 대비 가장 큰 사업 여력 변화</h3></div><span>${escapeHtml(String(Number(state.year) - 1))} → ${escapeHtml(state.year)} · 기업별 절대 변화율 최대 지표</span></div><div class="change-summary-grid">${cards}</div><p>재무 공시의 변화만 요약합니다. 인력·보상 변화와의 원인은 단정하지 않으며, 여러 연도 흐름은 Trend와 Strategy Brief에서 확인하세요.</p></section>`;
}

function renderOverview() {
  if (!state.results.length) return renderEmpty("비교할 기업이 없습니다.", "왼쪽에서 기업을 선택한 뒤 재무구조 비교를 눌러주세요.");
  return `<div class="tab-panel">${renderChangeSummary()}${renderKpis()}<div class="visual-grid">${renderBars("assets", "자산 규모", "억 원")}${renderBars("operating_margin", "영업이익률", "%")}</div>${renderTable()}</div>`;
}

function renderCompare() { return `<div class="tab-panel">${renderTable()}<div class="table-panel" style="margin-top:15px">${renderBars("debt_ratio", "부채비율", "%")}</div></div>`; }

function renderTrend() {
  const valid = state.results.filter((item) => valueFor(item, "revenue") !== null || valueFor(resultFor(item.company?.corp_code, state.previous), "revenue") !== null); if (!valid.length) return renderEmpty("전년 데이터가 없습니다.", "현재 연도와 전년도의 OpenDART 응답을 함께 받을 수 있어야 추세를 그릴 수 있습니다.");
  const max = Math.max(...valid.flatMap((item) => [valueFor(item, "revenue"), valueFor(resultFor(item.company.corp_code, state.previous), "revenue")]).filter((value) => value !== null).map(Math.abs), 1); const width = 620; const height = 235; const step = valid.length > 1 ? width / (valid.length - 1) : width / 2;
  const line = (key, source, color, offset = 0) => { let penDown = false; return valid.map((item, index) => { const value = valueFor(resultFor(item.company.corp_code, source), key); if (value === null) { penDown = false; return ""; } const x = valid.length === 1 ? width / 2 : index * step; const y = height - (Math.abs(value) / max * 180) - 12 + offset; const command = penDown ? "L" : "M"; penDown = true; return `${command} ${x} ${y}`; }).join(" "); };
  const points = valid.map((item, index) => { const current = valueFor(item, "revenue"); const previous = valueFor(resultFor(item.company.corp_code, state.previous), "revenue"); const x = valid.length === 1 ? width / 2 : index * step; const currentCircle = current === null ? "" : `<circle cx="${x}" cy="${height - (Math.abs(current) / max * 180) - 12}" r="4" fill="var(--teal)"/>`; const previousCircle = previous === null ? "" : `<circle cx="${x}" cy="${height - (Math.abs(previous) / max * 180) - 7}" r="3" fill="var(--coral)"/>`; return `<g>${currentCircle}${previousCircle}<text x="${x}" y="${height + 15}" text-anchor="middle" fill="var(--muted)" font-size="10">${escapeHtml(companyName(item).slice(0, 7))}</text></g>`; }).join("");
  const cards = valid.slice(0, 3).map((item) => { const current = valueFor(item, "revenue"); const previous = valueFor(resultFor(item.company.corp_code, state.previous), "revenue"); const delta = current !== null && previous ? (current - previous) / Math.abs(previous) * 100 : null; return `<div class="trend-card"><span>${escapeHtml(companyName(item))}</span><strong class="${delta !== null && delta >= 0 ? "delta-up" : "delta-down"}">${delta === null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}%`}</strong><small>매출 전년 대비</small></div>`; }).join("");
  return `<div class="tab-panel trend-layout"><article class="panel chart-panel"><div class="panel-title"><div><span class="kicker">YEAR OVER YEAR</span><h3>매출 규모 추세</h3></div><span>${state.year} vs ${Number(state.year) - 1}</span></div><svg class="trend-svg" viewBox="0 0 ${width} ${height + 30}" role="img" aria-label="매출 전년 대비 추세"><path d="${line("revenue", state.results, "teal")}" fill="none" stroke="var(--teal)" stroke-width="2.5"/><path d="${line("revenue", state.previous, "coral", 5)}" fill="none" stroke="var(--coral)" stroke-width="2" stroke-dasharray="5 5"/>${points}</svg><div class="trend-legend"><span><i></i>${state.year} 매출</span><span><i></i>${Number(state.year) - 1} 매출</span></div></article><div class="trend-side">${cards}</div></div>`;
}

function historyValue(item, year, key) {
  const entry = (item?.years || []).find((row) => String(row.year) === String(year));
  return numberValue(entry?.financials?.[key]);
}

function trendMetricKey() {
  const preferred = ["revenue", "assets", "operating_profit", "operating_margin", "debt_ratio"];
  return preferred.find((key) => state.selectedMetrics.includes(key)) || state.selectedMetrics[0] || "revenue";
}

function renderTrendByYear() {
  if (state.historyError) return renderEmpty("재무 추이 요청에 실패했습니다.", state.historyError);
  const metricKey = trendMetricKey();
  const historyRows = (state.history || []).filter((item) => Array.isArray(item.years));
  const years = [...new Set(historyRows.flatMap((item) => item.years.map((row) => Number(row.year)).filter(Number.isFinite)))].sort((a, b) => a - b);
  const valid = historyRows.filter((item) => years.some((year) => historyValue(item, year, metricKey) !== null));
  if (!valid.length || !years.length) return renderEmpty("연도별 데이터가 없습니다.", "선택한 기업의 여러 연도 OpenDART 공시를 확인할 수 없습니다.");

  const values = valid.flatMap((item) => years.map((year) => historyValue(item, year, metricKey))).filter((value) => value !== null);
  const minValue = Math.min(0, ...values);
  const maxValue = Math.max(1, ...values);
  const chartWidth = 760;
  const chartHeight = 300;
  const pad = { left: 48, right: 20, top: 20, bottom: 42 };
  const innerWidth = chartWidth - pad.left - pad.right;
  const innerHeight = chartHeight - pad.top - pad.bottom;
  const xFor = (index) => pad.left + (years.length === 1 ? innerWidth / 2 : index * innerWidth / (years.length - 1));
  const yFor = (value) => pad.top + (maxValue - value) / Math.max(1, maxValue - minValue) * innerHeight;
  const palette = ["var(--teal)", "var(--coral)", "var(--gold)", "#7b8cff", "#b06cff", "#56b4a8", "#d47c62", "#84945c"];
  const lineFor = (item) => {
    let path = "";
    let penDown = false;
    years.forEach((year, index) => {
      const value = historyValue(item, year, metricKey);
      if (value === null) { penDown = false; return; }
      path += `${penDown ? "L" : "M"} ${xFor(index)} ${yFor(value)} `;
      penDown = true;
    });
    return path.trim();
  };
  const paths = valid.map((item, index) => `<path d="${lineFor(item)}" fill="none" stroke="${palette[index % palette.length]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`).join("");
  const points = valid.map((item, itemIndex) => years.map((year, yearIndex) => {
    const value = historyValue(item, year, metricKey);
    if (value === null) return "";
    return `<circle cx="${xFor(yearIndex)}" cy="${yFor(value)}" r="3.5" fill="${palette[itemIndex % palette.length]}" stroke="var(--card)" stroke-width="2"><title>${escapeHtml(companyName(item))} · ${year}년 · ${escapeHtml(fmtNumber(value, metricDefs[metricKey].kind))}</title></circle>`;
  }).join("")).join("");
  const yearLabels = years.map((year, index) => `<text x="${xFor(index)}" y="${chartHeight - 13}" text-anchor="middle" fill="var(--muted)" font-size="10">${year}</text>`).join("");
  const grid = [0, .5, 1].map((ratio) => { const value = maxValue - (maxValue - minValue) * ratio; const y = yFor(value); return `<line x1="${pad.left}" y1="${y}" x2="${chartWidth - pad.right}" y2="${y}" stroke="var(--line)"/><text x="${pad.left - 8}" y="${y + 3}" text-anchor="end" fill="var(--muted)" font-size="9">${escapeHtml(fmtNumber(value, metricDefs[metricKey].kind))}</text>`; }).join("");
  const latestYear = years[years.length - 1];
  const firstYear = years[0];
  const cards = valid.slice(0, 4).map((item, index) => {
    const first = historyValue(item, firstYear, metricKey);
    const latest = historyValue(item, latestYear, metricKey);
    const delta = first !== null && latest !== null && first !== 0 ? (latest - first) / Math.abs(first) * 100 : null;
    return `<div class="trend-card"><span><i class="trend-color" style="background:${palette[index % palette.length]}"></i>${escapeHtml(companyName(item))}</span><strong class="${delta !== null && delta >= 0 ? "delta-up" : "delta-down"}">${delta === null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}%`}</strong><small>${firstYear} → ${latestYear} · ${escapeHtml(fmtNumber(latest, metricDefs[metricKey].kind))}</small></div>`;
  }).join("");
  const tableHead = `<thead><tr><th>연도</th>${valid.map((item) => `<th>${escapeHtml(companyName(item))}</th>`).join("")}</tr></thead>`;
  const tableBody = years.map((year) => `<tr><td>${year}</td>${valid.map((item) => { const value = historyValue(item, year, metricKey); return `<td class="number ${value === null ? "na" : ""}">${escapeHtml(value === null ? "데이터 없음" : fmtNumber(value, metricDefs[metricKey].kind))}</td>`; }).join("")}</tr>`).join("");
  const legend = valid.map((item, index) => `<span><i style="background:${palette[index % palette.length]}"></i>${escapeHtml(companyName(item))}</span>`).join("");
  return `<div class="tab-panel trend-layout"><article class="panel chart-panel"><div class="panel-title"><div><span class="kicker">YEARLY TREND</span><h3>${metricDefs[metricKey].label} 연도별 추이</h3></div><span>${firstYear}–${latestYear} · ${reportLabel(state.reportCode)}</span></div><svg class="trend-svg yearly-trend-svg" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="${escapeHtml(metricDefs[metricKey].label)} 연도별 추이">${grid}${paths}${points}${yearLabels}</svg><div class="trend-legend">${legend}</div></article><div class="trend-side">${cards}</div><article class="table-panel trend-years-panel"><div class="panel-title"><div><span class="kicker">YEAR BY YEAR</span><h3>연도별 수치</h3></div><span>지표: ${metricDefs[metricKey].label}</span></div><div class="table-scroll"><table class="data-table trend-table">${tableHead}<tbody>${tableBody}</tbody></table></div></article></div>`;
}

function renderPeople() {
  const data = (state.people || []).filter((item) => item?.people && !item.error);
  const hasPeopleValue = (item) => ["employees_total", "regular_employees", "average_tenure_years", "average_salary", "executives_total", "unregistered_pay_total"].some((key) => peopleValue(item, key) !== null);
  const valid = data.filter(hasPeopleValue);
  if (!valid.length) return renderEmpty("People 데이터가 없습니다.", "선택한 기업의 직원·임원 현황 공시가 없거나 해당 보고서에서 제공되지 않습니다.");
  const selectedCount = Math.max((state.people || []).length, valid.length);
  const sumStat = (key) => {
    const rows = valid.map((item) => peopleValue(item, key)).filter((value) => value !== null);
    return {
      value: rows.length ? rows.reduce((total, value) => total + value, 0) : null,
      coverage: rows.length,
    };
  };
  const weightedStat = (key, weightKey = "employees_total") => {
    const rows = valid
      .map((item) => ({ value: peopleValue(item, key), weight: peopleValue(item, weightKey) }))
      .filter((row) => row.value !== null && row.weight > 0);
    const weight = rows.reduce((total, row) => total + row.weight, 0);
    return {
      value: weight ? rows.reduce((total, row) => total + row.value * row.weight, 0) / weight : null,
      coverage: rows.length,
    };
  };
  const pairedRegularRows = valid
    .map((item) => ({
      employees: peopleValue(item, "employees_total"),
      regular: peopleValue(item, "regular_employees"),
    }))
    .filter((row) => row.employees > 0 && row.regular !== null);
  const pairedEmployees = pairedRegularRows.reduce((total, row) => total + row.employees, 0);
  const totalEmployees = sumStat("employees_total");
  const totalExecutives = sumStat("executives_total");
  const averageTenure = weightedStat("average_tenure_years");
  const averageSalary = weightedStat("average_salary");
  const regularShare = pairedEmployees
    ? pairedRegularRows.reduce((total, row) => total + row.regular, 0) / pairedEmployees * 100
    : null;
  const coverageLabel = (coverage, suffix) => `${coverage}/${selectedCount}개 기업 사용 · ${suffix}`;
  const cards = [
    ["총 직원 수", fmtCount(totalEmployees.value), coverageLabel(totalEmployees.coverage, "합산")],
    ["정규직 비중", fmtPercent(regularShare), coverageLabel(pairedRegularRows.length, "정규직÷총직원")],
    ["평균 근속", fmtYears(averageTenure.value), coverageLabel(averageTenure.coverage, "직원수 가중")],
    ["1인 평균 급여", fmtSalary(averageSalary.value), coverageLabel(averageSalary.coverage, averageSalaryAggregateLabel(valid))],
    ["임원 수", fmtCount(totalExecutives.value), coverageLabel(totalExecutives.coverage, "공시 행 합산")],
  ];
  const rows = state.people.map((item) => {
    const p = people(item);
    const f = financials(resultFor(item.company?.corp_code));
    const employees = peopleValue(item, "employees_total");
    const revenuePerEmployee = employees && numberValue(f.revenue) !== null ? f.revenue / employees : null;
    const regular = peopleValue(item, "regular_employees");
    const regularShare = regular !== null && employees ? regular / employees * 100 : null;
    const averageSalary = peopleValue(item, "average_salary");
    const salaryBasis = averageSalaryBasisLabel(item.people?.average_salary_basis);
    return `<tr><td><strong>${escapeHtml(companyName(item))}</strong><br><small>${escapeHtml(item.company?.stock_code || item.company?.corp_code || "")}</small></td><td class="number ${employees === null ? "na" : ""}">${escapeHtml(fmtCount(employees))}</td><td class="number ${regular === null ? "na" : ""}">${escapeHtml(fmtCount(regular))}</td><td class="number ${peopleValue(item, "contract_employees") === null ? "na" : ""}">${escapeHtml(fmtCount(peopleValue(item, "contract_employees")))}</td><td class="number ${regularShare === null ? "na" : ""}">${escapeHtml(fmtPercent(regularShare))}</td><td class="number ${peopleValue(item, "average_tenure_years") === null ? "na" : ""}">${escapeHtml(fmtYears(peopleValue(item, "average_tenure_years")))}</td><td class="number ${averageSalary === null ? "na" : ""}">${escapeHtml(fmtSalary(averageSalary))}<small class="people-salary-basis">${escapeHtml(salaryBasis)}</small></td><td class="number ${peopleValue(item, "executives_total") === null ? "na" : ""}">${escapeHtml(fmtCount(peopleValue(item, "executives_total")))}</td><td class="number ${peopleValue(item, "unregistered_average_salary") === null ? "na" : ""}">${escapeHtml(fmtSalary(peopleValue(item, "unregistered_average_salary")))}</td><td class="number ${revenuePerEmployee === null ? "na" : ""}">${escapeHtml(fmtAmount(revenuePerEmployee))}</td></tr>`;
  }).join("");
  const sourceModes = [...new Set(valid.map((item) => item.people?.employee_aggregation).filter(Boolean))].map((mode) => mode === "gender_total" ? "성별합계 우선 집계" : "반환 행 전체 대체 집계");
  const salaryBases = [...new Set(valid.map((item) => item.people?.average_salary_basis).filter(Boolean))].map((basis) => `평균 급여: ${averageSalaryBasisLabel(basis)}`);
  const qualityNotes = [...new Set(valid.flatMap((item) => [
    ...(item.component_quality?.employees?.warnings || []),
    ...(item.component_quality?.unregistered_pay?.warnings || []),
  ]))];
  const qualityMessage = qualityNotes.length
    ? ` · 데이터 주의: ${qualityNotes.join(" · ")}`
    : "";
  return `<div class="tab-panel people-layout"><div class="kpi-grid people-kpi-grid">${cards.map(([label, value, sub]) => `<div class="kpi"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(sub)}</small></div>`).join("")}</div><article class="panel"><div class="panel-title"><div><span class="kicker">PEOPLE ANALYTICS SNAPSHOT</span><h3>인력·보상 구조 비교</h3></div><span>${state.year}년 · ${reportLabel(state.reportCode)}</span></div><div class="table-scroll"><table class="data-table people-table"><thead><tr><th>기업</th><th>총 직원</th><th>정규직</th><th>계약직</th><th>정규직 비중</th><th>평균 근속</th><th>1인 평균 급여</th><th>임원 수</th><th>미등기임원 평균 급여</th><th>매출/인</th></tr></thead><tbody>${rows}</tbody></table></div></article><article class="people-note panel"><div><span class="kicker">STRATEGY READOUT</span><h3>HR 전략에 활용하는 방법</h3></div><p>직원 수·정규직 비중·근속·급여와 재무 규모가 선택 기업 안에서 어떤 조합으로 공시됐는지 비교할 수 있습니다. <strong>매출/인</strong>은 생산성의 참고지표이고, 채용·보상·조직개편의 원인을 단정하는 지표는 아닙니다.</p><small>집계 방식: ${escapeHtml(sourceModes.concat(salaryBases).join(" · ") || "원문 행 기준")}${escapeHtml(qualityMessage)} · DART 공시에는 개인별 성과·이직·몰입·역량 데이터가 포함되지 않습니다.</small></article></div>`;
}

function renderExecutives() {
  const valid = (state.executives || []).filter((item) => item?.executive_metrics && item.quality?.status !== "no_data" && !item.error);
  if (state.executivesError) return renderEmpty("임원 API 요청에 실패했습니다.", state.executivesError);
  if (!valid.length) return renderEmpty("임원 데이터가 없습니다.", "선택한 기업의 임원 현황 공시가 없거나 해당 보고서에서 제공되지 않습니다.");
  const metrics = (item) => item.executive_metrics || {};
  const sum = (key) => {
    const values = valid.map((item) => numberValue(metrics(item)[key]));
    return values.length && values.every((value) => value !== null)
      ? values.reduce((total, value) => total + value, 0)
      : null;
  };
  const average = (key) => {
    const values = valid.map((item) => numberValue(metrics(item)[key]));
    return values.length && values.every((value) => value !== null)
      ? values.reduce((total, value) => total + value, 0) / values.length
      : null;
  };
  const averageTenure = average("average_tenure_months");
  const cards = [
    ["전체 임원", fmtCount(sum("executives_total")), `${valid.length}개 기업 합산`],
    ["사외이사 비율", fmtPercent(average("outside_director_share")), "등기임원 기준 참고지표"],
    ["여성 임원 비율", fmtPercent(average("female_share")), "전체 임원 기준"],
    ["평균 재직기간", averageTenure === null ? "—" : `${Math.round(averageTenure).toLocaleString("ko-KR")}개월`, "공시 재직기간 평균"],
    ["12개월 이내 임기 만료", fmtCount(sum("term_expiring_within_12_months")), "보고기간 말일 이후 달력 기준 12개월"],
  ];
  const rows = valid.map((item) => {
    const p = metrics(item);
    const value = (key) => numberValue(p[key]);
    return `<tr><td><strong>${escapeHtml(companyName(item))}</strong><br /><small>${escapeHtml(item.company?.stock_code || item.company?.corp_code || "")}</small></td><td class="number">${escapeHtml(fmtCount(value("executives_total")))}</td><td class="number">${escapeHtml(fmtCount(value("registered_executives")))}</td><td class="number">${escapeHtml(fmtCount(value("outside_directors")))}</td><td class="number">${escapeHtml(fmtCount(value("ceo_count")))}</td><td class="number">${escapeHtml(fmtPercent(value("female_share")))}</td><td class="number">${escapeHtml(value("average_tenure_months") === null ? "데이터 없음" : `${Math.round(value("average_tenure_months")).toLocaleString("ko-KR")}개월`)}</td><td class="number">${escapeHtml(fmtCount(value("term_expiring_within_12_months")))}</td></tr>`;
  }).join("");
  const qualityNotes = [...new Set(valid.flatMap((item) => (item.quality?.warnings || [])))];
  return `<div class="tab-panel people-layout"><div class="kpi-grid people-kpi-grid">${cards.map(([label, value, sub]) => `<div class="kpi"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(sub)}</small></div>`).join("")}</div><article class="panel"><div class="panel-title"><div><span class="kicker">EXECUTIVE STRUCTURE</span><h3>임원·이사회 구조 비교</h3></div><span>${state.year}년 · ${reportLabel(state.reportCode)}</span></div><div class="table-scroll"><table class="data-table people-table"><thead><tr><th>기업</th><th>전체 임원</th><th>등기임원</th><th>사외이사</th><th>대표이사</th><th>여성 임원 비율</th><th>평균 재직기간</th><th>12개월 이내 만료</th></tr></thead><tbody>${rows}</tbody></table></div></article><article class="people-note panel"><div><span class="kicker">TENURE & SUCCESSION</span><h3>승계 관점의 참고지표</h3></div><p>임기 만료 예정자 수와 평균 재직기간은 이사회·경영진 변화 가능성을 확인하는 출발점입니다. 승계 리스크나 조직문화의 원인을 단정하지 않고 후속 공시와 내부 검토가 필요합니다.</p><small>${escapeHtml(qualityNotes.length ? `데이터 주의: ${qualityNotes.join(" · ")}` : "개인별 임원 원자료는 화면에 노출하지 않습니다.")}</small></article></div>`;
}

function normalized(item, key, comparisonRows = availableResults()) { const values = comparisonRows.map((row) => valueFor(row, key)).filter((value) => value !== null); const value = valueFor(item, key); if (value === null || !values.length) return null; const max = Math.max(...values); const min = Math.min(...values); return max === min ? 70 : 20 + ((value - min) / (max - min)) * 70; }

function relativeComparisonBoundary() {
  return '<p class="comparison-boundary" role="note">선택 기업 내부 상대 비교이며 인과·개인평가·자동 인사조치의 근거가 아닙니다.</p>';
}

function renderRadar() {
  const keys = ["operating_margin", "current_ratio", "debt_ratio", "cash", "equity"]; const valid = availableResults().filter((item) => keys.every((key) => valueFor(item, key) !== null)); if (!valid.length) return renderEmpty("레이더를 그릴 완전한 데이터가 없습니다.", "영업이익률·유동비율·부채비율·현금·자본이 모두 공시된 기업이 필요합니다."); const center = 175; const radius = 120; const point = (index, value) => { const angle = -Math.PI / 2 + index * (Math.PI * 2 / keys.length); const r = radius * (value / 100); return `${center + Math.cos(angle) * r},${center + Math.sin(angle) * r}`; }; const grid = [25, 50, 75, 100].map((scale) => `<polygon points="${keys.map((_, i) => point(i, scale)).join(" ")}" fill="none" stroke="var(--line)" stroke-width="1"/>`).join(""); const axes = keys.map((key, i) => { const angle = -Math.PI / 2 + i * (Math.PI * 2 / keys.length); const x = center + Math.cos(angle) * radius; const y = center + Math.sin(angle) * radius; return `<line x1="${center}" y1="${center}" x2="${x}" y2="${y}" stroke="var(--line)"/><text x="${center + Math.cos(angle) * (radius + 22)}" y="${center + Math.sin(angle) * (radius + 22)}" text-anchor="middle" fill="var(--muted)" font-size="10">${metricDefs[key].label}</text>`; }).join(""); const polygons = valid.slice(0, 4).map((item, companyIndex) => `<polygon points="${keys.map((key, i) => point(i, normalized(item, key, valid))).join(" ")}" fill="var(--teal)" fill-opacity="${Math.max(.08, .2 - companyIndex * .025)}" stroke="${companyIndex % 2 ? "var(--coral)" : "var(--teal)"}" stroke-width="2"/>`).join(""); const legend = valid.slice(0, 4).map((item, index) => `<div class="legend-row"><i style="background:${index % 2 ? "var(--coral)" : "var(--teal)"}"></i>${escapeHtml(companyName(item))}<small>상대지수</small></div>`).join(""); return `<div class="tab-panel radar-layout"><article class="panel radar-box"><svg class="radar-svg" viewBox="0 0 350 350">${grid}${axes}${polygons}</svg></article><article class="panel radar-legend"><div class="panel-title"><div><span class="kicker">STRUCTURE PROFILE</span><h3>상대 비교 레이더</h3></div></div><p style="color:var(--muted);font-size:10px;line-height:1.6">선택한 기업 안에서 가장 낮은 값을 20, 가장 높은 값을 90에 가깝게 표시합니다. 절대 점수가 아니라 상대적인 구조를 봅니다.</p>${legend}${relativeComparisonBoundary()}</article></div>`;
}

function scatterAxisPosition(value, values) {
  const finiteValues = (values || []).map(numberValue).filter((item) => item !== null);
  const numericValue = numberValue(value);
  if (numericValue === null || !finiteValues.length) return null;
  const min = Math.min(...finiteValues, 0);
  const max = Math.max(...finiteValues, 0);
  if (min === max) return 50;
  return Math.max(5, Math.min(95, 5 + ((numericValue - min) / (max - min)) * 90));
}

function renderScatter() {
  const valid = availableResults().filter((item) => valueFor(item, "debt_ratio") !== null && valueFor(item, "operating_margin") !== null); if (!valid.length) return renderEmpty("산점도를 그릴 데이터가 없습니다.", "부채비율과 영업이익률이 모두 있는 기업이 필요합니다."); const xValues = valid.map((item) => valueFor(item, "debt_ratio")); const yValues = valid.map((item) => valueFor(item, "operating_margin")); const points = valid.map((item) => { const x = scatterAxisPosition(valueFor(item, "debt_ratio"), xValues); const y = scatterAxisPosition(valueFor(item, "operating_margin"), yValues); return `<span class="scatter-point" style="left:${x}%;bottom:${y}%" title="${escapeHtml(companyName(item))}">${escapeHtml(companyName(item).slice(0, 1))}</span>`; }).join(""); return `<div class="tab-panel"><article class="panel"><div class="panel-title"><div><span class="kicker">RISK / RETURN</span><h3>부채비율 × 영업이익률</h3></div><span>오른쪽일수록 부채비율 높음</span></div><div class="scatter-box"><span class="scatter-axis-y">영업이익률 ↑</span><span class="scatter-axis-x">부채비율 →</span>${points}</div><p class="scatter-note">점에 마우스를 올리면 기업명을 확인할 수 있습니다. 좌상단은 상대적으로 높은 수익성과 낮은 부채비율에 가깝습니다. 음수 값이 있으면 0을 포함한 양방향 축으로 비교합니다.</p>${relativeComparisonBoundary()}</article></div>`;
}

function renderRank() {
  const key = state.selectedMetrics.find((candidate) => ["debt_ratio", "operating_margin", "current_ratio"].includes(candidate)) || state.selectedMetrics[0]; const valid = availableResults().filter((item) => valueFor(item, key) !== null); if (!valid.length) return renderEmpty("순위를 만들 데이터가 없습니다.", "선택한 지표의 공시 데이터가 없습니다."); const descending = key !== "debt_ratio"; valid.sort((a, b) => (valueFor(b, key) - valueFor(a, key)) * (descending ? 1 : -1)); const values = valid.map((item) => Math.abs(valueFor(item, key))); const max = Math.max(...values, 1); return `<div class="tab-panel"><article class="panel"><div class="panel-title"><div><span class="kicker">LEADERBOARD</span><h3>${metricDefs[key].label} 순위</h3></div><span>${descending ? "높은 값부터" : "낮은 값부터"} · 우열 판단 아님</span></div><div class="rank-list" style="margin-top:18px">${valid.map((item, index) => `<div class="rank-row"><span class="rank-number">${String(index + 1).padStart(2, "0")}</span><strong class="rank-name">${escapeHtml(companyName(item))}</strong><span class="rank-track"><i style="width:${Math.max(5, Math.abs(valueFor(item, key)) / max * 100)}%"></i></span><span class="rank-value">${escapeHtml(metricValue(item, key))}</span></div>`).join("")}</div>${relativeComparisonBoundary()}</article></div>`;
}

function strategyPeopleResult(code, source = state.people) {
  return (source || []).find((item) => item.company?.corp_code === code);
}

function strategyHistoryValue(row, section, key) {
  return numberValue(section === "financials" ? row?.financials?.[key] : row?.people?.[key]);
}

function strategySeries(source, code, section, key) {
  const company = (source || []).find((item) => item.company?.corp_code === code);
  const actual = (company?.years || [])
    .map((row) => ({ year: Number(row.year), value: strategyHistoryValue(row, section, key) }))
    .filter((row) => Number.isFinite(row.year) && row.value !== null)
    .sort((a, b) => a.year - b.year)
    .slice(-3);
  if (!actual.length) return [];
  const last = actual[actual.length - 1];
  const previous = actual.length > 1 ? actual[actual.length - 2] : null;
  const forecast = previous ? last.value + (last.value - previous.value) : last.value;
  if (actual.length < 2 || (section === "people" && forecast < 0)) return actual;
  return [...actual, { year: last.year + 1, value: forecast, estimated: true }];
}

function strategyWeightedAverage(rows, field) {
  const values = (rows || []).map((row) => ({ value: numberValue(row[field]), weight: numberValue(row.total) }));
  if (!values.length || values.some((row) => row.weight === null || row.weight < 0)) return null;
  const contributing = values.filter((row) => row.weight > 0);
  if (!contributing.length || contributing.some((row) => row.value === null)) return null;
  const weight = contributing.reduce((sum, row) => sum + row.weight, 0);
  return contributing.reduce((sum, row) => sum + row.value * row.weight, 0) / weight;
}

function strategyGenderSummary(item, gender) {
  const rows = (item?.employee_breakdown || []).filter((row) => String(row.sex || "").includes(gender));
  const headcounts = rows.map((row) => numberValue(row.total));
  return {
    headcount: headcounts.length && headcounts.every((value) => value !== null)
      ? headcounts.reduce((sum, value) => sum + value, 0)
      : null,
    salary: strategyWeightedAverage(rows, "average_salary"),
    tenure: strategyWeightedAverage(rows, "average_tenure"),
  };
}

const strategyDecisionLabels = {
  productivity: "인력 생산성",
  compensation_sustainability: "보상 지속가능성",
  workforce_structure: "인력구조 변화",
  governance_continuity: "리더십 연속성",
  data_completeness: "근거 연결 완전성",
};
const strategySignalLabels = {
  benchmark: "비교 기준",
  early_warning_proxy: "조기점검 대리 지표",
  lagging: "후행 지표",
  data_gap: "데이터 공백",
};
const strategyReadinessLabels = {
  ready: "비교 준비",
  directional_only: "방향성 참고",
  blocked: "근거 부족",
};
const strategyConfidenceLabels = {
  high: "높음",
  medium: "보통",
  low: "낮음",
};
const strategyPolicyStatusLabels = {
  allowed: "허용",
  blocked: "차단",
};
const strategyReasonLabels = {
  peer_benchmark_available: "선택 기업 비교 가능",
  partial_metric_coverage: "후보 지표 일부만 비교 가능",
  single_usable_observation: "단일 기업 근거",
  required_metric_missing: "필수 지표 미공시",
  source_link_gap: "원문 연결 공백",
  quality_limit_present: "품질 제한 있음",
  small_peer_sample: "비교 표본 4개 미만",
  history_not_in_readiness: "추이는 판단 준비도 산정 제외",
  fallback_metric_used: "대체 계산 지표 사용",
  restatement_not_verified: "정정공시 최신성 미확인",
};
const strategyGapLabels = {
  missing_disclosure: "미공시",
  partial_disclosure: "부분 공시",
  comparability_limit: "비교 제한",
  source_link_gap: "원문 연결 공백",
  calculation_blocked: "계산 차단",
};
const strategyGapDetailLabels = {
  gender_total_not_returned_all_rows_used: "성별합계 행 미반환·전체 행 대체",
  term_end_not_parseable: "임기 종료일 일부 해석 불가",
  term_end_partial_executive_count: "임기 종료일 일부 인원만 확인",
  tenure_not_parseable: "근속기간 일부 해석 불가",
  source_url_missing: "원문 URL 없음",
  component_receipt_missing: "구성요소 접수번호 없음",
};

function strategyHistoryMetric(metricId, code) {
  const financialCompany = (state.history || []).find((item) => item.company?.corp_code === code);
  const peopleCompany = (state.peopleHistory || []).find((item) => item.company?.corp_code === code);
  const financialByYear = new Map((financialCompany?.years || []).map((row) => [String(row.year), row]));
  const peopleByYear = new Map((peopleCompany?.years || []).map((row) => [String(row.year), row]));
  const years = [...new Set([...financialByYear.keys(), ...peopleByYear.keys()])].sort();
  return years.map((year) => {
    const financialRow = financialByYear.get(year);
    const peopleRow = peopleByYear.get(year);
    const employees = peopleValue(peopleRow, "employees_total");
    let value = null;
    if (metricId === "operating_profit_per_employee") {
      const profit = numberValue(financialRow?.financials?.operating_profit);
      value = profit !== null && employees ? profit / employees : null;
    } else if (metricId === "revenue_per_employee") {
      const revenue = numberValue(financialRow?.financials?.revenue);
      value = revenue !== null && employees ? revenue / employees : null;
    } else if (metricId === "salary_to_revenue") {
      const salaryTotal = peopleValue(peopleRow, "annual_salary_total");
      const revenue = numberValue(financialRow?.financials?.revenue);
      value = salaryTotal !== null && revenue ? salaryTotal / revenue * 100 : null;
    } else if (metricId === "operating_margin") {
      value = numberValue(financialRow?.financials?.operating_margin);
    } else if (metricId === "contract_share") {
      const contract = peopleValue(peopleRow, "contract_employees");
      value = contract !== null && employees ? contract / employees * 100 : null;
    } else if (metricId === "average_tenure_years") {
      value = peopleValue(peopleRow, "average_tenure_years");
    }
    return { year, value };
  }).filter((row) => row.value !== null).slice(-2);
}

function strategyTrajectoryLabel(metricId, item) {
  const rows = strategyHistoryMetric(metricId, item.company?.corp_code);
  if (rows.length < 2) return `${companyName(item)} · 추이 근거 부족`;
  const [previous, current] = rows;
  const relative = previous.value === 0 ? current.value - previous.value : (current.value - previous.value) / Math.abs(previous.value);
  const direction = Math.abs(relative) < 0.01 ? "유사" : relative > 0 ? "상승" : "하락";
  return `${companyName(item)} · ${previous.year}→${current.year} ${direction}`;
}

function strategyMetricDisplay(metricId, value) {
  if (["operating_profit_per_employee", "revenue_per_employee"].includes(metricId)) return fmtAmount(value);
  if (["salary_to_revenue", "operating_margin", "contract_share", "outside_director_share"].includes(metricId)) return fmtPercent(value);
  if (metricId === "average_tenure_years") return fmtYears(value);
  return fmtNumber(value, "number");
}

function strategyPeerPositionLabel(brief, peer) {
  const delta = numberValue(peer.peer_delta);
  const median = numberValue(peer.peer_median);
  const tolerance = median === null ? 0 : Math.max(Math.abs(median) * 0.01, 1e-9);
  const position = delta === null || Math.abs(delta) <= tolerance ? "중앙값 부근" : delta > 0 ? "중앙값 상회" : "중앙값 하회";
  return `${strategyMetricDisplay(brief.selected_metric_id, peer.value)} · ${position}`;
}

function strategyMetricQualityDetail(assessment) {
  if (assessment.quality_complete !== false) return "";
  const componentBySource = {
    financial_status: "financials",
    employee_status: "employees",
    executive_status: "executives",
    unregistered_executive_pay: "unregistered_pay",
  };
  const componentLabels = {
    financial_status: "재무",
    employee_status: "직원 현황",
    executive_status: "임원 현황",
    unregistered_executive_pay: "미등기임원 보수",
  };
  const ledger = new Map((state.orchestration?.evidence?.ledger || [])
    .map((item) => [item.evidence_id, item]));
  const facts = new Map((state.orchestration?.facts?.records || [])
    .map((item) => [item.observation_id, item]));
  const grouped = new Map();
  (assessment.evidence_ids || []).forEach((evidenceId) => {
    const evidence = ledger.get(evidenceId);
    const fact = facts.get(evidence?.observation_id);
    (evidence?.source_components || []).forEach((source) => {
      const component = fact?.quality?.components?.[componentBySource[source]];
      if (!component || component.status === "complete") return;
      if (!grouped.has(source)) grouped.set(source, new Set());
      grouped.get(source).add(evidence.company?.corp_name || fact?.company?.corp_name || "기업 확인 필요");
    });
  });
  if (!grouped.size) return "관련 구성요소 품질 확인 필요";
  return [...grouped.entries()]
    .map(([source, companies]) => `${componentLabels[source] || source}: ${[...companies].join("·")}`)
    .join(" · ");
}

function renderStrategyDecisionBriefs(valid) {
  const briefs = state.orchestration?.decision_support?.briefs || [];
  if (!briefs.length) return `<section class="strategy-section strategy-decision-section"><div class="strategy-section-heading"><span class="kicker">DECISION BRIEF</span><h3>HR 의사결정 브리프</h3><p>근거 연결이 완료되지 않아 판단을 보류합니다.</p></div><div class="strategy-missing">결측값을 0으로 바꾸거나 공시 밖의 원인을 추정하지 않습니다.</div></section>`;
  const readinessItems = state.orchestration?.decision_support?.readiness || [];
  const readyWithQualityLimit = readinessItems.some((item) => (
    item.status === "ready"
    && item.confidence === "low"
    && (item.reason_codes || []).includes("quality_limit_present")
  ));
  const qualityLimitWarning = readyWithQualityLimit
    ? " 비교 표본은 충족했지만 일부 공시 품질 경고로 근거 신뢰를 낮게 두었습니다."
    : "";
  const restatementWarning = readinessItems.some((item) => (item.reason_codes || []).includes("restatement_not_verified"))
    ? `<div class="strategy-readiness-notice" role="note" aria-label="정정공시 최신성 경고"><strong>정정공시 최신성 미검증</strong><span>‘비교 준비’는 원문 연결·표본 조건만 뜻합니다.${qualityLimitWarning} 최신 정정공시 대조 전 확정 판단에 사용하지 마세요.</span></div>`
    : "";
  const readinessMatrix = readinessItems.map((item) => {
    const label = strategyDecisionLabels[item.dimension_id] || item.dimension_id;
    const status = strategyReadinessLabels[item.status] || item.status;
    const basis = item.selected_metric_label || (item.dimension_id === "data_completeness" ? "전체 원문·품질" : "대표 지표 없음");
    const confidence = strategyConfidenceLabels[item.confidence] || item.confidence || "미산정";
    const governanceBoundary = item.dimension_id === "governance_continuity"
      ? `<small class="strategy-readiness-boundary">승계 권고 아님 · 다음 확인: ${escapeHtml(item.next_data?.[0] || "핵심보직 승계 후보군")}<span>직접 알 수 없음: ${escapeHtml(item.interpretation_limit || "승계 준비도·이사회 실효성·임원 개인 성과")}</span></small>`
      : "";
    return `<div class="${escapeHtml(item.status || "blocked")}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(status)}</strong><small>${escapeHtml(basis)}</small><small>근거 신뢰 ${escapeHtml(confidence)}</small>${governanceBoundary}</div>`;
  }).join("");
  const cards = briefs.map((brief) => {
    const status = strategyReadinessLabels[brief.status] || "판단 보류";
    const conclusion = brief.conclusion || (brief.status === "blocked"
      ? "필수 공시 또는 원문 근거가 부족해 결론을 내리지 않습니다."
      : "선택 기업 집합 안의 상대 위치만 확인하며 원인이나 우열을 뜻하지 않습니다.");
    const peers = (brief.peer_context || []).length
      ? brief.peer_context.map((peer) => `<li><strong>${escapeHtml(peer.company?.corp_name || peer.observation_id)}</strong><span>${escapeHtml(strategyPeerPositionLabel(brief, peer))}</span>${renderEvidenceBadge(peer.evidence_id, state.orchestration?.evidence?.ledger || [])}</li>`).join("")
      : `<li class="empty"><span>비교 가능한 기업 근거가 없습니다.</span></li>`;
    const trajectories = valid.map((item) => `<li>${escapeHtml(strategyTrajectoryLabel(brief.selected_metric_id, item))}</li>`).join("");
    const nextData = (brief.next_data || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const reasons = (brief.reason_codes || []).map((code) => strategyReasonLabels[code] || code).join(" · ");
    const secondaryRepresentative = Boolean(
      brief.selected_metric_id
      && brief.metric_ids?.[0]
      && brief.selected_metric_id !== brief.metric_ids[0]
    );
    const representativeScopeNotice = secondaryRepresentative
      ? `<small class="strategy-representative-notice">우선 지표보다 원문 연결 범위가 넓은 보조 지표를 대표로 사용했습니다. 보상·인력 조치 전 우선 지표와 내부 원장을 확인하세요.</small>`
      : "";
    const metricAssessments = (brief.metric_assessments || []).map((item) => {
      const count = item.coverage?.comparable_observation_count ?? 0;
      const total = item.coverage?.total_observation_count ?? 0;
      const qualityDetail = strategyMetricQualityDetail(item);
      const qualityCopy = qualityDetail
        ? `<small class="strategy-metric-quality">품질 주의 · ${escapeHtml(qualityDetail)}</small>`
        : "";
      return `<li class="${escapeHtml(item.status || "blocked")}"><div><strong>${escapeHtml(item.metric_label || item.metric_id)}</strong>${qualityCopy}</div><span>${escapeHtml(strategySignalLabels[item.signal_type] || item.signal_type)} · ${escapeHtml(String(count))}/${escapeHtml(String(total))}개</span></li>`;
    }).join("");
    return `<article class="strategy-decision-card ${escapeHtml(brief.status || "blocked")}"><div class="strategy-decision-head"><div><span class="kicker">${escapeHtml(strategyDecisionLabels[brief.brief_id] || brief.brief_id)}</span><h4>${escapeHtml(brief.question || "확인 질문")}</h4></div><span class="strategy-readiness-badge">${escapeHtml(status)}</span></div><p class="strategy-decision-conclusion">${escapeHtml(conclusion)}</p><div class="strategy-decision-action"><strong>다음 판단 행동</strong><span>${escapeHtml(brief.decision_action || "추가 내부 데이터를 확인하기 전에는 개입 결정을 보류합니다.")}</span></div><div class="strategy-representative-metric"><strong>대표 지표 · ${escapeHtml(brief.selected_metric_label || brief.selected_metric_id || "없음")}</strong>${representativeScopeNotice}<span>${escapeHtml(brief.selection_reason || "대표 지표 선정 근거가 없습니다.")}</span><ul>${metricAssessments}</ul></div><div class="strategy-decision-meta"><span>${escapeHtml(strategySignalLabels[brief.signal_type] || brief.signal_type)}</span><span>근거 신뢰 ${escapeHtml(strategyConfidenceLabels[brief.confidence] || "낮음")}</span><span>근거 ${escapeHtml(String((brief.evidence_ids || []).length))}개</span></div><p class="strategy-decision-reasons">${escapeHtml(reasons)}</p><div class="strategy-decision-columns"><div><strong>선택 기업 중앙값 위치</strong><small class="strategy-cohort-limit">${escapeHtml(brief.cohort_limit || "선택 기업 내부 비교이며 산업·규모 보정 벤치마크가 아닙니다.")}</small><ul class="strategy-peer-list">${peers}</ul></div><div><strong>별도 이력 참고</strong><small>readiness 산정 제외 · 단순 2시점 방향</small><ul>${trajectories}</ul></div></div><div class="strategy-decision-limit"><strong>여기까지는 알 수 없음</strong><span>${escapeHtml((brief.cannot_tell || []).join(" · "))}</span><small>${escapeHtml(brief.interpretation_limit || "")}</small></div><div class="strategy-next-data"><strong>다음 내부 데이터</strong><ol>${nextData}</ol></div></article>`;
  }).join("");
  return `<section class="strategy-section strategy-decision-section"><div class="strategy-section-heading"><span class="kicker">DECISION BRIEF</span><h3>무엇을 판단하고, 무엇을 더 확인할 것인가</h3><p>AI 해석과 분리된 결정론적 브리프입니다. 대표 지표·선택 기업 중앙값·근거·판단 한계를 같은 카드에서 확인합니다.</p></div>${restatementWarning}<div class="strategy-readiness-matrix" aria-label="전체 HR 판단 준비도">${readinessMatrix}</div><div class="strategy-decision-grid">${cards}</div></section>`;
}

function strategyCompanyMetric(label, value, detail, tone = "") {
  return `<div class="strategy-company-metric ${tone}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(detail)}</small></div>`;
}

function strategyChartAmount(value) {
  const number = numberValue(value);
  if (number === null) return "—";
  if (Math.abs(number) >= 1000000000000) return `${(number / 1000000000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  return fmtAmount(number);
}

function renderStrategySalaryChart(seriesByCompany) {
  const available = seriesByCompany.map((entry, index) => ({ ...entry, index })).filter((entry) => entry.series.length);
  const requestError = seriesByCompany.find((item) => item.error)?.error;
  if (requestError) return `<div class="strategy-missing">DART 평균 급여 이력 요청이 실패했습니다: ${escapeHtml(requestError)}</div>`;
  if (!available.length) return `<div class="strategy-missing">평균 급여 추이 데이터가 공시되지 않았습니다.</div>`;
  const years = [...new Set(available.flatMap(({ series }) => series.map((row) => row.year)))].sort((a, b) => a - b);
  const forecastYear = Math.max(...years);
  const hasForecast = available.some(({ series }) => series.some((row) => row.estimated));
  const width = 760;
  const height = 292;
  const left = 64;
  const right = 28;
  const top = 28;
  const bottom = 52;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = available.flatMap(({ series }) => series.map((row) => row.value)).filter((value) => Number.isFinite(value));
  const minValue = Math.max(0, Math.min(...values) * 0.88);
  const maxValue = Math.max(...values, minValue + 1) * 1.08;
  const xFor = (year) => left + (years.length <= 1 ? plotWidth / 2 : (years.indexOf(year) / (years.length - 1)) * plotWidth);
  const yFor = (value) => top + (1 - (value - minValue) / (maxValue - minValue || 1)) * plotHeight;
  const ticks = [0, 1, 2, 3].map((index) => minValue + ((maxValue - minValue) * index) / 3);
  const forecastX = hasForecast ? xFor(forecastYear) : width - right;
  const step = plotWidth / Math.max(years.length - 1, 1);
  const zoneX = hasForecast ? Math.max(left, forecastX - step * 0.72) : width - right;
  const grid = ticks.map((tick) => `<line x1="${left}" y1="${yFor(tick).toFixed(1)}" x2="${width - right}" y2="${yFor(tick).toFixed(1)}" stroke="var(--ref-line-soft)"/><text class="strategy-svg-axis" x="${left - 10}" y="${(yFor(tick) + 4).toFixed(1)}" text-anchor="end">${escapeHtml(fmtSalary(tick))}</text>`).join("");
  const labels = years.map((year) => `<text class="strategy-svg-year" x="${xFor(year).toFixed(1)}" y="${height - 15}" text-anchor="middle"${year === forecastYear && hasForecast ? ` fill="var(--ref-warn)"` : ""}>${year}${year === forecastYear && hasForecast ? " E" : ""}</text>`).join("");
  const lines = available.map(({ item, series, index }) => {
    const tone = index % 2 ? "hyn" : "sam";
    const actual = series.filter((row) => !row.estimated);
    const forecast = series.find((row) => row.estimated);
    const actualPoints = actual.map((row) => `${xFor(row.year).toFixed(1)},${yFor(row.value).toFixed(1)}`).join(" ");
    const lastActual = actual[actual.length - 1];
    const delta = actual.length > 1 ? actual[actual.length - 1].value - actual[actual.length - 2].value : (actual[0]?.value || 0) * 0.05;
    const band = forecast ? Math.max(Math.abs(delta) * 0.35, Math.abs(forecast.value) * 0.04, 1000000) : 0;
    const bandTop = forecast ? yFor(Math.min(maxValue, forecast.value + band)) : 0;
    const bandBottom = forecast ? yFor(Math.max(minValue, forecast.value - band)) : 0;
    const labelOffset = index % 2 ? 22 : 12;
    const dots = actual.map((row, dotIndex) => `<circle cx="${xFor(row.year).toFixed(1)}" cy="${yFor(row.value).toFixed(1)}" r="${dotIndex === actual.length - 1 ? 4.7 : 3.8}" fill="var(--ref-${tone})"/><text class="strategy-svg-point ${tone}" x="${xFor(row.year).toFixed(1)}" y="${(yFor(row.value) - labelOffset).toFixed(1)}" text-anchor="middle">${escapeHtml(fmtSalary(row.value))}</text>`).join("");
    const forecastMarkup = forecast && lastActual ? `<polyline points="${xFor(lastActual.year).toFixed(1)},${yFor(lastActual.value).toFixed(1)} ${xFor(forecast.year).toFixed(1)},${yFor(forecast.value).toFixed(1)}" fill="none" stroke="var(--ref-${tone})" stroke-width="2" stroke-dasharray="6 5" opacity=".9"/><line x1="${forecastX.toFixed(1)}" y1="${bandTop.toFixed(1)}" x2="${forecastX.toFixed(1)}" y2="${bandBottom.toFixed(1)}" stroke="var(--ref-${tone})" stroke-width="9" opacity=".24" stroke-linecap="round"/><text class="strategy-svg-point ${tone}" x="${(forecastX - 10).toFixed(1)}" y="${(yFor(forecast.value) + (index % 2 ? 13 : 4)).toFixed(1)}" text-anchor="end">${escapeHtml(fmtSalary(forecast.value))}</text>` : "";
    return `<g class="strategy-salary-series"><polyline points="${actualPoints}" fill="none" stroke="var(--ref-${tone})" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>${forecastMarkup}${dots}</g>`;
  }).join("");
  const legend = available.map(({ item, index }) => `<span><i class="strategy-dot ${index % 2 ? "hyn" : "sam"}"></i>${escapeHtml(companyName(item))}</span>`).join("");
  return `<article class="strategy-chart-card strategy-salary-panel"><div class="strategy-chart-head"><div><strong>1인당 평균 급여 추이와 전망 구간</strong><small>DART 인력 공시 · 다음연도는 모델 추정</small></div><div class="strategy-chart-legend">${legend}<span><i class="strategy-dot forecast"></i>모델 추정</span></div></div><div class="strategy-salary-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="기업별 평균 급여 추이와 전망 구간">${hasForecast ? `<rect x="${zoneX.toFixed(1)}" y="${top}" width="${(width - right - zoneX).toFixed(1)}" height="${plotHeight}" fill="var(--ref-warn)" opacity=".055" stroke="var(--ref-warn)" stroke-dasharray="4 4"/><text class="strategy-svg-zone" x="${(zoneX + 9).toFixed(1)}" y="${top + 14}">FORECAST RANGE</text>` : ""}${grid}${lines}${labels}</svg></div><div class="strategy-inline-note"><b>전망은 확정 예측이 아닙니다.</b> 마지막 공시값과 최근 변화폭을 기반으로 화면에서만 계산한 모델 추정이며, 성과급 산식이나 개인별 보상을 의미하지 않습니다.</div></article>`;
}

function renderStrategyProfitChart(seriesByCompany) {
  const requestError = seriesByCompany.find((item) => item.error)?.error;
  if (requestError) return `<div class="strategy-missing">DART 영업이익 이력 요청이 실패했습니다: ${escapeHtml(requestError)}</div>`;
  const rows = seriesByCompany.flatMap(({ item, series }, companyIndex) => series.map((row) => ({ ...row, item, companyIndex })));
  if (!rows.length) return `<div class="strategy-missing">영업이익 추이 데이터가 공시되지 않았습니다.</div>`;
  const years = [...new Set(rows.map((row) => row.year))].sort((a, b) => a - b);
  const max = Math.max(...rows.map((row) => Math.abs(row.value)), 1);
  const hasNegative = rows.some((row) => row.value < 0);
  const yearGroups = years.map((year) => {
    const yearRows = seriesByCompany.map(({ item, series }, companyIndex) => ({ item, companyIndex, row: series.find((entry) => entry.year === year) })).filter((entry) => entry.row);
    const bars = yearRows.map(({ item, companyIndex, row }) => {
      const tone = companyIndex % 2 ? "hyn" : "sam";
      const height = row.value === 0 ? 0 : Math.max(4, Math.min(hasNegative ? 45 : 100, Math.abs(row.value) / max * (hasNegative ? 45 : 100)));
      const barPosition = hasNegative ? (row.value < 0 ? "top:50%" : "bottom:50%") : "";
      const labelPosition = hasNegative
        ? (row.value < 0 ? `top:calc(50% + ${height.toFixed(1)}% + 4px)` : `bottom:calc(50% + ${height.toFixed(1)}% + 4px)`)
        : "";
      return `<div class="strategy-profit-column ${tone}${row.estimated ? " forecast" : ""}${row.value < 0 ? " negative" : ""}${hasNegative ? " signed-axis" : ""}" title="${escapeHtml(companyName(item))} · ${row.year}${row.estimated ? "E" : ""} · ${escapeHtml(strategyChartAmount(row.value))}"><strong${labelPosition ? ` style="${labelPosition}"` : ""}>${escapeHtml(strategyChartAmount(row.value))}</strong><i style="height:${height.toFixed(1)}%;${barPosition}"></i><small>${escapeHtml(companyName(item))}</small></div>`;
    }).join("");
    return `<div class="strategy-profit-group"><div class="strategy-profit-bars">${bars}</div><span>${year}${year === Math.max(...years) && yearRows.some(({ row }) => row.estimated) ? " (E)" : ""}</span></div>`;
  }).join("");
  const legend = seriesByCompany.map(({ item }, index) => `<span><i class="strategy-dot ${index % 2 ? "hyn" : "sam"}"></i>${escapeHtml(companyName(item))}</span>`).join("");
  const axisValues = hasNegative ? [max, max * .5, 0, -max * .5, -max] : [max, max * .66, max * .33, 0];
  const axis = axisValues.map((value) => `<span>${escapeHtml(strategyChartAmount(value))}</span>`).join("");
  return `<article class="strategy-chart-card strategy-profit-panel"><div class="strategy-chart-head"><div><strong>영업이익 추이와 다음연도 전망</strong><small>실선 = DART 실제값 · 해칭 = 모델 추정</small></div><div class="strategy-chart-legend">${legend}<span><i class="strategy-dot forecast"></i>모델 추정</span></div></div><div class="strategy-profit-chart${hasNegative ? " signed-axis" : ""}" role="img" aria-label="기업별 연도별 영업이익과 다음연도 모델 추정"><div class="strategy-profit-axis">${axis}</div><div class="strategy-profit-plot${hasNegative ? " signed-axis" : ""}">${yearGroups}</div></div><div class="strategy-inline-note"><b>이익은 DART 공시 실제값부터 읽습니다.</b> ${hasNegative ? "0선을 중심으로 흑자는 위, 적자는 아래에 표시합니다. " : ""}다음연도 막대는 최근 공개 추세를 단순 연장한 모델 추정입니다.</div></article>`;
}

function renderStrategyChart(seriesByCompany, formatter, signed = formatter === fmtAmount) {
  if (formatter === fmtSalary) return renderStrategySalaryChart(seriesByCompany);
  if (formatter === fmtAmount) return renderStrategyProfitChart(seriesByCompany);
  const allValues = seriesByCompany.flatMap((item) => item.series.map((row) => Math.abs(row.value))).filter((value) => Number.isFinite(value));
  const max = Math.max(...allValues, 1);
  const requestError = seriesByCompany.find((item) => item.error)?.error;
  if (requestError) return `<div class="strategy-missing">추이 데이터 요청에 실패했습니다: ${escapeHtml(requestError)}</div>`;
  if (!seriesByCompany.some((item) => item.series.length)) return `<div class="strategy-missing">추이 데이터가 공시되지 않았습니다.</div>`;
  return `<div class="strategy-chart-list">${seriesByCompany.map(({ item, series }) => {
    if (!series.length) return `<article class="strategy-chart-card"><div class="strategy-chart-head"><strong>${escapeHtml(companyName(item))}</strong><span>데이터 없음</span></div><div class="strategy-missing compact">추이 데이터가 공시되지 않았습니다.</div></article>`;
    return `<article class="strategy-chart-card"><div class="strategy-chart-head"><strong>${escapeHtml(companyName(item))}</strong><span>실제 ${series.filter((row) => !row.estimated).length}개년${series.some((row) => row.estimated) ? " · 다음연도 전망" : " · 전망 없음"}</span></div><div class="strategy-bars">${series.map((row) => { const width = Math.max(3, Math.min(signed ? 50 : 100, Math.abs(row.value) / max * (signed ? 50 : 100))); const style = signed ? `${row.value < 0 ? "right" : "left"}:50%;width:${width}%` : `width:${width}%`; return `<div class="strategy-bar-row"><div class="strategy-bar-label"><span>${row.year}${row.estimated ? "E" : ""}</span><strong>${escapeHtml(formatter(row.value))}</strong></div><div class="strategy-bar-track${signed ? " signed" : ""}"><i class="${row.estimated ? "forecast" : "actual"}${row.value < 0 ? " negative" : ""}" style="${style}"></i></div></div>`; }).join("")}</div></article>`;
  }).join("")}</div>`;
}

function renderStrategy() {
  const valid = availableResults();
  if (!state.selected.length || !valid.length) return renderEmpty("Strategy Brief를 시작할 기업이 없습니다.", "기업을 선택하고 DART 비교를 실행하면 참고 대시보드의 보상·인력 분석이 열립니다.");
  if (state.strategyLoading) return `<div class="strategy-loading"><span class="kicker accent">STRATEGY BRIEF</span><h2>DART 인력·보상 근거를 정리하는 중입니다.</h2><p>People 추이와 에이전트 품질 검사를 함께 실행하고 있습니다.</p></div>`;

  const strategyLoadIssues = [
    state.peopleHistoryError ? `People 추이 실패: ${state.peopleHistoryError}` : "",
    state.orchestration?.status === "error" ? `결정 브리프 실패: ${state.orchestration.error || "에이전트 실행 실패"}` : "",
  ].filter(Boolean);
  const strategyLoadNotice = strategyLoadIssues.length
    ? `<div class="strategy-load-notice" role="alert"><strong>일부 HR 분석을 불러오지 못했습니다.</strong><span>${escapeHtml(strategyLoadIssues.join(" · "))}</span><small>현재 화면을 확정 판단에 사용하지 말고 잠시 후 비교를 다시 실행해 주세요.</small></div>`
    : "";

  const strategyPeople = valid.map((item) => strategyPeopleResult(item.company?.corp_code)).filter(Boolean);
  const companyCards = valid.map((item) => {
    const p = strategyPeopleResult(item.company?.corp_code);
    const employees = peopleValue(p, "employees_total");
    const operatingProfit = valueFor(item, "operating_profit");
    const profitPerEmployee = operatingProfit !== null && employees ? operatingProfit / employees : null;
    const salaryBasis = p?.people?.average_salary_basis;
    const salaryDetail = p?.error || state.peopleError
      ? "인력 공시 확인 필요"
      : averageSalaryBasisLabel(salaryBasis);
    return `<article class="strategy-company-card"><div class="strategy-company-head"><div><span class="kicker">${escapeHtml(item.company?.stock_code || item.company?.corp_code || "DART")}</span><h3>${escapeHtml(companyName(item))}</h3></div><span class="strategy-badge actual">${escapeHtml(state.year)} 실제</span></div><div class="strategy-company-metrics">${strategyCompanyMetric("영업이익", fmtAmount(operatingProfit), "DART 재무 공시", "teal")}${strategyCompanyMetric("영업이익률", fmtPercent(valueFor(item, "operating_margin")), "수익성 체력", "coral")}${strategyCompanyMetric("인당 영업이익", fmtAmount(profitPerEmployee), employees === null ? "직원 수 미공시" : `${fmtCount(employees)} 기준`, "gold")}${strategyCompanyMetric("평균 급여", fmtSalary(peopleValue(p, "average_salary")), salaryDetail, "")}</div></article>`;
  }).join("");
  const segmentDisclosure = `<article class="strategy-segment-note"><span class="kicker">SEGMENT DISCLOSURE</span><h3>사업부·반도체 세그먼트</h3><p>DART API 기본 재무 응답은 기업 전체 손익을 기준으로 합니다. 사업부별 영업이익은 이 화면에서 추정하지 않고, 사업보고서 원문 연계 확장 영역으로 남깁니다.</p></article>`;
  const operatingProfitValues = valid.map((item) => valueFor(item, "operating_profit"));
  const totalOperatingProfit = operatingProfitValues.length
    && operatingProfitValues.every((value) => value !== null)
    ? operatingProfitValues.reduce((sum, value) => sum + value, 0)
    : null;
  const flow = `<div class="strategy-flow"><div class="strategy-flow-node"><span class="kicker">DART FACT</span><strong>영업이익</strong><small>${fmtAmount(totalOperatingProfit)} · ${totalOperatingProfit === null ? "공시 데이터 없음" : "선택 기업 합산"}</small></div><span class="strategy-flow-arrow">＋</span><div class="strategy-flow-node"><span class="kicker">PEOPLE SIGNAL</span><strong>평균 급여·인당 지표</strong><small>인력 공시와 재무 공시를 나란히 비교</small></div><span class="strategy-flow-arrow">→</span><div class="strategy-flow-node muted"><span class="kicker">VALIDATION LIMIT</span><strong>성과급 연동 산식</strong><small>협약·산식은 DART API만으로 확인 불가</small></div></div>`;

  const operatingSeries = valid.map((item) => ({ item, series: strategySeries(state.history, item.company?.corp_code, "financials", "operating_profit"), error: state.historyError }));
  const salarySeries = valid.map((item) => ({ item, series: strategySeries(state.peopleHistory, item.company?.corp_code, "people", "average_salary"), error: state.peopleHistoryError }));
  const equityCards = valid.map((item) => {
    const p = strategyPeopleResult(item.company?.corp_code);
    if (state.peopleError) return `<article class="strategy-equity-card"><div class="strategy-chart-head"><strong>${escapeHtml(companyName(item))}</strong><span class="strategy-badge missing">요청 실패</span></div><div class="strategy-missing">People API 요청에 실패했습니다.</div><small>${escapeHtml(state.peopleError)}</small></article>`;
    const male = strategyGenderSummary(p, "남");
    const female = strategyGenderSummary(p, "여");
    const salaryRatio = male.salary !== null && female.salary !== null && male.salary !== 0 ? female.salary / male.salary * 100 : null;
    const tenureDelta = female.tenure !== null && male.tenure !== null ? female.tenure - male.tenure : null;
    const hasAnyDisclosure = salaryRatio !== null || tenureDelta !== null || female.headcount !== null || male.headcount !== null;
    if (!hasAnyDisclosure) return `<article class="strategy-equity-card"><div class="strategy-chart-head"><strong>${escapeHtml(companyName(item))}</strong><span class="strategy-badge missing">미공시</span></div><div class="strategy-missing">성별 급여·근속 미공시</div><small>공시되지 않은 값을 추정하거나 원인을 단정하지 않습니다.</small></article>`;
    const equityRatio = salaryRatio === null ? "" : `<div class="strategy-equity-ratio"><span>여성 급여 / 남성 급여</span><strong>${fmtPercent(salaryRatio)}</strong><div class="strategy-equity-ratio-track"><i style="width:${Math.min(100, Math.max(0, salaryRatio)).toFixed(1)}%"></i></div></div>`;
    return `<article class="strategy-equity-card"><div class="strategy-chart-head"><strong>${escapeHtml(companyName(item))}</strong><span class="strategy-badge actual">공시분</span></div><div class="strategy-equity-metrics">${strategyCompanyMetric("여성/남성 급여 비율", salaryRatio === null ? "데이터 없음" : fmtPercent(salaryRatio), salaryRatio === null ? "양쪽 성별 급여 필요" : `${fmtSalary(female.salary)} vs ${fmtSalary(male.salary)}`, "coral")}${strategyCompanyMetric("성별 근속 차이", tenureDelta === null ? "데이터 없음" : `${tenureDelta >= 0 ? "+" : ""}${fmtYears(tenureDelta)}`, "여성 - 남성", "teal")}${strategyCompanyMetric("분석 표본", `${fmtCount(female.headcount)} / ${fmtCount(male.headcount)}`, "여성 / 남성 인원", "")}</div>${equityRatio}<small>격차는 공시된 집계값의 비교이며 원인이나 공정성을 판정하지 않습니다.</small></article>`;
  }).join("");
  const placeholders = [
    ["평가 등급 분포", "직무·직급별 평가등급, 평가기간, 평가자 보정 이력", "평가 쏠림과 보정 필요 구간"],
    ["평가–보상 연동성", "평가등급, 고정·변동보상, 승진·인상 이력", "동일 조건 내 보상 결과의 일관성"],
    ["자사 Pay Equity", "직무가치, 직급, 근속, 근무형태, 보상 구성", "비교 가능한 집단의 설명 가능한 격차"],
    ["보상 인식 vs 실제", "익명 설문, 보상 원장, 제도 접점·커뮤니케이션 이력", "제도 설계와 직원 인식의 차이"],
  ].map(([title, source, decision]) => `<article class="strategy-placeholder"><span class="strategy-lock">NEEDED DATA</span><h3>${title}</h3><p><strong>요청 데이터</strong>${source}</p><small>확인 질문 · ${decision}</small></article>`).join("");
  const trace = state.orchestration?.trace || [];
  const decisionBriefs = renderStrategyDecisionBriefs(valid);
  const evidenceLedger = state.orchestration?.evidence?.ledger || [];
  const orchestrationSources = (state.orchestration?.evidence?.snapshots || []).flatMap((item) => item.source_urls || []);
  const sourceUrls = [...new Set(valid.flatMap((item) => item.source_urls || []).concat(valid.map((item) => item.source_url).filter(Boolean), strategyPeople.flatMap((item) => item.source_urls || []), orchestrationSources))].map(officialEvidenceUrl).filter(Boolean);
  const providerStatus = state.orchestration?.provider?.status || "미실행";
  const providerName = state.orchestration?.provider?.name || state.orchestration?.provider?.id || "AI provider";
  const providerResult = state.orchestration?.provider?.result;
  const providerError = state.orchestration?.provider?.error;
  const aiBrief = providerStatus === "completed" && providerResult
    ? `<section class="strategy-section strategy-ai-brief"><div class="strategy-section-heading"><span class="kicker">AI / BRIEFING</span><h3>AI HR 비교 브리핑</h3><p>${escapeHtml(providerName)}가 검증된 DART 컨텍스트만 사용해 작성했습니다.</p></div><article><pre>${renderProviderEvidenceText(providerResult)}</pre></article></section>`
    : providerStatus === "error"
      ? `<section class="strategy-section strategy-ai-brief"><div class="strategy-section-heading"><span class="kicker">AI / BRIEFING</span><h3>AI 브리핑을 만들지 못했습니다.</h3><p>${escapeHtml(providerError || "AI API 연결 상태를 확인해 주세요.")}</p></div></section>`
      : providerStatus === "not_configured"
        ? `<section class="strategy-section strategy-ai-brief"><div class="strategy-section-heading"><span class="kicker">AI / ON DEMAND</span><h3>AI 해석은 자동 실행하지 않습니다.</h3><p>탭을 여는 것만으로 API 비용이 발생하지 않습니다. 왼쪽 AI HR 브리핑에서 질문을 입력하고 ‘AI에게 질문하기’를 눌러 명시적으로 실행하세요.</p></div></section>`
        : "";
  const qualityStatus = state.orchestration?.status || "미실행";
  const evidenceSummary = state.orchestration?.evidence?.summary || {};
  const decisionGaps = state.orchestration?.decision_support?.data_gaps || [];
  const factRecords = state.orchestration?.facts?.records || [];
  const decisionGapRows = decisionGaps.slice(0, 5).map((gap) => {
    const record = factRecords.find((item) => item.observation_id === gap.observation_id);
    const company = record?.company?.corp_name || gap.observation_id;
    const details = (gap.details || []).map((detail) => strategyGapDetailLabels[detail] || String(detail).replaceAll("_", " ")).join(" · ");
    return `<div><strong>${escapeHtml(company)}</strong><span>${escapeHtml(strategyGapLabels[gap.gap_type] || gap.gap_type)}${details ? ` · ${escapeHtml(details)}` : ""}</span></div>`;
  }).join("");
  const decisionGapSummary = decisionGapRows
    ? `<div class="strategy-gap-list">${decisionGapRows}</div>`
    : `<div class="strategy-gap-list empty">판단에 영향을 주는 공시·원문 공백이 발견되지 않았습니다.</div>`;
  const policy = state.orchestration?.policy || {};
  const policyReasons = (policy.reason_codes || []).join(" · ") || "품질·개인정보·근거 게이트 통과";
  const policyModeLabels = { full: "전체", limited: "보수적 제한", none: "차단" };
  const excludedObservationCount = (policy.excluded_observations || []).length;
  const eligibleObservationCount = (policy.eligible_observation_ids || []).length;
  const decisionSupportScope = state.orchestration?.provider?.context_summary?.decision_support_status;
  const policyScopeSummary = policy.status === "blocked"
    ? policyReasons
    : excludedObservationCount
      ? `기업 ${excludedObservationCount}개 제외 · 허용 기업 ${eligibleObservationCount}개만 다시 계산해 AI에 전달`
      : policy.mode === "limited"
        ? `선택 기업 ${eligibleObservationCount}개 범위 유지 · 일부 공시 품질 경고로 AI 해석을 보수적으로 제한`
        : `선택 기업 ${eligibleObservationCount}개 근거 범위를 AI에 전달 가능`;
  const decisionSupportScopeLabel = decisionSupportScope === "limited"
    ? "제외 후 허용 범위"
    : decisionSupportScope === "available"
      ? "선택 기업 전체 범위"
      : "결정 브리프 범위 미산정";
  const runId = state.orchestration?.run_id || "미실행";
  const traceRows = trace.length ? trace.map((row) => `<div class="strategy-trace-row"><span>${escapeHtml(row.agent || "agent")}</span><strong class="${row.status === "completed" ? "status-ok" : "status-warn"}">${escapeHtml(row.status || "unknown")}</strong><small>${escapeHtml(String(row.duration_ms ?? 0))}ms</small></div>`).join("") : `<div class="strategy-missing compact">Strategy Brief 탭을 열면 에이전트 추적이 실행됩니다.</div>`;
  const evidenceLabels = { employees_total: "총 직원", average_salary: "평균 급여", annual_salary_total: "급여 총액", revenue: "매출", operating_profit: "영업이익", operating_margin: "영업이익률", revenue_per_employee: "인당 매출", operating_profit_per_employee: "인당 영업이익", salary_to_revenue: "급여/매출", contract_share: "계약직 비중", average_tenure_years: "평균 근속", term_expiring_within_12_months: "임기 만료" };
  const seenEvidenceUrls = new Set();
  const contextualEvidence = evidenceLedger.map((item) => ({ item, url: evidenceSourceUrl(item) })).filter(({ url }) => url && !seenEvidenceUrls.has(url) && seenEvidenceUrls.add(url)).slice(0, 12);
  const evidenceLinks = contextualEvidence.length
    ? contextualEvidence.map(({ item, url }) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"><strong>${escapeHtml(item.company?.corp_name || "기업")}</strong><span>${escapeHtml(evidenceLabels[item.metric_id] || item.metric_id)} · ${escapeHtml(item.year || state.year)} 원문 ↗</span></a>`).join("")
    : sourceUrls.length
      ? sourceUrls.slice(0, 8).map((url, index) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"><strong>${escapeHtml(companyName(valid[index % valid.length]))}</strong><span>재무·인력 공시 원문 ↗</span></a>`).join("")
      : `<span class="strategy-missing compact">원문 접수번호가 포함된 공시가 없습니다.</span>`;
  return `<div class="tab-panel strategy-brief"><section class="strategy-hero"><div><span class="kicker accent">이익 체력 · 보상 공시 · 급여 지표 · DART 근거</span><h2>이익 체력과 함께 읽는<br /><em>보상 대시보드</em></h2><p>참고 대시보드의 프레임을 선택 기업과 기준연도에 맞춰 재구성했습니다. 실제 공시와 모델 추정을 화면에서 분리합니다.</p></div><div class="strategy-legend"><span><i class="teal"></i>DART 실제</span><span><i class="coral"></i>보상·인력</span><span><i class="gold"></i>모델 추정</span></div></section>${strategyLoadNotice}${decisionBriefs}${aiBrief}<section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">00 / PROFIT CAPACITY</span><h3>이익 체력 — 급여를 논하기 전에</h3><p>영업이익의 크기와 직원 수·평균 급여를 같은 기업 단위에서 읽습니다.</p></div><div class="strategy-company-grid">${companyCards}</div>${segmentDisclosure}${flow}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">01 / OPERATING PROFIT</span><h3>영업이익 추이 & 다음연도 전망</h3><p>막대가 실선이면 DART 실제값, 점선이면 최근 추세를 단순 연장한 모델 추정입니다.</p></div>${renderStrategyChart(operatingSeries, fmtAmount)}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">02 / AVERAGE PAY</span><h3>평균 급여 추이 & 다음연도 전망 구간</h3><p>평균 급여는 인력 공시의 집계값이며 개인별 보상이나 성과급을 의미하지 않습니다.</p></div>${renderStrategySalaryChart(salarySeries)}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">03 / PAY EQUITY</span><h3>성별 급여·근속 격차 (공시분)</h3><p>성별 집계가 함께 공시된 경우에만 비교하며, 격차의 원인이나 공정성을 추론하지 않습니다.</p></div><div class="strategy-equity-grid">${equityCards}</div></section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">03+ / INTERNAL DIAGNOSTICS</span><h3>내부 제도 진단 — 다음 확인 데이터</h3><p>공시 데이터만으로 확정할 수 없는 질문과, 판단을 이어가기 위해 필요한 내부 데이터입니다.</p></div><div class="strategy-placeholder-grid">${placeholders}</div></section><section class="strategy-section strategy-evidence"><div class="strategy-section-heading"><span class="kicker">EVIDENCE / ORCHESTRATION</span><h3>근거와 에이전트 실행 상태</h3><p>${escapeHtml(state.year)}년 · ${escapeHtml(reportLabel(state.reportCode))} · 기업·지표가 표시된 OpenDART 원문을 확인할 수 있습니다.</p></div><div class="strategy-evidence-grid"><article class="strategy-evidence-card"><span class="kicker">SOURCE LINKS</span><div class="strategy-links">${evidenceLinks}</div></article><article class="strategy-evidence-card"><span class="kicker">QUALITY GATE</span><strong>${escapeHtml(qualityStatus)}</strong><small>근거 ${escapeHtml(String(evidenceSummary.evidence_count ?? 0))}개 · 원문 연결 ${escapeHtml(String(evidenceSummary.linked_observation_count ?? 0))}/${escapeHtml(String(evidenceSummary.observation_count ?? 0))}</small>${decisionGapSummary}<p>Run <span class="evidence-run-id">${escapeHtml(runId)}</span> · 원자료 지문과 지표 근거를 함께 검증했습니다. 정정공시 최신 여부는 별도 확인이 필요합니다.</p></article><article class="strategy-evidence-card"><span class="kicker">AI POLICY</span><strong>${escapeHtml(strategyPolicyStatusLabels[policy.status] || policy.status || "미실행")}</strong><small>${escapeHtml(policyModeLabels[policy.mode] || policy.mode || "미산정")} · ${escapeHtml(decisionSupportScopeLabel)} · ${escapeHtml(providerName)}: ${escapeHtml(providerStatus)}</small><p>${escapeHtml(policyScopeSummary)}</p></article><article class="strategy-evidence-card"><span class="kicker">TRACE</span><div class="strategy-trace">${traceRows}</div></article></div></section><p class="strategy-disclaimer">주의: 다음연도 값은 투자·인사 의사결정용 확정 전망이 아니라 최근 공시 추세를 단순 연장한 모델 추정입니다. 성과급 산식, 개인별 성과, 성별 격차의 원인은 DART API만으로 확정할 수 없습니다.</p></div>`;
}

function renderTab() {
  const content = { overview: renderOverview, compare: renderCompare, trend: renderTrendByYear, people: renderPeople, executives: renderExecutives, strategy: renderStrategy, radar: renderRadar, scatter: renderScatter, rank: renderRank }[state.activeTab]();
  $("#tabContent").innerHTML = content;
  document.body.classList.remove("strategy-mode");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta) themeMeta.setAttribute("content", document.documentElement.dataset.theme === "dark" ? "#132320" : "#f4f6f2");
  const introKicker = document.querySelector(".intro .kicker");
  const introTitle = document.querySelector(".intro h1");
  const introCopy = document.querySelector(".intro p");
  if (introKicker && introTitle && introCopy) {
    if (state.activeTab === "strategy") {
      introKicker.textContent = "DART / WORKFORCE INTELLIGENCE";
      introTitle.innerHTML = "공시 기반 인력·보상<br /><em>벤치마크를 읽으세요.</em>";
      introCopy.innerHTML = '이익 체력, 평균 급여, 임원 구조를 같은 기준으로 비교하고<br class="wide-only" /> HR 전략상 확인해야 할 근거와 한계를 함께 보여줍니다.';
    } else if (providerStatus === "rejected") {
      const fallback = buildValidatedFallback(payload);
      state.openAiProviderName = provider.name || "OpenAI API";
      state.openAiConnected = true;
      state.aiMessages.push(
        { role: "user", content: question },
        { role: "assistant", content: fallback.answer, evidence: fallback.evidence, guardedFallback: true },
      );
      $("#analysisPrompt").value = "";
      renderAiConversation();
      renderApiConnection("AI 초안이 안전 검증에서 차단되어 검증된 OpenDART 근거로 대체했습니다.");
      setMessage("AI 초안 대신 검증된 공시 근거 요약을 표시했습니다.");
    } else {
      introKicker.textContent = "DART / HR BRIEFING";
      introTitle.innerHTML = "공시 데이터를<br /><em>HR 브리핑으로.</em>";
      introCopy.innerHTML = '직원 수, 평균 급여, 근속연수와 인당 생산성을 같은 기준으로 비교하고<br class="wide-only" /> AI가 확인된 사실과 추가 검증 과제를 구분해 정리합니다.';
    }
  }
  if (state.activeTab === "strategy") {
    const title = $("#tabContent .strategy-hero h2");
    const companies = availableResults().slice(0, 2).map((item) => companyName(item));
    if (title && companies.length) {
      const line = document.createElement("div");
      line.className = "strategy-hero-companies";
      companies.forEach((name, index) => {
        if (index) {
          const versus = document.createElement("span");
          versus.className = "strategy-hero-versus";
          versus.textContent = "vs";
          line.append(versus);
        }
        const company = document.createElement("span");
        company.className = `strategy-hero-company ${index % 2 ? "hyn" : "sam"}`;
        company.textContent = name;
        line.append(company);
      });
      title.parentElement.insertBefore(line, title);
    }
  }
}

function updateReadout() {
  const valid = availableResults(); if (!valid.length) { $("#readoutText").textContent = "선택한 기업의 실제 공시 수치를 받으면 HR·재무 readout이 표시됩니다."; return; }
  if (["overview", "strategy"].includes(state.activeTab)) {
    const readiness = state.orchestration?.decision_support?.readiness || [];
    if (state.strategyLoading && !readiness.length) { $("#readoutText").textContent = "HR 비교 근거 준비도와 원문 연결률을 계산 중입니다. 공시 비교 화면은 그대로 사용할 수 있습니다."; return; }
    if (readiness.length) {
      const ready = readiness.filter((item) => item.status === "ready").length;
      const directional = readiness.filter((item) => item.status === "directional_only").length;
      const blocked = readiness.filter((item) => item.status === "blocked").length;
      const evidence = state.orchestration?.evidence?.summary || {};
      const freshnessWarning = evidence.restatement_verification === "verified_current"
        ? ""
        : " 정정공시 최신성은 아직 검증하지 않았습니다.";
      $("#readoutText").innerHTML = `<strong>HR 비교 근거 준비도</strong> ${escapeHtml(String(ready))}개 충족 · ${escapeHtml(String(directional))}개 방향성 참고 · ${escapeHtml(String(blocked))}개 근거 부족입니다. 원문 연결 근거 ${escapeHtml(String(evidence.source_complete_evidence_count ?? 0))}개를 사용합니다.${freshnessWarning} 각 결정 카드에서 다음 내부 데이터와 판단 한계를 함께 확인하세요.`;
      return;
    }
  }
  if (state.activeTab === "people") {
    const rows = (state.people || []).filter((item) => item?.people && !item.error);
    const comparable = rows.filter((item) => peopleValue(item, "employees_total") !== null && peopleValue(item, "average_salary") !== null);
    if (!comparable.length) { $("#readoutText").textContent = "직원 수와 평균 급여가 함께 공시된 기업이 없어 HR 자동 요약을 만들지 않았습니다."; return; }
    const largest = [...comparable].sort((a, b) => peopleValue(b, "employees_total") - peopleValue(a, "employees_total"))[0];
    const basisLabels = [...new Set(comparable.map((item) => item.people?.average_salary_basis).filter(Boolean))].map(averageSalaryBasisLabel);
    $("#readoutText").innerHTML = `<strong>${escapeHtml(companyName(largest))}</strong>의 공시 직원 수가 ${escapeHtml(fmtCount(peopleValue(largest, "employees_total")))}로 선택 기업 중 가장 큽니다. 평균 급여 계산 기준은 ${escapeHtml(basisLabels.join(" · ") || "원문 공시")}이며, 이는 개인별 보상이나 인력 효과의 원인을 뜻하지 않습니다.`;
    return;
  }
  if (state.activeTab === "executives") {
    const rows = (state.executives || []).filter((item) => item?.executive_metrics && !item.error);
    const expiries = rows.map((item) => numberValue(item.executive_metrics?.term_expiring_within_12_months));
    if (!rows.length || expiries.some((value) => value === null)) { $("#readoutText").textContent = "모든 선택 기업의 임기 만료 공시가 연결된 경우에만 거버넌스 요약을 만듭니다. 현재는 추가 원문 확인이 필요합니다."; return; }
    const total = expiries.reduce((sum, value) => sum + value, 0);
    $("#readoutText").innerHTML = `선택 기업에서 달력 기준 12개월 내 임기 만료 공시 인원은 합계 <strong>${escapeHtml(fmtCount(total))}</strong>입니다. 이는 승계 준비도나 개인 성과가 아니라 후속 점검 일정을 위한 대리 신호입니다.`;
    return;
  }
  const leader = (key, direction = "max") => valid.filter((item) => valueFor(item, key) !== null).sort((a, b) => (valueFor(b, key) - valueFor(a, key)) * (direction === "max" ? 1 : -1))[0];
  const marginLeader = leader("operating_margin"); const debtLeader = leader("debt_ratio", "min"); const liquidityLeader = leader("current_ratio");
  if (!marginLeader || !debtLeader || !liquidityLeader) { $("#readoutText").textContent = "영업이익률·부채비율·유동비율이 모두 공시된 지표만 비교합니다. 현재는 일부 지표가 없어 자동 요약을 만들지 않았습니다."; return; }
  $("#readoutText").innerHTML = `<strong>${escapeHtml(companyName(marginLeader))}</strong>의 영업이익률은 ${escapeHtml(metricValue(marginLeader, "operating_margin"))}, <strong>${escapeHtml(companyName(debtLeader))}</strong>의 부채비율은 ${escapeHtml(metricValue(debtLeader, "debt_ratio"))}이며, 유동비율은 <strong>${escapeHtml(companyName(liquidityLeader))}</strong>이(가) ${escapeHtml(metricValue(liquidityLeader, "current_ratio"))}로 가장 높습니다. 이는 단순 우열이 아닌 같은 공시 기준에서의 상대 비교입니다.`;
}

function updateCoverageStrip() {
  const valid = availableResults();
  const evidence = state.orchestration?.evidence?.summary;
  const readiness = state.orchestration?.decision_support?.readiness || [];
  if (evidence && readiness.length) {
    const ready = readiness.filter((item) => item.status === "ready").length;
    $("#dataCoverage").textContent = `${valid.length} / ${state.results.length}개 수신 · 근거 준비 ${ready}/${readiness.length} · 원문 ${evidence.linked_observation_count ?? 0}/${evidence.observation_count ?? 0}`;
    return;
  }
  if (state.strategyLoading) {
    $("#dataCoverage").textContent = `${valid.length} / ${state.results.length}개 수신 · 근거 준비도 계산 중 · 원문 연결 확인 중`;
    return;
  }
  $("#dataCoverage").textContent = `${valid.length} / ${state.results.length}개 기업 수신`;
}

function renderDashboard() {
  $("#dashboard").classList.remove("hidden"); $("#welcome").classList.add("hidden"); $("#dataMeta").textContent = `${state.year}년 · ${reportLabel(state.reportCode)}`; $("#headingMeta").textContent = `${state.selected.length}개 기업 · ${state.year}년 기준`; updateCoverageStrip(); renderMetricPills(); renderTab(); updateReadout();
  updateWorkshopProgress();
}

async function loadStrategyData() {
  if (!state.selected.length || !state.results.length) return;
  const key = dataSelectionKey();
  if (state.strategyLoadedFor === key && !state.strategyLoading) { renderTab(); updateCoverageStrip(); updateReadout(); return; }
  const requestToken = ++state.strategyRequestToken;
  state.strategyLoading = true;
  renderTab();
  const fromYear = Math.max(2015, Number(state.year) - 3);
  const [peopleResult, orchestrationResult] = await Promise.allSettled([
    requestPeopleHistory(state.selected, fromYear, state.year, state.reportCode),
    requestWorkforceOrchestration(state.selected, state.year, state.reportCode),
  ]);
  const currentKey = dataSelectionKey();
  if (requestToken !== state.strategyRequestToken || key !== currentKey) {
    if (requestToken === state.strategyRequestToken) state.strategyLoading = false;
    return;
  }
  state.peopleHistory = peopleResult.status === "fulfilled" ? peopleResult.value : [];
  state.orchestration = orchestrationResult.status === "fulfilled" ? orchestrationResult.value : { status: "error", provider: { status: "unavailable" }, trace: [], error: orchestrationResult.reason?.message || "에이전트 실행 실패" };
  state.peopleHistoryError = peopleResult.status === "rejected" ? peopleResult.reason?.message || "People 추이 요청 실패" : "";
  state.strategyLoadedFor = peopleResult.status === "rejected" && orchestrationResult.status === "rejected" ? "" : key;
  state.strategyLoading = false;
  if (peopleResult.status === "rejected" && orchestrationResult.status === "rejected") setMessage("Strategy Brief의 People 추이와 에이전트 결과를 불러오지 못했습니다.");
  renderTab();
  updateCoverageStrip();
  updateReadout();
  updateWorkshopProgress();
}

async function compare() {
  if (!state.selected.length) { setMessage("먼저 비교할 기업을 1개 이상 선택해 주세요."); return; }
  const button = $("#compareButton");
  const selected = state.selected.map((company) => ({ ...company }));
  const year = $("#yearSelect").value;
  const reportCode = $("#reportSelect").value;
  const requestKey = dataSelectionKey(selected, year, reportCode);
  const requestToken = ++state.compareRequestToken;
  resetAiConversationForContextChange();
  button.dataset.requestToken = String(requestToken); button.disabled = true; button.querySelector("span").textContent = "공시 데이터 불러오는 중"; setMessage(""); state.strategyRequestToken += 1; state.strategyLoading = false;
  try {
    const [currentResult, previousResult, peopleResult] = await Promise.allSettled([
      requestAll(selected, year, reportCode),
      requestAll(selected, String(Number(year) - 1), reportCode),
      requestPeople(selected, year, reportCode),
    ]);
    const currentInputKey = dataSelectionKey(state.selected, $("#yearSelect").value, $("#reportSelect").value);
    if (requestToken !== state.compareRequestToken || requestKey !== currentInputKey) {
      setMessage("비교 조건이 바뀌어 이전 응답을 폐기했습니다. 다시 비교를 실행해 주세요.");
      return;
    }
    if (currentResult.status !== "fulfilled" || previousResult.status !== "fulfilled") throw new Error("재무 공시 데이터를 불러오지 못했습니다.");
    const nextResults = currentResult.value;
    const nextPrevious = previousResult.value;
    const nextPeople = peopleResult.status === "fulfilled" ? peopleResult.value : [];
    const nextPeopleError = peopleResult.status === "rejected" ? peopleResult.reason?.message || "People 요청 실패" : "";
    const nextHistoryFromYear = String(Math.max(2015, Number(year) - 5));
    const nextHistoryToYear = year;
    let nextHistory = [];
    let nextHistoryError = "";
    try { nextHistory = await requestHistory(selected, nextHistoryFromYear, nextHistoryToYear, reportCode); } catch (error) { nextHistoryError = error.message || "재무 추이 요청 실패"; }
    if (requestToken !== state.compareRequestToken || requestKey !== dataSelectionKey(state.selected, $("#yearSelect").value, $("#reportSelect").value)) {
      setMessage("비교 조건이 바뀌어 이전 추이 응답을 폐기했습니다. 다시 비교를 실행해 주세요.");
      return;
    }
    state.year = year;
    state.reportCode = reportCode;
    state.results = nextResults;
    state.previous = nextPrevious;
    state.people = nextPeople;
    state.executives = executivesFromPeople(nextPeople);
    state.peopleError = nextPeopleError;
    state.executivesError = nextPeopleError;
    state.history = nextHistory;
    state.historyError = nextHistoryError;
    state.peopleHistory = [];
    state.peopleHistoryError = "";
    state.orchestration = null;
    state.strategyLoadedFor = "";
    state.strategyLoading = true;
    state.historyFromYear = nextHistoryFromYear;
    state.historyToYear = nextHistoryToYear;
    renderDashboard();
    loadStrategyData();
    $("#dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  catch (error) { setMessage(error.message || "인력·보상 데이터를 불러오지 못했습니다."); }
  finally { if (button.dataset.requestToken === String(requestToken)) { button.disabled = false; button.querySelector("span").textContent = "인력·보상 비교"; } }
}

function buildPeopleContext() {
  return (state.people || []).filter((item) => item?.people && !item.error).map((item) => {
    const p = people(item); const f = financials(resultFor(item.company?.corp_code)); const employees = peopleValue(item, "employees_total"); const revenuePerEmployee = employees && numberValue(f.revenue) !== null ? f.revenue / employees : null; const regularShare = employees && peopleValue(item, "regular_employees") !== null ? peopleValue(item, "regular_employees") / employees * 100 : null;
    return `${companyName(item)} | 총 직원 ${fmtCount(employees)} | 정규직 비중 ${fmtPercent(regularShare)} | 계약직 ${fmtCount(peopleValue(item, "contract_employees"))} | 평균 근속 ${fmtYears(peopleValue(item, "average_tenure_years"))} | 1인 평균 급여 ${fmtSalary(peopleValue(item, "average_salary"))} | 평균 급여 계산 기준 ${averageSalaryBasisLabel(item.people?.average_salary_basis)} | 임원 ${fmtCount(peopleValue(item, "executives_total"))} | 미등기임원 평균 급여 ${fmtSalary(peopleValue(item, "unregistered_average_salary"))} | 매출/인 ${fmtAmount(revenuePerEmployee)}`;
  }).join("\n");
}

function buildPeopleHistoryContext() {
  return (state.peopleHistory || []).flatMap((item) => (item.years || []).filter((year) => year?.people && !year.error).map((year) => {
    return `${companyName(item)} | 연도 ${year.year} | 총 직원 ${fmtCount(peopleValue(year, "employees_total"))} | 평균 급여 ${fmtSalary(peopleValue(year, "average_salary"))} | 평균 근속 ${fmtYears(peopleValue(year, "average_tenure_years"))}`;
  })).join("\n");
}

function buildPrompt() {
  const question = redactCredentialText($("#analysisPrompt").value.trim()) || DEFAULT_HR_ANALYSIS_QUESTION; const rows = state.results.filter((item) => !item.error).map((item) => { const f = financials(item); return `${companyName(item)} | 자산 ${fmtAmount(f.assets)} | 부채 ${fmtAmount(f.liabilities)} | 자본 ${fmtAmount(f.equity)} | 현금 ${fmtAmount(f.cash)} | 매출 ${fmtAmount(f.revenue)} | 영업이익 ${fmtAmount(f.operating_profit)} | 영업이익률 ${fmtPercent(f.operating_margin)} | 부채비율 ${fmtPercent(f.debt_ratio)} | 유동비율 ${fmtRatio(f.current_ratio)}`; }).join("\n"); const peopleRows = buildPeopleContext(); return `다음 OpenDART 공시 수치를 근거로 기업 재무구조와 People Analytics 관점을 비교해줘.\n\n[기준]\n연도: ${state.year || "미선택"} / 보고서: ${reportLabel(state.reportCode)} / 금액 단위: 억 원\n\n[기업별 재무 수치]\n${rows || "수치 없음"}\n\n[기업별 People Analytics 수치]\n${peopleRows || "직원·임원 공시 수치 없음"}\n\n[사용자 질문]\n${question}\n\n[답변 규칙]\n1. 먼저 질문에 대한 결론을 간단히 말해줘.\n2. 재무 구조와 인력·보상 구조를 기업별로 분리해 비교해줘.\n3. 직원 수, 정규직 비중, 근속, 급여, 임원 수, 매출/인을 HR 전략의 참고지표로 해석해줘.\n4. 공시 누락, 회계정책 차이, 집계 데이터의 한계를 구분하고 인과관계나 개인별 성과를 단정하지 마.\n5. 실행 가능한 HR 전략은 가설·추가 검증 데이터·예상 지표(KPI)로 나눠 제시해줘.\n6. 투자 매수·매도 추천은 하지 말고 수치와 해석을 분리해줘.`; }

async function fetchStructuredHandoff() {
  const question = redactCredentialText($("#analysisPrompt").value.trim())
    || DEFAULT_HR_ANALYSIS_QUESTION;
  const response = await fetch("/api/analysis/context", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      view: state.activeTab,
      corp_codes: state.selected.map((company) => company.corp_code),
      year: state.year,
      report_code: state.reportCode,
      metric_ids: state.selectedMetrics,
      page: 1,
      page_size: 40,
    }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "서버 분석 컨텍스트를 만들지 못했습니다.");
  return payload.prompt || payload.prompt_handoff?.prompt || buildPrompt();
}

async function runAiAnalysis() {
  const button = $("#runAiButton");
  const resultBox = $("#aiResult");
  if (!state.selected.length) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = "먼저 비교할 기업을 선택해 주세요.";
    return;
  }
  const selectedYear = $("#yearSelect").value;
  const selectedReportCode = $("#reportSelect").value;
  if (
    state.results.length
    && (state.year !== selectedYear || state.reportCode !== selectedReportCode)
  ) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = "기준연도 또는 보고서가 바뀌었습니다. 먼저 인력·보상 비교를 다시 실행해 주세요.";
    return;
  }
  if (!state.results.length) {
    state.year = selectedYear;
    state.reportCode = selectedReportCode;
  }
  const inputKey = $("#openAiApiKey").value.trim();
  const apiKey = inputKey || state.openAiKey;
  if (!apiKey) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = "위에 OpenAI API Key를 입력해 주세요.";
    $("#openAiApiKey").focus();
    return;
  }
  if (!/^sk-[A-Za-z0-9_-]{4,509}$/.test(apiKey)) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = "sk-로 시작하는 OpenAI API Key를 확인해 주세요.";
    $("#openAiApiKey").focus();
    return;
  }
  const questionInput = $("#analysisPrompt");
  const rawQuestion = questionInput.value.trim();
  const question = redactCredentialText(rawQuestion);
  if (question !== rawQuestion) questionInput.value = question;
  if (!question) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = "AI에게 물어볼 내용을 입력해 주세요.";
    $("#analysisPrompt").focus();
    return;
  }
  const previouslyConnected = state.openAiConnected && state.openAiKey === apiKey;
  state.openAiKey = apiKey;
  state.openAiConnected = previouslyConnected;
  state.strategyLoadedFor = "";
  const requestToken = ++state.aiRequestToken;
  const requestKey = aiContextKey();
  const abortController = new AbortController();
  state.aiAbortController = abortController;
  renderApiConnection("OpenAI에 질문을 보내는 중입니다.");
  button.disabled = true;
  button.textContent = "답변 생성 중…";
  renderAiConversation(question);
  try {
    const response = await fetch("/api/analysis", {
      method: "POST",
      signal: abortController.signal,
      headers: aiRequestHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        question: conversationQuestion(question),
        view: state.activeTab,
        corp_codes: state.selected.map((company) => company.corp_code),
        year: state.year,
        report_code: state.reportCode,
        metric_ids: state.selectedMetrics,
        page: 1,
        page_size: 40,
      }),
    });
    const payload = await response.json();
    if (requestToken !== state.aiRequestToken || requestKey !== aiContextKey()) {
      setMessage("분석 기준이 바뀌어 이전 AI 응답을 폐기했습니다.");
      renderApiConnection();
      return;
    }
    if (!response.ok) throw new Error(payload.error || "AI 분석 요청에 실패했습니다.");
    const provider = payload.provider || {};
    const providerStatus = provider.status || payload.provider_status || "not_configured";
    const providerResult = provider.result ?? payload.provider_result;
    const providerPrompt = provider.prompt || payload.prompt || payload.prompt_handoff?.prompt || "";
    if (providerStatus === "completed" && providerResult !== null && providerResult !== undefined) {
      const answer = typeof providerResult === "string" ? providerResult : JSON.stringify(providerResult, null, 2);
      state.openAiProviderName = provider.name || "OpenAI API";
      state.openAiConnected = true;
      state.aiMessages.push(
        { role: "user", content: question },
        { role: "assistant", content: answer, evidence: payload.evidence?.ledger || [] },
      );
      $("#analysisPrompt").value = "";
      renderAiConversation();
      renderApiConnection();
    } else {
      const providerName = provider.name || provider.id || "AI provider";
      const providerError = provider.error || payload.prompt_handoff?.error || `${providerName} 상태: ${providerStatus}`;
      throw new Error(providerError || providerPrompt || "AI가 답변을 반환하지 않았습니다.");
    }
  } catch (error) {
    if (requestToken !== state.aiRequestToken || requestKey !== aiContextKey()) {
      renderApiConnection();
      return;
    }
    const errorMessage = error.message || "AI 분석을 실행하지 못했습니다.";
    if (/401|api key|authentication|incorrect/i.test(errorMessage)) {
      state.openAiConnected = false;
      state.openAiKey = "";
    }
    state.aiMessages.push({ role: "user", content: question }, { role: "assistant", content: `오류: ${errorMessage}` });
    renderAiConversation();
    resultBox.dataset.state = "warning";
    renderApiConnection(errorMessage, true);
  } finally {
    if (requestToken === state.aiRequestToken) {
      state.aiAbortController = null;
      button.disabled = false;
      button.textContent = "AI에게 질문하기 ↗";
    }
  }
}

async function copyPrompt() {
  try {
    const prompt = state.selected.length ? await fetchStructuredHandoff() : buildPrompt();
    await navigator.clipboard.writeText(prompt);
    setMessage("서버 오케스트레이터가 만든 분석 프롬프트를 클립보드에 복사했습니다.");
  } catch (error) {
    try {
      await navigator.clipboard.writeText(buildPrompt());
      setMessage("OpenDART 재조회가 실패해 현재 화면의 구조화 프롬프트를 복사했습니다.");
    } catch {
      setMessage(error.message || "클립보드 복사에 실패했습니다. 브라우저 권한을 확인해 주세요.");
    }
  }
}
function csvCell(value) {
  const raw = String(value ?? "");
  const safe = typeof value === "string" && /^[\t\r\n ]*[=+\-@]/.test(raw)
    ? `'${raw}`
    : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}
function exportCsv() { if (!state.results.length) { setMessage("먼저 재무구조 비교를 실행해 주세요."); return; } const header = ["기준연도", "보고서", "기업명", "종목코드", ...allMetricKeys.map((key) => metricDefs[key].label)]; const rows = state.results.map((item) => [state.year, reportLabel(state.reportCode), companyName(item), item.company?.stock_code || "", ...allMetricKeys.map((key) => valueFor(item, key) ?? "")]); const csv = "\uFEFF" + [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n"); const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); link.download = `dart-financial-structure-${state.year || "export"}.csv`; link.click(); URL.revokeObjectURL(link.href); }

function activateTab(button, focus = false) {
  if (!button?.dataset.tab) return;
  if (state.activeTab !== button.dataset.tab) resetAiConversationForContextChange();
  state.activeTab = button.dataset.tab;
  $("#tabContent").setAttribute("aria-labelledby", button.id);
  $("#tabs").querySelectorAll("[role=tab]").forEach((tab) => {
    const active = tab === button;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  if (focus) button.focus();
  renderTab();
  updateCoverageStrip();
  updateReadout();
  if (state.activeTab === "strategy") loadStrategyData();
  updateWorkshopProgress();
}

function initializeTabs() {
  const tabs = [...$("#tabs").querySelectorAll("[role=tab]")];
  tabs.forEach((tab) => { tab.id = `analysis-tab-${tab.dataset.tab}`; });
  const active = tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
  if (active) $("#tabContent").setAttribute("aria-labelledby", active.id);
}

$("#compareButton").addEventListener("click", compare); $("#runAiButton").addEventListener("click", runAiAnalysis); $("#clearAiButton").addEventListener("click", clearAiConversation); $("#copyPromptButton").addEventListener("click", copyPrompt); $("#readoutCopyButton").addEventListener("click", copyPrompt); $("#exportButton").addEventListener("click", exportCsv); $("#toggleApiKey").addEventListener("click", () => { const input = $("#openAiApiKey"); const reveal = input.type === "password"; input.type = reveal ? "text" : "password"; $("#toggleApiKey").textContent = reveal ? "숨김" : "보기"; $("#toggleApiKey").setAttribute("aria-pressed", String(reveal)); }); $("#analysisPrompt").addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) runAiAnalysis(); }); document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => { $("#analysisPrompt").value = button.dataset.question || ""; $("#analysisPrompt").focus(); setMessage("예시 질문을 불러왔습니다. 기업 비교 후 AI에게 질문해 보세요."); })); $("#yearSelect").addEventListener("change", () => invalidatePeriodRequests("기준연도가 바뀌었습니다. 다시 비교를 실행해 주세요.")); $("#reportSelect").addEventListener("change", () => invalidatePeriodRequests("보고서가 바뀌었습니다. 다시 비교를 실행해 주세요.")); $("#clearMetricsButton").addEventListener("click", () => { state.selectedMetrics = ["assets", "liabilities", "equity", "cash", "revenue", "operating_profit", "operating_margin", "debt_ratio", "current_ratio"]; state.strategyLoadedFor = ""; resetAiConversationForContextChange(); renderMetricPills(); renderTab(); }); $("#tabs").addEventListener("click", (event) => activateTab(event.target.closest("[data-tab]"))); $("#tabs").addEventListener("keydown", (event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; const tabs = [...$("#tabs").querySelectorAll("[role=tab]")]; const current = tabs.indexOf(event.target.closest("[role=tab]")); if (current < 0) return; event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length; activateTab(tabs[next], true); }); $("#themeToggle").addEventListener("click", () => { const dark = document.documentElement.dataset.theme === "dark"; document.documentElement.dataset.theme = dark ? "" : "dark"; safeStorageSet("dart-theme", dark ? "light" : "dark"); });

initializeTabs(); setupYears(); renderSelected(); renderApiConnection(); if (safeStorageGet("dart-theme") === "dark") document.documentElement.dataset.theme = "dark";
fetch("/api/health").then(async (response) => {
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "서버 상태를 확인하지 못했습니다.");
  if (payload?.app?.id !== EXPECTED_APP_ID) throw new Error("현재 주소가 DART HR Briefing 서버가 아닙니다.");
  return payload;
}).then((payload) => {
  state.appIdentity = payload.app;
  state.dartApiReady = Boolean(payload.api_key_configured);
  const buildInfo = $("#appBuildInfo");
  buildInfo.textContent = `v${payload.app.version || "?"} · ${payload.app.build_id || "빌드 미상"} · port ${payload.app.port || location.port}`;
  buildInfo.title = `인스턴스 ${payload.app.instance_id || "미상"}`;
  renderApiConnection();
}).catch((error) => {
  state.dartApiReady = false;
  state.appIdentity = null;
  const buildInfo = $("#appBuildInfo");
  buildInfo.textContent = error.message || "서버 식별 실패";
  const status = $("#apiStatus");
  status.classList.add("error");
  status.innerHTML = "<i></i> 서버 연결 필요";
});
