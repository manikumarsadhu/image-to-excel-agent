"""Test helpers (PNG generation, fake OCR)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from ocr.base import OcrEngine, OcrResult


class FakeOcrEngine(OcrEngine):
    def __init__(self, text: str = "Sample OCR line 1\nLine 2") -> None:
        self._text = text

    @property
    def name(self) -> str:
        return "fake/test"

    def extract_from_bytes(self, content: bytes, *, source_hint: str = "") -> OcrResult:
        return OcrResult(
            engine=self.name,
            full_text=self._text,
            lines=[],
            average_confidence=0.99,
        )


def make_test_png(
    text: str = "INVOICE 123",
    *,
    size: tuple[int, int] = (320, 120),
    rgb: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    image = Image.new("RGB", size, rgb)
    draw = ImageDraw.Draw(image)
    draw.text((10, 40), text, fill=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
