#!/bin/sh
# Offsite copy of the local dump volume → an ENCRYPTED (rclone crypt) folder
# on Google Drive. Runs as its own container (compose: backup-offsite) beside
# db-backup, which owns dumping + local 14-day rotation.
#
# Deliberately `rclone copy`, never `sync`: a mirror would happily propagate a
# local wipe (disk failure mid-rotation, ransomware, fat-fingered volume rm)
# to the offsite copy. copy only ever ADDS; remote retention is capped
# separately below so Drive doesn't grow forever.
#
# Requires /config/rclone/rclone.conf (mounted from the host, mode 0600) with:
#   [wwf-gdrive]  type=drive  (OAuth token)
#   [wwf-crypt]   type=crypt  remote=wwf-gdrive:wwf-backups  (password pair)
# Losing the crypt password = losing every offsite backup — custody notes in
# docs/BACKUP.md ("Offsite copy").
set -u

REMOTE="${RCLONE_REMOTE:-wwf-crypt:}"
OFFSITE_RETENTION_DAYS="${OFFSITE_RETENTION_DAYS:-60}"

# Give db-backup a head start on first boot so the very first pass already
# has a dump to ship.
sleep "${INITIAL_DELAY_S:-300}"

while true; do
  if rclone copy /backups "$REMOTE" --transfers 2 --checkers 4 --log-level NOTICE; then
    echo "offsite: copy ok $(date -u +%FT%TZ)"
  else
    echo "offsite: COPY FAILED $(date -u +%FT%TZ) — will retry next cycle" >&2
  fi
  # Cap remote growth: local keeps 14 days, offsite keeps 60 independently
  # (deletions here are age-based only — never mirrored from local state).
  rclone delete "$REMOTE" --min-age "${OFFSITE_RETENTION_DAYS}d" --log-level NOTICE || true
  sleep 86400
done
