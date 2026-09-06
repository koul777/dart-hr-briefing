# DART Workforce Intelligence 실행 런북

## 1. 실행

공개 저장소에서 바로 실행하는 검증된 배포 파일은 다음과 같다.

`dist/DARTStructure.exe`

로컬 감사 원본은 `reports/overnight_sessions/build-p0-startup-20260906/dist/DARTStructure.exe`이며
`reports/overnight_sessions/latest-candidate-build-path.txt`가 이 빌드 루트를 가리킨다. 이 경로는
세션 산출물이라 Git에서 제외되지만, strict packaged smoke를 통과한 동일 바이너리를 공개 경로로 승격했으며
후보와 루트 배포 파일의 SHA-256은 `1274728D2222FF16A28441E563FD415A83933250DFEC51319C67EB0760DDA824`로 일치한다.
격리 후보를 실행할 때 OpenDART 키는 프로세스 환경변수로 주입하거나 실행 파일과 같은
`dist` 폴더의 `.env`에 둔다.

소스 모드로 실행하려면:

```powershell
python server.py
```

기본 주소는 `http://127.0.0.1:8765`이다. 기존 프로그램이 포트를 사용 중이면 중복 바인딩하지
않고 다음 빈 로컬 포트를 선택한다. 브라우저는 `/api/health`의 앱 ID·빌드 ID·인스턴스 ID가
방금 시작한 서버와 일치한 뒤 실제 바인딩 주소로만 열린다. `PORT`를 명시한 자동화에서는
점유 시 즉시 실패한다. 화면 왼쪽 아래에서 버전·빌드 ID·실제 포트를 확인한다.
소스 변경분을 패키지에 반영하려면 아래 검증용 빌드 절차를 사용하고,
새 빌드는 격리 후보를 strict smoke로 검증한 뒤에만 `dist/DARTStructure.exe`로 교체한다.

## 2. 시각화 확인 순서

1. 기업 검색창에서 기업명·종목코드·DART 고유번호로 기업을 선택한다.
2. 기준연도와 사업보고서를 선택하고 `재무구조 비교`를 실행한다.
3. `Strategy Brief` 탭으로 이동한다.
4. 다음 시각 요소를 확인한다.
   - `DECISION BRIEF`: 5개 전체 readiness와 3개 주 브리프가 표시되는지 확인
   - 각 브리프의 대표 지표·선정 이유·후보 지표별 커버리지·선택 기업 중앙값·다음 내부 데이터 확인
   - `별도 이력 참고`가 readiness 산정 제외로 표시되는지 확인
   - 상단 intro가 `DART / WORKFORCE INTELLIGENCE`와 인력·보상 벤치마크 문맥으로 전환되는지 확인
   - `LAYER 0`: 이익 체력·People Signal·제한사항을 인과 없이 병렬 분리한 흐름
   - `LAYER 1`: 영업이익 세로형 그룹 막대차트
   - `LAYER 2`: 평균 급여 SVG 추이선과 다음연도 전망 밴드
   - `LAYER 3`: Pay Equity 비율 바·근속 차이·공시 누락 상태
   - `LAYER 3+`: 내부 HR 데이터 연결에 필요한 구체 필드 체크리스트
   - `EVIDENCE`: DART 원문·품질 게이트·에이전트 trace

실제값은 채움/실선으로, 모델 추정은 해칭/점선/`E` 표기로 구분한다. 전망값은 DART에 없는 확정값이 아니라 최근 공시 추세를 화면에서 단순 연장한 값이다.

우측 상단 테마 전환 버튼으로 밝은/어두운 테마를 바꾼 뒤 Strategy 전체와 일반 탭에서 대비와 레이아웃이 유지되는지 확인한다.

## 3. AI 분석 질문

사이드바의 `AI 분석 질문`에 다음과 같은 질문을 입력한다.

- `영업이익이 증가한 기업의 평균 급여도 함께 증가했나?`
- `두 기업의 임원구조와 HR 전략상 확인할 추가 데이터를 비교해줘.`
- `Pay Equity 공시가 없는 기업에서 어떤 검증 절차가 필요한가?`

