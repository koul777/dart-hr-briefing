# DART Workforce Intelligence

공시 기반 인력·보상·임원구조 벤치마크

## 1. 문서 목적

이 문서는 `DART Workforce Intelligence` 개발의 기준 문서다. 이후 구현은 이 문서의 범위, 데이터 원칙, API 계약, 완료 조건을 따른다.

## 2. 제품 정의

OpenDART API만 사용해 기업의 공시된 인력·보상·임원 데이터를 수집하고, 기업 간 비교와 연도별 추이를 제공한다.

이 제품은 내부 HRIS가 없는 상태에서도 사용할 수 있는 공시 기반 Workforce Analytics 도구다. 개인의 채용·승진·해고·성과를 판단하지 않고, 기업 수준의 구조와 변화만 분석한다.

## 3. 제품명

- 제품명: `DART Workforce Intelligence`
- 부제: `공시 기반 인력·보상·임원구조 벤치마크`
- 데이터 출처: OpenDART
- 기본 비교 단위: 기업 × 사업연도 × 보고서

## 4. 데이터 범위

### 4.1 직원 현황

API: `empSttus.json`

- 총 직원 수
- 정규직 수
- 계약직 수
- 정규직·계약직 단시간 근로자 수
- 평균 근속연수
- 연간 급여 총액
- 1인 평균 급여
- 사업부문·성별 기준 원자료 행

공식 개발가이드: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019011>

### 4.2 임원 현황

API: `exctvSttus.json`

- 전체 임원 수
- 등기·미등기 임원 수
- 사내이사·사외이사 수
- 대표이사 수
- 상근·비상근 임원 수
- 여성 임원 수
- 임원 재직기간
- 임기 만료일
- 최대주주 관련 임원 수

개인 이름·생년월·주요 경력은 집계 목적 외에 기본 화면으로 전달하지 않는다.

공식 개발가이드: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019010>

### 4.3 임원 보수

API: `unrstExctvMendngSttus.json`

- 미등기임원 수
- 미등기임원 연간 급여 총액
- 미등기임원 1인 평균 급여

공식 개발가이드: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DE002&apiId=AE00028>

### 4.4 선택적 재무 결합

재무 데이터도 OpenDART API에서 조회하는 경우에만 결합한다.

- 매출/인
- 영업이익/인
- 인건비/매출
- 직원 수와 수익성의 동시 추이

재무 지표는 HR 원인으로 단정하지 않고, 인력 전략 가설을 만드는 참고지표로만 표시한다.

## 5. 지원 보고서

- 사업보고서: `11011`
- 반기보고서: `11012`
- 1분기보고서: `11013`
- 3분기보고서: `11014`

사업보고서(`11011`)를 연간 비교의 기본값으로 사용한다. 분기·반기 데이터는 별도 보고서 기준임을 화면에 표시한다.

## 6. 핵심 분석 지표

```text
정규직 비중 = 정규직 수 / 총 직원 수 × 100
계약직 비중 = 계약직 수 / 총 직원 수 × 100
직원 수 증가율 = (현재 직원 수 - 전년 직원 수) / 전년 직원 수 × 100
평균 급여 증가율 = (현재 평균 급여 - 전년 평균 급여) / 전년 평균 급여 × 100
사외이사 비율 = 사외이사 수 / 전체 등기임원 수 × 100
상근 임원 비율 = 상근 임원 수 / 전체 임원 수 × 100
여성 임원 비율 = 여성 임원 수 / 전체 임원 수 × 100
매출/인 = 매출 / 총 직원 수
영업이익/인 = 영업이익 / 총 직원 수
인건비/매출 = 연간 급여 총액 / 매출 × 100
```

분모가 없거나 0인 지표는 0으로 대체하지 않고 `null`과 데이터 품질 사유를 반환한다.

## 7. 표준 응답 모델

모든 인력·임원 응답은 기업, 기간, 지표, 출처, 품질 정보를 포함한다.

```json
{
  "corp_code": "00126380",
  "corp_name": "회사명",
  "year": "2024",
  "report_code": "11011",
  "metrics": {},
  "source": {
    "receipt_no": "접수번호",
    "source_url": "https://dart.fss.or.kr/..."
  },
  "quality": {
    "status": "complete",
    "missing_fields": [],
    "warnings": []
  }
}
```

