# CLAUDE.md

이 문서는 Claude Code가 이 저장소에서 작업할 때 따라야 하는 프로젝트 규칙이다. 사용자 요청과
저장소의 기존 계약을 먼저 확인하고, 관련 없는 파일이나 다른 작업자의 변경을 되돌리지 않는다.

## 제품 목적과 경계

- 이 앱은 OpenDART의 기업 단위 공개 공시를 비교해 HR 질문과 추가 확인 과제를 만드는
  의사결정 보조 도구다.
- 채용·평가·보상·감축·승계를 자동 결정하지 않는다. 상관관계나 선택 기업 내부 순위를 인과,
  개인 성과 또는 외부 산업 벤치마크로 표현하지 않는다.
- 예시와 테스트는 합성 fixture를 우선한다. 실제 데이터가 필요하면 삼성전자·SK하이닉스처럼
  공개된 기업 단위 OpenDART 공시만 사용한다.
- 실제 직원·지원자의 이름, 연락처, 이메일, 주민·사번, 이력서, 평가, 보상 원장, 건강·노조 정보
  등 개인 단위 HR 데이터는 코드, 프롬프트, fixture, 테스트, 로그, 캡처에 입력하지 않는다.
- 질문의 직접 식별자는 provider 전달 전에 `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`,
  `[REDACTED_RRN]`, `[REDACTED_EMPLOYEE_ID]`, `[REDACTED_PERSON]`으로 마스킹한다. 마스킹을
  실제 개인 데이터 입력 허가로 해석하지 않는다.

## 비밀정보

- 실제 키는 로컬 `.env` 또는 배포 플랫폼의 환경변수에만 둔다.
- `.env`, API 키, 인증 토큰을 커밋·로그·오류 메시지·URL·화면 캡처에 포함하지 않는다.
- 키 값을 확인해야 할 때도 설정 여부와 형식만 보고하고 값을 출력하지 않는다.
- 이미 공개된 키를 발견하면 내용을 다시 출력하지 말고 즉시 폐기·재발급이 필요하다고 알린다.

## 골든 실행 경로

```powershell
uv sync --locked --extra dev --python 3.12
uv run --locked --extra dev python tools/classroom_preflight.py
uv run --locked --extra dev python server.py
```

- 기본 주소는 `http://127.0.0.1:8765`다.
- `/api/health`의 `app.id`는 `kr.opendart.dart-hr-briefing`이어야 한다.
- `/api/classroom/bootstrap`은 외부 호출 없이 `sample.enabled=true`,
  `sample.watermark="SAMPLE — SYNTHETIC DATA"`, `network_requests=0`을 반환해야 한다.
- `dart`만 실행하지 않는다. 시스템에 설치된 Dart SDK나 같은 이름의 다른 프로그램이 실행될 수
  있으므로 프로젝트 루트에서 위 명령 또는 `dist\DARTStructure.exe`를 사용한다.
- 수업과 예시는 합성 데이터로 흐름을 먼저 확인한 뒤 실제 OpenDART 호출로 넘어간다.

## 변경 절차

1. `git status --short`와 관련 문서를 확인한다.
2. 변경 범위, 입력·출력, 실패 상태, 완료 기준을 짧게 정리한다.
3. 기존 API·schema·evidence 계약을 유지하면서 최소 범위로 수정한다.
4. 결측을 0으로 바꾸지 않고 `no_data`, `partial`, `error`, `blocked`를 구분한다.
5. AI provider보다 결정론적 계산과 evidence ledger를 우선한다.
6. 사용자 입력은 신뢰하지 않고 길이·형식·허용 범위를 검증한다.
7. 관련 검사 후 전체 회귀를 실행하고 실제 결과만 보고한다.

## 필수 검증

변경 범위에 맞는 검사부터 실행하고, 최종 통합 전에는 다음을 기준으로 확인한다.

```powershell
uv run --locked --extra dev python -m unittest discover -v
uv run --locked --extra dev python -m coverage run --branch -m unittest discover
uv run --locked --extra dev python -m coverage report -m --fail-under=80
uv run --locked --extra dev ruff check . --select E4,E7,E9,F
uv run --locked --extra dev python -m py_compile analysis_contract.py server.py agent_orchestration.py classroom_mode.py `
  workforce_analytics.py claude_mcp_adapter.py openai_responses_adapter.py `
  orchestration_evaluation.py orchestrator.py runtime_controls.py tools/classroom_preflight.py
node --check static/app.js
node --check tools/qa_classroom_mode.js
node --check tools/qa_failure_recovery.js
node --check tools/qa_orchestration_v2.js
```

- 테스트 개수는 구현에 따라 달라질 수 있으므로 고정 숫자로 성공을 주장하지 않는다.
- 프론트엔드 변경은 키보드 조작, 모바일 폭, 밝은/어두운 테마, 로딩·무자료·오류 상태를 확인한다.
- 오케스트레이션 변경은 schema v2, evidence 참조 무결성, 개인정보·근거·인과·개인판단 출력 가드를
  함께 검증한다.
- `uncited_factual_claim`, `automated_hr_action_recommendation`,
  `protected_characteristic_judgment`를 허용 답변으로 완화하지 않고 안전한 fallback을 유지한다.
- 패키지 실행 파일은 격리 빌드와 strict smoke를 통과하기 전에 `dist/DARTStructure.exe`를
  덮어쓰지 않는다.

## 강의 자료 변경

- 강의 골든패스는 [참가자 사전점검](docs/PARTICIPANT_PREFLIGHT.md)과
  [강사용 런북](docs/INSTRUCTOR_RUNBOOK.md)을 기준으로 한다.
- 실습 화면에는 `조작 → 기대 화면 → 통과 기준 → 실패 시 복구`를 함께 제공한다.
- 존재하지 않는 브랜치·태그·URL을 이미 사용 가능한 것처럼 안내하지 않는다.
- 실제 화면을 사용하며 키와 개인정보를 마스킹한다. 생성 이미지로 수치나 성공 상태를 만들지 않는다.
