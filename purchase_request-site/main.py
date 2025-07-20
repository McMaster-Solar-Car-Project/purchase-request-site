import os
import shutil
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from dotenv import load_dotenv
from data_processing import create_excel_report, copy_expense_report_template
from image_processing import convert_signature_to_png, detect_and_crop_signature
from logging_utils import setup_logger
from google_sheets import log_purchase_request_to_sheets
from google_drive import (
    upload_session_to_drive_background,
    create_drive_folder_and_get_url,
)

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions", "static", "templates", "excel_templates"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown"""
    # Startup: Log directory status
    logger.info("🚀 Application startup complete - all directories ready!")

    yield  # Application runs here

    # Shutdown: Cleanup code would go here if needed
    logger.info("👋 Application shutting down...")


app = FastAPI(title="Purchase Request Site", lifespan=lifespan)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Set up templates
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home(
    request: Request,
    success: str = None,
    session_folder: str = None,
    excel_file: str = None,
):
    success_message = None
    download_info = None

    if success:
        success_message = "All your purchase requests have been submitted successfully! We'll be in touch soon."

        # If session info is provided, add download information
        if session_folder and excel_file:
            download_info = {
                "session_folder": session_folder,
                "excel_file": excel_file,
                "download_url": f"/download-excel?session_folder={session_folder}&excel_file={excel_file}",
            }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "heading": "Enter your purchase request information",
            "success_message": success_message,
            "download_info": download_info,
            "google_api_key": os.getenv("GOOGLE_PLACES_API_KEY"),
        },
    )


