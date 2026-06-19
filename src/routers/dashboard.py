"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import sentry_sdk
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile

from src.core.logging_utils import setup_logger
from src.data_processing import create_expense_report, create_purchase_request
from src.db.schema import SessionLocal, User, get_db
from src.google_drive import GoogleDriveClient
from src.google_sheets import GoogleSheetsClient
from src.models.submissions import (
    Invoice,
    SubmissionLineItem,
)
from src.models.user_info import SubmissionUserInfo
from src.models.user_service import (
    get_user_by_email,
    is_user_profile_complete,
    save_signature_to_file,
    save_void_cheque_to_file,
)
from src.routers.utils import get_authenticated_user_email, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])
MAX_FORMS = 10
MAX_ITEMS_PER_FORM = 15
MIN_TOTAL_CAD_AMOUNT = 100.0
SESSIONS_ROOT = Path("sessions").resolve()
ITEM_FIELD_PATTERN = re.compile(
    r"^item_(?:name|usage|quantity|price)_(?P<form>\d+)_(?P<item>\d+)$"
)


class SubmissionValidationError(Exception):
    """User-correctable validation failure while parsing a dashboard submission."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SubmissionOutputResult:
    drive_folder_id: str = ""
    drive_upload_success: bool = False


def _form_str(value: object, default: str = "") -> str:
    """Coerce multipart form field to str; ignore accidental file parts."""
    if value is None or isinstance(value, UploadFile):
        return default
    return str(value).strip()


def _uploaded_file(value: object) -> UploadFile | None:
    if isinstance(value, UploadFile) and value.filename:
        return value
    return None


def _file_extension(filename: str | None, default: str = "pdf") -> str:
    if not filename or "." not in filename:
        return default
    return filename.rsplit(".", 1)[-1]


def _safe_filename_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "file"


def _dashboard_url(**params: str) -> str:
    return "/dashboard" if not params else f"/dashboard?{urlencode(params)}"


def _posted_item_numbers(form_data: FormData, form_num: int) -> set[int]:
    item_numbers: set[int] = set()
    for key in form_data:
        match = ITEM_FIELD_PATTERN.match(key)
        if not match or int(match.group("form")) != form_num:
            continue
        if _form_str(form_data.get(key)):
            item_numbers.add(int(match.group("item")))
    return item_numbers


def _parse_line_items(form_data: FormData, form_num: int) -> list[SubmissionLineItem]:
    item_numbers = _posted_item_numbers(form_data, form_num)
    overflow_items = [
        item_num for item_num in item_numbers if item_num > MAX_ITEMS_PER_FORM
    ]
    if overflow_items:
        raise SubmissionValidationError(
            "too_many_items",
            f"Form {form_num} has more than {MAX_ITEMS_PER_FORM} item rows",
        )

    items: list[SubmissionLineItem] = []
    for item_num in sorted(item_numbers):
        item_name = _form_str(form_data.get(f"item_name_{form_num}_{item_num}"))
        item_usage = _form_str(form_data.get(f"item_usage_{form_num}_{item_num}"))
        item_quantity = _form_str(form_data.get(f"item_quantity_{form_num}_{item_num}"))
        item_price = _form_str(form_data.get(f"item_price_{form_num}_{item_num}"))

        if not (item_name and item_usage and item_quantity and item_price):
            raise SubmissionValidationError(
                "invalid_items",
                f"Form {form_num} item {item_num} is incomplete",
            )

        try:
            items.append(
                SubmissionLineItem.model_validate(
                    {
                        "name": item_name,
                        "usage": item_usage,
                        "quantity": item_quantity,
                        "unit_price": item_price,
                    }
                )
            )
        except ValidationError as e:
            raise SubmissionValidationError(
                "invalid_items",
                f"Form {form_num} item {item_num} is invalid: {e.errors()}",
            ) from e

    if not items:
        raise SubmissionValidationError(
            "invalid_items", f"Form {form_num} must include at least one item"
        )
    return items


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
    data = await file.read()
    await run_in_threadpool(destination.write_bytes, data)


async def _cleanup_session_folder(session_folder: str) -> None:
    try:
        await run_in_threadpool(shutil.rmtree, session_folder)
        logger.info(f"Cleaned up session folder: {session_folder}")
    except FileNotFoundError:
        return
    except Exception:
        logger.exception(f"Failed to delete session folder {session_folder}")


def _build_submission_user_info(user: User) -> SubmissionUserInfo:
    return SubmissionUserInfo(
        name=user.name,
        email=user.email,
        e_transfer_email=user.personal_email,
        address=user.address,
        team=user.team,
        signature="signature.png",
    )


@router.get("/dashboard")
def dashboard(
    request: Request,
    user_email: str | None = None,
    updated: bool = False,
    profile_incomplete: bool = False,
    error: str | None = None,
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    # Legacy user_email query params are accepted but ignored for authorization.
    user = get_user_by_email(db, authenticated_email)
    if not user:
        logger.error(f"User not found in database: {authenticated_email}")
        raise HTTPException(status_code=404, detail="User not found")

    error_message = None
    success_message = None
    profile_warning_message = None

    if error == "no_forms":
        error_message = "Please complete at least one invoice form before submitting. Make sure to fill in the vendor name, upload an invoice file, and add at least one item."
    elif error == "invalid_items":
        error_message = "Please fully complete each item row before submitting."
    elif error == "too_many_items":
        error_message = f"Each invoice can include up to {MAX_ITEMS_PER_FORM} items."
    elif error == "below_minimum":
        error_message = "Total Canadian amount must be at least $100.00 CAD."
    elif error == "invalid_submission":
        error_message = (
            "Please check the highlighted purchase request details and try again."
        )
    elif updated:
        success_message = "Your profile has been updated successfully!"

    profile_is_complete = is_user_profile_complete(user)
    if profile_incomplete or not profile_is_complete:
        profile_warning_message = (
            "Your profile is incomplete. Please update your information before "
            "submitting purchase requests."
        )

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
            "profile_warning_message": profile_warning_message,
            "profile_is_complete": profile_is_complete,
        },
    )


def create_session_folder(name: str) -> str:
    """Create a timestamped session folder for generated files."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = _safe_filename_component(name).lower()
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    session_folder = (SESSIONS_ROOT / f"{safe_name}_{timestamp}").resolve()
    if not session_folder.is_relative_to(SESSIONS_ROOT):
        raise ValueError("Invalid session folder path")
    session_folder.mkdir(parents=True, exist_ok=True)
    return str(session_folder)


