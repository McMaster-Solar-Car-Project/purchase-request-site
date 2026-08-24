import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi.errors import RateLimitExceeded
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging_utils import configure_logging
from src.core.settings import get_settings
from src.db.schema import init_database
from src.routers.auth import router as auth_router
from src.routers.dashboard import router as dashboard_router
from src.routers.download import router as download_router
from src.routers.home import router as home_router
from src.routers.profile import router as profile_router
from src.routers.success import router as success_router
from src.routers.utils import AuthRedirect, limiter, templates

configure_logging()
logger = logging.getLogger(__name__)
HEALTH_PATH_PREFIX = "/health"


def configure_sentry() -> None:
    """Configure Sentry integrations for the running app."""
    settings = get_settings()
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            SqlalchemyIntegration(),
        ],
        environment=settings.environment,
        release=settings.sentry_release,
        sample_rate=1.0,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run app startup/shutdown work outside module import."""
    logger.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    get_settings().sessions_root.mkdir(parents=True, exist_ok=True)
    configure_sentry()
    await run_in_threadpool(init_database)
    yield


def handle_exceed_limit(request: Request, exc: Exception):
    """Handle rate limit exceeded errors by redirecting to login with error message"""
    if not isinstance(exc, RateLimitExceeded):
        raise exc
    return RedirectResponse(url="/login?error=ratelimit", status_code=303)


def home():
    """Redirect home page to login"""
    return RedirectResponse(url="/login", status_code=303)


def health_check():
    """Health check endpoint for Docker health monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


def auth_redirect_handler(request: Request, exc: Exception):
    """Redirect unauthenticated requests to the login page (or other target)."""
    if not isinstance(exc, AuthRedirect):
        raise exc
    return RedirectResponse(url=exc.location, status_code=303)


def http_exception_handler(request: Request, exc: Exception):
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


def generic_exception_handler(request: Request, exc: Exception):
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

    session_secret = settings.session_secret or secrets.token_urlsafe(32)
    application.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        https_only=settings.is_production,
        same_site="lax",
        max_age=60 * 60 * 24,
    )

    application.mount("/static", StaticFiles(directory="src/static"), name="static")

    application.include_router(auth_router)
    application.include_router(home_router)
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