품질 상태는 다음을 사용한다.

- `complete`: 핵심 지표가 모두 계산됨
- `partial`: 일부 데이터만 존재함
- `no_data`: 정상 응답이나 데이터가 없음
- `error`: API 요청 또는 응답 처리 실패

## 8. 백엔드 API 계획

기존 API를 유지하면서 다음 기능을 확장한다.

- `GET /api/people`: 특정 연도 직원·보상 요약
- `GET /api/people/history`: 직원·보상 연도별 추이
- `GET /api/executives`: 특정 연도 임원 구조 요약
- `GET /api/executives/history`: 임원 구조 연도별 추이
- `GET /api/workforce/orchestration`: DART 원자료를 에이전트 DAG로 실행한 통합 분석
- `GET /api/workforce/benchmark`: 여러 기업의 통합 비교 응답

각 API는 접수번호와 원문 URL을 반환하고, 누락·조회 실패·집계 방식을 명시한다.

## 9. 화면 계획

### Workforce Overview

- 총 직원 수
- 정규직·계약직 비중
- 평균 근속
- 1인 평균 급여
- 기업 간 비교표

### Compensation

- 평균 급여
- 연간 급여 총액
- 미등기임원 평균 급여
- 전년 대비 변화

### Executive Structure

- 등기·미등기
- 사내·사외이사
- 상근·비상근
- 대표이사 수
- 여성 임원 비율
- 최대주주 관련 임원 비율

### Tenure & Succession

- 평균 임원 재직기간
- 임기 만료 예정 임원 수
- 대표이사·사외이사 임기 현황
- 장기 재직·신규 선임 구성

### Peer Benchmark

- 동일 연도·동일 보고서 기준 기업 비교
- 순위와 상대 지수
- 원문 근거 확인

### Data Quality

- 기업별 조회 상태
- 누락 필드
- 집계 방식
- 비교 제한 사유

## 10. 데이터 처리 원칙

1. API 원문 수치와 계산 지표를 분리한다.
2. 공란·`-`·조회 실패를 0으로 바꾸지 않는다.
3. 직원 사업부문 행과 성별 합계 행의 중복 집계를 방지한다.
4. 임원 개인 식별 정보는 기본 분석 결과에서 제거한다.
5. 모든 수치는 기업명·연도·보고서·접수번호를 따라야 한다.
6. 평균·비율 지표는 분모와 계산식을 함께 기록한다.
7. 인과관계, 성과, 조직문화, 이직 가능성을 단정하지 않는다.
8. Claude나 다른 외부 AI는 데이터 원천으로 사용하지 않는다.

## 12. 에이전트 오케스트레이션

### 12.1 목표

People Analytics 분석을 하나의 긴 함수나 단일 프롬프트로 처리하지 않고, 책임이 분리된 에이전트 DAG로 실행한다. 각 에이전트는 입력·출력·상태·오류를 기록하며, 앞 단계가 실패하면 근거 없이 다음 단계가 진행되지 않는다.

### 12.2 실행 그래프

```text
request + DART raw bundle
        |
        v
source_snapshot
   |       |        |
   v       v        v
employee  executive compensation
agent     agent     agent
   \       |        /
    \      |       /
       quality agent
             |
             v
       benchmark agent
             |
             v
     privacy/report guard
             |
             +--> optional Claude MCP interpretation
             |
             v
       structured response
```

### 12.3 에이전트 책임

| 에이전트 | 책임 | 외부 호출 |
|---|---|---|
| `source_snapshot` | 기업·연도·보고서·접수번호와 원자료 존재 여부 확인 | 없음 |
| `employee_normalizer` | 직원·정규직·계약직·근속·급여 정규화 | 없음 |
| `executive_normalizer` | 임원·이사회·성별·재직기간·임기 지표 정규화 | 없음 |
| `compensation_normalizer` | 미등기임원 보수 정규화 | 없음 |
| `quality_auditor` | 누락·중복·분모·API 오류·집계 경고 통합 | 없음 |
| `benchmark_calculator` | 기업별 비율·증감률·상대 비교 계산 | 없음 |
| `privacy_guard` | 이름·생년월·경력 등 개인 원자료가 결과에 남지 않았는지 검증 | 없음 |
| `strategy_interpreter` | 검증된 사실을 전략 가설·KPI·제한사항으로 해석 | 선택적 Claude MCP |
| `response_guard` | 응답 스키마와 근거·가설 분리 최종 검증 | 없음 |

