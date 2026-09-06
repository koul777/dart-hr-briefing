# HR AI Agent Boot Camp WEEK 2 PPT 정렬 계획

## 목적과 범위

이 문서는 최종 편성 기준인 **본문 42장·부록 18장·총 60장**을 최신 강의 골든패스와 맞추기 위한
자산·조작·발표자 노트 계약이다. `training_deck/training_deck.pptx`는 레거시 56장 참고본이며,
최종본 여부는 파일명이나 장수만으로 선언하지 않고 이 문서의 렌더·증거 게이트로 판정한다.

커뮤니케이션 목표는 다음과 같다.

> 수강생이 4시간 뒤 합성 데이터로 안전하게 흐름을 검증한 다음 공개 기업 단위 공시로 비교하고,
> 외부 API가 실패해도 근거·개인정보 경계를 지키며 m0~m4를 완주할 수 있어야 한다.

### WEEK 1→2→3 학습 연결 계약

| 주차 | 학습 산출물 | 다음 주차로 넘기는 것 |
| --- | --- | --- |
| WEEK 1 면접 브리핑 에이전트 | 지원 자료를 구조화한 질문·확인 항목 | 개인 합격 예측이 아니라 검증할 질문의 구조 |
| WEEK 2 DART HR Analytics 에이전트 | 공개 기업 공시의 근거·한계·결정 브리프 | 결정 브리프의 `다음 내부 데이터` 목록 |
| WEEK 3 데이터 빌더 | 합성 데이터로 먼저 정의한 필드·단위·집계수준·품질 규칙 | 개인정보 없이 검증 가능한 내부 데이터 구조 |

`ready`는 성공확률이나 인사조치 권고가 아니라 정의된 공시 비교의 **근거 이용 가능성**을 뜻한다.
결정 브리프의 `다음 내부 데이터`는 WEEK 3 데이터 빌더의 입력으로 이어지되, 실제 직원·지원자
데이터를 넘기는 것이 아니라 합성 사례로 만들 필드와 검증 규칙을 정하는 요구사항이다.

강사 수용 기준은 수강생이 ① `ready`의 뜻을 근거 이용 가능성으로 설명하고 ② 결정 브리프 한 개의
`다음 내부 데이터`를 WEEK 3용 필드·단위·집계수준 카드로 바꾸며 ③ 이를 성공확률·채용·승진·보상
등의 개인 인사조치 권고로 해석하지 않는 것이다.

대조 기준:

- `training_deck/final_60/outline.md`, `training_deck/final_60/speech.md`,
  `training_deck/final_60/deck_spec.json`: 총 60장 편성의 원고·발표자 노트·구조 계약
- `training_deck/training_deck.pptx`: 레거시 56장 참고본. 최종 60장 실습 PPT로 안내하지 않음
- `OpenDART_HR_Analytics_4시간_커리큘럼.md`
- `docs/INSTRUCTOR_RUNBOOK.md`, `docs/PARTICIPANT_PREFLIGHT.md`, `CLAUDE.md`
- 현재 코드의 `/api/classroom/bootstrap`, AI 입력 마스킹·출력 가드, 요청 timeout·abort·request ID

## 현재 자료와 최신 구현의 차이

1. 레거시 56장 PPTX는 2026-09-06 화면을 사용해 새 합성 교실 진입 버튼, 모드 배너, 고정 조건,
   결정론적 브리핑, 실데이터 복귀 흐름을 보여 주지 않는다.
2. Slide 9는 올바른 실행 명령만 보여 주고 실제 기본 주소 `127.0.0.1:8765`와 정확한
   `app.id=kr.opendart.dart-hr-briefing` 검증을 보여 주지 않는다.
3. Slide 29는 정상 로딩만 설명한다. 브라우저 요청은 현재 45초 후 timeout되고, 기업·기간 변경 시
   이전 compare·strategy·AI 요청을 취소하며, 서버 오류에는 안전한 request ID가 붙는다.
4. Slide 43~45는 기존 AI 연결과 일반 근거 화면 중심이다. 최신 입력 마스킹 표식과
   `uncited_factual_claim`, `unsupported_causal_assertion`,
   `automated_hr_action_recommendation`, `protected_characteristic_judgment` 차단 및 검증 fallback이 보이지 않는다.
5. 레거시 56장 PPTX의 발표자 노트는 대부분 공통 생성 문장이다. 최종 60장용
   `training_deck/final_60/speech.md`를 조립할 때는 슬라이드별 클릭, 정확한 기대 결과, 5분 내 복구,
   m0~m4 체크포인트와 출처 블록을 그대로 반영한다.
6. 최종 편성은 본문 42장만 시간표대로 진행하고 부록 18장은 질문·복구 때만 연다.

### 사람/AI 역할 경계

- **사람의 역할**은 입력 범위 선택, AI 전송 동의, 공시 원문·근거 확인과 최종 판단 책임이다.
- **AI의 역할**은 공개 기업 단위 집계의 근거 있는 요약·해석 초안이다. 개인 평가, 인과 단정,
  자동 채용·승진·보상·감축 등 자동 인사조치를 결정하거나 권고하지 않는다.
- `ready`는 근거 이용 가능성일 뿐 성공확률이나 인사조치 권고가 아니다.

## 최신 UI·문서 정합성 감사

### 현재 화면 계약

- 라이브 첫 화면의 왼쪽 **합성 샘플로 시작**(`#loadClassroomButton`)을 누르면 브라우저가 로컬
  서버의 `GET /api/classroom/bootstrap`을 한 번 호출한다. `network_requests=0`은 이 로컬 호출까지
  없다는 뜻이 아니라, fixture를 만들기 위한 외부 OpenDART·AI 호출이 없다는 뜻이다.
- 성공하면 두 가상 기업, `2024년`, `사업보고서`가 로드되고 검색·기업 제거·연도·보고서·AI 키·
  전송 동의 입력이 잠긴다. 상단에는 `SAMPLE — SYNTHETIC DATA`, 데이터 출처에는
  `합성 fixture · 원문 링크 없음`이 표시된다.
- 샘플 모드의 **인력·보상 비교**, Strategy Brief, **합성 결정 브리핑 만들기**, CSV
  `classroom-synthetic-2024.csv`는 외부 OpenDART·AI를 호출하지 않는다. 합성 브리핑에는
  `외부 AI가 생성한 답변이 아닙니다`가 표시된다.
- **실데이터 화면으로 돌아가기**(`#exitClassroomButton`)는 진행 중 요청, 기업 선택, 샘플 결과,
  대화와 전송 동의를 초기화하고 라이브 입력을 다시 연다. 이전 샘플 선택을 유지한다고 설명하면 안 된다.
- 라이브 AI는 키 입력만으로 실행되지 않고 **전송 동의**(`#aiTransferConsent`) 체크가 필수다.
  **대화 지우기**(`#clearAiButton`)는 대화와 질문 입력만 비우지만, **AI 키·대화 연결 해제**
  (`#disconnectAiButton`)는 키 입력·메모리 연결 상태·대화·전송 동의를 제거한다. 두 버튼을 같은
  기능처럼 설명하면 안 된다.

### 제공 캡처가 증명하는 범위

| 현재 캡처 | 실제로 보이는 증거 | PPT 처리 |
| --- | --- | --- |
| `docs/assets/classroom-sample-entry.png` | 클릭 전 **합성 샘플로 시작**, 기업 미선택, 빈 키·미체크 동의 | Slide 10 진입 전 화면의 표준 자산 |
| `docs/assets/classroom-sample-ui.png` | 두 샘플 기업, SAMPLE 배너, **실데이터 화면으로 돌아가기**, 2024년·사업보고서, 합성 출처, 결정론적 버튼 | Slides 10·28·30·35·44의 데스크톱 합성 화면 표준 자산. 필요한 영역만 crop |
| `docs/assets/classroom-sample-strategy.png` | 외부 원문 링크 없음, `DETERMINISTIC POLICY`, 외부 AI 미사용, trace, 합성 브리핑 결과 | Slides 35·38·45의 결정론적 경로 표준 자산. 라이브 AI 가드와 혼용 금지 |
| `docs/assets/ai-live-consent-disconnect.png` | 빈 BYOK 필드, 전송 동의, 질문, 대화 지우기, 연결 해제 | Slides 43·54의 라이브 AI 경계 표준 자산 |
| `docs/assets/classroom-sample-mobile-controls.png` | 390×844에서 SAMPLE 배너·복귀 버튼·합성 기업/기간 메타가 잘림 없이 표시 | A18의 모바일 표준 자산 |

