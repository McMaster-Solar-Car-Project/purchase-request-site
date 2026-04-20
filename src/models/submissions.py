"""Shared Pydantic models for purchase request submissions.

These models represent a validated submission payload used across the
dashboard router, data processing (Excel generation), Google Drive/Sheets
clients, and tests.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    usage: str
    quantity: int
    unit_price: float
    total: float


class SubmissionForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    form_number: int
    vendor_name: str
    currency: Literal["CAD", "USD"]
    invoice_filename: str
    invoice_file_location: str
    proof_of_payment_filename: str | None = None
    proof_of_payment_location: str | None = None
    subtotal_amount: float
    discount_amount: float
    hst_gst_amount: float
    shipping_amount: float
    total_amount: float
    us_total: float
    usd_taxes: float
    canadian_amount: float
    items: list[SubmissionLineItem]


class SubmissionUserInfo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: str
    e_transfer_email: str
    address: str
    team: str
    signature: str
