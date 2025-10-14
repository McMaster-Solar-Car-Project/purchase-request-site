from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.logging_utils import setup_logger
from db.schema import get_db
from models.user_service import get_user_by_email
from routers.auth import require_auth

logger = setup_logger(__name__)

router = APIRouter(tags=["dashboard"])
templates_dir = "templates"
templates = Jinja2Templates(directory=templates_dir)


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