### 동일 해시 자산 표준화

파일을 새로 만들거나 삭제하지 않고 다음처럼 사용 우선순위만 고정한다.

| SHA-256 동일 그룹 | 표준으로 사용할 파일 | 비권장 별칭 | 이유 |
| --- | --- | --- | --- |
| `56CBA366…` | `docs/assets/classroom-sample-ui.png` | `docs/assets/classroom-sample-header.png` | 현재 두 파일은 byte-identical이다. UI 표준 이름 하나만 PPT와 발표자 노트에서 인용 |
| `E225EEB6…` | `docs/assets/classroom-sample-mobile-controls.png` | `docs/assets/classroom-sample-mobile.png` | 현재 두 파일은 byte-identical이고 화면 내용이 모바일 상단 컨트롤에 해당 |

비권장 별칭은 기존 README 호환을 위해 남겨 두되 새 슬라이드·노트·캡처 목록에는 사용하지 않는다.

### 문서 재점검 결과

2026-09-07 최신 상태를 다시 대조했다. 이 계획 작성 단계에서는 아래 파일을 수정하지 않는다.

| 파일 | 현재 정합성 | PPT에 적용할 계약 |
| --- | --- | --- |
| `README.md` | 화면 1·2·8이 최신 합성 진입/배너/AI 동의·연결 해제 자산으로 교체됨 | 합성→실데이터→동의→연결 해제 순서 유지 |
| `docs/PARTICIPANT_PREFLIGHT.md` | 샘플 키리스 경로와 실데이터 키 필요 조건이 분리되고 라이브 동의·연결 해제가 추가됨 | m0·m2 발표자 노트와 같은 PASS/WARN 기준 사용 |
| `docs/INSTRUCTOR_RUNBOOK.md` | 로컬 bootstrap 1회/외부 0회, 라이브 전송 동의, 연결 해제 검증이 추가됨 | 13:45·14:45·15:45·16:40과 80% 전환 기준 유지 |
| `docs/COURSE_REHEARSAL_CHECKLIST.md` | 60장 계획의 조작·통과·복구 증거를 실제 수업 순서로 검증 | 최종 드레스리허설 증거 파일명과 동일하게 유지 |

`README.md`의 `127.0.0.1:8000`은 `docs/demo.html`을 보여 주는 별도 정적 문서 서버다. 앱의
골든패스 포트는 계속 `127.0.0.1:8765`이므로 이 8000 예시를 일괄 치환하지 않는다.

## 수정 원칙

- 기존 승인 스타일, 16:9 비율, 따뜻한 흰색·차콜·보라·민트 색상, 큰 한글을 유지한다.
- 한 슬라이드에는 하나의 학습 행동과 하나의 통과 기준만 둔다.
- 실제 화면은 최신 교육 릴리스에서 다시 캡처하고 설명은 화면 픽셀 위가 아니라 별도 영역에 둔다.
- 합성 모드는 첫 화면의 **합성 샘플로 시작** 버튼과 `GET /api/classroom/bootstrap` 계약을 함께
  사용한다. 화면에는 두 가상 기업과 `SAMPLE — SYNTHETIC DATA` 배너가 표시되고, 외부
  OpenDART·AI 호출은 발생하지 않는다.
- 합성 화면에는 `SAMPLE — SYNTHETIC DATA`를 항상 보이고, 실제 OpenDART 화면과 색·라벨로
  명확히 구분한다.
- 실제 키, 토큰, 실제 직원·지원자 정보는 슬라이드, 발표자 노트, 캡처에 넣지 않는다.
- AI 차단 화면은 실패가 아니라 안전 가드 성공으로 설명한다. 차단된 원문은 재노출하지 않는다.
- 외부 출처 이미지와 비자명한 외부 주장은 해당 슬라이드 노트의 `[Sources]` 블록에 기록한다.

## 본문과 부록 구성

### 본문 42장

현재 번호 기준으로 다음 슬라이드를 본문에 유지한다.

`1–5, 7, 9–11, 13, 15–22, 25–26, 28–31, 33, 35–38, 42–50, 53–56`

다음 결합을 적용한다.

- Slide 5에 현재 Slide 6의 20/80 운영 원칙을 합친다.
- Slide 50에 현재 Slide 51의 Vercel 환경변수 등록을 합친다.
- Slide 53에 현재 Slide 52의 build/deploy/alias와 공개 URL 검증을 합친다.

### 기존 부록 14장

현재 번호 `6, 8, 12, 14, 23, 24, 27, 32, 34, 39, 40, 41, 51, 52`를 부록으로
이동한다. 내용은 삭제하지 않고 빠른 반·고급 반·질문 대응 때만 연다.

- 구조·개념 참고: 8, 12, 14, 23, 27
- OpenDART 사이트·API 참고: 24
- 추가 데이터와 분석 화면: 32, 34, 39, 40, 41
- 배포 세부 화면: 51, 52
- Slide 6은 Slide 5에 병합한 뒤 운영 철학 참고본으로 둔다.

### 새 부록 4장

- `A15`: 개인정보 입력 마스킹 표식과 금지 데이터 목록
- `A16`: AI 출력 차단 reason code와 안전한 fallback 읽는 법
- `A17`: 100점 전체 루브릭, 70점 통과선, 필수 안전 게이트
- `A18`: 모바일에서 합성 모드 진입·결과 확인·실데이터 복귀

계획대로 유지하면 최종 구성은 본문 42장과 부록 18장, 총 60장이다. 본문만 순서대로 재생하는
발표용 section을 별도로 만들고, 부록은 질문·고급 실습 때만 연다.

최종 편집 시 화면에 보이는 새 페이지 번호는 확정된 본문·부록 순서로 다시 매긴다. 아래 명세는
원본 추적을 위해 현재 번호를 유지한다.

## 슬라이드 번호별 수정 명세

