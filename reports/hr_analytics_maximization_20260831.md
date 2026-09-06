# DART HR Briefing · HR Analytics 최대화 감리 및 개선 기록

- 작업일: 2026-08-31 KST
- 작업 세션: 6시간 지속 오케스트레이션
- 기준 저장소: `C:\workspace\dart`
- 상태: 구현·소스/브라우저·Claude HRMCP 재감리·최종 패키지 검증 완료

## 1. 결론

이번 작업은 제품을 “공시 숫자 대시보드”에서 “공시로 무엇을 판단할 수 있고 무엇을 보류해야 하는지 설명하는 HR 검토 우선순위 브리프”로 이동시켰다.

핵심 변화는 다음과 같다.

1. AI 없이도 동일 입력에 동일 결과를 내는 `DecisionSupportAgent`를 추가했다.
2. 생산성·보상 지속가능성·인력구조·리더십 연속성·근거 연결 완전성의 readiness를 `ready / directional_only / blocked`로 구분한다.
3. 다중 지표 질문을 가장 잘 채워진 한 지표만으로 판정하지 않고, 선언된 모든 후보 지표의 커버리지를 readiness에 반영한다.
4. 각 주 브리프에 대표 지표, 선정 이유, 후보 지표별 비교 가능 기업 수, 선택 기업 집합 중앙값 위치, 근거 ID, 판단 한계, 다음 내부 데이터를 연결한다.
5. 별도 이력 API의 2시점 방향은 `readiness 산정 제외`라고 명시해 단일연도 서버 계약과 화면 의미를 맞췄다.
6. AI 출력의 무근거 수치·인용 모순·인과 단정·가공 인물/직함 언급을 fail-closed로 거부한다.
7. Overview 첫 화면에서 readiness와 원문 연결률을 백그라운드로 미리 계산하며, 계산 중 상태도 숨기지 않는다.

이 결과는 “의사결정을 대신하는 AI”가 아니다. 공개 DART 집계로 검증 가능한 상대 위치와 데이터 공백을 보여 주고, 실제 결정 전에 어떤 내부 HR 데이터를 붙여야 하는지 안내하는 triage 계층이다.

## 2. 감리 구성

### Claude 독립 감리

- Claude Code 2.1.251
- 모델: Sonnet
- 노력 수준: high
- 세션 ID: `126a4521-0b33-4607-a00c-8b1a91ebad1d`
- 실행 정책: plan/read-only, `Bash,Write,Edit,NotebookEdit` 비허용
- 초기 발견:
  - provider 인과 단정이 런타임에서 완전히 막히지 않음
  - 가공 인물 판단이 경고에 머무름
  - 평균 급여 계산 근거가 화면에 약함
  - 정정공시 최신 여부 검증이 없음
  - 전역 readout이 재무 중심
  - strict schema 기본값이 꺼져 있음

초기 HRMCP 호출은 Claude 서비스의 세션 한도 `HTTP 429`로 중단됐지만, 2026-08-31 02:50 KST 리셋 후 같은 세션에서 실제 read-only 호출에 성공했다.

- `mcp__claude_ai_HRMCP__ncs_search`
  - 고수준 인자: `query="인사전략 인력운영 보상관리"`, `limit=10`
  - 핵심 결과: `인사기획(0202020101_23v3, 수준 6)`, `인력이동관리(0202020104_23v4, 수준 5)` 등
- `mcp__claude_ai_HRMCP__ncs_unit_detail`
  - 고수준 인자: `unit_code="0202020101_23v3"`
  - 핵심 결과: 인사전략 수립·인력운영계획 수립·인건비 운영계획 수립의 3개 요소와 수행준거·KSA

NCS 결과는 HR 과업 분해와 내부 검증 데이터의 방법론적 참고로만 사용했고, 특정 기업의 DART 수치·비교 결론·인과관계 근거로 사용하지 않았다. Claude는 최신 디스크 12개 코드·계약 파일을 다시 읽은 최종 감리에서 P0/P1 없음, 필수 변경 없음, 통과로 판정했다.

### 병렬 에이전트 재감리

| 감리자 | 관점 | 핵심 재발견 | 처리 |
|---|---|---|---|
| Gibbs | 백엔드·보안 | 보조 지표 하나만으로 false-ready, 가공 이름 warning-only | 다중 지표 readiness, 이름+직함 fail-closed |
| Zeno | 프런트·접근성 | Overview 전역 readiness 지연, People 부분값 전체 blank, 모바일 라벨 7px | preload, 부분 커버리지 표시, 9px 상향 |
| Aquinas | HR 도메인 | 대표 지표 불투명, self trajectory 계약 불일치, 일반적 결론, 과도한 confidence | 대표/후보 공개, 비산정 표시, 회사별 중앙값 결론, 보수적 confidence |

