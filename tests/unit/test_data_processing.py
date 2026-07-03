import re

import pytest
from openpyxl import Workbook, load_workbook

import src.data_processing as data_processing
from src.core.settings import EXCEL_ITEM_END_ROW, EXCEL_ITEM_START_ROW
from src.models.submissions import Invoice, SubmissionLineItem
from src.models.user_info import SubmissionUserInfo


def _make_form(**overrides) -> Invoice:
    """Build an Invoice with sensible defaults for tests."""
    defaults = {
        "form_number": 1,
        "vendor_name": "Vendor",
        "is_usd": False,
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
        "items": [
            SubmissionLineItem(name="Item", usage="Test", quantity=1, unit_price=1.0)
        ],
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def _make_user_info() -> SubmissionUserInfo:
    return SubmissionUserInfo(
        name="Test User",
        email="test@example.com",
        e_transfer_email="transfer@example.com",
        address="123 Main St",
        team="Software",
        signature="signature.png",
    )


def _make_items(count: int) -> list[SubmissionLineItem]:
    return [
        SubmissionLineItem(
            name=f"Item {item_number}",
            usage=f"Usage {item_number}",
            quantity=item_number,
            unit_price=1.25,
        )
        for item_number in range(1, count + 1)
    ]


def test_populate_expense_rows_supports_cad_and_usd() -> None:
    wb = Workbook()
    ws = wb.active

    submitted_forms = [
        _make_form(
            form_number=1,
            vendor_name="CAD Vendor",
            is_usd=False,
            subtotal_amount=120.0,
            discount_amount=20.0,
            total_cad_amount=113.0,
            hst_gst_amount=13.0,
        ),
        _make_form(
            form_number=2,
            vendor_name="USD Vendor",
            is_usd=True,
            proof_of_payment_filename="proof.pdf",
            proof_of_payment_location="/tmp/proof.pdf",
            us_subtotal=80.0,
            us_additional_fees=20.0,
            total_cad_amount=135.0,
        ),
    ]

    data_processing.populate_expense_rows_from_submitted_forms(ws, submitted_forms)

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


@pytest.mark.parametrize(
    ("item_count", "expected_hidden_start"),
    [
        (1, 24),
        (15, 24),
        (30, 39),
        (50, None),
    ],
)
def test_create_purchase_request_supports_fifty_item_template_rows(
    monkeypatch, tmp_path, item_count: int, expected_hidden_start: int | None
) -> None:
    signature_calls: list[tuple[str, str, int, int]] = []

    def fake_insert_signature_at_cell(
        ws, _session_folder: str, cell_location: str, width: int, height: int
    ) -> bool:
        signature_calls.append((ws.title, cell_location, width, height))
        return True

    monkeypatch.setattr(
        data_processing, "insert_signature_at_cell", fake_insert_signature_at_cell
    )

    items = _make_items(item_count)
    output_filename = data_processing.create_purchase_request(
        _make_user_info(),
        [
            _make_form(
                items=items,
                subtotal_amount=125.0,
                hst_gst_amount=16.25,
                shipping_amount=10.0,
                total_cad_amount=151.25,
            )
        ],
        str(tmp_path),
    )

    assert re.fullmatch(
        r"[A-Z][a-z]+[1-9][0-9]?-\d{4}-PurchaseRequest-TestUser\.xlsx",
        output_filename,
    )
    assert not (tmp_path / "purchase_request.xlsx").exists()

    wb = load_workbook(tmp_path / output_filename)
    try:
        assert wb.sheetnames == ["Receipt1"]
        ws = wb["Receipt1"]
        assert ws["B67"].value == "123 Main St"
        assert ws["F59"].value == 125.0
        assert ws["F60"].value == 16.25
        assert ws["F61"].value == 10.0
        assert ws["F62"].value == 151.25

        for index, item in enumerate(items, start=EXCEL_ITEM_START_ROW):
            assert ws[f"B{index}"].value == item.name
            assert ws[f"C{index}"].value == item.usage
            assert ws[f"D{index}"].value == item.quantity
            assert ws[f"E{index}"].value == item.unit_price
            assert ws[f"F{index}"].value == item.total

        for row in range(EXCEL_ITEM_START_ROW, EXCEL_ITEM_END_ROW + 1):
            expected_hidden = (
                expected_hidden_start is not None and row >= expected_hidden_start
            )
            assert ws.row_dimensions[row].hidden is expected_hidden

    finally:
        wb.close()

    assert signature_calls == [("Receipt1", "B68", 280, 70)]


def test_create_purchase_request_deletes_unsubmitted_receipt_sheets(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        data_processing,
        "insert_signature_at_cell",
        lambda *_args, **_kwargs: True,
    )

    output_filename = data_processing.create_purchase_request(
        _make_user_info(),
        [
            _make_form(
                form_number=1,
                vendor_name="First Vendor",
                items=_make_items(1),
            ),
            _make_form(
                form_number=3,
                vendor_name="Third Vendor",
                items=_make_items(2),
            ),
        ],
        str(tmp_path),
    )

    wb = load_workbook(tmp_path / output_filename)
    try:
        assert wb.sheetnames == ["Receipt1", "Receipt3"]
        assert wb["Receipt1"]["B7"].value == "First Vendor"
        assert wb["Receipt3"]["B7"].value == "Third Vendor"
    finally:
        wb.close()
