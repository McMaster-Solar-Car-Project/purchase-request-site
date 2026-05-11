"""Shared Pydantic models for purchase request submissions.

These models represent a validated submission payload used across the
dashboard router, data processing (Excel generation), Google Drive/Sheets
clients, and tests.
"""

from pydantic import BaseModel, ConfigDict, Field


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    usage: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)

    @property
    def total(self) -> float:
        return self.unit_price * self.quantity


class Invoice(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    form_number: int = Field(ge=1)
    vendor_name: str = Field(min_length=1)
    is_usd: bool
    invoice_filename: str = Field(min_length=1)
    invoice_file_location: str = Field(min_length=1)
    proof_of_payment_filename: str | None = None
    proof_of_payment_location: str | None = None
    subtotal_amount: float = Field(ge=0)
    discount_amount: float = Field(ge=0)
    hst_gst_amount: float = Field(ge=0)
    shipping_amount: float = Field(ge=0)
    total_cad_amount: float = Field(ge=0)
    us_subtotal: float = Field(ge=0)
    us_additional_fees: float = Field(ge=0)
    items: list[SubmissionLineItem] = Field(min_length=1)

    @property
    def us_total(self) -> float:
        """Total USD paid (subtotal plus any additional fees/taxes/tariffs)."""
        return self.us_subtotal + self.us_additional_fees
