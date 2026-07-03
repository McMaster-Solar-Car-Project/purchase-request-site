import shutil
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.core.logging_utils import setup_logger
from src.core.settings import (
    EXCEL_ITEM_END_ROW,
    EXCEL_ITEM_ROW_COUNT,
    EXCEL_ITEM_START_ROW,
    MAX_ITEMS_PER_FORM,
    MIN_EXCEL_ITEM_ROWS,
)
from src.image_processing import insert_signature_at_cell
from src.models.submissions import Invoice
from src.models.user_info import SubmissionUserInfo

logger = setup_logger(__name__)


def _discard_partial_output(output_path: str) -> None:
    """Remove a partially-written output file; never raises."""
    try:
        Path(output_path).unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Failed to remove partial output {output_path}: {e}")


def create_expense_report(
    session_folder: str,
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
) -> bool:
    """Copy the expense report template to the session folder and populate with user data."""
    template_path = "src/excel_templates/expense_report_template.xlsx"
    if not Path(template_path).exists():
        logger.error(f"Expense report template not found: {template_path}")
        return False

    now = datetime.now()
    day = now.strftime("%d").lstrip("0")
    pascal_name = "".join(word.capitalize() for word in user_info.name.split())
    output_filename = f"{now.strftime('%B')}{day}-{now.strftime('%Y')}-ExpenseReport-{pascal_name}.xlsx"
    output_path = f"{session_folder}/{output_filename}"

    try:
        shutil.copy2(template_path, output_path)
        wb = load_workbook(output_path)
    except Exception:
        logger.exception("Failed to open expense report template")
        _discard_partial_output(output_path)
        return False

    try:
        ws = wb.active
        ws["C2"] = user_info.name
        ws["F2"] = now.strftime("%Y-%m-%d")
        ws["C3"] = user_info.email
        ws["F3"] = user_info.address

        populate_expense_rows_from_submitted_forms(ws, submitted_forms)

        try:
            insert_signature_at_cell(ws, session_folder, "A19", 200, 60)
        except Exception as e:
            logger.warning(f"Failed to insert signature into expense report: {e}")

        wb.save(output_path)
        return True
    except Exception:
        logger.exception("Failed to populate expense report")
        _discard_partial_output(output_path)
        return False
    finally:
        wb.close()


def populate_expense_rows_from_submitted_forms(
    ws: Worksheet, submitted_forms: list[Invoice]
) -> None:
    """Populate expense report rows from submitted form data."""
    current_date = datetime.now().strftime("%Y-%m-%d")

    for i, form in enumerate(submitted_forms):
        row = 6 + i  # starts at row 6 in excel
        ws[f"B{row}"] = current_date
        ws[f"C{row}"] = form.vendor_name

        if not form.is_usd:
            ws[f"F{row}"] = form.subtotal_amount - form.discount_amount
            ws[f"G{row}"] = form.total_cad_amount
            ws[f"H{row}"] = form.hst_gst_amount
        else:
            ws[f"D{row}"] = form.us_total
            ws[f"E{row}"] = form.exchange_rate
            ws[f"F{row}"] = form.total_cad_amount
            ws[f"G{row}"] = form.total_cad_amount
            ws[f"H{row}"] = 0


def _visible_excel_item_rows(item_count: int) -> int:
    if item_count > MAX_ITEMS_PER_FORM:
        raise ValueError(
            f"Purchase request has {item_count} items, "
            f"but the template supports at most {MAX_ITEMS_PER_FORM}"
        )
    return max(MIN_EXCEL_ITEM_ROWS, item_count)


def _hide_unused_item_rows(ws: Worksheet, item_count: int) -> None:
    visible_rows = _visible_excel_item_rows(item_count)
    first_hidden_row = EXCEL_ITEM_START_ROW + visible_rows

    for row in range(EXCEL_ITEM_START_ROW, EXCEL_ITEM_END_ROW + 1):
        ws.row_dimensions[row].hidden = row >= first_hidden_row


def _delete_unused_receipt_sheets(wb, submitted_forms: list[Invoice]) -> None:
    submitted_sheet_names = {f"Receipt{form.form_number}" for form in submitted_forms}

    for ws in list(wb.worksheets):
        if ws.title not in submitted_sheet_names:
            wb.remove(ws)


def create_purchase_request(
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
    session_folder: str,
) -> str:
    """Create Purchase Request using a template with one tab per submitted form."""
    template_path = "src/excel_templates/purchase_request_template.xlsx"
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    now = datetime.now()
    day = now.strftime("%d").lstrip("0")
    pascal_name = "".join(word.capitalize() for word in user_info.name.split())
    output_filename = f"{now.strftime('%B')}{day}-{now.strftime('%Y')}-PurchaseRequest-{pascal_name}.xlsx"
    output_path = f"{session_folder}/{output_filename}"
    shutil.copy2(template_path, output_path)
    wb = load_workbook(output_path)

    try:
        _delete_unused_receipt_sheets(wb, submitted_forms)

        for ws in wb.worksheets:
            _hide_unused_item_rows(ws, 0)

        for form in submitted_forms:
            tab_name = f"Receipt{form.form_number}"

            if tab_name not in wb.sheetnames:
                logger.warning(
                    f"Tab '{tab_name}' not found in template, skipping form {form.form_number}"
                )
                continue

            ws = wb[tab_name]
            if len(form.items) > EXCEL_ITEM_ROW_COUNT:
                raise ValueError(
                    f"Form {form.form_number} has {len(form.items)} items, "
                    f"but the template supports at most {EXCEL_ITEM_ROW_COUNT}"
                )
            _hide_unused_item_rows(ws, len(form.items))

            ws["B1"] = now.strftime("%Y-%m-%d")
            ws["D1"] = "USD" if form.is_usd else "CAD"
            ws["B3"] = user_info.name
            ws["D3"] = user_info.e_transfer_email
            ws["B4"] = user_info.team
            ws["B7"] = form.vendor_name
            ws["B67"] = user_info.address

            for i, item in enumerate(form.items):
                row = EXCEL_ITEM_START_ROW + i
                ws[f"B{row}"] = item.name
                ws[f"C{row}"] = item.usage
                ws[f"D{row}"] = item.quantity
                ws[f"E{row}"] = item.unit_price
                ws[f"F{row}"] = item.total

            ws["F59"] = form.us_subtotal if form.is_usd else form.subtotal_amount
            ws["F60"] = form.us_additional_fees if form.is_usd else form.hst_gst_amount
            ws["F61"] = form.us_total if form.is_usd else form.shipping_amount
            ws["F62"] = form.total_cad_amount

            if form.is_usd:
                ws["D7"] = round(form.exchange_rate, 4)

            insert_signature_at_cell(ws, session_folder, "B68", 280, 70)

        wb.save(output_path)
        return output_filename
    except Exception:
        _discard_partial_output(output_path)
        raise
    finally:
        wb.close()