def _load_user_in_new_session(email: str):
    # Used from a threadpool worker. The request-scoped Session from Depends(get_db)
    # is not safe to share across threads, so we open and close our own session here.
    db = SessionLocal()
    try:
        return get_user_by_email(db, email)
    finally:
        db.close()


async def _parse_invoice_form(
    form_data: FormData, form_num: int, session_folder: str
) -> Invoice | None:
    vendor_name = _form_str(form_data.get(f"vendor_name_{form_num}"))
    if not vendor_name:
        return None

    sentry_sdk.add_breadcrumb(
        category="purchase_flow",
        message=f"Processing form {form_num}: {vendor_name}",
        level="info",
    )

    invoice_file = _uploaded_file(form_data.get(f"invoice_file_{form_num}"))
    if invoice_file is None:
        raise SubmissionValidationError(
            "invalid_submission", f"Form {form_num} is missing an invoice file"
        )

    currency = _form_str(form_data.get(f"currency_{form_num}"), "CAD")
    if currency not in {"CAD", "USD"}:
        raise SubmissionValidationError(
            "invalid_submission", f"Form {form_num} has unsupported currency {currency}"
        )

    proof_of_payment_file = _uploaded_file(
        form_data.get(f"proof_of_payment_{form_num}")
    )
    if currency == "USD" and proof_of_payment_file is None:
        raise SubmissionValidationError(
            "invalid_submission", f"Form {form_num} is missing proof of payment"
        )

    total_cad_amount = _form_str(form_data.get(f"total_cad_amount_{form_num}"))
    if currency == "USD":
        us_subtotal = _form_str(form_data.get(f"us_subtotal_{form_num}"))
        us_additional_fees = _form_str(form_data.get(f"us_additional_fees_{form_num}"))
        subtotal_amount = discount_amount = hst_gst_amount = shipping_amount = 0
    else:
        subtotal_amount = _form_str(form_data.get(f"subtotal_amount_{form_num}"))
        discount_amount = _form_str(form_data.get(f"discount_amount_{form_num}"))
        hst_gst_amount = _form_str(form_data.get(f"hst_gst_amount_{form_num}"))
        shipping_amount = _form_str(form_data.get(f"shipping_amount_{form_num}"))
        us_subtotal = us_additional_fees = 0

    items = _parse_line_items(form_data, form_num)

    invoice_extension = _file_extension(invoice_file.filename)
    safe_vendor_name = _safe_filename_component(vendor_name)
    invoice_filename = f"{form_num}_{safe_vendor_name}.{invoice_extension}"
    invoice_file_path = _build_session_file_path(session_folder, invoice_filename)

    proof_of_payment_filename = proof_of_payment_location = None
    proof_of_payment_path = None
    if currency == "USD" and proof_of_payment_file is not None:
        payment_extension = _file_extension(proof_of_payment_file.filename)
        proof_of_payment_filename = f"{form_num}_proof_of_payment.{payment_extension}"
        proof_of_payment_path = _build_session_file_path(
            session_folder, proof_of_payment_filename
        )
        proof_of_payment_location = str(proof_of_payment_path)

    try:
        form_submission = Invoice.model_validate(
            {
                "form_number": form_num,
                "vendor_name": vendor_name,
                "is_usd": currency == "USD",
                "invoice_filename": invoice_filename,
                "invoice_file_location": str(invoice_file_path),
                "proof_of_payment_filename": proof_of_payment_filename,
                "proof_of_payment_location": proof_of_payment_location,
                "subtotal_amount": subtotal_amount,
                "discount_amount": discount_amount,
                "hst_gst_amount": hst_gst_amount,
                "shipping_amount": shipping_amount,
                "total_cad_amount": total_cad_amount,
                "us_subtotal": us_subtotal,
                "us_additional_fees": us_additional_fees,
                "items": items,
            }
        )
    except ValidationError as e:
        raise SubmissionValidationError(
            "invalid_submission", f"Form {form_num} is invalid: {e.errors()}"
        ) from e

    await _save_uploaded_file(invoice_file, invoice_file_path)
    if proof_of_payment_file is not None and proof_of_payment_path is not None:
        await _save_uploaded_file(proof_of_payment_file, proof_of_payment_path)

    return form_submission