| 현재 번호 | 위치 | 수정할 본문·화면 | 발표자 노트의 클릭·기대 결과·실패 복구 |
| --- | --- | --- | --- |
| 3 | 본문 | 네 결과물 아래에 “합성 샘플로 먼저 검증, 공개 공시는 그다음” 한 줄 추가. 기존 완성 앱 포스터는 유지 | 완성품 시연 전에 합성/실데이터 경계를 말한다. 실제 직원 데이터는 오늘 산출물이 아니라고 확인 |
| 4 | 본문·문구 보완 | WEEK 1 질문 구조→WEEK 2 공시 근거·결정 브리프→WEEK 3 데이터 빌더 입력의 연결선을 표시 | `ready` 배지를 가리켜 근거 이용 가능성이라고 읽고, 결정 브리프의 `다음 내부 데이터` 한 항목을 필드·단위·집계수준 카드로 옮긴다. 성공확률·개인 인사조치 권고가 아니라고 확인 |
| 5 | 본문·재제작 필요 | 13:00 `m0` 환경→m1 선택→m2 합성·공시→m3 Strategy·AI→m4 저장·배포 타임라인으로 교체하고 20/80 원칙 병합. 현재 raster의 “반의 80%가 막히면”을 쓰지 않음 | `m0`과 하드 체크포인트 13:45·14:45·15:45·16:40을 모두 표시. **정시 통과율이 80% 미만이면** 체크포인트 복구본 전환 |
| 7 | 본문·재제작 필요 | 제목을 “m0 · 시작 전 자동 사전점검”으로 변경. `classroom_preflight.py` 실제 PASS/WARN/FAIL 출력과 계정 체크를 한 화면에 표시. 현재 캡처의 고정 테스트 파일 수는 최신 캡처로 교체 | 클릭/명령: `py -3.12 -X utf8 tools\classroom_preflight.py`. 기대: FAIL 0, 키 값 비노출. 포트 WARN이면 기존 서버 health 확인, 의존성 FAIL이면 `pip install -e ".[dev]"` |
| 9 | 본문·재제작 | 실제 터미널로 `dart` 이름 충돌과 `py -3.12 server.py`를 대조. `http://127.0.0.1:8765`와 정확한 app ID를 함께 표시 | 현재 폴더 확인→서버 실행→health 확인. 기대: `kr.opendart.dart-hr-briefing`. 다르면 다른 프로세스 종료 또는 앱이 안내한 대체 포트 사용 |
| 10 | 본문·재촬영 | 35:65 전후 화면. 왼쪽은 `classroom-sample-entry.png`의 **합성 샘플로 시작**을 ①로, 오른쪽은 표준 `classroom-sample-ui.png`를 ② 로드 완료로 배치. 오른쪽 화면 안의 SAMPLE 배너·복귀 버튼을 그대로 보존 | ① 클릭. 기대: 로컬 `/api/classroom/bootstrap` 1회, 두 가상 기업·2024·사업보고서, 검색/기간/provider 입력 잠김, SAMPLE 배너. 실패: 버튼이 없으면 health의 app/build ID 대조 후 최신 릴리스 사용 |
| 11 | 본문 | 제목 앞에 `m1` 배지. 완료 기준은 두 기업·연도·보고서·비교 버튼뿐 아니라 조건 변경 시 이전 결과 폐기 포함 | 참가자 행동과 13:45 종료 시각 명시. 미완료자는 기존 폴더를 보존하고 m1 worktree/ZIP 사용 |
| 13 | 본문 | 사람 역할에 “실제 개인 데이터 입력 금지”, AI 역할에 “식별자 마스킹·근거 검증” 추가 | 실제 이름·연락처를 예로 입력하지 않는다. 합성 사례를 사용하고 마스킹이 입력 허가가 아님을 설명 |
| 15 | 본문 | 첫 프롬프트의 데이터 조건을 “합성 fixture 우선, 실제 조회는 공개 기업 집계만”으로 바꿈 | 붙여넣기 전 개인·고객 데이터를 제거. 참가자가 개인 사례를 쓰면 실행을 멈추고 합성 사례로 교체 |
| 16 | 본문 | `claude auth login` 다음에 `CLAUDE.md` 확인과 preflight 실행을 추가 | Claude가 수정 전에 계획·관련 파일·검증 명령을 제시하는지 확인. 인증 실패 시 PPT의 완성 프롬프트와 체크포인트 코드로 진행 |
| 17 | 본문·부분 재촬영 | 최신 앱 첫 화면으로 교체하되 주소창 또는 터미널 콜아웃에 8765를 표시. API 키 입력 칸은 빈 상태 | 기대: 첫 화면과 4단계 진행 표시. 브라우저 자동 실행 실패 시 8765 직접 접속, 다른 화면이면 health app ID 확인 |
| 21 | 본문 | 제목을 “m1 체크포인트”로 변경하고 통과·복구 2열 구성 | 클릭: 기업 2곳, 2024, 사업보고서. 기대: 선택 수 2/8와 버튼 활성. 실패: 작업 보존 후 m1 복구본을 새 폴더에서 시작 |
| 22 | 본문 | 제목을 “MODULE 2 · 합성 데이터로 계약을 확인한 뒤 OpenDART로 갑니다”로 변경 | 실제 API 키 없이도 다음 학습이 가능함을 선언. 합성 성공 후에만 공개 기업 실조회 시연 |
| 23 | 부록 | 데이터 흐름을 2개 레인으로 수정: 로컬 bootstrap 1회→fixture 외부 호출 0회 / 실제 OpenDART. 두 레인이 같은 정규화·오케스트레이션 계약으로 합류 | `network_requests=0`을 “브라우저 요청 0회”로 말하지 않는다. 합성 evidence는 외부 원문 링크를 억제하고 실제 레인만 OpenDART 원문을 연다고 설명 |
| 24 | 부록 | OpenDART 발급 절차는 유지하되 수업 중 신규 발급이 지연될 수 있음을 표시 | 키가 없으면 합성 경로로 계속하고 발급은 사후 보완. 키 화면은 절대 캡처하지 않음 |
| 25 | 본문 | `.env` 화면에 값 대신 `••••••` 사용. preflight가 값이 아닌 설정 여부·길이만 확인한다고 추가 | 클릭: `.env.example`→`.env`, 키 입력, `git check-ignore .env`. 기대: preflight PASS. 실패: 파일명·프로젝트 루트 확인, 키 공유 금지 |
| 26 | 본문 | 비밀키 경계와 개인 HR 데이터 경계를 두 개의 별도 경로로 표현. 실제 직원·지원자 데이터 금지 목록 추가 | `.env`, 프롬프트, CSV, 캡처 네 위치를 확인. 개인 식별자가 감지돼도 마스킹 후 계속 쓰지 말고 합성 질문으로 교체 |
| 27 | 부록 | 실제 삼성전자 검색 결과는 유지. `corp_code`와 개인 식별자를 혼동하지 않도록 “기업 식별자” 표시 | 기업 코드만 사용. 직원번호·사번은 요청 입력이 아님을 설명 |
| 28 | 본문·전면 교체 | “먼저 합성 골든패스를 확인합니다.” 왼쪽 68%에 `classroom-sample-ui.png`, 오른쪽 32%에 ① 버튼 ② 두 기업/고정 기간 ③ 출처 라벨 ④ 외부 호출 0회 카드. 하단 작은 개발자 검증 inset에 `sample` JSON 네 필드만 표시 | 참가자는 **합성 샘플로 시작**을 클릭하고 화면 상태로 통과한다. 사전점검에서는 로컬 JSON을 1회 확인할 수 있지만 수업 중 endpoint 대조 시연은 강사만 수행. 기대: `enabled=True`, `network_requests=0`, real/personal=False. 실패: app/build ID 확인 후 준비 캡처로 진행 |
| 29 | 본문·재제작 | 정상 로딩 화면 옆에 45초 timeout, 조건 변경 시 이전 요청 취소, 오류 request ID의 세 상태를 작은 순서도로 표시 | 정상: 중복 클릭 금지. timeout이면 **최초 요청 포함 최대 3회(재시도 최대 2회)**에서 멈추고 합성 경로 전환. 연도 변경 후 이전 응답이 나타나지 않아야 함. request ID만 조교에게 전달 |
| 30 | 본문·부분 재촬영 | 52:48 비교. 왼쪽은 `classroom-sample-ui.png`에서 `2024년 · 사업보고서 · SAMPLE`과 `합성 fixture · 원문 링크 없음`을 읽히게 crop, 오른쪽은 최신 라이브 Overview의 `OpenDART 원문` crop. 같은 위치에 SAMPLE/OPEN DART 라벨을 붙임 | 왼쪽에서는 샘플 숫자를 실제 기업 수치로 인용하지 않고 원문을 찾지 않는다. 오른쪽에서는 기업·연도·보고서·단위·원문 링크를 확인. 두 상태를 한 캡처처럼 합성하지 않음 |
| 31 | 본문 | Compare 유지. 결측과 실제 0 외에 `error`를 세 번째 상태로 표시 | 참가자가 세 상태를 짚는다. error이면 요청 ID와 조건만 기록하고 키·응답 원문은 공유하지 않음 |
| 32 | 부록 | Trend 화면은 참고 기능으로 이동. 45초 deadline 안에서 조회 범위를 나누는 운영 팁 추가 | 재무 기업×연도 48, People 32 한도를 넘기지 않도록 범위를 줄임 |
| 33 | 본문 | People 화면은 기업 집계만이라는 배지를 추가하고 개인 데이터가 없음을 명시 | 직원 수·급여·근속은 집계값으로만 읽는다. 개인 성과·보상 공정성으로 확장하지 않음 |
| 34 | 부록 | Executives를 개인 평가가 아닌 구성·공시 범위 비교로 다시 강조 | 이름이나 개인 리더십 평가 질문을 받으면 거버넌스 집계 질문으로 바꿈 |
| 35 | 본문·재촬영 | 제목을 “m2 체크포인트 · 합성/실제와 근거를 구분했는가”로 변경. 표준 `classroom-sample-ui.png`의 배너·복귀·합성 출처 crop과 `classroom-sample-strategy.png`의 SOURCE LINKS·QUALITY GATE crop을 가로 3칸에 배치 | 기대: 배너, 두 고정 기업, 합성 근거 ID, 외부 링크 없음. 이어 **인력·보상 비교**를 눌러도 외부 호출이 없어야 함. OpenDART 장애면 이 세 증거와 bootstrap 계약으로 통과 |
| 37 | 본문 | 품질 규칙에 `timeout`, `aborted`, `request ID`를 추가. 0·결측·오류·취소를 4개 상태로 분리 | 조건을 바꿔 이전 요청을 취소하는 시연. 기대: stale 결과가 화면을 덮지 않음. timeout은 숫자 0이나 데이터 없음으로 바꾸지 않음 |
| 38 | 본문·재촬영 | `classroom-sample-strategy.png`를 오른쪽 70%에 배치하고 SOURCE LINKS·DETERMINISTIC POLICY·TRACE·`다음 내부 데이터`를 ①②③④로 표시. 왼쪽 30%에는 “합성 사실 / 모델 추정 / 확인 불가 / WEEK 3 입력” 읽기 순서를 둠 | Strategy Brief 탭 클릭. 기대: 외부 원문 링크 없음, deterministic policy 허용, trace 완료. `ready`는 근거 이용 가능성일 뿐 성공확률·조치 권고가 아님을 말하고, `다음 내부 데이터` 한 항목을 WEEK 3 필드 카드로 옮긴다. 이어 **합성 결정 브리핑 만들기**를 누르면 키·동의 없이 같은 fixture 답변과 `외부 AI가 생성한 답변이 아닙니다` 표시 |
| 42 | 본문 | CSV 내보내기에 “합성/실제 구분과 키·개인정보 없음” 검사 추가 | CSV 첫 행과 메타데이터 확인. 개인 열 추가 금지. 다운로드 실패 시 비교 완료 여부와 브라우저 권한 확인 |
| 43 | 본문·전면 재촬영 | 최신 라이브 AI 패널을 왼쪽 58%에 배치해 빈 키 입력, 미체크 전송 동의, **AI에게 질문하기**, **대화 지우기**, **AI 키·대화 연결 해제**가 한 화면에 보이게 한다. 오른쪽은 ① BYOK ② 동의 필수 ③ 연결 해제 범위 | 키는 촬영 전 비우고 합성 기업 질문만 입력. 전송 동의 전 실행이 거부되는지 확인한 뒤 동의→1회 실행. **대화 지우기**와 **연결 해제**를 각각 눌러 후자는 키·연결·대화·동의가 모두 제거됨을 확인 |
| 44 | 본문·부분 재촬영 | 위 60%는 `classroom-sample-ui.png`의 합성 AI 패널 crop으로 제목·비활성 키/동의·**합성 결정 브리핑 만들기**를 표시. 아래 40%는 “확인된 수치 / 인과 아닌 가설 / 추가 내부 데이터” 세 안전 질문 카드 | 샘플 모드에서는 키 입력·전송 동의 없이 합성 버튼 클릭. 기대: 로컬 fixture의 결정론적 답변, 외부 AI 미생성 문구. 실제 이름·연락처·사번 질문이면 실행하지 않고 합성 질문으로 교체 |
| 45 | 본문·전면 재촬영 | 48:52 이중 경로. 왼쪽은 `classroom-sample-strategy.png`의 합성 답변+DETERMINISTIC POLICY crop, 오른쪽은 로컬 live UI에서 `/api/analysis` 거절 계약을 route mock으로 재현한 `ai-policy-fallback.png`. 가운데에 “결정론적 합성 정상 경로 / 정책 차단 UI 계약 재현(mock)” 경계선을 둠 | 합성 경로는 차단 테스트가 아니라 결정론적 정상 경로다. 오른쪽은 실제 provider 응답이 아니며 외부 DART/provider 요청 0회다. 네 reason code, 차단 원문 비표시, 근거 fallback·한계, `QA 회사`와 `qa request ID`가 보이는지 확인 |
| 46 | 본문 | 제목을 “m3 체크포인트 · 답변보다 근거 경계를 증명했는가”로 변경 | 근거 ID, 공시 사실/계산/가설, 개인판단 없음 확인. 외부 AI 장애 참가자도 fallback 검증으로 동일 통과 |
| 48 | 본문 | Git 제외 대상에 `.env`, 합성 캡처 원본, 대용량 PPT 생성물 구분. 합성 fixture 소스는 공개 가능한 비개인 데이터임을 별도 표시 | `git status`, `git check-ignore .env`, staged 파일 확인. 키가 보이면 commit 금지, 즉시 폐기·재발급 절차 안내 |
| 49 | 본문·재촬영 권장 | 최신 교육 릴리스의 GitHub 파일 목록과 커밋으로 교체. 새 문서·preflight·classroom fixture가 보이게 함 | 원격 저장소가 본인 것인지 확인. 충돌이면 기존 작업을 보존하고 개인 브랜치 또는 체크포인트 ZIP 사용 |
| 50 | 본문 | Slide 51을 병합해 “Vercel 연결+환경변수” 한 장으로 구성. `OPENDART_API_KEY`와 선택 모델명만 보이고 값은 마스킹 | Import→루트→환경변수 이름 확인. 권한 실패 시 강사 URL로 검증하고 개인 배포는 사후 과제로 전환 |
| 53 | 본문·재촬영 | Slide 52를 병합해 build→deploy→alias→root/health 검증을 한 장에 표시. 최신 production 화면과 build ID 사용 | 기대: root 200, health의 app ID·build ID 일치, 기업 검색 1회 성공. 지연/404면 로그와 request ID 확인 후 강사 URL로 대체 |
| 54 | 본문·전면 교체 | 2×2 복구 카드: 포트/health, 45초 timeout+request ID, **합성 샘플로 시작**, **AI 키·대화 연결 해제**. 하단에 OpenDART 시도당 10초·최초 요청 포함 최대 3회(재시도 최대 2회)와 Git/Vercel 대체 URL을 한 줄로 둠 | 2분: 주소·app/build ID·오류 범주·request ID만 수집. 5분: 최초 요청 포함 최대 3회에서 멈춤→합성 버튼. AI 상태가 꼬이면 연결 해제로 키·대화·동의 제거. 정상 복귀는 단일 요청 성공 후 |
| 55 | 본문 | 제목 앞에 `m4` 배지. 제출물에 preflight 요약, GitHub, Vercel, 근거 화면, AI 또는 fallback 증거 추가 | 16:40까지 배포 미완료면 강사 URL로 기능 검증 후 개인 배포를 사후 과제로 전환. 키 노출은 즉시 제출 중단 |
| 56 | 본문 | 종료 화면에 최소 루브릭 요약: 재현15·데이터25·해석20·AI안전15·저장소15·배포10. 70점과 필수 안전 게이트 표시 | 점수보다 필수 게이트를 먼저 확인. 키/개인정보 노출, 무근거 수치, 개인평가·자동 인사조치는 수정 후 재검토 |
| A15 | 새 부록 | 직접 식별자 마스킹 표식 5종과 “마스킹은 입력 허가가 아님”을 정리 | 합성 문자열만 사용. 실제 입력을 재현하지 않음 |
| A16 | 새 부록 | 네 출력 reason code, 사용자용 라벨, fallback 읽기 순서를 표로 정리 | 차단 원문을 복원하거나 재사용하지 않음. 근거 ID→공시 원문→한계 순서로 확인 |
| A17 | 새 부록 | 강사용 전체 100점 루브릭과 필수 게이트 | 외부 AI 장애 시 fallback 검증을 동등한 증거로 인정 |
| A18 | 새 부록 | 표준 `classroom-sample-mobile-controls.png`를 왼쪽 60%에 두고 오른쪽 40%에 “진입→SAMPLE 확인→복귀” 세 단계와 390px 무가로넘침 통과 기준을 둠 | 캡처에서 SAMPLE 배너·복귀 버튼·합성 기업/기간을 확인. 실제 앱에서 복귀를 눌러 선택 0개·welcome 화면·검색 가능 상태까지 검증 |

