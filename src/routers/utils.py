"""
Shared helper utility functions for routers.
"""

from fastapi import Request
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

templates_dir = "src/templates"
templates = Jinja2Templates(directory=templates_dir)


class AuthRedirect(Exception):  # noqa: N818  # flow-control, not an error
    def __init__(self, location: str = "/login") -> None:
        super().__init__(f"Redirecting to {location}")
        self.location = location


def require_auth(request: Request) -> None:
    """Need to be authenticated to access this endpoint."""
    get_authenticated_user_email(request)


def get_authenticated_user_email(request: Request) -> str:
    """Return the authenticated session email or redirect to login."""
    if not request.session.get("authenticated", False):
        raise AuthRedirect()

    user_email = request.session.get("user_email")
    if not isinstance(user_email, str) or not user_email.strip():
        request.session.clear()
        raise AuthRedirect()
    return user_email


# Initialize rate limiter based on client IP address
limiter = Limiter(key_func=get_remote_address)
