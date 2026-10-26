"""Groq adapter (text in, JSON out via chat completions)."""

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
from providers.errors import classify_http_like_error, redact_secrets
from providers.structuring import structure_with_json_generator


class GroqGenerateFn(Protocol):
    def __call__(self, *, model: str, system_instruction: str, user_content: str) -> str: ...


def default_groq_generate(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    user_content: str,
) -> str:
    try:
        from groq import Groq
    except ImportError as exc:
        from providers.base import ProviderTransientError

        raise ProviderTransientError(
            "groq package is not installed. pip install groq"
        ) from exc

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_completion_tokens=16384,
        )
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        headers: dict[str, str] | None = None
        response = getattr(exc, "response", None)
        if response is not None:
            raw_headers = getattr(response, "headers", None)
            if raw_headers is not None:
                headers = dict(raw_headers)
        raise classify_http_like_error(
            exc, api_key=api_key, status_code=status, headers=headers
        ) from exc

    choices = getattr(response, "choices", None) or []
    if not choices:
        from providers.base import ProviderTransientError

        raise ProviderTransientError("Groq returned no choices.")
    message = choices[0].message
    text = getattr(message, "content", None) or ""
    if not text.strip():
        from providers.base import ProviderTransientError

        raise ProviderTransientError("Groq returned empty content.")
    return text


class GroqProvider(AIProvider):
    provider_id = AIProviderName.GROQ

    def __init__(
        self,
        settings: Settings,
        *,
        generate_fn: GroqGenerateFn | None = None,
    ) -> None:
        if not settings.provider_configured(AIProviderName.GROQ):
            raise ProviderAuthError("Groq is not configured (set GROQ_API_KEY).")
        self._api_key = settings.groq_api_key.get_secret_value().strip()
        self._model = settings.groq_model
        if generate_fn is not None:
            self._generate = generate_fn
        else:
            api_key = self._api_key

            def _bound(
                *,
                model: str,
                system_instruction: str,
                user_content: str,
            ) -> str:
                return default_groq_generate(
                    api_key=api_key,
                    model=model,
                    system_instruction=system_instruction,
                    user_content=user_content,
                )

            self._generate = _bound

    @property
    def name(self) -> str:
        return f"groq/{self._model}"

    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        def generate_json(system: str, user: str, _schema: dict[str, Any]) -> str:
            try:
                return self._generate(
                    model=self._model,
                    system_instruction=system,
                    user_content=user,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_http_like_error(exc, api_key=self._api_key) from exc

        return structure_with_json_generator(context, generate_json)
