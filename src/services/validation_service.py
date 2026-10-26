"""Validate uploaded images before OCR."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from config import Settings

ALLOWED_MIMES = frozenset({"image/jpeg", "image/png"})


class ImageValidationError(ValueError):
    """Upload failed validation (extension, size, MIME, or dimensions)."""


@dataclass(frozen=True)
class ValidatedImage:
    filename: str
    mime_type: str
    file_size_bytes: int
    width: int
    height: int
    content: bytes


def sniff_image_mime(content: bytes) -> str | None:
    if len(content) >= 8 and content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(content) >= 3 and content[0:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return None


def validate_image_upload(
    filename: str,
    content: bytes,
    settings: Settings,
    *,
    declared_mime: str | None = None,
) -> ValidatedImage:
    name = Path(filename).name
    if not name or name in {".", ".."}:
        raise ImageValidationError("Invalid filename.")

    extension = Path(name).suffix.lstrip(".").lower()
    if extension not in settings.allowed_extensions_set:
        allowed = ", ".join(sorted(settings.allowed_extensions_set))
        raise ImageValidationError(
            f"Unsupported file extension '.{extension}'. Allowed: {allowed}."
        )

    size = len(content)
    if size < 1:
        raise ImageValidationError("Empty file.")
    if size > settings.max_upload_size_bytes:
        raise ImageValidationError(
            f"File exceeds maximum size of {settings.max_upload_size_mb} MB."
        )

    sniffed = sniff_image_mime(content)
    if sniffed is None:
        raise ImageValidationError("File is not a valid JPEG or PNG image.")

    if declared_mime and declared_mime.lower() not in ALLOWED_MIMES:
        raise ImageValidationError(f"Unsupported MIME type: {declared_mime}.")
    if declared_mime and declared_mime.lower() != sniffed:
        raise ImageValidationError(
            "Declared MIME type does not match file content."
        )

    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        with Image.open(io.BytesIO(content)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError("Could not read image.") from exc

    if width > settings.max_image_width or height > settings.max_image_height:
        raise ImageValidationError(
            f"Image dimensions {width}x{height} exceed the "
            f"{settings.max_image_width}x{settings.max_image_height} limit."
        )

    return ValidatedImage(
        filename=name,
        mime_type=sniffed,
        file_size_bytes=size,
        width=width,
        height=height,
        content=content,
    )