### 12.4 오케스트레이션 원칙

1. 직원·임원·보상 정규화 에이전트는 서로 독립적으로 실행할 수 있다.
2. 품질검사 이전에는 전략 해석을 실행하지 않는다.
3. `no_data`, `partial`, `error`를 구분하고 실패를 0으로 대체하지 않는다.
4. Claude MCP는 DART 데이터를 조회하지 않고, 검증된 집계 컨텍스트만 해석한다.
5. Claude MCP가 없거나 실패해도 사실·지표·품질 결과는 반환한다.
6. 개인 임원 원자료는 `privacy_guard`를 통과한 뒤에만 외부 분석 경계로 전달한다.
7. 각 단계의 실행 상태와 오류는 `trace`에 남긴다.

### 12.5 표준 오케스트레이션 응답

```json
{
  "schema_version": 1,
  "status": "completed",
  "facts": {},
  "benchmarks": {},
  "quality": {},
  "provider": {
    "status": "not_configured",
    "result": null
  },
  "trace": [
    {"agent": "employee_normalizer", "status": "completed"},
    {"agent": "privacy_guard", "status": "completed"}
  ]
}
```

`provider.status`는 `not_configured`, `completed`, `error`, `skipped` 중 하나이며, `provider.result`가 없어도 `facts`와 `benchmarks`는 유효해야 한다.

## 13. 개발 단계와 완료 조건

### Phase 1 — 문서·브랜드·범위 고정

완료 조건:

- 제품명과 부제가 화면에 적용됨
- 이 문서가 저장소에 존재함
- DART API만 데이터 원천으로 명시됨

### Phase 2 — 데이터 정규화

완료 조건:

- 직원·임원·보상 원자료를 공통 구조로 변환
- 임원 재직기간을 개월 수로 변환
- 등기·사외·상근·여성 등 분류 규칙 테스트
- 데이터 품질 상태 반환

### Phase 3 — 백엔드 API

완료 조건:

- 단일 연도 및 연도별 이력 API 제공
- 기업 간 벤치마크 응답 제공
- 원문 URL과 접수번호 제공
- API 실패와 데이터 없음 구분

### Phase 4 — 프론트엔드

완료 조건:

- Workforce, Compensation, Executive, Tenure 화면 제공
- 기업 간 비교와 연도별 추이 제공
- 개인 임원 원자료 미노출
- CSV 내보내기 제공

### Phase 5 — 검증

완료 조건:

- 샘플 응답 기반 단위 테스트 통과
- API 키 미설정 시 안전한 오류 표시
- 누락·중복·분모 0 테스트 통과
- 로컬 서버·패키지·정적 자산 smoke 통과; 브라우저 캡처 회귀는 backend 연결 후 수행

## 14. 현재 진행 상태

- [x] 제품명 확정: `DART Workforce Intelligence`
- [x] 부제 확정: `공시 기반 인력·보상·임원구조 벤치마크`
- [x] 브라우저 제목·브랜드 적용
- [x] 개발 기준 문서 작성
- [x] 직원·임원·보상 정규화
- [x] 에이전트 오케스트레이션 DAG 및 테스트
- [x] 백엔드 API 확장 (`/api/people`·history, `/api/executives`·history, `/api/workforce/orchestration`)
- [x] People Analytics 화면 확장 (People·Executives·Strategy Brief 및 추이·품질 화면)
- [x] 테스트 및 검증 (단위·구문·실제 OpenDART·패키지 smoke)

### 구현 기록

