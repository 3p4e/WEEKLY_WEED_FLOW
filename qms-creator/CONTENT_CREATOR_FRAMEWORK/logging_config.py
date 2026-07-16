"""
Structured logging configuration for Cannabis EU GMP QMS Creator.

Provides JSON structured logging for production environments and formatted
logging for development. Includes request ID correlation, error tracking,
and performance monitoring.
"""

import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

# Get environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv(
    "LOG_FORMAT", "colored" if ENVIRONMENT == "development" else "json"
)
LOG_FILE = os.getenv("LOG_FILE", "logs/qms.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "10"))


class ContextFilter(logging.Filter):
    """Add contextual information to log records."""

    _context = {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        # Add request ID if available
        request_id = self._context.get("request_id")
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "-"

        # Add user ID if available
        user_id = self._context.get("user_id")
        if user_id:
            record.user_id = user_id
        else:
            record.user_id = "-"

        # Add correlation ID for distributed tracing
        correlation_id = self._context.get("correlation_id")
        if correlation_id:
            record.correlation_id = correlation_id
        else:
            record.correlation_id = "-"

        # Add environment
        record.environment = ENVIRONMENT

        return True

    @classmethod
    def set_context(cls, **kwargs):
        """Set context variables for all subsequent log records."""
        cls._context.update(kwargs)

    @classmethod
    def clear_context(cls):
        """Clear context."""
        cls._context.clear()


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to JSON log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Add environment
        log_record["environment"] = ENVIRONMENT

        # Add log level
        log_record["level"] = record.levelname

        # Add request ID
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        # Add user ID
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id

        # Add correlation ID
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id

        # Add exception information if present
        if record.exc_info:
            log_record["exception"] = record.exc_text or self.formatException(
                record.exc_info
            )

        # Add performance metrics if available
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms

        if hasattr(record, "status_code"):
            log_record["status_code"] = record.status_code


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development logging."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to level
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format message
        message = super().format(record)

        # Reset color after message
        return message


def get_config() -> Dict[str, Any]:
    """Get logging configuration dictionary."""

    # Ensure log directory exists
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {
                "()": ContextFilter,
            },
        },
        "formatters": {
            "json": {
                "()": JSONFormatter,
                "fmt": "%(timestamp)s %(level)s %(name)s %(message)s",
            },
            "colored": {
                "()": ColoredFormatter,
                "fmt": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": LOG_FORMAT if LOG_FORMAT != "detailed" else LOG_FORMAT,
                "stream": "ext://sys.stdout",
                "filters": ["context"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": LOG_LEVEL,
                "formatter": "json" if LOG_FORMAT == "json" else "detailed",
                "filename": LOG_FILE,
                "maxBytes": LOG_MAX_BYTES,
                "backupCount": LOG_BACKUP_COUNT,
                "filters": ["context"],
            },
        },
        "root": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file"],
        },
        "loggers": {
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "alembic": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }

    return config


def setup_logging() -> None:
    """Initialize logging configuration."""
    config = get_config()
    logging.config.dictConfig(config)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized: {LOG_FORMAT} format, {LOG_LEVEL} level, {ENVIRONMENT} environment"
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to add logging to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return logging.getLogger(self.__class__.__name__)


# Initialize on import
setup_logging()
