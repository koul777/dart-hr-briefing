import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const deckDir = path.dirname(fileURLToPath(import.meta.url));

const modules = [
  { key: 'm1', label: '01 UI' },
  { key: 'm2', label: '02 DART' },
  { key: 'm3', label: '03 ANALYTICS' },
  { key: 'm4', label: '04 DEPLOY' },
];

const css = String.raw`
  :root {
    --bg: #FFFFFF;
    --dark: #071526;
    --accent: #123FC2;
    --surface: #EAF0FB;
    --text: #0B1736;
    --muted: #596579;
    --line: #C7D2E5;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    width: 720pt;
    height: 405pt;
    overflow: hidden;
    background: var(--bg);
    color: var(--text);
    font-family: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    padding: 22pt 36pt 24pt;
    position: relative;
    display: flex;
    flex-direction: column;
    word-break: keep-all;
    text-wrap: pretty;
  }
  body.dark { background: var(--dark); color: #FFFFFF; }
  h1, h2, h3, p, ul, ol { margin: 0; }
  h1, h2, h3, p, li { word-break: keep-all; padding-bottom: 2px; }
  .rail {
    height: 18pt;
    display: grid;
    grid-template-columns: repeat(4, 1fr) 44pt;
    gap: 12pt;
    align-items: start;
    border-bottom: 1pt solid var(--line);
  }
  .rail p { font-size: 10pt; line-height: 1; color: var(--muted); padding-bottom: 6pt; }
  .rail p.active { color: var(--accent); font-weight: 750; border-bottom: 2pt solid var(--accent); }
  .rail p.page { text-align: right; font-variant-numeric: tabular-nums; }
  .title-wrap { margin-top: 20pt; }
  .kicker { color: var(--accent); font-size: 10.5pt; font-weight: 750; letter-spacing: .04em; margin-bottom: 7pt; }
  .slide-title { font-size: 28pt; line-height: 1.3; font-weight: 760; letter-spacing: -.035em; text-wrap: balance; padding-bottom: 4px; }
  .slide-subtitle { margin-top: 9pt; font-size: 15pt; line-height: 1.52; color: var(--muted); max-width: 570pt; }
  .body { font-size: 15pt; line-height: 1.58; }
  .small { font-size: 15pt; line-height: 1.42; color: var(--muted); }
  .caption { font-size: 15pt; line-height: 1.38; color: var(--muted); }
  .accent { color: var(--accent); }
  .muted { color: var(--muted); }
  .strong { font-weight: 760; }
  .nowrap { white-space: nowrap; }
  .content { margin-top: 16pt; flex: 1 1 auto; min-height: 0; height: auto; }
  .split { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: minmax(0, 1fr); gap: 28pt; height: auto; min-height: 0; align-items: stretch; }
  .split-40 { display: grid; grid-template-columns: 40% 60%; grid-template-rows: minmax(0, 1fr); gap: 24pt; height: auto; min-height: 0; align-items: stretch; }
  .split-60 { display: grid; grid-template-columns: 60% 40%; grid-template-rows: minmax(0, 1fr); gap: 24pt; height: auto; min-height: 0; align-items: stretch; }
  .center { display: flex; align-items: center; justify-content: center; }
  .vcenter { display: flex; flex-direction: column; justify-content: center; }
  .rule { width: 100%; height: 1pt; background: var(--line); }
  .big-number { font-size: 66pt; line-height: 1.1; font-weight: 820; letter-spacing: -.06em; color: var(--accent); padding-bottom: 18px; }
  .huge-word { font-size: 58pt; line-height: 1.08; font-weight: 420; letter-spacing: -.055em; }
  .statement { font-size: 31pt; line-height: 1.32; font-weight: 720; letter-spacing: -.04em; text-wrap: balance; }
  .quote-mark { font-size: 70pt; color: var(--accent); line-height: .7; }
  .list { padding-left: 20pt; }
  .list li { font-size: 15pt; line-height: 1.5; margin-bottom: 8pt; padding-left: 3pt; }
  .numbered-row { display: grid; grid-template-columns: 38pt 1fr; gap: 16pt; padding: 7pt 0; border-bottom: 1pt solid var(--line); }
  .numbered-row:last-child { border-bottom: 0; }
  .numbered-row .n { font-size: 22pt; line-height: 1; font-weight: 800; color: var(--accent); }
  .numbered-row h3 { font-size: 16pt; line-height: 1.38; margin-bottom: 2pt; }
  .numbered-row p { font-size: 15pt; line-height: 1.42; color: var(--muted); }
  .code {
    background: var(--dark);
    color: #FFFFFF;
    padding: 18pt 20pt;
    border-radius: 10pt;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .code p { font-size: 15pt; line-height: 1.38; white-space: pre-wrap; font-family: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', sans-serif; }
  .code p.dim { color: #C7D2E5; }
  .code p.hl { color: #FFFFFF; font-weight: 760; }
  .screen { border: 1pt solid var(--line); border-radius: 9pt; overflow: hidden; background: #FFFFFF; height: 100%; min-height: 0; }
  .screen img { width: 100%; height: 100%; object-fit: contain; display: block; }
  .screen.cover img { object-fit: cover; }
  .screen-caption { margin-top: 7pt; font-size: 15pt; line-height: 1.35; color: var(--muted); }
  .flow { display: flex; align-items: center; gap: 8pt; width: 100%; }
  .flow-item { flex: 1; min-height: 52pt; padding: 9pt 8pt; border-top: 3pt solid var(--accent); background: var(--surface); display: flex; flex-direction: column; justify-content: center; }
  .flow-item h3 { font-size: 15pt; margin-bottom: 5pt; }
  .flow-item p { font-size: 15pt; line-height: 1.38; color: var(--muted); }
  .connector { width: 18pt; height: 1pt; background: var(--accent); position: relative; flex: 0 0 auto; }
  .connector::after { content: ''; position: absolute; right: -1pt; top: -3pt; border-left: 5pt solid var(--accent); border-top: 3.5pt solid transparent; border-bottom: 3.5pt solid transparent; }
  .metric { border-top: 3pt solid var(--accent); padding-top: 10pt; }
  .metric h3 { font-size: 18pt; margin-bottom: 7pt; }
  .metric p { font-size: 15pt; line-height: 1.42; }
  .formula { font-size: 18pt !important; font-weight: 760; color: var(--accent); }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  th, td { padding: 8pt 8pt; vertical-align: top; border-bottom: 1pt solid var(--line); text-align: left; }
  th { background: var(--surface); }
  th p { color: var(--accent); font-size: 15pt; font-weight: 760; }
  td p { font-size: 15pt; line-height: 1.35; }
  .compact-table th, .compact-table td { padding: 4pt 7pt; }
  .env-table th:first-child, .env-table td:first-child { width: 48%; }
  .timeline { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; position: relative; padding-top: 12pt; }
  .timeline::before { content: ''; position: absolute; left: 8%; right: 8%; top: 26pt; height: 2pt; background: var(--line); }
  .time-node { position: relative; padding: 0 8pt; }
  .time-node::before { content: ''; display: block; width: 13pt; height: 13pt; border-radius: 50%; background: var(--accent); margin: 8pt auto 15pt; position: relative; z-index: 1; }
  .time-node h3 { text-align: center; font-size: 15pt; margin-bottom: 6pt; }
  .time-node p { text-align: center; font-size: 15pt; line-height: 1.35; color: var(--muted); }
  .checkpoint { height: auto; min-height: 0; display: grid; grid-template-columns: 190pt 1fr; gap: 34pt; align-items: center; }
  .checkpoint-mark { border-right: 1pt solid var(--line); height: 100%; display: flex; flex-direction: column; justify-content: center; }
  .checkpoint-mark h2 { font-size: 74pt; line-height: 1.08; color: var(--accent); letter-spacing: -.07em; padding-bottom: 18px; }
  .checkpoint-mark p { font-size: 15pt; margin-top: 12pt; color: var(--muted); }
  .checkline { padding: 7pt 0; border-bottom: 1pt solid var(--line); }
  .checkline h3 { font-size: 16pt; margin-bottom: 4pt; }
  .checkline p { font-size: 15pt; color: var(--muted); line-height: 1.42; }
  .compact-check .checkline { padding: 4pt 0; }
  .compact-check .small { line-height: 1.32; }
  .dark .kicker { color: #AFC4FF; }
  .dark .section-no { color: #AFC4FF; font-size: 12pt; font-weight: 700; letter-spacing: .08em; }
  .dark .section-title { margin-top: 36pt; font-size: 48pt; line-height: 1.18; font-weight: 480; letter-spacing: -.055em; text-wrap: balance; padding-bottom: 8px; }
  .dark .section-sub { margin-top: 20pt; font-size: 16pt; line-height: 1.5; color: #C7D2E5; }
  .dark .section-line { position: absolute; left: 36pt; right: 36pt; bottom: 32pt; height: 2pt; background: var(--accent); }
  .cover-eyebrow { font-size: 12pt; color: #AFC4FF; letter-spacing: .08em; font-weight: 700; }
  .cover-title { font-size: 51pt; line-height: 1.14; font-weight: 520; letter-spacing: -.06em; max-width: 600pt; text-wrap: balance; padding-bottom: 12px; }
  .cover-sub { margin-top: 20pt; color: #C7D2E5; font-size: 16pt; }
  .cover-meta { position: absolute; left: 36pt; bottom: 28pt; font-size: 15pt; color: #AFC4FF; }
  .cover-page::after { content: ''; position: absolute; right: 36pt; top: 36pt; width: 90pt; height: 90pt; border-top: 8pt solid var(--accent); border-right: 8pt solid var(--accent); }
  .vconnector { width: 1.5pt; height: 10pt; margin: 2pt auto; background: var(--accent); flex: 0 0 auto; }
  .label { display: inline-block; background: var(--surface); color: var(--accent); padding: 5pt 8pt; font-size: 10pt; font-weight: 760; border-radius: 4pt; }
`;

