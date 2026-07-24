"""WEEKLY_WEED_FLOW backend configuration (Pydantic settings from env)."""
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

# Every placeholder ever shipped in an .env.example, plus the code's own
# default. A guard that only caught its own default would pass a deployer
# who copied .env.example and forgot to regenerate the key.
_INSECURE_DEFAULT_SECRET = "dev-change-me"
_INSECURE_SECRETS = {
    _INSECURE_DEFAULT_SECRET,
    "change-me-to-a-long-random-string",
    "CHANGE_ME",
}
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Two databases (identity vs work data — separate Postgres containers),
    # each reached through two roles: app_user is NOBYPASSRLS (request
    # handlers), app_admin is BYPASSRLS (auth lookups + provisioning).
    users_database_url: str = "postgresql://app_user:app_user@db-users:5432/wwf_users"
    users_admin_database_url: str = "postgresql://app_admin:app_admin@db-users:5432/wwf_users"
    tasks_database_url: str = "postgresql://app_user:app_user@db-tasks:5432/wwf_tasks"
    tasks_admin_database_url: str = "postgresql://app_admin:app_admin@db-tasks:5432/wwf_tasks"

    # "production" (default, safe) or "development". Gates the insecure-
    # SECRET_KEY guard below — set ENVIRONMENT=development locally to allow
    # the placeholder key during first-time setup.
    environment: str = "production"

    # Live demo mode (app/api/demo.py + app/demo_org.py): OFF by default
    # everywhere — /demo/* 404s unless DEMO_ENABLED=true is set on the stack
    # (currently the wwf_mass test stack only; production stays off).
    demo_enabled: bool = False

    # Auth
    secret_key: str = _INSECURE_DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    remember_device_expire_days: int = 7
    password_min_length: int = 12

    # AI / Letta (always-on layer)
    letta_base_url: str = "http://host.docker.internal:8283"
    letta_mcp_url: str = "http://host.docker.internal:6507"
    qdrant_url: str = "http://host.docker.internal:6333"
    letta_api_key: str = ""

    # QMS Studio federation (Phase 1 of the unification — see
    # docs/UNIFICATION-ANALYSIS-2026-07.md). The internal qms-api container
    # is reached only through the authed proxy router (app/api/qms.py); an
    # EMPTY key means "not deployed here" and the proxy answers 503 without
    # attempting, so local/dev/e2e degrade cleanly.
    qms_api_url: str = "http://qms-api:8000"
    qms_api_key: str = ""
    # GrowFlow DocEngine (docengine/): the dedicated Letta-powered document
    # AI service — internal-only container, same key-injection pattern.
    docengine_url: str = "http://docengine:8000"
    docengine_api_key: str = ""

    # CORS. (APP_HOST also exists as a bare env var — read directly by
    # docker-compose.yml's Traefik routing rule, not by this app, so it has
    # no corresponding Settings field here.)
    cors_origins: str = "*"


settings = Settings()


def is_development(env: str) -> bool:
    """Fail-safe, not fail-open: True only for the exact string 'development'.
    Anything else — 'prod', 'Production ', a typo, an unset/mistyped
    platform-injected value — is treated as production-like. A guard that
    instead allow-listed the literal string 'production' would silently
    fall through to a warning for any other value, leaving a shipped
    placeholder SECRET_KEY active on a real deployment. Shared by the
    SECRET_KEY guard below and main.py's /docs gate so the two can never
    drift apart."""
    return env.strip().lower() == "development"


def docs_kwargs(env: str) -> dict:
    """FastAPI docs/redoc/openapi kwargs — enabled only in development. A
    regulated QC LIMS's complete route/schema map must not be browsable
    unauthenticated on a real deployment."""
    dev = is_development(env)
    return {
        "docs_url": "/docs" if dev else None,
        "redoc_url": "/redoc" if dev else None,
        "openapi_url": "/openapi.json" if dev else None,
    }


_secret_is_weak = (
    settings.secret_key in _INSECURE_SECRETS or len(settings.secret_key) < _MIN_SECRET_LENGTH
)
if _secret_is_weak:
    if not is_development(settings.environment):
        raise RuntimeError(
            f"SECRET_KEY is a known placeholder or shorter than {_MIN_SECRET_LENGTH} characters. "
            "Set a real SECRET_KEY (e.g. `openssl rand -hex 32`) before running with "
            "ENVIRONMENT=production, or set ENVIRONMENT=development to bypass this check for "
            "local development."
        )
    logging.getLogger(__name__).warning(
        f"SECRET_KEY is a known placeholder or shorter than {_MIN_SECRET_LENGTH} characters — "
        "fine for local development, never deploy this to production."
    )
