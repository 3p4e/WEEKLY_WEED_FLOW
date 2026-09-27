"""WEEKLY_WEED_FLOW backend configuration (Pydantic settings from env)."""
import logging
import os

from pydantic import Field
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

# The production floor on the password policy (review 2026-09-27, BC-23).
# PASSWORD_MIN_LENGTH is an env knob so a facility can tighten it, and the
# owner has asked, more than once, to loosen it "for now" for trial accounts.
# On this stack — which IS the production system — a loosened policy puts
# manager and ADMIN accounts with guessable passwords on the internet-facing
# login. So below this floor the setting is raised back to the floor unless
# PASSWORD_POLICY_OVERRIDE=true is set alongside it: the override is the
# deliberate, greppable record that someone chose the weaker policy, and it
# is logged at every start so it cannot be forgotten. Development is exempt.
_PASSWORD_MIN_LENGTH_FLOOR = 12

# The capture connector's static bearer (app/api/capture.py). It acts as the
# configured capture user — an ADMIN in practice — on an internet-reachable
# route, so a placeholder or short value must be treated as UNSET (the route
# then falls back to normal auth) rather than honoured (review 2026-09-27,
# BC-11). Mirrors the SECRET_KEY guard: catch every placeholder ever shipped,
# not only the code's own default.
_INSECURE_CAPTURE_TOKENS = {"change-me", "CHANGE_ME", "changeme", "test", "secret"}
_MIN_CAPTURE_TOKEN_LENGTH = 32


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
    # A session token's life. Bounded below at one minute — zero or a negative
    # value would mint tokens that are expired on arrival.
    access_token_expire_minutes: int = Field(default=15, ge=1)
    # See _PASSWORD_MIN_LENGTH_FLOOR: outside development this is raised to
    # the floor unless password_policy_override is set.
    password_min_length: int = Field(default=12, ge=1)
    password_policy_override: bool = False

    # Business timezone for week windows, work-session classification and the
    # weekly snapshot's fire time. Read through Settings like everything else
    # rather than via a bare os.environ at import time in two separate modules
    # (app/worktime.py and scripts/scheduler.py), which is how they could
    # silently disagree — and a snapshot that fires on a different week
    # boundary than the report it summarises is not obviously wrong from
    # either side.
    snapshot_tz: str = "Europe/Skopje"

    # AI / Letta (always-on layer)
    letta_base_url: str = "http://host.docker.internal:8283"
    letta_api_key: str = ""

    # GrowFlow DocEngine (docengine/): the dedicated Letta-powered document
    # AI service — internal-only container, reached only through the authed
    # proxy router (app/api/qms.py) with the key injected server-side. An
    # EMPTY key means "not deployed here" and the proxy answers 503.
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


def capture_import_token(raw: str | None) -> str:
    """The capture connector's bearer as the route should honour it: the
    configured value, or "" (treated as unset) when it is a known placeholder
    or shorter than _MIN_CAPTURE_TOKEN_LENGTH. Pure, so app/api/capture.py can
    apply it to the live environment on every request (the connector's token
    is rotated by redeploying with a new env value) and tests can exercise it
    without touching the process environment."""
    token = (raw or "").strip()
    if not token or token in _INSECURE_CAPTURE_TOKENS or len(token) < _MIN_CAPTURE_TOKEN_LENGTH:
        return ""
    return token


def effective_password_min_length(configured: int, env: str, override: bool) -> tuple[int, str | None]:
    """(the minimum length the app enforces, a warning to log or None).

    Development keeps whatever was configured. Everywhere else a value below
    the floor is raised to the floor, unless the override flag records that
    the weaker policy is deliberate — in which case it stands, and is warned
    about, on every start."""
    if is_development(env) or configured >= _PASSWORD_MIN_LENGTH_FLOOR:
        return configured, None
    if override:
        return configured, (
            f"PASSWORD_MIN_LENGTH={configured} is below the production floor of "
            f"{_PASSWORD_MIN_LENGTH_FLOOR} and PASSWORD_POLICY_OVERRIDE is set — the weaker "
            "policy is in force. Accounts created under it have guessable passwords on an "
            "internet-facing login; rotate them and remove the override.")
    return _PASSWORD_MIN_LENGTH_FLOOR, (
        f"PASSWORD_MIN_LENGTH={configured} is below the production floor of "
        f"{_PASSWORD_MIN_LENGTH_FLOOR}; enforcing {_PASSWORD_MIN_LENGTH_FLOOR}. Set "
        "PASSWORD_POLICY_OVERRIDE=true as well if the weaker policy is deliberate.")


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

# Same problem as the SECRET_KEY guard above — the insecure value is the
# DEFAULT, so forgetting to set the real one is silent — but deliberately NOT
# the same remedy. This one warns where that one raises, and the asymmetry is
# the point:
#
#   * The risk is genuinely smaller. Auth is bearer-only and allow_credentials
#     is False (main.py), so a wildcard origin does not let another site read
#     an authenticated response; it only lets any origin reach the
#     unauthenticated surface from a victim's browser, behind nginx.
#   * The cost of being wrong is not. Raising here turns "CORS_ORIGINS was
#     never set on this deployment" into "the backend will not boot" — an
#     outage of a production QMS, triggered by the deploy that shipped this
#     line, to close a finding of that size. A guard must not be more
#     dangerous than what it guards against.
#
# Promote this to a raise once a deployment is confirmed to set CORS_ORIGINS
# (the committed .env.example does; the live env file is not in this repo).
if settings.cors_origins.strip() == "*":
    logging.getLogger(__name__).warning(
        "CORS_ORIGINS is '*' (the default) — every origin may reach this API's unauthenticated "
        "surface. Fine for local development; set the deployment's real scheme+host "
        "(e.g. CORS_ORIGINS=https://wwf.example.com) in production."
    )

# The password floor (BC-23): applied in place so every reader of
# settings.password_min_length — change_password's check and its error text —
# sees the enforced value, not the configured one.
settings.password_min_length, _pw_warning = effective_password_min_length(
    settings.password_min_length, settings.environment, settings.password_policy_override)
if _pw_warning:
    logging.getLogger(__name__).warning(_pw_warning)

# The capture token (BC-11) is read from the environment per request by
# app/api/capture.py, not through Settings, so that a rotation is a redeploy
# and nothing else. The startup warning lives here with the other guards so
# an operator sees every weak-credential complaint in one place.
_raw_capture_token = os.environ.get("CAPTURE_IMPORT_TOKEN", "")
if _raw_capture_token and not capture_import_token(_raw_capture_token):
    logging.getLogger(__name__).warning(
        f"CAPTURE_IMPORT_TOKEN is a known placeholder or shorter than {_MIN_CAPTURE_TOKEN_LENGTH} "
        "characters — it is being treated as UNSET, so POST /capture/import accepts only normal "
        "user sessions. Generate a real one (e.g. `openssl rand -hex 24`) for the connector."
    )