function rail(active, page) {
  return `<div class="rail">${modules.map(m => `<p class="${m.key === active ? 'active' : ''}">${m.label}</p>`).join('')}<p class="page">${String(page).padStart(2, '0')}</p></div>`;
}

function page({ page, active = 'm1', kicker = '', title = '', subtitle = '', content = '', bodyClass = '' }) {
  return `<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head>
<body class="${bodyClass}">
${bodyClass.includes('dark') ? '' : rail(active, page)}
${title ? `<div class="title-wrap">${kicker ? `<p class="kicker">${kicker}</p>` : ''}<h1 class="slide-title">${title}</h1>${subtitle ? `<p class="slide-subtitle">${subtitle}</p>` : ''}</div>` : ''}
${content}
</body></html>`;
}

function section(pageNo, moduleNo, title, sub) {
  return page({
    page: pageNo,
    bodyClass: 'dark',
    content: `<p class="section-no">MODULE ${moduleNo}</p><h1 class="section-title">${title}</h1><p class="section-sub">${sub}</p><div class="section-line"></div>`,
  });
}

function connector() { return '<div class="connector"></div>'; }

const slides = [
  page({ page: 1, bodyClass: 'dark cover-page', content: `
    <div class="vcenter" style="height:300pt">
      <p class="cover-eyebrow">HR AI AGENT BOOT CAMP · WEEK 2</p>
      <h1 class="cover-title" style="margin-top:16pt">DART로<br>HR Analytics<br>에이전트 만들기</h1>
      <p class="cover-sub">OpenDART · 생성형 AI · GitHub · Vercel</p>
    </div>
    <p class="cover-meta">4시간 실습 · 설명 20% · 직접 만들기 80%</p>` }),

  page({ page: 2, active: 'm1', kicker: '오늘의 출발 질문', title: '경쟁사의 인당 생산성을<br>사업보고서를 직접 뒤지지 않고 확인한다면?', content: `
    <div class="content split">
      <div class="vcenter"><p class="statement">기업과 연도를 고르면<br><span class="accent">인력·보상·재무</span>를<br>한 화면에서 비교합니다.</p></div>
      <div class="vcenter" style="border-left:1pt solid var(--line);padding-left:30pt">
        <p class="small">예시 계산</p>
        <p class="big-number" style="font-size:46pt;margin-top:12pt">20조</p>
        <p class="body" style="margin:8pt 0">÷ 10,000명</p>
        <div class="rule"></div>
        <p class="formula" style="font-size:25pt!important;margin-top:12pt">인당 매출 20억원</p>
      </div>
    </div>` }),

  page({ page: 3, active: 'm1', kicker: '완성본 먼저 보기', title: '기업과 연도만 고르면 비교부터 브리핑까지 이어진다', content: `
    <div class="content split-40">
      <div class="vcenter">
        <p class="body strong">기업 선택</p><p class="small" style="margin:4pt 0 14pt">삼성전자 · SK하이닉스</p>
        <p class="body strong">공시 조회와 계산</p><p class="small" style="margin:4pt 0 14pt">직원수 · 급여 · 매출 · 생산성</p>
        <p class="body strong">근거 기반 브리핑</p><p class="small" style="margin-top:4pt">사실 · 해석 · 추가 확인</p>
      </div>
      <div><div class="screen" style="height:calc(100% - 28pt)"><img src="./assets/current/current-sample.png" alt="현재 빌드에서 직접 실행한 DART HR Briefing 화면"></div><p class="screen-caption">현재 소스 빌드 직접 캡처 · 합성 데이터 · 외부 호출 0회</p></div>
    </div>` }),

  page({ page: 4, active: 'm1', kicker: '학습 결과', title: '4시간 뒤 네 가지 결과물이 남는다', content: `
    <div class="content" style="padding-top:8pt">
      ${[
        ['01','HR Analytics 화면','기업·연도·보고서를 선택하고 핵심 지표를 비교한다'],
        ['02','AI HR 브리핑','구조화된 데이터와 근거 ID로 후속 질문에 답한다'],
        ['03','GitHub 저장소','API 키를 제외하고 재현 가능한 코드를 저장한다'],
        ['04','공개 Web URL','Vercel에서 실제 접속 가능한 서비스를 확인한다'],
      ].map(([n,h,d])=>`<div class="numbered-row"><p class="n">${n}</p><div><h3>${h}</h3><p>${d}</p></div></div>`).join('')}
    </div>` }),

  page({ page: 5, active: 'm1', kicker: '4시간 운영 지도', title: '설명 20%, 직접 만들기 80%', subtitle: '정시 통과율이 80% 미만이면 설명을 늘리지 않고 검증된 체크포인트로 복구합니다.', content: `
    <div class="content vcenter">
      <div class="timeline">
        ${[
          ['13:00','m0','환경·안전'],['13:45','m1','선택 UI'],['14:45','m2','OpenDART'],['15:45','m3','Analytics·AI'],['16:40','m4','GitHub·Vercel']
        ].map(([t,h,d])=>`<div class="time-node"><h3>${t}</h3><p><strong>${h}</strong><br>${d}</p></div>`).join('')}
      </div>
      <p class="caption" style="margin-top:34pt;text-align:center">모듈 사이 10분 휴식 · 16:40–17:00 캡스톤 재현과 결과 공유</p>
    </div>` }),

  page({ page: 6, active: 'm1', kicker: '교육 설계', title: '작동하는 뼈대에서 핵심 기능 네 개를 붙인다', content: `
    <div class="content split">
      <div class="vcenter"><p class="big-number">80%</p><p class="statement" style="font-size:24pt;margin-top:14pt">Starter Project</p><p class="body muted" style="margin-top:12pt">실행·라우팅·기본 UI·배포 구조가 이미 준비된 상태</p></div>
      <div class="vcenter">
        ${['기업·기간 선택 UI','OpenDART 데이터 연결','HR 지표와 AI 브리핑','GitHub·Vercel 배포'].map((x,i)=>`<div class="numbered-row"><p class="n">${i+1}</p><div><h3>${x}</h3><p>${['m1','m2','m3','m4'][i]} 체크포인트에서 저장</p></div></div>`).join('')}
      </div>
    </div>` }),

  page({ page: 7, active: 'm1', kicker: 'm0 · 수업 전 사전점검', title: '시작 조건은 FAIL 0과 비밀값 비노출', content: `
    <div class="content split-60">
      <div><div class="screen"><img src="./assets/preflight.png" alt="classroom preflight 통과 화면"></div></div>
      <div class="vcenter" style="padding-left:8pt">
        <div class="code" style="height:auto"><p>py -3.12 -X utf8</p><p class="hl">tools\\classroom_preflight.py</p></div>
        <ul class="list" style="margin-top:18pt"><li>Python과 필수 파일 확인</li><li>환경변수 이름만 확인</li><li>비밀값은 화면에 출력하지 않음</li></ul>
      </div>
    </div>` }),

  page({ page: 8, active: 'm1', kicker: '프로젝트 지도', title: '다섯 위치만 알면 전체 흐름을 따라갈 수 있다', content: `
    <div class="content split">
      <div class="code">
        <p class="hl">static/index.html</p><p class="dim">화면 구조</p>
        <p class="hl" style="margin-top:9pt">static/app.js</p><p class="dim">화면 동작과 API 호출</p>
        <p class="hl" style="margin-top:9pt">server.py</p><p class="dim">데이터 수집·계산·AI</p>
        <p class="hl" style="margin-top:9pt">api/index.py · vercel.json</p><p class="dim">Vercel 진입점과 라우팅</p>
      </div>
      <div class="vcenter">
        <div class="flow" style="flex-direction:column;align-items:stretch">
          <div class="flow-item"><h3>브라우저</h3><p>기업·연도 선택과 결과 표시</p></div>
          <div class="vconnector"></div>
          <div class="flow-item"><h3>Python 서버</h3><p>OpenDART 조회 · 계산 · 검증</p></div>
          <div class="vconnector"></div>
          <div class="flow-item"><h3>외부 서비스</h3><p>OpenDART · AI · Vercel</p></div>
        </div>
      </div>
    </div>` }),

  section(9, '01', 'AI와 기본 화면 만들기', '13:10–13:45 · m1 기업·연도·보고서 선택'),

  page({ page: 10, active: 'm1', kicker: '협업 경계', title: '사람은 기준을 정하고 AI는 탐색·구현·검증을 돕는다', content: `
    <div class="content split">
      <div style="border-top:5pt solid var(--accent);padding-top:18pt">
        <p class="label">사람</p><h2 style="font-size:28pt;margin:18pt 0">문제와 기준</h2>
        <ul class="list"><li>누가 어떤 결정을 지원받는가</li><li>데이터와 보안의 경계</li><li>계산식과 완료 기준</li><li>최종 실행과 검증 책임</li></ul>
      </div>
      <div style="border-top:5pt solid var(--dark);padding-top:18pt">
        <p class="label">AI</p><h2 style="font-size:28pt;margin:18pt 0">탐색과 구현</h2>
        <ul class="list"><li>코드베이스와 관련 파일 탐색</li><li>작은 단위의 코드 변경</li><li>오류 원인 후보와 수정안 제시</li><li>테스트와 문서 초안 작성</li></ul>
      </div>
    </div>` }),

  page({ page: 11, active: 'm1', kicker: '실습 프롬프트 01', title: '첫 작업은 수정이 아니라 구조 파악이다', content: `
    <div class="content split-60">
      <div class="code">
        <p>이 프로젝트를 분석해줘.</p><p class="hl">코드는 수정하지 말고</p>
        <p style="margin-top:10pt">1. 사용자 화면</p><p>2. OpenDART 데이터 수집</p><p>3. HR 지표 계산</p><p>4. AI 분석</p><p>5. Vercel 배포</p>
        <p class="dim" style="margin-top:10pt">각 기능이 어떤 파일에서 이루어지는지 비개발자도 이해할 수 있게 설명해줘.</p>
      </div>
      <div class="vcenter"><p class="statement" style="font-size:25pt">코드를 내가 먼저 읽기보다<br><span class="accent">AI에게 코드베이스를 읽게 한다.</span></p><p class="small" style="margin-top:18pt">출력에서 파일 경로와 실행 흐름을 확인한 뒤 다음 요청으로 넘어갑니다.</p></div>
    </div>` }),

  page({ page: 12, active: 'm1', kicker: '프롬프트 캔버스', title: '목적·입력·규칙·완료기준을 한 번에 전달한다', content: `
    <div class="content" style="display:grid;grid-template-columns:1fr 1fr;gap:18pt">
      ${[
        ['01 목적','사용자가 해결할 업무와 화면의 역할'],['02 입력','기업·연도·보고서와 데이터 범위'],['03 규칙','보안·결측·단위·기존 구조 유지'],['04 완료기준','눈으로 확인할 상태와 실행 검증']
      ].map(([n,d])=>`<div style="background:var(--surface);padding:18pt;border-top:3pt solid var(--accent)"><h3 style="font-size:19pt;margin-bottom:10pt">${n}</h3><p class="body muted">${d}</p></div>`).join('')}
    </div>` }),

  page({ page: 13, active: 'm1', kicker: 'Starter 실행', title: '실제 데이터 전에 합성 샘플로 화면 계약을 확인한다', content: `
    <div class="content split-60">
      <div><div class="screen"><img src="./assets/current/current-home.png" alt="현재 빌드의 합성 샘플 시작 화면"></div></div>
      <div class="vcenter">
        <p class="label">SAMPLE — SYNTHETIC DATA</p>
        <ul class="list" style="margin-top:20pt"><li>실제 직원·지원자 데이터 없음</li><li>외부 OpenDART·AI 호출 0회</li><li>화면과 계산 흐름을 먼저 검증</li></ul>
        <p class="small" style="margin-top:12pt">강사만 bootstrap JSON을 시연하고 수강생은 화면 상태로 통과합니다.</p>
      </div>
    </div>` }),

  page({ page: 14, active: 'm1', kicker: '실습 프롬프트 02', title: '기업·연도·보고서 선택 화면을 추가한다', content: `
    <div class="content split-60">
      <div class="code">
        <p>현재 프로젝트에 기업 비교 조건을 선택하는 화면을 추가해줘.</p>
        <p class="hl" style="margin-top:10pt">필수 기능</p><p>· 기업 검색과 최대 2개 선택</p><p>· 기준연도와 보고서 선택</p><p>· 비교 실행 버튼</p>
        <p class="hl" style="margin-top:10pt">완료 기준</p><p>선택 조건이 화면에 남고, 조건이 바뀌면 이전 결과를 무효화해줘.</p>
      </div>
      <div class="vcenter"><div class="numbered-row"><p class="n">1</p><div><h3>계획 확인</h3><p>수정 파일과 이유를 먼저 설명</p></div></div><div class="numbered-row"><p class="n">2</p><div><h3>작게 변경</h3><p>기존 스타일과 API 계약 유지</p></div></div><div class="numbered-row"><p class="n">3</p><div><h3>직접 실행</h3><p>브라우저에서 완료 기준 확인</p></div></div></div>
    </div>` }),

  page({ page: 15, active: 'm1', kicker: '13:45 · 필수 체크포인트', title: '기업 2곳과 기간을 선택하고 비교 버튼을 누를 수 있는가', content: `
    <div class="content checkpoint">
      <div class="checkpoint-mark"><h2>m1</h2><p>선택 UI</p></div>
      <div class="vcenter"><div class="checkline"><h3>기업 선택</h3><p>검색 결과에서 두 기업을 중복 없이 추가하고 제거할 수 있다.</p></div><div class="checkline"><h3>기간 조건</h3><p>기준연도와 보고서 유형이 화면에 명확히 보인다.</p></div><div class="checkline"><h3>결과 무효화</h3><p>조건이 바뀌면 이전 비교 결과가 남지 않는다.</p></div><p class="small" style="margin-top:14pt"><strong>80% 미만:</strong> 현재 폴더를 보존하고 m1 복구본으로 전환</p></div>
    </div>` }),

  section(16, '02', 'OpenDART 연결', '14:00–14:45 · m2 공개 공시와 근거 연결'),

  page({ page: 17, active: 'm2', kicker: '데이터 흐름', title: '기업명은 corp_code를 거쳐 보고서 데이터가 된다', content: `
    <div class="content vcenter"><div class="flow">
      <div class="flow-item"><h3>기업</h3><p>삼성전자</p></div>${connector()}
      <div class="flow-item"><h3>corp_code</h3><p>DART 고유번호</p></div>${connector()}
      <div class="flow-item"><h3>보고서</h3><p>2024 사업보고서</p></div>${connector()}
      <div class="flow-item"><h3>데이터</h3><p>직원·급여·매출·이익</p></div>
    </div><p class="statement" style="font-size:24pt;text-align:center;margin-top:38pt">API 호출보다 먼저 <span class="accent">기업·기간·단위</span>를 고정합니다.</p></div>` }),

  page({ page: 18, active: 'm2', kicker: '데이터 정의', title: 'API 호출보다 먼저 지표의 의미를 고정한다', content: `
    <div class="content"><table><thead><tr><th><p>지표</p></th><th><p>확인할 기준</p></th><th><p>화면에 남길 정보</p></th></tr></thead><tbody>
      <tr><td><p class="strong">직원수</p></td><td><p>정규·계약 포함 범위, 기준일</p></td><td><p>명 · 공시 기준일</p></td></tr>
      <tr><td><p class="strong">평균급여</p></td><td><p>연간 지급액인지 평균인지</p></td><td><p>원 · 공시 정의</p></td></tr>
      <tr><td><p class="strong">매출액</p></td><td><p>연결·별도, 누적 기간</p></td><td><p>원 · 재무제표 범위</p></td></tr>
      <tr><td><p class="strong">영업이익</p></td><td><p>연결·별도, 손실 표시</p></td><td><p>원 · 음수 유지</p></td></tr>
    </tbody></table><p class="caption" style="margin-top:9pt">같은 이름의 지표도 보고서·연결범위·기준일이 다르면 직접 비교하지 않습니다.</p></div>` }),

  page({ page: 19, active: 'm2', kicker: '비밀정보 경계', title: 'API 키는 코드가 아니라 환경변수에 둔다', content: `
    <div class="content split">
      <div class="code"><p class="hl">.env</p><p>OPENDART_API_KEY=••••••••</p><p style="margin-top:14pt" class="hl">.env.example</p><p>OPENDART_API_KEY=</p><p style="margin-top:14pt" class="hl">.gitignore</p><p>.env</p></div>
      <div class="vcenter">
        ${[['브라우저','키를 보내지 않는다'],['서버','환경변수에서 읽는다'],['GitHub','.env를 올리지 않는다']].map(([h,d],i)=>`<div class="numbered-row"><p class="n">${i+1}</p><div><h3>${h}</h3><p>${d}</p></div></div>`).join('')}
        <p class="small" style="margin-top:18pt">키 값 자체를 화면·로그·캡처에 표시하지 않습니다.</p>
      </div>
    </div>` }),

  page({ page: 20, active: 'm2', kicker: '실습 프롬프트 03', title: '결측을 0으로 바꾸지 않는 수집 로직을 요청한다', content: `
    <div class="content split-60">
      <div class="code">
        <p>OpenDART API를 연결해서 선택한 기업과 연도의 데이터를 조회하도록 만들어줘.</p>
        <p class="hl" style="margin-top:10pt">사용 데이터</p><p>직원수 · 평균급여 · 매출액 · 영업이익</p>
        <p class="hl" style="margin-top:10pt">규칙</p><p>API Key는 환경변수로 처리하고, 데이터가 없으면 0으로 바꾸지 말고 ‘데이터 없음’을 유지해줘.</p>
        <p class="dim" style="margin-top:10pt">수정 파일과 검증 명령도 함께 알려줘.</p>
      </div>
      <div class="vcenter"><p class="big-number" style="font-size:54pt">0 ≠ ∅</p><p class="statement" style="font-size:23pt;margin-top:18pt">실제 0과<br>공시되지 않은 값은<br>다른 정보입니다.</p></div>
    </div>` }),

  page({ page: 21, active: 'm2', kicker: '실습 화면', title: '화면의 기업 선택이 DART 고유번호로 이어진다', content: `
    <div class="content split-60"><div><div class="screen"><img src="./assets/company-search.png" alt="삼성전자 기업 검색 결과"></div></div><div class="vcenter"><p class="label">SEARCH → DART ID</p><p class="statement" style="font-size:24pt;margin-top:18pt">기업명과 종목코드는<br>사용자 입력입니다.</p><p class="body muted" style="margin-top:16pt"><span class="accent strong">005930 → corp_code 00126380</span></p><p class="small" style="margin-top:14pt">corp_code는 OpenDART 요청에 사용하는 8자리 고유 식별자입니다.</p></div></div>` }),

  page({ page: 22, active: 'm2', kicker: '비교 조건', title: '기업·연도·보고서 조건이 결과와 함께 남아야 한다', content: `
    <div class="content split-60"><div><div class="screen"><img src="./assets/companies-selected.png" alt="두 기업이 선택된 화면"></div></div><div class="vcenter"><p class="statement" style="font-size:25pt">비교 결과의 의미는<br><span class="accent">조건이 보일 때</span><br>검증할 수 있습니다.</p><ul class="list" style="margin-top:20pt"><li>선택 기업과 식별자</li><li>기준연도와 보고서</li><li>조회 단위와 공시 범위</li></ul></div></div>` }),

  page({ page: 23, active: 'm2', kicker: '14:45 · 필수 체크포인트', title: '값뿐 아니라 단위·결측·원문 근거를 설명할 수 있는가', content: `
    <div class="content checkpoint"><div class="checkpoint-mark"><h2>m2</h2><p>공시와 근거</p></div><div class="vcenter"><div class="checkline"><h3>조건</h3><p>기업·연도·보고서·연결범위를 확인한다.</p></div><div class="checkline"><h3>품질</h3><p>결측과 실제 0을 구분하고 단위를 표시한다.</p></div><div class="checkline"><h3>근거</h3><p>각 값에서 원문 또는 evidence ID로 이동할 수 있다.</p></div><p class="small" style="margin-top:14pt"><strong>API 장애:</strong> 최초 요청 포함 최대 3회 후 합성 복구 데이터로 전환</p></div></div>` }),

  section(24, '03', 'HR 지표와 AI 브리핑', '15:00–15:45 · m3 계산·해석·근거·한계'),

  page({ page: 25, active: 'm3', kicker: '파생지표', title: '조회한 값에 계산과 해석 규칙을 더해야 Analytics가 된다', content: `
    <div class="content" style="display:grid;grid-template-columns:1fr 1fr;gap:22pt">
      ${[
        ['인당 매출','매출액 ÷ 직원수'],['인당 영업이익','영업이익 ÷ 직원수'],['직원수 증가율','(당기 − 전기) ÷ 전기'],['평균급여 증가율','(당기 − 전기) ÷ 전기']
      ].map(([h,f])=>`<div class="metric"><h3>${h}</h3><p class="formula">${f}</p><p class="small" style="margin-top:8pt">결측 또는 분모 0이면 계산하지 않음</p></div>`).join('')}
    </div>` }),

  page({ page: 26, active: 'm3', kicker: '실습 프롬프트 04', title: '계산식을 별도 함수로 만들고 결측이면 계산하지 않는다', content: `
    <div class="content split-60">
      <div class="code"><p>직원수, 평균급여, 매출액, 영업이익으로 파생지표를 계산해줘.</p><p class="hl" style="margin-top:10pt">계산할 지표</p><p>인당 매출 · 인당 영업이익</p><p>직원수 증가율 · 평균급여 증가율</p><p class="hl" style="margin-top:10pt">구현 규칙</p><p>계산식은 별도 함수로 만들고, 결측 또는 분모 0이면 계산하지 마.</p><p class="dim" style="margin-top:10pt">단위 변환과 테스트 사례도 추가해줘.</p></div>
      <div class="vcenter"><div class="checkline"><h3>원 단위 유지</h3><p>저장 값과 표시 단위를 분리</p></div><div class="checkline"><h3>분모 검증</h3><p>0과 결측을 나눠 처리</p></div><div class="checkline"><h3>테스트 사례</h3><p>정상·결측·음수·0을 확인</p></div></div>
    </div>` }),

  page({ page: 27, active: 'm3', kicker: 'AI 입력 계약', title: '원문 전체 대신 검증된 구조화 데이터만 전달한다', content: `
    <div class="content split-60"><div class="code"><p>{</p><p>  "company": "A사",</p><p>  "employees": 10000,</p><p>  "average_salary": 92000000,</p><p>  "revenue": 20000000000000,</p><p class="hl">  "revenue_per_employee": 2000000000,</p><p class="hl">  "evidence_ids": ["EMP-01", "FIN-03"]</p><p>}</p></div><div class="vcenter"><p class="statement" style="font-size:25pt">LLM은 계산기가 아니라<br><span class="accent">검증된 결과의 설명자</span>로 사용합니다.</p><p class="small" style="margin-top:18pt">수치·단위·출처를 서버에서 확정하고 AI는 해석 초안을 작성합니다.</p></div></div>` }),

  page({ page: 28, active: 'm3', kicker: 'Agent 구조', title: '에이전트는 질문 뒤에서 도구와 검증 절차를 실행한다', content: `
    <div class="content split">
      <div><p class="label">단순 챗봇</p><div class="flow" style="margin-top:24pt"><div class="flow-item"><h3>질문</h3></div>${connector()}<div class="flow-item"><h3>LLM</h3></div>${connector()}<div class="flow-item"><h3>답변</h3></div></div><p class="small" style="margin-top:20pt">근거와 계산 과정을 시스템이 보장하지 못함</p></div>
      <div><p class="label">HR Analytics Agent</p><div class="flow" style="margin-top:24pt;flex-direction:column;align-items:stretch"><div class="flow-item"><h3>질문과 조건 확인</h3></div><div class="flow-item"><h3>OpenDART · 계산 · 근거 검증</h3></div><div class="flow-item"><h3>AI 해석과 후속 질문</h3></div></div></div>
    </div>` }),

  page({ page: 29, active: 'm3', kicker: '실습 프롬프트 05', title: '사실·해석·추가 확인을 구분하도록 시스템 규칙을 준다', content: `
    <div class="content split-60"><div class="code"><p>당신은 HR Business Partner를 지원하는 HR Analytics Assistant입니다.</p><p class="hl" style="margin-top:10pt">공시 데이터에 기반해서만 답하십시오.</p><p style="margin-top:10pt">1. 확인된 사실</p><p>2. 계산 결과</p><p>3. 해석</p><p>4. 추가로 확인할 정보</p><p class="dim" style="margin-top:10pt">인과관계를 단정하지 말고, 개인 평가·채용·보상 판단을 하지 마십시오.</p></div><div class="vcenter"><p class="statement" style="font-size:24pt">좋은 답변은<br>더 단정적인 답변이 아니라<br><span class="accent">경계가 보이는 답변</span>입니다.</p></div></div>` }),

  page({ page: 30, active: 'm3', kicker: 'Strategy Brief', title: 'AI 답변보다 먼저 근거가 연결된 결정 브리프를 만든다', content: `
    <div class="content split-60"><div><div class="screen"><img src="./assets/current/current-strategy.png" alt="현재 빌드에서 직접 연 Strategy Brief 화면"></div></div><div class="vcenter"><p class="body strong">브리프의 기본 구조</p><ul class="list" style="margin-top:14pt"><li>확인된 공시 사실</li><li>서버가 계산한 지표</li><li>제한적인 해석</li><li>가설과 추가 내부 데이터</li><li>원문 근거 ID</li></ul><p class="small" style="margin-top:10pt"><strong>ready</strong>는 성공확률이 아니라 근거 이용 가능성을 뜻합니다.</p></div></div>` }),

  page({ page: 31, active: 'm3', kicker: '후속 질문', title: '현재 기업·연도·지표 맥락을 유지한 채 질문한다', content: `
    <div class="content split-60"><div><div class="screen"><img src="./assets/current/current-ai.png" alt="현재 빌드에서 직접 실행한 합성 AI 브리핑 화면"></div></div><div class="vcenter"><p class="label">질문 예시</p><p class="statement" style="font-size:24pt;margin-top:18pt">“두 기업의 인력 생산성 차이를 설명해줘.”</p><div class="rule" style="margin:20pt 0"></div><p class="body">기업·기간·선택 지표·근거 ID를 질문과 함께 전달합니다.</p><p class="small" style="margin-top:12pt">합성 모드에서는 외부 AI를 호출하지 않고 결정론적 브리핑으로 검증합니다.</p></div></div>` }),

  page({ page: 32, active: 'm3', kicker: '15:45 · 필수 체크포인트', title: '답변의 사실·계산·해석·한계를 구분할 수 있는가', content: `
    <div class="content checkpoint"><div class="checkpoint-mark"><h2>m3</h2><p>분석과 AI</p></div><div class="vcenter"><div class="checkline"><h3>구조</h3><p>사실·계산·해석·가설·추가 데이터를 나눈다.</p></div><div class="checkline"><h3>근거</h3><p>주요 수치와 문장에 evidence ID가 연결된다.</p></div><div class="checkline"><h3>안전</h3><p>개인 평가·인과 단정·자동 인사조치를 제안하지 않는다.</p></div><p class="small" style="margin-top:14pt"><strong>AI 장애:</strong> Strategy Brief와 검증 대체 응답으로 통과</p></div></div>` }),

  section(33, '04', 'GitHub와 Vercel 배포', '16:00–16:40 · m4 재현 가능한 저장소와 공개 URL'),

  page({ page: 34, active: 'm4', kicker: 'GitHub 1/4 · 업로드 전', title: 'git add 전에 비밀값과 불필요한 파일부터 막는다', content: `
    <div class="content split-60"><div class="code"><p class="hl">git init</p><p>git status</p><p>git check-ignore .env</p><p>git ls-files .env</p><p class="dim"># 마지막 명령은 출력이 없어야 합니다</p><p style="margin-top:10pt"># 올라가면 안 되는 파일</p><p class="dim">.env · API 키 · 개인 데이터</p><p class="dim">로컬 빌드 · 보고서 · 대용량 미디어</p></div><div class="vcenter"><div class="checkline"><h3>1. 저장소 시작</h3><p>ZIP으로 받았어도 git init으로 준비합니다.</p></div><div class="checkline"><h3>2. ignore·추적 확인</h3><p>.env가 제외되고 이미 추적되지 않아야 합니다.</p></div><div class="checkline"><h3>3. 공개 가능성</h3><p>처음 보는 사람에게 보여도 되는 파일만 남깁니다.</p></div></div></div>` }),

  page({ page: 35, active: 'm4', kicker: 'GitHub 2/4 · 저장소 만들기', title: 'github.com/new에서 비어 있는 공개 저장소를 만든다', content: `
    <div class="content split"><div class="vcenter"><p class="big-number" style="font-size:46pt">github.com/new</p><p class="body muted" style="margin-top:16pt">오른쪽 위 <strong>＋</strong> → <strong>New repository</strong>로 들어가도 됩니다.</p></div><div class="vcenter"><div class="numbered-row"><p class="n">1</p><div><h3>Repository name</h3><p>dart-hr-agent</p></div></div><div class="numbered-row"><p class="n">2</p><div><h3>Visibility</h3><p>Public 또는 수업 정책에 맞는 범위</p></div></div><div class="numbered-row"><p class="n">3</p><div><h3>Initialize</h3><p>README · .gitignore · License 추가 안 함</p></div></div><div class="numbered-row"><p class="n">4</p><div><h3>Create repository</h3><p>생성 뒤 표시되는 HTTPS 주소 복사</p></div></div></div></div>` }),

  page({ page: 36, active: 'm4', kicker: 'GitHub 3/4 · 첫 푸시', title: '로컬 폴더를 main 브랜치로 연결해 처음 푸시한다', content: `
    <div class="content split-60"><div class="code"><p>git add .</p><p class="hl">git diff --cached --name-only</p><p class="hl">git diff --cached</p><p>git commit -m "Build DART HR agent"</p><p>git branch -M main</p><p>git remote add origin &lt;복사한 HTTPS 주소&gt;</p><p>git push -u origin main</p></div><div class="vcenter"><p class="label">커밋 직전 통과 기준</p><ul class="list" style="margin-top:16pt"><li>staged 파일에 .env가 없다</li><li>diff에 실제 API 키가 없다</li><li>push 결과에 main → main이 보인다</li></ul><p class="small" style="margin-top:10pt"><strong>&lt;복사한 HTTPS 주소&gt;</strong>는 GitHub Quick Setup에서 복사한 주소 전체로 바꿉니다.</p></div></div>` }),

  page({ page: 37, active: 'm4', kicker: 'GitHub 4/4 · 웹 확인', title: '브라우저에서 저장소 이름·필수 파일·커밋을 확인한다', content: `
    <div class="content split-60"><div class="code"><p class="hl">&lt;내 ID&gt; / dart-hr-agent</p><p style="margin-top:12pt">README.md</p><p>api/index.py</p><p>static/index.html</p><p>server.py</p><p>vercel.json</p><p class="dim" style="margin-top:12pt">Latest commit · Build DART HR agent</p></div><div class="vcenter compact-check"><div class="checkline"><h3>주소</h3><p>내 계정의 dart-hr-agent 저장소</p></div><div class="checkline"><h3>파일</h3><p>README.md · api/index.py · vercel.json</p></div><div class="checkline"><h3>보안</h3><p>.env와 실제 API 키가 보이지 않음</p></div><div class="checkline"><h3>기록</h3><p>방금 만든 커밋 메시지가 보임</p></div></div></div>` }),

  page({ page: 38, active: 'm4', kicker: 'Vercel 1/5 · Git 연결', title: 'vercel.com/new에서 GitHub 저장소를 가져온다', content: `
    <div class="content vcenter"><div class="flow"><div class="flow-item"><h3>New Project</h3><p>vercel.com/new</p></div>${connector()}<div class="flow-item"><h3>Continue with GitHub</h3><p>GitHub 연동 승인</p></div>${connector()}<div class="flow-item"><h3>Repository</h3><p>dart-hr-agent 찾기</p></div>${connector()}<div class="flow-item"><h3>Import</h3><p>프로젝트 설정 열기</p></div></div><p class="statement" style="font-size:23pt;text-align:center;margin-top:36pt">목록에 저장소가 없으면 먼저 <span class="accent">GitHub App 접근 권한</span>을 확인합니다.</p></div>` }),

  page({ page: 39, active: 'm4', kicker: 'Vercel 2/5 · 프로젝트 설정', title: '이 저장소는 vercel.json과 api/index.py를 그대로 사용한다', content: `
    <div class="content"><table class="compact-table"><thead><tr><th><p>설정</p></th><th><p>입력</p></th><th><p>이유</p></th></tr></thead><tbody><tr><td><p class="strong">Project Name</p></td><td><p>dart-hr-agent</p></td><td><p>공개 URL의 기본 이름</p></td></tr><tr><td><p class="strong">Framework Preset</p></td><td><p>Other</p></td><td><p>Python Function과 정적 화면 조합</p></td></tr><tr><td><p class="strong">Root Directory</p></td><td><p>./</p></td><td><p>api·static·vercel.json이 루트에 있음</p></td></tr><tr><td><p class="strong">Build / Output</p></td><td><p>Override 하지 않음</p></td><td><p>저장소 설정을 Vercel이 읽음</p></td></tr></tbody></table><p class="caption" style="margin-top:7pt">모노레포가 아니라면 Root Directory의 Edit 버튼을 누를 필요가 없습니다.</p></div>` }),

  page({ page: 40, active: 'm4', kicker: 'Vercel 3/5 · 환경변수', title: '키 값은 Environment Variables에 등록하고 새로 배포한다', content: `
    <div class="content"><table class="compact-table env-table"><thead><tr><th><p>Name / 입력 위치</p></th><th><p>용도와 보호</p></th></tr></thead><tbody><tr><td><p class="strong">OPENDART_API_KEY</p></td><td><p>Vercel Production · Sensitive ON</p></td></tr><tr><td><p class="strong">OPENAI_MODEL</p></td><td><p>Vercel Production · Sensitive OFF · 선택</p></td></tr><tr><td><p class="strong">수강생 개인 AI 키</p></td><td><p>브라우저 입력 · 서버 저장 안 함</p></td></tr></tbody></table><p class="caption" style="margin-top:10pt"><strong>수업 경로:</strong> 공시 키는 서버 환경변수, AI 키는 각 수강생이 화면에서 직접 입력</p></div>` }),

  page({ page: 41, active: 'm4', kicker: 'Vercel 4/5 · 배포', title: 'Deploy를 누르고 Building에서 Ready까지 확인한다', content: `
    <div class="content split"><div class="vcenter"><div class="flow" style="flex-direction:column;align-items:stretch"><div class="flow-item"><h3>Deploy</h3><p>GitHub commit 선택</p></div><div class="vconnector"></div><div class="flow-item"><h3>Building</h3><p>Function과 route 구성</p></div><div class="vconnector"></div><div class="flow-item"><h3>Ready</h3><p>Visit 버튼과 배포 URL 생성</p></div></div></div><div class="vcenter"><p class="label">실패했을 때</p><p class="statement" style="font-size:24pt;margin-top:18pt">Deployment → <span class="accent">Build Logs</span>에서 첫 번째 오류부터 읽습니다.</p><p class="small" style="margin-top:16pt">환경변수 값은 로그에 출력하지 말고 변수 이름과 설정 대상만 확인합니다.</p></div></div>` }),

  page({ page: 42, active: 'm4', kicker: 'Vercel 5/5 · 운영 검증', title: 'Ready가 아니라 실제 화면과 API 재현으로 배포를 통과시킨다', content: `
    <div class="content split-60"><div><div class="screen"><img src="./assets/production.png" alt="운영 배포 완료 화면"></div></div><div class="vcenter"><div class="code" style="height:auto"><p>BASE  Visit 버튼이 연 주소</p><p class="hl">ROOT  / · HEALTH  /api/health</p></div><ol class="list compact-check" style="margin-top:8pt"><li>루트 화면이 열린다</li><li>health의 app.id를 확인한다</li><li>합성 샘플을 1회 실행한다</li><li>비밀값이 없고 서버 파일 URL이 차단된다</li></ol></div></div>` }),

  page({ page: 43, active: 'm4', kicker: '자동 재배포', title: '이후에는 push가 새 Preview 또는 Production 배포를 만든다', content: `
    <div class="content vcenter"><div class="flow"><div class="flow-item"><h3>코드 수정</h3><p>로컬 검증</p></div>${connector()}<div class="flow-item"><h3>git push</h3><p>branch에 전송</p></div>${connector()}<div class="flow-item"><h3>Vercel</h3><p>새 배포 생성</p></div>${connector()}<div class="flow-item"><h3>URL 확인</h3><p>화면 · health</p></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:20pt;margin-top:34pt"><div class="metric"><h3>기능 브랜치</h3><p class="formula">Preview URL</p><p class="small" style="margin-top:8pt">공유·확인 후 main에 반영</p></div><div class="metric"><h3>main 브랜치</h3><p class="formula">Production URL</p><p class="small" style="margin-top:8pt">최종 사용자 주소 갱신</p></div></div></div>` }),

  page({ page: 44, active: 'm4', kicker: '배포 복구 지도', title: '문제가 생기면 증상에 맞는 화면 한 곳만 확인한다', content: `
    <div class="content"><table><thead><tr><th><p>증상</p></th><th><p>먼저 볼 곳</p></th><th><p>복구</p></th></tr></thead><tbody><tr><td><p class="strong">GitHub 저장소가 안 보임</p></td><td><p>Vercel Git 권한</p></td><td><p>GitHub App 저장소 접근 허용</p></td></tr><tr><td><p class="strong">push 인증 실패</p></td><td><p>remote와 로그인</p></td><td><p>주소 확인 후 브라우저 인증</p></td></tr><tr><td><p class="strong">Build Failed</p></td><td><p>Build Logs 첫 오류</p></td><td><p>파일·의존성·Python 버전 수정</p></td></tr><tr><td><p class="strong">키 변경이 반영 안 됨</p></td><td><p>환경과 최근 배포</p></td><td><p>Production 선택 후 Redeploy</p></td></tr><tr><td><p class="strong">404 또는 API 오류</p></td><td><p>vercel.json · Root</p></td><td><p>루트 ./ 확인 후 새 배포</p></td></tr></tbody></table></div>` }),

  page({ page: 45, active: 'm4', kicker: '16:40 · 필수 체크포인트', title: 'GitHub 주소와 실제 동작하는 Vercel URL을 제출할 수 있는가', content: `
    <div class="content checkpoint compact-check"><div class="checkpoint-mark"><h2>m4</h2><p>저장과 배포</p></div><div class="vcenter"><div class="checkline"><h3>GitHub</h3><p>README·코드·커밋이 보이고 .env는 보이지 않는다.</p></div><div class="checkline"><h3>Vercel</h3><p>루트 화면과 /api/health가 같은 배포에서 열린다.</p></div><div class="checkline"><h3>재현</h3><p>합성 샘플을 실행하고 배포 URL을 짝과 교환한다.</p></div><p class="small" style="margin-top:8pt"><strong>5분 초과:</strong> 강사 배포 URL로 검증하고 개인 배포는 사후 과제로 보존</p></div></div>` }),

  page({ page: 46, bodyClass: 'dark cover-page', content: `
    <div class="vcenter" style="height:310pt">
      <p class="cover-eyebrow">CAPSTONE COMPLETE</p>
      <h1 class="cover-title" style="margin-top:16pt;max-width:650pt">질문을 근거와 URL이 있는 도구로 바꿨습니다</h1>
      <p class="cover-sub">HR Analytics Dashboard · AI Briefing · GitHub · Web URL</p>
    </div>
    <p class="cover-meta">다음 단계: 합성 내부 데이터의 필드·단위·집계수준·검증 규칙 설계</p>
    ` }),
];