후속 감리에서 Gibbs는 응답이 `schema_version: 2`를 스스로 선언할 때만 strict 검증되는 fail-open을 발견했다. 오케스트레이션 엔드포인트를 명시적 검증 경계로 바꾸고 버전 누락·`1`·문자열 `"2"`를 모두 500으로 닫았다. Zeno는 390px에서 긴 판단 행동·코호트 한계·readiness 라벨이 잘리는 회귀를 자동 탐지하도록 QA를 확장했다. Aquinas는 이력 제외가 confidence 계산에 직접 들어가지 않는다는 의미를 문서와 구현에서 다시 일치시켰다.

실제 4개사 partial-quality 화면의 추가 감리에서 Zeno는 정정공시 최신성 경고가 Decision Brief가 아니라 데스크톱 약 5,654px·모바일 약 11,918px 아래 Evidence 영역에만 있어 `ready + low`를 즉시 해석하기 어렵다는 P1을 발견했다. 경고를 readiness matrix 앞에 올리고 “표본·원문 조건 충족”과 “부분 품질·최신성 미검증”을 분리해 설명했으며, DOM 순서·문구·390px wrapping을 브라우저 QA로 고정했다. 세 감리자는 보강 후 잔여 P0/P1 없음으로 판정했다.

## 3. HR Analytics 제품 원칙

### DART로 가능한 것

- 같은 연도·보고서·사용자 선택 기업 집합 안의 상대 비교
- 공시된 인당 매출·인당 영업이익·급여총액/매출·계약직 비중·임기 일정의 점검 신호
- 원문 연결과 공시 품질을 기준으로 한 판단 준비도
- 데이터가 부족할 때 보류 사유와 다음 내부 데이터 제시

### DART만으로 불가능한 것

- 개인·팀 생산성 또는 성과 판정
- 보상 적정성·공정성·개인별 보상 결과
- 이직·몰입·조직문화·고용형태 선택의 원인
- 승계 후보 준비도·이사회 실효성·임원 개인 평가
- 산업·규모 보정을 거친 보편적 peer benchmark

따라서 화면의 `peer`는 “사용자가 선택한 기업 집합의 중앙값”으로 표현하며, 상회/하회를 우열로 번역하지 않는다.

## 4. 결정지원 계약

### 전체 readiness

- `productivity`
- `compensation_sustainability`
- `workforce_structure`
- `governance_continuity`
- `data_completeness`

### 주 브리프 필수 정보

- `question`
- `status`
- `selected_metric_id` / `selected_metric_label`
- `selection_reason`
- `metric_assessments[]`
- `signal_type`
- `peer_context[]`
- `conclusion`
- `decision_action`
- `cohort_limit`
- `evidence_ids[]`
- `confidence`
- `cannot_tell[]`
- `interpretation_limit`
- `next_data[]`
- `self_trajectory.status=not_available`

`metric_assessments`는 각 후보 지표의 상태, 비교 가능 기업 수, 원문 근거, 관련 컴포넌트 품질, 대체 계산 사용 여부를 분리한다. 차원 상태는 모든 후보 지표가 비교 가능하고 대표지표의 비교 가능 기업이 4개 이상일 때만 `ready`가 되며, 일부만 있거나 작은 선택 집합이면 최대 `directional_only`다.

confidence는 의사결정 확률이 아니라 현재 공시 근거의 사용 가능성이다. 선택 기업이 4개 미만이거나 관련 컴포넌트가 부분 품질이면 보수적으로 낮춘다. 이력 제외는 `history_not_in_readiness` reason code로만 노출되며 confidence 계산식에는 직접 포함되지 않는다.

## 5. 구현 변경

### 백엔드와 계약

- `agent_orchestration.py`
  - 결정론적 `DecisionSupportAgent`
  - metric-level signal catalog
  - 다중 지표 readiness
  - 회사별 중앙값 결론
  - 데이터 공백 taxonomy
  - causal/person-reference output guard
  - 결정지원 지표·evidence 참조 무결성 검사
  - 정책 제외 관측치가 없으면 provider에 결정지원을 `available`로 전달하고, 하나라도 있으면 허용 관측치만으로 다시 계산해 `limited`로 전달
  - provider evidence·metric·요약 메타데이터를 런타임과 오프라인에서 재선택해 exact match 검증
  - 정정공시 최신성 미검증 시 근거 연결 완전성 confidence를 `high`로 올리지 않고 `restatement_not_verified` 및 첫 확인 과제 노출
