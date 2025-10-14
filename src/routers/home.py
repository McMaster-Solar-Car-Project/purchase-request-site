from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["home"])


@router.get("/")
async def home(request: Request):
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


@router.get("/health")
async def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
