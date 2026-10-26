"""Streamlit secrets → environment bridging."""

from __future__ import annotations

import os

from config import _flatten_secret_values, apply_streamlit_secrets_to_environ


def test_flatten_top_level_secrets() -> None:
    mapping = {
        "GEMINI_API_KEY": "g-test",
        "GROQ_API_KEY": "q-test",
    }
    flat = _flatten_secret_values(mapping)
    assert flat["GEMINI_API_KEY"] == "g-test"
    assert flat["GROQ_API_KEY"] == "q-test"


def test_flatten_nested_secrets() -> None:
    mapping = {"gemini": {"api_key": "nested-g"}}
    flat = _flatten_secret_values(mapping)
    assert flat["GEMINI_API_KEY"] == "nested-g"


def test_apply_streamlit_secrets_sets_environ(monkeypatch) -> None:
    class FakeSecrets(dict):
        pass

    fake = FakeSecrets(GEMINI_API_KEY="from-cloud", GROQ_API_KEY="groq")

    class FakeStreamlit:
        secrets = fake

    monkeypatch.setitem(os.environ, "GEMINI_API_KEY", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "streamlit", FakeStreamlit())

    apply_streamlit_secrets_to_environ()
    assert os.environ["GEMINI_API_KEY"] == "from-cloud"
    assert os.environ["GROQ_API_KEY"] == "groq"