## 최종 60장 자산·조작·통과 증거 대조표

표의 `원본`은 기존 full-slide raster를 그대로 제출한다는 뜻이 아니라 승인된 스타일·구도 참조로
사용한다는 뜻이다. 내용이 바뀌는 슬라이드는 해당 원본 구도를 바탕으로 다시 제작한다. `미촬영`은
파일명이 확정됐지만 현재 디스크에 없는 캡처이며 PPT 최종 제작 전에 반드시 실제 경로를 만들어야
한다. 모든 60장에는 최소 하나의 존재하는 참조 자산, 강사 조작, 학습자 통과 증거가 지정돼 있다.

### 본문 42장

| 최종 | 현재 | 실제 사용할 자산 파일명·상태 | 강사 조작 | 학습자 통과 증거 |
| --- | ---: | --- | --- | --- |
| B01 | 1 | `training_deck/origin_image/slide_01.png` | 제목·WEEK 2·4시간 약속을 가리킨다 | 오늘 만들 도구를 “공개 기업 공시 기반 HR 브리핑”으로 한 문장 설명 |
| B02 | 2 | `training_deck/origin_image/slide_02.png` | 핵심 질문을 읽고 기업·연도 선택 결과를 묻는다 | “인당 생산성 비교” 질문과 필요한 기업/기간 조건을 적음 |
| B03 | 3 | `docs/assets/dart-workforce-demo-poster.png` | 네 결과물과 “합성 먼저” 순서를 가리킨다 | 대시보드·브리핑·GitHub·배포 URL 네 산출물을 체크 |
| B04 | 4 | `training_deck/origin_image/slide_04.png` | WEEK 1 질문 구조→WEEK 2 공시 근거·결정 브리프→WEEK 3 데이터 빌더 입력의 연결선을 따라 포인터를 이동한다 | `ready`는 근거 이용 가능성이고 `다음 내부 데이터`가 합성 필드·단위·집계수준 카드로 이어지며 성공확률·인사조치 권고가 아님을 설명 |
| B05 | 5 | `training_deck/origin_image/slide_05.png`(재생성 필요: 80% 문구 교체) | m0~m4와 13:45·14:45·15:45·16:40을 순서대로 짚는다 | 네 하드 체크포인트 시각과 “정시 통과율 80% 미만” 전환 규칙을 기록 |
| B06 | 7 | `training_deck/origin_image/slide_07.png`; `training_deck/assets/screenshots/classroom-preflight-pass.png`(재촬영·재생성 필요: 고정 테스트 파일 수 제거 또는 최신화) | `py -3.12 -X utf8 tools\classroom_preflight.py` 실행 | FAIL 0, 키 값 비노출, OpenDART 키 WARN은 합성 경로에서 허용 |
| B07 | 9 | `training_deck/origin_image/slide_09.png`; `training_deck/assets/screenshots/terminal-start-8765-health.png`(촬영 완료) | `python server.py` 후 8765 health 확인 | `app.id=kr.opendart.dart-hr-briefing`, root/health 동일 인스턴스 |
| B08 | 10 | `docs/assets/classroom-sample-entry.png`; `docs/assets/classroom-sample-ui.png` | **합성 샘플로 시작**을 한 번 클릭 | 샘플 기업 2개, SAMPLE 배너, 2024·사업보고서, 입력 잠김 |
| B09 | 11 | `training_deck/origin_image/slide_11.png` | m1 목표와 13:45 완료 기준을 읽는다 | 기업 2개·기간·비교 가능·조건 변경 시 이전 결과 폐기를 말함 |
| B10 | 13 | `docs/assets/classroom-sample-entry.png`(표준, slide 13 재생성 필요) | 사람/AI 역할과 개인정보 금지선을 대조한다 | 실제 개인 데이터 없이 합성 사례를 선택하고 인간 검증 책임을 표시 |
| B11 | 15 | `training_deck/origin_image/slide_15.png` | 합성 fixture 우선 프롬프트를 복사해 붙인다 | 사용자·문제·입력·데이터·경계·완료 기준 여섯 칸 확인 |
| B12 | 16 | `training_deck/origin_image/slide_16.png` | `claude auth login`→`CLAUDE.md`→변경 계획 순서 시연 | 인증 상태, 수정 파일, 검증 명령을 확인한 화면 또는 기록 |
| B13 | 17 | `docs/assets/classroom-sample-entry.png`; `training_deck/assets/screenshots/terminal-start-8765-health.png`(촬영 완료) | 로컬 주소를 열고 첫 화면의 합성 버튼·4단계를 가리킨다 | 빈 키, 기업 0/8, 합성 버튼, 정확한 8765/app ID 확인 |
| B14 | 18 | `training_deck/assets/screenshots/company-search-samsung.png` | 공개 기업명 또는 종목코드를 검색한다 | 법인명·종목코드·DART 기업 식별자 후보 표시 |
| B15 | 19 | `training_deck/assets/screenshots/companies-selected.png` | 공개 기업 두 곳을 추가하고 중복·삭제를 확인한다 | 선택 2/8, 중복 없음, 선택 카드가 실제 조작과 일치 |
| B16 | 20 | `training_deck/assets/screenshots/period-controls.png` | 2024년·사업보고서를 선택하고 조건을 바꿔 본다 | 조건 변경 뒤 이전 결과가 새 화면을 덮지 않음 |
| B17 | 21 | `training_deck/assets/screenshots/workshop-progress-selected.png` | m1 통과 인원을 집계하고 미완료자를 복구본으로 보낸다 | m1 증거 캡처와 13:45 통과 상태 제출 |
| B18 | 22 | `training_deck/origin_image/slide_22.png` | 합성 bootstrap과 실제 OpenDART 두 경로를 소개한다 | “로컬 GET 1회·fixture 외부 호출 0회”를 구분해 설명 |
| B19 | 25 | `training_deck/origin_image/slide_25.png` | `.env.example`→`.env`와 `git check-ignore .env` 시연 | 키 값 없이 설정 여부와 `.env` 제외 결과만 표시 |
| B20 | 26 | `training_deck/origin_image/slide_26.png` | 비밀키 경로와 개인 HR 데이터 금지 경로를 각각 가리킨다 | `.env`·프롬프트·CSV·캡처 네 위치의 금지 항목 체크 |
| B21 | 28 | `docs/assets/classroom-sample-ui.png`; `training_deck/assets/screenshots/classroom-bootstrap.png`(촬영 완료) | 참가자는 합성 버튼으로 진입하고, 강사는 수업 중 bootstrap 계약을 대조한다 | enabled true, network 0, real/personal false와 화면 SAMPLE 상태 일치 |
| B22 | 29 | `training_deck/assets/screenshots/comparison-loading.png`; `training_deck/assets/screenshots/comparison-timeout.png`(촬영 완료)·`training_deck/assets/screenshots/request-id-error.png`(촬영 완료)·`training_deck/assets/screenshots/selection-aborted.png`(촬영 완료) | 비교 클릭→45초 timeout→조건 변경 취소 세 상태 시연 | 중복 요청 없음, stale 결과 없음, 서버 오류 request ID만 기록 |
| B23 | 30 | `docs/assets/classroom-sample-ui.png`; `training_deck/assets/screenshots/tab-overview.png` | 합성 Overview와 라이브 Overview의 같은 위치를 번갈아 가리킨다 | SAMPLE/합성 출처와 OpenDART 원문·기업·기간·단위를 구분 |
| B24 | 31 | `training_deck/assets/screenshots/tab-compare.png` | Compare에서 0·결측·오류 행을 짚는다 | 세 상태를 서로 다른 의미로 설명하고 오류 시 조건/request ID만 제출 |
| B25 | 33 | `training_deck/assets/screenshots/tab-people.png` | 직원 수·급여·근속·인당 지표의 분모를 가리킨다 | 기업 집계값만 읽고 개인 성과·보상 판단으로 확장하지 않음 |
| B26 | 35 | `docs/assets/classroom-sample-ui.png`; `docs/assets/classroom-sample-strategy.png`; `training_deck/assets/screenshots/classroom-bootstrap.png`(촬영 완료) | SAMPLE 배너→합성 출처→SOURCE LINKS/QUALITY GATE 순서 확인 | 합성 근거 ID, 외부 링크 없음, 실제 원문과의 경계로 m2 통과 |
| B27 | 36 | `training_deck/origin_image/slide_36.png` | 네 계산식의 분자·분모와 단위를 가리킨다 | 인력증가율·평균급여·인당매출·인당영업이익 정의를 작성 |
| B28 | 37 | `training_deck/origin_image/slide_37.png`; `training_deck/assets/screenshots/selection-aborted.png`(촬영 완료) | 0·결측·오류·취소 네 상태와 stale 폐기를 시연 | timeout/aborted를 숫자 0이나 데이터 없음으로 바꾸지 않음 |
| B29 | 38 | `docs/assets/classroom-sample-strategy.png` | Strategy의 SOURCE LINKS→POLICY→TRACE→`다음 내부 데이터`를 짚고 합성 브리핑 실행 | `ready`를 근거 이용 가능성으로 설명하고 한 항목을 WEEK 3 합성 필드·단위·집계수준 카드로 변환 |
| B30 | 42 | `training_deck/assets/screenshots/metric-toolbar.png`; `docs/assets/classroom-sample-ui.png` | 지표 선택·초기화 후 합성 CSV 내보내기 클릭 | `classroom-synthetic-2024.csv`, 합성 메타, 키·개인 열 없음 |
| B31 | 43 | `docs/assets/ai-live-consent-disconnect.png` | 동의 전 실행 거부→동의→1회 실행→연결 해제 순서 시연 | 빈 키 캡처, 전송 동의 경계, provider 상태, 연결 해제 범위 확인 |
| B32 | 44 | `docs/assets/classroom-sample-ui.png`; `training_deck/origin_image/slide_44.png` | 비활성 키·동의를 가리키고 합성 결정 브리핑 실행 | 키·동의 없이 외부 AI 미생성 문구와 안전 질문 3종 확인 |
| B33 | 45 | `docs/assets/classroom-sample-strategy.png`; `training_deck/assets/screenshots/ai-policy-fallback.png`(촬영 완료) | 합성 정상 경로와 로컬 live UI의 `/api/analysis` 거절 route mock을 분리해 보여 준다 | 외부 DART/provider 요청 0회, reason code·근거 fallback·한계·`QA 회사`·`qa request ID` 확인 |
| B34 | 46 | `training_deck/assets/screenshots/workshop-progress-after-question.png`; `training_deck/assets/screenshots/ai-policy-fallback.png`(촬영 완료) | m3 증거를 근거 ID→사실/가설→개인판단 없음 순으로 점검하고 mock 표식을 읽는다 | 실제 라이브 provider 응답으로 설명하지 않고 정책 차단 UI 계약 재현 증거로 15:45 m3 통과 |
| B35 | 47 | `training_deck/origin_image/slide_47.png` | 코드→비밀 분리→배포→검증 흐름을 따라 포인터 이동 | m4에서 제출할 GitHub·Vercel·health 증거를 나열 |
| B36 | 48 | `training_deck/origin_image/slide_48.png` | `git status`, `git check-ignore .env`, staged diff를 순서대로 확인 | `.env`·키·개인정보·비의도 대용량 파일이 staged에 없음 |
| B37 | 49 | `training_deck/assets/screenshots/github-repository.png`(최종 commit 뒤 재촬영) | 원격 소유권·브랜치·최신 commit을 확인한다 | 실제 GitHub 주소와 로컬/원격 commit 일치, `.env` 없음 |
| B38 | 50 | `training_deck/origin_image/slide_50.png` | Vercel Import→루트→환경변수 이름을 가리킨다 | 본인 저장소 연결, 변수 이름만 보이고 값은 비노출 |
| B39 | 53 | `training_deck/assets/screenshots/production-app-final.png`(최종 배포 뒤 재촬영) | 실제 배포 root와 `/api/health`를 연다 | root 200, 정확한 app ID, commit/build ID 일치 |
| B40 | 54 | `training_deck/origin_image/slide_54.png`; `training_deck/assets/screenshots/comparison-timeout.png`(촬영 완료)·`training_deck/assets/screenshots/request-id-error.png`(촬영 완료); `docs/assets/ai-live-consent-disconnect.png` | 포트→timeout/request ID→합성 전환→AI 연결 해제 순서 시연 | 2분 진단·5분 복구와 최초 요청 포함 최대 3회(재시도 최대 2회) 제한을 선택 |
| B41 | 55 | `training_deck/origin_image/slide_55.png` | 새 공개 기업 비교부터 GitHub/Vercel 증거까지 재현을 시작시킨다 | preflight·근거·AI/fallback·GitHub·Vercel 묶음 제출 |
| B42 | 56 | `training_deck/origin_image/slide_56.png` | 100점 루브릭과 필수 안전 게이트를 먼저 확인한다 | 70점 이상이며 키/개인정보·무근거 수치·개인평가·자동조치 없음 |

