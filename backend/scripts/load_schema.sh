#!/usr/bin/env bash
# Bootstrap a fresh database from schema.sql — used by the test suite and CI.
#
# schema.sql is a raw `pg_dump` from a PostgreSQL 17 server; it sets
# `transaction_timeout`, a session parameter that only exists on PG >= 17.
# Target Postgres for this project (local dev, CI, and this script) is 16,
# so that one line is filtered out before loading — everything else in the
# dump is plain DDL/RLS policies with no other version-specific syntax.
#
# Usage: load_schema.sh <database-url-or-name> [psql-connection-args...]
#   backend/scripts/load_schema.sh weekly_weed_flow_test
#   backend/scripts/load_schema.sh weekly_weed_flow_test -h localhost -U postgres
set -euo pipefail

SCHEMA_FILE="$(dirname "${BASH_SOURCE[0]}")/../schema.sql"
DB_NAME="$1"
shift

grep -v '^SET transaction_timeout' "$SCHEMA_FILE" | psql -v ON_ERROR_STOP=1 -d "$DB_NAME" "$@"
