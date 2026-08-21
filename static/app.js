const MAX_COMPANIES = 8;

const state = {
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
const escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const companyName = (item) => item?.company?.corp_name || "알 수 없음";
const numberValue = (value) => value === null || value === undefined || value === "" || Number.isNaN(Number(value)) ? null : Number(value);
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

function setMessage(text = "") { $("#message").textContent = text; }
function financials(item) { return item?.financials || {}; }
function valueFor(item, key) { return numberValue(financials(item)[key]); }
function people(item) { return item?.people || {}; }
function peopleValue(item, key) { return numberValue(people(item)[key]); }
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

function renderSelected() {
  $("#selectionCount").textContent = `${state.selected.length} / ${MAX_COMPANIES}`;
  if (!state.selected.length) {
    $("#selectedChips").innerHTML = '<div class="empty-rail"><span class="empty-rail-icon">＋</span><p>기업을 검색해<br>비교 목록에 추가하세요.</p><small>최대 8개 · DART 공시 기준</small></div>';
    return;
  }
  $("#selectedChips").innerHTML = state.selected.map((company, index) => `<div class="company-row"><span class="company-avatar">${escapeHtml((company.corp_name || "?").slice(0, 1))}</span><span class="company-info"><strong title="${escapeHtml(company.corp_name)}">${escapeHtml(company.corp_name)}</strong><small>${escapeHtml(company.stock_code || company.corp_code)}</small></span><button class="remove-company" data-remove="${index}" type="button" aria-label="${escapeHtml(company.corp_name)} 제거">×</button></div>`).join("");
  $("#selectedChips").querySelectorAll("[data-remove]").forEach((button) => button.addEventListener("click", () => { state.selected.splice(Number(button.dataset.remove), 1); renderSelected(); }));
}

function addCompany(company) {
  if (!company || state.selected.some((item) => item.corp_code === company.corp_code)) { $("#companySearch").value = ""; $("#searchResults").innerHTML = ""; return; }
  if (state.selected.length >= MAX_COMPANIES) { setMessage(`비교 기업은 최대 ${MAX_COMPANIES}개까지 선택할 수 있습니다.`); return; }
  state.selected.push(company); $("#companySearch").value = ""; $("#searchResults").innerHTML = ""; setMessage(""); renderSelected();
}

function renderSearchResults(companies) {
  const container = $("#searchResults");
  if (!companies.length) { container.innerHTML = '<div class="result-empty">검색 결과가 없습니다.</div>'; return; }
  container.innerHTML = companies.map((company, index) => `<button class="result-item" type="button" data-result="${index}"><strong>${escapeHtml(company.corp_name)}</strong><small>${escapeHtml(company.stock_code || company.corp_code)}</small></button>`).join("");
  container.querySelectorAll("[data-result]").forEach((button) => button.addEventListener("click", () => addCompany(companies[Number(button.dataset.result)])));
}

let searchTimer;
$("#companySearch").addEventListener("input", (event) => {
  clearTimeout(searchTimer); const query = event.target.value.trim();
  if (!query) { $("#searchResults").innerHTML = ""; return; }
  searchTimer = setTimeout(async () => {
    try { const response = await fetch(`/api/companies?q=${encodeURIComponent(query)}`); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "기업 검색에 실패했습니다."); renderSearchResults(payload.companies || []); }
    catch (error) { setMessage(error.message); }
  }, 250);
});
document.addEventListener("click", (event) => { if (!event.target.closest(".search-wrap") && !event.target.closest("#searchResults")) $("#searchResults").innerHTML = ""; });

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

