"""Tests for settings loading and provider configuration checks."""

from __future__ import annotations

from config import AIProviderName, Settings


def test_settings_no_keys_means_providers_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.configured_cloud_providers() == []
    assert settings.provider_configured(AIProviderName.GEMINI) is False


def test_settings_detects_gemini_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    settings = Settings(_env_file=None)
    assert settings.provider_configured(AIProviderName.GEMINI) is True
    assert "gemini" in settings.configured_cloud_providers()


def test_allowed_extensions_parsed() -> None:
    settings = Settings(
        _env_file=None,
        allowed_image_extensions=" JPG, PNG ,jpeg ",
    )
    assert settings.allowed_extensions_set == frozenset({"jpg", "png", "jpeg"})