`AI 분석 실행`은 선택 기업의 단일 기준연도 재무·People 원자료를
`/api/analysis`의 v2 오케스트레이터로 전달한다. 입력·품질·개인정보·근거 정책을
통과한 지표만 provider context에 포함된다. provider가 연결되지 않은 경우에도
`not_configured` 상태, evidence ledger, 근거 기반 prompt handoff를 표시한다.
정책상 제외 관측치가 없을 때 결정지원 브리프를 `available`로 AI에 전달한다. 제외 관측치가
하나라도 있으면 허용 관측치만으로 브리프를 다시 계산해 `limited`로 전달하며, 제외 기업을
명시하고 화면의 전체 브리프와 AI의 실제 근거 범위를 구분한다. 런타임과 오프라인 감사기는
provider evidence 선택 전체를 재계산해 요약과 exact match인지 확인한다.

연도 범위 AI 생성은 지표별 기간 evidence 계약이 완성될 때까지 `422`와
`range_ai_requires_orchestration_v2`로 차단한다. 범위 데이터를 생성 없이 점검할 때는
`/api/analysis/context`를 사용한다.

비교 계열 GET `/api/financials`, `/api/people`, `/api/people/history`,
`/api/workforce/orchestration`는 `corp_code`가 아니라 `corp_codes=00126380,00401731`
형식의 쿼리 문자열을 사용한다. POST `/api/analysis`, `/api/analysis/context`도
동일한 의미의 `corp_codes` 배열 또는 콤마 구분 문자열을 입력으로 받는다.

gateway가 오류를 반환하면 provider 결과를 성공 답변으로 표시하지 않고 `error` 상태로 분리한다. 오류가 있어도 DART 관측값·출처·프롬프트 handoff는 유지한다.

provider 출력의 개인정보, 알 수 없는 evidence ID, 같은 줄에 근거가 없는 수치,
인용 evidence와 모순되는 수치, 근거 없는 인과 단정, 입력에 없는 이름+임원직함 언급은
`rejected`로 바뀌며 원문 결과는 응답에서 제거된다.

## 4. Claude MCP gateway 선택 연결

`.env`에 다음 선택 설정을 추가한다.

```text
CLAUDE_MCP_GATEWAY_URL=
CLAUDE_MCP_GATEWAY_TOKEN=
CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS=20
```

토큰은 화면·응답·trace에 노출하지 않는다. AI는 DART의 데이터 원천이 아니며, 공시된 집계값을 설명하는 보조 계층이다.

추이 조회는 한 HTTP 요청에서 재무 최대 48개, People/임원 최대 32개의 기업×연도 관측으로
제한된다. 더 큰 비교는 기업 또는 기간을 나눠 실행한다.

## 5. 품질 기준

- `py -3.12 -m unittest discover -v`: 302개 테스트 통과
- `py -3.12 -m coverage run --branch -m unittest discover` 후 `py -3.12 -m coverage report -m`: 제품 모듈 branch 84%, 핵심 v2 DAG 92%
- `py -3.12 tools/benchmark_orchestration.py --iterations 1000 --warmups 50`: provider·network 없이 p50 8.882ms, p95 11.303ms, max 15.999ms, 최대 응답 147,413 bytes 예산 확인
- `ruff check .`: 통과
- `python -m compileall -q .`: 통과
- `node --check static/app.js` 및 `node --check tools/qa_orchestration_v2.js`: 통과
- 새 Python 3.12 venv에서 `python -m pip install -e ".[dev]"` 후 전체 302개 테스트와 `api.index`·`server` import 통과
- `pip-audit` 프로젝트 감사: Python 의존성 6개, 알려진 취약점 0건; `reports/overnight_sessions/sbom-cyclonedx-final.json` 생성
- `py -3.12 tools/packaged_runtime_smoke.py --exe dist/DARTStructure.exe --working-directory reports/overnight_sessions/smoke-p0-startup-20260906 --port 8784 --year 2024 --strict-schema`: 앱 ID·버전·빌드·인스턴스 식별, health ok, root HTML 응답, schema v2, evidence 41/41건 원문 연결, 결정 브리프 3개·readiness 5개·지표평가 6개 확인
- `python tools/artifact_manifest.py --include-session-artifacts --output reports/overnight_sessions/artifact-manifest-final.json`: 최종 후보·matching smoke·benchmark·runtime audit SHA-256 묶음 생성
- 이번 HR Analytics 최대화 변경분은 Python 3.11·3.12·3.13·3.14에서 전체 회귀를 검증했고 strict packaged smoke를 별도로 확인했다. 지원 Python 버전별 매트릭스는 CI가 동일 302개 계약을 실행해야 한다.
- headless Edge 4개사 QA: Overview readiness preload·3개 결정 브리프·5개 readiness·`ready + low` 회사별 품질 원인·대표/후보 지표·근거 링크·unsafe URL 비링크·숫자 경계·People 부분 커버리지·키보드 탭·원자적 비교 커밋·stale/기간 변경 AI 취소·첫 요청 API 키·CSV 수식 경계·다크/390px 모바일 확인
- JSON·정적 응답은 `Strict-Transport-Security: max-age=31536000`, `nosniff`, `no-referrer`, `DENY`, `Permissions-Policy`를 내보내며 정적 자산에는 CSP도 적용한다.

