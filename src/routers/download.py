"""
Download router for the /download-excel.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import Response

from src.core.logging_utils import setup_logger
from src.google_drive import download_file_from_drive
from src.routers.utils import get_authenticated_user_email

logger = setup_logger(__name__)

router = APIRouter(tags=["download"])


@router.get("/download-excel")
def download_excel(
    request: Request,
    _: str = Depends(get_authenticated_user_email),
):
    """Download the generated Excel file from Google Drive"""
    download_info = request.session.get("download_info")
    if not isinstance(download_info, dict):
        raise HTTPException(status_code=404, detail="Excel file not found")

    drive_folder_id = download_info.get("drive_folder_id")
    excel_file = download_info.get("excel_file")
    if not isinstance(drive_folder_id, str) or not isinstance(excel_file, str):
        raise HTTPException(status_code=404, detail="Excel file not found")

    try:
        file_content = download_file_from_drive(drive_folder_id, excel_file)
        # Return the file content as a streaming response
        return Response(
            content=file_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={excel_file}"},
        )

    except Exception:
        logger.exception(f"Failed to download {excel_file} from Google Drive")
        raise HTTPException(
            status_code=404, detail="Excel file not found in Google Drive"
        ) from None
