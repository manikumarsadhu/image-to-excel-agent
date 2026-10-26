"""Dynamic schema and column label tests."""

from __future__ import annotations

from models.document import (
    DocumentProcessingState,
    ExtractionFieldDefinition,
    ExtractionSchema,
    ExtractedFieldValue,
    FieldReviewStatus,
    ProcessingStatus,
    SourceDocument,
    StructuredExtractionResult,
)
from providers.mapping import map_model_output_to_result
from providers.response_models import ModelFieldOutput, ModelStructuringOutput
from services.excel_service import build_column_headers
from utils.schema_dynamic import merge_extraction_schema_from_documents, normalize_field_key


def test_normalize_field_key() -> None:
    assert normalize_field_key("Invoice Number") == "invoice_number"
    assert normalize_field_key("123") is None


def test_dynamic_mapping_creates_columns() -> None:
    schema = ExtractionSchema(
        name="dynamic",
        fields=[ExtractionFieldDefinition(key="auto_placeholder", label="Auto")],
    )
    output = ModelStructuringOutput(
        fields=[
            ModelFieldOutput(
                key="supplier_name",
                label="Supplier",
                value="VMA",
                review_status=FieldReviewStatus.CONFIRMED,
            ),
            ModelFieldOutput(
                key="invoice_number",
                label="Invoice #",
                value="ZR1",
                review_status=FieldReviewStatus.CONFIRMED,
            ),
        ]
    )
    result = map_model_output_to_result(schema, output)
    assert len(result.fields) == 2
    assert result.field_map()["invoice_number"].label == "Invoice #"


def test_merge_schema_from_documents() -> None:
    schema = ExtractionSchema(
        name="dynamic",
        fields=[ExtractionFieldDefinition(key="auto_placeholder", label="Auto")],
    )
    doc = SourceDocument(
        source_filename="a.png",
        mime_type="image/png",
        file_size_bytes=10,
        status=ProcessingStatus.READY_FOR_EXPORT,
        extraction=StructuredExtractionResult(
            fields=[
                ExtractedFieldValue(
                    key="gstin",
                    label="GSTIN",
                    value="36AAA",
                    review_status=FieldReviewStatus.CONFIRMED,
                )
            ]
        ),
    )
    merged = merge_extraction_schema_from_documents(schema, [doc])
    assert [f.key for f in merged.fields] == ["gstin"]
    headers = build_column_headers(merged)
    assert "GSTIN" in headers


def test_sync_state_schema() -> None:
    from utils.schema_dynamic import sync_state_schema

    schema = ExtractionSchema(
        name="dynamic",
        fields=[ExtractionFieldDefinition(key="auto_placeholder", label="Auto")],
    )
    state = DocumentProcessingState(
        extraction_schema=schema,
        documents=[
            SourceDocument(
                source_filename="b.png",
                mime_type="image/png",
                file_size_bytes=10,
                status=ProcessingStatus.READY_FOR_EXPORT,
                extraction=StructuredExtractionResult(
                    fields=[
                        ExtractedFieldValue(
                            key="net_amount",
                            label="Net Amount",
                            value="100",
                            review_status=FieldReviewStatus.CONFIRMED,
                        )
                    ]
                ),
            )
        ],
    )
    sync_state_schema(state)
    assert state.extraction_schema is not None
    assert state.extraction_schema.fields[0].key == "net_amount"
