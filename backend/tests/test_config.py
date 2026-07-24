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
