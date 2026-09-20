# GitHub + Vercel 배포 실습지

## 목표

로컬 프로젝트를 GitHub 저장소에 올리고, GitHub와 연결된 Vercel Production URL에서 루트 화면과 `/api/health`를 확인합니다.

## A. GitHub에 첫 푸시

### 1. 업로드 전 확인

```powershell
git status
git check-ignore .env
git ls-files .env
```

Starter 복사 직후 만든 `Save workshop starter` 기준 커밋이 있어야 합니다. 마지막 명령은 출력이 없어야 합니다. `.env`, 실제 API 키, 개인 데이터, 로컬 빌드·보고서·영상 산출물이 커밋 대상에 없어야 합니다.

### 2. 빈 저장소 생성

1. <https://github.com/new>을 엽니다.
2. 저장소 이름을 `dart-hr-agent`로 입력합니다.
3. 공개 범위를 선택합니다.
4. 로컬 프로젝트에 README와 `.gitignore`가 있으므로 GitHub의 README, `.gitignore`, License 초기화 옵션은 선택하지 않습니다.
5. **Create repository**를 누르고 HTTPS 주소를 복사합니다.

### 3. 로컬 폴더 연결

```powershell
git add .
git diff --cached --name-only
git diff --cached
git commit -m "Build DART HR agent"
git branch -M main
git remote add origin https://github.com/<ID>/dart-hr-agent.git
git remote -v
git push -u origin main
```

이미 `origin`이 있다면 `git remote add origin`을 다시 실행하지 않습니다. `git remote -v`로 주소를 확인하고 필요한 경우 `git remote set-url origin <새 주소>`를 사용합니다.

### 4. 웹에서 확인

- README.md, `api/index.py`, `vercel.json`이 보인다.
- 최신 커밋 메시지가 보인다.
- `.env`와 실제 API 키는 보이지 않는다.

공식 참고: [GitHub — 기존 로컬 코드를 저장소에 추가](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)

## B. Vercel에 배포

### 1. GitHub 저장소 가져오기

1. <https://vercel.com/new>을 엽니다.
2. GitHub로 로그인하거나 **Continue with GitHub**를 선택합니다.
3. `dart-hr-agent` 저장소를 찾고 **Import**를 누릅니다.
4. 저장소가 없으면 GitHub App의 저장소 접근 권한을 확인합니다.

### 2. 프로젝트 설정

| 항목 | 값 |
|---|---|
| Project Name | `dart-hr-agent` |
| Framework Preset | `Other` |
| Root Directory | `./` |
| Build / Output | Override하지 않음 |

이 프로젝트는 루트의 `vercel.json`과 `api/index.py`를 사용합니다.

### 3. 환경변수

| 이름 | 설정 |
|---|---|
| `OPENDART_API_KEY` | 실제 공시 조회에 필요, Production, Sensitive ON |
| `OPENAI_MODEL` | 사용할 모델 이름, 선택, Sensitive OFF |
| 수강생 개인 AI 키 | Vercel 환경변수가 아니라 브라우저 화면에 직접 입력, 서버 저장 안 함 |

키 값은 GitHub, 채팅, 슬라이드, 화면 캡처에 넣지 않습니다. 환경변수의 값을 바꾸면 이전 배포에는 적용되지 않으므로 새 배포나 **Redeploy**가 필요합니다.

### 4. 배포와 검증

1. **Deploy**를 누릅니다.
2. **Building → Ready**를 확인합니다.
3. 실패하면 Deployment의 **Build Logs**에서 첫 번째 오류부터 읽습니다.
4. 다음 주소를 같은 배포에서 확인합니다.

```text
BASE    https://<project>.vercel.app
ROOT    /
HEALTH  /api/health
```

5. `/api/health`에서 `api_key_configured: true`와 `app.id`를 확인합니다.
6. 루트 화면에서 기업을 검색하고, 같은 연도·보고서로 두 기업 비교를 한 번 실행합니다.
7. AI까지 구현했다면 `/api/ai/briefing` 요청이 성공하고 응답·로그·URL에 키가 없는지 확인합니다.

공식 참고: [Vercel — Git 저장소 배포](https://vercel.com/docs/git), [Vercel — 환경변수 관리](https://vercel.com/docs/environment-variables/managing-environment-variables)

## C. 이후 업데이트

```powershell
git add .
git commit -m "Update DART HR agent"
git push
```

- 기능 브랜치 push: Preview 배포
- `main` push: Production 배포
- 매번 화면과 `/api/health`를 다시 확인

## D. 5분 복구표

| 증상 | 먼저 볼 곳 | 복구 |
|---|---|---|
| Vercel에서 저장소가 안 보임 | GitHub App 권한 | 해당 저장소 접근 허용 |
| push 인증 실패 | `git remote -v`, 로그인 | 주소 확인 후 브라우저 인증 |
| Build Failed | Build Logs 첫 오류 | 파일·의존성·Python 버전 수정 |
| 키 변경 미반영 | 환경 대상, 최근 배포 | Production 선택 후 Redeploy |
| 404 또는 API 오류 | `vercel.json`, Root Directory | 루트 `./` 확인 후 새 배포 |
