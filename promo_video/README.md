# DART HR Briefing promotional video

`video-shotcraft`의 Ink Press 10-shot 구조를 DART HR Briefing의 실제 화면과 디자인 토큰으로 재구성한 36.2초 홍보영상입니다.

## Render

```powershell
npm install
npm run typecheck
npm run render
npm run poster
```

- Composition: `DARTPromo`
- Output: 1920×1080, 30fps, 1,085 frames
- Screens: `public/screens/`의 실제 서비스 캡처
- Audio: BGM 없이 검증 가능한 Mixkit SFX만 사용

API 키·개인정보·비공개 데이터는 캡처에 포함하지 않습니다.

합성 계열인 `ui-confirm-tone.mp3`는 정책 게이트가 검증 상태를 알리는 장면에만
사용했습니다. 나머지 효과음은 카메라 이동, 화면 전환, 스캔과 엔딩 공개
동작에 맞춘 물리적·영화적 큐입니다.
