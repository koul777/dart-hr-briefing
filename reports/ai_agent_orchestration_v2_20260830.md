# AI Agent 오케스트레이션 v2 작업 기록

작업일: 2026-08-30
상태: 8시간 지속 작업 완료 (2026-08-30 15:47:53–23:47:53 KST)
대상: DART HR Briefing / Workforce Intelligence

## 결론

프로그램의 다음 방향은 “AI 에이전트 수를 늘리는 것”이 아니라, OpenDART 사실 계층을
결정적으로 만든 뒤 선택형 AI 해석을 그 바깥에 두는 것이다. 이번 작업은 기존 분석 경로를
다음 네 가지 운영 원칙으로 재구성했다.

1. 모든 수치는 원천 컴포넌트·접수번호·공식 URL·원자료 지문까지 추적한다.
2. 입력·품질·개인정보·근거 정책이 실패하면 AI 호출을 실행하지 않는다.
3. AI 출력은 같은 문장 안의 허용된 evidence와 수치가 일치할 때만 유지한다.
4. 각 단계의 성공·오류·차단을 trace로 남기고, guard 자체가 실패해도 AI 원문을 폐기한다.

## Codex–Claude 토론 기록

실제 Claude CLI의 동일 세션(`7d26e921-ad83-4b99-94c6-ac95e61d1e15`, Claude Sonnet 5)을
읽기 전용 검토자로 사용했다. Codex가 구현하고 Claude가 반론·재현 경로를 제시한 뒤,
Codex가 코드와 테스트로 독립 확인하는 방식으로 초기 반론과 종료 구간의 집중 재감사를 반복했다.

### 1차: 기존 구조에 대한 반론

Claude가 제기한 핵심 위험은 다음과 같았다.

- 서버에 기존 `AnalysisOrchestrator` 경로가 남아 guard를 우회할 수 있음
- `view`·`metric_ids`가 allowlist 없이 provider prompt에 들어갈 수 있음
- Strategy GET이 사용자 동의 없이 유료 AI를 호출할 수 있음
- 수치 일치 허용오차가 너무 커 거친 단위 표기로 모순을 숨길 수 있음
- 개인 이름을 새로 만들어내는 출력에 대한 감지가 없음
- schema가 CI에만 있고 실제 HTTP 경계에서 선택 검증할 수 없음
- evidence ID가 화면에서 공식 원문 링크로 연결되지 않음

### 2차: 구현 우선순위 합의

양측은 다음 순서에 합의했다.

- P0: GET의 provider를 서버에서 `None`으로 강제, 단일·범위 분석의 legacy 경로 제거,
  `view`·`metric_ids` 이중 allowlist, 표시 정밀도와 0.5% materiality cap을 결합한 수치 검증
- P1: 가공 인명 경고, 명시적 “AI on demand” UX, 프로세스 단위 rate limit 공개
- P2: 공식 DART 원문으로 연결되는 evidence 링크, opt-in runtime schema 검사

### 3차: 수정본 최종 반론 감사

Claude는 현재 작업트리와 전체 테스트를 직접 다시 읽고 다음과 같이 판정했다.

- 기존 8개 지적은 모두 해결됨
- `provider_output_guard` 자체 실패 시 원문이 남던 추가 fail-open 경로도 닫힘
- 새 P0 보안·정확성 결함은 발견되지 않음
- 한글 조사와 일반 리더십 용어를 가공 인명으로 오경고하는 P1 한 건을 재현

마지막 P1은 다음 네 문장을 회귀 fixture로 추가한 뒤 수정했다.

- `이사회는 사외이사 비율을 유지하고 있습니다.`
- `경영진은 최근 임원 승계 계획을 강화했습니다.`
- `경영진이 이사회 구성을 개편했습니다.`
- `이사회의 사내이사 비중이 감소했습니다.`

조사 제거 전후의 알려진 일반 용어·기업명을 비교하고, 직함 정규식이 `이사회` 안의
`이사`를 부분 일치하지 않게 했다. 이 감지는 아직 warning 전용이며 hard reject가 아니다.

### 독립 백엔드·프런트엔드 교차 감사

최종 Claude 반론 전에 백엔드와 프런트엔드를 서로 다른 읽기 전용 검토자에게 분리했다.
백엔드 검토는 source/evidence/provider/response guard, HTTP, 정규화, 어댑터와 런타임
제어를 대상으로 183개 핵심 테스트를 다시 실행했으며 P0/P1을 찾지 못했다.

