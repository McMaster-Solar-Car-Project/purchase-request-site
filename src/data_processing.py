import os
import shutil
from datetime import datetime

from openpyxl import load_workbook

from src.core.logging_utils import setup_logger
from src.image_processing import insert_signature_at_cell

# Set up logger
logger = setup_logger(__name__)


def create_expense_report(user_info, submitted_forms, session_folder):
    """Copy the expense report template to the session folder and populate with user data"""

    template_path = "src/excel_templates/expense_report_template.xlsx"

    # Check if template exists
    if not os.path.exists(template_path):
        logger.exception(f"Expense report template not found: {template_path}")
        return False

    try:
        # Create destination filename with format: MonthDay-Year-ExpenseReport-FullName
        now = datetime.now()
        month_name, day, year = (
            now.strftime("%B"),
            now.strftime("%d").lstrip("0"),
            now.strftime("%Y"),
        )
        pascal_name = "".join(
            word.capitalize() for word in user_info.get("name", "UnknownUser").split()
        )
        output_filename = f"{month_name}{day}-{year}-ExpenseReport-{pascal_name}.xlsx"
        output_path = f"{session_folder}/{output_filename}"

        shutil.copy2(template_path, output_path)
        # Expense report template copied

        # Load the copied template and populate with user data
        wb = load_workbook(output_path)

        # Get the active worksheet (assuming first sheet)
        ws = wb.active

        # Populate user information in specified cells
        ws["C2"] = user_info.get("name", "")  # User's name in C2
        ws["F2"] = datetime.now().strftime("%Y-%m-%d")  # Current date in F2
        ws["C3"] = user_info.get("email", "")  # Email in C3
        ws["F3"] = user_info.get("address", "")  # Address in F3

        # Populate expense rows from submitted form data
        try:
            populate_expense_rows_from_submitted_forms(ws, submitted_forms)
        except Exception as e:
            logger.exception(
                f"Failed to populate expense rows from submitted forms: {e}"
            )

        try:
            # Insert signature at cell A19
            insert_signature_at_cell(ws, session_folder, "A19", 200, 60)
        except Exception as e:
            logger.warning(f"Failed to insert signature into expense report: {e}")

        # Save the populated template
        wb.save(output_path)
        wb.close()

        return True

    except Exception as e:
        logger.exception(f"Failed to copy and populate expense report template: {e}")
        return False


def populate_expense_rows_from_submitted_forms(ws, submitted_forms):
    """Populate expense report rows from submitted form data"""

    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        start_row = 6  # Starting at row 6 as specified
        current_row = start_row

        # Process forms in the order they appear
        for i, form in enumerate(submitted_forms):
            row = current_row + i
            subtotal = form.get("subtotal_amount", 0)
            discount = form.get("discount_amount", 0)
            final_subtotal = subtotal - discount
            ws[f"B{row}"] = current_date  # Date
            ws[f"C{row}"] = form.get("vendor_name", "")  # Vendor name

            if form.get("currency", "CAD") == "CAD":
                ws[f"F{row}"] = final_subtotal
                ws[f"G{row}"] = form.get("total_amount", 0)  # Total
                ws[f"H{row}"] = form.get("hst_gst_amount", 0)  # HST/GST
            else:  # USD
                us_total = form.get("us_total", 1)
                canadian_amount = form.get("canadian_amount", 0)
                ws[f"D{row}"] = us_total  # US total
                ws[f"E{row}"] = (
                    canadian_amount / us_total
                    if us_total > 0 and canadian_amount > 0
                    else 0
                )  # Exchange rate
                ws[f"F{row}"] = ws[f"G{row}"] = canadian_amount  # Canadian amount
                ws[f"H{row}"] = 0  # No HST for US

        return True

    except Exception as e:
        logger.exception(f"Error populating expense rows: {e}")
        return False


