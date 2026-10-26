"""Parse pharmacy product line text into structured rows."""

from __future__ import annotations

from models.pharmacy import PharmacyLineItem

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
    data = dict(zip(_LINE_KEYS, parts, strict=False))
    item = PharmacyLineItem.model_validate(data)
    if item.is_empty():
        return None
    return item


def parse_product_lines_text(text: str | None) -> list[PharmacyLineItem]:
    """
    Parse product_lines field: one row per line, columns separated by |.

    Also accepts rows with fewer columns (mapped left-to-right).
    """
    if not text or not text.strip():
        return []
    items: list[PharmacyLineItem] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
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