@app.get("/download-excel")
async def download_excel(session_folder: str, excel_file: str):
    """Download the generated Excel file for a session"""
    file_path = f"{session_folder}/{excel_file}"

    # Security check: ensure the path is within the sessions directory
    if not session_folder.startswith("sessions/"):
        raise HTTPException(status_code=400, detail="Invalid session folder")

    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="Excel file not found")

    # Return the file for download
    return FileResponse(
        path=file_path,
        filename=excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def create_session_folder(name):
    """Create a unique session folder name with timestamp and user name"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").lower()
    session_folder = f"sessions/{timestamp}_{safe_name}"

    # Create the session directory if it doesn't exist
    os.makedirs(session_folder, exist_ok=True)

    return session_folder


@app.post("/submit-request")
async def submit_request(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    e_transfer_email: str = Form(...),
    address: str = Form(...),
    team: str = Form(...),
    signature: UploadFile = File(...),
):
    # Create session folder for this user
    session_folder = create_session_folder(name)

    # Save signature file in session folder
    signature_extension = (
        signature.filename.split(".")[-1] if "." in signature.filename else "png"
    )
    signature_filename = f"signature.{signature_extension}"
    signature_location = f"{session_folder}/{signature_filename}"

    # Save the original signature file first
    with open(signature_location, "wb") as file_object:
        content = await signature.read()
        file_object.write(content)

    # Convert signature to PNG format first (save as original for records)
    original_png_filename = "signature_original.png"
    original_png_location = f"{session_folder}/{original_png_filename}"

    conversion_success = convert_signature_to_png(
        signature_location, original_png_location
    )

    if conversion_success:
        logger.info(f"Original signature saved as PNG: {original_png_location}")

        # Now crop the original PNG to create the processed version for Excel
        final_signature_filename = "signature.png"
        final_signature_location = f"{session_folder}/{final_signature_filename}"

        cropping_success = detect_and_crop_signature(
            original_png_location, final_signature_location
        )

        if cropping_success:
            logger.info(f"Signature processed successfully: {final_signature_location}")
        else:
            # Cropping failed - copy the original PNG as the final version
            try:
                shutil.copy2(original_png_location, final_signature_location)
                logger.warning(
                    f"Signature cropping failed, using original PNG: {final_signature_location}"
                )
            except Exception as e:
                logger.error(f"Could not copy original PNG: {e}")
                final_signature_filename = original_png_filename

        # Remove the original file if conversion was successful and it's not PNG
        if signature_extension.lower() != "png":
            try:
                os.remove(signature_location)
                logger.info(f"Original signature file removed: {signature_location}")
            except Exception as e:
                logger.warning(f"Could not remove original signature file: {e}")

    else:
        # Conversion failed - fall back to original file
        final_signature_filename = signature_filename
        logger.error(
            f"Signature conversion failed, using original: {signature_location}"
        )

    # Redirect to dashboard with user information including session folder
    return RedirectResponse(
        url=f"/dashboard?name={name}&email={email}&e_transfer_email={e_transfer_email}&address={address}&team={team}&session_folder={session_folder}&signature={final_signature_filename}",
        status_code=303,
    )


@app.get("/dashboard")
async def dashboard(
    request: Request,
    name: str,
    email: str,
    e_transfer_email: str,
    address: str,
    team: str,
    session_folder: str,
    signature: str,
    error: str = None,
):
    error_message = None
    if error == "no_forms":
        error_message = "Please complete at least one invoice form before submitting. Make sure to fill in the vendor name, upload an invoice file, and add at least one item."

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "name": name,
            "email": email,
            "e_transfer_email": e_transfer_email,
            "address": address,
            "team": team,
            "session_folder": session_folder,
            "signature": signature,
            "error_message": error_message,
        },
    )


@app.post("/submit-all-requests")
async def submit_all_requests(request: Request):
    # Get form data
    form_data = await request.form()

    # Extract user information
    name = form_data.get("name")
    email = form_data.get("email")
    e_transfer_email = form_data.get("e_transfer_email")
    address = form_data.get("address")
    team = form_data.get("team")
    session_folder = form_data.get("session_folder")
    signature_filename = form_data.get("signature")

    submitted_forms = []

    # Process each of the 10 possible forms
    for form_num in range(1, 11):
        vendor_name = form_data.get(f"vendor_name_{form_num}")
        invoice_file = form_data.get(f"invoice_file_{form_num}")
        proof_of_payment_file = form_data.get(f"proof_of_payment_{form_num}")
        currency = form_data.get(
            f"currency_{form_num}", "CAD"
        )  # Default to CAD if not specified

        # Skip empty forms (no vendor name or invoice)
        if not vendor_name or not invoice_file or not hasattr(invoice_file, "filename"):
            continue

        # For USD purchases, proof of payment is required
        if currency == "USD" and (
            not proof_of_payment_file or not hasattr(proof_of_payment_file, "filename")
        ):
            logger.warning(
                f"Form {form_num} in USD currency missing proof of payment - skipping"
            )
            continue

        # Extract financial data based on currency
        if currency == "USD":
            # For USD, use simplified breakdown
            us_total = float(form_data.get(f"us_total_{form_num}") or 0)
            usd_taxes = float(form_data.get(f"usd_taxes_{form_num}") or 0)
            canadian_amount = float(form_data.get(f"canadian_amount_{form_num}") or 0)

            # Set other fields to 0 for USD
            subtotal_amount = 0
            discount_amount = 0
            hst_gst_amount = usd_taxes  # Use USD taxes as the tax amount
            shipping_amount = 0
            total_amount = (
                canadian_amount  # Use Canadian amount as total for reimbursement
            )
        else:
            # For CAD, use detailed breakdown
            subtotal_amount = float(form_data.get(f"subtotal_amount_{form_num}") or 0)
            discount_amount = float(form_data.get(f"discount_amount_{form_num}") or 0)
            hst_gst_amount = float(form_data.get(f"hst_gst_amount_{form_num}") or 0)
            shipping_amount = float(form_data.get(f"shipping_amount_{form_num}") or 0)
            total_amount = float(form_data.get(f"total_amount_{form_num}") or 0)

            # Set USD fields to 0 for CAD
            us_total = 0
            usd_taxes = 0
            canadian_amount = 0

        # Debug logging to see what values we're getting
        logger.debug(f"Form {form_num} ({currency}) financial data:")
        logger.debug(
            f"  Raw subtotal_amount: '{form_data.get(f'subtotal_amount_{form_num}')}'"
        )
        logger.debug(
            f"  Raw total_amount: '{form_data.get(f'total_amount_{form_num}')}'"
        )
        logger.debug(
            f"  Raw hst_gst_amount: '{form_data.get(f'hst_gst_amount_{form_num}')}'"
        )
        logger.debug(
            f"  Raw shipping_amount: '{form_data.get(f'shipping_amount_{form_num}')}'"
        )
        if currency == "USD":
            logger.debug(f"  Raw us_total: '{form_data.get(f'us_total_{form_num}')}'")
            logger.debug(f"  Raw usd_taxes: '{form_data.get(f'usd_taxes_{form_num}')}'")
            logger.debug(
                f"  Raw canadian_amount: '{form_data.get(f'canadian_amount_{form_num}')}'"
            )
        logger.debug("  Parsed values:")
        logger.debug(f"    subtotal_amount: {subtotal_amount}")
        logger.debug(f"    discount_amount: {discount_amount}")
        logger.debug(f"    hst_gst_amount: {hst_gst_amount}")
        logger.debug(f"    shipping_amount: {shipping_amount}")
        logger.debug(f"    total_amount: {total_amount}")
        logger.debug(f"    us_total: {us_total}")
        logger.debug(f"    usd_taxes: {usd_taxes}")
        logger.debug(f"    canadian_amount: {canadian_amount}")
        logger.debug("---")

        # Extract items for this form
        items = []
        item_num = 1
        while True:
            item_name = form_data.get(f"item_name_{form_num}_{item_num}")
            if not item_name:
                break

            item_usage = form_data.get(f"item_usage_{form_num}_{item_num}")
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")

            # Debug logging for item values
            logger.debug(f"  Item {item_num} raw values:")
            logger.debug(f"    name: '{item_name}'")
            logger.debug(f"    usage: '{item_usage}'")
            logger.debug(f"    quantity: '{item_quantity}'")
            logger.debug(f"    price: '{item_price}'")
            logger.debug(f"    total: '{item_total}'")

            if item_name and item_usage and item_quantity and item_price:
                parsed_total = float(item_total) if item_total else 0
                items.append(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": int(item_quantity),
                        "unit_price": float(item_price),
                        "total": parsed_total,
                    }
                )
                logger.debug(
                    f"    → Added to items: qty={int(item_quantity)}, price=${float(item_price)}, total=${parsed_total}"
                )
            else:
                logger.debug("    → Skipped (missing required fields)")

            item_num += 1

        # Skip forms with no items
        if not items:
            continue

        # Save uploaded invoice file in session folder
        invoice_extension = (
            invoice_file.filename.split(".")[-1]
            if "." in invoice_file.filename
            else "pdf"
        )
        invoice_filename = f"{form_num}_{vendor_name}.{invoice_extension}"
        invoice_file_location = f"{session_folder}/{invoice_filename}"

        # Save the invoice file
        with open(invoice_file_location, "wb") as file_object:
            content = await invoice_file.read()
            file_object.write(content)

        # Save proof of payment file only for USD currency
        proof_of_payment_filename = None
        proof_of_payment_location = None
        if (
            currency == "USD"
            and proof_of_payment_file
            and hasattr(proof_of_payment_file, "filename")
        ):
            payment_extension = (
                proof_of_payment_file.filename.split(".")[-1]
                if "." in proof_of_payment_file.filename
                else "pdf"
            )
            proof_of_payment_filename = (
                f"{form_num}_proof_of_payment.{payment_extension}"
            )
            proof_of_payment_location = f"{session_folder}/{proof_of_payment_filename}"

            # Save the proof of payment file
            with open(proof_of_payment_location, "wb") as file_object:
                content = await proof_of_payment_file.read()
                file_object.write(content)

        # Store form data
        form_submission = {
            "form_number": form_num,
            "vendor_name": vendor_name,
            "currency": currency,
            "invoice_filename": invoice_filename,
            "invoice_file_location": invoice_file_location,
            "proof_of_payment_filename": proof_of_payment_filename,
            "proof_of_payment_location": proof_of_payment_location,
            "subtotal_amount": subtotal_amount,
            "discount_amount": discount_amount,
            "hst_gst_amount": hst_gst_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "us_total": us_total,
            "usd_taxes": usd_taxes,
            "canadian_amount": canadian_amount,
            "items": items,
        }

        submitted_forms.append(form_submission)

    # Print all submitted forms
    if submitted_forms:
        # Create Excel export in session folder
        user_info = {
            "name": name,
            "email": email,
            "e_transfer_email": e_transfer_email,
            "address": address,
            "team": team,
            "signature": signature_filename,
        }

        excel_report = create_excel_report(user_info, submitted_forms, session_folder)

        logger.info("Bulk submission received from:")
        logger.info(f"Name: {name}")
        logger.info(f"McMaster Email: {email}")
        logger.info(f"E-Transfer Email: {e_transfer_email}")
        logger.info(f"Address: {address}")
        logger.info(f"Team: {team}")
        logger.info(f"Session Folder: {session_folder}")
        logger.info(
            f"Digital Signature: {signature_filename} (saved to {session_folder}/{signature_filename})"
        )
        logger.info(f"Excel Report Generated: {excel_report['filename']}")
        logger.info(f"  - Forms processed: {excel_report['forms_processed']}")
        logger.info(f"  - Tabs used: {', '.join(excel_report['tabs_used'])}")
        logger.info(f"  - File location: {excel_report['filepath']}")
        logger.info("")
        logger.info(f"Number of forms submitted: {len(submitted_forms)}")
        logger.info("=" * 60)

        for form in submitted_forms:
            logger.info(f"Purchase Request #{form['form_number']}:")
            logger.info(f"  Vendor: {form['vendor_name']}")
            logger.info(f"  Currency: {form['currency']}")
            logger.info(
                f"  Invoice File: {form['invoice_filename']} (saved to {form['invoice_file_location']})"
            )
            if form["proof_of_payment_filename"]:
                logger.info(
                    f"  Proof of Payment: {form['proof_of_payment_filename']} (saved to {form['proof_of_payment_location']})"
                )
            logger.info("  Financial Breakdown:")

            if form["currency"] == "USD":
                # Show USD breakdown
                logger.info(f"    US Subtotal: ${form['us_total']:.2f} USD")
                logger.info(f"    Canadian Amount: ${form['canadian_amount']:.2f} CAD")
                logger.info(
                    f"    Reimbursement Total: ${form['canadian_amount']:.2f} CAD"
                )
            else:
                # Show CAD breakdown
                logger.info(
                    f"    Subtotal: ${form['subtotal_amount']:.2f} {form['currency']}"
                )
                logger.info(
                    f"    Discount: -${form['discount_amount']:.2f} {form['currency']}"
                )

                # Use appropriate tax label based on currency
                tax_label = "Taxes" if form["currency"] == "USD" else "HST/GST"
                logger.info(
                    f"    {tax_label}: ${form['hst_gst_amount']:.2f} {form['currency']}"
                )

                logger.info(
                    f"    Shipping: ${form['shipping_amount']:.2f} {form['currency']}"
                )
                logger.info(
                    f"    Total Amount: ${form['total_amount']:.2f} {form['currency']}"
                )

            logger.info("  Items:")
            for i, item in enumerate(form["items"], 1):
                logger.info(f"    {i}. {item['name']}")
                logger.info(f"       Usage: {item['usage']}")
                logger.info(f"       Quantity: {item['quantity']}")
                logger.info(
                    f"       Unit Price: ${item['unit_price']:.2f} {form['currency']}"
                )
                logger.info(f"       Total: ${item['total']:.2f} {form['currency']}")
            logger.info("-" * 40)

        logger.info("=" * 60)

        # Copy expense report template to session folder
        try:
            logger.info("Copying and populating expense report template...")
            copy_expense_report_template(session_folder, user_info, submitted_forms)
        except Exception as e:
            logger.error(f"Failed to copy and populate expense report template (continuing anyway): {e}")

        # Create Google Drive folder and get URL
        drive_folder_url = ""
        drive_folder_id = ""
        try:
            logger.info("Creating Google Drive folder structure...")
            drive_folder_url, drive_folder_id = create_drive_folder_and_get_url(
                session_folder, user_info
            )
        except Exception as e:
            logger.error(
                f"Failed to create Google Drive folder (continuing anyway): {e}"
            )

        # Log to Google Sheets (with Drive folder URL)
        try:
            logger.info("Logging session data to Google Sheets...")
            log_purchase_request_to_sheets(
                user_info, submitted_forms, session_folder, drive_folder_url
            )
        except Exception as e:
            logger.error(f"Failed to log to Google Sheets (continuing anyway): {e}")

        # Upload files to Google Drive (in background)
        try:
            logger.info("Starting background file upload to Google Drive...")
            upload_session_to_drive_background(
                session_folder, user_info, drive_folder_id
            )
        except Exception as e:
            logger.error(
                f"Failed to start Google Drive upload (continuing anyway): {e}"
            )

    else:
        logger.warning("No forms were submitted (all forms were empty)")
        # Redirect back to dashboard with error message instead of success
        return RedirectResponse(
            url=f"/dashboard?name={name}&email={email}&e_transfer_email={e_transfer_email}&address={address}&team={team}&session_folder={session_folder}&signature={signature_filename}&error=no_forms",
            status_code=303,
        )

    # Redirect back to home with success message and session info for download
    return RedirectResponse(
        url=f"/?success=true&session_folder={session_folder}&excel_file=purchase_request.xlsx",
        status_code=303,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
