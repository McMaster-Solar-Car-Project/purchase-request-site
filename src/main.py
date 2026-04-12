import logging
import os
import secrets
from collections.abc import Mapping
from datetime import datetime
from typing import cast
from urllib.parse import urlparse

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging_utils import setup_logger
from src.db.schema import init_database
from src.request_logging import RequestLoggingMiddleware
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
from src.routers.profile import router as profile_router
from src.routers.success import router as success_router
from src.routers.utils import limiter, templates

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)
HEALTH_PATH_PREFIX = "/health"


def _event_is_for_health_endpoint(event: Mapping[str, object]) -> bool:
    """Return True when a Sentry event/transaction belongs to /health."""
    request_data = event.get("request")
    if isinstance(request_data, Mapping):
        # Sentry's request payload is str-keyed; bare Mapping narrows to unusable key type for ty.
        request_payload = cast("Mapping[str, object]", request_data)
        request_url = request_payload.get("url")
        if isinstance(request_url, str):
            parsed_path = urlparse(request_url).path
            if parsed_path.startswith(HEALTH_PATH_PREFIX):
                return True

    transaction_name = event.get("transaction")
    return isinstance(transaction_name, str) and "/health" in transaction_name


def _drop_health_events(event: Event, hint: Hint) -> Event | None:
    """Prevent health-check errors/log events from being sent to Sentry."""
    del hint
    if _event_is_for_health_endpoint(event):
        return None
    return event


def _drop_health_transactions(event: Event, hint: Hint) -> Event | None:
    """Prevent health-check transactions from being sent to Sentry."""
    del hint
    if _event_is_for_health_endpoint(event):
        return None
    return event


class ExcludeHealthFromAccessLogFilter(logging.Filter):
    """Filter out Uvicorn access logs for health probe endpoints."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn access logger provides request details in record.args:
        # (client_addr, method, full_path, http_version, status_code).
        # Prefer parsing full_path directly instead of brittle message matching.
        args = getattr(record, "args", ())
        if isinstance(args, tuple) and len(args) >= 3:
            tuple_args = cast("tuple[object, ...]", args)
            full_path = tuple_args[2]
            if isinstance(full_path, str) and full_path.startswith(HEALTH_PATH_PREFIX):
                return False

        message = record.getMessage()
        return " /health" not in message


def configure_uvicorn_access_log_filter() -> None:
    """Prevent noisy health-check probes from being emitted as access logs."""
    access_logger = logging.getLogger("uvicorn.access")
    if not any(
        isinstance(f, ExcludeHealthFromAccessLogFilter) for f in access_logger.filters
    ):
        access_logger.addFilter(ExcludeHealthFromAccessLogFilter())


# Log start time and date
logger.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Create required directories immediately (before mounting static files)
required_dirs = ["sessions"]
for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)


sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
        # Disable legacy breadcrumb/event behavior - we use native Sentry logs via sentry_sdk.logger
        LoggingIntegration(event_level=None, level=None),
    ],
    enable_logs=True,  # Enable Sentry's native structured logs
    environment=os.getenv("ENVIRONMENT", "development"),
    release=os.getenv("SENTRY_RELEASE"),
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
    before_send=_drop_health_events,
    before_send_transaction=_drop_health_transactions,
)

configure_uvicorn_access_log_filter()

init_database()
app = FastAPI(
    title="Purchase Request Site",
    docs_url=None if os.getenv("ENVIRONMENT", "testing") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT", "testing") == "production" else "/redoc",
    openapi_url=None
    if os.getenv("ENVIRONMENT", "testing") == "production"
    else "/openapi.json",
)

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


async def handle_exceed_limit(request: Request, exc: Exception):
    """Handle rate limit exceeded errors by redirecting to login with error message"""
    if not isinstance(exc, RateLimitExceeded):
        raise exc
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


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"request": request},
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith(HEALTH_PATH_PREFIX):
        return JSONResponse(status_code=500, content={"status": "unhealthy"})
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request},
        status_code=500,
    )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        access_log=False,
    )
