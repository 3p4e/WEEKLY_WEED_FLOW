#!/bin/sh
# Rotating local pg_dump backups for the WWF Postgres database.
#
# Runs in a loop inside the db-backup container (see docker-compose.yml):
# dump, gzip, prune anything older than RETENTION_DAYS, sleep, repeat. Local
# volume only — see docs/BACKUP.md for the documented residual risk (no
# offsite copy) and the restore procedure.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
PGUSER="${PGUSER:-postgres}"
# Two databases in two containers. The dumps run back-to-back, NOT atomically
# across the pair — a restore of both files can be up to a few seconds apart
# in state. Acceptable for this app (see docs/BACKUP.md).
USERS_PGHOST="${USERS_PGHOST:-wwf-db-users}"
TASKS_PGHOST="${TASKS_PGHOST:-wwf-db-tasks}"
USERS_PGDATABASE="${USERS_PGDATABASE:-wwf_users}"
TASKS_PGDATABASE="${TASKS_PGDATABASE:-wwf_tasks}"

# Dumps "$@" (a pg_dump/pg_dumpall command) to "$2.gz", checking pg_dump's own
# exit code (a bare `pg_dump | gzip` hides it behind gzip's, which still exits
# 0 on a truncated/empty input) and gzip-testing the result before trusting it
# — a partial dump from a transient connection blip must never look healthy.
dump_and_gzip() {
  desc="$1"; out="$2"; shift 2
  if "$@" > "$out"; then
    gzip -f "$out"
    if gzip -t "${out}.gz" 2>/dev/null; then
      return 0
    fi
    echo "[db_backup] ERROR: ${out}.gz failed gzip integrity check ($desc)" >&2
    rm -f "${out}.gz"
  else
    echo "[db_backup] ERROR: dump command failed for $desc" >&2
    rm -f "$out"
  fi
  return 1
}

dump_once() {
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  ok=1
  for pair in "users:$USERS_PGHOST:$USERS_PGDATABASE" "tasks:$TASKS_PGHOST:$TASKS_PGDATABASE"; do
    which=${pair%%:*}; rest=${pair#*:}; host=${rest%%:*}; db=${rest#*:}
    out="$BACKUP_DIR/wwf_${which}_${ts}.sql"
    echo "[db_backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) dumping $db@$host -> ${out}.gz"
    dump_and_gzip "$db@$host" "$out" pg_dump -h "$host" -U "$PGUSER" -d "$db" --format=plain || ok=0
  done
  # Per-database pg_dump never captures cluster-global roles (app_user
  # NOBYPASSRLS / app_admin BYPASSRLS + their attributes) — each container is
  # its own independent Postgres instance, so both need a globals-only dump
  # or a restore into a fresh cluster fails on the GRANT/OWNER statements.
  for pair in "users:$USERS_PGHOST" "tasks:$TASKS_PGHOST"; do
    which=${pair%%:*}; host=${pair#*:}
    out="$BACKUP_DIR/wwf_${which}_globals_${ts}.sql"
    echo "[db_backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) dumping globals@$host -> ${out}.gz"
    dump_and_gzip "globals@$host" "$out" pg_dumpall -h "$host" -U "$PGUSER" --globals-only || ok=0
  done
  if [ "$ok" -eq 1 ]; then
    find "$BACKUP_DIR" -name 'wwf_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete
  else
    echo "[db_backup] one or more dumps failed this cycle — skipping rotation so existing good backups are kept" >&2
  fi
  echo "[db_backup] done"
}

if [ "${1:-}" = "--once" ]; then
  dump_once
  exit 0
fi

while true; do
  dump_once
  sleep 86400
done
