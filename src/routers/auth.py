"""
Authentication router for login/logout functionality.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.logging_utils import setup_logger
from db.schema import get_db
from models.user_service import get_user_by_email, is_user_profile_complete

# Set up logger
logger = setup_logger(__name__)

# Create router
router = APIRouter(tags=["authentication"])

# Templates setup
templates_dir = "templates"
templates = Jinja2Templates(directory=templates_dir)


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

        # If profile incomplete, go to edit profile page
        return RedirectResponse(
            url=f"/edit-profile?user_email={email}", status_code=303
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


def require_auth(request: Request):
    """Dependency to require authentication"""
    if not request.session.get("authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )
