"""Structure OCR text into schema fields using an AI provider."""

from __future__ import annotations

from models.document import (
    ExtractionSchema,
    ProcessingStatus,
    SourceDocument,
)
from providers.base import AIProvider, ProviderError, StructuringContext


class StructuringService:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def _resolve_provider_label(self) -> str:
        last = getattr(self._provider, "last_used_provider", None)
        if isinstance(last, str) and last:
            return last
        return self._provider.name

    @property
    def provider_name(self) -> str:
        return self._resolve_provider_label()

    def structure_document(
        self,
        document: SourceDocument,
        schema: ExtractionSchema,
        *,
        retry: bool = False,
    ) -> SourceDocument:
        if document.status == ProcessingStatus.DUPLICATE_SKIPPED:
            return document

        if not document.ocr_text or not document.ocr_text.strip():
            document.mark_failed(
                ProcessingStatus.STRUCTURING_FAILED,
                "OCR text is missing. Run OCR before structuring.",
            )
            return document

        if retry:
            document.retry_count += 1
            document.error_message = None

        document.status = ProcessingStatus.STRUCTURING_IN_PROGRESS
        context = StructuringContext(
            ocr_text=document.ocr_text,
            source_filename=document.source_filename,
            schema=schema,
        )

        try:
            result = self._provider.structure(context)
        except ProviderError as exc:
            document.mark_failed(ProcessingStatus.STRUCTURING_FAILED, str(exc))
            document.last_provider = self._resolve_provider_label()
            return document
        except Exception as exc:
            document.mark_failed(
                ProcessingStatus.STRUCTURING_FAILED,
                "Unexpected error during structuring.",
            )
            document.last_provider = self._resolve_provider_label()
            _ = exc
            return document

        document.extraction = result
        document.schema_name = schema.name
        document.last_provider = self._resolve_provider_label()
        document.error_message = None
        document.status = (
            ProcessingStatus.REVIEW_REQUIRED
            if document.needs_review()
            else ProcessingStatus.READY_FOR_EXPORT
        )
        return document
