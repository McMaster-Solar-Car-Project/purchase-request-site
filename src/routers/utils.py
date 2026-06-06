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
    if not request.session.get("authenticated", False):
        raise AuthRedirect()


# Initialize rate limiter based on client IP address
limiter = Limiter(key_func=get_remote_address)
