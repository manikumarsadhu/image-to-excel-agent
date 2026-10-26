"""Built-in extraction schemas for common document types."""

from __future__ import annotations

from models.document import ExtractionFieldDefinition, ExtractionSchema

PRESET_RECEIPT = ExtractionSchema(
    name="receipt",
    description="Retail or restaurant receipt",
    fields=[
        ExtractionFieldDefinition(
            key="vendor",
            label="Vendor",
            description="Store or business name",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="date",
            label="Date",
            description="Transaction date if visible",
        ),
        ExtractionFieldDefinition(
            key="total",
            label="Total amount",
            description="Final total paid",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="currency",
            label="Currency",
            description="ISO or symbol if shown",
        ),
    ],
)

PRESET_APPLICATION = ExtractionSchema(
    name="application",
    description="Form or application",
    fields=[
        ExtractionFieldDefinition(
            key="full_name",
            label="Full name",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="email",
            label="Email",
        ),
        ExtractionFieldDefinition(
            key="phone",
            label="Phone",
        ),
        ExtractionFieldDefinition(
            key="address",
            label="Address",
        ),
    ],
)

PRESET_PHARMACY_RECEIPT = ExtractionSchema(
    name="pharmacy_receipt",
    description="Pharmacy or medical store bill / receipt",
    fields=[
        ExtractionFieldDefinition(
            key="pharmacy_name",
            label="Pharmacy name",
            description="Medical store or pharmacy business name",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="invoice_number",
            label="Invoice / bill number",
            description="Receipt or invoice ID printed on the bill",
        ),
        ExtractionFieldDefinition(
            key="receipt_date",
            label="Receipt date",
            description="Date on the receipt (as printed)",
        ),
        ExtractionFieldDefinition(
            key="patient_name",
            label="Patient / customer name",
            description="Only if clearly printed; do not guess",
        ),
        ExtractionFieldDefinition(
            key="prescriber_name",
            label="Doctor / prescriber",
            description="Prescribing doctor if shown",
        ),
        ExtractionFieldDefinition(
            key="medicines",
            label="Medicines (line summary)",
            description=(
                "All medicine lines as one text block: name, strength, qty, rate "
                "when visible (e.g. 'Paracetamol 500mg tab x10 @ 12.00')"
            ),
            required=True,
        ),
        ExtractionFieldDefinition(
            key="subtotal",
            label="Subtotal",
            description="Amount before tax/discount if shown",
        ),
        ExtractionFieldDefinition(
            key="discount",
            label="Discount",
            description="Discount amount if shown",
        ),
        ExtractionFieldDefinition(
            key="tax_gst",
            label="Tax / GST",
            description="Tax or GST amount if shown",
        ),
        ExtractionFieldDefinition(
            key="total_amount",
            label="Total paid",
            description="Final amount paid or net payable",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="payment_mode",
            label="Payment mode",
            description="Cash, UPI, card, etc. if shown",
        ),
    ],
)

PRESET_PHARMACY_WHOLESALE_INVOICE = ExtractionSchema(
    name="pharmacy_tax_invoice",
    description="Pharmacy / medical wholesale tax invoice with product table",
    fields=[
        ExtractionFieldDefinition(
            key="supplier_name",
            label="Supplier / pharmacy name",
            description="Seller name on tax invoice header",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="gstin",
            label="GSTIN",
            description="Supplier GSTIN if printed",
        ),
        ExtractionFieldDefinition(
            key="invoice_number",
            label="Invoice number",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="invoice_date",
            label="Invoice date",
            description="Date as printed on invoice",
        ),
        ExtractionFieldDefinition(
            key="billed_to",
            label="Billed to",
            description="Customer / party name and place",
        ),
        ExtractionFieldDefinition(
            key="product_lines",
            label="Product lines",
            description=(
                "One line per product row from the table. Include columns when visible: "
                "mfg | product_name | pack | exp | batch | qty | free | mrp | rate | "
                "amount | gst_pct | hsn. Use | as separator within a line."
            ),
            required=True,
        ),
        ExtractionFieldDefinition(
            key="subtotal",
            label="Subtotal",
        ),
        ExtractionFieldDefinition(
            key="discount",
            label="Less discount",
        ),
        ExtractionFieldDefinition(
            key="gst_amount",
            label="GST amount",
        ),
        ExtractionFieldDefinition(
            key="rounding",
            label="Rounding",
        ),
        ExtractionFieldDefinition(
            key="net_amount",
            label="Net amount",
            required=True,
        ),
        ExtractionFieldDefinition(
            key="total_items",
            label="Total items",
            description="Count of distinct product lines if shown",
        ),
        ExtractionFieldDefinition(
            key="total_units",
            label="Total units",
            description="Sum of quantities if shown",
        ),
    ],
)

PRESET_GENERAL = ExtractionSchema(
    name="general",
    description="General document",
    fields=[
        ExtractionFieldDefinition(
            key="title",
            label="Title",
            description="Main heading or subject",
        ),
        ExtractionFieldDefinition(
            key="reference_id",
            label="Reference ID",
            description="Invoice, ticket, or reference number",
        ),
        ExtractionFieldDefinition(
            key="summary",
            label="Summary",
            description="Short summary of key content",
        ),
    ],
)

SCHEMA_PRESETS: dict[str, ExtractionSchema] = {
    "Pharmacy tax invoice (wholesale)": PRESET_PHARMACY_WHOLESALE_INVOICE,
    "Pharmacy receipt": PRESET_PHARMACY_RECEIPT,
    "Receipt": PRESET_RECEIPT,
    "Application form": PRESET_APPLICATION,
    "General document": PRESET_GENERAL,
}


def get_preset(name: str) -> ExtractionSchema:
    return SCHEMA_PRESETS[name].model_copy(deep=True)
