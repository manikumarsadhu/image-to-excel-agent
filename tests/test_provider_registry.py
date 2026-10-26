"""Provider factory tests."""

from __future__ import annotations

import pytest

from config import AIProviderName, Settings
from providers.base import ProviderInvalidRequestError
from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.registry import create_provider, configured_providers_in_order
from providers.router import ProviderRouter


def test_create_gemini_provider_wraps_router(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    settings = Settings(_env_file=None)
    provider = create_provider(AIProviderName.GEMINI, settings)
    assert isinstance(provider, ProviderRouter)


def test_auto_single_provider_returns_direct_instance(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    provider = create_provider(AIProviderName.AUTO, settings)
    assert isinstance(provider, GeminiProvider)


def test_auto_two_providers_returns_router(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GROQ_API_KEY", "secret2")
    settings = Settings(_env_file=None)
    provider = create_provider(AIProviderName.AUTO, settings)
    assert isinstance(provider, ProviderRouter)
    assert len(configured_providers_in_order(settings)) == 2


def test_auto_without_keys_raises(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(ProviderInvalidRequestError):
        create_provider(AIProviderName.AUTO, settings)


def test_create_groq(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "secret")
    settings = Settings(_env_file=None)
    provider = create_provider(AIProviderName.GROQ, settings)
    assert isinstance(provider, ProviderRouter)
