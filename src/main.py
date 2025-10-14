import os
import secrets
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from core.logging_utils import setup_logger
from db.schema import init_database
from request_logging import RequestLoggingMiddleware
from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.download import router as download_router
from routers.profile import router as profile_router
from routers.success import router as success_router

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions", "static", "templates", "excel_templates"]
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
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sessions", StaticFiles(directory="sessions"), name="sessions")

# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(profile_router)
app.include_router(success_router)
app.include_router(download_router)


@app.get("/")
async def home():
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
