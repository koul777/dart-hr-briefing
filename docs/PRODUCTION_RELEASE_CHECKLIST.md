# 운영 배포 검증 체크리스트

대상: `https://dart-ruby-zeta.vercel.app`

읽기 전용 기준 점검일: 2026-09-07 KST

점검 범위: 공개 정적 화면, `/api/health`, 합성 교실 endpoint, AI 접근 경계의 비밀정보 없는 음성 테스트, 응답 헤더·크기·시간

이 문서는 배포를 수행하는 절차가 아니라 **배포 승인 전후에 동일한 계약을 검증하는 체크리스트**다. 기준 점검에서는 실제 OpenDART 조회, 유효한 OpenAI 키 또는 operator token 사용, AI provider 호출, 로그인, 환경변수 변경을 하지 않았다.

## 1. 현재 운영 기준선과 판정

| 항목 | 2026-09-07 운영 관찰값 | 판정 | 배포 후 필수 조건 |
|---|---|---:|---|
| 루트 화면 | `GET /` → 200, 10,063 bytes | 통과 | 200, HTML, 현재 UI의 합성 샘플 진입 버튼 표시 |
| 앱 ID | `kr.opendart.dart-hr-briefing` | 통과 | 정확히 동일 |
| 앱 버전 | `0.2.0` | 통과 | 의도한 릴리스 버전과 동일 |
| build ID | `source` | **차단** | `source`가 아닌 불변 식별자이며 배포한 commit/build와 일치 |
| strict schema | `strict_schema_enabled=true`, `strict_schema_validator_ready=true` | 통과 | 두 값 모두 `true` |
| 합성 교실 API | `GET /api/classroom/bootstrap` → 404 | **차단** | 200 및 아래 합성 데이터 계약 충족 |
| 합성 교실 UI | 운영 HTML/JS에서 합성 샘플 marker 없음 | **차단** | `loadClassroomButton`과 `/api/classroom/bootstrap` marker 존재 |
| AI provider 상태 | `ai_provider_configured=false`, provider=`claude_mcp` | 제한적 통과 | 익명 사용자가 운영자 provider를 사용할 수 없어야 함 |
| 운영자 AI 경계 | 운영 health에 `operator_ai_access` 없음 | **검증 불가/차단** | 새 health 계약 노출 및 `authentication_required=true`; 유효 토큰 없이 provider 호출 0회 |
| API 보안 헤더 | no-store, HSTS, nosniff, DENY, no-referrer, camera/mic/geolocation 차단 | 통과 | 아래 헤더 계약 유지 |
| 루트 CSP | 엄격한 same-origin CSP와 `frame-ancestors 'none'` | 통과 | 현재 정책 유지 또는 더 엄격하게 변경 |
| 정적 JS 헤더 | Vercel 정적 응답은 HSTS를 제공하지만 앱 CSP·nosniff·frame/referrer 헤더는 없음; `Access-Control-Allow-Origin: *` | 검토 필요 | 공개 정적 자산의 의도된 정책인지 확인하고 문서화 |

현재 URL은 응답하지만 **로컬의 합성 교실 기능과 명시적 operator AI 경계가 배포되지 않은 이전 빌드**로 판단된다. 가장 강한 근거는 운영 교실 endpoint의 반복 404, UI marker 부재, health의 새 계약 부재와 `build_id="source"`다.

## 2. HTTP 증적

같은 시점에 3회 연속 수행한 안전한 GET 측정값이다. 시간은 클라이언트에서 본 전체 시간이며 SLA가 아니라 재검증 기준선이다.

| Method / path | status | bytes | 3회 전체 시간 | cache | 관찰 |
|---|---:|---:|---:|---|---|
| `GET /` | 200 | 10,063 | 0.248–0.299s | `no-cache` | HTML 반환, 합성 샘플 버튼 marker 없음 |
| `GET /api/health` | 200 | 1,174 | 0.237–0.256s | `no-store` | 앱 ID·버전·strict schema 확인, 새 classroom/operator 계약 없음 |
| `GET /api/classroom/bootstrap` | 404 | 84 | 0.234–0.283s | `no-store` | 현재 운영에 합성 endpoint 없음 |