### 부록 18장

| 최종 | 현재 | 실제 사용할 자산 파일명·상태 | 강사 조작 | 학습자 통과 증거 |
| --- | ---: | --- | --- | --- |
| A01 | 6 | `training_deck/origin_image/slide_06.png` | 20/80 운영 원칙을 질문 때만 연다 | 시연→재현→통과→저장 순서를 말함 |
| A02 | 8 | `training_deck/origin_image/slide_08.png` | 파일 트리에서 코드·비밀·배포 산출물을 가리킨다 | `server.py`, `static/`, `.env`, 배포 설정의 역할 구분 |
| A03 | 12 | `training_deck/origin_image/slide_12.png` | Input→Collect→Calculate→Explain→Verify를 따라간다 | Agent를 대화창이 아닌 검증 흐름으로 설명 |
| A04 | 14 | `training_deck/origin_image/slide_14.png` | 프롬프트 여섯 칸을 빠진 항목 없이 확인한다 | 여섯 칸이 채워진 합성·공개 기업 프롬프트 |
| A05 | 23 | `training_deck/origin_image/slide_23.png` | 합성 로컬 레인과 실제 OpenDART 레인을 분리해 가리킨다 | 로컬 bootstrap 1회와 외부 호출 0회, 실제 원문 레인을 구분 |
| A06 | 24 | `training_deck/assets/screenshots/opendart-home.png`; `training_deck/assets/screenshots/opendart-guide.png` | 공식 키 발급 위치만 가리키고 값 입력 화면은 공유하지 않는다 | 키가 없으면 합성 경로를 선택하고 발급은 사후 보완 |
| A07 | 27 | `training_deck/assets/screenshots/company-search-samsung.png` | corp_code·종목코드·법인명을 각각 짚는다 | 기업 식별자와 사번/개인 식별자를 혼동하지 않음 |
| A08 | 32 | `training_deck/assets/screenshots/tab-trend.png` | 조회 연도 범위와 추세선을 가리킨다 | 비교 기준·범위·결측 연도를 설명 |
| A09 | 34 | `training_deck/assets/screenshots/tab-executives.png` | 임원 구성·공시 범위를 가리키고 개인 평가 질문을 멈춘다 | 개인 리더십 평가가 아닌 기업 공시 수준 비교만 말함 |
| A10 | 39 | `training_deck/assets/screenshots/tab-radar.png` | 표준화 기준과 상대 비교 범위를 가리킨다 | 레이더 크기를 절대 우수성으로 해석하지 않음 |
| A11 | 40 | `training_deck/assets/screenshots/tab-scatter.png` | 축·기업 위치·상관 한계를 가리킨다 | 위치 관계를 인과로 단정하지 않음 |
| A12 | 41 | `training_deck/assets/screenshots/tab-rank.png` | 선택 기업 내 순위와 비교 조건을 함께 읽는다 | 외부 업계 순위로 오해하지 않고 조건을 기록 |
| A13 | 51 | `training_deck/origin_image/slide_51.png` | Vercel 변수명·환경만 보여 주고 값은 가린다 | `OPENDART_API_KEY` 이름과 Production 범위만 확인 |
| A14 | 52 | `training_deck/origin_image/slide_52.png` | build→deploy→alias 흐름과 로그 위치를 가리킨다 | 실제 READY·URL은 B39에서 검증하며 이 장에서 성공을 추측하지 않음 |
| A15 | 신규 | `training_deck/final_60_revisions/origin_image/slide_57.png`(recorded) | 다섯 마스킹 표식과 실제 입력 금지를 읽는다 | 합성 문자열에서만 `[REDACTED_*]` 5종 의미를 구분 |
| A16 | 신규 | `training_deck/final_60_revisions/origin_image/slide_58.png`(recorded); `training_deck/assets/screenshots/ai-policy-fallback.png`(촬영 완료) | route mock 표식→네 reason code→근거 ID→공시 원문→한계 순으로 가리킨다 | 외부 DART/provider 요청 0회이며 차단 원문을 복원하지 않고 fallback 검증 순서를 재현 |
| A17 | 신규 | `training_deck/final_60_revisions/origin_image/slide_59.png`(recorded) | 100점 배점과 필수 안전 게이트를 대조한다 | 외부 AI 장애의 fallback을 동등 증거로 채점 |
| A18 | 신규 | `training_deck/final_60_revisions/origin_image/slide_60.png`(recorded); `docs/assets/classroom-sample-mobile-controls.png`(표준) | 390px에서 SAMPLE 배너·복귀를 가리키고 실제 복귀 클릭 | 가로 넘침 없음, 복귀 뒤 선택 0·welcome·검색 가능 |