if (slides.length !== 46) throw new Error(`Expected 46 slides, got ${slides.length}`);

slides.forEach((html, index) => {
  fs.writeFileSync(path.join(deckDir, `slide-${String(index + 1).padStart(2, '0')}.html`), html, 'utf8');
});

const notes = `# 발표자 노트 — DART로 HR Analytics 에이전트 만들기

## 운영 원칙
- 슬라이드 설명은 전체 시간의 20%를 넘기지 않습니다.
- 각 모듈은 설명 → 강사 시연 → 참가자 재현 → 통과 확인 → 저장 순으로 진행합니다.
- 정시 통과율이 80% 미만이면 새 설명을 멈추고 검증된 복구본으로 전환합니다.
- 실제 직원·지원자 개인정보는 어떤 단계에서도 입력하지 않습니다.

## 슬라이드별 진행
${[
  ['오프닝 2분','완성 결과를 예고하고 오늘의 질문을 던집니다.'],
  ['문제 제기 2분','인당 생산성 계산 예시로 공시 데이터가 HR 질문으로 바뀌는 장면을 설명합니다.'],
  ['완성본 시연 3분','기업 선택, Compare, Strategy, AI 질문을 끊지 않고 보여줍니다.'],
  ['산출물 약속 2분','수강생이 제출할 네 가지 결과물을 명확히 말합니다.'],
  ['시간표 2분','체크포인트 시각과 80% 전환 규칙을 공지합니다.'],
  ['Starter 방식 2분','전체 코드를 처음부터 작성하지 않는 이유와 네 가지 직접 구현 범위를 설명합니다.'],
  ['사전점검 2분','FAIL 0만 확인하고 키 값은 절대 화면에 띄우지 않습니다.'],
  ['구조 지도 3분','다섯 파일 위치를 실제 편집기에서 열어 보여줍니다.'],
  ['모듈 1 시작','m1 완료 상태를 다시 읽습니다.'],
  ['역할 경계 3분','AI에게 맡길 일과 사람이 검증할 일을 수강생에게 한 가지씩 말하게 합니다.'],
  ['프롬프트 01 실습 5분','출력에서 파일 경로 다섯 개를 찾게 합니다. 수정 제안이 나오면 아직 적용하지 않습니다.'],
  ['프롬프트 구조 3분','목적·입력·규칙·완료기준 중 빠진 항목을 찾게 합니다.'],
  ['합성 샘플 3분','SAMPLE 배너와 외부 호출 없음 상태를 확인합니다.'],
  ['프롬프트 02 실습 15분','계획 확인 후 변경을 적용하고 브라우저에서 직접 조건을 바꿉니다.'],
  ['m1 점검 5분','통과율을 집계하고 미완료자는 작업 폴더를 보존한 채 복구본으로 이동합니다.'],
  ['모듈 2 시작','API 호출보다 데이터 정의가 먼저라는 메시지를 강조합니다.'],
  ['OpenDART 흐름 3분','corp_code와 종목코드의 차이를 설명합니다.'],
  ['데이터 정의 4분','연결·별도, 기준일, 단위가 다른 값의 직접 비교를 금지합니다.'],
  ['키 경계 3분','env 파일과 공개 가능한 예시 파일의 차이를 보여줍니다.'],
  ['프롬프트 03 실습 15분','결측을 0으로 치환하지 않았는지 코드와 화면에서 확인합니다.'],
  ['기업 검색 4분','삼성전자 검색 결과에서 법인명·종목코드·DART 식별자를 확인합니다.'],
  ['비교 조건 4분','기업·연도·보고서가 결과와 함께 보이는지 확인합니다.'],
  ['m2 점검 5분','키 오류나 429가 반복되면 즉시 합성 복구 데이터로 전환합니다.'],
  ['모듈 3 시작','조회와 분석의 차이를 예고합니다.'],
  ['파생지표 5분','계산식 네 개를 설명하고 결측·분모 0 조건을 묻습니다.'],
  ['프롬프트 04 실습 12분','함수와 테스트를 함께 만들고 정상·결측·0 사례를 실행합니다.'],
  ['AI 입력 계약 3분','원문 전체가 아니라 서버가 검증한 JSON을 전달하는 이유를 설명합니다.'],
  ['챗봇과 Agent 3분','도구 호출과 검증 루프가 Agent의 핵심임을 설명합니다.'],
  ['프롬프트 05 실습 10분','사실·계산·해석·추가 확인 구분과 금지 규칙을 적용합니다.'],
  ['Strategy Brief 4분','ready의 의미가 성공확률이 아님을 확인합니다.'],
  ['후속 질문 4분','두 기업의 생산성 차이를 묻고 근거 ID와 한계를 찾습니다.'],
  ['m3 점검 5분','AI 장애는 실패가 아니라 대체 응답 검증 경로로 평가합니다.'],
  ['모듈 4 시작','저장소와 공개 URL을 최종 산출물로 다시 확인합니다.'],
  ['업로드 전 점검 3분','git add 전에 .env, 비밀값, 로컬 산출물이 제외됐는지 확인합니다.'],
  ['GitHub 저장소 생성 3분','github.com/new에서 초기 파일을 추가하지 않은 빈 저장소를 만들게 합니다.'],
  ['GitHub 첫 푸시 6분','명령을 한 줄씩 실행하고 status, remote, main → main을 확인합니다.'],
  ['GitHub 웹 확인 2분','README, vercel.json, 최신 커밋을 확인하고 .env가 없는지 검사합니다.'],
  ['Vercel Git 연결 3분','vercel.com/new에서 GitHub 권한과 저장소 Import까지 진행합니다.'],
  ['Vercel 프로젝트 설정 3분','Framework Other, Root ./, Build/Output 기본값을 확인합니다.'],
  ['Vercel 환경변수 4분','변수 이름과 대상 환경만 함께 확인하고 실제 키 값은 화면에서 가립니다.'],
  ['Vercel Deploy 3분','Building에서 멈추면 Build Logs의 첫 번째 오류를 읽게 합니다.'],
  ['운영 검증 4분','root, health, 합성 샘플을 같은 Production URL에서 재현합니다.'],
  ['자동 재배포 2분','기능 브랜치와 main의 Preview·Production 차이를 설명합니다.'],
  ['배포 복구 2분','저장소 권한, 인증, 로그, 환경변수, route 중 증상에 맞는 한 곳만 봅니다.'],
  ['m4 점검 3분','GitHub URL과 Vercel URL을 짝과 교환하고 합성 샘플을 실행합니다.'],
  ['마무리 2분','네 결과물을 함께 읽고 다음 주 합성 내부 데이터 설계로 연결합니다.'],
].map((x,i)=>`### ${String(i+1).padStart(2,'0')}. ${x[0]}\n${x[1]}`).join('\n\n')}
`;
fs.writeFileSync(path.join(deckDir, 'speaker-notes.md'), notes, 'utf8');

const prompts = `# 수강생용 Claude Code 실습 프롬프트