추가로 `GET /static/app.js`는 200, 141,477 bytes, 약 0.058s였다. 공개 정적 파일이므로 `Access-Control-Allow-Origin: *` 자체를 취약점으로 단정하지 않는다. 다만 이 경로에는 루트 HTML에서 확인된 앱 CSP와 API의 `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`가 없었으므로 Vercel 정적 자산 정책으로 의도한 결과인지 릴리스 때 결정해야 한다.

비용이 발생하지 않는 경계 확인 결과:

| 요청 | 결과 | 확인된 범위 | 확인하지 못한 범위 |
|---|---|---|---|
| `POST /api/ai/connect`, 빈 JSON, 키 없음 | 400, 85 bytes, 약 0.254s | 키가 없는 연결 요청을 거부하며 비밀정보를 응답하지 않음 | 실제 키의 연결·provider 호출 |
| `POST /api/analysis`, 빈 JSON, 합성 invalid token | 400, 97 bytes, 약 0.243s | 입력 검증 단계에서 종료하고 token을 반사하지 않음 | 올바른 payload에서 invalid token이 운영자 provider를 확실히 차단하는지 여부 |

두 응답의 `request_id`는 형식만 16자리 hex인지 확인했고 값을 기록하지 않았다. 유효한 token·키·기업 코드는 전송하지 않았다.

## 3. 보안 헤더 계약

### 루트 HTML

- [ ] `Content-Security-Policy`에 `default-src 'self'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`가 있다.
- [ ] `Strict-Transport-Security`가 최소 `max-age=31536000`을 제공한다.
- [ ] `X-Content-Type-Options: nosniff`다.
- [ ] `X-Frame-Options: DENY`다.
- [ ] `Referrer-Policy: no-referrer`다.
- [ ] `Permissions-Policy`가 camera, microphone, geolocation을 비활성화한다.
- [ ] `Cache-Control: no-cache`다.

### JSON API

- [ ] `/api/health`와 `/api/classroom/bootstrap`이 `Cache-Control: no-store`다.
- [ ] HSTS, nosniff, DENY, no-referrer, camera/microphone/geolocation 차단이 유지된다.
- [ ] 응답에는 API 키, operator token, 이메일, 전화번호, 사번, 주민번호 또는 원문 예외가 포함되지 않는다.
- [ ] `X-Request-ID`는 16자리 hex 형식이며 사용자 입력이나 자격증명을 포함하지 않는다.
- [ ] JSON API에 CSP를 적용하지 않는 현재 정책을 유지한다면, CSP가 HTML 실행 문맥을 통제하고 JSON은 `nosniff`와 정확한 `Content-Type`으로 보호된다는 운영 결정을 기록한다.

## 4. 로컬 변경과 운영의 차이

| 계약 | 현재 로컬 | 현재 운영 | 배포 후 증적 |
|---|---|---|---|
| 첫 화면 | `static/index.html` 11,404 bytes, `loadClassroomButton` 존재 | 10,063 bytes, marker 없음 | 새 버튼 표시 스크린샷 + root body marker |
| 프런트 JS | `static/app.js` 166,228 bytes, classroom bootstrap 로직 존재 | 141,477 bytes, marker 없음 | 현재 파일 크기/해시와 운영 다운로드 해시 일치 |
| health classroom 계약 | `classroom_sample.available=true`, endpoint·network count 제공 | 필드 없음 | health JSON 저장(비밀정보 제거) |
| 합성 교실 API | 로컬 handler와 결정론적 fixture 존재; 현재 compact JSON 102,173 bytes | 404 | 200 + 합성 계약 assertion |
| operator AI 계약 | 로컬 health에 enabled/authentication_required/ready boolean 제공 | 필드 없음 | `authentication_required=true`; enabled/ready는 환경 의도와 일치 |
| build 식별성 | Vercel에서는 `VERCEL_GIT_COMMIT_SHA` 우선, 로컬은 `DART_BUILD_ID` 또는 frozen hash | `source` | 배포 commit SHA와 정확히 일치, `source` 금지 |

응답 byte 수는 압축·직렬화 변경에 따라 달라질 수 있으므로 동일함 자체가 합격 기준은 아니다. 그러나 현재 차이는 기능 marker와 endpoint 상태 차이까지 함께 나타나므로 단순 압축 차이가 아니다.

## 5. 재현 가능한 빌드와 표준 배포 게이트

