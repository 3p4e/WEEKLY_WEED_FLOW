"""Tests for API key authentication (CONTENT_CREATOR_FRAMEWORK/auth.py)."""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CONTENT_CREATOR_FRAMEWORK"))

import auth  # noqa: E402


def test_verify_api_key_accepts_valid_key():
    assert auth.verify_api_key(auth.API_KEY) == auth.API_KEY


def test_verify_api_key_rejects_missing_key():
    with pytest.raises(HTTPException) as exc:
        auth.verify_api_key(None)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_invalid_key():
    with pytest.raises(HTTPException) as exc:
        auth.verify_api_key("wrong-key")
    assert exc.value.status_code == 401


def test_is_api_key_valid():
    assert auth.is_api_key_valid(auth.API_KEY)
    assert not auth.is_api_key_valid("wrong-key")