- `static/app.js`
  - 정정공시 최신성 경고를 readiness matrix보다 먼저 노출
  - `ready + low`를 표본 충족과 부분 공시 품질 경고로 분리 설명
  - `policy.mode=limited`를 기업 제외 여부에 따라 “선택 기업 전체 범위 유지” 또는 “허용 기업만 재계산”으로 구분
  - `이익 → 성과급 → 급여 연동` 인과 암시를 제거하고 DART 사실·People 신호·성과급 산식 검증 한계를 병렬 분리
  - 전역 readout에도 정정공시 최신성 미검증을 표시하고 AI 정책 상태를 한국어로 현지화
  - 우선 지표 대신 보조 지표가 대표가 될 때 내부 원장 확인 경고 노출
  - 거버넌스 readiness 행에 `승계 권고 아님`과 첫 내부 확인 과제를 표시하되 행동 브리프로 승격하지 않아 과대해석 방지
  - People 표의 평균 급여 셀마다 회사별 계산 기준을 표시해 공시 평균 가중과 급여총액÷직원 수 대체가 섞여도 기준을 직접 매핑
  - People 상단 평균 급여 KPI에도 단일·혼합 계산 기준을 표시하고 수동 AI 문맥에 회사별 기준을 포함
  - `ready + low`의 품질 원인을 지표별 회사·공시 구성요소로 Strategy 카드에 직접 표시
  - 회사 검색을 combobox/listbox로 구성하고 방향키·Enter·Escape·활성 옵션을 스크린리더 계약으로 고정
  - 브라우저 저장소가 차단돼도 앱 초기화와 테마 전환이 중단되지 않도록 storage 접근을 fail-soft 처리
  - 레이더·산점도·순위에 인과·개인평가·자동 인사조치 금지 경계를 공통 표시
  - People 추이·결정 브리프 실패를 Strategy 탭 내부 경고로 구분하고 재실행 필요를 표시
  - 거버넌스 readiness에서 승계 권고 금지뿐 아니라 직접 알 수 없는 범위를 함께 노출
- `schemas/workforce_orchestration_v2.schema.json`
  - `decision_support` 필수화
  - readiness, brief, metric assessment, peer position, data gap 정의
- `orchestration_evaluation.py`
  - 결정 브리프·지표평가·peer·data gap 변조 탐지
  - `completed/passed`로 변조된 저장 결과의 근거 없는 인과 단정·가공 인물 판단도 공용 정책 헬퍼로 재검사
- `server.py`
  - strict schema 기본값 `true`
  - 오케스트레이션 POST/GET 경계에서 버전 누락·다운그레이드·타입 변조 fail-closed
  - 질문 누락 시에도 재무 요약이 아니라 생산성·보상 지속가능성·인력구조·판단 한계·다음 내부 데이터를 묻는 HR 기본 질문 사용
  - 12개 decision metric과 5개 dimension metadata
  - JSON·정적 응답에 HSTS·CSP·nosniff·frame·referrer·permissions 보안 헤더
- `pyproject.toml` / CI
  - flat-layout 자동 탐색 충돌을 제거하도록 런타임 모듈과 `api` 패키지를 명시
  - CI가 실제 `.[dev]`·`.[build]` extras를 editable 설치해 공개 clone 설치 경로까지 검증
- `tools/artifact_manifest.py`
  - 이전·현재 파일명 규칙을 함께 인식하고 최종 후보와 `build_path`가 일치하는 packaged smoke만 매니페스트에 포함
- `workforce_analytics.py`
  - 평균 급여 계산 기준 공개

### 화면

- Overview 전년 변화 요약
- 비교 직후 readiness·원문 연결 백그라운드 preload
- 5개 readiness matrix와 3개 주 Decision Brief
- 대표 지표·선정 이유·후보 지표 커버리지
- 첫 번째 내부 데이터 과제와 연결된 다음 판단 행동
- 선택 기업 중앙값이 산업·규모·사업모델 비보정 비교라는 고정 한계
- 회사·지표·연도 문맥이 있는 원문 링크
- `cannot tell`과 구체적 다음 내부 데이터
- People KPI의 유효 행 계산 및 `n/m개 기업 사용` 표시
- 별도 이력은 readiness 제외·2시점 방향으로 표시
- 모바일 Strategy 수치 라벨 최소 9px

### 문서와 아키텍처

