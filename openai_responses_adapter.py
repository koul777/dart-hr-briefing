"""Minimal OpenAI Responses API adapter for DART briefing generation.

The API key is used only in server-side requests.  It may come from a server
environment variable or from a same-origin dashboard request and is never
included in the model input or response payload.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_OUTPUT_TOKENS = 1800
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

BRIEFING_INSTRUCTIONS = """당신은 기업 공시 기반 HR Analytics 브리핑 작성자입니다.
반드시 제공된 OpenDART 관측값과 출처만 사용하고, 누락된 수치나 원인을 만들어내지 마세요.
답변은 한국어로 작성하고 사용자의 최신 질문에 먼저 직접 답하세요.
질문에 필요한 기업·지표만 간결하게 비교하고, 질문하지 않은 일반론이나 경영진 해석을 덧붙이지 마세요.
공시 사실과 수치에는 제공된 evidence_id를 붙이고, 사실·해석·가설을 명확히 구분하세요.
기업명 외에는 실제 또는 가상의 사람 이름·직함·개인 정보를 언급하지 마세요.
투자 추천, 개인별 평가, 채용·승진·보상·해고 권고를 하지 마세요."""


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
        authorization = self._authorization_header()
        model = self._validated_model()

        body = json.dumps(
            {
                "model": model,
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
                "Authorization": authorization,
                "Content-Type": "application/json",
                "User-Agent": "dart-workforce-briefing/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                document = _read_json_response(response)
        except HTTPError as exc:
            message = (
                f"OpenAI 모델 '{model}'을 사용할 수 없습니다. 모델명과 API Key 권한을 확인해 주세요."
                if exc.code == 404
                else _safe_http_error_message(exc.code)
            )
            exc.close()
            raise OpenAIResponsesError(f"OpenAI API 요청 실패 ({exc.code}): {message}") from exc
        except (OSError, TimeoutError, URLError) as exc:
            raise OpenAIResponsesError("OpenAI API에 연결하지 못했습니다.") from exc
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raise OpenAIResponsesError("OpenAI API 응답을 해석하지 못했습니다.") from exc

        if not isinstance(document, Mapping):
            raise OpenAIResponsesError("OpenAI API 응답 형식이 올바르지 않습니다.")
        if document.get("error"):
            raise OpenAIResponsesError("OpenAI API가 요청을 처리하지 못했습니다.")

        output_text = _extract_output_text(document)
        if not output_text:
            raise OpenAIResponsesError("OpenAI API가 텍스트를 반환하지 않았습니다.")
        return output_text

    def validate_connection(self) -> None:
        """Verify the supplied key without retaining it or generating content."""

        if not self.configured:
            raise OpenAIResponsesError("OpenAI API Key가 입력되지 않았습니다.")
        authorization = self._authorization_header()
        model = self._validated_model()
        request = Request(
            OPENAI_MODELS_URL,
            method="GET",
            headers={
                "Authorization": authorization,
                "User-Agent": "dart-workforce-briefing/1.0",
            },
        )
        try:
            with urlopen(request, timeout=min(self.timeout_seconds, 30)) as response:
                document = _read_json_response(response)
        except HTTPError as exc:
            message = _safe_http_error_message(exc.code)
            exc.close()
            raise OpenAIResponsesError(
                f"OpenAI API 연결 확인 실패 ({exc.code}): {message}"
            ) from exc
        except (OSError, TimeoutError, URLError) as exc:
            raise OpenAIResponsesError("OpenAI API에 연결하지 못했습니다.") from exc
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raise OpenAIResponsesError("OpenAI API 연결 응답을 해석하지 못했습니다.") from exc
        if not isinstance(document, Mapping) or not isinstance(document.get("data"), list):
            raise OpenAIResponsesError("OpenAI API 연결 응답 형식이 올바르지 않습니다.")
        available_models = {
            item.get("id")
            for item in document["data"]
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
        if model not in available_models:
            raise OpenAIResponsesError(
                f"OpenAI 모델 '{model}'을 이 API Key로 사용할 수 없습니다. "
                "OPENAI_MODEL 설정과 모델 접근 권한을 확인해 주세요."
            )

    def _authorization_header(self) -> str:
        key = self.api_key.strip()
        if not re.fullmatch(r"sk-[A-Za-z0-9_-]{4,509}", key):
            raise OpenAIResponsesError("OpenAI API Key 형식이 올바르지 않습니다.")
        return f"Bearer {key}"

    def _validated_model(self) -> str:
        model = self.model.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", model):
            raise OpenAIResponsesError("OPENAI_MODEL 형식이 올바르지 않습니다.")
        return model


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


def _read_json_response(response: Any) -> Any:
    """Read one bounded UTF-8 JSON response from an untrusted provider."""

    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise OpenAIResponsesError("OpenAI API 응답이 허용된 크기를 초과했습니다.")
    return json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite_json)


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _safe_http_error_message(status: int) -> str:
    """Map an HTTP status without reflecting an untrusted provider body."""

    if status in {401, 403}:
        return "API Key 인증에 실패했습니다."
    if status == 429:
        return "요청 한도에 도달했습니다."
    if status == 400:
        return "요청 구성 또는 모델 설정을 확인해 주세요."
    if status >= 500:
        return "공급자 서비스가 일시적으로 응답하지 않습니다."
    return "공급자가 요청을 거부했습니다."


__all__ = [
    "BRIEFING_INSTRUCTIONS",
    "DEFAULT_OPENAI_MODEL",
    "MAX_RESPONSE_BYTES",
    "OPENAI_MODELS_URL",
    "OpenAIResponsesError",
    "OpenAIResponsesProvider",
]
