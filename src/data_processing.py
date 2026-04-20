import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.core.logging_utils import setup_logger
from src.image_processing import insert_signature_at_cell

# Set up logger
logger = setup_logger(__name__)


def create_expense_report(
    session_folder: str,
    user_info: dict[str, Any],
    submitted_forms: list[dict[str, Any]],
) -> bool:
    """Copy the expense report template to the session folder and populate with user data"""

    template_path = "src/excel_templates/expense_report_template.xlsx"

    if not Path(template_path).exists():
        logger.exception(f"Expense report template not found: {template_path}")
        return False

    try:
        # Extract user info
        user_name = user_info.get("name", "UnknownUser")
        user_email = user_info.get("email", "")
        user_address = user_info.get("address", "")

        # Build output filename: MonthDay-Year-ExpenseReport-FullName
        now = datetime.now()
        month_name = now.strftime("%B")
        day = now.strftime("%d").lstrip("0")
        year = now.strftime("%Y")
        today = now.strftime("%Y-%m-%d")
        pascal_name = "".join(word.capitalize() for word in user_name.split())

        output_filename = f"{month_name}{day}-{year}-ExpenseReport-{pascal_name}.xlsx"
        output_path = f"{session_folder}/{output_filename}"

        shutil.copy2(template_path, output_path)

        wb = load_workbook(output_path)
        ws = wb.active

        # Header section
        ws["C2"] = user_name
        ws["F2"] = today
        ws["C3"] = user_email
        ws["F3"] = user_address

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
    ws: Worksheet, submitted_forms: list[dict[str, Any]]
) -> bool:
    """Populate expense report rows from submitted form data"""

    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        start_row = 6

        for i, form in enumerate(submitted_forms):
            row = start_row + i

            vendor_name = form.get("vendor_name", "")
            currency = form.get("currency", "CAD")
            subtotal = form.get("subtotal_amount", 0)
            discount = form.get("discount_amount", 0)
            total = form.get("total_amount", 0)
            hst_gst = form.get("hst_gst_amount", 0)
            us_total = form.get("us_total", 0)
            canadian_amount = form.get("canadian_amount", 0)

            subtotal_after_discount = subtotal - discount

            ws[f"B{row}"] = current_date
            ws[f"C{row}"] = vendor_name

            if currency == "CAD":
                ws[f"F{row}"] = subtotal_after_discount
                ws[f"G{row}"] = total
                ws[f"H{row}"] = hst_gst
            else:
                exchange_rate = (
                    canadian_amount / us_total
                    if us_total > 0 and canadian_amount > 0
                    else 0
                )
                ws[f"D{row}"] = us_total
                ws[f"E{row}"] = exchange_rate
                ws[f"F{row}"] = canadian_amount
                ws[f"G{row}"] = canadian_amount
                ws[f"H{row}"] = 0

        return True

    except Exception as e:
        logger.exception(f"Error populating expense rows: {e}")
        return False


def create_purchase_request(
    user_info: dict[str, Any],
    submitted_forms: list[dict[str, Any]],
    session_folder: str,
) -> dict[str, Any]:
    """Create Purchase Request using the template with multiple tabs for each submitted form"""

    template_path = "src/excel_templates/purchase_request_template.xlsx"

    # Check if template exists
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    # Create single output file
    output_filename = "purchase_request.xlsx"
    output_path = f"{session_folder}/{output_filename}"

    # Copy template to session folder
    shutil.copy2(template_path, output_path)

    # Load the copied template
    wb = load_workbook(output_path)

    for form in submitted_forms:
        form_number = form["form_number"]
        tab_name = f"Receipt{form_number}"

        if tab_name not in wb.sheetnames:
            logger.warning(
                f"Tab '{tab_name}' not found in template, skipping form {form_number}"
            )
            continue

        ws = wb[tab_name]

        # Extract user info
        submitter_name = user_info["name"]
        e_transfer_email = user_info["e_transfer_email"]
        team = user_info["team"]
        address = user_info["address"]

        # Extract form fields
        currency = form["currency"]
        vendor_name = form["vendor_name"]
        items = form["items"][:15]
        subtotal = form.get("subtotal_amount", 0)
        hst_gst = form.get("hst_gst_amount", 0)
        shipping = form.get("shipping_amount", 0)
        total = form.get("total_amount", 0)
        us_total = form.get("us_total", 0)
        canadian_amount = form.get("canadian_amount", 0)

        is_usd = currency == "USD"
        today = datetime.now().strftime("%Y-%m-%d")

        # Header section
        ws["B1"] = today
        ws["D1"] = currency
        ws["B3"] = submitter_name
        ws["D3"] = e_transfer_email
        ws["B4"] = team
        ws["B7"] = vendor_name
        ws["B32"] = address

        # Item rows (starting at row 9)
        for i, item in enumerate(items):
            row = 9 + i
            item_name = item["name"]
            item_usage = item["usage"]
            item_quantity = item["quantity"]
            item_unit_price = item["unit_price"]
            item_total = item["total"]

            ws[f"B{row}"] = item_name
            ws[f"C{row}"] = item_usage
            ws[f"D{row}"] = item_quantity
            ws[f"E{row}"] = item_unit_price
            ws[f"F{row}"] = item_total

        # Financial summary
        ws["E25"] = "Taxes" if is_usd else "HST/GST"
        ws["F24"] = us_total if is_usd else subtotal
        ws["F25"] = hst_gst
        ws["F26"] = shipping
        ws["F27"] = total

        # USD conversion rate
        if is_usd:
            ws["C7"] = "Conversion Rate"
            exchange_rate = (
                round(canadian_amount / us_total, 4)
                if us_total > 0 and canadian_amount > 0
                else 0
            )
            ws["D7"] = exchange_rate

        insert_signature_at_cell(ws, session_folder, "B33", 280, 70)

    # Save the modified workbook
    wb.save(output_path)
    wb.close()

    # Return information about the single generated file
    return {
        "filename": output_filename,
        "filepath": output_path,
        "forms_processed": len(submitted_forms),
        "tabs_used": [f"Receipt{form['form_number']}" for form in submitted_forms],
    }
