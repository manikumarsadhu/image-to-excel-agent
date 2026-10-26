"""Wire OCR + AI structuring for the UI."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from config import AIProviderName, Settings
from models.document import (
    DocumentProcessingState,
    ExtractionSchema,
    ProcessingStatus,
    SourceDocument,
    merge_user_edits,
)
from ocr.base import OcrEngine, OcrEngineError
from ocr import get_default_ocr_engine
from providers.registry import create_provider
from services.extraction_service import ExtractionService
from services.structuring_service import StructuringService
from utils.pharmacy_lines import parse_product_lines_text


@dataclass
class PipelineOutcome:
    document: SourceDocument
    message: str | None = None


def create_ocr_engine_or_none(settings: Settings) -> tuple[OcrEngine | None, str | None]:
    try:
        return get_default_ocr_engine(settings), None
    except OcrEngineError as exc:
        return None, str(exc)


def create_structuring_service(settings: Settings, provider_name: AIProviderName) -> StructuringService:
    provider = create_provider(provider_name, settings)
    return StructuringService(provider)


def process_upload(
    *,
    settings: Settings,
    ocr_engine: OcrEngine,
    structuring: StructuringService,
    schema: ExtractionSchema,
    filename: str,
    content: bytes,
    declared_mime: str | None,
    known_fingerprints: set[str],
) -> PipelineOutcome:
    extraction = ExtractionService(settings, ocr_engine)
    document = extraction.ingest_upload(
        filename,
        content,
        declared_mime=declared_mime,
        known_fingerprints=known_fingerprints,
    )
    if document.status == ProcessingStatus.DUPLICATE_SKIPPED:
        return PipelineOutcome(
            document=document,
            message="Skipped duplicate (matching fingerprint).",
        )

    document = extraction.run_ocr(document, content)
    if document.status == ProcessingStatus.OCR_FAILED:
        return PipelineOutcome(document=document, message=document.error_message)

    document = structuring.structure_document(document, schema)
    if document.status == ProcessingStatus.STRUCTURING_FAILED:
        return PipelineOutcome(document=document, message=document.error_message)

    return PipelineOutcome(document=document)


def retry_document(
    *,
    settings: Settings,
    ocr_engine: OcrEngine,
    structuring: StructuringService,
    schema: ExtractionSchema,
    document: SourceDocument,
    content: bytes,
) -> PipelineOutcome:
    extraction = ExtractionService(settings, ocr_engine)
    if document.status == ProcessingStatus.OCR_FAILED or not document.ocr_text:
        document = extraction.run_ocr(document, content, retry=True)
        if document.status == ProcessingStatus.OCR_FAILED:
            return PipelineOutcome(document=document, message=document.error_message)

    document = structuring.structure_document(document, schema, retry=True)
    if document.status == ProcessingStatus.STRUCTURING_FAILED:
        return PipelineOutcome(document=document, message=document.error_message)
    return PipelineOutcome(document=document)


def apply_edits_to_document(
    document: SourceDocument,
    schema: ExtractionSchema,
    edits: dict[str, str | None],
) -> SourceDocument:
    if document.extraction is None:
        return document
    document.extraction = merge_user_edits(document.extraction, edits)
    if schema.name == "pharmacy_tax_invoice" and "product_lines" in edits:
        text = edits.get("product_lines")
        line_items = parse_product_lines_text(text) if text else []
        document.extraction = document.extraction.model_copy(
            update={"line_items": line_items}
        )
    document.user_edited = True
    document.status = (
        ProcessingStatus.REVIEW_REQUIRED
        if document.needs_review()
        else ProcessingStatus.READY_FOR_EXPORT
    )
    return document


def replace_document(state: DocumentProcessingState, updated: SourceDocument) -> None:
    for index, doc in enumerate(state.documents):
        if doc.id == updated.id:
            state.documents[index] = updated
            return
    state.documents.append(updated)


def get_file_bytes(store: dict[str, bytes], document_id: UUID) -> bytes | None:
    return store.get(str(document_id))
