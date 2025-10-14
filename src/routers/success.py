from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates

from core.logging_utils import setup_logger
from google_drive import download_file_from_drive
from routers.auth import require_auth

logger = setup_logger(__name__)

router = APIRouter(tags=["download"])
templates_dir = "templates"
templates = Jinja2Templates(directory=templates_dir)


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


@router.get("/download-excel")
async def download_excel(
    request: Request,
    drive_folder_id: str,
    excel_file: str,
    _: None = Depends(require_auth),
):
    """Download the generated Excel file from Google Drive"""
    try:
        file_content = download_file_from_drive(drive_folder_id, excel_file)
        # Return the file content as a streaming response
        from fastapi.responses import Response

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
