"""Pydantic schemas for raw model JSON (validated before mapping to domain models)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from models.document import FieldReviewStatus


class ModelFieldOutput(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=128)
    value: str | None = None
    review_status: FieldReviewStatus = FieldReviewStatus.CONFIRMED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = Field(default=None, max_length=512)


class ModelLineItemOutput(BaseModel):
    mfg: str | None = None
    product_name: str | None = None
    pack: str | None = None
    exp: str | None = None
    batch: str | None = None
    qty: str | None = None
    free: str | None = None
    mrp: str | None = None
    rate: str | None = None
    amount: str | None = None
    gst_pct: str | None = None
    hsn: str | None = None


class ModelStructuringOutput(BaseModel):
    document_type: str = Field(default="general", max_length=64)
    fields: list[ModelFieldOutput] = Field(default_factory=list)
    line_items: list[ModelLineItemOutput] = Field(default_factory=list)
    model_notes: str | None = Field(default=None, max_length=2000)