프런트엔드 검토는 재현 가능한 P1 두 건을 찾았다. 음수 영업이익률·부채비율이 산점도
한쪽 끝에 겹치던 축을 0 포함 signed range로 바꿨고, 0명 하위행이 유효한 성별 급여·근속
가중평균을 `null`로 만들던 계산은 양수 가중치 행만 기여하도록 고쳤다. 모든 음수 값,
음수·0·양수 혼합, 0명+양수 인원, 양수 인원 값 누락을 headless Edge 회귀에 추가해 통과했다.
후속 재검토에서 영업이익 0의 CSS 최소 높이까지 발견해 signed 축에서는 0px로 고정했고,
실제 렌더링 기하를 측정한 뒤 잔여 P0/P1 없음 판정을 받았다.

### 종료 구간 Claude 집중 재감사

Claude의 전체 읽기 전용 재감사는 새 P0/P1 없음으로 끝났지만, Codex가 후속 수치 불변식
감사에서 직접 DAG의 모순된 파생비율과 회계식을 재현했다. 파생 재무비율은 원시 분자·분모와
일치해야 하고, 자산=부채+자본 및 현금·유동자산·유동부채의 상위 총계 관계도 입력 단계에서
검증하도록 수정했다. 첫 회계식 허용오차가 기업 규모에 따라 커지는 P1은 Claude가 재현했고,
규모와 무관한 고정 1원 허용치 및 400조원 규모 회귀로 교체했다. 동일 세션의 수정 확인은
P1 해결·새 P0/P1 없음으로 끝났다. 유한 재무값과 파생값에는 도메인 파서와 같은 `1e21`
절댓값 상한을 적용했다.

Claude 최종·집중 재감사 판정과 P1 처리 이력은
[`overnight_sessions/claude-review-20260830-2150.md`](overnight_sessions/claude-review-20260830-2150.md)에 고정했다.

## v2 실행 흐름

```text
source_snapshot
      |
input_validator
      |
      +----------------------+----------------------+
      |                      |                      |
employee_normalizer  executive_normalizer  compensation_normalizer
      +----------------------+----------------------+
                             |
                      quality_auditor
                             |
                    benchmark_calculator
                             |
                       privacy_guard
                             |
                       evidence_ledger
                             |
                       provider_policy
                             |
                    strategy_interpreter
                             |
                   provider_output_guard
                             |
                       response_guard
```

## 구현된 안전 계약

### 결정적 실행과 계보

- `observation_id`: 기업·연도·보고서 조합의 결정적 ID
- `content_fingerprint`: 개인 필드를 제외한 원자료의 SHA-256 기반 지문
- `run_id`: 관측 ID와 원자료 지문 묶음의 결정적 실행 ID
- `EV-xxxxxxxxxxxx`: 지표·값·단위·기업·연도·원천 컴포넌트·접수번호를 연결한 근거 ID
- 재무·직원·임원·미등기임원 보수를 `source_by_component`로 분리
- 공식 `https://dart.fss.or.kr` 또는 `https://opendart.fss.or.kr` 링크만 노출

### 입력·데이터 품질

- 중복 관측과 중복 기업 코드 차단
- 연도·보고서·행 컬렉션·재무/출처 구조 검증
- `NaN`, `Infinity`, 음수·분수 인원 배제, 공시된 0은 유지
- 재무 비율은 양수 분모만 허용하고 부채·유동성 비율의 음수 분자를 차단해 자본잠식을 낮은 부채비율로 오인하지 않음
- 직접 DAG 입력에서도 음수 자산·부채·현금·유동 항목·부채/유동비율을 provider 전에 차단하고 파생비율 분모를 양수로 제한
- 여러 사업부 전체 행 보존, 공시 평균급여의 인원 가중값 우선
- 일부 행만 값이 있는 additive 합계를 전체 합계로 내보내지 않고 부분 행 경고를 기록
- 임기 만료 기준일을 실행일이 아닌 보고기간 말일로 고정하고 달력 기준 12개월 경계를 사용
- 임원 성별·직위·등기·상근 정보의 부분/전체 누락을 false zero와 분리
- 일부 컴포넌트만 실패한 기업은 다른 기업과 정상 컴포넌트를 유지
- 원천 오류가 있는 기업은 다른 컴포넌트가 partial이어도 error 우선순위를 유지해 provider에서 격리
- 일반 재무/People 단건·추이 조회도 future별 예외를 기업·연도 단위 오류로 격리

### Provider 정책과 출력 검증