- [ ] 릴리스 대상 파일을 먼저 명시적으로 stage한 뒤 `python -X utf8 tools/release_secret_scan.py --root .`를 실행한다. 기본 검사는 tracked 파일과 Vercel 배포 후보를 대상으로 하며, stage하지 않는 별도 바이너리·문서는 `--binary <path>`로 추가 검사한다.
- [ ] `.python-version`과 `uv.lock`이 Vercel 후보에 포함되고, 소스 설치는 `uv sync --locked`로 잠금파일 변경 없이 완료된다.
- [ ] `vercel deploy --prod`의 표준 소스 배포만 사용하고 `vercel deploy --prebuilt`는 사용하지 않는다.
- [ ] 로컬 `.vercel/output`의 존재 여부와 관계없이 해당 디렉터리를 업로드하거나 배포 근거로 사용하지 않는다. 이 캐시는 이전 코드·환경·route를 포함할 수 있다.
- [ ] Windows EXE는 빌드 직후 `release_preflight.py`로 모든 패키징 입력보다 새 산출물인지 검사하고 commit SHA·소스 fingerprint·EXE SHA-256을 `DARTStructure.release.json`에 고정한다.
- [ ] 별도 clean 디렉터리에 23개 allowlist 파일만 복사해 `vercel build --prod --cwd <clean-dir>`를 실행하고, 생성된 `.vc-config.json`을 `python tools/vercel_bundle_contract.py <clean-dir>/.vercel/output/functions/api/index.func/.vc-config.json`으로 검사한다.
- [ ] bundle 검사는 `python3.12`·공식 handler·x86_64·120초·streaming·고정된 비자격증명 환경만 허용한다. `filePathMap`의 앱/생성물 40개는 정확한 allowlist와 `logical path == source path`를 만족하고, vendor는 `_vendor/...`와 잠금 환경의 `site-packages/...` tail이 일치해야 한다.
- [ ] bundle의 논리·원본 경로에는 절대경로, drive-relative 경로, `..`, `.`, 빈 segment, 역슬래시, 제어문자, 대소문자 충돌이 없어야 한다. 모든 원본은 clean root 내부의 일반 파일이어야 하며 symlink는 허용하지 않는다.
- [ ] `build/lib`의 Python 복사본은 대응하는 root 원본과 SHA-256이 같아야 한다. 2026-09-07 clean 기준 820 paths(앱/생성물 40, vendor 780)는 관찰값이며, 개수가 같다는 이유만으로 통과시키지 않는다.
- [ ] `vercel.json`의 첫 catch-all route가 모든 공개 경로를 Python handler로 전달하며 `handle: filesystem`보다 소스 파일을 먼저 노출하는 rewrite 출력이 없어야 한다.

```powershell
python -X utf8 tools/release_secret_scan.py --root .
python -X utf8 tools/release_preflight.py `
  --root . `
  --exe dist/DARTStructure.exe `
  --commit-sha <배포한 Git commit SHA> `
  --manifest-output dist/DARTStructure.release.json
vercel deploy --prod
```

`release_executable_stale`이면 기존 EXE를 재사용하지 않고 clean build 후 다시 검사한다. `vercel_bundle_contract.py`가 실패하면 reason code만 기록하고 `.vc-config.json` 내용이나 환경값을 공유하지 않는다. CI 산출물은 commit SHA가 들어간 artifact 이름과 위 manifest를 함께 제공해야 한다.

## 6. 배포 후 필수 무비용 검증

아래 수동 예시는 `-SkipHttpErrorCheck`를 지원하는 PowerShell 7 이상 전용이다. Windows PowerShell 5.1에서는 정식 검증 경로인 `python -X utf8 tools/post_deploy_smoke.py`를 사용한다. 공개 GET과 의도적인 입력 오류만 사용하며, 유효한 API 키, operator token, 기업 코드 또는 실제 분석 payload를 넣지 않는다.

