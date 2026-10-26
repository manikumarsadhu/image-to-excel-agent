"""Orchestrate validation, OCR, and duplicate detection for source documents."""

from __future__ import annotations

from config import Settings
from models.document import ProcessingStatus, SourceDocument
from ocr.base import OcrEngine, OcrEngineError, OcrResult
from services.validation_service import ImageValidationError, validate_image_upload
from utils.fingerprints import fingerprint_from_bytes
from utils.image_preprocess import normalize_image_for_ocr


class ExtractionService:
    def __init__(self, settings: Settings, ocr_engine: OcrEngine) -> None:
        self._settings = settings
        self._ocr = ocr_engine

    def ingest_upload(
        self,
        filename: str,
        content: bytes,
        *,
        declared_mime: str | None = None,
        known_fingerprints: set[str] | None = None,
    ) -> SourceDocument:
        """Validate upload and return a pending document (OCR not run yet)."""
        validated = validate_image_upload(
            filename, content, self._settings, declared_mime=declared_mime
        )
        document = SourceDocument(
            source_filename=validated.filename,
            mime_type=validated.mime_type,
            file_size_bytes=validated.file_size_bytes,
        )
        if self._settings.fingerprint_enabled:
            document.fingerprint = fingerprint_from_bytes(
                validated.content, source_filename=validated.filename
            )
            if (
                known_fingerprints
                and document.fingerprint.value in known_fingerprints
            ):
                document.status = ProcessingStatus.DUPLICATE_SKIPPED
                document.error_message = "Duplicate document fingerprint."
        return document

    def run_ocr(
        self,
        document: SourceDocument,
        content: bytes,
        *,
        retry: bool = False,
    ) -> SourceDocument:
        """Run OCR on validated bytes and update the document in place."""
        if document.status == ProcessingStatus.DUPLICATE_SKIPPED:
            return document

        if retry:
            document.retry_count += 1
            document.error_message = None

        document.status = ProcessingStatus.OCR_IN_PROGRESS
        try:
            validate_image_upload(
                document.source_filename,
                content,
                self._settings,
                declared_mime=document.mime_type,
            )
            ocr_bytes = normalize_image_for_ocr(content)
            result = self._ocr.extract_from_bytes(
                ocr_bytes, source_hint=document.source_filename
            )
        except ImageValidationError as exc:
            document.mark_failed(ProcessingStatus.OCR_FAILED, str(exc))
            return document
        except OcrEngineError as exc:
            document.mark_failed(ProcessingStatus.OCR_FAILED, str(exc))
            return document

        document.ocr_text = result.full_text
        document.ocr_engine = result.engine
        document.status = ProcessingStatus.PENDING
        document.error_message = None
        return document

    def process_upload(
        self,
        filename: str,
        content: bytes,
        *,
        declared_mime: str | None = None,
        known_fingerprints: set[str] | None = None,
        retry: bool = False,
    ) -> SourceDocument:
        """Validate, detect duplicates, and run OCR in one step."""
        document = self.ingest_upload(
            filename,
            content,
            declared_mime=declared_mime,
            known_fingerprints=known_fingerprints,
        )
        if document.status == ProcessingStatus.DUPLICATE_SKIPPED:
            return document
        return self.run_ocr(document, content, retry=retry)
