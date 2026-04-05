"""
Middleware for logging HTTP requests and responses.
"""

import time

import sentry_sdk
from fastapi import Request
from sentry_sdk import metrics
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging_utils import setup_logger

# Set up logger for request logging
request_logger = setup_logger("requests")


def _emit_request_metrics(
    method: str, path: str, status_code: int, process_time_seconds: float
) -> None:
    """Emit low-cardinality request metrics to Sentry."""
    tags = {
        "method": method,
        "status_code": str(status_code),
        "path": path,
    }
    try:
        metrics.count("http.server.requests", 1, tags=tags)
        metrics.distribution(
            "http.server.duration_ms", process_time_seconds * 1000.0, tags=tags
        )
        if status_code >= 500:
            metrics.count("http.server.errors", 1, tags=tags)
    except Exception:
        # Metrics should never break request handling.
        request_logger.debug("Failed to emit Sentry metrics", exc_info=True)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()

        # Get client IP (handle potential proxies)
        client_ip = request.client.host if request.client else "unknown"
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            client_ip = request.headers["x-real-ip"]

        # Add Sentry Context
        try:
            user_email = request.session.get("user_email")
            if user_email:
                sentry_sdk.set_user({"email": user_email})
            else:
                sentry_sdk.set_user(None)
        except Exception:
            # Session might not be available
            pass

        # Only log important requests (skip static files and health probes)
        skip_paths = ["/static", "/favicon.ico", "/robots.txt", "/health"]
        should_log = not any(request.url.path.startswith(path) for path in skip_paths)

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            _emit_request_metrics(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time_seconds=process_time,
            )

            # Only log slow requests (>1s) or important endpoints or errors (excluding 404s)
            if should_log and (
                process_time > 1.0
                or (response.status_code >= 400 and response.status_code != 404)
                or request.method in ["POST", "PUT", "DELETE"]
            ):
                request_logger.info(
                    f"{request.method} {request.url.path} "
                    f"→ {response.status_code} ({process_time:.3f}s) from {client_ip}"
                )

            return response

        except Exception as e:
            # Always log errors
            process_time = time.time() - start_time
            _emit_request_metrics(
                method=request.method,
                path=request.url.path,
                status_code=500,
                process_time_seconds=process_time,
            )
            request_logger.exception(
                f"❌ {request.method} {request.url.path} "
                f"failed after {process_time:.3f}s - {str(e)}"
            )
            raise
