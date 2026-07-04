#!/usr/bin/env bash
# Bootstrap a fresh database from one of the generated schema dumps — used by
# the test suite and CI. There are two databases now (users + tasks), so the
# schema file is an explicit argument:
#
#   load_schema.sh users wwf_users_test [psql-connection-args...]
#   load_schema.sh tasks wwf_tasks_test -h localhost -U postgres
#
# The dumps are raw `pg_dump` output; a PG17-origin dump sets
# `transaction_timeout`, a session parameter that only exists on PG >= 17,
# so that line is filtered out for PG16 targets (CI, local dev). Everything
# else is plain DDL/RLS with no version-specific syntax.
set -euo pipefail

WHICH="$1"   # users | tasks
DB_NAME="$2"
shift 2

SCHEMA_FILE="$(dirname "${BASH_SOURCE[0]}")/../schema.${WHICH}.sql"
[ -f "$SCHEMA_FILE" ] || { echo "no such schema file: $SCHEMA_FILE" >&2; exit 1; }

grep -v '^SET transaction_timeout' "$SCHEMA_FILE" | psql -v ON_ERROR_STOP=1 -d "$DB_NAME" "$@"
