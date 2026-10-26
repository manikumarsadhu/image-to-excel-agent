"""Application configuration loaded from environment variables."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProviderName(str, Enum):
    AUTO = "auto"
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    CLOUDFLARE = "cloudflare"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: SecretStr | None = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    default_ai_provider: AIProviderName = AIProviderName.AUTO
    gemini_model: str = "gemini-3.8-flash"
    groq_model: str = "openai/gpt-oss-120b"

    ai_provider_order: str = "gemini,groq"
    ai_max_attempts_per_provider: int = Field(default=3, ge=1, le=10)
    ai_retry_base_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    ai_retry_max_seconds: float = Field(default=30.0, ge=1.0, le=300.0)

    max_upload_size_mb: int = Field(default=10, ge=1, le=100)
    max_image_width: int = Field(default=8000, ge=100)
    max_image_height: int = Field(default=8000, ge=100)
    allowed_image_extensions: str = "jpg,jpeg,png"

    fingerprint_enabled: bool = True
    excel_default_sheet: str = "ExtractedData"
    excel_line_items_sheet: str = "LineItems"

    ocr_lang: str = "en"
    paddle_use_gpu: bool = False

    @field_validator("allowed_image_extensions", mode="before")
    @classmethod
    def _normalize_extensions(cls, value: str) -> str:
        return value.lower().replace(" ", "")

    @property
    def allowed_extensions_set(self) -> frozenset[str]:
        parts = [p.strip().lstrip(".") for p in self.allowed_image_extensions.split(",")]
        return frozenset(p for p in parts if p)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def provider_configured(self, provider: AIProviderName) -> bool:
        """Return True only when required credentials exist for a provider."""
        if provider == AIProviderName.GEMINI:
            return self.gemini_api_key is not None and bool(
                self.gemini_api_key.get_secret_value().strip()
            )
        if provider == AIProviderName.GROQ:
            return self.groq_api_key is not None and bool(
                self.groq_api_key.get_secret_value().strip()
            )
        if provider == AIProviderName.OPENROUTER:
            return self.openrouter_api_key is not None and bool(
                self.openrouter_api_key.get_secret_value().strip()
            )
        if provider == AIProviderName.CLOUDFLARE:
            return bool(
                self.cloudflare_account_id
                and self.cloudflare_api_token
                and self.cloudflare_api_token.get_secret_value().strip()
            )
        if provider == AIProviderName.OLLAMA:
            return bool(self.ollama_base_url.strip() and self.ollama_model.strip())
        return provider == AIProviderName.AUTO

    def configured_cloud_providers(self) -> list[Literal["gemini", "groq"]]:
        """Providers with API keys present (does not verify quota or connectivity)."""
        names: list[Literal["gemini", "groq"]] = []
        if self.provider_configured(AIProviderName.GEMINI):
            names.append("gemini")
        if self.provider_configured(AIProviderName.GROQ):
            names.append("groq")
        return names


@lru_cache
def get_settings() -> Settings:
    return Settings()
