"""
Application configuration using Pydantic BaseSettings.

Reads values from .env file and environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/qc_lims"
    )

    # Authentication
    secret_key: str = "change-me-to-a-random-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost",
    ]

    # Application
    app_name: str = "Purely Plant GmbH QC LIMS API"
    debug: bool = False

    # GMP compliance
    data_retention_years: int = 10
    inactivity_timeout_minutes: int = 15
    max_login_attempts: int = 5

    # Google OAuth
    google_client_id: str = ""

    # Qdrant vector database
    qdrant_url: str = "http://localhost:6333"

    # Letta AI service (KVM4 via SSH tunnel)
    letta_base_url: str = "http://localhost:8283"
    letta_mcp_url: str = "http://localhost:6507"

    # VoyageAI embeddings
    voyage_api_key: str = ""


settings = Settings()