async def _run_submission_outputs(
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
    session_folder: str,
) -> SubmissionOutputResult:
    try:
        await run_in_threadpool(
            create_purchase_request, user_info, submitted_forms, session_folder
        )
    except Exception:
        logger.exception("Failed to create purchase request (continuing anyway)")

    try:
        await run_in_threadpool(
            create_expense_report, session_folder, user_info, submitted_forms
        )
    except Exception:
        logger.exception(
            "Failed to copy and populate expense report template (continuing anyway)"
        )

    drive_folder_url = ""
    drive_folder_id = ""
    drive_upload_success = False
    drive_client = GoogleDriveClient()
    try:
        try:
            success, drive_folder_url, drive_folder_id = await run_in_threadpool(
                drive_client.create_session_folder_structure,
                session_folder,
                user_info,
            )
            if not success:
                logger.warning("Failed to create Google Drive folder")
        except Exception:
            logger.exception("Failed to create Google Drive folder (continuing anyway)")

        sheets_client: GoogleSheetsClient | None = None
        try:
            sheets_client = GoogleSheetsClient()
            await run_in_threadpool(
                sheets_client.log_purchase_request,
                user_info,
                submitted_forms,
                session_folder,
                drive_folder_url,
            )
        except Exception:
            logger.exception("Failed to log to Google Sheets (continuing anyway)")
        finally:
            if sheets_client is not None:
                await run_in_threadpool(sheets_client.close)

        sentry_sdk.add_breadcrumb(
            category="external_api",
            message="Starting Google Drive upload",
            level="info",
        )
        try:
            drive_upload_success = await run_in_threadpool(
                drive_client.upload_session_folder,
                session_folder,
                user_info,
                drive_folder_id or None,
            )
            logger.info(
                "Google Drive upload completed: "
                f"{'Success' if drive_upload_success else 'Failed'}"
            )
        except Exception:
            logger.exception("Unexpected error in upload task")
    finally:
        await run_in_threadpool(drive_client.close)

    return SubmissionOutputResult(
        drive_folder_id=drive_folder_id,
        drive_upload_success=drive_upload_success,
    )


