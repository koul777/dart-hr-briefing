async function checkHealth() {
  const target = document.querySelector("#healthText");
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    target.textContent = payload.api_key_configured
      ? "서버 연결됨 · OpenDART 키 설정됨"
      : "서버 연결됨 · .env에 OpenDART 키를 입력하세요";
  } catch (error) {
    target.textContent = `서버 연결 실패: ${error.message}`;
  }
}

checkHealth();
