"""Tests for image upload validation."""

from __future__ import annotations

import pytest

from config import Settings
from services.validation_service import ImageValidationError, validate_image_upload
from tests.helpers import make_test_png


def test_valid_png_passes(settings: Settings) -> None:
    content = make_test_png()
    validated = validate_image_upload("doc.png", content, settings, declared_mime="image/png")
    assert validated.mime_type == "image/png"
    assert validated.width == 320


def test_rejects_oversized_file(settings: Settings) -> None:
    settings = Settings(_env_file=None, max_upload_size_mb=1)
    content = make_test_png() + b"\x00" * (2 * 1024 * 1024)
    with pytest.raises(ImageValidationError, match="maximum size"):
        validate_image_upload("big.png", content, settings)


def test_rejects_bad_extension(settings: Settings) -> None:
    content = make_test_png()
    with pytest.raises(ImageValidationError, match="extension"):
        validate_image_upload("doc.gif", content, settings)


def test_rejects_mime_mismatch(settings: Settings) -> None:
    content = make_test_png()
    with pytest.raises(ImageValidationError, match="does not match"):
        validate_image_upload("doc.png", content, settings, declared_mime="image/jpeg")


def test_rejects_oversized_dimensions(settings: Settings) -> None:
    settings = Settings(_env_file=None, max_image_width=100, max_image_height=100)
    content = make_test_png(size=(200, 200))
    with pytest.raises(ImageValidationError, match="dimensions"):
        validate_image_upload("large.png", content, settings)
