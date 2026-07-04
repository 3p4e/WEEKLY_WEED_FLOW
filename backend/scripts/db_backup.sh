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

dump_once() {
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  for pair in "users:$USERS_PGHOST:$USERS_PGDATABASE" "tasks:$TASKS_PGHOST:$TASKS_PGDATABASE"; do
    which=${pair%%:*}; rest=${pair#*:}; host=${rest%%:*}; db=${rest#*:}
    out="$BACKUP_DIR/wwf_${which}_${ts}.sql.gz"
    echo "[db_backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) dumping $db@$host -> $out"
    pg_dump -h "$host" -U "$PGUSER" -d "$db" --format=plain | gzip > "$out"
  done
  find "$BACKUP_DIR" -name 'wwf_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete
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
