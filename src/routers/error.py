from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/404", response_class=HTMLResponse)
async def not_found(request: Request):
    """Return a 404 page when URL is invalid"""
    return templates.TemplateResponse("404.html", {"request": request})


@router.get("/error", response_class=HTMLResponse)
async def general_error(request: Request):
    """Return a general error page when something goes wrong"""
    return templates.TemplateResponse("error.html", {"request": request})
