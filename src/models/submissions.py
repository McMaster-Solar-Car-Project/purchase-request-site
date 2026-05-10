"""Shared Pydantic models for purchase request submissions.

These models represent a validated submission payload used across the
dashboard router, data processing (Excel generation), Google Drive/Sheets
clients, and tests.
"""

from pydantic import BaseModel, ConfigDict


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    usage: str
    quantity: int
    unit_price: float

    @property
    def total(self) -> float:
        return self.unit_price * self.quantity


class Invoice(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    form_number: int
    vendor_name: str
    is_usd: bool
    invoice_filename: str
    invoice_file_location: str
    proof_of_payment_filename: str | None = None
    proof_of_payment_location: str | None = None
    subtotal_amount: float
    discount_amount: float
    hst_gst_amount: float
    shipping_amount: float
    total_cad_amount: float
    us_subtotal: float
    us_additional_fees: float
    items: list[SubmissionLineItem]

    @property
    def us_total(self) -> float:
        """Total USD paid (subtotal plus any additional fees/taxes/tariffs)."""
        return self.us_subtotal + self.us_additional_fees
