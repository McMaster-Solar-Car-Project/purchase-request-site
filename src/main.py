import os
import secrets
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging_utils import setup_logger
from src.core.rate_limit import limiter
from src.db.schema import init_database
from src.request_logging import RequestLoggingMiddleware
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
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


async def handle_exceed_limit(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors by redirecting to login with error message"""
    return RedirectResponse(url="/login?error=ratelimit", status_code=303)


# Initialize rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, handle_exceed_limit)


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
