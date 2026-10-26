"""Pydantic models for documents, extraction schemas, and processing state."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.pharmacy import PharmacyLineItem


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    OCR_IN_PROGRESS = "ocr_in_progress"
    OCR_FAILED = "ocr_failed"
    STRUCTURING_IN_PROGRESS = "structuring_in_progress"
    STRUCTURING_FAILED = "structuring_failed"
    REVIEW_REQUIRED = "review_required"
    READY_FOR_EXPORT = "ready_for_export"
    EXPORTED = "exported"
    DUPLICATE_SKIPPED = "duplicate_skipped"


class FieldReviewStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
    MISSING = "missing"
    USER_EDITED = "user_edited"


class ExtractionFieldDefinition(BaseModel):
    """User-configurable field the AI should populate from OCR text."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    required: bool = False
    examples: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("examples")
    @classmethod
    def _trim_examples(cls, value: list[str]) -> list[str]:
        return [e.strip() for e in value if e.strip()]


class ExtractionSchema(BaseModel):
    """Named set of fields (e.g. receipt, application form)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=512)
    fields: list[ExtractionFieldDefinition] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _unique_field_keys(self) -> ExtractionSchema:
        keys = [f.key for f in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("field keys must be unique within a schema")
        return self


class ExtractedFieldValue(BaseModel):
    """Single structured value with review metadata."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: str
    label: str
    value: str | None = None
    review_status: FieldReviewStatus = FieldReviewStatus.CONFIRMED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _align_missing_with_status(self) -> ExtractedFieldValue:
        if self.review_status == FieldReviewStatus.MISSING:
            self.value = None
        elif self.value is None or not str(self.value).strip():
            self.value = None
            if self.review_status == FieldReviewStatus.CONFIRMED:
                self.review_status = FieldReviewStatus.MISSING
        return self


class StructuredExtractionResult(BaseModel):
    """Validated AI output before user review."""

    document_type: str = Field(default="general", max_length=64)
    fields: list[ExtractedFieldValue] = Field(default_factory=list)
    line_items: list[PharmacyLineItem] = Field(default_factory=list)
    raw_model_notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _unique_field_keys(self) -> StructuredExtractionResult:
        keys = [f.key for f in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("extracted field keys must be unique")
        return self

    def field_map(self) -> dict[str, ExtractedFieldValue]:
        return {f.key: f for f in self.fields}


class DocumentFingerprint(BaseModel):
    """Stable fingerprint to detect duplicate imports."""

    algorithm: str = "sha256"
    value: str = Field(..., min_length=16, max_length=128)

    @field_validator("value")
    @classmethod
    def _normalize_hex(cls, value: str) -> str:
        return value.strip().lower()


class SourceDocument(BaseModel):
    """One uploaded image and its processing lifecycle."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)
    source_filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=3, max_length=128)
    file_size_bytes: int = Field(..., ge=1)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    ocr_text: str | None = None
    ocr_engine: str | None = None

    schema_name: str | None = None
    extraction: StructuredExtractionResult | None = None

    fingerprint: DocumentFingerprint | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: str | None = Field(default=None, max_length=2000)
    retry_count: int = Field(default=0, ge=0)
    last_provider: str | None = None

    user_edited: bool = False

    def mark_failed(self, status: ProcessingStatus, message: str) -> None:
        if status not in (
            ProcessingStatus.OCR_FAILED,
            ProcessingStatus.STRUCTURING_FAILED,
        ):
            raise ValueError("mark_failed requires an *_FAILED status")
        self.status = status
        self.error_message = message[:2000]

    def needs_review(self) -> bool:
        if self.extraction is None:
            return True
        return any(
            f.review_status in (FieldReviewStatus.UNCERTAIN, FieldReviewStatus.MISSING)
            for f in self.extraction.fields
        )


class DocumentProcessingState(BaseModel):
    """Batch processing snapshot for UI and export."""

    documents: list[SourceDocument] = Field(default_factory=list)
    extraction_schema: ExtractionSchema | None = None

    def by_id(self, document_id: UUID) -> SourceDocument | None:
        for doc in self.documents:
            if doc.id == document_id:
                return doc
        return None

    def fingerprint_values(self) -> set[str]:
        return {
            d.fingerprint.value
            for d in self.documents
            if d.fingerprint is not None
        }


def merge_user_edits(
    extraction: StructuredExtractionResult,
    edits: dict[str, str | None],
) -> StructuredExtractionResult:
    """Apply user edits without inventing values for keys not in the schema result."""
    field_map = extraction.field_map()
    updated: list[ExtractedFieldValue] = []
    for field in extraction.fields:
        if field.key not in edits:
            updated.append(field)
            continue
        new_value = edits[field.key]
        if new_value is None or new_value.strip() == "":
            updated.append(
                field.model_copy(
                    update={
                        "value": None,
                        "review_status": FieldReviewStatus.MISSING,
                    }
                )
            )
        else:
            updated.append(
                field.model_copy(
                    update={
                        "value": new_value.strip(),
                        "review_status": FieldReviewStatus.USER_EDITED,
                    }
                )
            )
    return extraction.model_copy(update={"fields": updated})