아래 프롬프트는 순서대로 사용합니다. 각 단계에서 AI가 제안한 변경 파일과 검증 방법을 먼저 확인합니다.

## 01. 저장소 구조 파악
이 프로젝트를 분석해줘. 코드는 수정하지 말고 사용자 화면, OpenDART 데이터 수집, HR 지표 계산, AI 분석, Vercel 배포가 각각 어떤 파일에서 이루어지는지 비개발자도 이해할 수 있게 설명해줘.

## 02. 실행 방법 확인
이 저장소의 정확한 로컬 실행 방법과 health 확인 방법을 찾아줘. 추측하지 말고 README와 실제 진입점을 근거로 설명해줘.

## 03. 변경 계획 작성
기업 검색, 최대 2개 선택, 기준연도, 보고서 유형, 비교 버튼을 추가하려고 한다. 아직 코드를 수정하지 말고 변경할 파일과 구현 순서, 완료 기준을 제안해줘.

## 04. 기업 선택 UI 구현
승인한 계획대로 기업 비교 조건 UI를 구현해줘. 기존 스타일과 API 계약을 유지하고, 조건이 바뀌면 이전 결과를 무효화해줘. 변경 후 실행 검증 방법을 알려줘.

## 05. m1 오류 수정
현재 화면 또는 터미널의 오류를 읽고 원인 후보를 좁혀줘. 가장 작은 수정부터 적용하고, 수정한 파일과 재현·검증 결과를 정리해줘.

