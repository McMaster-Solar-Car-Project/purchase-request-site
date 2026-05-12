"""Shared Pydantic models for purchase request submissions.

These models represent a validated submission payload used across the
dashboard router, data processing (Excel generation), Google Drive/Sheets
clients, and tests.
"""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _blank_to_zero(value: object) -> object:
    if value is None:
        return 0
    if isinstance(value, str) and not value.strip():
        return 0
    return value


NonNegFloat = Annotated[float, BeforeValidator(_blank_to_zero), Field(ge=0)]
PositiveInt = Annotated[int, BeforeValidator(_blank_to_zero), Field(gt=0)]


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    usage: str = Field(min_length=1)
    quantity: PositiveInt
    unit_price: NonNegFloat

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
    subtotal_amount: NonNegFloat
    discount_amount: NonNegFloat
    hst_gst_amount: NonNegFloat
    shipping_amount: NonNegFloat
    total_cad_amount: NonNegFloat
    us_subtotal: NonNegFloat
    us_additional_fees: NonNegFloat
    items: list[SubmissionLineItem] = Field(min_length=1)

    @property
    def us_total(self) -> float:
        """Total USD paid (subtotal plus any additional fees/taxes/tariffs)."""
        return self.us_subtotal + self.us_additional_fees