- `README.md`
- `DART_WORKFORCE_INTELLIGENCE_PLAN.md`
- `DART_WORKFORCE_INTELLIGENCE_RUNBOOK.md`
- `orchestration.workflow.json`
- `orchestration-dart-claude.html`

아키텍처 HTML은 showcase 정적 검증 오류·경고 0, 1440×900부터 2048×1320까지 light/dark overflow 0으로 통과했다.

## 6. 검증 증거

### 소스 회귀와 정적 품질

| 검증 | 결과 |
|---|---|
| Python 3.11·3.12·3.13·3.14 unittest | 각 293 passed |
| 제품 모듈 branch coverage | 84% |
| `agent_orchestration.py` coverage | 92% |
| CI coverage 하한 | 80% |
| Ruff | 통과 |
| compileall | 통과 |
| `node --check` app/QA | 통과 |
| 새 격리 환경 `pip install -e ".[dev]"` | 설치·293 tests·서버/API import 통과 |
| `pip-audit 2.10.1` 프로젝트 감사 | 6개 Python 의존성, 알려진 취약점 0건 |
| CycloneDX 프로젝트 SBOM | 1.4 형식, 6개 Python 구성요소 |
| 안정성 soak | 1,460 test executions·1,200 fuzz cases·16-thread 2,000 calls·200회 메모리 게이트 통과 |

### 성능

- 1,000 iterations, 50 warmups
- provider/network disabled
- p50 8.882ms
- p95 11.303ms
- max 15.999ms
- response 최대 147,413 bytes
- 예산: p95 100ms 이하, 1,000,000 bytes 이하
- 결과: passed
- 최대 8개사 synthetic 100회도 p95 16.940ms, evidence 232개, 응답 426,430 bytes로 동일 예산 통과

### 실제 OpenDART strict 런타임

- 기업: 삼성전자 단독, 삼성전자·SK하이닉스·LG전자 3개사, 삼성전자·SK하이닉스·LG전자·현대자동차 4개사
- 연도/보고서: 2025 / 사업보고서
- schema v2
- status: partial
- 단독 evidence 41/41, 3개사 122/122, 4개사 162/162 source-complete
- trace 14개 에이전트
- response validation: passed
- 주 브리프 3개, 각 후보 지표평가 2개
- 회사별 중앙값 결론과 `small_peer_sample`, `history_not_in_readiness` 이유 확인
- 1개사와 3개사 선택 집합은 주 브리프가 모두 `directional_only/low`
- 4개사에서는 대표 지표 3개와 거버넌스가 `ready/low`였다. 관련 컴포넌트의 부분 품질 때문에 confidence는 `low`로 유지되어 readiness와 근거 품질이 분리됨을 확인했다.
- 세 선택 집합 모두 정정공시 검증은 `not_performed`; 정책상 기업 제외는 0개이며 provider 결정지원 범위는 `available`
- 질문 누락 POST도 HR 기본 질문을 사용하고 기존 재무 전용 기본 문구가 prompt에 없음을 실제 응답에서 확인
- 장시간 소스 프로세스 누적 43회에서 evidence 5,797/5,797 source-complete, trace error 0, 텔레메트리 사용자 콘텐츠 보존 없음
- DART cache 1,883 hits/668 misses, eviction·oversize rejection 0; 반복 QA 과호출 1건은 분당 rate limit이 의도대로 차단

### 브라우저

Headless Edge 실제 서비스 조작에서 다음을 통과했다.

- Overview 변화 요약과 readiness preload/계산 중 상태
- Decision Brief 3개, readiness 5개
- 대표 지표 3개, 후보 지표평가 6개 이상
- evidence badge와 공식 DART URL allowlist
- 데이터 공백 노출
- 키보드 탭
- 키보드 회사 검색(방향키·Enter·Escape)과 combobox/listbox ARIA 상태
- 결측값 false-zero 방지
- People 부분 커버리지 계산
- signed chart
- 비교 원자적 커밋
- stale/기간 변경 AI 취소
- 대화 예산·credential redaction
- CSV formula injection 방어
- dark theme와 390px 모바일 overflow 0
- 390px 판단 행동·코호트 한계·readiness 상세 라벨의 카드 폭·줄바꿈 계약
- 모바일 첫 readout의 정정공시 최신성 미검증 경고와 AI POLICY 한국어 상태
- 보조 대표지표 선택 분기의 내부 원장 확인 경고
- 거버넌스 `승계 권고 아님` 경계와 People 혼합 평균급여 계산기준의 회사별 표시
- 실제 4개사 `ready + low`에서 회사·공시 구성요소별 품질 원인 표시
- light·dark·Strategy 핵심 텍스트 색상 WCAG AA 4.5:1 이상
- 레이더·산점도·순위의 비인과·비개인평가·비자동조치 경계
- People 추이와 결정 브리프 이중 실패의 탭 내부 오류 상태
- `localStorage` 접근 차단 환경의 앱 초기화·테마 전환 fail-soft

