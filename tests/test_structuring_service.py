"""Tests for structuring orchestration on SourceDocument."""

from __future__ import annotations

from models.document import (
    ExtractionFieldDefinition,
    ExtractionSchema,
    FieldReviewStatus,
    ProcessingStatus,
    SourceDocument,
    StructuredExtractionResult,
    ExtractedFieldValue,
)
from providers.base import AIProvider, ProviderTransientError, StructuringContext
from services.structuring_service import StructuringService


class StubProvider(AIProvider):
    def __init__(self, result: StructuredExtractionResult | None = None, fail: bool = False) -> None:
        self._result = result
        self._fail = fail

    @property
    def name(self) -> str:
        return "stub/test"

    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        if self._fail:
            raise ProviderTransientError("temporary outage")
        assert self._result is not None
        return self._result


def _schema() -> ExtractionSchema:
    return ExtractionSchema(
        name="form",
        fields=[ExtractionFieldDefinition(key="name", label="Name")],
    )


def test_structure_sets_ready_when_all_confirmed() -> None:
    doc = SourceDocument(
        source_filename="f.png",
        mime_type="image/png",
        file_size_bytes=100,
        ocr_text="Name: Ada",
    )
    result = StructuredExtractionResult(
        fields=[
            ExtractedFieldValue(
                key="name",
                label="Name",
                value="Ada",
                review_status=FieldReviewStatus.CONFIRMED,
            )
        ]
    )
    service = StructuringService(StubProvider(result=result))
    out = service.structure_document(doc, _schema())
    assert out.status == ProcessingStatus.READY_FOR_EXPORT
    assert out.extraction == result
    assert out.last_provider == "stub/test"


def test_structure_sets_review_required_for_uncertain() -> None:
    doc = SourceDocument(
        source_filename="f.png",
        mime_type="image/png",
        file_size_bytes=100,
        ocr_text=" blurry ",
    )
    result = StructuredExtractionResult(
        fields=[
            ExtractedFieldValue(
                key="name",
                label="Name",
                value=None,
                review_status=FieldReviewStatus.UNCERTAIN,
            )
        ]
    )
    service = StructuringService(StubProvider(result=result))
    out = service.structure_document(doc, _schema())
    assert out.status == ProcessingStatus.REVIEW_REQUIRED


def test_structure_failure_marks_document() -> None:
    doc = SourceDocument(
        source_filename="f.png",
        mime_type="image/png",
        file_size_bytes=100,
        ocr_text="text",
    )
    service = StructuringService(StubProvider(fail=True))
    out = service.structure_document(doc, _schema())
    assert out.status == ProcessingStatus.STRUCTURING_FAILED
    assert "temporary" in (out.error_message or "")
