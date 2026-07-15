"""
Sentry integration for error tracking and monitoring.

Provides centralized error tracking, performance monitoring, and release tracking.
"""

import logging
import os
from typing import Any, Dict, Optional

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

logger = logging.getLogger(__name__)


class SentryConfig:
    """Configuration for Sentry integration."""

    def __init__(self):
        """Initialize Sentry configuration from environment variables."""
        self.dsn = os.getenv("SENTRY_DSN", "")
        self.environment = os.getenv("SENTRY_ENVIRONMENT", "development")
        self.traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
        self.profiles_sample_rate = float(
            os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")
        )
        self.enabled = bool(self.dsn)
        self.release = os.getenv("SENTRY_RELEASE", "unknown")
        self.server_name = os.getenv("SENTRY_SERVER_NAME", "")

    def is_enabled(self) -> bool:
        """Check if Sentry is enabled."""
        return self.enabled


def init_sentry() -> bool:
    """
    Initialize Sentry for error tracking and monitoring.

    Returns:
        bool: True if Sentry was initialized successfully, False if disabled
    """
    config = SentryConfig()

    if not config.is_enabled():
        logger.info("Sentry is disabled (no DSN provided)")
        return False

    logger.info(f"Initializing Sentry with environment: {config.environment}")

    try:
        sentry_sdk.init(
            dsn=config.dsn,
            environment=config.environment,
            release=config.release,
            server_name=config.server_name or None,
            traces_sample_rate=config.traces_sample_rate,
            profiles_sample_rate=config.profiles_sample_rate,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            # Performance Monitoring
            enable_tracing=True,
            # Set the transaction sample rate
            transaction_sample_rate=config.traces_sample_rate,
            # Error filtering
            ignore_errors=[
                ConnectionError,
                TimeoutError,
            ],
            # Attach stack traces to messages
            attach_stacktrace=True,
            # Include local variables in error reports (be careful with sensitive data)
            include_local_variables=config.environment != "production",
            # Capture breadcrumbs
            max_breadcrumbs=100,
        )

        logger.info("Sentry initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def capture_exception(exception: Exception, **kwargs) -> None:
    """
    Capture and report an exception to Sentry.

    Args:
        exception: The exception to capture
        **kwargs: Additional context to send to Sentry
    """
    if SentryConfig().is_enabled():
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_context(key, {"value": str(value)})
            sentry_sdk.capture_exception(exception)
        logger.debug(f"Exception captured in Sentry: {exception}")


def capture_message(message: str, level: str = "info", **kwargs) -> None:
    """
    Capture and report a message to Sentry.

    Args:
        message: The message to capture
        level: Message level (info, warning, error)
        **kwargs: Additional context to send to Sentry
    """
    if SentryConfig().is_enabled():
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_context(key, {"value": str(value)})
            sentry_sdk.capture_message(message, level=level)
        logger.debug(f"Message captured in Sentry: {message}")


def set_user_context(user_id: str, email: Optional[str] = None, **extra) -> None:
    """
    Set user context for error tracking.

    Args:
        user_id: Unique user identifier
        email: User email (optional)
        **extra: Additional user information
    """
    if SentryConfig().is_enabled():
        sentry_sdk.set_user({"id": user_id, "email": email, **extra})


def clear_user_context() -> None:
    """Clear user context."""
    if SentryConfig().is_enabled():
        sentry_sdk.set_user(None)


def set_tag(key: str, value: str) -> None:
    """
    Set a tag for error tracking.

    Tags are used to group and filter errors.

    Args:
        key: Tag key
        value: Tag value
    """
    if SentryConfig().is_enabled():
        sentry_sdk.set_tag(key, value)


def set_context(key: str, context: Dict[str, Any]) -> None:
    """
    Set context information for error tracking.

    Args:
        key: Context key
        context: Context dictionary
    """
    if SentryConfig().is_enabled():
        sentry_sdk.set_context(key, context)


def add_breadcrumb(
    message: str, category: str = "info", level: str = "info", **data
) -> None:
    """
    Add a breadcrumb for error tracking.

    Breadcrumbs are used to track the sequence of events leading to an error.

    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Breadcrumb level (debug, info, warning, error, critical)
        **data: Additional data to include
    """
    if SentryConfig().is_enabled():
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )


def start_transaction(name: str, op: str = "http.request") -> Any:
    """
    Start a performance transaction.

    Args:
        name: Transaction name
        op: Operation type

    Returns:
        Transaction object (or None if Sentry is disabled)
    """
    if SentryConfig().is_enabled():
        return sentry_sdk.start_transaction(
            name=name,
            op=op,
            trace_id=None,
            parent_span_id=None,
        )
    return None


class SentryMiddleware:
    """FastAPI middleware for Sentry integration."""

    def __init__(self, app):
        """Initialize middleware."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Handle ASGI scope."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_path = scope.get("path", "")
        request_method = scope.get("method", "")

        # Start transaction
        transaction = start_transaction(
            name=f"{request_method} {request_path}", op="http.request"
        )

        async def send_with_transaction(message):
            """Send message and finish transaction."""
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                if transaction:
                    transaction.set_http_status(status_code)

                # Set tag for status code
                set_tag("http.status_code", str(status_code))

            await send(message)

        try:
            await self.app(scope, receive, send_with_transaction)
        except Exception as e:
            # Capture exception and re-raise
            capture_exception(e)
            raise
        finally:
            if transaction:
                transaction.finish()
