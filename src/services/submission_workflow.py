"""Submission workflow orchestration for purchase request batches."""

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlencode

import sentry_sdk
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile

from src.core.settings import MAX_FORMS, MAX_ITEMS_PER_FORM, get_settings
from src.data_processing import create_expense_report, create_purchase_request
from src.db.schema import SessionLocal, User
from src.google_drive import GoogleDriveClient
from src.google_sheets import GoogleSheetsClient
from src.models.submissions import Invoice, SubmissionLineItem
from src.models.user_info import SubmissionUserInfo
from src.models.user_service import (
    get_user_by_email,
    is_user_profile_complete,
    save_signature_to_file,
    save_void_cheque_to_file,
)

logger = logging.getLogger(__name__)

MONEY_QUANTUM = Decimal("0.01")
UPLOAD_CHUNK_BYTES = 1024 * 1024
ITEM_FIELD_PATTERN = re.compile(
    r"^item_(?:name|usage|quantity|price)_(?P<form>\d+)_(?P<item>\d+)$"
)
DOCUMENT_UPLOAD_TYPES = {
    ".pdf": ({"application/pdf"}, (b"%PDF-",)),
    ".png": ({"image/png"}, (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ({"image/jpeg"}, (b"\xff\xd8\xff",)),
    ".jpeg": ({"image/jpeg"}, (b"\xff\xd8\xff",)),
    ".gif": ({"image/gif"}, (b"GIF87a", b"GIF89a")),
}


class SubmissionValidationError(Exception):
    """User-correctable validation failure while parsing a dashboard submission."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SubmissionOutputResult:
    drive_folder_id: str = ""
    drive_upload_success: bool = False
    purchase_request_filename: str = ""
    expense_report_success: bool = False
    sheets_log_success: bool = False


@dataclass(frozen=True)
class SubmissionWorkflowResult:
    redirect_url: str
    download_info: dict[str, str] | None = None


@dataclass
class UploadBudget:
    max_bytes: int
    used_bytes: int = 0

    def consume(self, byte_count: int) -> None:
        self.used_bytes += byte_count
        if self.used_bytes > self.max_bytes:
            raise SubmissionValidationError(
                "file_too_large",
                "Combined invoice uploads exceed the configured limit",
            )


def _form_str(value: object, default: str = "") -> str:
    """Coerce multipart form field to str; ignore accidental file parts."""
    if value is None or isinstance(value, UploadFile):
        return default
    return str(value).strip()


def _uploaded_file(value: object) -> UploadFile | None:
    if isinstance(value, UploadFile) and value.filename:
        return value
    return None


def _validated_document_extension(file: UploadFile, field_label: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    upload_type = DOCUMENT_UPLOAD_TYPES.get(suffix)
    if upload_type is None:
        raise SubmissionValidationError(
            "invalid_file",
            f"{field_label} must be a PDF, PNG, JPG, JPEG, or GIF file",
        )

    allowed_content_types, _ = upload_type
    content_type = (file.content_type or "").lower()
    if content_type not in allowed_content_types:
        raise SubmissionValidationError(
            "invalid_file",
            f"{field_label} has an unsupported content type",
        )
    return suffix.removeprefix(".")


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


def _build_session_file_path(
    session_folder: str, filename: str, sessions_root: Path
) -> Path:
    sessions_root = sessions_root.resolve()
    session_path = Path(session_folder).resolve()
    if not session_path.is_relative_to(sessions_root):
        raise ValueError("Invalid session path outside sessions root")
    destination = (session_path / filename).resolve()
    if not destination.is_relative_to(session_path):
        raise ValueError("Invalid destination path outside session folder")
    return destination


async def _save_uploaded_file(
    file: UploadFile,
    destination: Path,
    extension: str,
    upload_budget: UploadBudget,
    sessions_root: Path,
    max_file_bytes: int,
) -> None:
    if not destination.resolve().is_relative_to(sessions_root.resolve()):
        raise ValueError("Invalid destination path outside sessions root")

    file_bytes = 0
    header = b""
    try:
        with destination.open("wb") as output_file:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                file_bytes += len(chunk)
                if file_bytes > max_file_bytes:
                    raise SubmissionValidationError(
                        "file_too_large",
                        f"{file.filename or 'Upload'} exceeds the configured file limit",
                    )
                upload_budget.consume(len(chunk))
                if len(header) < 8:
                    header = (header + chunk)[:8]
                output_file.write(chunk)

        allowed_headers = DOCUMENT_UPLOAD_TYPES[f".{extension}"][1]
        if not any(header.startswith(prefix) for prefix in allowed_headers):
            raise SubmissionValidationError(
                "invalid_file",
                f"{file.filename or 'Upload'} does not match its file type",
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise


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
    )


def create_session_folder(name: str, sessions_root: Path) -> str:
    """Create a unique session folder for generated files."""
    safe_name = _safe_filename_component(name).lower()
    sessions_root = sessions_root.resolve()
    sessions_root.mkdir(parents=True, exist_ok=True)
    session_folder = Path(
        tempfile.mkdtemp(prefix=f"{safe_name}_", dir=sessions_root)
    ).resolve()
    if not session_folder.is_relative_to(sessions_root):
        raise ValueError("Invalid session folder path")
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
    form_data: FormData,
    form_num: int,
    session_folder: str,
    upload_budget: UploadBudget,
    sessions_root: Path,
    max_file_bytes: int,
) -> Invoice | None:
    vendor_name = _form_str(form_data.get(f"vendor_name_{form_num}"))
    if not vendor_name:
        return None

    purchase_date = _form_str(form_data.get(f"purchase_date_{form_num}"))

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

    items = _parse_line_items(form_data, form_num)
    item_subtotal = sum((item.total for item in items), start=Decimal(0)).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )

    if currency == "USD":
        total_cad_amount = _form_str(form_data.get(f"total_cad_amount_{form_num}"))
        us_subtotal = item_subtotal
        us_additional_fees = _form_str(form_data.get(f"us_additional_fees_{form_num}"))
        subtotal_amount = discount_amount = hst_gst_amount = shipping_amount = 0
    else:
        subtotal_amount = item_subtotal
        discount_amount = _form_str(form_data.get(f"discount_amount_{form_num}"))
        hst_gst_amount = _form_str(form_data.get(f"hst_gst_amount_{form_num}"))
        shipping_amount = _form_str(form_data.get(f"shipping_amount_{form_num}"))
        total_cad_amount = 0
        us_subtotal = us_additional_fees = 0

    invoice_extension = _validated_document_extension(
        invoice_file, f"Form {form_num} invoice"
    )
    safe_vendor_name = _safe_filename_component(vendor_name)
    invoice_filename = f"{form_num}_{safe_vendor_name}.{invoice_extension}"
    invoice_file_path = _build_session_file_path(
        session_folder, invoice_filename, sessions_root
    )

    proof_of_payment_filename = proof_of_payment_location = None
    proof_of_payment_path = None
    if currency == "USD" and proof_of_payment_file is not None:
        payment_extension = _validated_document_extension(
            proof_of_payment_file, f"Form {form_num} proof of payment"
        )
        proof_of_payment_filename = f"{form_num}_proof_of_payment.{payment_extension}"
        proof_of_payment_path = _build_session_file_path(
            session_folder, proof_of_payment_filename, sessions_root
        )
        proof_of_payment_location = str(proof_of_payment_path)

    try:
        form_submission = Invoice.model_validate(
            {
                "form_number": form_num,
                "vendor_name": vendor_name,
                "purchase_date": purchase_date,
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

    if not form_submission.is_usd:
        calculated_total = (
            form_submission.subtotal_amount
            - form_submission.discount_amount
            + form_submission.hst_gst_amount
            + form_submission.shipping_amount
        )
        form_submission = form_submission.model_copy(
            update={
                "total_cad_amount": max(Decimal(0), calculated_total).quantize(
                    MONEY_QUANTUM, rounding=ROUND_HALF_UP
                )
            }
        )

    await _save_uploaded_file(
        invoice_file,
        invoice_file_path,
        invoice_extension,
        upload_budget,
        sessions_root,
        max_file_bytes,
    )
    if proof_of_payment_file is not None and proof_of_payment_path is not None:
        await _save_uploaded_file(
            proof_of_payment_file,
            proof_of_payment_path,
            payment_extension,
            upload_budget,
            sessions_root,
            max_file_bytes,
        )

    return form_submission


async def _run_submission_outputs(
    user_info: SubmissionUserInfo,
    submitted_forms: list[Invoice],
    session_folder: str,
) -> SubmissionOutputResult:
    purchase_request_filename = ""
    try:
        purchase_request_filename = await run_in_threadpool(
            create_purchase_request, user_info, submitted_forms, session_folder
        )
    except Exception:
        logger.exception("Failed to create purchase request (continuing anyway)")

    expense_report_success = False
    try:
        expense_report_success = bool(
            await run_in_threadpool(
                create_expense_report, session_folder, user_info, submitted_forms
            )
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
        sheets_log_success = False
        try:
            sheets_client = GoogleSheetsClient()
            sheets_log_success = await run_in_threadpool(
                sheets_client.log_purchase_request,
                user_info,
                submitted_forms,
                drive_folder_url=drive_folder_url,
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
        purchase_request_filename=purchase_request_filename,
        expense_report_success=expense_report_success,
        sheets_log_success=sheets_log_success,
    )


async def _load_submission_user(authenticated_email: str):
    user = await run_in_threadpool(_load_user_in_new_session, authenticated_email)
    if not user:
        logger.error(f"User not found in database: {authenticated_email}")
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _profile_completion_redirect(
    user,
    authenticated_email: str,
) -> SubmissionWorkflowResult | None:
    if not is_user_profile_complete(user):
        logger.warning(
            f"Profile incomplete for user {authenticated_email}; blocking submission"
        )
        return SubmissionWorkflowResult(
            redirect_url=_dashboard_url(profile_incomplete="true")
        )
    return None


async def _save_profile_documents(
    user, session_folder: str, authenticated_email: str, sessions_root: Path
) -> None:
    signature_path = _build_session_file_path(
        session_folder, "signature.png", sessions_root
    )
    if not await run_in_threadpool(save_signature_to_file, user, str(signature_path)):
        logger.warning(f"Could not save signature for user {authenticated_email}")

    void_cheque_path = _build_session_file_path(
        session_folder, "void_cheque.pdf", sessions_root
    )
    if not await run_in_threadpool(
        save_void_cheque_to_file, user, str(void_cheque_path)
    ):
        logger.warning(f"Could not save void cheque for user {authenticated_email}")


async def _parse_submitted_forms(
    form_data: FormData,
    session_folder: str,
    sessions_root: Path,
    max_file_bytes: int,
    max_submission_bytes: int,
) -> list[Invoice]:
    submitted_forms: list[Invoice] = []
    upload_budget = UploadBudget(max_bytes=max_submission_bytes)
    for form_num in range(1, MAX_FORMS + 1):
        form_submission = await _parse_invoice_form(
            form_data,
            form_num,
            session_folder,
            upload_budget,
            sessions_root,
            max_file_bytes,
        )
        if form_submission is not None:
            submitted_forms.append(form_submission)
    return submitted_forms


async def _validated_submitted_forms(
    form_data: FormData,
    session_folder: str,
    sessions_root: Path,
    max_file_bytes: int,
    max_submission_bytes: int,
    minimum_total_cad_amount: Decimal,
) -> list[Invoice] | SubmissionWorkflowResult:
    try:
        submitted_forms = await _parse_submitted_forms(
            form_data,
            session_folder,
            sessions_root,
            max_file_bytes,
            max_submission_bytes,
        )
    except SubmissionValidationError as e:
        logger.warning(str(e))
        await _cleanup_session_folder(session_folder)
        return SubmissionWorkflowResult(redirect_url=_dashboard_url(error=e.error_code))

    if not submitted_forms:
        logger.warning("No forms were submitted (all forms were empty)")
        await _cleanup_session_folder(session_folder)
        return SubmissionWorkflowResult(redirect_url=_dashboard_url(error="no_forms"))

    total_cad_amount = sum(form.total_cad_amount for form in submitted_forms)
    if total_cad_amount < minimum_total_cad_amount:
        logger.warning(f"Submission below minimum CAD amount: ${total_cad_amount:.2f}")
        await _cleanup_session_folder(session_folder)
        return SubmissionWorkflowResult(
            redirect_url=_dashboard_url(error="below_minimum")
        )

    return submitted_forms


async def _complete_submission(
    user,
    submitted_forms: list[Invoice],
    session_folder: str,
) -> SubmissionWorkflowResult:
    user_info = _build_submission_user_info(user)
    output_result = await _run_submission_outputs(
        user_info, submitted_forms, session_folder
    )

    download_info = None
    if (
        output_result.drive_upload_success
        and output_result.drive_folder_id
        and output_result.purchase_request_filename
    ):
        download_info = {
            "drive_folder_id": output_result.drive_folder_id,
            "excel_file": output_result.purchase_request_filename,
        }

    generated_outputs_complete = bool(output_result.purchase_request_filename) and (
        output_result.expense_report_success
    )
    if (
        generated_outputs_complete
        and output_result.drive_upload_success
        and output_result.sheets_log_success
    ):
        await _cleanup_session_folder(session_folder)
    else:
        logger.error(
            "Submission outputs are incomplete; retaining local session folder "
            f"{session_folder} (drive={output_result.drive_upload_success}, "
            f"sheets={output_result.sheets_log_success})"
        )

    if not generated_outputs_complete:
        return SubmissionWorkflowResult(
            redirect_url=_dashboard_url(error="processing_failed")
        )

    return SubmissionWorkflowResult(
        redirect_url="/success",
        download_info=download_info,
    )


async def process_submission_workflow(
    form_data: FormData,
    authenticated_email: str,
) -> SubmissionWorkflowResult:
    settings = get_settings()
    sessions_root = settings.sessions_root.resolve()

    sentry_sdk.add_breadcrumb(
        category="purchase_flow",
        message="Started submission processing",
        level="info",
    )

    user = await _load_submission_user(authenticated_email)
    incomplete_result = _profile_completion_redirect(user, authenticated_email)
    if incomplete_result is not None:
        return incomplete_result

    session_folder = await run_in_threadpool(
        create_session_folder, user.name, sessions_root
    )
    await _save_profile_documents(
        user, session_folder, authenticated_email, sessions_root
    )

    forms_result = await _validated_submitted_forms(
        form_data,
        session_folder,
        sessions_root,
        settings.max_upload_file_bytes,
        settings.max_submission_upload_bytes,
        settings.minimum_total_cad_amount,
    )
    if isinstance(forms_result, SubmissionWorkflowResult):
        return forms_result

    return await _complete_submission(user, forms_result, session_folder)
