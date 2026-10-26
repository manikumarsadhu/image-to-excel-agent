"""Tests for Gemini provider (mocked API)."""

from __future__ import annotations

import json

import pytest

from config import Settings
from models.document import (
    ExtractionFieldDefinition,
    ExtractionSchema,
    FieldReviewStatus,
)
from providers.base import ProviderAuthError, ProviderInvalidRequestError, StructuringContext
from providers.gemini import GeminiProvider
from providers.json_output import parse_model_json
from providers.mapping import map_model_output_to_result
from providers.response_models import ModelFieldOutput, ModelStructuringOutput


@pytest.fixture
def gemini_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    return Settings(_env_file=None)


@pytest.fixture
def receipt_schema() -> ExtractionSchema:
    return ExtractionSchema(
        name="receipt",
        description="Retail receipt",
        fields=[
            ExtractionFieldDefinition(key="vendor", label="Vendor", required=True),
            ExtractionFieldDefinition(key="total", label="Total", required=True),
        ],
    )


def test_gemini_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(ProviderAuthError):
        GeminiProvider(settings)


def test_structure_maps_schema_fields(gemini_settings: Settings, receipt_schema: ExtractionSchema) -> None:
    payload = ModelStructuringOutput(
        document_type="receipt",
        fields=[
            ModelFieldOutput(key="vendor", value="Acme Shop", review_status=FieldReviewStatus.CONFIRMED),
            ModelFieldOutput(key="total", value="42.00", review_status=FieldReviewStatus.CONFIRMED),
        ],
    )

    def fake_generate(**kwargs: object) -> str:
        assert "ocr_text" in kwargs["user_content"]  # type: ignore[index]
        assert "image" not in kwargs["user_content"].lower()  # type: ignore[union-attr]
        return payload.model_dump_json()

    provider = GeminiProvider(gemini_settings, generate_fn=fake_generate)
    context = StructuringContext(
        ocr_text="ACME SHOP\nTOTAL 42.00",
        source_filename="scan.png",
        schema=receipt_schema,
    )
    result = provider.structure(context)
    assert result.document_type == "receipt"
    assert result.field_map()["vendor"].value == "Acme Shop"
    assert result.field_map()["total"].value == "42.00"


def test_missing_model_field_becomes_missing_status(receipt_schema: ExtractionSchema) -> None:
    output = ModelStructuringOutput(
        fields=[ModelFieldOutput(key="vendor", value="Only Vendor")]
    )
    result = map_model_output_to_result(receipt_schema, output)
    assert result.field_map()["total"].review_status == FieldReviewStatus.MISSING


def test_parse_model_json_strips_markdown_fence() -> None:
    inner = {"document_type": "general", "fields": []}
    raw = "```json\n" + json.dumps(inner) + "\n```"
    parsed = parse_model_json(raw)
    assert parsed.document_type == "general"


def test_empty_ocr_rejected(gemini_settings: Settings, receipt_schema: ExtractionSchema) -> None:
    provider = GeminiProvider(
        gemini_settings,
        generate_fn=lambda **_: '{"document_type":"x","fields":[]}',
    )
    with pytest.raises(ProviderInvalidRequestError, match="empty"):
        provider.structure(
            StructuringContext(ocr_text="  ", source_filename="a.png", schema=receipt_schema)
        )
