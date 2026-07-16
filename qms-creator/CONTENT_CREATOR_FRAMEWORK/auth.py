"""
API Authentication and Security Module

Provides API key-based authentication for the QMS API endpoints.
"""

import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

# Get API key from environment variable
API_KEY = os.getenv("API_KEY", "default-dev-key-change-in-production")
API_KEY_NAME = "X-API-Key"

# API Key header security scheme
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verify_api_key(api_key: Optional[str] = Depends(api_key_header)) -> str:
    """
    Verify the API key from the request header.

    Args:
        api_key: The API key from the X-API-Key header

    Returns:
        str: The verified API key

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Provide it in the X-API-Key header.",
        )
    if not is_api_key_valid(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key.",
        )
    return api_key


def is_api_key_valid(api_key: str) -> bool:
    """
    Check if the provided API key is valid.

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return api_key == API_KEY


class APIKeyValidator:
    """
    Context manager for API key validation in background tasks or custom flows.
    """

    def __init__(self, api_key: str):
        """
        Initialize the validator with an API key.

        Args:
            api_key: The API key to validate
        """
        self.api_key = api_key
        self.is_valid = False

    def __enter__(self):
        """Validate the API key on entry."""
        if not is_api_key_valid(self.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key.",
            )
        self.is_valid = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up on exit."""
        self.is_valid = False
