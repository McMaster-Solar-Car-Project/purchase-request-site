from openpyxl import Workbook

from src.data_processing import populate_expense_rows_from_submitted_forms


def test_populate_expense_rows_supports_cad_and_usd() -> None:
    wb = Workbook()
    ws = wb.active

    submitted_forms = [
        {
            "form_number": 1,
            "vendor_name": "CAD Vendor",
            "currency": "CAD",
            "subtotal_amount": 120.0,
            "discount_amount": 20.0,
            "total_amount": 113.0,
            "hst_gst_amount": 13.0,
        },
        {
            "form_number": 2,
            "vendor_name": "USD Vendor",
            "currency": "USD",
            "us_total": 100.0,
            "canadian_amount": 135.0,
        },
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
    assert ws["D7"].value == 100.0
    assert ws["E7"].value == 1.35
    assert ws["F7"].value == 135.0
    assert ws["G7"].value == 135.0
    assert ws["H7"].value == 0
