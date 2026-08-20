"""
Dashboard router for the /dashboard and /submit-all-requests endpoints.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.core.settings import MAX_FORMS, MAX_ITEMS_PER_FORM
from src.db.schema import get_db
from src.models.user_service import (
    get_user_by_email,
    is_user_profile_complete,
)
from src.routers.utils import get_authenticated_user_email, templates
from src.services.submission_workflow import process_submission_workflow

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    request: Request,
    updated: bool = False,
    profile_incomplete: bool = False,
    error: str | None = None,
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
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
        error_message = "Total Canadian amount must be at least $100.00 CAD."
    elif error == "invalid_submission":
        error_message = (
            "Please check the highlighted purchase request details and try again."
        )
    elif error == "invalid_file":
        error_message = "Upload a valid PDF, PNG, JPG, JPEG, or GIF document."
    elif error == "file_too_large":
        error_message = (
            "Each file must be 10 MB or smaller. Combined uploads may be up to 100 MB."
        )
    elif updated:
        success_message = "Your profile has been updated successfully."

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
            "name": user.name,
            "email": user.email,
            "e_transfer_email": user.personal_email,
            "address": user.address,
            "team": user.team,
            "error_message": error_message,
            "success_message": success_message,
            "profile_warning_message": profile_warning_message,
            "profile_is_complete": profile_is_complete,
            "max_items_per_form": MAX_ITEMS_PER_FORM,
            "max_forms": MAX_FORMS,
        },
    )


@router.post("/submit-all-requests")
async def submit_all_requests(
    request: Request,
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    form_data = await request.form()
    try:
        request.session.pop("download_info", None)
        result = await process_submission_workflow(form_data, authenticated_email)
        if result.download_info is not None:
            request.session["download_info"] = result.download_info
        return RedirectResponse(url=result.redirect_url, status_code=303)
    finally:
        await form_data.close()
