# Production notes

## Requirements to execution

| Requirement | Execution |
| --- | --- |
| HR 실무자와 강의 참가자에게 제품 가치를 40초 이내 전달 | Ink Press 10-shot, 1,085-frame 구조 유지 |
| 실제 제품을 보여 줄 것 | `public/screens/`의 실제 DART HR Briefing 캡처만 사용 |
| 기업 선택과 같은 기준 비교 | S3 기업 선택 패널과 Overview, S4 Compare 원값 표 |
| Strategy Brief와 근거 추적 | S6 Strategy Brief에서 Evidence/Orchestration으로 좌→우 wipe |
| AI 질문과 안전장치 | S8 실제 AI 질문 패널과 개인정보·근거·인과·개인판단 4개 게이트 |
| 공개 서비스로 연결 | S10 워드마크, 핵심 문장, `dart-ruby-zeta.vercel.app` 1초 이상 hold |
| 민감정보를 노출하지 않을 것 | 공개 OpenDART 기업 집계만 사용, API 키는 `sk-...` 마스킹 |
| 배포 용량을 키우지 않을 것 | `promo_video/`, `docs/`, `node_modules/`를 Vercel 함수 번들에서 제외 |

## Template adaptation

- Mode: direct Ink Press template adaptation.
- Preserved: 10 shots, four title cards, real-page camera movement, three full-screen flash transitions, readable captions, SFX-only design, feature-family outro.
- Replaced: product pages, Korean copy, brand mark, palette and CTA.
- Gallery variant: none named beyond the installed Ink Press template.
- Intentional exceptions: none.

## Shot and feature map

| Frames | Shot | Product evidence |
| --- | --- | --- |
| 0–219 | Brand → real home | public app home and four-step build flow |
| 220–274 | Title 1 | same-basis comparison benefit |
| 275–464 | Company selection → Overview | 2-company selection, current report, KPI overview |
| 465–564 | Compare detail | side-by-side financial values and missing-data state |
| 565–619 | Title 2 | facts, limits and next questions |
| 620–724 | Strategy → evidence | Decision Brief, source links, quality gate and trace |
| 725–774 | Title 3 | AI question with evidence |
| 775–884 | AI and policy gate | question panel and four output checks |
| 885–939 | Title 4 | verifiable sources and better HR questions |
| 940–1084 | Feature family → CTA | four product states, wordmark and public URL |

## Audio policy

- No BGM.
- Cinematic sweeps and impacts follow camera moves and scene changes.
- The only synthetic UI cue, `ui-confirm-tone.mp3`, represents the policy gate explicitly reporting a successful system check.
- Every audio sequence has an explicit frame window. Source URLs are recorded in `AUDIO_LICENSES.md`.
