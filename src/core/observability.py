import logging
from collections.abc import Mapping
from typing import cast
from urllib.parse import urlparse

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.settings import Settings

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
        _, exc_value, _ = exc_info
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


def drop_unwanted_sentry_payload(event: Event, hint: Hint) -> Event | None:
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


def init_sentry(settings: Settings) -> None:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            # Disable legacy breadcrumb/event behavior - we use native Sentry logs via sentry_sdk.logger
            LoggingIntegration(event_level=None, level=None),
        ],
        enable_logs=True,  # Enable Sentry's native structured logs
        environment=settings.environment,
        release=settings.sentry_release,
        traces_sample_rate=1.0,
        profile_session_sample_rate=1.0,
        profile_lifecycle="trace",
        before_send=drop_unwanted_sentry_payload,
        before_send_transaction=drop_unwanted_sentry_payload,
    )