### 60장 대조 결론

- 자산 파일명 지정: `60/60`. 강사 조작 지정: `60/60`. 학습자 통과 증거 지정: `60/60`.
- 현재 존재하지 않는 필수 캡처는 0개다.
- 현재 존재하지만 최종 교육 commit/build 증거로 재촬영해야 하는 자산은
  `training_deck/assets/screenshots/github-repository.png`,
  `training_deck/assets/screenshots/production-app-final.png` 2개다.
- 신규 부록 A15~A18의 final full-slide raster는
  `training_deck/final_60_revisions/origin_image/slide_57.png`~`slide_60.png`로 recorded 상태다.
- `slide_37`·`slide_39` job은 최신 GitHub·배포 증거가 확보될 때까지 pending이다. 레거시
  `training_deck/training_deck.pptx`는 최종 편성의 기준 파일이 아니다. 두 증거를 최신 commit/build로
  기록하고 총 60장 PPTX를 조립·렌더 검수하기 전에는 최종본으로 선언하지 않는다.

## 다시 촬영할 화면

### 필수 신규·재촬영 및 촬영 완료 현황

| 제안 파일 | 사용 슬라이드 | 캡처 내용 | 검증 조건 |
| --- | --- | --- | --- |
| `training_deck/assets/screenshots/classroom-preflight-pass.png`(촬영 완료) | 7 | 실제 preflight 출력 | 키 값 없음, FAIL 0, 실행한 Python 버전 표시 |
| `training_deck/assets/screenshots/terminal-start-8765-health.png`(촬영 완료) | 9, 17 | 서버 시작, 실제 주소, health app ID | `127.0.0.1:8765`, 정확한 app ID·build ID |
| `docs/assets/classroom-sample-entry.png` | 10 | 클릭 전 최신 첫 화면 | **합성 샘플로 시작** 버튼, 키·동의 미입력, 실제 기업 미선택 |
| `docs/assets/classroom-sample-ui.png`(표준) | 10, 28, 30, 35, 44 | 합성 모드 상단과 Overview | 두 가상 기업, SAMPLE 배너·복귀, 합성 메타·출처, 결정론적 버튼 |
| `docs/assets/classroom-sample-strategy.png`(표준) | 35, 38, 45 | 합성 Strategy evidence와 합성 답변 | 외부 원문 링크 없음, deterministic policy, trace, 외부 AI 미사용 |
| `docs/assets/classroom-sample-mobile-controls.png`(표준) | A18 | 390×844 합성 상단 컨트롤 | SAMPLE 배너, 복귀 버튼, 합성 기업·기간, 잘림·가로 넘침 없음 |
| `docs/assets/classroom-sample-header.png`(비권장) | 사용하지 않음 | `classroom-sample-ui.png`와 동일 해시 | 호환 보존만 하고 새 슬라이드·노트에서 인용 금지 |
| `docs/assets/classroom-sample-mobile.png`(비권장) | 사용하지 않음 | `classroom-sample-mobile-controls.png`와 동일 해시 | 호환 보존만 하고 새 슬라이드·노트에서 인용 금지 |
| `training_deck/assets/screenshots/classroom-bootstrap.png`(촬영 완료) | 28, 35 | 합성 bootstrap의 `sample` 객체 | enabled, `network_requests: 0`(fixture 외부 요청), real/personal false, 워터마크 모두 표시 |
| `training_deck/assets/screenshots/comparison-timeout.png`(촬영 완료) | 29, 54 | 45초 timeout 사용자 메시지 | DOM 조작이 아니라 실제 fetch deadline 경로, 키·민감 응답 없음 |
| `training_deck/assets/screenshots/request-id-error.png`(촬영 완료) | 29, 31, 54 | 안전한 오류와 request ID | 내부 예외·키 없음, bounded request ID만 표시 |
| `training_deck/assets/screenshots/selection-aborted.png`(촬영 완료) | 29, 37 | 조회 중 연도 변경 후 이전 요청 폐기 | stale 결과가 새 조건 화면을 덮지 않음 |
| `training_deck/assets/screenshots/ai-policy-fallback.png`(촬영 완료) | 45, 46, 54 | 로컬 live UI의 `/api/analysis` 거절 route mock, 새 reason code와 검증 fallback | 실제 provider 응답 아님, 외부 DART/provider 요청 0회, 차단 원문 비표시, 근거 ID·한계·`QA 회사`·`qa request ID` 표시 |
| `docs/assets/ai-live-consent-disconnect.png` | 43, 54 | 최신 라이브 AI 패널 | 빈 키, 전송 동의, 질문/대화 지우기/연결 해제 버튼이 함께 보임 |
| `training_deck/assets/screenshots/github-repository.png` | 49 | 최신 교육 릴리스 저장소 | 2026-09-06 자산이므로 최종 commit 뒤 같은 경로로 재촬영. `.env` 없음 |
| `training_deck/assets/screenshots/production-app-final.png` | 53 | 최신 배포의 root와 health 증거 | 2026-09-06 자산이므로 최종 배포 뒤 같은 경로로 재촬영. commit/build ID 일치 |

