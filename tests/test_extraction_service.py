"""Tests for OCR orchestration."""

from __future__ import annotations

from config import Settings
from models.document import ProcessingStatus
from ocr.base import OcrEngineError, OcrResult
from services.extraction_service import ExtractionService
from tests.helpers import FakeOcrEngine, make_test_png


class FailingOcrEngine(FakeOcrEngine):
    def extract_from_bytes(self, content: bytes, *, source_hint: str = "") -> OcrResult:
        raise OcrEngineError("engine offline")


def test_process_upload_runs_ocr(settings: Settings, fake_ocr: FakeOcrEngine) -> None:
    service = ExtractionService(settings, fake_ocr)
    content = make_test_png()
    doc = service.process_upload("receipt.png", content, declared_mime="image/png")
    assert doc.status == ProcessingStatus.PENDING
    assert doc.ocr_text == fake_ocr._text
    assert doc.ocr_engine == "fake/test"
    assert doc.source_filename == "receipt.png"


def test_duplicate_fingerprint_skips_ocr(settings: Settings, fake_ocr: FakeOcrEngine) -> None:
    service = ExtractionService(settings, fake_ocr)
    content = make_test_png()
    first = service.ingest_upload("a.png", content)
    assert first.fingerprint is not None
    second = service.process_upload(
        "a.png",
        content,
        known_fingerprints={first.fingerprint.value},
    )
    assert second.status == ProcessingStatus.DUPLICATE_SKIPPED
    assert second.ocr_text is None


def test_ocr_failure_sets_status(settings: Settings) -> None:
    service = ExtractionService(settings, FailingOcrEngine())
    content = make_test_png()
    doc = service.process_upload("x.png", content)
    assert doc.status == ProcessingStatus.OCR_FAILED
    assert doc.error_message == "engine offline"


def test_retry_increments_counter(settings: Settings, fake_ocr: FakeOcrEngine) -> None:
    service = ExtractionService(settings, FailingOcrEngine())
    content = make_test_png()
    doc = service.ingest_upload("x.png", content)
    doc = service.run_ocr(doc, content)
    assert doc.retry_count == 0

    service = ExtractionService(settings, fake_ocr)
    doc = service.run_ocr(doc, content, retry=True)
    assert doc.retry_count == 1
    assert doc.status == ProcessingStatus.PENDING
