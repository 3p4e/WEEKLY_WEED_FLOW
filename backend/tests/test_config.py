"""app/config.py — the fail-safe environment guard and the development-only
docs-exposure gate. Both derive from is_development() so they can never
drift apart (H1: SECRET_KEY guard only tripped for the literal string
"production"; H2: /docs was always reachable regardless of environment)."""
import os
import subprocess
import sys
from pathlib import Path

from app.config import docs_kwargs, is_development

_BACKEND_DIR = str(Path(__file__).resolve().parents[1])


def test_is_development_only_true_for_the_exact_string():
    assert is_development("development") is True
    assert is_development(" Development ") is True  # whitespace/case-insensitive
    assert is_development("production") is False
    assert is_development("prod") is False           # the exact fail-open bug: common shorthand
    assert is_development("") is False
    assert is_development("Production") is False


def test_docs_kwargs_disabled_outside_development():
    assert docs_kwargs("production") == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert docs_kwargs("prod") == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_docs_kwargs_enabled_in_development():
    assert docs_kwargs("development") == {
        "docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def test_app_docs_enabled_under_the_test_environment():
    # conftest.py sets ENVIRONMENT=development for the whole suite — proves
    # nothing broke for local dev/CI, which relies on /docs being reachable.
    from app.main import app
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"


def _run_import_with_env(environment):
    # The SECRET_KEY guard runs at module-import time as a side effect —
    # exercised in a subprocess so it can't poison this process's
    # already-imported app.config for the rest of the suite.
    env = {**os.environ, "ENVIRONMENT": environment, "SECRET_KEY": "dev-change-me"}
    return subprocess.run([sys.executable, "-c", "import app.config"],
                          cwd=_BACKEND_DIR, env=env, capture_output=True, text=True)


def test_secret_key_guard_raises_for_a_placeholder_outside_development():
    r = _run_import_with_env("prod")  # common shorthand — the exact fail-open bug
    assert r.returncode != 0
    assert "SECRET_KEY" in r.stderr


def test_secret_key_guard_still_raises_for_the_literal_production_string():
    r = _run_import_with_env("production")
    assert r.returncode != 0
    assert "SECRET_KEY" in r.stderr


def test_secret_key_guard_allows_placeholder_under_development():
    r = _run_import_with_env("development")
    assert r.returncode == 0


# ── BC-23 (review 2026-09-27): the production floor on the password policy ──
from app.config import (  # noqa: E402
    _PASSWORD_MIN_LENGTH_FLOOR, capture_import_token, effective_password_min_length)


def test_password_floor_raises_a_weak_policy_outside_development_and_warns():
    length, warning = effective_password_min_length(4, "production", override=False)
    assert length == _PASSWORD_MIN_LENGTH_FLOOR
    assert warning and "PASSWORD_POLICY_OVERRIDE" in warning
    # 'prod' and any other non-development string count as production
    assert effective_password_min_length(4, "prod", override=False)[0] == _PASSWORD_MIN_LENGTH_FLOOR


def test_password_floor_yields_to_a_deliberate_override_but_still_warns():
    length, warning = effective_password_min_length(4, "production", override=True)
    assert length == 4
    assert warning and "below the production floor" in warning


def test_password_floor_is_not_applied_in_development_or_above_the_floor():
    assert effective_password_min_length(4, "development", override=False) == (4, None)
    assert effective_password_min_length(20, "production", override=False) == (20, None)


def _import_with(env_extra: dict):
    env = {**os.environ, "SECRET_KEY": "a-real-looking-secret-that-is-long-enough-1234", **env_extra}
    return subprocess.run(
        [sys.executable, "-c",
         "import logging; logging.basicConfig(level=logging.WARNING);"
         "from app.config import settings; print('MIN', settings.password_min_length)"],
        cwd=_BACKEND_DIR, env=env, capture_output=True, text=True)


def test_password_floor_is_applied_to_the_live_settings_in_production():
    """The whole point is change_password reading the enforced value, so the
    floor must land on settings.password_min_length itself, at import."""
    r = _import_with({"ENVIRONMENT": "production", "PASSWORD_MIN_LENGTH": "4"})
    assert r.returncode == 0, r.stderr
    assert f"MIN {_PASSWORD_MIN_LENGTH_FLOOR}" in r.stdout
    assert "below the production floor" in r.stderr
    r = _import_with({"ENVIRONMENT": "production", "PASSWORD_MIN_LENGTH": "4",
                      "PASSWORD_POLICY_OVERRIDE": "true"})
    assert r.returncode == 0, r.stderr
    assert "MIN 4" in r.stdout
    assert "PASSWORD_POLICY_OVERRIDE is set" in r.stderr


# ── BC-11: the capture connector's token has the same placeholder guard ──
def test_capture_token_placeholders_and_short_values_are_unset():
    assert capture_import_token("change-me") == ""
    assert capture_import_token("CHANGE_ME") == ""
    assert capture_import_token("x" * 31) == ""
    assert capture_import_token("") == ""
    assert capture_import_token(None) == ""
    real = "3f1c9e7a5b2d4c8e6a0f1b3d5c7e9a2b4d6f8c0e1a3b5d7f"
    assert capture_import_token(real) == real
    assert capture_import_token(f"  {real}  ") == real


def test_weak_capture_token_warns_at_startup():
    r = _import_with({"ENVIRONMENT": "development", "CAPTURE_IMPORT_TOKEN": "change-me"})
    assert r.returncode == 0, r.stderr
    assert "CAPTURE_IMPORT_TOKEN" in r.stderr and "treated as UNSET" in r.stderr