- 입력·개인정보·evidence 조건을 통과한 관측만 provider context로 전달
- 최대 160개 evidence, 최대 10개 요청 지표, 기업별 균형 표본
- 질문 경계 문자를 escape하고 `view`·`metric_ids`를 HTTP와 DAG에서 이중 allowlist
- 민감 키·개인 원문·알 수 없는/형식 오류/컨텍스트 밖 evidence 인용 차단
- 수치 주장은 같은 텍스트 필드·같은 줄의 evidence와 값·단위가 일치해야 함
- 표시 반올림 오차는 허용하되 실제 evidence 값의 0.5%를 최대 허용치로 제한
- guard 또는 최종 response guard가 실패하면 provider 결과를 강제로 `rejected` 처리
- 구조화 결과의 순환 참조·빈 값·scalar도 안전하게 거부
- provider 결과는 strict JSON·UTF-8·256KiB 경계를 적용하고 bidi/서러게이트 제어문자를 거부

### HTTP·런타임·어댑터

- GET `/api/workforce/orchestration`은 헤더와 무관하게 `provider=None`
- `/api/analysis`만 명시적 AI 생성 POST이고 `/api/analysis/context`는 생성하지 않음
- 비교 계열 GET은 `corp_code` 단건이 아니라 `corp_codes` CSV 계약을 사용하고, POST도 같은 의미의 `corp_codes` 배열/문자열만 허용
- HTTP 요청 DTO를 `analysis_contract.py`로 분리해 서버의 구형 `orchestrator.py` import를 제거
- 기간 AI는 기간 evidence 계약 전까지 두 POST 경로 모두 `422` fail-closed
- 프로세스 단위 TTL/LRU 캐시·sliding-window rate limit과 익명화된 클라이언트 키
- health에 `scope: per_process`, `distributed_enforcement: false` 공개
- 질문·기업·run ID를 저장하지 않는 상태/정책/provider/검증/evidence 집계 telemetry 공개
- telemetry 자체 실패는 응답과 분리하고 오류 유형만 correlation ID와 기록
- 오류 응답과 로그를 `X-Request-ID`로 연결하고 내부 예외·인증값은 비공개
- OpenAI·Claude MCP 응답은 2MB 상한, provider 오류문은 사용자 응답에 반사하지 않음
- OpenDART·OpenAI·Claude MCP의 HTTP 오류 응답은 재시도·반환·예외 경로에서 즉시 닫아 연결 자원 누수를 방지
- HTTP·OpenAI·Claude MCP JSON에서 `NaN`·`Infinity` 같은 비표준 상수를 거부
- 원격 Claude MCP gateway는 HTTPS만 허용하고 로컬 루프백만 HTTP 예외
- MCP 응답 request ID 일치와 안전한 오류 코드 형식 검증
- OpenDART 응답 25MB, 기업목록 XML 100MB, 기업 캐시 40MB 상한
- 단일 추이 요청의 기업×연도 fan-out을 재무 48개, People/임원 32개 관측으로 제한
- 기업 캐시는 스키마·중복·길이를 검증하고 임시 파일에서 원자적으로 교체하며 검색어는 100자로 제한
- 동일 OpenDART cache key의 동시 miss는 64개 striped lock으로 single-flight 처리
- 로컬 서버는 loopback Host와 정확히 일치하는 Origin만 허용하고 cross-site Fetch Metadata를 거부해 DNS rebinding/GET CSRF를 차단
- Host·Origin의 userinfo, 비정상·범위 초과 포트, 경로·쿼리·fragment 혼입도 거부
- 분석 POST는 2MB 이하 `application/json`만 허용하고 HTTP 서버 배너에서 Python 버전을 숨김
- `.env`는 앱·실행파일 위치와 `DARTStructure.spec`으로 확인한 표준 `dist` 상위만 읽고 임의 현재 작업 폴더는 무시하며 프로세스 환경변수를 우선
- strict schema 모드는 validator를 시작 시 선로딩하고 health에서 활성·준비 상태를 각각 공개
- 직접 DAG도 파생 재무비율, 회계등식, 재무 상하위 총계, `1e21` 수치 상한을 provider 전에 검증

## 응답·스키마·평가

