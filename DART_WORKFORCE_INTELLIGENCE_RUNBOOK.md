# DART Workforce Intelligence 실행 런북

## 1. 실행

최신 시각화가 포함된 패키지는 다음 파일이다.

`dist/DARTStructure.exe`

소스 모드로 실행하려면:

```powershell
python server.py
```

기본 주소는 `http://127.0.0.1:8765`이다. 기존에 실행 중인 구버전 `DARTStructure.exe`가 있으면 종료한 뒤 최신 `dist/DARTStructure.exe`를 실행한다.

## 2. 시각화 확인 순서

1. 기업 검색창에서 기업명·종목코드·DART 고유번호로 기업을 선택한다.
2. 기준연도와 사업보고서를 선택하고 `재무구조 비교`를 실행한다.
3. `Strategy Brief` 탭으로 이동한다.
4. 다음 시각 요소를 확인한다.
   - 상단 intro가 `DART / WORKFORCE INTELLIGENCE`와 인력·보상 벤치마크 문맥으로 전환되는지 확인
   - `LAYER 0`: 이익 체력 카드와 이익 → People Signal → 제한사항 흐름
   - `LAYER 1`: 영업이익 세로형 그룹 막대차트
   - `LAYER 2`: 평균 급여 SVG 추이선과 다음연도 전망 밴드
   - `LAYER 3`: Pay Equity 비율 바·근속 차이·공시 누락 상태
   - `LAYER 3+`: 내부 HR 데이터 연결이 필요한 잠금 카드
   - `EVIDENCE`: DART 원문·품질 게이트·에이전트 trace

실제값은 채움/실선으로, 모델 추정은 해칭/점선/`E` 표기로 구분한다. 전망값은 DART에 없는 확정값이 아니라 최근 공시 추세를 화면에서 단순 연장한 값이다.

`Strategy Brief` 활성화 시 참고 HTML의 다크 팔레트가 차트 내부뿐 아니라 상단바·사이드바·검색 결과·AI 입력·기준연도 선택기·지표 툴바·readout까지 적용된다. 다른 탭으로 이동하면 기존 테마로 돌아온다.

## 3. AI 분석 질문

사이드바의 `AI 분석 질문`에 다음과 같은 질문을 입력한다.

- `영업이익이 증가한 기업의 평균 급여도 함께 증가했나?`
- `두 기업의 임원구조와 HR 전략상 확인할 추가 데이터를 비교해줘.`
- `Pay Equity 공시가 없는 기업에서 어떤 검증 절차가 필요한가?`

`AI 분석 실행`은 DART 재무 관측값, 현재 People 요약, Strategy에서 조회한 연도별 People 이력을 `/api/analysis`로 전달한다. Claude MCP gateway가 연결되지 않은 경우에도 `not_configured` 상태와 근거 기반 prompt handoff를 표시한다.

gateway가 오류를 반환하면 provider 결과를 성공 답변으로 표시하지 않고 `error` 상태로 분리한다. 오류가 있어도 DART 관측값·출처·프롬프트 handoff는 유지한다.

## 4. Claude MCP gateway 선택 연결

`.env`에 다음 선택 설정을 추가한다.

```text
CLAUDE_MCP_GATEWAY_URL=
CLAUDE_MCP_GATEWAY_TOKEN=
CLAUDE_MCP_GATEWAY_TIMEOUT_SECONDS=20
```

토큰은 화면·응답·trace에 노출하지 않는다. AI는 DART의 데이터 원천이 아니며, 공시된 집계값을 설명하는 보조 계층이다.

## 5. 품질 기준

- `python -m unittest discover -v`: 14개 테스트 통과(시각 계약·provider 오류·MCP 경계 테스트 포함)
- `ruff check server.py agent_orchestration.py workforce_analytics.py claude_mcp_adapter.py orchestrator.py test_*.py`: 통과
- `node --check static/app.js`: 통과
- PyInstaller 패키지 임시 포트 실행 smoke: health·HTML·AI·차트 자산 확인
- 브라우저 캡처 QA는 브라우저 backend 연결 후 `reports/visual_qa_20260821.md`의 체크리스트를 수행한다.
