import logging
import os
import secrets
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from urllib.parse import urlparse

import sentry_sdk
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
from src.core.settings import get_settings
from src.db.schema import init_database
from src.request_logging import RequestLoggingMiddleware
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
from src.routers.profile import router as profile_router
from src.routers.success import router as success_router
from src.routers.utils import AuthRedirect, limiter, templates

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


def _is_unwanted_log(event: Event, hint: Hint) -> bool:
    """Return True if the event or transaction should be dropped."""
    exc_info = hint.get("exc_info")
    if exc_info is not None:
        exc_type, exc_value, _ = exc_info
        if (
            isinstance(exc_value, StarletteHTTPException)
            and exc_value.status_code == 404
        ):
            return True

    contexts = event.get("contexts")
    if isinstance(contexts, Mapping):
        response = contexts.get("response")
        if isinstance(response, Mapping) and response.get("status_code") == 404:
            return True

    return False


def _drop_unwanted_sentry_payload(event: Event, hint: Hint) -> Event | None:
    """Prevent unwanted Sentry events/transactions from being sent."""
    if _event_is_for_health_endpoint(event):
        return None
    if _is_unwanted_log(event, hint):
        return None
    return event


class ExcludeUnwantedAccessLogsFilter(logging.Filter):
    """Filter out Uvicorn access logs for health probes and unwanted status codes."""

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

        if isinstance(args, tuple) and len(args) >= 5:
            tuple_args = cast("tuple[object, ...]", args)
            status_code = tuple_args[4]
            if status_code == 404:
                return False

        message = record.getMessage()
        return " /health" not in message


def configure_uvicorn_access_log_filter() -> None:
    """Prevent noisy health-check probes and unwanted logs from being emitted as access logs."""
    access_logger = logging.getLogger("uvicorn.access")
    if not any(
        isinstance(f, ExcludeUnwantedAccessLogsFilter) for f in access_logger.filters
    ):
        access_logger.addFilter(ExcludeUnwantedAccessLogsFilter())


def configure_sentry() -> None:
    """Configure Sentry integrations for the running app."""
    settings = get_settings()
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            # Disable legacy breadcrumb/event behavior; native Sentry logs are enabled.
            LoggingIntegration(event_level=None, level=None),
        ],
        enable_logs=True,
        environment=settings.environment,
        release=settings.sentry_release,
        traces_sample_rate=1.0,
        profile_session_sample_rate=1.0,
        profile_lifecycle="trace",
        before_send=_drop_unwanted_sentry_payload,
        before_send_transaction=_drop_unwanted_sentry_payload,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run app startup/shutdown work outside module import."""
    logger.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    os.makedirs("sessions", exist_ok=True)
    configure_sentry()
    configure_uvicorn_access_log_filter()
    init_database()
    yield


async def handle_exceed_limit(request: Request, exc: Exception):
    """Handle rate limit exceeded errors by redirecting to login with error message"""
    if not isinstance(exc, RateLimitExceeded):
        raise exc
    return RedirectResponse(url="/login?error=ratelimit", status_code=303)


async def home():
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


async def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


async def auth_redirect_handler(request: Request, exc: Exception):
    """Redirect unauthenticated requests to the login page (or other target)."""
    if not isinstance(exc, AuthRedirect):
        raise exc
    return RedirectResponse(url=exc.location, status_code=303)


async def http_exception_handler(request: Request, exc: Exception):
    if not isinstance(exc, StarletteHTTPException):
        raise exc
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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="Purchase Request Site",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(RequestLoggingMiddleware)

    # Generate a random secret key for this process; users are logged out on restart.
    session_secret = secrets.token_urlsafe(32)
    application.add_middleware(SessionMiddleware, secret_key=session_secret)

    application.mount("/static", StaticFiles(directory="src/static"), name="static")

    application.include_router(auth_router)
    application.include_router(dashboard_router)
    application.include_router(profile_router)
    application.include_router(success_router)
    application.include_router(download_router)

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, handle_exceed_limit)
    application.add_exception_handler(AuthRedirect, auth_redirect_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(Exception, generic_exception_handler)

    application.add_api_route("/", home, methods=["GET"])
    application.add_api_route("/health", health_check, methods=["GET"])

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=False,
    )
