"""Provider selection, retries, and failover."""

from __future__ import annotations

import time
from typing import Callable

from config import AIProviderName, Settings
from models.document import StructuredExtractionResult
from providers.base import (
    AIProvider,
    ProviderAuthError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    ProviderTransientError,
    StructuringContext,
)
from providers.health import ProviderHealthTracker


SleepFn = Callable[[float], None]


class ProviderRouter(AIProvider):
    """
    Wraps one or more providers with bounded backoff and failover.

    Failover applies only to recoverable errors (transient, rate limit, auth on one key).
    Invalid requests are not retried or failovered.
    """

    provider_id = AIProviderName.AUTO

    def __init__(
        self,
        settings: Settings,
        providers: list[AIProvider],
        *,
        health: ProviderHealthTracker | None = None,
        sleep_fn: SleepFn | None = None,
    ) -> None:
        if not providers:
            raise ProviderInvalidRequestError("No AI providers configured.")
        self._settings = settings
        self._providers = providers
        self._health = health or ProviderHealthTracker()
        self._sleep = sleep_fn or time.sleep
        self._last_used_provider: str | None = None

    @property
    def name(self) -> str:
        if self._last_used_provider:
            return f"router→{self._last_used_provider}"
        return "router/auto"

    @property
    def last_used_provider(self) -> str | None:
        return self._last_used_provider

    @property
    def health(self) -> ProviderHealthTracker:
        return self._health

    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        errors: list[str] = []
        max_attempts = self._settings.ai_max_attempts_per_provider

        for provider in self._providers:
            provider_key = getattr(provider, "provider_id", None)
            if isinstance(provider_key, AIProviderName) and not self._health.is_available(
                provider_key
            ):
                errors.append(f"{provider.name}: in cooldown")
                continue

            for attempt in range(max_attempts):
                try:
                    result = provider.structure(context)
                except ProviderInvalidRequestError as exc:
                    if self._failover_invalid_request(exc, provider):
                        errors.append(f"{provider.name}: {exc}")
                        break
                    raise
                except ProviderModelNotFoundError as exc:
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_failure(provider_key, str(exc))
                    errors.append(f"{provider.name}: {exc}")
                    break
                except ProviderAuthError as exc:
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_failure(provider_key, str(exc))
                    errors.append(f"{provider.name}: {exc}")
                    break
                except ProviderRateLimitError as exc:
                    errors.append(f"{provider.name}: {exc}")
                    if attempt + 1 < max_attempts:
                        self._wait_before_retry(exc, attempt)
                        continue
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_failure(
                            provider_key,
                            str(exc),
                            retry_after_seconds=exc.retry_after_seconds,
                        )
                    break
                except ProviderTransientError as exc:
                    errors.append(f"{provider.name}: {exc}")
                    if attempt + 1 < max_attempts:
                        self._wait_before_retry(exc, attempt)
                        continue
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_failure(provider_key, str(exc))
                    break
                except ProviderError as exc:
                    if not exc.recoverable:
                        raise
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_failure(provider_key, str(exc))
                    errors.append(f"{provider.name}: {exc}")
                    break
                else:
                    if isinstance(provider_key, AIProviderName):
                        self._health.record_success(provider_key)
                    self._last_used_provider = provider.name
                    return result

        summary = "; ".join(errors) if errors else "No providers available."
        hint = (
            " Check GEMINI_MODEL and GROQ_MODEL in .env (see .env.example for current defaults)."
        )
        raise ProviderTransientError(f"All providers failed. {summary}.{hint}")

    def _failover_invalid_request(
        self, exc: ProviderInvalidRequestError, provider: AIProvider
    ) -> bool:
        """Try next provider when schema/JSON validation fails on one backend."""
        if provider is self._providers[-1]:
            return False
        message = str(exc).lower()
        tokens = (
            "json_validate",
            "failed validation",
            "invalid json",
            "json schema",
            "adjust your prompt",
        )
        return any(token in message for token in tokens)

    def _wait_before_retry(self, exc: ProviderError, attempt: int) -> None:
        if exc.retry_after_seconds is not None and exc.retry_after_seconds > 0:
            delay = exc.retry_after_seconds
        else:
            delay = min(
                self._settings.ai_retry_base_seconds * (2**attempt),
                self._settings.ai_retry_max_seconds,
            )
        self._sleep(delay)
