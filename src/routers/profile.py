"""Profile router for the /edit-profile endpoints."""

import logging

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.db.schema import get_db
from src.models.user_service import (
    get_user_by_email,
    get_user_signature_as_data_url,
)
from src.routers.utils import get_authenticated_user_email, templates
from src.services.profile_updates import update_user_profile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


@router.get("/edit-profile")
def edit_profile_get(
    request: Request,
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    user = get_user_by_email(db, authenticated_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert signature to data URL for display
    signature_data_url = get_user_signature_as_data_url(user)
    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "request": request,
            "title": "Edit Profile - Purchase Request Site",
            "user": user,
            "signature_data_url": signature_data_url,
            "has_void_cheque": user.has_valid_void_cheque,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/edit-profile")
def edit_profile_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    personal_email: str = Form(...),
    team: str = Form(...),
    address: str = Form(...),
    signature: UploadFile = File(None),
    void_cheque: UploadFile = File(None),
    db: Session = Depends(get_db),
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    user = get_user_by_email(db, authenticated_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        result = update_user_profile(
            user,
            name=name,
            email=email,
            personal_email=personal_email,
            team=team,
            address=address,
            signature=signature,
            void_cheque=void_cheque,
        )

        db.commit()
        request.session["user_email"] = result.user_email

        return RedirectResponse(url="/home?updated=true", status_code=303)

    except ValueError as exc:
        logger.warning(f"Profile update rejected for {authenticated_email}: {exc}")
        db.rollback()
    except Exception:
        logger.exception(f"Error updating profile for {authenticated_email}")
        db.rollback()

    return RedirectResponse(
        url="/edit-profile?error=update_failed",
        status_code=303,
    )
