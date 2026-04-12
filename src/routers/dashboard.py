"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal

import sentry_sdk
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from src.core.logging_utils import setup_logger
from src.data_processing import create_expense_report, create_purchase_request
from src.db.schema import get_db
from src.google_drive import GoogleDriveClient
from src.google_sheets import GoogleSheetsClient
from src.models.user_service import (
    get_user_by_email,
    save_signature_to_file,
)
from src.routers.utils import require_auth, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])
MAX_FORMS = 10
MAX_ITEMS_PER_FORM = 50
SESSIONS_ROOT = Path("sessions").resolve()


class SubmissionLineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    usage: str
    quantity: int
    unit_price: float
    total: float


class SubmissionForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    form_number: int
    vendor_name: str
    currency: Literal["CAD", "USD"]
    invoice_filename: str
    invoice_file_location: str
    proof_of_payment_filename: str | None = None
    proof_of_payment_location: str | None = None
    subtotal_amount: float
    discount_amount: float
    hst_gst_amount: float
    shipping_amount: float
    total_amount: float
    us_total: float
    usd_taxes: float
    canadian_amount: float
    items: list[SubmissionLineItem]


class SubmissionUserInfo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: str
    e_transfer_email: str
    address: str
    team: str
    signature: str


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


def _file_extension(filename: str | None, default: str = "pdf") -> str:
    if not filename or "." not in filename:
        return default
    return filename.rsplit(".", 1)[-1]


def _safe_filename_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "file"


def _build_session_file_path(session_folder: str, filename: str) -> Path:
    session_path = Path(session_folder).resolve()
    if not session_path.is_relative_to(SESSIONS_ROOT):
        raise ValueError("Invalid session path outside sessions root")
    destination = (session_path / filename).resolve()
    if not destination.is_relative_to(session_path):
        raise ValueError("Invalid destination path outside session folder")
    return destination


