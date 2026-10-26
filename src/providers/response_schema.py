"""JSON Schema for provider structured output (Groq/Gemini-compatible subset)."""

from __future__ import annotations

from typing import Any


def build_structuring_json_schema() -> dict[str, Any]:
    """
    Provider-facing schema: flat, no $ref/$defs, no line_items.

    Line items are parsed from the product_lines field after mapping.
    """
    return {
        "type": "object",
        "properties": {
            "document_type": {"type": "string"},
            "model_notes": {"type": "string"},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                        "review_status": {
                            "type": "string",
                            "enum": ["confirmed", "uncertain", "missing"],
                        },
                        "confidence": {"type": "number"},
                        "notes": {"type": "string"},
                    },
                    "required": ["key"],
                },
            },
        },
        "required": ["fields"],
    }
