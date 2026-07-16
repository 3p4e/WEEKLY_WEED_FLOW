"""
Input validation and sanitization for Cannabis EU GMP QMS Creator.

Provides validators for common input patterns and sanitization for user input
to prevent injection attacks and malformed data.
"""

import logging
import re
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Regular expressions for validation
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALPHANUMERIC_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
FILE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-. ]+$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class InputValidator:
    """Utility class for input validation."""

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address.

        Args:
            email: Email to validate

        Returns:
            True if valid, False otherwise
        """
        if not email or len(email) > 254:
            return False
        return bool(EMAIL_PATTERN.match(email))

    @staticmethod
    def validate_slug(slug: str) -> bool:
        """
        Validate URL slug (lowercase alphanumeric with hyphens).

        Args:
            slug: Slug to validate

        Returns:
            True if valid, False otherwise
        """
        if not slug or len(slug) > 255:
            return False
        return bool(SLUG_PATTERN.match(slug))

    @staticmethod
    def validate_identifier(identifier: str) -> bool:
        """
        Validate identifier (alphanumeric, hyphens, underscores).

        Args:
            identifier: Identifier to validate

        Returns:
            True if valid, False otherwise
        """
        if not identifier or len(identifier) > 255:
            return False
        return bool(ALPHANUMERIC_PATTERN.match(identifier))

    @staticmethod
    def validate_file_name(filename: str) -> bool:
        """
        Validate file name (prevent path traversal).

        Args:
            filename: File name to validate

        Returns:
            True if valid, False otherwise
        """
        if not filename or len(filename) > 255:
            return False

        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            return False

        # Validate characters
        if not FILE_NAME_PATTERN.match(filename):
            return False

        return True

    @staticmethod
    def validate_file_path(file_path: str, allowed_dir: Optional[str] = None) -> bool:
        """
        Validate file path (prevent path traversal).

        Args:
            file_path: File path to validate
            allowed_dir: Optional allowed directory (resolved path must be within this)

        Returns:
            True if valid, False otherwise
        """
        if not file_path:
            return False

        try:
            # Resolve to absolute path
            path = Path(file_path).resolve()

            # If allowed_dir is specified, ensure path is within it
            if allowed_dir:
                allowed = Path(allowed_dir).resolve()
                # Check if path is within allowed directory
                if not str(path).startswith(str(allowed)):
                    logger.warning(f"Path traversal attempt detected: {file_path}")
                    return False

            return True
        except Exception as e:
            logger.warning(f"Invalid file path: {file_path} - {e}")
            return False

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL (basic validation, prevent SSRF).

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        if not url or len(url) > 2048:
            return False

        # Only allow http/https
        if not (url.startswith("http://") or url.startswith("https://")):
            return False

        # Prevent localhost/internal addresses (SSRF protection)
        dangerous_patterns = [
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "::1",
        ]

        lower_url = url.lower()
        for pattern in dangerous_patterns:
            if pattern in lower_url:
                logger.warning(f"SSRF attempt detected: {url}")
                return False

        return True

    @staticmethod
    def validate_uuid(uuid_str: str) -> bool:
        """
        Validate UUID format.

        Args:
            uuid_str: UUID string to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(UUID_PATTERN.match(uuid_str))

    @staticmethod
    def validate_length(value: str, min_length: int = 0, max_length: int = 255) -> bool:
        """
        Validate string length.

        Args:
            value: String to validate
            min_length: Minimum length
            max_length: Maximum length

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(value, str):
            return False
        return min_length <= len(value) <= max_length

    @staticmethod
    def validate_enum(value: str, allowed_values: List[str]) -> bool:
        """
        Validate value is in allowed list.

        Args:
            value: Value to validate
            allowed_values: List of allowed values

        Returns:
            True if valid, False otherwise
        """
        return value in allowed_values


class InputSanitizer:
    """Utility class for input sanitization."""

    @staticmethod
    def sanitize_string(
        value: Optional[str], max_length: int = 255, allow_html: bool = False
    ) -> str:
        """
        Sanitize string input.

        Args:
            value: String to sanitize
            max_length: Maximum length
            allow_html: Whether to allow HTML

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Remove null bytes
        value = value.replace("\x00", "")

        # Truncate to max length
        value = value[:max_length]

        # Remove control characters if not allowing HTML
        if not allow_html:
            value = "".join(
                char for char in value if ord(char) >= 32 or char in "\n\r\t"
            )

        return value.strip()

    @staticmethod
    def sanitize_identifier(value: Optional[str]) -> str:
        """
        Sanitize identifier (remove invalid characters).

        Args:
            value: Identifier to sanitize

        Returns:
            Sanitized identifier
        """
        if not value:
            return ""

        # Keep only alphanumeric, hyphens, underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", value)

        # Limit length
        return sanitized[:255]

    @staticmethod
    def sanitize_file_name(filename: Optional[str]) -> str:
        """
        Sanitize file name (remove path components and invalid characters).

        Args:
            filename: File name to sanitize

        Returns:
            Sanitized file name
        """
        if not filename:
            return ""

        # Remove any path components
        filename = Path(filename).name

        # Remove invalid characters
        filename = re.sub(r"[^a-zA-Z0-9._\- ]", "", filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip(". ")

        # Limit length
        return filename[:255]

    @staticmethod
    def sanitize_path(path: Optional[str]) -> str:
        """
        Sanitize file path (normalize and prevent traversal).

        Args:
            path: Path to sanitize

        Returns:
            Sanitized path
        """
        if not path:
            return ""

        # Remove null bytes
        path = path.replace("\x00", "")

        # Resolve path (removes .. and symlinks)
        try:
            resolved = Path(path).resolve()
            return str(resolved)
        except Exception:
            return ""


# Pydantic validators for common patterns
class DocumentRequest(BaseModel):
    """Base model for document requests with validation."""

    title: str = Field(..., min_length=1, max_length=500)
    code: str = Field(..., min_length=1, max_length=100)
    department: str = Field(..., min_length=1, max_length=200)
    version: str = Field(default="1.0", min_length=1, max_length=20)

    @field_validator("title", "code", "department")
    def sanitize_text_fields(cls, v: str) -> str:
        """Sanitize text fields."""
        if not v:
            raise ValueError("Field cannot be empty")
        return InputSanitizer.sanitize_string(v)


class FileUploadRequest(BaseModel):
    """Model for file upload requests with validation."""

    filename: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(..., min_length=1, max_length=10)
    title: Optional[str] = Field(None, max_length=500)

    @field_validator("filename")
    def validate_filename(cls, v: str) -> str:
        """Validate and sanitize filename."""
        if not InputValidator.validate_file_name(v):
            raise ValueError("Invalid filename format")
        return InputSanitizer.sanitize_file_name(v)

    @field_validator("file_type")
    def validate_file_type(cls, v: str) -> str:
        """Validate file type."""
        allowed_types = ["pdf", "docx", "xlsx", "pptx"]
        if v.lower() not in allowed_types:
            raise ValueError(f"File type must be one of: {', '.join(allowed_types)}")
        return v.lower()

    @field_validator("title")
    def sanitize_title(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize title."""
        if v:
            return InputSanitizer.sanitize_string(v)
        return v


class QuestionnaireRequest(BaseModel):
    """Model for questionnaire requests with validation."""

    facility_name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=255)
    answers: dict = Field(...)

    @field_validator("facility_name", "location")
    def sanitize_text(cls, v: str) -> str:
        """Sanitize text fields."""
        if not v:
            raise ValueError("Field cannot be empty")
        return InputSanitizer.sanitize_string(v)

    @field_validator("answers")
    def validate_answers(cls, v: dict) -> dict:
        """Validate answers format."""
        if not isinstance(v, dict):
            raise ValueError("Answers must be a dictionary")
        if len(v) > 1000:  # Reasonable limit
            raise ValueError("Too many answers provided")
        return v
