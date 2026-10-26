"""PaddleOCR adapter (requires paddlepaddle + paddleocr)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ocr.base import OcrEngine, OcrEngineError, OcrLine, OcrResult

_WINDOWS_PADDLE_HINT = (
    "On Windows, use paddlepaddle==2.6.2 with paddleocr 2.x "
    "(pip install paddlepaddle==2.6.2). Paddle 3.x is not compatible with this OCR stack."
)


def _friendly_paddle_error(exc: Exception) -> str:
    raw = str(exc)
    if "OneDnnContext" in raw or "fused_conv2d" in raw or "fluid/dygraph" in raw:
        return f"PaddleOCR failed (PaddlePaddle version mismatch). {_WINDOWS_PADDLE_HINT}"
    first_line = raw.strip().splitlines()[0] if raw.strip() else repr(exc)
    if len(first_line) > 240:
        first_line = first_line[:240] + "…"
    return f"PaddleOCR failed: {first_line}"


def is_paddle_ocr_available() -> bool:
    try:
        import paddle  # noqa: F401
        from paddleocr import PaddleOCR  # noqa: F401
    except ImportError:
        return False
    return True


def parse_paddle_raw(raw: Any) -> list[OcrLine]:
    """
    Normalize PaddleOCR output into lines.

    Typical shape: list[ list[ [box], (text, score) ] ] with optional None pages.
    """
    if not raw:
        return []
    lines: list[OcrLine] = []
    pages = raw if isinstance(raw, list) else [raw]
    for page in pages:
        if not page:
            continue
        for item in page:
            if not item or len(item) < 2:
                continue
            text_part = item[1]
            if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                text = str(text_part[0]).strip()
                confidence = float(text_part[1]) if len(text_part) > 1 else None
            else:
                text = str(text_part).strip()
                confidence = None
            if text:
                lines.append(OcrLine(text=text, confidence=confidence))
    return lines


class PaddleOcrEngine(OcrEngine):
    def __init__(self, *, lang: str = "en", use_gpu: bool = False) -> None:
        if not is_paddle_ocr_available():
            raise OcrEngineError(
                "paddlepaddle and paddleocr must be installed (Python 3.11–3.12 recommended)."
            )
        from paddleocr import PaddleOCR

        self._lang = lang
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)

    @property
    def name(self) -> str:
        return f"paddleocr/{self._lang}"

    def extract_from_bytes(self, content: bytes, *, source_hint: str = "") -> OcrResult:
        suffix = Path(source_hint).suffix if source_hint else ".png"
        if suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            suffix = ".png"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            raw = self._ocr.ocr(str(tmp_path), cls=True)
            lines = parse_paddle_raw(raw)
            return OcrResult.from_lines(engine=self.name, lines=lines)
        except OcrEngineError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as OCR failure, not crash
            raise OcrEngineError(_friendly_paddle_error(exc)) from exc
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
