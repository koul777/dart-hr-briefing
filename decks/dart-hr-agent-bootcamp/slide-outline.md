# DART로 HR Analytics 에이전트 만들기

## Meta
- **Topic**: OpenDART 공공데이터와 생성형 AI를 연결한 HR Analytics Agent 실습
- **Target Audience**: 코딩 경험이 적은 HR 실무자와 HRD 담당자
- **Tone/Mood**: 차분하고 신뢰감 있는 기업 교육, 실제 제품 화면 중심
- **Slide Count**: 46 slides
- **Aspect Ratio**: 16:9
- **Mode**: html
- **Style**: brand-neutral corporate learning system — white and deep navy backgrounds, electric blue accent, Pretendard typography, four-module progress rail, flat composition, generous whitespace, real application screenshots as primary evidence
- **Primary output**: browser viewer, PDF, and PowerPoint backup

## Visual thesis
공시 문서가 실제 HR 의사결정 지원 도구로 바뀌는 과정을 흰 캔버스, 딥 블루 타이포그래피, 실제 제품 화면으로 보여준다.

## Content plan
완성본 시연으로 기대를 만든 뒤, UI·OpenDART·Analytics/AI·배포의 네 모듈을 따라가며 각 모듈 끝에 통과 기준과 복구 경로를 제시한다.

## System declaration
표지, 네 개의 섹션 구분 슬라이드, 마무리는 딥 네이비 배경을 사용한다. 나머지는 흰 배경을 사용한다. Pretendard 한 서체와 전기 블루 한 강조색만 사용한다. 본문은 좌우 분할, 큰 문장, 실제 화면 확대의 세 가지 레이아웃을 반복한다. 화면 캡처가 있는 슬라이드는 제품 화면을 가장 큰 시각 요소로 두고, 설명 슬라이드는 한 문장과 한 구조에 집중한다.

## Slide composition

### Slide 1 - 표지
- **Type**: Cover
- **Title**: DART로 HR Analytics 에이전트 만들기
- **Subtitle**: OpenDART · 생성형 AI · GitHub · Vercel

### Slide 2 - 출발 질문
- **Type**: Key message
- **Title**: 경쟁사의 인당 생산성을 사업보고서를 직접 뒤지지 않고 확인한다면?
- **Key message**: 오늘 해결할 HR 업무 질문을 한 문장으로 제시한다.

### Slide 3 - 완성본 먼저 보기
- **Type**: Product proof
- **Title**: 기업과 연도만 고르면 비교부터 브리핑까지 이어진다
- **Asset**: assets/demo-poster.png

### Slide 4 - 오늘 가져갈 결과물
- **Type**: Outcomes
- **Title**: 4시간 뒤 네 가지 결과물이 남는다
- **Details**: HR Analytics 화면, AI 브리핑, GitHub 저장소, 공개 URL

### Slide 5 - 4시간 운영 지도
- **Type**: Timeline
- **Title**: 설명 20%, 직접 만들기 80%
- **Details**: m0 13:00, m1 13:45, m2 14:45, m3 15:45, m4 16:40

### Slide 6 - Starter와 복구 전략
- **Type**: Teaching model
- **Title**: 작동하는 뼈대에서 핵심 기능 네 개를 붙인다
- **Key message**: 빈 프로젝트 대신 80% Starter와 checkpoint를 사용한다.

### Slide 7 - 수업 전 사전점검
- **Type**: Screenshot
- **Title**: 시작 조건은 FAIL 0과 비밀값 비노출
- **Asset**: assets/preflight.png

### Slide 8 - 프로젝트 구조
- **Type**: Architecture
- **Title**: 다섯 위치만 알면 전체 흐름을 따라갈 수 있다
- **Details**: static/index.html, static/app.js, server.py, api/index.py, vercel.json

### Slide 9 - 모듈 1 구분
- **Type**: Section divider
- **Title**: MODULE 1 · AI와 기본 화면 만들기
- **Subtitle**: 13:10–13:45 · m1 기업·연도·보고서 선택

### Slide 10 - 바이브 코딩의 역할
- **Type**: Comparison
- **Title**: 사람은 기준을 정하고 AI는 탐색·구현·검증을 돕는다
- **Details**: 사람과 AI의 책임 경계

