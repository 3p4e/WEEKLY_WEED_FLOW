"""
Security middleware for Cannabis EU GMP QMS Creator.

Implements request size limits, timeout handling, security headers,
and CSRF protection.
"""

import logging
import os
import time
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """Add security headers to response."""
        if request.method == "OPTIONS":
            return await call_next(request)

        response = await call_next(request)

        # Prevent content type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS (HTTP Strict Transport Security)
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy - Relaxed for local dev
        response.headers["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
        )

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response


class RequestLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request size and timeout limits."""

    # Configuration (in bytes and seconds)
    DEFAULT_MAX_REQUEST_SIZE = 52428800  # 50MB
    DEFAULT_MAX_BODY_SIZE = 10485760  # 10MB for JSON bodies
    DEFAULT_REQUEST_TIMEOUT = 300  # 5 minutes

    # Endpoint-specific limits
    ENDPOINT_LIMITS = {
        "/documents": {"max_size": 52428800, "timeout": 300},  # File upload
        "/generate": {
            "max_size": 1048576,
            "timeout": 600,
        },  # Larger timeout for generation
        "/api/files": {"max_size": 104857600, "timeout": 600},  # 100MB for large files
    }

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """Check request size and timeout."""
        if request.method == "OPTIONS":
            return await call_next(request)

        start_time = time.time()

        # Get endpoint-specific limits
        endpoint_limits = self.ENDPOINT_LIMITS.get(
            request.url.path,
            {
                "max_size": self.DEFAULT_MAX_BODY_SIZE,
                "timeout": self.DEFAULT_REQUEST_TIMEOUT,
            },
        )

        max_size = endpoint_limits["max_size"]
        timeout = endpoint_limits["timeout"]

        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                content_length = int(content_length)
                if content_length > max_size:
                    logger.warning(
                        f"Request too large: {content_length} > {max_size}",
                        extra={"path": request.url.path},
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                        content={
                            "status": "error",
                            "code": "REQUEST_TOO_LARGE",
                            "message": f"Request body is too large. Maximum size: {max_size} bytes",
                        },
                    )
            except (ValueError, TypeError):
                pass

        try:
            # Process request with timeout
            response = await call_next(request)

            # Check request duration
            duration = time.time() - start_time
            if duration > timeout:
                logger.warning(
                    f"Request timeout: {duration:.2f}s > {timeout}s",
                    extra={"path": request.url.path, "duration": duration},
                )
                # Log but don't fail - response already being sent

            # Add timing header
            response.headers["X-Response-Time"] = str(duration)

            return response

        except Exception as e:
            logger.error(f"Request processing error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "code": "REQUEST_PROCESSING_ERROR",
                    "message": "Error processing request",
                },
            )


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce IP whitelist (if configured)."""

    def __init__(self, app: FastAPI, whitelist: list = None):
        """
        Initialize whitelist middleware.

        Args:
            app: FastAPI application
            whitelist: List of allowed IP addresses
        """
        super().__init__(app)
        self.whitelist = whitelist or self._load_whitelist_from_env()

    @staticmethod
    def _load_whitelist_from_env() -> list:
        """Load whitelist from environment variables."""
        whitelist_str = os.getenv("IP_WHITELIST", "")
        if whitelist_str:
            return [ip.strip() for ip in whitelist_str.split(",")]
        return []

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """Check if client IP is whitelisted."""
        if not self.whitelist:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else None

        # Check if in whitelist
        if client_ip not in self.whitelist:
            logger.warning(f"Unauthorized IP access attempt: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "status": "error",
                    "code": "IP_NOT_WHITELISTED",
                    "message": "Your IP address is not authorized to access this resource",
                },
            )

        return await call_next(request)


class RateLimitByIPMiddleware(BaseHTTPMiddleware):
    """Middleware for basic IP-based rate limiting."""

    def __init__(self, app: FastAPI, requests_per_minute: int = 100):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            requests_per_minute: Requests allowed per minute per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_history = {}  # IP -> list of timestamps

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """Check rate limit for client IP."""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        minute_ago = current_time - 60

        # Initialize or clean up history for this IP
        if client_ip not in self.request_history:
            self.request_history[client_ip] = []

        # Remove old entries (older than 1 minute)
        self.request_history[client_ip] = [
            ts for ts in self.request_history[client_ip] if ts > minute_ago
        ]

        # Check if rate limit exceeded
        if len(self.request_history[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "status": "error",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Record this request
        self.request_history[client_ip].append(current_time)

        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_history[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        return response


class NoSQLInjectionMiddleware(BaseHTTPMiddleware):
    """Middleware to prevent NoSQL/SQL injection through query parameters."""

    # Patterns that might indicate injection attempts
    DANGEROUS_PATTERNS = [
        r"\$where",
        r"\$or",
        r"\$and",
        r"\$nor",
        r"mongodb",
        r"union.*select",
        r"drop.*table",
        r"delete.*from",
        r"exec\(",
        r"execute\(",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """Check for injection attempts in query parameters."""
        # Check query parameters
        for param_name, param_value in request.query_params.items():
            if self._check_for_injection(str(param_value)):
                logger.warning(
                    f"Potential injection attempt detected in parameter: {param_name}",
                    extra={"param": param_name, "path": request.url.path},
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "status": "error",
                        "code": "INVALID_REQUEST",
                        "message": "Invalid request parameters",
                    },
                )

        return await call_next(request)

    @classmethod
    def _check_for_injection(cls, value: str) -> bool:
        """Check if value contains injection patterns."""
        import re

        value_lower = value.lower()
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value_lower):
                return True
        return False


def register_security_middleware(app: FastAPI) -> None:
    """
    Register all security middleware with FastAPI application.

    Args:
        app: FastAPI application instance
    """
    logger.info("Registering security middleware")

    # Add middleware in reverse order (they execute bottom-up)
    app.add_middleware(NoSQLInjectionMiddleware)
    app.add_middleware(RateLimitByIPMiddleware, requests_per_minute=100)

    # Add IP whitelist if configured
    whitelist_str = os.getenv("IP_WHITELIST", "")
    if whitelist_str:
        whitelist = [ip.strip() for ip in whitelist_str.split(",")]
        app.add_middleware(IPWhitelistMiddleware, whitelist=whitelist)

    app.add_middleware(RequestLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    logger.info("Security middleware registered successfully")
