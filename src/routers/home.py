"""Home router for the post-login main menu."""

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.db.schema import get_db
from src.models.user_service import get_user_by_email, is_user_profile_complete
from src.routers.utils import get_authenticated_user_email, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["home"])


@router.get("/home")
def home(
    request: Request,
    updated: bool = False,
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    """Display the authenticated post-login main menu."""
    user = get_user_by_email(db, authenticated_email)
    if not user:
        logger.error(f"User not found in database: {authenticated_email}")
        raise HTTPException(status_code=404, detail="User not found")

    profile_is_complete = is_user_profile_complete(user)
    profile_warning_message = None
    success_message = None
    if not profile_is_complete:
        profile_warning_message = (
            "Your profile is incomplete. Update your information before submitting "
            "purchase requests."
        )
    elif updated:
        success_message = "Your profile has been updated successfully."

    return templates.TemplateResponse(
        request=request,
        name="main_menu.html",
        context={
            "request": request,
            "title": "Home - Purchase Request Site",
            "user_name": user.name,
            "user_email": user.email,
            "profile_is_complete": profile_is_complete,
            "profile_warning_message": profile_warning_message,
            "success_message": success_message,
        },
    )
