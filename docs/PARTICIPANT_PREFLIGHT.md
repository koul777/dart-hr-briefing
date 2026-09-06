# DART HR Briefing 참가자 사전점검

이 점검은 수업 시작 전에 실행 환경과 계정을 확인하기 위한 것입니다. 실제 직원·지원자 데이터가
아닌 합성 데이터와 공개 기업 단위 공시만 사용합니다.

강의 자료는 **본문 42장·부록 18장·총 60장** 편성입니다. 참가자는 본문 42장의 m0~m4 골든패스를
따르고, 부록 18장은 질문이나 복구가 필요할 때만 엽니다. 하드 체크포인트의
**정시 통과율이 80% 미만**이면 현재 작업을 지우지 말고 강사가 지정한 검증 복구본으로 전환합니다.

### 사람/AI 역할 경계

- **사람의 역할**은 사용할 입력 범위를 고르고, AI 전송에 동의하며, 공시 원문·근거를 확인하고
  최종 판단 책임을 지는 것입니다.
- **AI의 역할**은 공개 기업 단위 집계를 근거와 함께 요약하고 해석 초안을 만드는 것입니다. AI는
  개인 평가, 인과 단정, 자동 채용·승진·보상·감축 등 자동 인사조치를 결정하거나 권고하지 않습니다.

## 1. 수업 전에 준비할 것

- Windows 10/11과 최신 Chrome 또는 Edge
- Python 3.11 이상(권장 3.12), Git
- Claude Pro/Team 또는 사용할 수 있는 Claude Code 계정
- GitHub 계정과 Vercel에 연결할 수 있는 GitHub 권한
- 개인 OpenDART API 인증키
- AI 실습을 할 경우 본인이 사용 권한과 한도를 확인한 OpenAI API 키

OpenAI 키는 선택 사항입니다. 키가 없어도 기업 비교, Strategy Brief, 근거 확인 실습은 계속할 수
있습니다. 계정 비밀번호와 API 키는 강사·조교·AI 대화창에 보내지 않습니다.

## 2. 안전한 실습 데이터

1. 합성 fixture와 강사가 제공한 샘플로 흐름을 먼저 익힙니다.
2. 실제 조회는 삼성전자·SK하이닉스처럼 공개된 기업 단위 OpenDART 공시만 사용합니다.
3. 실제 직원·지원자의 이름, 연락처, 이메일, 사번, 이력서, 평가·보상·건강·노조 정보는
   프롬프트, 소스, CSV, 화면 캡처 어디에도 입력하지 않습니다.
4. DART 집계값은 개인 평가, 자동 채용·보상·감축 결정, 인과관계의 근거로 사용하지 않습니다.

시스템이 질문에서 직접 식별자를 발견하면 `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`,
`[REDACTED_RRN]`, `[REDACTED_EMPLOYEE_ID]`, `[REDACTED_PERSON]`으로 마스킹할 수 있습니다.
마스킹으로 질문의 의미가 달라질 수 있으므로 실제 개인 데이터를 다시 입력하지 말고 합성 사례로
바꿉니다.

## 3. 프로젝트 준비

강사가 제공한 저장소를 개인 실습 폴더에 준비한 뒤 프로젝트 루트에서 실행합니다.

```powershell
py -3.12 --version
git --version
claude --version
claude auth login
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.env`의 `OPENDART_API_KEY=` 오른쪽에 본인의 키를 입력합니다. 실제 키가 보이는 `.env` 파일과
터미널 화면은 캡처하거나 공유하지 않습니다.

PowerShell이 가상환경 활성화를 차단하면 정책을 전역으로 낮추지 말고 다음처럼 가상환경의 Python을
직접 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -X utf8 tools\classroom_preflight.py
```

## 4. 자동 사전점검

```powershell
py -3.12 -X utf8 tools\classroom_preflight.py
```

이 스크립트는 Python 버전, 필수 파일·의존성, `.env`의 OpenDART 키 설정 여부, 기본 포트 8765,
테스트 파일과 품질 도구 준비 상태를 읽기 전용으로 확인합니다. 키 값은 출력하지 않습니다.

- `PASS`: 준비 완료
- `WARN`: 수업 참여는 가능하지만 해당 기능이나 품질 검사가 제한될 수 있음
- `FAIL`: 수업 전에 해결 필요

조교에게는 마지막 요약과 `PASS/WARN/FAIL` 항목만 전달하고 `.env` 내용은 보내지 않습니다.

## 5. 실행 확인

```powershell
python server.py
```

브라우저가 자동으로 열리지 않으면 `http://127.0.0.1:8765`에 접속합니다. 다른 프로그램이 포트를
사용 중이면 앱이 다음 빈 포트를 선택할 수 있으므로 터미널과 화면 왼쪽 아래의 실제 주소를
확인합니다.

