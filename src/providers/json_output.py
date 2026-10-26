"""Shared JSON parsing for structured model responses."""

from __future__ import annotations

import json
import re
from typing import Any

from providers.base import ProviderInvalidRequestError
from providers.response_models import ModelStructuringOutput

_VALID_REVIEW = frozenset({"confirmed", "uncertain", "missing", "user_edited"})


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).strip()
    return text or None


def _sanitize_fields(raw_fields: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_fields, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key or not str(key).strip():
            continue
        review = str(item.get("review_status", "confirmed")).strip().lower()
        if review not in _VALID_REVIEW:
            review = "uncertain"
        field: dict[str, Any] = {
            "key": str(key).strip(),
            "value": _coerce_optional_str(item.get("value")),
            "review_status": review,
        }
        conf = item.get("confidence")
        if isinstance(conf, (int, float)):
            field["confidence"] = max(0.0, min(1.0, float(conf)))
        notes = _coerce_optional_str(item.get("notes"))
        if notes is not None:
            field["notes"] = notes
        cleaned.append(field)
    return cleaned


def _sanitize_line_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    keys = (
        "mfg",
        "product_name",
        "pack",
        "exp",
        "batch",
        "qty",
        "free",
        "mrp",
        "rate",
        "amount",
        "gst_pct",
        "hsn",
    )
    cleaned: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        row = {k: _coerce_optional_str(item.get(k)) for k in keys}
        if any(row.values()):
            cleaned.append(row)
    return cleaned


def sanitize_structuring_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize model JSON before Pydantic validation."""
    out: dict[str, Any] = {
        "fields": _sanitize_fields(payload.get("fields")),
    }
    doc_type = payload.get("document_type")
    if doc_type is not None:
        out["document_type"] = str(doc_type)
    notes = _coerce_optional_str(payload.get("model_notes"))
    if notes is not None:
        out["model_notes"] = notes
    line_items = _sanitize_line_items(payload.get("line_items"))
    if line_items:
        out["line_items"] = line_items
    return out


def parse_model_json(raw: str) -> ModelStructuringOutput:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderInvalidRequestError("Model returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderInvalidRequestError("Model JSON must be an object.")
    try:
        return ModelStructuringOutput.model_validate(sanitize_structuring_payload(payload))
    except Exception as exc:
        raise ProviderInvalidRequestError("Model JSON failed validation.") from exc
