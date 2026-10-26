"""Tests for Pydantic document models and validation rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.document import (
    ExtractionFieldDefinition,
    ExtractionSchema,
    ExtractedFieldValue,
    FieldReviewStatus,
    ProcessingStatus,
    SourceDocument,
    StructuredExtractionResult,
    merge_user_edits,
)
from utils.fingerprints import fingerprint_from_bytes


def test_extraction_schema_rejects_duplicate_keys() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ExtractionSchema(
            name="receipt",
            fields=[
                ExtractionFieldDefinition(key="total", label="Total"),
                ExtractionFieldDefinition(key="total", label="Total again"),
            ],
        )


def test_extracted_field_missing_status_clears_value() -> None:
    field = ExtractedFieldValue(
        key="amount",
        label="Amount",
        value="12.50",
        review_status=FieldReviewStatus.MISSING,
    )
    assert field.value is None
    assert field.review_status == FieldReviewStatus.MISSING


def test_extracted_field_empty_value_becomes_missing() -> None:
    field = ExtractedFieldValue(key="name", label="Name", value="   ")
    assert field.value is None
    assert field.review_status == FieldReviewStatus.MISSING
    empty = ExtractedFieldValue(key="name", label="Name", value=None)
    assert empty.review_status == FieldReviewStatus.MISSING


def test_structured_result_unicode_roundtrip() -> None:
    result = StructuredExtractionResult(
        fields=[
            ExtractedFieldValue(
                key="vendor",
                label="Vendor",
                value="Café Müller — ₹500",
                review_status=FieldReviewStatus.CONFIRMED,
            )
        ]
    )
    restored = StructuredExtractionResult.model_validate_json(result.model_dump_json())
    assert restored.fields[0].value == "Café Müller — ₹500"


def test_source_document_mark_failed() -> None:
    doc = SourceDocument(
        source_filename="scan.png",
        mime_type="image/png",
        file_size_bytes=1024,
    )
    doc.mark_failed(ProcessingStatus.OCR_FAILED, "OCR timeout")
    assert doc.status == ProcessingStatus.OCR_FAILED
    assert doc.error_message == "OCR timeout"

    with pytest.raises(ValueError):
        doc.mark_failed(ProcessingStatus.READY_FOR_EXPORT, "invalid")


def test_merge_user_edits_does_not_invent_unrelated_fields() -> None:
    extraction = StructuredExtractionResult(
        fields=[
            ExtractedFieldValue(key="total", label="Total", value="10.00"),
        ]
    )
    merged = merge_user_edits(extraction, {"total": "10.50", "phantom": "ignored"})
    keys = {f.key for f in merged.fields}
    assert "phantom" not in keys
    assert merged.field_map()["total"].value == "10.50"
    assert merged.field_map()["total"].review_status == FieldReviewStatus.USER_EDITED


def test_fingerprint_stable_for_same_content() -> None:
    data = b"\x89PNG fake"
    a = fingerprint_from_bytes(data, source_filename="a.png")
    b = fingerprint_from_bytes(data, source_filename="a.png")
    c = fingerprint_from_bytes(data, source_filename="b.png")
    assert a.value == b.value
    assert a.value != c.value
