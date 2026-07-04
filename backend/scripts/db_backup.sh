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
PGHOST="${PGHOST:-db}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-weekly_weed_flow}"

dump_once() {
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  out="$BACKUP_DIR/weekly_weed_flow_${ts}.sql.gz"
  echo "[db_backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) dumping -> $out"
  pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" --format=plain | gzip > "$out"
  find "$BACKUP_DIR" -name 'weekly_weed_flow_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete
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
