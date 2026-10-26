"""Common AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from models.document import ExtractionSchema, StructuredExtractionResult


class ProviderError(Exception):
    """Base error for AI structuring failures."""

    recoverable: bool = False
    retry_after_seconds: float | None = None

    def __init__(
        self,
        message: str,
        *,
        recoverable: bool | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        if recoverable is not None:
            self.recoverable = recoverable
        self.retry_after_seconds = retry_after_seconds


class ProviderAuthError(ProviderError):
    recoverable = False


class ProviderInvalidRequestError(ProviderError):
    recoverable = False


class ProviderModelNotFoundError(ProviderError):
    """Unknown or retired model ID; failover to another provider may work."""

    recoverable = False


class ProviderRateLimitError(ProviderError):
    recoverable = True


class ProviderTransientError(ProviderError):
    recoverable = True


@dataclass(frozen=True)
class StructuringContext:
    """Minimum text sent to cloud providers (no image bytes)."""

    ocr_text: str
    source_filename: str
    schema: ExtractionSchema


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        """Map OCR text to validated structured fields."""
        raise NotImplementedError
