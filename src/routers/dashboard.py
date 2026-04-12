"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

import os
import shutil
from datetime import datetime

import anyio
import sentry_sdk
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from src.core.logging_utils import setup_logger
from src.data_processing import create_expense_report, create_purchase_request
from src.db.schema import get_db
from src.google_drive import (
    create_drive_folder_and_get_url,
    upload_session_to_drive,
)
from src.google_sheets import GoogleSheetsClient
from src.models.user_service import (
    get_user_by_email,
    save_signature_to_file,
)
from src.routers.utils import require_auth, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])


def _form_str(value: object, default: str = "") -> str:
    """Coerce multipart form field to str; ignore accidental file parts."""
    if value is None or isinstance(value, UploadFile):
        return default
    return str(value)


def _form_float(value: object, default: float = 0.0) -> float:
    if value is None or isinstance(value, UploadFile):
        return default
    s = str(value).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _form_int(value: object, default: int = 0) -> int:
    if value is None or isinstance(value, UploadFile):
        return default
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


@router.get("/dashboard")
async def dashboard(
    request: Request,
    user_email: str,
    updated: bool = False,
    error: str | None = None,
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
        request=request,
        name="dashboard.html",
        context={
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


def create_session_folder(name: str) -> str:
    """Create a session folder with user name and timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").lower()
    session_folder = f"sessions/{safe_name}_{timestamp}"

    # Create the session directory if it doesn't exist
    os.makedirs(session_folder, exist_ok=True)

    return session_folder


@router.post("/submit-all-requests")
def submit_all_requests(
    request: Request, db: Session = Depends(get_db), _: None = Depends(require_auth)
):
    # Get form data
    form_data = anyio.from_thread.run(request.form)

    # Extract user information
    name = _form_str(form_data.get("name"))
    email = _form_str(form_data.get("email"))
    e_transfer_email = _form_str(form_data.get("e_transfer_email"))
    address = _form_str(form_data.get("address"))
    team = _form_str(form_data.get("team"))

    sentry_sdk.add_breadcrumb(
        category="purchase_flow",
        message="Started submission processing",
        level="info",
    )

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
        vendor_name = _form_str(form_data.get(f"vendor_name_{form_num}"))

        if vendor_name:
            sentry_sdk.add_breadcrumb(
                category="purchase_flow",
                message=f"Processing form {form_num}: {vendor_name}",
                level="info",
            )
        invoice_file = form_data.get(f"invoice_file_{form_num}")
        proof_of_payment_file = form_data.get(f"proof_of_payment_{form_num}")
        currency = _form_str(form_data.get(f"currency_{form_num}"), "CAD")

        # Skip empty forms (no vendor name or invoice)
        if not vendor_name or not isinstance(invoice_file, UploadFile):
            continue

        # For USD purchases, proof of payment is required
        if currency == "USD" and not isinstance(proof_of_payment_file, UploadFile):
            logger.warning(
                f"Form {form_num} in USD currency missing proof of payment - skipping"
            )
            continue

        # Extract financial data based on currency
        if currency == "USD":
            us_total = _form_float(form_data.get(f"us_total_{form_num}"))
            usd_taxes = _form_float(form_data.get(f"usd_taxes_{form_num}"))
            canadian_amount = _form_float(form_data.get(f"canadian_amount_{form_num}"))
            subtotal_amount = discount_amount = shipping_amount = 0
            hst_gst_amount = usd_taxes
            total_amount = canadian_amount
        else:
            subtotal_amount = _form_float(form_data.get(f"subtotal_amount_{form_num}"))
            discount_amount = _form_float(form_data.get(f"discount_amount_{form_num}"))
            hst_gst_amount = _form_float(form_data.get(f"hst_gst_amount_{form_num}"))
            shipping_amount = _form_float(form_data.get(f"shipping_amount_{form_num}"))
            total_amount = _form_float(form_data.get(f"total_amount_{form_num}"))
            us_total = usd_taxes = canadian_amount = 0

        # Extract items for this form
        items = []
        for item_num in range(1, 50):  # Reasonable limit
            item_name = _form_str(form_data.get(f"item_name_{form_num}_{item_num}"))
            if not item_name:
                break
            item_usage = _form_str(form_data.get(f"item_usage_{form_num}_{item_num}"))
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")

            if item_name and item_usage and item_quantity and item_price:
                items.append(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": _form_int(item_quantity),
                        "unit_price": _form_float(item_price),
                        "total": _form_float(item_total),
                    }
                )

        # Skip forms with no items
        if not items:
            continue

        # Save uploaded invoice file in session folder
        invoice_fn = invoice_file.filename or "invoice"
        invoice_extension = invoice_fn.split(".")[-1] if "." in invoice_fn else "pdf"
        invoice_filename = f"{form_num}_{vendor_name}.{invoice_extension}"
        invoice_file_location = f"{session_folder}/{invoice_filename}"

        # Save the invoice file
        with open(invoice_file_location, "wb") as file_object:
            content = invoice_file.file.read()
            file_object.write(content)

        # Save proof of payment file only for USD currency
        proof_of_payment_filename = proof_of_payment_location = None
        if currency == "USD" and isinstance(proof_of_payment_file, UploadFile):
            pop_fn = proof_of_payment_file.filename or "payment"
            payment_extension = pop_fn.split(".")[-1] if "." in pop_fn else "pdf"
            proof_of_payment_filename = (
                f"{form_num}_proof_of_payment.{payment_extension}"
            )
            proof_of_payment_location = f"{session_folder}/{proof_of_payment_filename}"
            with open(proof_of_payment_location, "wb") as file_object:
                file_object.write(proof_of_payment_file.file.read())

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

        # Upload files to external storage providers
        drive_upload_success = False

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
        sentry_sdk.add_breadcrumb(
            category="external_api",
            message="Starting Google Drive upload",
            level="info",
        )
        drive_upload_success = False
        try:
            drive_upload_success = upload_to_drive()
            logger.info(
                f"Google Drive upload completed: {'✅ Success' if drive_upload_success else '❌ Failed'}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error in upload task: {e}")

        # Clean up session folder if at least one upload was successful
        if drive_upload_success:
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
