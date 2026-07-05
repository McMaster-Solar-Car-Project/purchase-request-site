"""
Past submissions router for the /submissions endpoint.
"""

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from src.core.logging_utils import setup_logger
from src.google_sheets import GoogleSheetsClient, PastSubmission
from src.routers.utils import get_authenticated_user_email, templates

logger = setup_logger(__name__)

router = APIRouter(tags=["submissions"])


@router.get("/submissions")
async def past_submissions_page(
    request: Request,
    authenticated_email: str = Depends(get_authenticated_user_email),
):
    """Display the authenticated user's past reimbursement submissions."""
    submissions: list[PastSubmission] = []
    error_message = None
    sheets_client: GoogleSheetsClient | None = None

    try:
        sheets_client = GoogleSheetsClient()
        submissions = await run_in_threadpool(
            sheets_client.list_past_submissions, authenticated_email
        )
    except Exception:
        logger.exception("Failed to load past submissions")
        error_message = (
            "Past submissions are temporarily unavailable. Please try again later."
        )
    finally:
        if sheets_client is not None:
            await run_in_threadpool(sheets_client.close)

    return templates.TemplateResponse(
        request=request,
        name="past_submissions.html",
        context={
            "request": request,
            "title": "Past Submissions",
            "user_email": authenticated_email,
            "submissions": submissions,
            "error_message": error_message,
        },
    )
