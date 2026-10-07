"""Cliente HTTP de Gemini (spec 007, RF-3/RF-4).

La clave viaja solo en la cabecera ``x-goog-api-key`` (nunca en la URL ni
en los mensajes de error, RNF-3). Reintentos ante timeout/5xx sin
backoff; 429 ⇒ ``GeminiQuotaExceeded`` sin reintento.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.config import settings


class GeminiUnavailable(RuntimeError):
    """El servicio no respondió de forma utilizable (RF-4)."""


class GeminiQuotaExceeded(RuntimeError):
    """Google devolvió 429: cuota del tier gratuita agotada (RF-3)."""


@dataclass(frozen=True)
class GeminiReply:
    """Respuesta cruda del modelo: texto, tokens y metadatos."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str
    request_id: str
    latency_ms: int


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiUnavailable("gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise GeminiUnavailable("gemini returned empty text")
    return text


class GeminiClient:
    """``generateContent`` con timeout, reintentos y cuota (brief §19)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        key = (
            settings.gemini_api_key if api_key is None else api_key
        ).strip()
        name = (
            settings.gemini_model if model is None else model
        ).strip()
        if not key:
            raise ValueError("gemini_api_key is required")
        if not name:
            raise ValueError("gemini_model is required")
        self.api_key = key
        self.model = name
        raw_base = (
            base_url
            if base_url is not None
            else settings.gemini_base_url
        )
        self.base_url = raw_base.rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.gemini_timeout_seconds
        )
        retries = (
            max_retries
            if max_retries is not None
            else settings.gemini_max_retries
        )
        self.max_retries = max(0, retries)

    def generate(self, prompt: str, *, request_id: str) -> GeminiReply:
        """Llama al modelo y devuelve texto + uso; nunca filtra la clave."""
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if not request_id:
            raise ValueError("request_id is required")

        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        started = time.perf_counter()
        last_error: Exception | None = None

        for _attempt in range(self.max_retries + 1):
            try:
                response = httpx.request(
                    "POST",
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                continue
            except httpx.TransportError as exc:
                last_error = exc
                continue

            status = response.status_code
            if status == 429:
                raise GeminiQuotaExceeded("gemini quota exceeded (HTTP 429)")
            if status >= 500:
                last_error = GeminiUnavailable(f"gemini HTTP {status}")
                continue
            if not 200 <= status < 300:
                raise GeminiUnavailable(f"gemini HTTP {status}")

            try:
                data = response.json()
            except ValueError as exc:
                raise GeminiUnavailable(
                    "gemini answer is not JSON"
                ) from exc
            if not isinstance(data, dict):
                raise GeminiUnavailable("gemini answer is not an object")

            text = _extract_text(data)
            usage = data.get("usageMetadata") or {}
            latency_ms = int((time.perf_counter() - started) * 1000)
            return GeminiReply(
                text=text,
                input_tokens=int(usage.get("promptTokenCount") or 0),
                output_tokens=int(usage.get("candidatesTokenCount") or 0),
                model=self.model,
                request_id=request_id,
                latency_ms=latency_ms,
            )

        detail = type(last_error).__name__ if last_error else "no response"
        raise GeminiUnavailable(f"gemini unavailable: {detail}") from last_error