## 06. OpenDART 연결 계획
선택한 기업과 연도의 직원수, 평균급여, 매출액, 영업이익을 조회하려고 한다. 사용할 기존 함수와 API 경로, 변경 파일, 호출 예산을 먼저 분석해줘. 아직 수정하지 마.

## 07. API 키 환경변수 처리
OPENDART_API_KEY를 코드에 넣지 않고 환경변수로 읽도록 구현해줘. .env.example에는 변수 이름만 남기고 .env가 Git에서 제외되는지도 확인해줘. 키 값은 출력하지 마.

## 08. 기업 검색과 corp_code
기업명 또는 종목코드로 검색하고 선택 결과에 corp_code를 보관하도록 구현해줘. 유사 법인명과 중복 선택을 안전하게 처리하고 테스트해줘.

## 09. 핵심 데이터 수집
선택 기업·연도·보고서의 직원수, 평균급여, 매출액, 영업이익을 조회해줘. 데이터가 없으면 0으로 바꾸지 말고 결측 상태와 이유를 유지해줘.

## 10. 데이터 품질 표시
각 값에 단위, 기준일 또는 기간, 연결·별도 범위, 원문 근거 ID를 함께 표시해줘. 서로 직접 비교할 수 없는 조건이면 경고를 보여줘.

