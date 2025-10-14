"""
Shared helper utility functions for routers.
"""

from fastapi import HTTPException, Request, status


def require_auth(request: Request):
    """Need to be authenticated to access this endpoint"""
    if not request.session.get("authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/login"}
        )