### Slide 11 - 코드베이스를 읽는 첫 프롬프트
- **Type**: Prompt
- **Title**: 첫 작업은 수정이 아니라 구조 파악이다
- **Details**: 사용자 화면, 데이터 수집, 지표 계산, AI 분석, 배포 파일 위치 요청

### Slide 12 - 좋은 요청의 구조
- **Type**: Framework
- **Title**: 목적·입력·규칙·완료기준을 한 번에 전달한다
- **Details**: 네 칸 프롬프트 캔버스

### Slide 13 - Starter 실행
- **Type**: Screenshot
- **Title**: 실제 데이터 전에 합성 샘플로 화면 계약을 확인한다
- **Asset**: assets/sample-entry.png

### Slide 14 - 첫 구현 프롬프트
- **Type**: Prompt
- **Title**: 기업·연도·보고서 선택 화면을 추가한다
- **Details**: 수정 파일 확인, 기존 스타일 유지, 완료 기준, 실행 검증

### Slide 15 - m1 체크포인트
- **Type**: Checkpoint
- **Title**: 기업 2곳과 기간을 선택하고 비교 버튼을 누를 수 있는가
- **Details**: 13:45 통과 기준과 80% 복구 규칙

### Slide 16 - 모듈 2 구분
- **Type**: Section divider
- **Title**: MODULE 2 · OpenDART 연결
- **Subtitle**: 14:00–14:45 · m2 공개 공시와 근거 연결

### Slide 17 - OpenDART 데이터 흐름
- **Type**: Process
- **Title**: 기업명은 corp_code를 거쳐 보고서 데이터가 된다
- **Details**: 기업 → corp_code → 보고서 → 직원·급여·매출·영업이익

### Slide 18 - 네 개 데이터와 정의
- **Type**: Table
- **Title**: API 호출보다 먼저 지표의 의미를 고정한다
- **Details**: 직원수, 평균급여, 매출액, 영업이익의 단위와 기준

### Slide 19 - API 키 경계
- **Type**: Security
- **Title**: API 키는 코드가 아니라 환경변수에 둔다
- **Details**: .env, .env.example, .gitignore

### Slide 20 - OpenDART 연결 프롬프트
- **Type**: Prompt
- **Title**: 결측을 0으로 바꾸지 않는 수집 로직을 요청한다
- **Details**: 네 지표, 환경변수, 데이터 없음 상태, 변경 파일과 테스트

### Slide 21 - 기업 검색과 고유번호
- **Type**: Screenshot
- **Title**: 화면의 기업 선택이 DART 고유번호로 이어진다
- **Asset**: assets/company-search.png

### Slide 22 - 비교 조건 확인
- **Type**: Screenshot
- **Title**: 기업·연도·보고서 조건이 결과와 함께 남아야 한다
- **Asset**: assets/companies-selected.png

### Slide 23 - m2 체크포인트
- **Type**: Checkpoint
- **Title**: 값뿐 아니라 단위·결측·원문 근거를 설명할 수 있는가
- **Details**: 14:45 통과 기준과 API 장애 대체 경로

### Slide 24 - 모듈 3 구분
- **Type**: Section divider
- **Title**: MODULE 3 · HR 지표와 AI 브리핑
- **Subtitle**: 15:00–15:45 · m3 계산·해석·근거·한계

### Slide 25 - 데이터와 분석의 차이
- **Type**: Formula
- **Title**: 조회한 값에 계산과 해석 규칙을 더해야 Analytics가 된다
- **Details**: 인당 매출, 인당 영업이익, 직원수 증감률, 평균급여 증감률

### Slide 26 - 계산 로직 프롬프트
- **Type**: Prompt
- **Title**: 계산식을 별도 함수로 만들고 결측이면 계산하지 않는다
- **Details**: 분모 0, 단위 통일, 결측값, 테스트 조건

### Slide 27 - 구조화된 AI 입력
- **Type**: Data contract
- **Title**: 원문 전체 대신 검증된 구조화 데이터만 전달한다
- **Details**: JSON 예시와 evidence_ids

### Slide 28 - 챗봇과 에이전트
- **Type**: Comparison diagram
- **Title**: 에이전트는 질문 뒤에서 도구와 검증 절차를 실행한다
- **Details**: 단순 LLM 응답과 DART Analytics Agent 흐름 비교