새 PowerShell 창에서 다음을 확인합니다. 이 JSON 확인은 사전점검에서 1회만 수행합니다. 수업 중에는
강사가 JSON 계약을 시연하고 참가자는 브라우저의 **합성 샘플로 시작** 화면으로 통과합니다.

```powershell
$health = Invoke-RestMethod http://127.0.0.1:8765/api/health
$health.app.id
$health.api_key_configured
$sample = Invoke-RestMethod http://127.0.0.1:8765/api/classroom/bootstrap
$sample.sample
```

통과 기준:

- `app.id`가 `kr.opendart.dart-hr-briefing`
- 합성 샘플만 실습할 때는 `api_key_configured`가 `False`여도 됨. 실제 공시 조회까지 할 때는 `True`
- 합성 bootstrap이 `enabled: True`, `network_requests: 0`,
  `watermark: SAMPLE — SYNTHETIC DATA`를 표시함
- 첫 화면에 기업 검색창과 기준연도·보고서 선택 영역이 표시됨

합성 bootstrap은 수업용 JSON 계약을 확인하는 로컬 경로이며 실제 OpenDART나 AI provider를
호출하지 않습니다. 첫 화면의 **합성 샘플로 시작**을 누르면 같은 계약을 사용하는 두 가상 기업이
자동 선택되고, 상단에 `SAMPLE — SYNTHETIC DATA` 배너가 표시됩니다. 샘플 화면의
**합성 결정 브리핑 만들기**도 외부 AI를 호출하지 않습니다. 실데이터 실습으로 전환할 때는
**실데이터 화면으로 돌아가기**를 누릅니다.

실데이터 AI 브리핑은 질문과 공개 기업 집계의 전송 안내를 읽고 **전송 동의**를 체크한 경우에만
실행됩니다. 수업을
마치거나 좌석을 넘길 때 **AI 키·대화 연결 해제**를 눌러 메모리의 키·연결 상태·대화·동의를
함께 지웁니다.

## 6. 계정과 배포 확인

```powershell
git remote -v
git status --short
```

- `git remote -v`에 본인이 사용할 저장소 또는 강사가 지정한 원격 저장소가 표시되는지 확인합니다.
- GitHub와 Vercel을 연결하되 수업 전에는 실제 배포를 만들 필요가 없습니다.
- Vercel에서 GitHub 저장소 Import 화면까지 접근할 수 있는지만 확인합니다.
- 조직 계정은 저장소 생성·Import 권한이 제한될 수 있으므로 D-3까지 조교에게 알려야 합니다.

## 7. 문제가 있을 때

| 증상 | 확인과 복구 |
| --- | --- |
| `dart`를 실행했더니 다른 프로그램이 열림 | `dart` 명령을 종료하고 프로젝트 루트에서 `python server.py` 또는 `dist\DARTStructure.exe` 실행 |
| `py -3.12`를 찾지 못함 | `python --version` 확인. Python 3.11 이상이면 `python` 사용, 아니면 Python 설치 후 터미널 재시작 |
| 가상환경 활성화가 차단됨 | 실행 정책을 낮추지 말고 `.\.venv\Scripts\python.exe`를 직접 사용 |
| `jsonschema`가 없음 | 가상환경에서 `python -m pip install -e ".[dev]"` 재실행 |
| OpenDART 키가 설정되지 않음 | `.env.example`이 아니라 `.env`에 입력했는지 확인. 키 자체는 공유하지 않음 |
| 포트 8765 사용 중 | 기존 서버를 종료하거나 새로 실행한 앱이 안내하는 대체 포트 사용 |
| OpenDART timeout·429 | 같은 조건은 **최초 요청 포함 최대 3회(재시도 최대 2회)**에서 멈추고 합성 샘플·준비 화면으로 전환 |
| OpenAI 키 또는 한도 없음 | AI 호출은 건너뛰고 Strategy Brief·근거 확인·안전한 대체 응답 실습 진행 |
| AI 답변이 검증 정책에 차단됨 | `uncited_factual_claim`은 무근거 사실, `unsupported_causal_assertion`은 확인 불가능한 인과 단정, `automated_hr_action_recommendation`은 자동 인사조치, `protected_characteristic_judgment`는 보호특성 판단 차단. 원문 재사용 없이 근거 대체 응답 확인 |
| GitHub/Vercel 권한 없음 | 조교가 제공한 체크포인트 ZIP으로 수업을 계속하고 배포는 짝 실습 또는 사후 보완 |

사전점검이 끝나면 `git status --short`가 예상하지 않은 변경을 보이지 않는지 확인합니다. `.env`는
Git에서 제외되어야 합니다.
