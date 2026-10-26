"""OCR engine interface and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from pydantic import BaseModel, Field


class OcrEngineError(Exception):
    """Raised when OCR cannot run or fails for a recoverable reason."""


class OcrLine(BaseModel):
    text: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class OcrResult(BaseModel):
    engine: str
    full_text: str
    lines: list[OcrLine] = Field(default_factory=list)
    average_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @classmethod
    def from_lines(cls, *, engine: str, lines: Sequence[OcrLine]) -> OcrResult:
        non_empty = [line for line in lines if line.text.strip()]
        full_text = "\n".join(line.text.strip() for line in non_empty)
        confidences = [line.confidence for line in non_empty if line.confidence is not None]
        average = sum(confidences) / len(confidences) if confidences else None
        return cls(
            engine=engine,
            full_text=full_text,
            lines=list(non_empty),
            average_confidence=average,
        )


class OcrEngine(ABC):
    """Extract printed text from images locally (no cloud upload)."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract_from_bytes(self, content: bytes, *, source_hint: str = "") -> OcrResult:
        raise NotImplementedError
