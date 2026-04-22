import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.core.logging_utils import setup_logger
from src.image_processing import insert_signature_at_cell
from src.models.submissions import Invoice
from src.models.user_info import SubmissionUserInfo

logger = setup_logger(__name__)


def create_expense_report(
    session_folder: str,
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
) -> bool:
    """Copy the expense report template to the session folder and populate with user data"""

    template_path = "src/excel_templates/expense_report_template.xlsx"

    if not Path(template_path).exists():
        logger.exception(f"Expense report template not found: {template_path}")
        return False

    try:
        # Build output filename: MonthDay-Year-ExpenseReport-FullName
        now = datetime.now()
        month_name = now.strftime("%B")
        day = now.strftime("%d").lstrip("0")
        year = now.strftime("%Y")
        today = now.strftime("%Y-%m-%d")
        pascal_name = "".join(word.capitalize() for word in user_info.name.split())

        output_filename = f"{month_name}{day}-{year}-ExpenseReport-{pascal_name}.xlsx"
        output_path = f"{session_folder}/{output_filename}"

        shutil.copy2(template_path, output_path)

        wb = load_workbook(output_path)
        ws = wb.active

        # Header section
        ws["C2"] = user_info.name
        ws["F2"] = today
        ws["C3"] = user_info.email
        ws["F3"] = user_info.address

        try:
            populate_expense_rows_from_submitted_forms(ws, submitted_forms)
        except Exception as e:
            logger.exception(
                f"Failed to populate expense rows from submitted forms: {e}"
            )

        try:
            insert_signature_at_cell(ws, session_folder, "A19", 200, 60)
        except Exception as e:
            logger.warning(f"Failed to insert signature into expense report: {e}")

        wb.save(output_path)
        wb.close()

        return True

    except Exception as e:
        logger.exception(f"Failed to copy and populate expense report template: {e}")
        return False


def populate_expense_rows_from_submitted_forms(
    ws: Worksheet, submitted_forms: list[Invoice]
) -> bool:
    """Populate expense report rows from submitted form data"""

    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        start_row = 6

        for i, form in enumerate(submitted_forms):
            row = start_row + i

            subtotal_after_discount = form.subtotal_amount - form.discount_amount

            ws[f"B{row}"] = current_date
            ws[f"C{row}"] = form.vendor_name

            if form.currency == "CAD":
                ws[f"F{row}"] = subtotal_after_discount
                ws[f"G{row}"] = form.total_cad_amount
                ws[f"H{row}"] = form.hst_gst_amount
            else:
                exchange_rate = (
                    form.total_cad_amount / form.us_total
                    if form.us_total > 0 and form.total_cad_amount > 0
                    else 0
                )
                ws[f"D{row}"] = form.us_total
                ws[f"E{row}"] = exchange_rate
                ws[f"F{row}"] = form.total_cad_amount
                ws[f"G{row}"] = form.total_cad_amount
                ws[f"H{row}"] = 0

        return True

    except Exception as e:
        logger.exception(f"Error populating expense rows: {e}")
        return False


def create_purchase_request(
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
    session_folder: str,
) -> dict[str, Any]:
    """Create Purchase Request using the template with multiple tabs for each submitted form"""

    template_path = "src/excel_templates/purchase_request_template.xlsx"

    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    output_filename = "purchase_request.xlsx"
    output_path = f"{session_folder}/{output_filename}"

    shutil.copy2(template_path, output_path)

    wb = load_workbook(output_path)

    for form in submitted_forms:
        tab_name = f"Receipt{form.form_number}"

        if tab_name not in wb.sheetnames:
            logger.warning(
                f"Tab '{tab_name}' not found in template, skipping form {form.form_number}"
            )
            continue

        ws = wb[tab_name]

        items = form.items[:15]
        is_usd = form.currency == "USD"

        # Header section
        ws["B1"] = datetime.now().strftime("%Y-%m-%d")
        ws["D1"] = form.currency
        ws["B3"] = user_info.name
        ws["D3"] = user_info.e_transfer_email
        ws["B4"] = user_info.team
        ws["B7"] = form.vendor_name
        ws["B32"] = user_info.address

        # Item rows (starting at row 9)
        for i, item in enumerate(items):
            row = 9 + i
            ws[f"B{row}"] = item.name
            ws[f"C{row}"] = item.usage
            ws[f"D{row}"] = item.quantity
            ws[f"E{row}"] = item.unit_price
            ws[f"F{row}"] = item.total

        # Financial summary
        ws["F24"] = form.us_subtotal if is_usd else form.subtotal_amount
        ws["F25"] = form.us_additional_fees if is_usd else form.hst_gst_amount
        ws["F26"] = form.us_total if is_usd else form.shipping_amount
        ws["F27"] = form.total_cad_amount

        # USD conversion rate
        if is_usd:
            exchange_rate = (
                round(form.total_cad_amount / form.us_total, 4)
                if form.us_total > 0 and form.total_cad_amount > 0
                else 0
            )
            ws["D7"] = exchange_rate

        insert_signature_at_cell(ws, session_folder, "B33", 280, 70)

    wb.save(output_path)
    wb.close()

    return {
        "filename": output_filename,
        "filepath": output_path,
        "forms_processed": len(submitted_forms),
        "tabs_used": [f"Receipt{form.form_number}" for form in submitted_forms],
    }
