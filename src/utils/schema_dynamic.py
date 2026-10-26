"""Dynamic schema expansion and column label helpers."""

from __future__ import annotations

import re

from models.document import (
    DocumentProcessingState,
    ExtractionFieldDefinition,
    ExtractionSchema,
    ExtractedFieldValue,
    SourceDocument,
    StructuredExtractionResult,
)

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def is_dynamic_schema(schema: ExtractionSchema) -> bool:
    return schema.name == "dynamic"


def is_exportable_field_key(key: str) -> bool:
    return key != "auto_placeholder"


def normalize_field_key(raw: str) -> str | None:
    text = raw.strip().lower().replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text or not _KEY_PATTERN.match(text):
        return None
    return text[:64]


def default_label_for_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def merge_extraction_schema_from_documents(
    schema: ExtractionSchema,
    documents: list[SourceDocument],
) -> ExtractionSchema:
    """Union field keys from extractions into the working schema (order preserved)."""
    ordered_keys: list[str] = []
    definitions: dict[str, ExtractionFieldDefinition] = {}

    for field in schema.fields:
        if field.key == "auto_placeholder":
            continue
        if field.key not in definitions:
            ordered_keys.append(field.key)
            definitions[field.key] = field

    for document in documents:
        if document.extraction is None:
            continue
        for extracted in document.extraction.fields:
            key = extracted.key
            if not is_exportable_field_key(key):
                continue
            if key not in definitions:
                ordered_keys.append(key)
                definitions[key] = ExtractionFieldDefinition(
                    key=key,
                    label=extracted.label or default_label_for_key(key),
                )
            elif extracted.label and definitions[key].label != extracted.label:
                # Prefer schema label already edited by user; sync extraction display label
                pass

    if not ordered_keys and is_dynamic_schema(schema):
        ordered_keys = ["document_notes"]
        definitions["document_notes"] = ExtractionFieldDefinition(
            key="document_notes",
            label="Document notes",
            description="Fallback when no fields were extracted",
        )

    return schema.model_copy(update={"fields": [definitions[k] for k in ordered_keys]})


def apply_schema_labels_to_extractions(
    schema: ExtractionSchema,
    documents: list[SourceDocument],
) -> None:
    """Sync each document's field labels from the schema (after user edits headings)."""
    label_by_key = {f.key: f.label for f in schema.fields}
    for document in documents:
        if document.extraction is None:
            continue
        updated_fields: list[ExtractedFieldValue] = []
        for field in document.extraction.fields:
            label = label_by_key.get(field.key, field.label)
            updated_fields.append(field.model_copy(update={"label": label}))
        document.extraction = document.extraction.model_copy(update={"fields": updated_fields})


def update_schema_field_labels(
    schema: ExtractionSchema,
    labels: dict[str, str],
) -> ExtractionSchema:
    updated: list[ExtractionFieldDefinition] = []
    for field in schema.fields:
        new_label = labels.get(field.key)
        if new_label and new_label.strip():
            updated.append(field.model_copy(update={"label": new_label.strip()[:128]}))
        else:
            updated.append(field)
    return schema.model_copy(update={"fields": updated})


def sync_state_schema(state: DocumentProcessingState) -> None:
    if state.extraction_schema is None:
        return
    state.extraction_schema = merge_extraction_schema_from_documents(
        state.extraction_schema,
        state.documents,
    )
    apply_schema_labels_to_extractions(state.extraction_schema, state.documents)


def map_dynamic_model_fields(raw_fields: list) -> list[ExtractedFieldValue]:
    """Build extracted fields from all model outputs (dynamic preset)."""
    from providers.mapping import _clean_field_value
    from providers.response_models import ModelFieldOutput

    merged: list[ExtractedFieldValue] = []
    seen: set[str] = set()
    for item in raw_fields:
        if not isinstance(item, ModelFieldOutput):
            continue
        key = normalize_field_key(item.key)
        if key is None or key in seen:
            continue
        seen.add(key)
        label = (item.label or "").strip() or default_label_for_key(key)
        merged.append(
            ExtractedFieldValue(
                key=key,
                label=label[:128],
                value=_clean_field_value(item.value),
                review_status=item.review_status,
                confidence=item.confidence,
                notes=item.notes,
            )
        )
    return merged
