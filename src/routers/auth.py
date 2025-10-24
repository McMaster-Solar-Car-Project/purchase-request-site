"""
Authentication router for the /login and /logout endpoints.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.db.schema import get_db
from src.models.user_service import get_user_by_email, is_user_profile_complete
from src.routers.utils import templates

# Set up logger
logger = setup_logger(__name__)

# Create router
router = APIRouter(tags=["authentication"])


@router.get("/login")
async def login_page(request: Request, error: str = None):
    """Display login page"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error_message": "Invalid email or password"
            if error == "invalid"
            else None,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Handle login form submission"""
    # Check user database
    user = get_user_by_email(db, email)
    if user and user.password == password:
        request.session["authenticated"] = True
        request.session["user_email"] = email
        logger.info(f"🔐 User login: {user.name} ({email})")

        # Check if user profile is complete
        if is_user_profile_complete(user):
            # Redirect directly to dashboard
            return RedirectResponse(
                url=f"/dashboard?user_email={email}",
                status_code=303,
            )

        # Default Val Check
        return RedirectResponse(
            url=f"/edit-profile?user_email={email}&error=default_values",
            status_code=303,
        )
    else:
        logger.warning(f"🚫 Failed login attempt: {email}")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error_message": "Invalid email or password",
                "email": email,
            },
        )


@router.get("/logout")
async def logout(request: Request):
    """Handle user logout"""
    request.session.clear()
    logger.info("🔓 User logged out")
    return RedirectResponse(url="/login", status_code=303)
