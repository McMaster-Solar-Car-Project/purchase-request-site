"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.core.settings import MAX_FORMS, MAX_ITEMS_PER_FORM, get_settings
from src.db.schema import get_db
from src.models.user_service import (
    get_user_by_email,
    is_user_profile_complete,
)
from src.routers.utils import AuthRedirect, get_authenticated_user_email, templates
from src.services.submission_tracking import (
    claim_submission,
    finish_submission,
    submission_status,
)
from src.services.submission_workflow import process_submission_workflow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    request: Request,
    updated: bool = False,
    error: str | None = None,
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    settings = get_settings()
    user = get_user_by_email(db, authenticated_email)
    if not user:
        logger.error(f"User not found in database: {authenticated_email}")
        raise HTTPException(status_code=404, detail="User not found")

    error_message = None
    success_message = None
    profile_warning_message = None

    if error == "no_forms":
        error_message = "Please complete at least one invoice form before submitting. Make sure to fill in the vendor name, purchase date, upload an invoice file, and add at least one item."
    elif error == "invalid_items":
        error_message = "Please fully complete each item row before submitting."
    elif error == "too_many_items":
        error_message = f"Each invoice can include up to {MAX_ITEMS_PER_FORM} items."
    elif error == "below_minimum":
        error_message = (
            "Total Canadian amount must be at least "
            f"${settings.minimum_total_cad_amount:.2f} CAD."
        )
    elif error == "invalid_submission":
        error_message = (
            "Please check the highlighted purchase request details and try again."
        )
    elif error == "invalid_file":
        error_message = "Upload a valid PDF, PNG, JPG, JPEG, or GIF document."
    elif error == "file_too_large":
        error_message = "One or more uploads exceeded the configured size limit."
    elif error == "processing_failed":
        error_message = (
            "We could not generate all required submission files. Your uploads were "
            "retained for recovery."
        )
    elif error == "submission_needs_review":
        error_message = (
            "Your submission needs attention. Your draft has been kept. "
            "Check with finance before submitting again."
        )
    elif error == "submission_processing":
        error_message = "This batch is already being processed. Do not submit it again."
    elif updated:
        success_message = "Your profile has been updated successfully."

    profile_is_complete = is_user_profile_complete(user)
    if not profile_is_complete:
        profile_warning_message = (
            "Your profile is incomplete. Update your information before "
            "starting a purchase request."
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "title": "Purchase Request Site",
            "name": user.name,
            "email": user.email,
            "e_transfer_email": user.personal_email,
            "address": user.address,
            "team": user.team,
            "error_message": error_message,
            "success_message": success_message,
            "profile_warning_message": profile_warning_message,
            "profile_is_complete": profile_is_complete,
            "draft_owner_id": user.id,
            "max_items_per_form": MAX_ITEMS_PER_FORM,
            "max_forms": MAX_FORMS,
            "minimum_total_cad_amount": f"{settings.minimum_total_cad_amount:.2f}",
            "minimum_total_cad_cents": int(settings.minimum_total_cad_amount * 100),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/draft-submissions/{draft_id}")
def draft_submission_status(
    request: Request,
    draft_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        email = get_authenticated_user_email(request)
    except AuthRedirect:
        return JSONResponse(
            {"error": "login_required"},
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
    user = get_user_by_email(db, email)
    if user is None:
        return JSONResponse(
            {"error": "login_required"},
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        submission_status(db, user.id, str(draft_id)),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/submit-all-requests")
async def submit_all_requests(
    request: Request,
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    form_data = await request.form(
        max_files=MAX_FORMS * 2,
        max_fields=MAX_FORMS * (MAX_ITEMS_PER_FORM * 5 + 10),
    )
    try:
        raw_draft_id = form_data.get("draft_id")
        draft_id = None
        claim = None
        if raw_draft_id:
            try:
                draft_id = str(UUID(str(raw_draft_id)))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid draft ID") from exc
            claim = await run_in_threadpool(
                claim_submission,
                authenticated_email,
                draft_id,
                str(form_data.get("draft_owner_id", "")),
            )
            if not claim.claimed:
                if claim.status == "succeeded":
                    url = f"/success?submission_id={draft_id}"
                else:
                    error = (
                        "submission_processing"
                        if claim.status == "processing"
                        else "submission_needs_review"
                    )
                    url = f"/dashboard?error={error}"
                return RedirectResponse(url=url, status_code=303)
        request.session.pop("download_info", None)
        try:
            result = await process_submission_workflow(form_data, authenticated_email)
        except Exception:
            if claim and draft_id:
                await run_in_threadpool(
                    finish_submission, claim.user_id, draft_id, "needs_review"
                )
            raise
        if claim and draft_id:
            await run_in_threadpool(
                finish_submission, claim.user_id, draft_id, result.submission_status
            )
        if result.download_info is not None:
            request.session["download_info"] = result.download_info
        url = result.redirect_url
        if draft_id:
            if result.submission_status == "succeeded":
                url = f"/success?submission_id={draft_id}"
            elif result.submission_status == "needs_review":
                url = "/dashboard?error=submission_needs_review"
        return RedirectResponse(url=url, status_code=303)
    finally:
        await form_data.close()
