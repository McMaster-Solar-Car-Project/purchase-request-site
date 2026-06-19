"""
Success router for the /success endpoint.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from src.core.logging_utils import setup_logger
from src.routers.utils import get_authenticated_user_email, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["success"])


@router.get("/success")
async def success_page(
    request: Request,
    _: str = Depends(get_authenticated_user_email),
):
    """Display success page after purchase request submission"""
    download_info = None
    current_time = datetime.now()

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
        },
    )
