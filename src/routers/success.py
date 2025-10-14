"""
Success router for the /success endpoint.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from src.core.logging_utils import setup_logger
from src.routers.utils import require_auth, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["success"])


@router.get("/success")
async def success_page(
    request: Request,
    drive_folder_id: str = None,
    excel_file: str = None,
    user_email: str = None,
    _: None = Depends(require_auth),
):
    """Display success page after purchase request submission"""
    download_info = None
    current_time = datetime.now()

    if drive_folder_id and excel_file:
        download_info = {
            "drive_folder_id": drive_folder_id,
            "excel_file": excel_file,
            "download_url": f"/download-excel?drive_folder_id={drive_folder_id}&excel_file={excel_file}",
        }

    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "download_info": download_info,
            "user_email": user_email,
            "current_time": current_time,
        },
    )
