"""OCR engines for local text extraction."""

from ocr.base import OcrEngine, OcrEngineError, OcrResult
from ocr.paddle_ocr import PaddleOcrEngine, is_paddle_ocr_available

__all__ = [
    "OcrEngine",
    "OcrEngineError",
    "OcrResult",
    "PaddleOcrEngine",
    "is_paddle_ocr_available",
    "get_default_ocr_engine",
]


def get_default_ocr_engine(
    settings: "Settings | None" = None,
    *,
    lang: str | None = None,
    use_gpu: bool | None = None,
) -> OcrEngine:
    from config import Settings as SettingsCls

    cfg = settings or SettingsCls()
    if not is_paddle_ocr_available():
        raise OcrEngineError(
            "PaddleOCR is not available. Install paddlepaddle on Python 3.11–3.12, "
            "then paddleocr (see README)."
        )
    return PaddleOcrEngine(
        lang=lang if lang is not None else cfg.ocr_lang,
        use_gpu=use_gpu if use_gpu is not None else cfg.paddle_use_gpu,
    )
