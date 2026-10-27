"""Gemini Vision OCR engine: extract text directly from document images via Gemini API."""

from __future__ import annotations

from typing import Callable

from ocr.base import OcrEngine, OcrEngineError, OcrLine, OcrResult
from providers.errors import redact_secrets


def _guess_mime(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"RIFF") and len(content) > 12 and content[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


DEFAULT_OCR_PROMPT = (
    "Extract all visible text from this document image exactly as printed.\n"
    "Preserve layout, tabular columns, itemized rows, and line breaks where applicable.\n"
    "Do not summarize, do not omit numbers or codes, and do not include conversational text or markdown code blocks."
)

GeminiVisionGenerateFn = Callable[[bytes, str, str, str], str]


def default_gemini_vision_generate(
    content: bytes,
    mime_type: str,
    api_key: str,
    model: str,
    prompt: str = DEFAULT_OCR_PROMPT,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise OcrEngineError(
            "google-genai is not installed. Run `pip install google-genai`."
        ) from exc

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=content, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        )
    except Exception as exc:
        safe_msg = redact_secrets(str(exc), api_key)
        raise OcrEngineError(f"Gemini Vision OCR failed: {safe_msg}") from exc

    text = getattr(response, "text", None) or ""
    return text.strip()


class GeminiVisionOcrEngine(OcrEngine):
    """Extract printed and handwritten text using Google Gemini Multimodal Vision."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
        *,
        generate_fn: GeminiVisionGenerateFn | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise OcrEngineError("Gemini API key is required for Gemini Vision OCR.")
        self._api_key = api_key.strip()
        self._model = model.strip() or "gemini-3.8-flash"
        self._generate_fn = generate_fn or default_gemini_vision_generate

    @property
    def name(self) -> str:
        return f"gemini_vision/{self._model}"

    def extract_from_bytes(self, content: bytes, *, source_hint: str = "") -> OcrResult:
        if not content:
            return OcrResult(engine=self.name, full_text="", lines=[])

        mime_type = _guess_mime(content)
        try:
            full_text = self._generate_fn(
                content,
                mime_type,
                self._api_key,
                self._model,
            )
        except OcrEngineError:
            raise
        except Exception as exc:
            safe = redact_secrets(str(exc), self._api_key)
            raise OcrEngineError(f"Gemini Vision extraction failed: {safe}") from exc

        raw_lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        lines = [OcrLine(text=line, confidence=0.95) for line in raw_lines]
        return OcrResult(
            engine=self.name,
            full_text=full_text,
            lines=lines,
            average_confidence=0.95 if lines else None,
        )
