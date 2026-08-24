"""
Authentication router for the /login and /logout endpoints.
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.db.schema import get_db
from src.models.user_service import get_user_by_email
from src.routers.utils import limiter, templates

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["authentication"])


@router.get("/login")
def login_page(request: Request, error: str | None = None):
    """Display login page"""

    error_messages = {
        "ratelimit": "Too many login attempts. Please try again in 60 seconds.",
        "invalid": "Invalid email or password.",
    }

    error_message = None if error is None else error_messages.get(error)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error_message": error_message,
        },
    )


@router.post("/login")
@limiter.limit("5/minute")  # Limit to 5 login attempts per minute per IP
def login(
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

        return RedirectResponse(url="/home", status_code=303)
    else:
        logger.warning(f"🚫 Failed login attempt: {email}")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "error_message": "Invalid email or password",
                "email": email,
            },
        )


@router.get("/logout")
def logout(request: Request):
    """Handle user logout"""
    request.session.clear()
    logger.info("🔓 User logged out")
    return RedirectResponse(url="/login", status_code=303)
