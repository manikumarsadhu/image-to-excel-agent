"""OCR engines for local or cloud vision text extraction."""

from __future__ import annotations

from config import AIProviderName, Settings
from ocr.base import OcrEngine, OcrEngineError, OcrResult
from ocr.gemini_vision import GeminiVisionOcrEngine
from ocr.paddle_ocr import PaddleOcrEngine, is_paddle_ocr_available

__all__ = [
    "OcrEngine",
    "OcrEngineError",
    "OcrResult",
    "PaddleOcrEngine",
    "GeminiVisionOcrEngine",
    "is_paddle_ocr_available",
    "get_default_ocr_engine",
]


def get_default_ocr_engine(
    settings: Settings | None = None,
    *,
    engine_name: str | None = None,
    lang: str | None = None,
    use_gpu: bool | None = None,
) -> OcrEngine:
    cfg = settings or Settings()
    target = (engine_name or getattr(cfg, "ocr_engine", "auto")).lower()

    if target in {"gemini_vision", "gemini"}:
        if not cfg.provider_configured(AIProviderName.GEMINI):
            raise OcrEngineError("GEMINI_API_KEY is not configured for Gemini Vision OCR.")
        api_key = cfg.gemini_api_key.get_secret_value() if cfg.gemini_api_key else ""
        return GeminiVisionOcrEngine(api_key=api_key, model=cfg.gemini_model)

    if target in {"paddleocr", "paddle", "local"}:
        if not is_paddle_ocr_available():
            raise OcrEngineError(
                "PaddleOCR is not available. Install paddlepaddle on Python 3.11–3.12, "
                "or switch to Gemini Vision OCR."
            )
        return PaddleOcrEngine(
            lang=lang if lang is not None else cfg.ocr_lang,
            use_gpu=use_gpu if use_gpu is not None else cfg.paddle_use_gpu,
        )

    # "auto" mode: prefer local PaddleOCR if installed, fall back to Gemini Vision
    if is_paddle_ocr_available():
        return PaddleOcrEngine(
            lang=lang if lang is not None else cfg.ocr_lang,
            use_gpu=use_gpu if use_gpu is not None else cfg.paddle_use_gpu,
        )
    if cfg.provider_configured(AIProviderName.GEMINI):
        api_key = cfg.gemini_api_key.get_secret_value() if cfg.gemini_api_key else ""
        return GeminiVisionOcrEngine(api_key=api_key, model=cfg.gemini_model)

    raise OcrEngineError(
        "No OCR engine available. Either install paddlepaddle (Python 3.11–3.12) "
        "or configure GEMINI_API_KEY for cloud AI Vision OCR."
    )
