"""Image preprocessing for OCR."""

from __future__ import annotations

import io

from PIL import Image

from tests.helpers import make_test_png
from utils.image_preprocess import normalize_image_for_ocr


def test_normalize_returns_jpeg_bytes() -> None:
    out = normalize_image_for_ocr(make_test_png())
    assert out[:3] == b"\xff\xd8\xff"
    with Image.open(io.BytesIO(out)) as img:
        assert img.mode == "RGB"
