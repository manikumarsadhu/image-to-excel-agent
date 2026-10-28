"""PaddleOCR parsing and optional integration smoke test."""

from __future__ import annotations

import pytest

from ocr.paddle_ocr import is_paddle_ocr_available, parse_paddle_raw
from tests.helpers import make_test_png


def test_parse_paddle_raw_extracts_lines_and_confidence() -> None:
    raw = [
        [
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("Hello", 0.95)],
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("World", 0.85)],
        ]
    ]
    lines = parse_paddle_raw(raw)
    assert len(lines) == 2
    assert lines[0].text == "Hello"
    assert lines[0].confidence == pytest.approx(0.95)


def test_parse_paddle_raw_empty() -> None:
    assert parse_paddle_raw(None) == []
    assert parse_paddle_raw([None]) == []


def test_is_paddle_ocr_available_handles_runtime_or_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in {"paddle", "paddleocr"}:
            raise OSError("libgomp.so.1: cannot open shared object file")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert is_paddle_ocr_available() is False


def test_root_entrypoints_exist() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    assert (root / "streamlit_app.py").is_file()
    assert (root / "app.py").is_file()
    assert (root / "packages.txt").read_text(encoding="utf-8").splitlines() == [
        "libgl1",
        "libglib2.0-0",
        "libgomp1",
    ]


@pytest.mark.integration
@pytest.mark.skipif(not is_paddle_ocr_available(), reason="paddlepaddle not installed")
def test_paddle_ocr_smoke_on_generated_png() -> None:
    from ocr.paddle_ocr import PaddleOcrEngine

    engine = PaddleOcrEngine(lang="en", use_gpu=False)
    result = engine.extract_from_bytes(make_test_png("TOTAL 42.00"), source_hint="t.png")
    assert result.engine.startswith("paddleocr/")
    assert isinstance(result.full_text, str)