- `workforce_analytics.py`: 직원·임원·미등기임원 보수 정규화 및 지표 계산
- `test_workforce_analytics.py`: 재직기간·임원 구조·직원 집계 테스트
- `server.py`: 임원 요약 API와 임원 지표 메타데이터 추가
- `server.py`: 일반 People 응답에서 개인별 임원 원자료 제거
- `agent_orchestration.py`: 병렬 정규화·품질·벤치마크·개인정보·응답 검증 DAG
- `test_agent_orchestration.py`: provider 유무와 개인정보 차단을 포함한 DAG 테스트
- `static/index.html`: 제품명 및 Executives 탭 추가
- `static/app.js`: 임원 구조 비교 화면과 DART API 호출 연결

## 15. 참고 대시보드 통합 원칙

참고 파일: `C:\Users\dd\Downloads\기업 비교 대시보드_v1.html`

참고 화면의 정보 구조를 `Strategy Brief` 화면으로 통합한다.

### 통합할 정보 구조

1. `이익 체력`: 영업이익·영업이익률·사업부문 또는 기업 간 차이
2. `이익 → 보상 연동`: 영업이익, 인당 수익성, 평균 급여를 하나의 흐름으로 표시
3. `영업이익 추이`: 실제 DART 연도별 수치와 추정 구간을 구분
4. `평균 급여 추이`: 실제 공시값과 모델 추정값을 시각적으로 분리
5. `Pay Equity`: DART 직원 현황에서 성별 급여·근속이 모두 있을 때만 비교
6. `내부 제도 진단`: 평가등급·평가-보상 연동·내부 Pay Equity·보상 인식은 데이터 없음 placeholder로 표시
7. `근거와 주의사항`: 접수번호·원문 URL·기준연도·보고서 코드·추정 여부·비교 제한사항

### 구현 원칙

- 참고 HTML의 삼성전자·SK하이닉스 수치를 제품에 하드코딩하지 않는다.
- 현재 선택 기업과 선택 연도의 DART 응답으로 모든 숫자를 계산한다.
- 관측값과 추정값을 색·라벨·범례로 분리한다.
- 2026 전망처럼 DART에 없는 미래 수치는 `모델 추정`으로만 표시한다.
- Pay Equity 데이터가 없으면 빈 그래프를 만들지 않고 `공시되지 않음`을 표시한다.
- 참고 HTML의 “이익이 급여를 규정한다”는 문구는 인과관계가 아니라 `가설`로 표시한다.
- 내부 HR 데이터가 필요한 항목은 잠금 상태의 placeholder로 남긴다.

### Strategy Brief 완료 조건

- 선택 기업별 이익 체력 카드가 표시됨
- 이익→보상 연동 흐름이 실제 DART 값으로 계산됨
- 연도별 영업이익·평균 급여 추이가 표시됨
- 실제값과 추정값이 구분됨
- 성별 급여·근속 데이터의 공시 여부가 기업별로 표시됨
- 내부 HR 데이터 필요 영역이 명시됨
- 출처와 한계가 화면 하단에 표시됨

핵심 구현은 완료되었으며, 후속 작업은 DART 기반 시각화 고도화·브라우저 캡처 회귀 검증·선택적 AI 해석 계층 연결이다.

## 16. 참고 대시보드 반영 진행 기록

- [x] `Strategy Brief` 탭 추가
- [x] 선택 기업의 영업이익·영업이익률·인당 영업이익·평균 급여 카드 연결
- [x] 영업이익 및 평균 급여의 실제값/다음연도 모델 추정 구분
- [x] 성별 급여·근속 공시가 있을 때만 Pay Equity 비교
- [x] 내부 HR 데이터가 필요한 평가·보상 진단 영역을 잠금 상태로 표시
- [x] DART 원문 링크와 Workforce 에이전트 trace·quality·provider 상태 표시
- [x] 참조 HTML의 삼성전자·SK하이닉스 수치 하드코딩 없이 선택 기업에 동적 적용
- [x] 실제 OpenDART 단일 기업 재무·People·오케스트레이션 연동 검증
- [x] 참고 HTML의 다크 패널·기업별 블루/레드 강조색·실제/추정 범례를 Strategy 화면에 적용
- [x] Strategy 활성화 시 상단바·사이드바·검색·AI 질문·지표 툴바까지 참고 HTML 계열 다크 테마로 전환
- [x] 영업이익을 세로형 그룹 막대차트, 평균 급여를 SVG 추이선·전망 밴드로 시각화
- [x] `AI 분석 질문` 입력·실행 UI를 `/api/analysis` 및 Claude MCP provider 상태와 연결
- [x] 수정된 정적 자산을 포함한 배포용 `dist/DARTStructure.exe` 재빌드 및 임시 포트 실행 검증
- [x] 최신 실행 파일 경로를 `dist/DARTStructure.exe`로 고정하고 소스 서버와 동일한 정적 자산 포함 확인
- [x] 실행·시각화·AI 질문·품질 검증 순서를 `DART_WORKFORCE_INTELLIGENCE_RUNBOOK.md`에 문서화
- [x] 시각화 전용 검증 결과를 `reports/visual_qa_20260821.md`에 기록
- [x] 차트·AI·다크 테마 정적 자산을 확인하는 `test_frontend_contract.py` 추가