## 11. 파생지표 함수
인당 매출, 인당 영업이익, 직원수 증가율, 평균급여 증가율을 별도 함수로 계산해줘. 결측 또는 분모 0이면 계산하지 말고 정상·결측·음수·0 테스트를 추가해줘.

## 12. 비교 화면
두 기업의 원자료와 파생지표를 한 화면에서 비교해줘. 값이 없는 칸과 실제 0을 시각적으로 구분하고 비교 조건을 결과 위에 고정해줘.

## 13. AI 입력 계약
AI에게 원문 전체를 보내지 말고 검증된 구조화 데이터, 계산 결과, evidence_ids만 전달하는 payload를 만들어줘. 전송 전 스키마 검증도 추가해줘.

## 14. HR Analytics 시스템 규칙
AI 응답을 확인된 사실, 계산 결과, 해석, 추가로 확인할 정보로 구분해줘. 공시만으로 인과를 단정하거나 개인 평가·채용·보상·감축을 권고하지 못하도록 검증 규칙을 적용해줘.

## 15. 후속 질문
현재 선택된 기업·연도·지표·근거 ID를 유지한 채 후속 질문을 할 수 있게 구현해줘. 질문이 바뀌어도 근거 범위를 넘어선 수치는 만들지 않게 해줘.

## 16. GitHub 배포 전 점검
git status와 ignore 파일을 확인해서 .env, 비밀정보, 개인 데이터, 대용량 로컬 산출물이 커밋되지 않도록 점검해줘. 코드 변경 없이 문제 목록만 먼저 보여줘.

