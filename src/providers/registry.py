"""Provider factory and AUTO routing."""

from __future__ import annotations

from config import AIProviderName, Settings
from providers.base import AIProvider, ProviderInvalidRequestError
from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.router import ProviderRouter


def _build_provider(name: AIProviderName, settings: Settings) -> AIProvider:
    if name == AIProviderName.GEMINI:
        return GeminiProvider(settings)
    if name == AIProviderName.GROQ:
        return GroqProvider(settings)
    raise ProviderInvalidRequestError(f"Provider '{name.value}' is not implemented yet.")


def _parse_provider_order(raw: str) -> list[AIProviderName]:
    mapping = {
        "gemini": AIProviderName.GEMINI,
        "groq": AIProviderName.GROQ,
    }
    order: list[AIProviderName] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if not key:
            continue
        provider = mapping.get(key)
        if provider is None:
            continue
        if provider not in order:
            order.append(provider)
    return order


def configured_providers_in_order(settings: Settings) -> list[AIProvider]:
    """Instantiate configured providers following AI_PROVIDER_ORDER."""
    providers: list[AIProvider] = []
    for name in _parse_provider_order(settings.ai_provider_order):
        if not settings.provider_configured(name):
            continue
        providers.append(_build_provider(name, settings))
    return providers


def create_provider(name: AIProviderName, settings: Settings) -> AIProvider:
    if name == AIProviderName.AUTO:
        providers = configured_providers_in_order(settings)
        if not providers:
            raise ProviderInvalidRequestError(
                "No AI provider configured. Set GEMINI_API_KEY and/or GROQ_API_KEY."
            )
        if len(providers) == 1:
            return providers[0]
        return ProviderRouter(settings, providers)

    if not settings.provider_configured(name):
        raise ProviderInvalidRequestError(
            f"Provider '{name.value}' is not configured (missing API key or settings)."
        )
    provider = _build_provider(name, settings)
    return ProviderRouter(settings, [provider])