### 조건부 재촬영

- `training_deck/assets/screenshots/app-home.png`: 기존 자산에는 합성 진입 버튼이 없으므로 새 PPT에서
  쓰지 않는다. 첫 화면은 표준 `docs/assets/classroom-sample-entry.png`로 교체한다.
- `comparison-loading.png`: 정상 로딩 UI가 바뀌지 않으면 유지하고 timeout 캡처를 별도로 추가한다.
- `training_deck/assets/screenshots/ai-question-panel.png`: 기존 자산에는 전송 동의와 연결 해제가 없어
  새 PPT에서 쓰지 않는다. 표준 `docs/assets/ai-live-consent-disconnect.png`로 교체한다.
- `strategy-evidence.png`: 정상 evidence 화면은 유지할 수 있으나 AI 차단 증거로 재사용하지 않는다.
- `tab-overview.png`, `tab-compare.png`, `tab-people.png`, `tab-strategy.png`: 최종 build ID의 UI·수치
  계약이 기존 촬영본과 같을 때만 유지한다.

### 캡처 규칙

1. 최신 교육 릴리스 commit을 고정하고 root와 health의 build ID를 먼저 기록한다.
2. 1536×960, device scale 2, 밝은 테마를 기본으로 하고 핵심 영역은 별도 crop도 저장한다.
3. 정상 화면은 실제 앱을 조작해 캡처한다. timeout·오류는 로컬 결정론적 장애 harness로 실제 코드
   경로를 실행하며, 슬라이드에 “장애 시뮬레이션”이라고 표시한다.
