import os
import secrets
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging_utils import setup_logger
from src.core.templates import templates
from src.db.schema import init_database
from src.request_logging import RequestLoggingMiddleware
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
from src.routers.error import router as error_router
from src.routers.profile import router as profile_router
from src.routers.success import router as success_router

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)


init_database()
app = FastAPI(title="Purchase Request Site")

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Generate a random secret key for this session (Note: users will be logged out on restart)
session_secret = secrets.token_urlsafe(32)

# Add session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
)

# Mount static files (directories are guaranteed to exist now)
app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(profile_router)
app.include_router(success_router)
app.include_router(download_router)
app.include_router(error_router)


@app.get("/")
async def home():
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    return templates.TemplateResponse(
        "error.html", {"request": request}, status_code=exc.status_code
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return templates.TemplateResponse(
        "error.html", {"request": request}, status_code=500
    )


# deliberately raise a Python exception FOR TESTING USE ONLY
"""
@app.get("/cause-500")
async def cause_500():
    raise Exception("Deliberate server error for testing 500 page")
"""

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
