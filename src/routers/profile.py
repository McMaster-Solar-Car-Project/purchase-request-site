"""Profile router for the /edit-profile endpoints."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.core.settings import get_settings
from src.db.schema import get_db
from src.image_processing import convert_signature_to_png_bytes
from src.models.user_info import ProfileUpdateInput
from src.models.user_service import (
    DEFAULT_NAME,
    DEFAULT_PERSONAL_EMAIL,
    get_user_by_email,
    get_user_signature_as_data_url,
    get_user_void_cheque_as_data_url,
)
from src.routers.utils import require_auth, templates

logger = setup_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["profile"])


@router.get("/edit-profile")
async def edit_profile_get(
    request: Request,
    user_email: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = get_user_by_email(db, user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert signature to data URL for display
    signature_data_url = get_user_signature_as_data_url(user)
    void_cheque_data_url = get_user_void_cheque_as_data_url(user)

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "request": request,
            "title": "Edit Profile - Purchase Request Site",
            "user": user,
            "signature_data_url": signature_data_url,
            "void_cheque_data_url": void_cheque_data_url,
            "google_api_key": settings.google_places_api_key,
        },
    )


@router.post("/edit-profile")
def edit_profile_post(
    request: Request,
    user_email: str,
    name: str = Form(...),
    email: str = Form(...),
    personal_email: str = Form(...),
    team: str = Form(...),
    address: str = Form(...),
    signature: UploadFile = File(None),
    void_cheque: UploadFile = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    try:
        # Get existing user
        user = get_user_by_email(db, user_email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile_input = ProfileUpdateInput(
            name=name,
            email=email,
            personal_email=personal_email,
            team=team,
            address=address,
        )

        # Update user information with validated input
        user.name = profile_input.name
        user.email = str(profile_input.email)
        user.personal_email = str(profile_input.personal_email)
        user.team = profile_input.team
        user.address = profile_input.address

        if user.name == DEFAULT_NAME:
            logger.warning("User is still using default name.")
        if user.personal_email == DEFAULT_PERSONAL_EMAIL:
            logger.warning("User is still using default personal email.")

        if signature and signature.filename:
            signature_content = signature.file.read()
            if not signature_content:
                raise ValueError("Uploaded signature file is empty")

            png_bytes = convert_signature_to_png_bytes(signature_content)
            if png_bytes is None:
                raise ValueError(
                    f"Failed to convert signature to PNG for user {profile_input.email}"
                )

            user.signature_data = png_bytes
            logger.info(
                f"Signature converted to PNG and saved for user {profile_input.email}"
            )

        if void_cheque and void_cheque.filename:
            void_cheque_content = void_cheque.file.read()
            if not void_cheque_content:
                raise ValueError("Uploaded void cheque file is empty")
            if not void_cheque_content.startswith(b"%PDF-"):
                raise ValueError("Void cheque must be a valid PDF file")
            user.void_cheque = void_cheque_content
            logger.info(f"Void cheque PDF saved for user {profile_input.email}")

        if not user.void_cheque:
            raise ValueError("Void cheque PDF is required")

        # Save changes to database
        db.commit()

        # Redirect back to dashboard with success message
        redirect_url = f"/dashboard?user_email={profile_input.email}&updated=true"
        return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.exception(f"Error updating profile for {user_email}: {e}")
        db.rollback()

        # Redirect back to edit form with error
        return RedirectResponse(
            url=f"/edit-profile?user_email={user_email}&error=update_failed",
            status_code=303,
        )
