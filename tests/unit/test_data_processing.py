from openpyxl import Workbook

from src.data_processing import populate_expense_rows_from_submitted_forms
from src.models.submissions import Invoice


def _make_form(**overrides) -> Invoice:
    """Build an Invoice with sensible defaults for tests."""
    defaults = {
        "form_number": 1,
        "vendor_name": "Vendor",
        "currency": "CAD",
        "invoice_filename": "invoice.pdf",
        "invoice_file_location": "/tmp/invoice.pdf",
        "proof_of_payment_filename": None,
        "proof_of_payment_location": None,
        "subtotal_amount": 0.0,
        "discount_amount": 0.0,
        "hst_gst_amount": 0.0,
        "shipping_amount": 0.0,
        "total_cad_amount": 0.0,
        "us_subtotal": 0.0,
        "us_additional_fees": 0.0,
        "items": [],
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def test_populate_expense_rows_supports_cad_and_usd() -> None:
    wb = Workbook()
    ws = wb.active

    submitted_forms = [
        _make_form(
            form_number=1,
            vendor_name="CAD Vendor",
            currency="CAD",
            subtotal_amount=120.0,
            discount_amount=20.0,
            total_cad_amount=113.0,
            hst_gst_amount=13.0,
        ),
        _make_form(
            form_number=2,
            vendor_name="USD Vendor",
            currency="USD",
            us_subtotal=80.0,
            us_additional_fees=20.0,
            total_cad_amount=135.0,
        ),
    ]

    ok = populate_expense_rows_from_submitted_forms(ws, submitted_forms)
    assert ok is True

    # First row (CAD) starts at row 6.
    assert ws["C6"].value == "CAD Vendor"
    assert ws["F6"].value == 100.0  # subtotal - discount
    assert ws["G6"].value == 113.0
    assert ws["H6"].value == 13.0

    # Second row (USD) is row 7.
    assert ws["C7"].value == "USD Vendor"
    assert ws["D7"].value == 100.0  # US total
    assert ws["E7"].value == 1.35  # Exchange rate
    assert ws["F7"].value == 135.0  # Total amount in CAD
    assert ws["G7"].value == 135.0  # Total amount in CAD
    assert ws["H7"].value == 0  # No HST for US
