"""WEEKLY_WEED_FLOW backend configuration (Pydantic settings from env)."""
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "dev-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Two DSNs → two roles. app_user is NOBYPASSRLS (request handlers);
    # app_admin is BYPASSRLS (auth lookups + provisioning).
    database_url: str = "postgresql://app_user:app_user@db:5432/weekly_weed_flow"
    admin_database_url: str = "postgresql://app_admin:app_admin@db:5432/weekly_weed_flow"

    # "production" (default, safe) or "development". Gates the insecure-
    # SECRET_KEY guard below — set ENVIRONMENT=development locally to allow
    # the placeholder key during first-time setup.
    environment: str = "production"

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

    # CORS / host
    cors_origins: str = "*"
    app_host: str = "wwf.srv1231216.hstgr.cloud"


settings = Settings()

if settings.secret_key == _INSECURE_DEFAULT_SECRET:
    if settings.environment == "production":
        raise RuntimeError(
            "SECRET_KEY is still the insecure placeholder 'dev-change-me'. Set a real "
            "SECRET_KEY (e.g. `openssl rand -hex 32`) before running with ENVIRONMENT=production, "
            "or set ENVIRONMENT=development to bypass this check for local development."
        )
    logging.getLogger(__name__).warning(
        "SECRET_KEY is the insecure placeholder 'dev-change-me' — fine for local development, "
        "never deploy this to production."
    )