- 기계 계약: `schemas/workforce_orchestration_v2.schema.json`
- 대표 비개인 fixture: `fixtures/workforce/representative_2024_11011.json`
- 혼합 실패 fixture: `fixtures/workforce/edge_cases_2024_11011.json`
- 독립 scorecard: `orchestration_evaluation.py`
- 기본 런타임 guard는 항상 실행
- `DART_STRICT_ORCHESTRATION_SCHEMA=true`이면 HTTP 전송 직전에도 JSON Schema 검증
- PyInstaller spec에 `static`, `schemas`, `HR_BRIEFING_RULES.md`를 모두 포함
- frozen 기업 캐시는 실행 파일 옆이 아닌 사용자 쓰기 가능 `%LOCALAPPDATA%\DART-HR-Briefing` 사용

## 프런트엔드

- Strategy 탭 진입만으로는 AI를 호출하지 않으며 비용이 발생하지 않는다는 문구 표시
- AI 생성은 사용자가 `AI에게 질문하기`를 누른 POST에서만 실행
- 정확히 ledger에 존재하는 EV 토큰만 공식 DART URL 또는 14자리 접수번호 링크로 렌더링
- 알 수 없는·형식 오류·비공식 URL의 citation은 escaped plain text로 유지
- run ID, quality, policy, trace, evidence 원문을 Strategy Brief에서 확인 가능
- 선택·검색·Strategy·AI 응답은 요청 토큰으로 화면 컨텍스트에 묶고, AI 요청은 `AbortController`로 취소
- 연도·보고서·탭·지표 변경도 진행 중 AI 요청을 취소하고 pending UI를 제거
- 질문·최근 대화·복사용 구조화 handoff에서 API key·Bearer·token 형태를 provider 전 마스킹
- 산점도는 0을 포함한 signed range를 사용해 음수 수익성·부채비율의 순서를 보존
- 가중평균은 0명 행을 제외하되 양수 인원 행의 누락값은 계속 fail-closed 처리
- CSV 문자열이 `=`, `+`, `-`, `@`로 시작하면 수식으로 실행되지 않게 보호
- ARIA roving tab과 좌우/Home/End 키보드 이동을 지원

## 검증 근거

- `demo-video-skill`을 `C:\Users\dd\.codex\skills\demo-video-skill`에 공식 설치 도우미로 설치하고
  원문 `SKILL.md`와 전체 playbook을 적용
- 사용자 참조 영상(11.52초·1280×720·24fps)의 짧은 홍보 리듬을 분석한 뒤, 실제 앱을
  Playwright headless Chrome으로 조작하는 26.3초·1920×1080·30fps 대표 시연 씬 제작
- 기업 선택 → 비교 조회 → Strategy Brief → Run ID·quality gate·공시 원문·trace 흐름을
  자막·기능 라벨·가짜 커서·1.3배 줌으로 녹화하고, 측정된 조회 대기 구간만 6배속 압축
- 최종 영상 전체 디코딩, 3×3 몽타주 육안검사, 5개 시점 스팟검사, 브라우저 실제 재생
  (`readyState=4`, `video/mp4` 200, 1920×1080, duration 26.3초) 통과
