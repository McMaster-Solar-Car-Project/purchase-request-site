"""
Profile router for the /edit-profile endpoints.
"""

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.logging_utils import setup_logger
from db.schema import get_db
from image_processing import convert_signature_to_png
from models.user_service import get_user_by_email, get_user_signature_as_data_url
from routers.utils import require_auth

logger = setup_logger(__name__)

router = APIRouter(tags=["profile"])

templates_dir = "templates"
templates = Jinja2Templates(directory=templates_dir)


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
        "edit_profile.html",
        {
            "request": request,
            "title": "Edit Profile - Purchase Request Site",
            "user": user,
            "signature_data_url": signature_data_url,
            "google_api_key": os.getenv("GOOGLE_PLACES_API_KEY"),
        },
    )


@router.post("/edit-profile")
async def edit_profile_post(
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

        # Update user information (strip whitespace from all fields)
        user.name = name.strip()
        user.email = email.strip()
        user.personal_email = personal_email.strip()
        user.team = team.strip()
        user.address = address.strip()

        # Handle password change if provided (strip whitespace from passwords too)
        current_password = current_password.strip()
        new_password = new_password.strip()
        confirm_password = confirm_password.strip()

        password_error = None
        if new_password or current_password:
            if not current_password:
                password_error = "Current password is required to change password"
            elif not new_password:
                password_error = "New password cannot be empty"
            elif len(new_password) < 5:
                password_error = "New password must be at least 5 characters"
            elif new_password != confirm_password:
                password_error = "New password and confirmation do not match"
            elif user.password != current_password:
                password_error = "Current password is incorrect"
            else:
                # All validations passed, update password
                user.password = new_password

        if password_error:
            logger.warning(f"Password change failed for {email}: {password_error}")
            # You could redirect with error, but for now we'll continue with other updates
            # and show the error in logs

        # Handle signature update if provided
        if signature and signature.filename:
            # Read the signature file content
            signature_content = await signature.read()
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
                            f"Signature converted to PNG and saved for user {email}"
                        )
                    else:
                        logger.warning(
                            f"Failed to convert signature to PNG for user {email}"
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
        redirect_url = f"/dashboard?user_email={email}&updated=true"
        return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.exception(f"Error updating profile for {user_email}: {str(e)}")
        db.rollback()

        # Redirect back to edit form with error
        return RedirectResponse(
            url=f"/edit-profile?user_email={user_email}&error=update_failed",
            status_code=303,
        )
