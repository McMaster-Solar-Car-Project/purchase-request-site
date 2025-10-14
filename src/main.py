import os
import secrets
import tempfile
from datetime import datetime

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from core.logging_utils import setup_logger
from db.schema import get_db, init_database
from image_processing import convert_signature_to_png
from models.user_service import (
    get_user_by_email,
    get_user_signature_as_data_url,
)
from request_logging import RequestLoggingMiddleware
from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.success import router as success_router

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions", "static", "templates", "excel_templates"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)


init_database()
app = FastAPI(title="Purchase Request Site")

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Generate a random secret key for this session (Note: users will be logged out on restart)
session_secret = secrets.token_urlsafe(32)

# Add session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Set up templates
templates_dir = "src/templates" if os.path.exists("src/templates") else "templates"
templates = Jinja2Templates(directory=templates_dir)

# Include routers
app.include_router(auth_router)
app.include_router(success_router)
app.include_router(dashboard_router)


def require_auth(request: Request):
    """Dependency to require authentication"""
    if not request.session.get("authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )


@app.get("/edit-profile")
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


@app.post("/edit-profile")
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


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
