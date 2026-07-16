"""
Custom error handlers for Cannabis EU GMP QMS Creator.

Provides consistent error responses, logging, and error tracking for all exception types.
Prevents sensitive information leakage in error messages.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import (
    add_breadcrumb,
    capture_exception,
)

logger = logging.getLogger(__name__)


class QMSException(Exception):
    """Base exception for QMS application."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(QMSException):
    """Validation error exception."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation exception."""
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field": field, **(details or {})},
        )


class ResourceNotFoundException(QMSException):
    """Resource not found exception."""

    def __init__(self, resource_type: str, resource_id: str):
        """Initialize not found exception."""
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class UnauthorizedException(QMSException):
    """Unauthorized access exception."""

    def __init__(self, message: str = "Unauthorized"):
        """Initialize unauthorized exception."""
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(QMSException):
    """Forbidden access exception."""

    def __init__(self, message: str = "Forbidden"):
        """Initialize forbidden exception."""
        super().__init__(
            message=message, code="FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN
        )


class ConflictException(QMSException):
    """Resource conflict exception."""

    def __init__(self, message: str, resource_type: str = "resource"):
        """Initialize conflict exception."""
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details={"resource_type": resource_type},
        )


class ExternalServiceException(QMSException):
    """External service error exception."""

    def __init__(self, service: str, message: str):
        """Initialize external service exception."""
        super().__init__(
            message=f"{service} service error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service},
        )


class RateLimitException(QMSException):
    """Rate limit exceeded exception."""

    def __init__(self, retry_after: int = 60):
        """Initialize rate limit exception."""
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )


def create_error_response(exception: Exception, request_id: str = "") -> Dict[str, Any]:
    """
    Create standardized error response.

    Args:
        exception: Exception that occurred
        request_id: Request ID for correlation

    Returns:
        Error response dictionary
    """
    if isinstance(exception, QMSException):
        return {
            "status": "error",
            "code": exception.code,
            "message": exception.message,
            "details": exception.details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
        }
    else:
        # Generic error - don't expose internal details
        return {
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please contact support.",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
        }


async def qms_exception_handler(request: Request, exc: QMSException) -> JSONResponse:
    """Handle QMS application exceptions."""
    request_id = request.headers.get("X-Request-ID", "")

    logger.warning(
        f"QMS Exception: {exc.code}",
        extra={
            "code": exc.code,
            "message": exc.message,
            "status_code": exc.status_code,
            "request_id": request_id,
        },
    )

    # Track in Sentry for warning-level issues
    if exc.status_code >= 500:
        add_breadcrumb(
            message=f"QMS Exception: {exc.code}",
            category="error",
            level="warning",
            data={"code": exc.code, "message": exc.message},
        )

    response = create_error_response(exc, request_id)
    return JSONResponse(
        status_code=exc.status_code,
        content=response,
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI validation errors."""
    request_id = request.headers.get("X-Request-ID", "")

    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"][1:]),
                "type": error["type"],
                "message": error["msg"],
            }
        )

    logger.warning(
        "Validation error",
        extra={
            "error_count": len(errors),
            "request_id": request_id,
        },
    )

    response = {
        "status": "error",
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
    }

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response,
        headers={"X-Request-ID": request_id},
    )


async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Handle database errors."""
    request_id = request.headers.get("X-Request-ID", "")

    logger.error(
        "Database error",
        exc_info=exc,
        extra={
            "error_type": type(exc).__name__,
            "request_id": request_id,
        },
    )

    # Capture in Sentry
    capture_exception(exc)

    # Don't expose database error details to client
    response = {
        "status": "error",
        "code": "DATABASE_ERROR",
        "message": "A database error occurred. Please try again later.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
    }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response,
        headers={"X-Request-ID": request_id},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    request_id = request.headers.get("X-Request-ID", "")

    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=exc,
        extra={
            "error_type": type(exc).__name__,
            "request_id": request_id,
        },
    )

    # Capture in Sentry
    capture_exception(exc)

    # Don't expose internal error details
    response = {
        "status": "error",
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred. Please contact support.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
    }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response,
        headers={"X-Request-ID": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Register all error handlers with FastAPI application.

    Args:
        app: FastAPI application instance
    """
    logger.info("Registering error handlers")

    app.add_exception_handler(QMSException, qms_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Error handlers registered successfully")
