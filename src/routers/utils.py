"""
Shared helper utility functions for routers.
"""

from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

templates_dir = "src/templates"
templates = Jinja2Templates(directory=templates_dir)


def require_auth(request: Request):
    """Need to be authenticated to access this endpoint"""
    if not request.session.get("authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )


def get_authenticated_user_email(request: Request) -> str:
    """Return authenticated user's email from session."""
    require_auth(request)
    user_email = request.session.get("user_email")
    if not isinstance(user_email, str) or not user_email:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )
    return user_email


# Initialize rate limiter based on client IP address
limiter = Limiter(key_func=get_remote_address)