async function requestExecutives(companies, year, reportCode) {
  const query = new URLSearchParams({
    corp_codes: companies.map((item) => item.corp_code).join(","),
    year: String(year),
    report_code: reportCode,
  });
  const response = await fetch(`/api/executives?${query}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "임원 데이터를 불러오지 못했습니다.");
  return payload.results || [];
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
    renderMetricPills(); renderTab();
  }));
}

function availableResults() { return state.results.filter((item) => financials(item) && !item.error); }
function renderEmpty(title, detail) { return `<div class="empty-state"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div></div>`; }

function renderKpis() {
  const valid = availableResults();
  if (!valid.length) return renderEmpty("표시할 재무 데이터가 없습니다.", "선택한 기업에 해당 연도·보고서의 공시 데이터가 없거나 OpenDART 응답을 확인할 수 없습니다.");
  const best = (key, direction = "max") => [...valid].sort((a, b) => ((valueFor(b, key) ?? (direction === "max" ? -Infinity : Infinity)) - (valueFor(a, key) ?? (direction === "max" ? -Infinity : Infinity))) * (direction === "max" ? 1 : -1))[0];
  const highestMargin = best("operating_margin"); const lowestDebt = best("debt_ratio", "min"); const highestCash = best("cash");
  const cards = [["비교 기업", `${valid.length}개`, `${state.results.length - valid.length ? `${state.results.length - valid.length}개 데이터 없음` : "모든 선택 기업 수신"}`], ["영업이익률 최고", highestMargin ? metricValue(highestMargin, "operating_margin") : "—", companyName(highestMargin)], ["부채비율 최저", lowestDebt ? metricValue(lowestDebt, "debt_ratio") : "—", companyName(lowestDebt)], ["현금 규모 최고", highestCash ? metricValue(highestCash, "cash") : "—", companyName(highestCash)]];
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

function renderOverview() {
  if (!state.results.length) return renderEmpty("비교할 기업이 없습니다.", "왼쪽에서 기업을 선택한 뒤 재무구조 비교를 눌러주세요.");
  return `<div class="tab-panel">${renderKpis()}<div class="visual-grid">${renderBars("assets", "자산 규모", "억 원")}${renderBars("operating_margin", "영업이익률", "%")}</div>${renderTable()}</div>`;
}

function renderCompare() { return `<div class="tab-panel">${renderTable()}<div class="table-panel" style="margin-top:15px">${renderBars("debt_ratio", "부채비율", "%")}</div></div>`; }

function renderTrend() {
  const valid = state.results.filter((item) => valueFor(item, "revenue") !== null || valueFor(item, "operating_profit") !== null); if (!valid.length) return renderEmpty("전년 데이터가 없습니다.", "현재 연도와 전년도의 OpenDART 응답을 함께 받을 수 있어야 추세를 그릴 수 있습니다.");
  const max = Math.max(...valid.flatMap((item) => [valueFor(item, "revenue"), valueFor(resultFor(item.company.corp_code, state.previous), "revenue")]).filter((value) => value !== null).map(Math.abs), 1); const width = 620; const height = 235; const step = valid.length > 1 ? width / (valid.length - 1) : width / 2;
  const line = (key, source, color, offset = 0) => valid.map((item, index) => { const value = valueFor(resultFor(item.company.corp_code, source), key); if (value === null) return ""; const x = valid.length === 1 ? width / 2 : index * step; const y = height - (Math.abs(value) / max * 180) - 12 + offset; return `${index === 0 ? "M" : "L"} ${x} ${y}`; }).join(" ");
  const points = valid.map((item, index) => { const current = valueFor(item, "revenue"); const previous = valueFor(resultFor(item.company.corp_code, state.previous), "revenue"); const x = valid.length === 1 ? width / 2 : index * step; const currentY = current === null ? 0 : height - (Math.abs(current) / max * 180) - 12; const previousY = previous === null ? 0 : height - (Math.abs(previous) / max * 180) - 12 + 5; return `<g><circle cx="${x}" cy="${currentY}" r="4" fill="var(--teal)"/><circle cx="${x}" cy="${previousY}" r="3" fill="var(--coral)"/><text x="${x}" y="${height + 15}" text-anchor="middle" fill="var(--muted)" font-size="10">${escapeHtml(companyName(item).slice(0, 7))}</text></g>`; }).join("");
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
  const sum = (key) => valid.reduce((total, item) => total + (peopleValue(item, key) || 0), 0);
  const weightedAverage = (key, weightKey = "employees_total") => {
    const rows = valid.map((item) => ({ value: peopleValue(item, key), weight: peopleValue(item, weightKey) })).filter((row) => row.value !== null && row.weight);
    const weight = rows.reduce((total, row) => total + row.weight, 0);
    return weight ? rows.reduce((total, row) => total + row.value * row.weight, 0) / weight : null;
  };
  const totalEmployees = sum("employees_total");
  const regularShare = totalEmployees ? sum("regular_employees") / totalEmployees * 100 : null;
  const totalExecutives = sum("executives_total");
  const cards = [
    ["총 직원 수", fmtCount(totalEmployees), `${valid.length}개 기업 합산`],
    ["정규직 비중", fmtPercent(regularShare), "정규직 ÷ 총 직원"],
    ["평균 근속", fmtYears(weightedAverage("average_tenure_years")), "직원 수 가중 평균"],
    ["1인 평균 급여", fmtSalary(weightedAverage("average_salary")), "직원 수 가중 평균"],
    ["임원 수", fmtCount(totalExecutives), "등기·미등기 포함 공시 행"],
  ];
  const rows = state.people.map((item) => {
    const p = people(item);
    const f = financials(resultFor(item.company?.corp_code));
    const employees = peopleValue(item, "employees_total");
    const revenuePerEmployee = employees && numberValue(f.revenue) !== null ? f.revenue / employees : null;
    const regular = peopleValue(item, "regular_employees");
    const regularShare = regular !== null && employees ? regular / employees * 100 : null;
    return `<tr><td><strong>${escapeHtml(companyName(item))}</strong><br><small>${escapeHtml(item.company?.stock_code || item.company?.corp_code || "")}</small></td><td class="number ${employees === null ? "na" : ""}">${escapeHtml(fmtCount(employees))}</td><td class="number ${regular === null ? "na" : ""}">${escapeHtml(fmtCount(regular))}</td><td class="number ${peopleValue(item, "contract_employees") === null ? "na" : ""}">${escapeHtml(fmtCount(peopleValue(item, "contract_employees")))}</td><td class="number ${regularShare === null ? "na" : ""}">${escapeHtml(fmtPercent(regularShare))}</td><td class="number ${peopleValue(item, "average_tenure_years") === null ? "na" : ""}">${escapeHtml(fmtYears(peopleValue(item, "average_tenure_years")))}</td><td class="number ${peopleValue(item, "average_salary") === null ? "na" : ""}">${escapeHtml(fmtSalary(peopleValue(item, "average_salary")))}</td><td class="number ${peopleValue(item, "executives_total") === null ? "na" : ""}">${escapeHtml(fmtCount(peopleValue(item, "executives_total")))}</td><td class="number ${peopleValue(item, "unregistered_average_salary") === null ? "na" : ""}">${escapeHtml(fmtSalary(peopleValue(item, "unregistered_average_salary")))}</td><td class="number ${revenuePerEmployee === null ? "na" : ""}">${escapeHtml(fmtAmount(revenuePerEmployee))}</td></tr>`;
  }).join("");
  const sourceModes = [...new Set(valid.map((item) => item.people?.employee_aggregation).filter(Boolean))].map((mode) => mode === "gender_total" ? "성별합계 우선 집계" : "반환 행 전체 대체 집계");
  return `<div class="tab-panel people-layout"><div class="kpi-grid people-kpi-grid">${cards.map(([label, value, sub]) => `<div class="kpi"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(sub)}</small></div>`).join("")}</div><article class="panel"><div class="panel-title"><div><span class="kicker">PEOPLE ANALYTICS SNAPSHOT</span><h3>인력·보상 구조 비교</h3></div><span>${state.year}년 · ${reportLabel(state.reportCode)}</span></div><div class="table-scroll"><table class="data-table people-table"><thead><tr><th>기업</th><th>총 직원</th><th>정규직</th><th>계약직</th><th>정규직 비중</th><th>평균 근속</th><th>1인 평균 급여</th><th>임원 수</th><th>미등기임원 평균 급여</th><th>매출/인</th></tr></thead><tbody>${rows}</tbody></table></div></article><article class="people-note panel"><div><span class="kicker">STRATEGY READOUT</span><h3>HR 전략에 활용하는 방법</h3></div><p>직원 수·정규직 비중·근속·급여를 재무 규모와 함께 보면 인력 구조가 사업 성과를 얼마나 지지하는지 비교할 수 있습니다. <strong>매출/인</strong>은 생산성의 참고지표이고, 채용·보상·조직개편의 원인을 단정하는 지표는 아닙니다.</p><small>집계 방식: ${escapeHtml(sourceModes.join(" · ") || "원문 행 기준")} · DART 공시에는 개인별 성과·이직·몰입·역량 데이터가 포함되지 않습니다.</small></article></div>`;
}

function renderExecutives() {
  const valid = (state.executives || []).filter((item) => item?.executive_metrics && item.quality?.status !== "no_data" && !item.error);
  if (state.executivesError) return renderEmpty("임원 API 요청에 실패했습니다.", state.executivesError);
  if (!valid.length) return renderEmpty("임원 데이터가 없습니다.", "선택한 기업의 임원 현황 공시가 없거나 해당 보고서에서 제공되지 않습니다.");
  const metrics = (item) => item.executive_metrics || {};
  const sum = (key) => valid.reduce((total, item) => total + (numberValue(metrics(item)[key]) || 0), 0);
  const average = (key) => {
    const values = valid.map((item) => numberValue(metrics(item)[key])).filter((value) => value !== null);
    return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
  };
  const cards = [
    ["전체 임원", fmtCount(sum("executives_total")), `${valid.length}개 기업 합산`],
    ["사외이사 비율", fmtPercent(average("outside_director_share")), "등기임원 기준 참고지표"],
    ["여성 임원 비율", fmtPercent(average("female_share")), "전체 임원 기준"],
    ["평균 재직기간", `${Math.round(average("average_tenure_months") || 0).toLocaleString("ko-KR")}개월`, "공시 재직기간 평균"],
    ["12개월 이내 임기 만료", fmtCount(sum("term_expiring_within_12_months")), "기준일 이후 366일"],
  ];
  const rows = valid.map((item) => {
    const p = metrics(item);
    const value = (key) => numberValue(p[key]);
    return `<tr><td><strong>${escapeHtml(companyName(item))}</strong><br /><small>${escapeHtml(item.company?.stock_code || item.company?.corp_code || "")}</small></td><td class="number">${escapeHtml(fmtCount(value("executives_total")))}</td><td class="number">${escapeHtml(fmtCount(value("registered_executives")))}</td><td class="number">${escapeHtml(fmtCount(value("outside_directors")))}</td><td class="number">${escapeHtml(fmtCount(value("ceo_count")))}</td><td class="number">${escapeHtml(fmtPercent(value("female_share")))}</td><td class="number">${escapeHtml(value("average_tenure_months") === null ? "데이터 없음" : `${Math.round(value("average_tenure_months")).toLocaleString("ko-KR")}개월`)}</td><td class="number">${escapeHtml(fmtCount(value("term_expiring_within_12_months")))}</td></tr>`;
  }).join("");
  const qualityNotes = [...new Set(valid.flatMap((item) => (item.quality?.warnings || [])))];
  return `<div class="tab-panel people-layout"><div class="kpi-grid people-kpi-grid">${cards.map(([label, value, sub]) => `<div class="kpi"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(sub)}</small></div>`).join("")}</div><article class="panel"><div class="panel-title"><div><span class="kicker">EXECUTIVE STRUCTURE</span><h3>임원·이사회 구조 비교</h3></div><span>${state.year}년 · ${reportLabel(state.reportCode)}</span></div><div class="table-scroll"><table class="data-table people-table"><thead><tr><th>기업</th><th>전체 임원</th><th>등기임원</th><th>사외이사</th><th>대표이사</th><th>여성 임원 비율</th><th>평균 재직기간</th><th>12개월 이내 만료</th></tr></thead><tbody>${rows}</tbody></table></div></article><article class="people-note panel"><div><span class="kicker">TENURE & SUCCESSION</span><h3>승계 관점의 참고지표</h3></div><p>임기 만료 예정자 수와 평균 재직기간은 이사회·경영진 변화 가능성을 확인하는 출발점입니다. 승계 리스크나 조직문화의 원인을 단정하지 않고 후속 공시와 내부 검토가 필요합니다.</p><small>${escapeHtml(qualityNotes.length ? `데이터 주의: ${qualityNotes.join(" · ")}` : "개인별 임원 원자료는 화면에 노출하지 않습니다.")}</small></article></div>`;
}

function normalized(item, key) { const values = availableResults().map((row) => valueFor(row, key)).filter((value) => value !== null); const value = valueFor(item, key); if (value === null || !values.length) return 0; const max = Math.max(...values); const min = Math.min(...values); return max === min ? 70 : 20 + ((value - min) / (max - min)) * 70; }

function renderRadar() {
  const keys = ["operating_margin", "current_ratio", "debt_ratio", "cash", "equity"]; const valid = availableResults(); if (!valid.length) return renderEmpty("레이더를 그릴 데이터가 없습니다.", "재무지표가 하나 이상 수신된 기업이 필요합니다."); const center = 175; const radius = 120; const point = (index, value) => { const angle = -Math.PI / 2 + index * (Math.PI * 2 / keys.length); const r = radius * (value / 100); return `${center + Math.cos(angle) * r},${center + Math.sin(angle) * r}`; }; const grid = [25, 50, 75, 100].map((scale) => `<polygon points="${keys.map((_, i) => point(i, scale)).join(" ")}" fill="none" stroke="var(--line)" stroke-width="1"/>`).join(""); const axes = keys.map((key, i) => { const angle = -Math.PI / 2 + i * (Math.PI * 2 / keys.length); const x = center + Math.cos(angle) * radius; const y = center + Math.sin(angle) * radius; return `<line x1="${center}" y1="${center}" x2="${x}" y2="${y}" stroke="var(--line)"/><text x="${center + Math.cos(angle) * (radius + 22)}" y="${center + Math.sin(angle) * (radius + 22)}" text-anchor="middle" fill="var(--muted)" font-size="10">${metricDefs[key].label}</text>`; }).join(""); const polygons = valid.slice(0, 4).map((item, companyIndex) => `<polygon points="${keys.map((key, i) => point(i, normalized(item, key))).join(" ")}" fill="var(--teal)" fill-opacity="${Math.max(.08, .2 - companyIndex * .025)}" stroke="${companyIndex % 2 ? "var(--coral)" : "var(--teal)"}" stroke-width="2"/>`).join(""); const legend = valid.slice(0, 4).map((item, index) => `<div class="legend-row"><i style="background:${index % 2 ? "var(--coral)" : "var(--teal)"}"></i>${escapeHtml(companyName(item))}<small>상대지수</small></div>`).join(""); return `<div class="tab-panel radar-layout"><article class="panel radar-box"><svg class="radar-svg" viewBox="0 0 350 350">${grid}${axes}${polygons}</svg></article><article class="panel radar-legend"><div class="panel-title"><div><span class="kicker">STRUCTURE PROFILE</span><h3>상대 비교 레이더</h3></div></div><p style="color:var(--muted);font-size:10px;line-height:1.6">선택한 기업 안에서 가장 낮은 값을 20, 가장 높은 값을 90에 가깝게 표시합니다. 절대 점수가 아니라 상대적인 구조를 봅니다.</p>${legend}</article></div>`;
}

function renderScatter() {
  const valid = availableResults().filter((item) => valueFor(item, "debt_ratio") !== null && valueFor(item, "operating_margin") !== null); if (!valid.length) return renderEmpty("산점도를 그릴 데이터가 없습니다.", "부채비율과 영업이익률이 모두 있는 기업이 필요합니다."); const maxX = Math.max(...valid.map((item) => valueFor(item, "debt_ratio")), 1); const maxY = Math.max(...valid.map((item) => valueFor(item, "operating_margin")), 1); const points = valid.map((item) => { const x = Math.max(5, Math.min(95, valueFor(item, "debt_ratio") / maxX * 90 + 5)); const y = Math.max(5, Math.min(95, valueFor(item, "operating_margin") / maxY * 90 + 5)); return `<span class="scatter-point" style="left:${x}%;bottom:${y}%" title="${escapeHtml(companyName(item))}">${escapeHtml(companyName(item).slice(0, 1))}</span>`; }).join(""); return `<div class="tab-panel"><article class="panel"><div class="panel-title"><div><span class="kicker">RISK / RETURN</span><h3>부채비율 × 영업이익률</h3></div><span>오른쪽일수록 부채비율 높음</span></div><div class="scatter-box"><span class="scatter-axis-y">영업이익률 ↑</span><span class="scatter-axis-x">부채비율 →</span>${points}</div><p class="scatter-note">점에 마우스를 올리면 기업명을 확인할 수 있습니다. 좌상단은 상대적으로 높은 수익성과 낮은 부채비율에 가깝습니다.</p></article></div>`;
}

function renderRank() {
  const key = state.selectedMetrics.find((candidate) => ["debt_ratio", "operating_margin", "current_ratio"].includes(candidate)) || state.selectedMetrics[0]; const valid = availableResults().filter((item) => valueFor(item, key) !== null); if (!valid.length) return renderEmpty("순위를 만들 데이터가 없습니다.", "선택한 지표의 공시 데이터가 없습니다."); const descending = key !== "debt_ratio"; valid.sort((a, b) => (valueFor(b, key) - valueFor(a, key)) * (descending ? 1 : -1)); const values = valid.map((item) => Math.abs(valueFor(item, key))); const max = Math.max(...values, 1); return `<div class="tab-panel"><article class="panel"><div class="panel-title"><div><span class="kicker">LEADERBOARD</span><h3>${metricDefs[key].label} 순위</h3></div><span>${descending ? "높을수록 우수" : "낮을수록 우수"}</span></div><div class="rank-list" style="margin-top:18px">${valid.map((item, index) => `<div class="rank-row"><span class="rank-number">${String(index + 1).padStart(2, "0")}</span><strong class="rank-name">${escapeHtml(companyName(item))}</strong><span class="rank-track"><i style="width:${Math.max(5, Math.abs(valueFor(item, key)) / max * 100)}%"></i></span><span class="rank-value">${escapeHtml(metricValue(item, key))}</span></div>`).join("")}</div></article></div>`;
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
  if (section === "people" && (actual.length < 2 || forecast < 0)) return actual;
  return [...actual, { year: last.year + 1, value: forecast, estimated: true }];
}

function strategyWeightedAverage(rows, field) {
  const values = (rows || []).map((row) => ({ value: numberValue(row[field]), weight: numberValue(row.total) || 1 })).filter((row) => row.value !== null);
  if (!values.length) return null;
  const weight = values.reduce((sum, row) => sum + row.weight, 0);
  return values.reduce((sum, row) => sum + row.value * row.weight, 0) / (weight || values.length);
}

function strategyGenderSummary(item, gender) {
  const rows = (item?.employee_breakdown || []).filter((row) => String(row.sex || "").includes(gender));
  return {
    headcount: rows.reduce((sum, row) => sum + (numberValue(row.total) || 0), 0) || null,
    salary: strategyWeightedAverage(rows, "average_salary"),
    tenure: strategyWeightedAverage(rows, "average_tenure"),
  };
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
  const yearGroups = years.map((year) => {
    const yearRows = seriesByCompany.map(({ item, series }, companyIndex) => ({ item, companyIndex, row: series.find((entry) => entry.year === year) })).filter((entry) => entry.row);
    const bars = yearRows.map(({ item, companyIndex, row }) => {
      const tone = companyIndex % 2 ? "hyn" : "sam";
      const height = Math.max(4, Math.min(100, Math.abs(row.value) / max * 100));
      return `<div class="strategy-profit-column ${tone}${row.estimated ? " forecast" : ""}${row.value < 0 ? " negative" : ""}" title="${escapeHtml(companyName(item))} · ${row.year}${row.estimated ? "E" : ""} · ${escapeHtml(strategyChartAmount(row.value))}"><strong>${escapeHtml(strategyChartAmount(row.value))}</strong><i style="height:${height.toFixed(1)}%"></i><small>${escapeHtml(companyName(item))}</small></div>`;
    }).join("");
    return `<div class="strategy-profit-group"><div class="strategy-profit-bars">${bars}</div><span>${year}${year === Math.max(...years) && yearRows.some(({ row }) => row.estimated) ? " (E)" : ""}</span></div>`;
  }).join("");
  const legend = seriesByCompany.map(({ item }, index) => `<span><i class="strategy-dot ${index % 2 ? "hyn" : "sam"}"></i>${escapeHtml(companyName(item))}</span>`).join("");
  return `<article class="strategy-chart-card strategy-profit-panel"><div class="strategy-chart-head"><div><strong>영업이익 추이와 다음연도 전망</strong><small>실선 = DART 실제값 · 해칭 = 모델 추정</small></div><div class="strategy-chart-legend">${legend}<span><i class="strategy-dot forecast"></i>모델 추정</span></div></div><div class="strategy-profit-chart" role="img" aria-label="기업별 연도별 영업이익과 다음연도 모델 추정"><div class="strategy-profit-axis"><span>${escapeHtml(strategyChartAmount(max))}</span><span>${escapeHtml(strategyChartAmount(max * .66))}</span><span>${escapeHtml(strategyChartAmount(max * .33))}</span><span>0</span></div><div class="strategy-profit-plot">${yearGroups}</div></div><div class="strategy-inline-note"><b>이익은 DART 공시 실제값부터 읽습니다.</b> 다음연도 막대는 최근 공개 추세를 단순 연장한 모델 추정입니다.</div></article>`;
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

  const strategyPeople = valid.map((item) => strategyPeopleResult(item.company?.corp_code)).filter(Boolean);
  const companyCards = valid.map((item) => {
    const p = strategyPeopleResult(item.company?.corp_code);
    const employees = peopleValue(p, "employees_total");
    const operatingProfit = valueFor(item, "operating_profit");
    const profitPerEmployee = operatingProfit !== null && employees ? operatingProfit / employees : null;
    return `<article class="strategy-company-card"><div class="strategy-company-head"><div><span class="kicker">${escapeHtml(item.company?.stock_code || item.company?.corp_code || "DART")}</span><h3>${escapeHtml(companyName(item))}</h3></div><span class="strategy-badge actual">${escapeHtml(state.year)} 실제</span></div><div class="strategy-company-metrics">${strategyCompanyMetric("영업이익", fmtAmount(operatingProfit), "DART 재무 공시", "teal")}${strategyCompanyMetric("영업이익률", fmtPercent(valueFor(item, "operating_margin")), "수익성 체력", "coral")}${strategyCompanyMetric("인당 영업이익", fmtAmount(profitPerEmployee), employees === null ? "직원 수 미공시" : `${fmtCount(employees)} 기준`, "gold")}${strategyCompanyMetric("평균 급여", fmtSalary(peopleValue(p, "average_salary")), p?.error || state.peopleError ? "인력 공시 확인 필요" : "DART 인력 공시", "")}</div></article>`;
  }).join("");
  const segmentDisclosure = `<article class="strategy-segment-note"><span class="kicker">SEGMENT DISCLOSURE</span><h3>사업부·반도체 세그먼트</h3><p>DART API 기본 재무 응답은 기업 전체 손익을 기준으로 합니다. 사업부별 영업이익은 이 화면에서 추정하지 않고, 사업보고서 원문 연계 확장 영역으로 남깁니다.</p></article>`;
  const totalOperatingProfit = valid.map((item) => valueFor(item, "operating_profit")).filter((value) => value !== null).reduce((sum, value) => sum + value, 0);
  const flow = `<div class="strategy-flow"><div class="strategy-flow-node"><span class="kicker">DART FACT</span><strong>영업이익</strong><small>${fmtAmount(totalOperatingProfit)} · 선택 기업 합산</small></div><span class="strategy-flow-arrow">→</span><div class="strategy-flow-node"><span class="kicker">PEOPLE SIGNAL</span><strong>평균 급여·인당 지표</strong><small>인력 공시와 재무 공시를 연결</small></div><span class="strategy-flow-arrow">→</span><div class="strategy-flow-node muted"><span class="kicker">LIMITATION</span><strong>성과급 재원</strong><small>성과급 협약·산식은 DART API만으로 확인 불가</small></div></div>`;

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
  const placeholders = [["평가 등급 분포", "내부 HR 데이터를 연결하면"], ["평가–보상 연동성", "평가·보상 원장을 연결하면"], ["자사 Pay Equity", "개인·직무·직급 데이터를 연결하면"], ["보상 인식 vs 실제", "설문과 AI 분석을 연결하면"]].map(([title, source]) => `<article class="strategy-placeholder"><span class="strategy-lock">LOCKED</span><h3>${title}</h3><p>${source} 활성화됩니다.</p></article>`).join("");
  const trace = state.orchestration?.trace || [];
  const sourceUrls = [...new Set(valid.flatMap((item) => item.source_urls || []).concat(valid.map((item) => item.source_url).filter(Boolean), strategyPeople.flatMap((item) => item.source_urls || [])))].filter(Boolean);
  const providerStatus = state.orchestration?.provider?.status || "미실행";
  const qualityStatus = state.orchestration?.status || "미실행";
  const traceRows = trace.length ? trace.map((row) => `<div class="strategy-trace-row"><span>${escapeHtml(row.agent || "agent")}</span><strong class="${row.status === "completed" ? "status-ok" : "status-warn"}">${escapeHtml(row.status || "unknown")}</strong><small>${escapeHtml(String(row.duration_ms ?? 0))}ms</small></div>`).join("") : `<div class="strategy-missing compact">Strategy Brief 탭을 열면 에이전트 추적이 실행됩니다.</div>`;
  const evidenceLinks = sourceUrls.length ? sourceUrls.slice(0, 8).map((url) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">DART 원문 보기 ↗</a>`).join("") : `<span class="strategy-missing compact">원문 접수번호가 포함된 공시가 없습니다.</span>`;
  return `<div class="tab-panel strategy-brief"><section class="strategy-hero"><div><span class="kicker accent">이익 → 성과급 → 급여 연동 · DART 근거</span><h2>이익 체력으로 읽는<br /><em>보상 대시보드</em></h2><p>참고 대시보드의 프레임을 선택 기업과 기준연도에 맞춰 재구성했습니다. 실제 공시와 모델 추정을 화면에서 분리합니다.</p></div><div class="strategy-legend"><span><i class="teal"></i>DART 실제</span><span><i class="coral"></i>보상·인력</span><span><i class="gold"></i>모델 추정</span></div></section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">00 / PROFIT CAPACITY</span><h3>이익 체력 — 급여를 논하기 전에</h3><p>영업이익의 크기와 직원 수·평균 급여를 같은 기업 단위에서 읽습니다.</p></div><div class="strategy-company-grid">${companyCards}</div>${segmentDisclosure}${flow}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">01 / OPERATING PROFIT</span><h3>영업이익 추이 & 다음연도 전망</h3><p>막대가 실선이면 DART 실제값, 점선이면 최근 추세를 단순 연장한 모델 추정입니다.</p></div>${renderStrategyChart(operatingSeries, fmtAmount)}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">02 / AVERAGE PAY</span><h3>평균 급여 추이 & 다음연도 전망 구간</h3><p>평균 급여는 인력 공시의 집계값이며 개인별 보상이나 성과급을 의미하지 않습니다.</p></div>${renderStrategyChart(salarySeries, fmtSalary)}</section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">03 / PAY EQUITY</span><h3>성별 급여·근속 격차 (공시분)</h3><p>성별 집계가 함께 공시된 경우에만 비교하며, 격차의 원인이나 공정성을 추론하지 않습니다.</p></div><div class="strategy-equity-grid">${equityCards}</div></section><section class="strategy-section"><div class="strategy-section-heading"><span class="kicker">03+ / INTERNAL DIAGNOSTICS</span><h3>내부 제도 진단 — 자사 데이터 연결 시 활성화</h3><p>공시 데이터만으로는 평가·보상 프로세스와 인식 데이터를 판단할 수 없습니다.</p></div><div class="strategy-placeholder-grid">${placeholders}</div></section><section class="strategy-section strategy-evidence"><div class="strategy-section-heading"><span class="kicker">EVIDENCE / ORCHESTRATION</span><h3>근거와 에이전트 실행 상태</h3><p>${escapeHtml(state.year)}년 · ${escapeHtml(reportLabel(state.reportCode))} · OpenDART 원문 접수번호를 확인할 수 있습니다.</p></div><div class="strategy-evidence-grid"><article class="strategy-evidence-card"><span class="kicker">SOURCE LINKS</span><div class="strategy-links">${evidenceLinks}</div></article><article class="strategy-evidence-card"><span class="kicker">QUALITY GATE</span><strong>${escapeHtml(qualityStatus)}</strong><small>Claude MCP provider: ${escapeHtml(providerStatus)}</small><p>에이전트는 원자료 정규화·품질·개인정보 경계를 확인한 뒤 해석 단계로 넘깁니다.</p></article><article class="strategy-evidence-card"><span class="kicker">TRACE</span><div class="strategy-trace">${traceRows}</div></article></div></section><p class="strategy-disclaimer">주의: 다음연도 값은 투자·인사 의사결정용 확정 전망이 아니라 최근 공시 추세를 단순 연장한 모델 추정입니다. 성과급 산식, 개인별 성과, 성별 격차의 원인은 DART API만으로 확정할 수 없습니다.</p></div>`;
}

