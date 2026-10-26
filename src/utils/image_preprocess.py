"""Prepare images for OCR (orientation, EXIF)."""

from __future__ import annotations

import io

from PIL import Image, ImageOps


def normalize_image_for_ocr(content: bytes) -> bytes:
    """
    Apply EXIF orientation and lightly normalize for document OCR.

    Many phone photos store rotation in EXIF; PaddleOCR expects upright text.
    """
    with Image.open(io.BytesIO(content)) as img:
        img = ImageOps.exif_transpose(img)
        rgb = img.convert("RGB")
        # Portrait photo of a landscape invoice (common on WhatsApp) — try one 90° turn.
        width, height = rgb.size
        if height > width * 1.05:
            rgb = rgb.rotate(90, expand=True)
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()
