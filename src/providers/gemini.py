"""Google Gemini adapter (text in, structured JSON out)."""

from __future__ import annotations

from typing import Any, Protocol

from config import AIProviderName, Settings
from models.document import StructuredExtractionResult
from providers.base import (
    AIProvider,
    ProviderAuthError,
    ProviderError,
    StructuringContext,
)
from providers.errors import classify_http_like_error, parse_retry_after, redact_secrets
from providers.structuring import structure_with_json_generator


class GeminiGenerateFn(Protocol):
    def __call__(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        response_schema: dict[str, Any],
    ) -> str: ...


def default_gemini_generate(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    user_content: str,
    response_schema: dict[str, Any],
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        from providers.base import ProviderTransientError

        raise ProviderTransientError(
            "google-genai package is not installed. pip install google-genai"
        ) from exc

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_json_schema=response_schema,
                temperature=0.1,
            ),
        )
    except Exception as exc:
        raise classify_http_like_error(exc, api_key=api_key) from exc

    text = getattr(response, "text", None) or ""
    if not text.strip():
        from providers.base import ProviderTransientError

        raise ProviderTransientError("Gemini returned an empty response.")
    return text


class GeminiProvider(AIProvider):
    provider_id = AIProviderName.GEMINI

    def __init__(
        self,
        settings: Settings,
        *,
        generate_fn: GeminiGenerateFn | None = None,
    ) -> None:
        if not settings.provider_configured(AIProviderName.GEMINI):
            raise ProviderAuthError("Gemini is not configured (set GEMINI_API_KEY).")
        self._api_key = settings.gemini_api_key.get_secret_value().strip()
        self._model = settings.gemini_model
        if generate_fn is not None:
            self._generate = generate_fn
        else:
            api_key = self._api_key

            def _bound_generate(
                *,
                model: str,
                system_instruction: str,
                user_content: str,
                response_schema: dict[str, Any],
            ) -> str:
                return default_gemini_generate(
                    api_key=api_key,
                    model=model,
                    system_instruction=system_instruction,
                    user_content=user_content,
                    response_schema=response_schema,
                )

            self._generate = _bound_generate

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        def generate_json(system: str, user: str, schema: dict[str, Any]) -> str:
            try:
                return self._generate(
                    model=self._model,
                    system_instruction=system,
                    user_content=user,
                    response_schema=schema,
                )
            except ProviderError:
                raise
            except Exception as exc:
                headers = getattr(exc, "headers", None)
                hdrs = dict(headers) if isinstance(headers, dict) else None
                retry_after = parse_retry_after(hdrs)
                classified = classify_http_like_error(exc, api_key=self._api_key, headers=hdrs)
                if retry_after and classified.retry_after_seconds is None:
                    classified.retry_after_seconds = retry_after
                raise classified from exc

        return structure_with_json_generator(context, generate_json)
