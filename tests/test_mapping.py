"""Provider mapping tests."""

from __future__ import annotations

from models.document import ExtractionFieldDefinition, ExtractionSchema, FieldReviewStatus
from providers.mapping import map_model_output_to_result
from providers.response_models import ModelFieldOutput, ModelStructuringOutput


def test_strips_confirmed_prefix_from_values() -> None:
    schema = ExtractionSchema(
        name="pharmacy_tax_invoice",
        fields=[ExtractionFieldDefinition(key="supplier_name", label="Supplier")],
    )
    output = ModelStructuringOutput(
        fields=[
            ModelFieldOutput(
                key="supplier_name",
                value="confirmed VENKATESHWARA",
                review_status=FieldReviewStatus.CONFIRMED,
            )
        ]
    )
    result = map_model_output_to_result(schema, output)
    assert result.field_map()["supplier_name"].value == "VENKATESHWARA"
    assert result.field_map()["supplier_name"].review_status == FieldReviewStatus.CONFIRMED