async def _save_uploaded_file(file: UploadFile, destination: Path) -> None:
    if not destination.resolve().is_relative_to(SESSIONS_ROOT):
        raise ValueError("Invalid destination path outside sessions root")
    with open(destination, "wb") as file_object:
        file_object.write(await file.read())


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
    """Create a timestamped session folder for generated files."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = _safe_filename_component(name).lower()
    session_folder = (SESSIONS_ROOT / f"{safe_name}_{timestamp}").resolve()
    if not session_folder.is_relative_to(SESSIONS_ROOT):
        raise ValueError("Invalid session folder path")
    session_folder.mkdir(parents=True, exist_ok=True)
    return str(session_folder)


@router.post("/submit-all-requests")
async def submit_all_requests(
    request: Request, db: Session = Depends(get_db), _: None = Depends(require_auth)
):
    form_data = await request.form()

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

    session_folder = create_session_folder(name)

    # Get user from database to fetch signature
    user = get_user_by_email(db, email)
    if not user:
        logger.exception(f"User not found in database: {email}")
        raise HTTPException(status_code=404, detail="User not found")

    signature_filename = "signature.png"
    signature_path = _build_session_file_path(session_folder, signature_filename)
    if not save_signature_to_file(user, str(signature_path)):
        logger.warning(f"Could not save signature for user {email}")

    submitted_forms: list[SubmissionForm] = []

    for form_num in range(1, MAX_FORMS + 1):
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

        if not vendor_name or not isinstance(invoice_file, UploadFile):
            continue

        if currency == "USD" and not isinstance(proof_of_payment_file, UploadFile):
            logger.warning(
                f"Form {form_num} in USD currency missing proof of payment - skipping"
            )
            continue

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

        items = []
        for item_num in range(1, MAX_ITEMS_PER_FORM + 1):
            item_name = _form_str(form_data.get(f"item_name_{form_num}_{item_num}"))
            if not item_name:
                break
            item_usage = _form_str(form_data.get(f"item_usage_{form_num}_{item_num}"))
            item_quantity = form_data.get(f"item_quantity_{form_num}_{item_num}")
            item_price = form_data.get(f"item_price_{form_num}_{item_num}")
            item_total = form_data.get(f"item_total_{form_num}_{item_num}")

            if item_name and item_usage and item_quantity and item_price:
                items.append(
                    SubmissionLineItem(
                        name=item_name,
                        usage=item_usage,
                        quantity=_form_int(item_quantity),
                        unit_price=_form_float(item_price),
                        total=_form_float(item_total),
                    )
                )

        if not items:
            continue

        invoice_extension = _file_extension(invoice_file.filename)
        safe_vendor_name = _safe_filename_component(vendor_name)
        invoice_filename = f"{form_num}_{safe_vendor_name}.{invoice_extension}"
        invoice_file_path = _build_session_file_path(session_folder, invoice_filename)
        await _save_uploaded_file(invoice_file, invoice_file_path)
        invoice_file_location = str(invoice_file_path)

        proof_of_payment_filename = proof_of_payment_location = None
        if currency == "USD" and isinstance(proof_of_payment_file, UploadFile):
            payment_extension = _file_extension(proof_of_payment_file.filename)
            proof_of_payment_filename = (
                f"{form_num}_proof_of_payment.{payment_extension}"
            )
            proof_of_payment_path = _build_session_file_path(
                session_folder, proof_of_payment_filename
            )
            await _save_uploaded_file(proof_of_payment_file, proof_of_payment_path)
            proof_of_payment_location = str(proof_of_payment_path)

        form_submission = SubmissionForm(
            form_number=form_num,
            vendor_name=vendor_name,
            currency="USD" if currency == "USD" else "CAD",
            invoice_filename=invoice_filename,
            invoice_file_location=invoice_file_location,
            proof_of_payment_filename=proof_of_payment_filename,
            proof_of_payment_location=proof_of_payment_location,
            subtotal_amount=subtotal_amount,
            discount_amount=discount_amount,
            hst_gst_amount=hst_gst_amount,
            shipping_amount=shipping_amount,
            total_amount=total_amount,
            us_total=us_total,
            usd_taxes=usd_taxes,
            canadian_amount=canadian_amount,
            items=items,
        )

        submitted_forms.append(form_submission)

    if submitted_forms:
        user_info = SubmissionUserInfo(
            name=name,
            email=email,
            e_transfer_email=e_transfer_email,
            address=address,
            team=team,
            signature=signature_filename,
        )
        user_info_payload = user_info.model_dump()
        submitted_forms_payload = [
            submission.model_dump() for submission in submitted_forms
        ]
        try:
            create_purchase_request(
                user_info_payload, submitted_forms_payload, session_folder
            )
        except Exception:
            logger.exception("Failed to create purchase request (continuing anyway)")

        try:
            create_expense_report(
                session_folder, user_info_payload, submitted_forms_payload
            )
        except Exception:
            logger.exception(
                "Failed to copy and populate expense report template (continuing anyway)"
            )

        # Create Google Drive folder and upload using one client instance
        drive_folder_url = ""
        drive_folder_id = ""
        drive_upload_success = False
        drive_client = GoogleDriveClient()
        try:
            try:
                success, drive_folder_url, drive_folder_id = (
                    drive_client.create_session_folder_structure(
                        session_folder, user_info_payload
                    )
                )
                if not success:
                    logger.warning("Failed to create Google Drive folder")
            except Exception:
                logger.exception(
                    "Failed to create Google Drive folder (continuing anyway)"
                )
            # Log to Google Sheets (with Drive folder URL)
            sheets_client: GoogleSheetsClient | None = None
            try:
                sheets_client = GoogleSheetsClient()
                sheets_client.log_purchase_request(
                    user_info_payload,
                    submitted_forms_payload,
                    session_folder,
                    drive_folder_url,
                )
            except Exception:
                logger.exception("Failed to log to Google Sheets (continuing anyway)")
            finally:
                if sheets_client is not None:
                    sheets_client.close()

            sentry_sdk.add_breadcrumb(
                category="external_api",
                message="Starting Google Drive upload",
                level="info",
            )
            try:
                drive_upload_success = drive_client.upload_session_folder(
                    session_folder, user_info_payload, drive_folder_id or None
                )
                logger.info(
                    f"Google Drive upload completed: {'✅ Success' if drive_upload_success else '❌ Failed'}"
                )
            except Exception as e:
                logger.exception(f"Unexpected error in upload task: {e}")
        finally:
            drive_client.close()

        if drive_upload_success:
            try:
                shutil.rmtree(session_folder)
                logger.info(f"🗑️ Cleaned up session folder: {session_folder}")
            except Exception:
                logger.exception(f"Failed to delete session folder {session_folder}")

    else:
        logger.warning("No forms were submitted (all forms were empty)")
        return RedirectResponse(
            url=f"/dashboard?user_email={email}&error=no_forms",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/success?drive_folder_id={drive_folder_id}&excel_file=purchase_request.xlsx&user_email={email}",
        status_code=303,
    )
