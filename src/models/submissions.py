"""Shared Pydantic models for purchase request submissions.

These models represent a validated submission payload used across the
dashboard router, data processing (Excel generation), Google Drive/Sheets
clients, and tests.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _blank_to_zero(value: object) -> object:
    if value is None:
        return 0
    if isinstance(value, str) and not value.strip():
        return 0
    return value


NonNegDecimal = Annotated[
    Decimal,
    BeforeValidator(_blank_to_zero),
    Field(ge=0, max_digits=16, decimal_places=8),
]
PositiveInt = Annotated[int, BeforeValidator(_blank_to_zero), Field(gt=0)]


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    usage: str = Field(min_length=1)
    quantity: PositiveInt
    unit_price: NonNegDecimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


class Invoice(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    form_number: int = Field(ge=1)
    vendor_name: str = Field(min_length=1)
    purchase_date: date
    is_usd: bool
    invoice_filename: str = Field(min_length=1)
    invoice_file_location: str = Field(min_length=1)
    proof_of_payment_filename: str | None = None
    proof_of_payment_location: str | None = None
    subtotal_amount: NonNegDecimal
    discount_amount: NonNegDecimal
    hst_gst_amount: NonNegDecimal
    shipping_amount: NonNegDecimal
    total_cad_amount: NonNegDecimal
    us_subtotal: NonNegDecimal
    us_additional_fees: NonNegDecimal
    items: list[SubmissionLineItem] = Field(min_length=1)

    @field_validator("purchase_date")
    @classmethod
    def purchase_date_cannot_be_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Purchase date cannot be in the future")
        return value

    @property
    def us_total(self) -> Decimal:
        """Total USD paid (subtotal plus any additional fees/taxes/tariffs)."""
        return self.us_subtotal + self.us_additional_fees

    @property
    def exchange_rate(self) -> Decimal:
        if self.us_total <= 0 or self.total_cad_amount <= 0:
            return Decimal(0)
        return self.total_cad_amount / self.us_total
