"""Map validated model output onto user extraction schemas."""

from __future__ import annotations

from models.document import (
    ExtractedFieldValue,
    ExtractionSchema,
    FieldReviewStatus,
    StructuredExtractionResult,
)
from models.pharmacy import PharmacyLineItem
from providers.response_models import ModelStructuringOutput
from utils.pharmacy_lines import line_items_from_model, parse_product_lines_text
from utils.schema_dynamic import is_dynamic_schema, map_dynamic_model_fields


def _clean_field_value(value: str | None) -> str | None:
    """Strip review labels accidentally placed in value by the model."""
    if value is None:
        return None
    text = value.strip()
    lowered = text.lower()
    for prefix in ("confirmed ", "uncertain ", "missing ", "user_edited "):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip() or None
    return text or None


def map_model_output_to_result(
    schema: ExtractionSchema,
    model_output: ModelStructuringOutput,
) -> StructuredExtractionResult:
    """Align model fields with schema keys; never invent values for missing keys."""
    if is_dynamic_schema(schema):
        merged = map_dynamic_model_fields(model_output.fields)
        line_items: list[PharmacyLineItem] = line_items_from_model(
            [item.model_dump() for item in model_output.line_items]
        )
        product_lines = next((f for f in merged if f.key == "product_lines"), None)
        if not line_items and product_lines and product_lines.value:
            line_items = parse_product_lines_text(product_lines.value)
        return StructuredExtractionResult(
            document_type=model_output.document_type or schema.name,
            fields=merged,
            line_items=line_items,
            raw_model_notes=model_output.model_notes,
        )

    returned = {field.key: field for field in model_output.fields}
    merged: list[ExtractedFieldValue] = []

    for definition in schema.fields:
        raw = returned.get(definition.key)
        if raw is None:
            merged.append(
                ExtractedFieldValue(
                    key=definition.key,
                    label=definition.label,
                    value=None,
                    review_status=FieldReviewStatus.MISSING,
                    notes="Not present in OCR text or model output.",
                )
            )
            continue

        merged.append(
            ExtractedFieldValue(
                key=definition.key,
                label=definition.label,
                value=_clean_field_value(raw.value),
                review_status=raw.review_status,
                confidence=raw.confidence,
                notes=raw.notes,
            )
        )

    line_items: list[PharmacyLineItem] = line_items_from_model(
        [item.model_dump() for item in model_output.line_items]
    )
    if not line_items and schema.name == "pharmacy_tax_invoice":
        product_lines = next((f for f in merged if f.key == "product_lines"), None)
        if product_lines and product_lines.value:
            line_items = parse_product_lines_text(product_lines.value)

    return StructuredExtractionResult(
        document_type=model_output.document_type or schema.name,
        fields=merged,
        line_items=line_items,
        raw_model_notes=model_output.model_notes,
    )
