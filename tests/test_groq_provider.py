"""Tests for Groq provider (mocked API)."""

from __future__ import annotations

import pytest

from config import Settings
from models.document import ExtractionFieldDefinition, ExtractionSchema, FieldReviewStatus
from providers.base import ProviderAuthError, StructuringContext
from providers.groq import GroqProvider
from providers.response_models import ModelFieldOutput, ModelStructuringOutput


@pytest.fixture
def groq_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    return Settings(_env_file=None)


def test_groq_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError):
        GroqProvider(Settings(_env_file=None))


def test_groq_structure_uses_text_only(groq_settings: Settings) -> None:
    schema = ExtractionSchema(
        name="receipt",
        fields=[ExtractionFieldDefinition(key="total", label="Total")],
    )
    payload = ModelStructuringOutput(
        fields=[
            ModelFieldOutput(key="total", value="9.99", review_status=FieldReviewStatus.CONFIRMED)
        ]
    )

    def fake_generate(**kwargs: object) -> str:
        user = kwargs["user_content"]
        assert isinstance(user, str)
        assert "ocr_text" in user
        assert "image/png" not in user
        return payload.model_dump_json()

    provider = GroqProvider(groq_settings, generate_fn=fake_generate)
    result = provider.structure(
        StructuringContext(ocr_text="TOTAL 9.99", source_filename="r.png", schema=schema)
    )
    assert result.field_map()["total"].value == "9.99"
