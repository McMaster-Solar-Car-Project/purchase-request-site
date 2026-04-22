"""Profile router for the /edit-profile endpoints."""

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.core.settings import get_settings
from src.db.schema import get_db
from src.image_processing import convert_signature_to_png
from src.models.user_info import ProfileUpdateInput
from src.models.user_service import (
    DEFAULT_NAME,
    DEFAULT_PERSONAL_EMAIL,
    get_user_by_email,
    get_user_signature_as_data_url,
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

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "request": request,
            "title": "Edit Profile - Purchase Request Site",
            "user": user,
            "signature_data_url": signature_data_url,
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
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    signature: UploadFile = File(None),
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
            current_password=current_password,
            new_password=new_password,
            confirm_password=confirm_password,
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

        # Handle signature update if provided
        if signature and signature.filename:
            # Read the signature file content
            signature_content = signature.file.read()
            if signature_content:
                # Create a temporary file to save the uploaded signature
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{signature.filename.split('.')[-1]}"
                ) as temp_file:
                    temp_file.write(signature_content)
                    temp_signature_path = temp_file.name

                # Create a temporary PNG file path
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".png"
                ) as temp_png_file:
                    temp_png_path = temp_png_file.name

                try:
                    # Convert signature to PNG
                    if convert_signature_to_png(temp_signature_path, temp_png_path):
                        # Read the converted PNG content
                        with open(temp_png_path, "rb") as png_file:
                            png_content = png_file.read()
                        # Save PNG content to database
                        user.signature_data = png_content
                        logger.info(
                            f"Signature converted to PNG and saved for user {profile_input.email}"
                        )
                    else:
                        logger.warning(
                            f"Failed to convert signature to PNG for user {profile_input.email}"
                        )
                        # Fallback: save original content
                        user.signature_data = signature_content
                finally:
                    # Clean up temporary files
                    try:
                        os.unlink(temp_signature_path)
                        os.unlink(temp_png_path)
                    except OSError:
                        pass  # Ignore cleanup errors

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
