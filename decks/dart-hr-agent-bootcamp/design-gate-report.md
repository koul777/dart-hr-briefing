# Design Gate Report — DART API부터 배포까지 직접 만들어가기

**Final scope:** slide-01 … slide-72
**Technical validation:** PASS — 72/72 slides, 0 errors, 0 warnings
**Pass A:** PASS — content/system truth, unresolved critical 0
**Pass B:** PASS — visual/classroom usability, unresolved critical 0
**Verdict:** PROCEED

## What the gate verified

- The deck follows the actual build sequence: Starter copy and baseline commit, OpenDART key issuance, `.env`, Claude Code prompt/approval/diff loop, UI growth, OpenDART and AI API paths, GitHub, and Vercel.
- Browser, Python server, OpenDART, and OpenAI Responses API boundaries are explicit; real keys do not appear in source, logs, responses, or screenshots.
- The Starter's startup text, port, health identity, unimplemented routes, and deployment files agree with the slides and handouts.
- All 14 complete Claude Code prompts are present in both the deck and participant prompt sheet.
- Earlier clipping on the OpenDART mockup, prompt terminal, combined JSON, and Vercel environment-variable panel is resolved.
- Every final HTML slide is SHA256-fingerprinted in both independent reports.

## Accepted nonblocking notes

- Whole-app screenshot microtext should be shown with live zoom when discussing individual values.
- Long shell commands on slides 08 and 64 may soft-wrap; participants should copy them from the handout.
- API code panels are focused excerpts. The preceding prompts require validation, helper functions, and failure handling in the actual implementation.

## Evidence

- `design-gate-pass-a.md`
- `design-gate-pass-b.md`
- `gate-preview/slide-01.png` through `gate-preview/slide-72.png`
- `qa-contact-sheets/sheet-1.png` through `qa-contact-sheets/sheet-8.png`
- `slide-outline.md`, `participant-prompts.md`, `speaker-notes.md`, `GitHub_Vercel_배포_실습지.md`

Any later change to slide HTML requires a new validation/render pass and refreshed fingerprints.