@router.post("/submit-all-requests")
async def submit_all_requests(
    request: Request,
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    form_data = await request.form()
    request.session.pop("download_info", None)

    sentry_sdk.add_breadcrumb(
        category="purchase_flow",
        message="Started submission processing",
        level="info",
    )

    user = await run_in_threadpool(_load_user_in_new_session, authenticated_email)
    if not user:
        logger.error(f"User not found in database: {authenticated_email}")
        raise HTTPException(status_code=404, detail="User not found")
    if not is_user_profile_complete(user):
        logger.warning(
            f"Profile incomplete for user {authenticated_email}; blocking submission"
        )
        return RedirectResponse(
            url=_dashboard_url(profile_incomplete="true"),
            status_code=303,
        )

    session_folder = await run_in_threadpool(create_session_folder, user.name)
    signature_filename = "signature.png"
    signature_path = _build_session_file_path(session_folder, signature_filename)
    if not await run_in_threadpool(save_signature_to_file, user, str(signature_path)):
        logger.warning(f"Could not save signature for user {authenticated_email}")

    void_cheque_filename = "void_cheque.pdf"
    void_cheque_path = _build_session_file_path(session_folder, void_cheque_filename)
    if not await run_in_threadpool(
        save_void_cheque_to_file, user, str(void_cheque_path)
    ):
        logger.warning(f"Could not save void cheque for user {authenticated_email}")

    submitted_forms: list[Invoice] = []
    try:
        for form_num in range(1, MAX_FORMS + 1):
            form_submission = await _parse_invoice_form(
                form_data, form_num, session_folder
            )
            if form_submission is not None:
                submitted_forms.append(form_submission)
    except SubmissionValidationError as e:
        logger.warning(str(e))
        await _cleanup_session_folder(session_folder)
        return RedirectResponse(
            url=_dashboard_url(error=e.error_code),
            status_code=303,
        )

    if not submitted_forms:
        logger.warning("No forms were submitted (all forms were empty)")
        await _cleanup_session_folder(session_folder)
        return RedirectResponse(
            url=_dashboard_url(error="no_forms"),
            status_code=303,
        )

    total_cad_amount = sum(form.total_cad_amount for form in submitted_forms)
    if total_cad_amount < MIN_TOTAL_CAD_AMOUNT:
        logger.warning(f"Submission below minimum CAD amount: ${total_cad_amount:.2f}")
        await _cleanup_session_folder(session_folder)
        return RedirectResponse(
            url=_dashboard_url(error="below_minimum"),
            status_code=303,
        )

    user_info = _build_submission_user_info(user)
    output_result = await _run_submission_outputs(
        user_info, submitted_forms, session_folder
    )

    if output_result.drive_upload_success:
        if output_result.drive_folder_id:
            request.session["download_info"] = {
                "drive_folder_id": output_result.drive_folder_id,
                "excel_file": "purchase_request.xlsx",
            }
        await _cleanup_session_folder(session_folder)

    return RedirectResponse(url="/success", status_code=303)
