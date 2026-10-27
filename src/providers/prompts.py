"""Prompt templates for structuring (text-only input)."""

from __future__ import annotations

import json

from providers.base import StructuringContext
from utils.schema_dynamic import is_exportable_field_key


def build_structuring_prompt(context: StructuringContext) -> tuple[str, str]:
    schema = context.schema
    field_specs = []
    for field in schema.fields:
        if not is_exportable_field_key(field.key):
            continue
        spec: dict[str, object] = {
            "key": field.key,
            "label": field.label,
            "required": field.required,
        }
        if field.description:
            spec["description"] = field.description
        if field.examples:
            spec["examples"] = field.examples
        field_specs.append(spec)

    table_hint = ""
    if schema.name == "dynamic":
        table_hint = (
            "- Infer columns from the document (invoice, form, receipt, ID, etc.).\n"
            "- Return one fields[] entry per distinct data column you extract.\n"
            "- Use snake_case key and a short human label (Excel column title).\n"
            "- Only include fields clearly supported by OCR text.\n"
        )
        field_specs = []
    elif schema.name == "pharmacy_tax_invoice":
        table_hint = (
            "- This is a pharmacy wholesale tax invoice with multiple medicine product rows.\n"
            "- Put every single product table row in product_lines: one line per medicine, columns "
            "separated by | (mfg | product_name | pack | exp | batch | qty | free | mrp | "
            "rate | amount | gst_pct | hsn).\n"
            "- Separate each medicine with a newline (\\n). Do NOT omit any medicine rows.\n"
        )

    system = (
        "You extract structured data from OCR text of scanned documents. "
        "Rules:\n"
        f"{table_hint}"
        "- Use ONLY the provided OCR text; do not guess or use outside knowledge.\n"
        "- If a value is not clearly supported by the OCR text, set value to null and "
        "review_status to \"missing\" or \"uncertain\".\n"
        "- Never invent amounts, dates, names, or IDs.\n"
        "- Return JSON matching the response schema exactly.\n"
        "- Include one object per extracted column in the fields array "
        "(each with key, label, value, review_status).\n"
        "- review_status must be one of: confirmed, uncertain, missing.\n"
        "- Put only the extracted text in value; never prefix value with review_status.\n"
    )

    user_payload = {
        "task": "structure_ocr_text",
        "document_schema": schema.name,
        "schema_description": schema.description,
        "fields": field_specs,
        "source_filename": context.source_filename,
        "ocr_text": context.ocr_text,
    }
    user = json.dumps(user_payload, ensure_ascii=False, indent=2)
    return system, user
