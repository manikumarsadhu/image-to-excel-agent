"""AI providers for structuring OCR text into schema fields."""

from providers.base import (
    AIProvider,
    ProviderAuthError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
    StructuringContext,
)
from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.health import ProviderHealthTracker
from providers.registry import create_provider
from providers.router import ProviderRouter

__all__ = [
    "AIProvider",
    "GeminiProvider",
    "GroqProvider",
    "ProviderHealthTracker",
    "ProviderRouter",
    "ProviderAuthError",
    "ProviderError",
    "ProviderInvalidRequestError",
    "ProviderRateLimitError",
    "ProviderTransientError",
    "StructuringContext",
    "create_provider",
]