def create_purchase_request(user_info, submitted_forms, session_folder):
    """Create Purchase Request using the template with multiple tabs for each submitted form"""

    template_path = "src/excel_templates/purchase_request_template.xlsx"

    # Check if template exists
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    # Create single output file
    output_filename = "purchase_request.xlsx"
    output_path = f"{session_folder}/{output_filename}"

    # Copy template to session folder
    shutil.copy2(template_path, output_path)

    # Load the copied template
    wb = load_workbook(output_path)

    # Process each submitted form
    for form in submitted_forms:
        # Find the corresponding tab (Receipt1, Receipt2, etc.)
        tab_name = f"Receipt{form['form_number']}"

        # Check if the tab exists
        if tab_name not in wb.sheetnames:
            logger.warning(
                f"Tab '{tab_name}' not found in template, skipping form {form['form_number']}"
            )
            continue

        # Select the appropriate worksheet
        ws = wb[tab_name]

        # Fill in the specified cells
        # B1: Today's date
        ws["B1"] = datetime.now().strftime("%Y-%m-%d")

        # D1: Currency used
        ws["D1"] = form["currency"]

        # B3: Name of submitter
        ws["B3"] = user_info["name"]

        # D3: E-transfer email address
        ws["D3"] = user_info["e_transfer_email"]

        # B4: Team they're on
        ws["B4"] = user_info["team"]

        # B7: Vendor name
        ws["B7"] = form["vendor_name"]

        # B32: Home address
        ws["B32"] = user_info["address"]

        # Populate items starting from row 9 (limit to first 15 items)
        for i, item in enumerate(form["items"][:15]):  # Only process first 15 items
            row = 9 + i  # Start from row 9, increment for each item

            # B9, B10, B11, etc: Item name
            ws[f"B{row}"] = item["name"]

            # C9, C10, C11, etc: Usage/purpose
            ws[f"C{row}"] = item["usage"]

            # D9, D10, D11, etc: Quantity
            ws[f"D{row}"] = item["quantity"]

            # E9, E10, E11, etc: Unit price
            ws[f"E{row}"] = item["unit_price"]

            # F9, F10, F11, etc: Total price
            ws[f"F{row}"] = item["total"]

        # Financial summary (updated row numbers)
        # Note: F24 is NOT the subtotal according to user feedback

        # E25: Tax label (depends on currency)
        if form["currency"] == "USD":
            ws["E25"] = "Taxes"
        else:
            ws["E25"] = "HST/GST"

        # F24: Subtotal amount (uses different fields for USD vs CAD)
        if form["currency"] == "USD":
            ws["F24"] = form["us_total"]  # For USD, use the US total as subtotal
        else:
            ws["F24"] = form["subtotal_amount"]  # For CAD, use regular subtotal

        # F25: Tax amount (HST/GST for CAD, Taxes for USD)
        ws["F25"] = form["hst_gst_amount"]

        # F26: Shipping
        ws["F26"] = form["shipping_amount"]

        # F27: Total
        ws["F27"] = form["total_amount"]

        # C7 & D7: Conversion Rate (only for USD)
        if form["currency"] == "USD":
            # C7: Conversion Rate label
            ws["C7"] = "Conversion Rate"

            # D7: Calculate conversion rate using expense report method = Canadian Amount / US Total
            us_total = form.get(
                "us_total", 0
            )  # Direct from form (same as expense report)
            canadian_amount = form.get(
                "canadian_amount", 0
            )  # Direct from form (same as expense report)

            if us_total > 0 and canadian_amount > 0:  # Avoid division by zero
                conversion_rate = canadian_amount / us_total
                ws["D7"] = round(conversion_rate, 4)  # Round to 4 decimal places
            else:
                ws["D7"] = 0

        # Insert signature image
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


def create_expense_report_non_mcmaster(user_info, submitted_forms, session_folder):
    """Create expense report for non-MCMaster users"""

    template_path = "src/excel_templates/expense_report_template_non_mcmaster.xlsx"

    # Check if template exists
    if not os.path.exists(template_path):
        logger.exception(f"Expense report template not found: {template_path}")
        return False
    # Create single output file
    output_filename = "purchase_request_non_mcmaster.xlsx"
    output_path = f"{session_folder}/{output_filename}"

    # Copy template to session folder
    shutil.copy2(template_path, output_path)

    # Load the copied template
    wb = load_workbook(output_path)

    ws = wb.active

    ws["A11"] = user_info["name"]
    ws["A14"] = user_info["address"]
    ws["L14"] = user_info["e_transfer_email"]

    row = 21
    for form in submitted_forms:
        invoice_subtotal = sum(
            item["unit_price"] * item["quantity"] for item in form["items"]
        )
        if form["currency"] == "USD":
            invoice_total_us = invoice_subtotal + form.get("hst_gst_amount", 0)
            canadian_total = form.get("canadian_amount", 0)

            us_tax_rate = invoice_total_us / invoice_subtotal

        for item in form["items"]:
            ws[f"C{row}"] = item["usage"]
            if form["currency"] == "USD":
                ws[f"L{row}"] = item["unit_price"] * item["quantity"] * us_tax_rate
                ws[f"N{row}"] = canadian_total / invoice_total_us
                ws[f"P{row}"] = canadian_total * (
                    item["unit_price"] * item["quantity"] / invoice_subtotal
                )
                ws[f"R{row}"] = canadian_total * (
                    item["unit_price"] * item["quantity"] / invoice_subtotal
                )
            else:
                ws[f"P{row}"] = item["unit_price"] * item["quantity"]
                ws[f"R{row}"] = item["unit_price"] * item["quantity"]
                ws[f"T{row}"] = form["hst_gst_amount"] * (
                    item["unit_price"] * item["quantity"] / invoice_subtotal
                )

            row += 1

    wb.save(output_path)
    wb.close()

    return {
        "filename": output_filename,
        "filepath": output_path,
        "forms_processed": len(submitted_forms),
    }