### 격리 패키지

- 후보: `reports/overnight_sessions/build-hr-max-20260831-final-v3/dist/DARTStructure.exe`
- 크기: 16,755,245 bytes
- SHA-256: `CC7E3897ABDDDAD8EA2F1CC676A76E6142F8DB259C5C798B29A1F96730EFE2E5`
- 검증된 후보를 `dist/DARTStructure.exe`로 승격했으며 SHA-256이 일치함
- strict schema enabled/validator ready
- root HTML/static assets 정상
- PyInstaller archive에 schema·static·HR rules 포함, `.env`·`corp_codes.json` 포함 0건
- 실제 OpenDART evidence 41/41 source-complete
- 주 브리프 3, readiness 5, metric assessment 6
- provider `not_configured`, deterministic GET에서 AI 미호출
- 패키지 `app.js`·CSS에서 혼합 급여 기준, 회사별 품질 원인, 키보드 검색, 상대비교 경계, 탭 내부 오류, storage fail-soft 기능 마커와 정적 보안 헤더 확인
- 공개 `dist` 실행 파일 health/static 시작·종료 5회 반복 후 잔류 listener 0
- 최종 SHA-256 매니페스트에 실행 파일·matching smoke·최신 benchmark·coverage 포함

## 7. 4시간 교육 커리큘럼 정합성

| 교육 모듈 | 현재 상태 | 검증·잔여 작업 |
|---|---|---|
| 1. 기본 화면·프로젝트 구조 | 완료 | 기업·연도·보고서 선택, 최대 8개, 모바일·접근성 계약 통과 |
| 2. OpenDART 연결·기본 대시보드 | 완료 | 실제 2025년 1·3·4개사와 키 미노출·결측 구분 검증 |
| 3. HR 지표·AI 브리핑 고도화 | 완료 | 결정론적 브리프, evidence, provider guard, 후속 질문·취소 계약 검증 |
| 4. GitHub·Vercel 배포 | 부분 완료 | GitHub public 확인; 이번 로컬 변경의 push와 실제 Vercel URL 배포·검증은 수행하지 않음 |

따라서 교육용 최종 사용자 흐름 중 로컬 앱과 공개 저장소 기반은 준비됐지만, “현재 변경분이 반영된 실제 웹 주소”는 별도 배포 권한과 환경변수 등록 후 확인해야 한다.

## 8. 남은 제한과 다음 계획

1. 정정공시 최신 여부는 아직 자동 판정하지 않고 `not_performed`로 공개한다.
2. 선택 기업 집합은 산업·규모 보정 cohort가 아니다. 추천 peer 기능은 별도 제품 결정이 필요하다.
3. 분산 rate limit·비용 예산은 아직 `per_process`다. 공개 serverless 운영 전 외부 KV/API gateway가 필요하다.
4. 기간 범위 AI는 기간 evidence 계약이 완성될 때까지 fail-closed다.
5. Python 의존성 CycloneDX SBOM은 생성했지만, `Get-AuthenticodeSignature` 결과는 `NotSigned`다. Windows 공개 릴리스에는 코드 서명·바이너리 수준 SBOM·provenance attestation이 추가로 필요하다.
6. 현재 로컬 변경은 원격 저장소에 push하지 않았고 Vercel production URL도 검증하지 않았다. 배포 시 실제 환경변수·분산 제한·최종 smoke를 다시 확인해야 한다.

## 9. 최종 감리 기록

- 실제 호출: `ncs_search`와 `ncs_unit_detail`, 대상 `인사기획 0202020101_23v3`
- 호출 증거: Claude 세션 원본 JSONL의 tool-use/tool-result 이벤트에서 도구명·인자·응답을 교차 확인
- Claude 최신 디스크 판정: P0 없음, P1 없음, 필수 변경 없음, 통과
- 선택 P2 후속 처리:
  - 오프라인 평가기의 completed provider 인과/가공인물 정책 재검사 구현
  - average salary basis는 백엔드 필드·People readout·Strategy 카드에 이미 공개됨을 재확인하고, 혼합 basis 시 People 표 회사별 표시까지 보강
  - NCS KSA의 `인사제도·운영방침 문서`는 기존 원장·성과급 산식·시장보상 기준보다 직접 검증력이 낮아 기본 next_data에는 추가하지 않음
