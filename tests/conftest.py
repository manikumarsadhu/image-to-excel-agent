"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from config import Settings
from tests.helpers import FakeOcrEngine


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def fake_ocr() -> FakeOcrEngine:
    return FakeOcrEngine()