- README 최상단에 13.2초 2배속 GIF 티저를 배치하고 MP4 원본·브라우저 플레이어 연결
- 전체 `pytest`·`unittest`: 각각 249개 회귀 통과
- branch coverage: 전체 82%, 핵심 v2 DAG 93%, 인력 분석 95%
- Python 3.12·3.13 전체 회귀 249개 호환 확인
- Python 3.11·3.14 선택 회귀 244개 통과(`jsonschema` 미설치 환경이라 스키마 전용 모듈 제외)
- Ruff, Python compile, `node --check` 통과
- schema fixture와 invalid/no-data/rejected-provider 응답 검증 통과
- 실제 삼성전자 2024 사업보고서: schema v2, evidence 41건, source 4종 확인
- 실제 삼성전자·LG전자 2024: 입력·회계 불변식 통과, evidence 82/82건 원문 연결 확인
- 삼성전자 2024 반기 41/41건 completed, 1·3분기 각 27/27건 partial 응답과 trace 무오류 확인
- `/api/analysis/context`: provider 미호출, prompt handoff와 요청 allowlist 확인
- 기간 context/analysis: `422 range_ai_requires_orchestration_v2` 확인
- headless Edge: evidence 링크 안전성, run ID, 숫자 경계, 키보드 탭, 원자적 비교 커밋, stale/기간 변경 AI 취소, 첫 요청 API 키, CSV 수식 경계, 다크 테마, 390px 모바일 렌더링 확인
- `tools/packaged_runtime_smoke.py`로 격리 frozen 최종 빌드(`build-final-20260830-221936`)를 검증했고, health ok·root HTML·schema v2·evidence 41/41건 원문 연결을 확인
- 최종 EXE의 PyInstaller CArchive를 직접 읽어 내장 HTML·CSS·JS·schema·브리핑 규칙이 동결 소스와 바이트 단위로 일치하고 `.env`·테스트·리포트가 제외됨을 확인
- `tools/artifact_manifest.py --include-session-artifacts`로 latest candidate·matching smoke·benchmark·runtime audit 해시 묶음을 자동 생성
- 결정적 benchmark 100회: p50 4.064ms, p95 4.639ms, 최대 응답 81,160 bytes, 예산 통과
- 추가 provider-free 성능 소크 1,000회: p95 7.780ms, 최대 응답 81,161 bytes, 예산 통과
- edge fixture benchmark 200회: p95 2.910ms, 최대 응답 23,474 bytes, 예산 통과
- 최대 8개 기업 합성 benchmark 100회: p95 13.945ms, 근거 232건, 응답 304,374 bytes로 1 MiB 예산 통과
- Archify 다이어그램: 9/9 validation, light/dark 다중 viewport containment 통과
- 격리 PyInstaller: strict schema 활성 상태에서 health·HTML·실제 OpenDART smoke 통과
- frozen cold-cache 동시 5요청의 동일 run ID·41/41 근거와 30회 허용/31번째 `429` rate-limit 경계 확인
- 공유 오케스트레이터 16스레드·2,000호출 소크에서 동일 run ID·58개 근거·검증 통과·trace 오류 0건 확인
- 전체 249개 회귀 두 회차 누적 45회 반복(총 11,205 실행)에서 비결정적 실패 0건
- 120개 seeded 변이 퍼즈 계약 50회 반복(총 6,000 케이스 실행)에서 실패 0건

격리 최종 빌드:

- 경로: `reports/overnight_sessions/build-final-20260830-221936/dist/DARTStructure.exe`
- 크기: 16,720,583 bytes
- SHA-256: `9F7E93FD2C043C9707B6D834C386EC230117C3EBEA307CCA1068BEA012DC9B38`
- 기존 사용자 변경 파일 `dist/DARTStructure.exe`는 덮어쓰지 않음

## 남은 한계와 후속 계획

### P1 — 운영 전 필요

1. 공개 serverless 배포에는 KV/Redis/API gateway 기반 분산 rate limit과 비용 예산을 추가한다.
2. 기간 비교용 evidence ledger 계약을 설계한 뒤에만 range AI를 다시 연다.
3. 개인정보 가공 인명 감지기는 실제 오경고율 corpus를 측정하기 전 hard reject로 승격하지 않는다.
4. 공개 배포 후보는 일회성 OpenDART 자격증명으로 live smoke를 수행하고, Windows 버전 리소스·코드 서명·SBOM·provenance attestation을 릴리스 게이트로 둔다.

### P2 — 다음 품질 단계

1. 여러 산업·보고서 유형·무자료·부분공시를 포함한 fixture corpus를 확대한다.
2. 구조화 provider가 도입되면 field-local citation 계약을 명시하고 cross-field 인용을 테스트한다.
3. 서버에서 완전히 격리된 구형 `orchestrator.py`는 호환 테스트가 더 이상 필요 없을 때 제거한다.
4. 브라우저 접근성 자동검사와 모바일 viewport 회귀를 CI에 추가한다.
5. 실제 운영 관측에서는 개인·질문 본문 없이 정책 차단률, 근거 인용률, provider 거부율만 집계한다.
6. 계약 회귀를 유지한 채 `do_GET`, 입력 validator, 결과 평가기의 고복잡도 분기를 작은 순수
   함수와 라우트 테이블로 분해하고 C901 추이를 품질 게이트로 관리한다.
7. `server.py`의 현재 결합 coverage 72%를 process-level HTTP 오류·종료·live 라우트 회귀로
   80% 이상까지 올리고, 전체 75% 게이트와 별도로 서버 최소치를 둔다.

## 최종 의사결정

Codex와 Claude의 합의는 동일하다. 이 프로그램은 “AI가 DART를 대신 해석하는 대시보드”가
아니라 “결정적 DART 사실·계보·품질 엔진 위에 비용과 실패가 격리된 AI 해석을 올린 제품”으로
발전해야 한다. 다음 기능은 에이전트 수가 아니라 evidence coverage, policy bypass 0건,
수치 근거율, 부분 실패 복구율로 우선순위를 판단한다.