성과 개선 후속 검토:

1. DART 호출량을 줄이기 위해 원자료/정규화 결과의 기간·기업 단위 캐시를 검토한다. 개인 임원 원자료는 캐시 대상에서 제외하거나 짧은 보존 정책을 적용한다.
2. Strategy Brief에서 사용하는 전망식을 선형 연장 하나로 고정하지 않고, 표본 수·결측률·변동성에 따라 신뢰도와 전망 구간을 함께 제시한다.
3. 기업·연도·보고서 조합을 기준으로 화면 요청을 캐시하고, API 호출 실패 시 마지막 성공 데이터와 최신성 상태를 구분한다.
4. Pay Equity는 성별 외에도 직급·직무·고용형태 층화가 가능한 공시 필드가 있는지 확인한 후 오해를 줄이는 최소표본 규칙을 추가한다.
5. Strategy 비동기 요청은 기업·연도·보고서 조합 토큰을 검증해 빠른 재비교나 탭 전환에서 오래된 응답을 폐기한다.
6. People·임원·추이 API 실패는 `미공시`와 구분해 오류 상태와 메시지를 표시한다.
7. 음수 영업이익 전망은 0 기준선 양방향 막대로 표시하고, 표본이 부족하거나 음수가 되는 평균 급여 전망은 생성하지 않는다.
8. 재무·직원·미등기 보상 API 응답은 5분 메모리 캐시로 재사용하고 개인 임원 현황 원자료는 캐시하지 않는다.
9. AI 분석은 DART 관측값·원문 링크·결측 상태를 컨텍스트로 전달하고, provider 미연결 시에도 근거 기반 프롬프트를 제공한다. AI 결과는 차트의 실제값·추정값·한계 표시를 대체하지 않는다.
10. 시각화 품질을 핵심 KPI로 삼아 차트 렌더링(실제값/추정값/전망 구간), 데이터 부족 상태, 모바일 축소 레이아웃을 브라우저 캡처로 회귀 검증한다.

## 17. AI 해석 계층 운영 방식

AI는 DART 원자료를 대신 수집하거나 숫자를 생성하는 계층이 아니다. OpenDART가 제공한 관측값·연도·보고서·원문 접수번호·결측/오류 상태를 컨텍스트로 받아 HR 질문을 해석하고, 근거와 한계를 포함한 설명을 만드는 보조 계층이다.

- 사용자는 사이드바의 `AI 분석 질문`에 질문을 입력한다.
- `/api/analysis`가 선택 기업·연도·보고서·People Analytics 요약을 묶어 구조화된 분석 컨텍스트를 만든다.
- Claude MCP gateway가 설정된 경우 provider 결과를 화면에 표시한다.
- gateway가 없으면 `not_configured` 상태와 함께 동일한 근거 기반 프롬프트를 표시한다.
- gateway가 오류를 반환하면 성공 답변으로 오인하지 않고 `error` 상태와 근거 기반 프롬프트를 유지한다.
- AI는 인과관계, 개인별 성과, 성별 격차의 원인을 단정하지 않으며 투자 매수·매도 추천을 하지 않는다.

연결 설정은 `.env.example`의 `CLAUDE_MCP_GATEWAY_URL`, `CLAUDE_MCP_GATEWAY_TOKEN`, `CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS`를 사용한다. 토큰은 공개 응답이나 trace에 포함하지 않는다.
