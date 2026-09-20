# DART HR Agent Workshop Starter

이 폴더는 4시간 실습의 출발점입니다. 완성 프로그램의 설명용 복사본이 아니라, Claude Code
프롬프트를 순서대로 입력하면서 화면·OpenDART API·HR 지표·AI 브리핑을 추가하는 최소 프로젝트입니다.

## 시작

이 폴더를 개인 작업 폴더로 복사한 뒤 복사본에서 실행합니다.

```powershell
Copy-Item -Recurse workshop_starter C:\work\dart-hr-agent
Set-Location C:\work\dart-hr-agent
git init
git add .
git commit -m "Save workshop starter"
Copy-Item .env.example .env
python server.py
```

브라우저에서 `http://127.0.0.1:8765`를 엽니다. 처음에는 제목과 준비 메시지만 표시됩니다.
`/api/health`는 서버와 `.env` 연결 여부만 확인하며 실제 키 값은 반환하지 않습니다.

## 수업 진행

1. 강사가 함께 배포한 `participant-prompts.md`의 프롬프트를 순서대로 사용합니다.
2. 한 프롬프트가 끝날 때마다 `git diff`, 서버, 브라우저를 확인합니다.
3. OpenDART 연결 전까지 `/api/companies`, `/api/financials`, `/api/people`은 `not_implemented`를 반환합니다.
4. 막히면 완성 프로그램인 저장소 루트를 참고하되, Starter 복사본의 현재 작업은 지우지 않습니다.

AI 단계에서는 브라우저의 password 입력값을 요청 헤더로 서버에 한 번 전달하거나, 서버의
`OPENAI_API_KEY`를 사용합니다. 개인 키를 브라우저 저장소, 로그, 응답 또는 Git에 남기지 않습니다.

실제 API 키를 Claude 대화창, 코드, GitHub, 화면 캡처에 넣지 않습니다.
