"""Runtime configuration (pydantic-settings). Override via PLANNER_* env vars or .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANNER_", env_file=".env", extra="ignore")

    # Database (PostgreSQL + pgvector). Async driver = psycopg3.
    database_url: str = "postgresql+psycopg://planner:planner@127.0.0.1:5432/planner_dev"

    # API bind.
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765

    # CORS origins for the web app (comma-separated or JSON list via PLANNER_CORS_ORIGINS).
    cors_origins: list[str] = [
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ]

    # JWT auth. Override jwt_secret in any non-dev environment.
    jwt_secret: str = "dev-insecure-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 720  # 12h working day

    # Optional Letta agent gateway (AI features degrade gracefully when unset).
    gateway_url: str = ""
    gateway_token: str = ""

    # Direct Letta stack (for governance/compliance agents not on the gateway
    # allow-list — schema_advisor, qms_architect, gmp_*). Degrades gracefully.
    letta_base_url: str = ""
    letta_api_key: str = ""

    # Weekly snapshot → Letta source wiring. When letta_snapshot_source_id (and the
    # Letta base/key) are set, the weekly export pushes its Markdown digest to that
    # source so the weekly_coordinator / executive_analytics agents can reason over it.
    letta_snapshot_source_id: str = ""
    # In-process weekly scheduler (Thursday 18:00 UTC) — runs the Fri→Thu export.
    enable_weekly_scheduler: bool = False

    # Row-Level Security: when app_database_url is set, request-scoped data access
    # runs through the NOBYPASSRLS role (growflow_app) with SET LOCAL identity.
    # Login / provisioning / migrations always use database_url (admin/owner).
    # Unset => single-engine fallback (RLS still defined in the DB).
    app_database_url: str = ""

    # Auth hardening (SUMA/WWF methodology).
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    otp_ttl_hours: int = 72            # provisioned temp-password validity

    environment: str = "dev"  # dev | validation | prod


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
