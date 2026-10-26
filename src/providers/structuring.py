"""Shared structuring flow for JSON-capable providers."""

from __future__ import annotations

from typing import Callable

from models.document import StructuredExtractionResult
from providers.base import ProviderInvalidRequestError, StructuringContext
from providers.json_output import parse_model_json
from providers.mapping import map_model_output_to_result
from providers.prompts import build_structuring_prompt
from providers.response_schema import build_structuring_json_schema


GenerateJsonFn = Callable[[str, str, dict], str]


def structure_with_json_generator(
    context: StructuringContext,
    generate_json: GenerateJsonFn,
) -> StructuredExtractionResult:
    if not context.ocr_text or not context.ocr_text.strip():
        raise ProviderInvalidRequestError("OCR text is empty; nothing to structure.")

    system, user = build_structuring_prompt(context)
    schema = build_structuring_json_schema()
    raw = generate_json(system, user, schema)
    model_output = parse_model_json(raw)
    return map_model_output_to_result(context.schema, model_output)