### Slide 29 - HR Analytics Assistant 규칙
- **Type**: Prompt
- **Title**: 사실·해석·추가 확인을 구분하도록 시스템 규칙을 준다
- **Details**: 인과 단정 금지, 개인 평가·자동 인사조치 금지

### Slide 30 - Strategy Brief
- **Type**: Screenshot
- **Title**: AI 답변보다 먼저 근거가 연결된 결정 브리프를 만든다
- **Asset**: assets/strategy-evidence.png

### Slide 31 - 후속 질문
- **Type**: Screenshot
- **Title**: 현재 기업·연도·지표 맥락을 유지한 채 질문한다
- **Asset**: assets/ai-question.png

### Slide 32 - m3 체크포인트
- **Type**: Checkpoint
- **Title**: 답변의 사실·계산·해석·한계를 구분할 수 있는가
- **Details**: 15:45 통과 기준과 AI 실패 시 검증 대체 응답

### Slide 33 - 모듈 4 구분
- **Type**: Section divider
- **Title**: MODULE 4 · GitHub와 Vercel 배포
- **Subtitle**: 16:00–16:40 · m4 재현 가능한 저장소와 공개 URL

### Slide 34 - GitHub 업로드 전 점검
- **Type**: Security checklist
- **Title**: git add 전에 비밀값과 불필요한 파일부터 막는다
- **Details**: status, check-ignore, staged diff, .env·개인 데이터·로컬 산출물 제외

### Slide 35 - GitHub 저장소 생성
- **Type**: UI walkthrough
- **Title**: github.com/new에서 비어 있는 공개 저장소를 만든다
- **Details**: 이름, 공개 범위, 초기화 옵션, HTTPS 주소

### Slide 36 - GitHub 첫 푸시
- **Type**: Command walkthrough
- **Title**: 로컬 폴더를 main 브랜치로 연결해 처음 푸시한다
- **Details**: init, add, commit, branch, remote, push

### Slide 37 - GitHub 웹 확인
- **Type**: Repository checklist
- **Title**: 브라우저에서 코드·README·커밋을 직접 확인한다

### Slide 38 - Vercel Git 연결
- **Type**: Process
- **Title**: vercel.com/new에서 GitHub 저장소를 가져온다
- **Details**: New Project, GitHub 권한, repository, Import

### Slide 39 - Vercel 프로젝트 설정
- **Type**: Configuration table
- **Title**: 이 저장소는 vercel.json과 api/index.py를 그대로 사용한다
- **Details**: Other, root ./, build/output 기본값

### Slide 40 - Vercel 환경변수
- **Type**: Security walkthrough
- **Title**: 키 값은 Environment Variables에 등록하고 새로 배포한다
- **Details**: OPENDART_API_KEY, 선택 AI 설정, Production/Preview, redeploy

### Slide 41 - Vercel 배포 진행
- **Type**: Status flow
- **Title**: Deploy를 누르고 Building에서 Ready까지 확인한다
- **Details**: Deploy, Building, Ready, Build Logs

### Slide 42 - 운영 검증
- **Type**: Screenshot + checklist
- **Title**: Ready가 아니라 실제 화면과 API 재현으로 배포를 통과시킨다
- **Asset**: assets/production.png

### Slide 43 - 자동 재배포
- **Type**: Process
- **Title**: 이후에는 push가 새 Preview 또는 Production 배포를 만든다
- **Details**: feature branch → Preview, main → Production

### Slide 44 - GitHub·Vercel 복구 지도
- **Type**: Recovery table
- **Title**: 문제가 생기면 증상에 맞는 화면 한 곳만 확인한다
- **Details**: Git 권한·인증, Build Logs, 환경변수, root와 route

### Slide 45 - m4 체크포인트
- **Type**: Checkpoint
- **Title**: GitHub 주소와 실제 동작하는 Vercel URL을 제출할 수 있는가
- **Details**: 16:40 통과 기준과 5분 복구 경로

### Slide 46 - 마무리
- **Type**: Closing
- **Title**: 질문을 근거와 URL이 있는 도구로 바꿨습니다
- **Message**: Dashboard · AI Briefing · GitHub · Web URL
