"""Parse pharmacy product line text into structured rows."""

from __future__ import annotations

from models.pharmacy import PharmacyLineItem

import ast
import json
import re

_LINE_KEYS = (
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


def _row_from_parts(parts: list[str]) -> PharmacyLineItem | None:
    cleaned = [p.strip().strip("'\"").strip() for p in parts]
    data = dict(zip(_LINE_KEYS, cleaned, strict=False))
    item = PharmacyLineItem.model_validate(data)
    if item.is_empty():
        return None
    return item


def _split_into_raw_lines(text: str) -> list[str]:
    raw = text.strip()
    if (raw.startswith("[") and raw.endswith("]")) or (raw.startswith("(") and raw.endswith(")")):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")

    lines = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[\s\-*•\d\.\)]+", "", line).strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def parse_product_lines_text(text: str | None) -> list[PharmacyLineItem]:
    """
    Parse product_lines field: one row per line, columns separated by |.

    Accepts newline-separated text, serialized list/array strings, and rows with fewer columns.
    """
    if not text or not text.strip():
        return []
    items: list[PharmacyLineItem] = []
    raw_lines = _split_into_raw_lines(text)
    for line in raw_lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 1 and "," in line:
            parts = [p.strip() for p in line.split(",")]
        item = _row_from_parts(parts)
        if item is not None:
            items.append(item)
    return items


def line_items_from_model(raw_items: list[object]) -> list[PharmacyLineItem]:
    parsed: list[PharmacyLineItem] = []
    for raw in raw_items:
        if isinstance(raw, PharmacyLineItem):
            parsed.append(raw)
            continue
        item = PharmacyLineItem.model_validate(raw)
        if not item.is_empty():
            parsed.append(item)
    return parsed
