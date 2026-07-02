#!/usr/bin/env bash
# Start the FastAPI backend for e2e tests: same test database as pytest
# (backend/tests/), a real venv, and the env vars app/config.py needs.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

export ENVIRONMENT=development
export SECRET_KEY="${SECRET_KEY:-local-e2e-secret-not-for-production}"
export DATABASE_URL="${DATABASE_URL:-postgresql://app_user:testpw_user@localhost:5432/weekly_weed_flow_test}"
export ADMIN_DATABASE_URL="${ADMIN_DATABASE_URL:-postgresql://app_admin:testpw_admin@localhost:5432/weekly_weed_flow_test}"

source .venv/bin/activate
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
