"""Pharmacy invoice line-item models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PharmacyLineItem(BaseModel):
    """One product row from a wholesale pharmacy tax invoice."""

    model_config = ConfigDict(str_strip_whitespace=True)

    mfg: str | None = None
    product_name: str | None = Field(default=None, max_length=256)
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

    def is_empty(self) -> bool:
        return not any(
            v and str(v).strip()
            for v in (
                self.mfg,
                self.product_name,
                self.pack,
                self.exp,
                self.batch,
                self.qty,
                self.mrp,
                self.rate,
                self.amount,
            )
        )