function renderTab() {
  const content = { overview: renderOverview, compare: renderCompare, trend: renderTrendByYear, people: renderPeople, executives: renderExecutives, strategy: renderStrategy, radar: renderRadar, scatter: renderScatter, rank: renderRank }[state.activeTab]();
  $("#tabContent").innerHTML = content;
  document.body.classList.toggle("strategy-mode", state.activeTab === "strategy");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta) themeMeta.setAttribute("content", state.activeTab === "strategy" ? "#0e1218" : (document.documentElement.dataset.theme === "dark" ? "#132320" : "#f4f6f2"));
  const introKicker = document.querySelector(".intro .kicker");
  const introTitle = document.querySelector(".intro h1");
  const introCopy = document.querySelector(".intro p");
  if (introKicker && introTitle && introCopy) {
    if (state.activeTab === "strategy") {
      introKicker.textContent = "DART / WORKFORCE INTELLIGENCE";
      introTitle.innerHTML = "공시 기반 인력·보상<br /><em>벤치마크를 읽으세요.</em>";
      introCopy.innerHTML = '이익 체력, 평균 급여, 임원 구조를 같은 기준으로 비교하고<br class="wide-only" /> HR 전략상 확인해야 할 근거와 한계를 함께 보여줍니다.';
    } else {
      introKicker.textContent = "DART / STRUCTURE VIEW";
      introTitle.innerHTML = "기업의 숫자를<br /><em>구조로 비교하세요.</em>";
      introCopy.innerHTML = '자산이 어떻게 구성되고, 부채와 자본이 어떤 균형을 이루는지<br class="wide-only" /> 같은 기준으로 나란히 살펴봅니다.';
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
  const valid = availableResults(); if (!valid.length) { $("#readoutText").textContent = "선택한 기업의 실제 공시 수치를 받으면 재무구조 readout이 표시됩니다."; return; }
  const marginLeader = [...valid].sort((a, b) => (valueFor(b, "operating_margin") ?? -Infinity) - (valueFor(a, "operating_margin") ?? -Infinity))[0]; const debtLeader = [...valid].sort((a, b) => (valueFor(a, "debt_ratio") ?? Infinity) - (valueFor(b, "debt_ratio") ?? Infinity))[0]; const liquidityLeader = [...valid].sort((a, b) => (valueFor(b, "current_ratio") ?? -Infinity) - (valueFor(a, "current_ratio") ?? -Infinity))[0]; $("#readoutText").innerHTML = `<strong>${escapeHtml(companyName(marginLeader))}</strong>의 영업이익률은 ${escapeHtml(metricValue(marginLeader, "operating_margin"))}, <strong>${escapeHtml(companyName(debtLeader))}</strong>의 부채비율은 ${escapeHtml(metricValue(debtLeader, "debt_ratio"))}이며, 유동비율은 <strong>${escapeHtml(companyName(liquidityLeader))}</strong>이(가) ${escapeHtml(metricValue(liquidityLeader, "current_ratio"))}로 가장 높습니다. 이는 단순 우열이 아닌 같은 공시 기준에서의 상대 비교입니다.`;
}

function renderDashboard() {
  $("#dashboard").classList.remove("hidden"); $("#welcome").classList.add("hidden"); $("#dataMeta").textContent = `${state.year}년 · ${reportLabel(state.reportCode)}`; const valid = availableResults(); $("#dataCoverage").textContent = `${valid.length} / ${state.results.length}개 기업 수신`; $("#headingMeta").textContent = `${state.selected.length}개 기업 · ${state.year}년 기준`; renderMetricPills(); renderTab(); updateReadout();
}

async function loadStrategyData() {
  if (!state.selected.length || !state.results.length) return;
  const key = `${state.selected.map((item) => item.corp_code).join(",")}:${state.year}:${state.reportCode}`;
  if (state.strategyLoadedFor === key && !state.strategyLoading) { renderTab(); return; }
  const requestToken = ++state.strategyRequestToken;
  state.strategyLoading = true;
  renderTab();
  const fromYear = Math.max(2015, Number(state.year) - 3);
  const [peopleResult, orchestrationResult] = await Promise.allSettled([
    requestPeopleHistory(state.selected, fromYear, state.year, state.reportCode),
    requestWorkforceOrchestration(state.selected, state.year, state.reportCode),
  ]);
  const currentKey = `${state.selected.map((item) => item.corp_code).join(",")}:${state.year}:${state.reportCode}`;
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
}

async function compare() {
  if (!state.selected.length) { setMessage("먼저 비교할 기업을 1개 이상 선택해 주세요."); return; }
  const button = $("#compareButton"); button.disabled = true; button.querySelector("span").textContent = "공시 데이터 불러오는 중"; setMessage(""); state.year = $("#yearSelect").value; state.reportCode = $("#reportSelect").value; state.strategyRequestToken += 1; state.strategyLoading = false; state.peopleError = ""; state.executivesError = ""; state.historyError = ""; state.peopleHistoryError = "";
  try {
    const [currentResult, previousResult, peopleResult, executiveResult] = await Promise.allSettled([
      requestAll(state.selected, state.year, state.reportCode),
      requestAll(state.selected, String(Number(state.year) - 1), state.reportCode),
      requestPeople(state.selected, state.year, state.reportCode),
      requestExecutives(state.selected, state.year, state.reportCode),
    ]);
    if (currentResult.status !== "fulfilled" || previousResult.status !== "fulfilled") throw new Error("재무 공시 데이터를 불러오지 못했습니다.");
    state.results = currentResult.value;
    state.previous = previousResult.value;
    state.people = peopleResult.status === "fulfilled" ? peopleResult.value : [];
    state.executives = executiveResult.status === "fulfilled" ? executiveResult.value : [];
    state.peopleError = peopleResult.status === "rejected" ? peopleResult.reason?.message || "People 요청 실패" : "";
    state.executivesError = executiveResult.status === "rejected" ? executiveResult.reason?.message || "임원 요청 실패" : "";
    state.peopleHistory = [];
    state.orchestration = null;
    state.strategyLoadedFor = "";
    state.historyFromYear = String(Math.max(2015, Number(state.year) - 5));
    state.historyToYear = state.year;
    try { state.history = await requestHistory(state.selected, state.historyFromYear, state.historyToYear, state.reportCode); } catch (error) { state.history = []; state.historyError = error.message || "재무 추이 요청 실패"; }
    renderDashboard();
    if (state.activeTab === "strategy") loadStrategyData();
    $("#dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  catch (error) { setMessage(error.message || "재무 데이터를 불러오지 못했습니다."); }
  finally { button.disabled = false; button.querySelector("span").textContent = "재무구조 비교"; }
}

function buildPeopleContext() {
  return (state.people || []).filter((item) => item?.people && !item.error).map((item) => {
    const p = people(item); const f = financials(resultFor(item.company?.corp_code)); const employees = peopleValue(item, "employees_total"); const revenuePerEmployee = employees && numberValue(f.revenue) !== null ? f.revenue / employees : null; const regularShare = employees && peopleValue(item, "regular_employees") !== null ? peopleValue(item, "regular_employees") / employees * 100 : null;
    return `${companyName(item)} | 총 직원 ${fmtCount(employees)} | 정규직 비중 ${fmtPercent(regularShare)} | 계약직 ${fmtCount(peopleValue(item, "contract_employees"))} | 평균 근속 ${fmtYears(peopleValue(item, "average_tenure_years"))} | 1인 평균 급여 ${fmtSalary(peopleValue(item, "average_salary"))} | 임원 ${fmtCount(peopleValue(item, "executives_total"))} | 미등기임원 평균 급여 ${fmtSalary(peopleValue(item, "unregistered_average_salary"))} | 매출/인 ${fmtAmount(revenuePerEmployee)}`;
  }).join("\n");
}

function buildPeopleHistoryContext() {
  return (state.peopleHistory || []).flatMap((item) => (item.years || []).filter((year) => year?.people && !year.error).map((year) => {
    return `${companyName(item)} | 연도 ${year.year} | 총 직원 ${fmtCount(peopleValue(year, "employees_total"))} | 평균 급여 ${fmtSalary(peopleValue(year, "average_salary"))} | 평균 근속 ${fmtYears(peopleValue(year, "average_tenure_years"))}`;
  })).join("\n");
}

function buildPrompt() {
  const question = $("#analysisPrompt").value.trim() || "기업별 재무구조와 인력 구조의 차이, HR 전략 시사점을 설명해줘"; const rows = state.results.filter((item) => !item.error).map((item) => { const f = financials(item); return `${companyName(item)} | 자산 ${fmtAmount(f.assets)} | 부채 ${fmtAmount(f.liabilities)} | 자본 ${fmtAmount(f.equity)} | 현금 ${fmtAmount(f.cash)} | 매출 ${fmtAmount(f.revenue)} | 영업이익 ${fmtAmount(f.operating_profit)} | 영업이익률 ${fmtPercent(f.operating_margin)} | 부채비율 ${fmtPercent(f.debt_ratio)} | 유동비율 ${fmtRatio(f.current_ratio)}`; }).join("\n"); const peopleRows = buildPeopleContext(); return `다음 OpenDART 공시 수치를 근거로 기업 재무구조와 People Analytics 관점을 비교해줘.\n\n[기준]\n연도: ${state.year || "미선택"} / 보고서: ${reportLabel(state.reportCode)} / 금액 단위: 억 원\n\n[기업별 재무 수치]\n${rows || "수치 없음"}\n\n[기업별 People Analytics 수치]\n${peopleRows || "직원·임원 공시 수치 없음"}\n\n[사용자 질문]\n${question}\n\n[답변 규칙]\n1. 먼저 질문에 대한 결론을 간단히 말해줘.\n2. 재무 구조와 인력·보상 구조를 기업별로 분리해 비교해줘.\n3. 직원 수, 정규직 비중, 근속, 급여, 임원 수, 매출/인을 HR 전략의 참고지표로 해석해줘.\n4. 공시 누락, 회계정책 차이, 집계 데이터의 한계를 구분하고 인과관계나 개인별 성과를 단정하지 마.\n5. 실행 가능한 HR 전략은 가설·추가 검증 데이터·예상 지표(KPI)로 나눠 제시해줘.\n6. 투자 매수·매도 추천은 하지 말고 수치와 해석을 분리해줘.`; }

async function fetchStructuredHandoff() {
  const response = await fetch("/api/analysis/context", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: $("#analysisPrompt").value.trim() || "기업별 재무구조의 차이와 주의할 점을 설명해줘",
      view: state.activeTab,
      corp_codes: state.selected.map((company) => company.corp_code),
      year: state.year,
      report_code: state.reportCode,
      metric_ids: state.selectedMetrics,
      people_context: [buildPeopleContext(), buildPeopleHistoryContext()].filter(Boolean).join("\n[PEOPLE_HISTORY]\n"),
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
  button.disabled = true;
  resultBox.dataset.state = "loading";
  resultBox.textContent = "DART 근거를 정리하고 AI 분석을 요청하는 중입니다…";
  try {
    const response = await fetch("/api/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: $("#analysisPrompt").value.trim() || "기업별 영업이익과 인력·보상 구조의 차이를 HR 관점에서 설명해줘",
        view: state.activeTab,
        corp_codes: state.selected.map((company) => company.corp_code),
        year: state.year,
        report_code: state.reportCode,
        metric_ids: state.selectedMetrics,
        people_context: [buildPeopleContext(), buildPeopleHistoryContext()].filter(Boolean).join("\n[PEOPLE_HISTORY]\n"),
        page: 1,
        page_size: 40,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "AI 분석 요청에 실패했습니다.");
    const provider = payload.provider || {};
    const providerStatus = provider.status || payload.provider_status || "not_configured";
    const providerResult = provider.result ?? payload.provider_result;
    const providerPrompt = provider.prompt || payload.prompt || payload.prompt_handoff?.prompt || "";
    if (providerStatus === "completed" && providerResult !== null && providerResult !== undefined) {
      resultBox.dataset.state = "ready";
      resultBox.textContent = typeof providerResult === "string" ? providerResult : JSON.stringify(providerResult, null, 2);
    } else {
      resultBox.dataset.state = "handoff";
      resultBox.textContent = `AI provider status: ${providerStatus}\n\n현재 Claude MCP 연결이 준비되지 않아 근거 기반 프롬프트를 생성했습니다.\n${providerPrompt}`;
    }
  } catch (error) {
    resultBox.dataset.state = "warning";
    resultBox.textContent = error.message || "AI 분석을 실행하지 못했습니다.";
  } finally {
    button.disabled = false;
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
function csvCell(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
function exportCsv() { if (!state.results.length) { setMessage("먼저 재무구조 비교를 실행해 주세요."); return; } const header = ["기준연도", "보고서", "기업명", "종목코드", ...allMetricKeys.map((key) => metricDefs[key].label)]; const rows = state.results.map((item) => [state.year, reportLabel(state.reportCode), companyName(item), item.company?.stock_code || "", ...allMetricKeys.map((key) => valueFor(item, key) ?? "")]); const csv = "\uFEFF" + [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n"); const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); link.download = `dart-financial-structure-${state.year || "export"}.csv`; link.click(); URL.revokeObjectURL(link.href); }

$("#compareButton").addEventListener("click", compare); $("#runAiButton").addEventListener("click", runAiAnalysis); $("#copyPromptButton").addEventListener("click", copyPrompt); $("#readoutCopyButton").addEventListener("click", copyPrompt); $("#exportButton").addEventListener("click", exportCsv); $("#yearSelect").addEventListener("change", () => { if (state.results.length) setMessage("기준연도가 바뀌었습니다. 다시 비교를 실행해 주세요."); }); $("#reportSelect").addEventListener("change", () => { if (state.results.length) setMessage("보고서가 바뀌었습니다. 다시 비교를 실행해 주세요."); }); $("#clearMetricsButton").addEventListener("click", () => { state.selectedMetrics = ["assets", "liabilities", "equity", "cash", "revenue", "operating_profit", "operating_margin", "debt_ratio", "current_ratio"]; renderMetricPills(); renderTab(); }); $("#tabs").addEventListener("click", (event) => { const button = event.target.closest("[data-tab]"); if (!button) return; state.activeTab = button.dataset.tab; $("#tabs").querySelectorAll("button").forEach((tab) => tab.classList.toggle("active", tab === button)); renderTab(); }); $("#themeToggle").addEventListener("click", () => { const dark = document.documentElement.dataset.theme === "dark"; document.documentElement.dataset.theme = dark ? "" : "dark"; localStorage.setItem("dart-theme", dark ? "light" : "dark"); });

$("#tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-tab]");
  if (button?.dataset.tab === "strategy") loadStrategyData();
});

setupYears(); renderSelected(); if (localStorage.getItem("dart-theme") === "dark") document.documentElement.dataset.theme = "dark";
fetch("/api/health").then((response) => response.json()).then((payload) => { const status = $("#apiStatus"); status.classList.add(payload.api_key_configured ? "ready" : "error"); status.innerHTML = `<i></i> ${payload.api_key_configured ? "OpenDART 연결됨" : "API 키 확인 필요"}`; }).catch(() => { const status = $("#apiStatus"); status.classList.add("error"); status.innerHTML = "<i></i> 서버 연결 필요"; });
