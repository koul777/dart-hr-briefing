# Design system

## Visual thesis
공시 문서가 실제 HR 의사결정 지원 도구로 바뀌는 과정을 차분한 기업 교육 미감과 실제 제품 화면으로 보여준다.

## Tokens
- Background: `#FFFFFF`
- Dark background and code surface: `#071526`
- Accent: `#123FC2`
- Dark-surface accent tint: `#AFC4FF`
- Surface: `#EAF0FB`
- Primary text: `#0B1736`
- Muted text: `#596579`
- Line: `#C7D2E5`
- Typeface: Pretendard, Noto Sans KR, Malgun Gothic

## Layout system
- Cover, section dividers, and closing outcome: dark background, oversized type, minimal metadata.
- Content: white background with a fixed module rail and strong left alignment.
- Screenshots: one large crop with a short explanatory caption.
- Prompts: one dark code surface, one small checklist, no decorative chrome.
- Checkpoints: oversized module marker with three pass conditions and one recovery instruction.

## Accessibility
- Body copy is at least 15pt.
- Korean wrapping uses `word-break: keep-all` and `text-wrap: balance`.
- Accent is never the only signal; labels and hierarchy also carry meaning.
- Screenshots use captions that state what the learner must verify.