```powershell
$baseUrl = "https://dart-ruby-zeta.vercel.app"
$expectedSha = "<배포한 Git commit SHA>"
$expectedBuildId = "git-" + $expectedSha.ToLowerInvariant().Substring(0, 12)

$root = Invoke-WebRequest "$baseUrl/" -SkipHttpErrorCheck
$health = Invoke-RestMethod "$baseUrl/api/health"
$sampleResponse = Invoke-WebRequest "$baseUrl/api/classroom/bootstrap" -SkipHttpErrorCheck
$sample = $sampleResponse.Content | ConvertFrom-Json

if ($root.StatusCode -ne 200) { throw "root_status" }
if ($root.Content -notmatch 'loadClassroomButton') { throw "classroom_ui_missing" }
$staticApp = Invoke-WebRequest "$baseUrl/static/app.js" -SkipHttpErrorCheck
if ($staticApp.StatusCode -ne 200 -or $staticApp.Content -notmatch 'API_REQUEST_TIMEOUT_MS') { throw "static_app_missing" }
$protectedPaths = @(
  '/.env', '/.git/config', '/server.py', '/agent_orchestration.py',
  '/analysis_contract.py', '/claude_mcp_adapter.py', '/classroom_mode.py',
  '/openai_responses_adapter.py', '/orchestration_evaluation.py', '/orchestrator.py',
  '/pyproject.toml', '/runtime_controls.py', '/uv.lock', '/vercel.json',
  '/workforce_analytics.py', '/.python-version', '/api/index.py',
  '/HR_BRIEFING_RULES.md', '/schemas/workforce_orchestration_v2.schema.json',
  '/seed/classroom_workforce_2024_11011.json', '/seed/corp_codes.json.gz'
)
foreach ($path in $protectedPaths) {
  $protected = Invoke-WebRequest "$baseUrl$path" -SkipHttpErrorCheck
  if ($protected.StatusCode -ne 404) { throw "runtime_source_public" }
}
if (-not $health.ok) { throw "health_not_ok" }
if ($health.app.id -ne 'kr.opendart.dart-hr-briefing') { throw "app_id_mismatch" }
if ($health.app.version -ne '0.2.0') { throw "app_version_mismatch" }
if ($health.app.build_id -ne $expectedBuildId) { throw "build_id_commit_mismatch" }
if (-not $health.api_key_configured) { throw "opendart_key_not_configured" }
if (-not $health.strict_schema_enabled -or -not $health.strict_schema_validator_ready) { throw "strict_schema_not_ready" }
if (-not $health.classroom_sample.available) { throw "classroom_not_advertised" }
if ($health.classroom_sample.endpoint -ne '/api/classroom/bootstrap') { throw "classroom_endpoint_mismatch" }
if ($health.classroom_sample.network_requests -ne 0) { throw "classroom_network_contract_mismatch" }
if (-not $health.operator_ai_access.authentication_required) { throw "operator_auth_not_required" }

if ($sampleResponse.StatusCode -ne 200) { throw "classroom_status" }
if (-not $sample.sample.enabled) { throw "classroom_disabled" }
if ($sample.sample.network_requests -ne 0) { throw "classroom_network_request" }
if ($sample.sample.contains_real_company_data) { throw "classroom_real_company_data" }
if ($sample.sample.contains_personal_data) { throw "classroom_personal_data" }
if ($sample.sample.watermark -ne 'SAMPLE — SYNTHETIC DATA') { throw "classroom_watermark" }
if ($sample.sample.outbound_evidence_links) { throw "classroom_external_link" }
if ($sample.sample.receipt_numbers_exposed) { throw "classroom_receipt_exposed" }
```

같은 계약은 응답 body를 로그에 남기지 않는 자동 smoke로 우선 실행한다. GitHub Actions의 `workflow_dispatch`에도 동일한 `base_url`과 `expected_sha`를 전달할 수 있다.

```powershell
python -X utf8 tools/post_deploy_smoke.py `
  --base-url $baseUrl `
  --expected-sha $expectedSha
```

오류 응답의 안전성은 body를 콘솔에 그대로 출력하지 않고 다음처럼 구조만 검사한다.

```powershell
$invalidOperatorToken = 'invalid-' + ('x' * 24)
$headers = @{ 'Content-Type' = 'application/json'; 'X-DART-Operator-Token' = $invalidOperatorToken }
$connect = Invoke-WebRequest "$baseUrl/api/ai/connect" -Method Post -ContentType 'application/json' -Body '{}' -SkipHttpErrorCheck
$analysis = Invoke-WebRequest "$baseUrl/api/analysis" -Method Post -Headers $headers -Body '{}' -SkipHttpErrorCheck

if ($connect.StatusCode -ne 400) { throw "missing_key_not_rejected" }
if ($analysis.StatusCode -ne 400) { throw "invalid_request_not_rejected" }
if ($connect.Content -match 'sk-[A-Za-z0-9_-]+' -or $analysis.Content -match [regex]::Escape($invalidOperatorToken)) { throw "credential_reflected" }
```

