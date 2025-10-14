"""
Shared dependencies for routers.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db.schema import get_db


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated via session"""
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    """Dependency to require authentication"""
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"}
        )


def get_current_user_email(request: Request) -> str:
    """Get current user email from session"""
    return request.session.get("user_email")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current user from database"""
    from models.user_service import get_user_by_email

    email = get_current_user_email(request)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"}
        )

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"}
        )

    return user
