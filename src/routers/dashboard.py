"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

import os
import shutil
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.logging_utils import setup_logger
from data_processing import create_expense_report, create_purchase_request
from db.schema import get_db
from google_drive import (
    create_drive_folder_and_get_url,
    upload_session_to_drive,
)
from google_sheets import GoogleSheetsClient
from models.user_service import (
    get_user_by_email,
    save_signature_to_file,
)
from routers.utils import require_auth, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
    request: Request,
    user_email: str,
    updated: bool = False,
    error: str = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    # Get user from database
    user = get_user_by_email(db, user_email)
    if not user:
        logger.exception(f"User not found in database: {user_email}")
        raise HTTPException(status_code=404, detail="User not found")

    error_message = None
    success_message = None

    if error == "no_forms":
        error_message = "Please complete at least one invoice form before submitting. Make sure to fill in the vendor name, upload an invoice file, and add at least one item."
    elif updated:
        success_message = "✅ Your profile has been updated successfully!"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Purchase Request Site",
            "user_name": user.name,
            "user_email": user.email,
            "name": user.name,
            "email": user.email,
            "e_transfer_email": user.personal_email,
            "address": user.address,
            "team": user.team,
            "error_message": error_message,
            "success_message": success_message,
        },
    )


def create_session_folder(name):
    """Create a session folder with user name and timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").lower()
    session_folder = f"sessions/{safe_name}_{timestamp}"

    # Create the session directory if it doesn't exist
    os.makedirs(session_folder, exist_ok=True)

    return session_folder


@router.post("/submit-all-requests")
async def submit_all_requests(
    request: Request, db: Session = Depends(get_db), _: None = Depends(require_auth)
):
    # Get form data
    form_data = await request.form()

    # Extract user information
    name = form_data.get("name")
    email = form_data.get("email")
    e_transfer_email = form_data.get("e_transfer_email")
    address = form_data.get("address")
    team = form_data.get("team")

    # Create session folder dynamically
    session_folder = create_session_folder(name)

    # Get user from database to fetch signature
    user = get_user_by_email(db, email)
    if not user:
        logger.exception(f"User not found in database: {email}")
        raise HTTPException(status_code=404, detail="User not found")

    # Save user's signature to session folder
    signature_filename = "signature.png"
    signature_path = f"{session_folder}/{signature_filename}"
    if not save_signature_to_file(user, signature_path):
        logger.warning(f"Could not save signature for user {email}")

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
            us_total = float(form_data.get(f"us_total_{form_num}") or 0)
            usd_taxes = float(form_data.get(f"usd_taxes_{form_num}") or 0)
            canadian_amount = float(form_data.get(f"canadian_amount_{form_num}") or 0)
            subtotal_amount = discount_amount = shipping_amount = 0
            hst_gst_amount = usd_taxes
            total_amount = canadian_amount
        else:
            subtotal_amount = float(form_data.get(f"subtotal_amount_{form_num}") or 0)
            discount_amount = float(form_data.get(f"discount_amount_{form_num}") or 0)
            hst_gst_amount = float(form_data.get(f"hst_gst_amount_{form_num}") or 0)
            shipping_amount = float(form_data.get(f"shipping_amount_{form_num}") or 0)
            total_amount = float(form_data.get(f"total_amount_{form_num}") or 0)
            us_total = usd_taxes = canadian_amount = 0

        # Extract items for this form
        items = []
        for item_num in range(1, 50):  # Reasonable limit
            item_name = form_data.get(f"item_name_{form_num}_{item_num}")
            if not item_name:
                break
            item_usage = form_data.get(f"item_usage_{form_num}_{item_num}")
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")

            if item_name and item_usage and item_quantity and item_price:
                items.append(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": int(item_quantity),
                        "unit_price": float(item_price),
                        "total": float(item_total or 0),
                    }
                )

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
        proof_of_payment_filename = proof_of_payment_location = None
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
            with open(proof_of_payment_location, "wb") as file_object:
                file_object.write(await proof_of_payment_file.read())

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
        try:
            create_purchase_request(user_info, submitted_forms, session_folder)
        except Exception:
            logger.exception("Failed to create purchase request (continuing anyway)")

        # Copy expense report template to session folder
        try:
            create_expense_report(session_folder, user_info, submitted_forms)
        except Exception:
            logger.exception(
                "Failed to copy and populate expense report template (continuing anyway)"
            )

        # Create Google Drive folder and get URL
        drive_folder_url = ""
        drive_folder_id = ""
        try:
            drive_folder_url, drive_folder_id = create_drive_folder_and_get_url(
                session_folder, user_info
            )
        except Exception:
            logger.exception("Failed to create Google Drive folder (continuing anyway)")

        # Log to Google Sheets (with Drive folder URL)
        try:
            sheets_client = GoogleSheetsClient()
            sheets_client.log_purchase_request(
                user_info, submitted_forms, session_folder, drive_folder_url
            )
            sheets_client.close()
        except Exception:
            logger.exception("Failed to log to Google Sheets (continuing anyway)")

        # Upload files to both Google Drive and Supabase concurrently
        drive_upload_success = False
        supabase_upload_success = False

        def upload_to_drive():
            """Upload to Google Drive and return success status"""
            try:
                return upload_session_to_drive(
                    session_folder, user_info, drive_folder_id
                )
            except Exception:
                logger.exception(
                    "Failed to start Google Drive upload (continuing anyway)"
                )
                return False

        # Run both uploads concurrently
        logger.info("Starting concurrent uploads to Google Drive and Supabase...")
        drive_upload_success = False
        supabase_upload_success = False
        try:
            drive_upload_success = upload_to_drive()
            logger.info(
                f"Google Drive upload completed: {'✅ Success' if drive_upload_success else '❌ Failed'}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error in upload task: {e}")

        # Clean up session folder if at least one upload was successful
        if drive_upload_success or supabase_upload_success:
            try:
                shutil.rmtree(session_folder)
                logger.info(f"🗑️ Cleaned up session folder: {session_folder}")
            except Exception:
                logger.exception(f"Failed to delete session folder {session_folder}")

    else:
        logger.warning("No forms were submitted (all forms were empty)")
        # Redirect back to dashboard with error message instead of success
        return RedirectResponse(
            url=f"/dashboard?user_email={email}&error=no_forms",
            status_code=303,
        )

    # Redirect back to home with success message and session info for download
    return RedirectResponse(
        url=f"/success?drive_folder_id={drive_folder_id}&excel_file=purchase_request.xlsx&user_email={email}",
        status_code=303,
    )
