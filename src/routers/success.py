from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException

from core.logging_utils import setup_logger
from google_drive import download_file_from_drive
from routers.auth import require_auth

logger = setup_logger(__name__)

router = APIRouter(tags=["download"])


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