HSTS는 HTTPS로 전달된 응답에서 브라우저가 적용하는 정책이다. 이 앱 서버가 TLS를 직접 종단하거나 로컬 `http://127.0.0.1`을 HTTPS로 바꾸는 기능은 아니므로, 공개 배포에서는 신뢰할 수 있는 프록시·플랫폼의 HTTPS 종단을 별도로 유지한다.

격리 빌드는 기존 배포 파일을 덮어쓰지 않는 새 디렉터리에서 수행한다.

```powershell
$buildRoot = Join-Path (Resolve-Path 'reports\overnight_sessions') 'build-manual'
python -m PyInstaller --noconfirm --clean `
  --distpath (Join-Path $buildRoot 'dist') `
  --workpath (Join-Path $buildRoot 'work') `
  DARTStructure.spec
```

## 6. 런타임 보호 설정

```text
DART_CACHE_TTL_SECONDS=300
DART_CACHE_MAX_ENTRIES=512
DART_CACHE_MAX_BYTES=67108864
DART_DATA_DIR=
DART_RETRY_ATTEMPTS=3
DART_RETRY_BASE_DELAY_MS=250
DART_RATE_LIMIT_PER_MINUTE=30
DART_RATE_LIMIT_MAX_CLIENTS=4096
DART_OPEN_BROWSER=true
DART_STRICT_ORCHESTRATION_SCHEMA=true
```

`DART_DATA_DIR`가 비어 있으면 소스 실행은 프로젝트 `data`, frozen 실행은
`%LOCALAPPDATA%\DART-HR-Briefing`, Vercel은 `/tmp/dart-workforce`를 사용한다.

`/api/health`의 `runtime`에는 캐시·요청 제한·오케스트레이션의 집계 통계만 표시되며 IP, 질문, 기업 ID, API Key는
남기지 않는다. 오류 응답과 서버 로그는 공통 `X-Request-ID`로 연계하고 내부 예외 상세와
인증 값은 공개 응답에 포함하지 않는다.

캐시와 요청 제한의 `scope`는 `per_process`다. 따라서 serverless 다중 인스턴스 전체에 대한
분산 제한으로 간주하면 안 된다. 공개 배포에서는 외부 저장소/API gateway 기반 rate limit과
비용 예산을 추가한 뒤 트래픽을 개방한다.

`jsonschema`는 핵심 런타임 의존성이며 기본값으로 schema v2 응답을 HTTP 직전에도 검증한다.
긴급 진단 외에는 `DART_STRICT_ORCHESTRATION_SCHEMA=false`로 내리지 않는다. 런타임
`response_guard`의 evidence·결정지원 참조 무결성 검사는 설정과 무관하게 계속 실행된다.

서버·CI·smoke처럼 브라우저 자동 실행이 불필요하면 `DART_OPEN_BROWSER=false`로 설정한다.