## 17. Vercel 설정 점검
api/index.py와 vercel.json을 확인해서 루트 화면과 API가 Vercel에서 같은 앱으로 동작하는지 점검해줘. 필요한 환경변수 이름과 배포 후 검증 URL을 정리해줘.

## 18. 최종 재현 검증
처음 보는 사람이 README만 보고 설치·실행·기업 검색·비교·health 확인을 재현할 수 있는지 점검해줘. 빠진 단계가 있으면 README를 수정하고 실제 검증 결과를 기록해줘.

## GitHub 수동 배포 체크리스트
1. \`github.com/new\`에서 \`dart-hr-agent\` 저장소를 만듭니다.
2. 로컬 프로젝트에 README와 \`.gitignore\`가 있으므로 GitHub의 초기화 옵션은 선택하지 않습니다.
3. \`git init\`을 실행한 뒤 \`git check-ignore .env\`와 \`git ls-files .env\`로 .env가 제외되고 이미 추적되지 않았는지 확인합니다.
4. \`git add .\` 뒤 \`git diff --cached --name-only\`와 \`git diff --cached\`로 실제 커밋 대상을 검토합니다.
5. \`git commit\` → \`git branch -M main\` → \`git remote add origin\` → \`git push -u origin main\` 순서로 실행합니다.
6. GitHub 웹에서 README, \`api/index.py\`, \`vercel.json\`, 최신 커밋을 확인합니다.

## Vercel 수동 배포 체크리스트
1. \`vercel.com/new\`에서 GitHub를 연결하고 방금 만든 저장소를 Import합니다.
2. Framework Preset은 \`Other\`, Root Directory는 \`./\`로 두고 Build/Output은 별도로 Override하지 않습니다.
3. \`OPENDART_API_KEY\`는 Production 환경에서 Sensitive를 켭니다. AI 키는 각 수강생이 브라우저 화면에 직접 입력하고 서버에 저장하지 않습니다.
4. Deploy를 누르고 Building → Ready를 확인합니다.
5. 공개 루트 URL, \`/api/health\`, 합성 샘플을 같은 배포에서 확인합니다.
6. 환경변수를 바꿨다면 반드시 새 배포를 만들거나 Redeploy합니다.
`;
fs.writeFileSync(path.join(deckDir, 'participant-prompts.md'), prompts, 'utf8');

console.log(`Generated ${slides.length} slides in ${deckDir}`);
