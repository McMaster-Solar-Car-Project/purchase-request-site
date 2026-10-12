"""
Success router for the /success endpoint.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.db.schema import get_db
from src.models.user_service import get_user_by_email
from src.routers.utils import get_authenticated_user_email, templates
from src.services.submission_tracking import submission_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["success"])


@router.get("/success")
def success_page(
    request: Request,
    submission_id: UUID | None = None,
    authenticated_email: str = Depends(get_authenticated_user_email),
    db: Session = Depends(get_db),
):
    """Display success page after purchase request submission"""
    download_info = None
    current_time = datetime.now()
    draft_owner_id = None
    if submission_id is not None:
        user = get_user_by_email(db, authenticated_email)
        if user is None:
            return RedirectResponse("/login", status_code=303)
        status = submission_status(db, user.id, str(submission_id))["status"]
        if status != "succeeded":
            return RedirectResponse("/dashboard", status_code=303)
        draft_owner_id = user.id

    session_download_info = request.session.get("download_info")
    if isinstance(session_download_info, dict):
        drive_folder_id = session_download_info.get("drive_folder_id")
        excel_file = session_download_info.get("excel_file")
    else:
        drive_folder_id = excel_file = None

    if isinstance(drive_folder_id, str) and isinstance(excel_file, str):
        download_info = {
            "drive_folder_id": drive_folder_id,
            "excel_file": excel_file,
            "download_url": "/download-excel",
        }

    return templates.TemplateResponse(
        request=request,
        name="success.html",
        context={
            "request": request,
            "download_info": download_info,
            "current_time": current_time,
            "submitted_draft_id": str(submission_id) if submission_id else None,
            "draft_owner_id": draft_owner_id,
        },
        headers={"Cache-Control": "no-store"},
    )