이 음성 테스트는 **잘 구성된 분석 요청에 대한 invalid operator token 거부를 증명하지 않는다**. 그 검증은 비용 없는 provider stub이 있는 자동화 테스트에서 수행하고, 운영에서는 유효한 자격증명이나 실제 데이터로 시험하지 않는다.

## 7. 응답 크기·시간 가드

- [ ] 루트 HTML은 128 KiB 이하, health는 16 KiB 이하, 합성 bootstrap은 512 KiB 이하인지 확인한다.
- [ ] 각 경로를 3회 호출해 warm 응답 중앙값이 2초 미만인지 기록한다.
- [ ] cold start가 포함된 첫 요청은 별도로 표시하고 10초를 넘으면 Vercel function 로그에서 request ID만 대조한다.
- [ ] 크기 또는 시간이 기준을 넘으면 body에 비밀정보를 저장하지 않고 status, bytes, elapsed, build ID만 남긴다.
- [ ] rate limiter가 `scope=per_process`, `distributed_enforcement=false`인 현재 제약을 운영 문서에 남기고, 다중 인스턴스 전체 한도로 오해하지 않는다.

이 수치는 현재 관찰값보다 충분히 큰 회귀 가드이며 서비스 SLA를 선언하는 값이 아니다.

## 8. 실패 시 안전한 재시도

1. UTC와 KST 시각, 경로, HTTP status, 응답 byte 수, elapsed만 기록한다.
2. 5–10초 간격으로 최대 3회 재시도한다. 실제 OpenDART·AI 요청으로 상태를 확인하지 않는다.
3. DNS/TLS/timeout은 구분하되 응답 body, 환경변수, 키, token, 개인식별정보는 티켓이나 채팅에 붙여 넣지 않는다.
4. 401/403/404/5xx가 반복되면 재시도를 멈추고 배포의 build ID, Vercel route/function 포함 여부, 환경변수 **존재 여부 boolean**만 확인한다.
5. `/api/health`가 실패하면 root와 정적 JS를 분리 점검한다. root만 성공하면 정적 배포와 함수 배포의 불일치로 분류한다.
6. classroom endpoint만 실패하면 `vercel.json`의 함수 포함 규칙과 현재 commit에 `classroom_mode.py`, 합성 seed가 들어갔는지 확인한다. 실제 공시 API로 대체 검증하지 않는다.
7. 재현 증적에는 공개 오류 문구 대신 reason code와 status만 남긴다. 지원 채널에 request ID가 필요하면 값은 제한된 운영 채널에서만 공유한다.

## 9. 릴리스 승인 조건

- [ ] `build_id`가 정확히 배포 대상 commit SHA의 `git-<앞 12자리>`와 일치한다.
- [ ] 비밀 스캔, 잠금파일 sync, EXE preflight/manifest가 모두 통과하고 prebuilt Vercel 배포를 사용하지 않았다.
- [ ] `/api/health`의 `api_key_configured=true`이며 실제 키 값은 응답·로그에 노출되지 않는다.
- [ ] root, health, classroom endpoint가 모두 200이다.
- [ ] classroom 합성/무네트워크/무개인정보 계약이 전부 통과한다.
- [ ] strict schema 두 플래그가 모두 `true`다.
- [ ] `operator_ai_access.authentication_required=true`이며 익명 사용자가 운영자 provider를 사용할 수 없다.
- [ ] 키 없는 AI 연결과 invalid 요청은 고정된 안전 오류로 종료하고 credential/user content를 반사하지 않는다.
- [ ] 보안 헤더, 크기, warm 응답 시간 가드가 통과한다.
- [ ] 배포한 root/JS의 기능 marker 및 해시가 의도한 로컬 릴리스와 일치한다.

하나라도 실패하면 유료/실데이터 호출로 우회 확인하지 않고 릴리스를 보류한다. 이 점검만으로 OpenDART 최신성, 실제 provider 가용성 또는 올바른 operator token의 성공 경로까지 확인했다고 해석해서는 안 된다.
