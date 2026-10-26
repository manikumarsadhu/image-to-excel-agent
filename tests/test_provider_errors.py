"""Error classification for provider HTTP responses."""

from __future__ import annotations

from providers.base import ProviderModelNotFoundError
from providers.errors import classify_http_like_error


def test_404_model_maps_to_model_not_found() -> None:
    exc = Exception(
        "404 NOT_FOUND. models/gemini-2.0-flash is no longer available."
    )
    err = classify_http_like_error(exc, status_code=404)
    assert isinstance(err, ProviderModelNotFoundError)


def test_groq_model_not_found() -> None:
    exc = Exception(
        "Error code: 404 - {'error': {'message': 'The model llama-3.3-70b-versatile does not exist'}}"
    )
    err = classify_http_like_error(exc, status_code=404)
    assert isinstance(err, ProviderModelNotFoundError)