4. 스크린샷의 숫자·문구·상태를 생성 이미지로 다시 그리지 않는다.
5. 키 입력 칸은 비우거나 `••••••`로 보이게 하고 `.env`나 개발자 도구의 헤더를 촬영하지 않는다.
6. 실제 화면 위에 설명을 합성하지 않고 PPT 레이아웃의 바깥 설명 영역에 배치한다.
7. 합성 캡처는 Network 로그에서 로컬 `/api/classroom/bootstrap` 1회와 외부 요청 0회를 검증한 뒤
   찍는다. 슬라이드에는 외부 호출 0회만 표시하고 개발자 로그는 발표자 노트 출처로 둔다.
8. 동일 해시 별칭은 표준 파일 한쪽만 사용한다. 데스크톱은 `classroom-sample-ui.png`, 모바일은
   `classroom-sample-mobile-controls.png`만 새 슬라이드와 노트에서 인용한다.

## 발표자 노트 표준

모든 본문 슬라이드 노트는 다음 순서로 다시 작성한다.

```text
[권장 시간] 2분 30초
[강사 조작] 클릭 위치 또는 정확한 명령
[수강생 행동] 한 문장으로 재현할 행동
[기대 결과] 화면의 정확한 상태·문구·ID
[통과 기준] 다음 슬라이드로 넘어갈 객관적 조건
[실패 복구] 2분 진단, 5분 대체 경로, 복귀 기준
[체크포인트] m0/m1/m2/m3/m4 또는 해당 없음
[Sources]
- 저장소 commit과 근거 파일/공식 외부 페이지
```

### 핵심 시연 슬라이드의 필수 노트 문안

| 슬라이드 | `[강사 조작]`에 반드시 기록 | `[기대 결과]`·`[통과 기준]`에 반드시 기록 | `[실패 복구]`에 반드시 기록 |
| --- | --- | --- | --- |
| 10·28 | 왼쪽 **합성 샘플로 시작**을 한 번 클릭하고 중복 클릭하지 않는다 | 로컬 bootstrap 1회, 샘플 기업 정확히 2개, 2024/11011, SAMPLE 배너, 검색·기간·키·동의 잠김, 외부 OpenDART·AI 0회 | 버튼 없음: 8765 health의 app/build ID 확인. bootstrap 오류: 키를 요구하지 말고 준비 캡처와 계약 JSON으로 계속 |
| 35·38 | Overview→Strategy Brief→**합성 결정 브리핑 만들기** 순으로 클릭한다 | 출처 `합성 fixture · 원문 링크 없음`, deterministic policy, 외부 AI 미사용, 동일 fixture의 결정론적 결과, CSV 이름 `classroom-synthetic-2024.csv` | 원문 링크를 찾거나 AI 키를 넣지 않는다. 화면 불일치 시 샘플을 종료한 뒤 한 번만 다시 진입하고, 재발하면 고정 캡처 사용 |
| 43 | 실데이터 화면에서 합성 기업 질문을 입력하고 동의 전 실행 거부를 확인한 뒤, 빈 화면 공유 상태에서 키 입력→전송 동의→1회 실행한다 | 동의 전 외부 호출 없음. 실행 후 provider·연결 상태만 공유. **대화 지우기**는 질문/대화 초기화, **연결 해제**는 키·연결·대화·동의 제거 | 키·한도·네트워크 실패는 Strategy Brief로 계속. 키 문자열이나 오류 응답 본문을 채팅·슬라이드에 복사하지 않음 |
| 44 | 샘플 모드로 돌아가 비활성 키·동의를 가리킨 뒤 **합성 결정 브리핑 만들기** 클릭 | 키·동의 없이 로컬에서 생성, `외부 AI가 생성한 답변이 아닙니다`, 외부 요청 증가 없음 | 샘플에서 동의를 요구하거나 provider가 연결되면 잘못된 build이므로 health 확인 후 고정 캡처 사용 |
| 45·46 | 합성 결정론적 결과와 라이브 정책 차단 결과를 차례로 보여 주되 같은 실행이라고 말하지 않는다 | 라이브 차단에서 네 reason code 중 해당 사유, 차단 원문 비표시, 검증된 근거 fallback, 근거 ID와 한계 | 무한 재시도 금지. 질문을 기업 집계·확인된 사실 범위로 좁히거나 fallback 증거로 m3 통과 |
| 54 | timeout→request ID 기록→합성 전환→필요 시 AI 연결 해제 순서로 포인터를 이동한다 | browser 45초 deadline, OpenDART 시도당 10초·최초 요청 포함 최대 3회(재시도 최대 2회), request ID는 서버가 반환한 오류에만 표시 | client timeout에 없는 request ID를 만들지 않는다. 단일 정상 요청이 확인될 때까진 전원이 라이브 호출로 돌아가지 않음 |
| A18 | 390px 라이브 첫 화면에서 **합성 샘플로 시작** 클릭→상단 SAMPLE 배너를 가리킴→**실데이터 화면으로 돌아가기** 클릭 | 가로 넘침 없음, 합성 기업·기간 표시, 복귀 후 선택 0개·welcome 화면·검색 가능 | 표준 모바일 컨트롤 캡처를 사용한다. 버튼이 접히면 브라우저 확대 100%와 390px viewport 확인 |

샘플 모드 종료의 노트에는 “라이브 기간 선택값은 진입 전 값으로 복원될 수 있으나 기업 선택과
샘플 결과는 모두 비워진다”라고 적는다. **실데이터 화면으로 돌아가기**를 “샘플 기업을 실데이터로
변환”하거나 “이전 비교를 보존”하는 기능으로 설명하지 않는다.

특히 실습 슬라이드는 “오류 메시지를 AI에게 전달한다”라는 공통 문장으로 끝내지 않는다. 키·개인정보를
제거한 오류 범주와 request ID만 전달하며, timeout·외부 API 장애는 반복 호출보다 합성 경로 전환을
우선한다.

## 최종 PPT 수정 후 검수 게이트

- 본문 42장을 실제 4시간 타임박스로 드레스리허설하고 부록은 질문 때만 연다.
- 모든 본문 슬라이드에 클릭·기대 결과·복구가 있고 m0~m4 하드 체크포인트가 일치한다.
- 8765, 정확한 app ID, 45초 browser timeout, OpenDART 시도당 timeout, request ID 계약을 코드와 대조한다.
- 합성 bootstrap에 실제 기업값·개인정보·외부 네트워크 호출이 없음을 테스트 결과와 대조한다.
- PII 마스킹 표식과 네 AI 출력 차단 reason code가 최신 화면 라벨과 일치한다.
- 키·실제 개인 데이터·차단된 AI 원문이 어느 슬라이드나 노트에도 없다.
- 각 외부 이미지·주장에 `[Sources]`가 있고 같은 화면을 서로 다른 상태의 증거로 재사용하지 않는다.
- 본문 42장과 부록 18장, 총 60장을 각각 전체 크기로 확인해 잘림·겹침·오탈자·작은 글자를 수정한다.
- 최종 PPTX의 빈 placeholder, 잘못된 페이지 표식, 이전 URL·포트·테스트 개수 표현을 검사한다.
