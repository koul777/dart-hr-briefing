"""Minimal OpenAI Responses API adapter for DART briefing generation.

The API key is used only in server-side requests.  It may come from a server
environment variable or from a same-origin dashboard request and is never
included in the model input or response payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_OUTPUT_TOKENS = 1800

BRIEFING_INSTRUCTIONS = """당신은 기업 공시 기반 HR Analytics 브리핑 작성자입니다.
반드시 제공된 OpenDART 관측값과 출처만 사용하고, 누락된 수치나 원인을 만들어내지 마세요.
답변은 한국어로 작성하고 다음 순서를 따르세요.
1. 핵심 요약
2. 기업별 인력·보상·생산성 비교
3. HR 관점의 가설과 시사점
4. 추가로 확인할 내부 HR 데이터와 KPI
5. 데이터 한계와 주의사항
사실, 해석, 가설을 명확히 구분하고 투자 추천이나 개인별 평가를 하지 마세요."""


class OpenAIResponsesError(RuntimeError):
    """Raised when the Responses API cannot return a usable answer."""


@dataclass(slots=True)
class OpenAIResponsesProvider:
    api_key: str = ""
    model: str = DEFAULT_OPENAI_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    endpoint: str = OPENAI_RESPONSES_URL
    instructions: str = BRIEFING_INSTRUCTIONS

    provider_id = "openai_responses"

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def provider_label(self) -> str:
        return f"OpenAI Responses API ({self.model})"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> "OpenAIResponsesProvider":
        def positive_int(name: str, default: int, maximum: int) -> int:
            raw = str(environ.get(name, "")).strip()
            if not raw:
                return default
            try:
                value = int(raw)
            except ValueError:
                return default
            return min(maximum, max(1, value))

        return cls(
            api_key=str(environ.get("OPENAI_API_KEY", "")).strip(),
            model=str(environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)).strip()
            or DEFAULT_OPENAI_MODEL,
            timeout_seconds=positive_int(
                "OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 180
            ),
            max_output_tokens=positive_int(
                "OPENAI_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS, 5000
            ),
        )

    def analyze(self, *, prompt: str, context: Mapping[str, Any]) -> str:
        if not self.configured:
            raise OpenAIResponsesError("OPENAI_API_KEY가 설정되지 않았습니다.")

        body = json.dumps(
            {
                "model": self.model,
                "instructions": self.instructions,
                "input": prompt,
                "max_output_tokens": self.max_output_tokens,
                "store": False,
                "text": {"verbosity": "medium"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "dart-workforce-briefing/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                document = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = _http_error_message(exc)
            raise OpenAIResponsesError(f"OpenAI API 요청 실패 ({exc.code}): {message}") from exc
        except URLError as exc:
            raise OpenAIResponsesError(f"OpenAI API에 연결하지 못했습니다: {exc.reason}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAIResponsesError("OpenAI API 응답을 해석하지 못했습니다.") from exc

        if not isinstance(document, Mapping):
            raise OpenAIResponsesError("OpenAI API 응답 형식이 올바르지 않습니다.")
        if document.get("error"):
            error = document["error"]
            message = error.get("message") if isinstance(error, Mapping) else str(error)
            raise OpenAIResponsesError(str(message or "OpenAI API 오류"))

        output_text = _extract_output_text(document)
        if not output_text:
            status = str(document.get("status") or "unknown")
            raise OpenAIResponsesError(f"OpenAI API가 텍스트를 반환하지 않았습니다. 상태: {status}")
        return output_text

    def validate_connection(self) -> None:
        """Verify the supplied key without retaining it or generating content."""

        if not self.configured:
            raise OpenAIResponsesError("OpenAI API Key가 입력되지 않았습니다.")
        request = Request(
            OPENAI_MODELS_URL,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "dart-workforce-briefing/1.0",
            },
        )
        try:
            with urlopen(request, timeout=min(self.timeout_seconds, 30)) as response:
                document = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = _http_error_message(exc)
            raise OpenAIResponsesError(
                f"OpenAI API 연결 확인 실패 ({exc.code}): {message}"
            ) from exc
        except URLError as exc:
            raise OpenAIResponsesError(
                f"OpenAI API에 연결하지 못했습니다: {exc.reason}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAIResponsesError("OpenAI API 연결 응답을 해석하지 못했습니다.") from exc
        if not isinstance(document, Mapping) or not isinstance(document.get("data"), list):
            raise OpenAIResponsesError("OpenAI API 연결 응답 형식이 올바르지 않습니다.")


def _extract_output_text(document: Mapping[str, Any]) -> str:
    direct = document.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    texts: list[str] = []
    output = document.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, Mapping) or block.get("type") != "output_text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n\n".join(texts)


def _http_error_message(exc: HTTPError) -> str:
    try:
        document = json.loads(exc.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return str(exc.reason or "요청 오류")
    if isinstance(document, Mapping):
        error = document.get("error")
        if isinstance(error, Mapping) and error.get("message"):
            return str(error["message"])
    return str(exc.reason or "요청 오류")


__all__ = [
    "BRIEFING_INSTRUCTIONS",
    "DEFAULT_OPENAI_MODEL",
    "OPENAI_MODELS_URL",
    "OpenAIResponsesError",
    "OpenAIResponsesProvider",
]
