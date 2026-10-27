"""Tests for Gemini Vision OCR engine."""

from __future__ import annotations

import pytest

from config import Settings
from ocr.base import OcrEngineError
from ocr.gemini_vision import GeminiVisionOcrEngine
from ocr import get_default_ocr_engine
from ui.pipeline import create_ocr_engine_or_none


def test_gemini_vision_ocr_requires_api_key() -> None:
    with pytest.raises(OcrEngineError, match="Gemini API key is required"):
        GeminiVisionOcrEngine(api_key="")


def test_gemini_vision_ocr_name_property() -> None:
    engine = GeminiVisionOcrEngine(api_key="fake-key", model="gemini-3.8-flash")
    assert engine.name == "gemini_vision/gemini-3.8-flash"


def test_gemini_vision_ocr_empty_bytes() -> None:
    engine = GeminiVisionOcrEngine(api_key="fake-key")
    res = engine.extract_from_bytes(b"")
    assert res.full_text == ""
    assert res.lines == []


def test_gemini_vision_ocr_extracts_lines_with_mock() -> None:
    calls: list[tuple[bytes, str, str, str]] = []

    def mock_generate(content: bytes, mime_type: str, api_key: str, model: str) -> str:
        calls.append((content, mime_type, api_key, model))
        return "Invoice #12345\nDate: 2026-10-27\nTotal: $99.00"

    engine = GeminiVisionOcrEngine(
        api_key="secret-api-key",
        model="gemini-3.8-flash",
        generate_fn=mock_generate,
    )

    test_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    result = engine.extract_from_bytes(test_png)

    assert len(calls) == 1
    content, mime, key, model = calls[0]
    assert content == test_png
    assert mime == "image/png"
    assert key == "secret-api-key"
    assert model == "gemini-3.8-flash"

    assert "Invoice #12345" in result.full_text
    assert len(result.lines) == 3
    assert result.lines[0].text == "Invoice #12345"
    assert result.lines[1].text == "Date: 2026-10-27"
    assert result.lines[2].text == "Total: $99.00"
    assert result.average_confidence == pytest.approx(0.95)


def test_gemini_vision_ocr_redacts_api_key_on_failure() -> None:
    def failing_generate(content: bytes, mime_type: str, api_key: str, model: str) -> str:
        raise RuntimeError(f"Connection failed for key {api_key}")

    engine = GeminiVisionOcrEngine(
        api_key="my-super-secret-key-1234",
        generate_fn=failing_generate,
    )

    with pytest.raises(OcrEngineError) as exc_info:
        engine.extract_from_bytes(b"\xff\xd8\xffjpegbytes")

    err_str = str(exc_info.value)
    assert "my-super-secret-key-1234" not in err_str
    assert "***" in err_str


def test_get_default_ocr_engine_with_gemini(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    settings = Settings(_env_file=None)

    engine = get_default_ocr_engine(settings, engine_name="gemini_vision")
    assert isinstance(engine, GeminiVisionOcrEngine)
    assert engine.name.startswith("gemini_vision/")


def test_get_default_ocr_engine_gemini_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = Settings(_env_file=None)

    with pytest.raises(OcrEngineError, match="GEMINI_API_KEY is not configured"):
        get_default_ocr_engine(settings, engine_name="gemini_vision")


def test_create_ocr_engine_or_none_handles_errors(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = Settings(_env_file=None)

    engine, err = create_ocr_engine_or_none(settings, engine_name="gemini_vision")
    assert engine is None
    assert err is not None
    assert "GEMINI_API_KEY is not configured" in err
