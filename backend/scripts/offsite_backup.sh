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
BACKUP_DIR="${BACKUP_DIR:-/backups}"
OFFSITE_RETENTION_DAYS="${OFFSITE_RETENTION_DAYS:-60}"
# The remote rotation only runs while local dumps are still being produced
# AND this cycle's copy demonstrably landed. Unconditionally, it would age
# the offsite set to EMPTY within OFFSITE_RETENTION_DAYS if db-backup wedged
# while rclone kept working (review 2026-09-27, DI-10) — or if the remote
# kept accepting deletes while refusing uploads (quota exhausted, an OAuth
# token revoked for writes: rclone's delete is a separate API call that can
# succeed when uploads are rejected), which the first guard did not see
# (DI2-05). 30 h is one daily cycle plus slack.
LOCAL_FRESH_MAX_S="${LOCAL_FRESH_MAX_S:-108000}"

newest_local_dump() {
  # Path of the newest tasks dump, or empty when there is none.
  ls -1t "$BACKUP_DIR"/wwf_tasks_*.sql.gz 2>/dev/null | head -n 1
}

newest_local_age_s() {
  # Age in seconds of the newest tasks dump, or empty when there is none.
  f=$(newest_local_dump)
  [ -n "$f" ] || return 0
  echo $(( $(date +%s) - $(stat -c %Y "$f") ))
}

remote_has() {
  # True when the remote lists exactly this file name (the newest local dump,
  # proving this cycle's copy — or an earlier one — put it there).
  rclone lsf "$REMOTE" --files-only --include "/$1" 2>/dev/null | grep -qx "$1"
}

# One cycle: copy, then rotate only when it is safe to. Exit status is the
# copy's, so `--once` can be checked by a caller.
offsite_once() {
  copy_ok=0
  if rclone copy "$BACKUP_DIR" "$REMOTE" --transfers 2 --checkers 4 --log-level NOTICE; then
    copy_ok=1
    echo "offsite: copy ok $(date -u +%FT%TZ)"
  else
    echo "offsite: COPY FAILED $(date -u +%FT%TZ) — will retry next cycle" >&2
  fi
  # Cap remote growth: local keeps 14 days, offsite keeps 60 independently
  # (deletions here are age-based only — never mirrored from local state),
  # and ONLY while (a) a fresh local dump proves the producer is alive,
  # (b) this cycle's copy succeeded, and (c) the remote listing shows that
  # newest dump is actually there. A remote that accepts deletes but not
  # uploads fails (b) and (c) and is never trimmed.
  age=$(newest_local_age_s)
  newest=$(newest_local_dump)
  if [ "$copy_ok" -ne 1 ]; then
    echo "offsite: copy failed this cycle — SKIPPING remote rotation so the offsite set is kept" >&2
  elif [ -z "$age" ] || [ "$age" -gt "$LOCAL_FRESH_MAX_S" ]; then
    echo "offsite: newest local dump is ${age:-absent}s old (> ${LOCAL_FRESH_MAX_S}s) — db-backup is not producing; SKIPPING remote rotation so the offsite set is kept" >&2
  elif ! remote_has "$(basename "$newest")"; then
    echo "offsite: the remote does not list $(basename "$newest") although the copy reported success — SKIPPING remote rotation" >&2
  else
    rclone delete "$REMOTE" --min-age "${OFFSITE_RETENTION_DAYS}d" --log-level NOTICE || true
  fi
  return $(( 1 - copy_ok ))
}

if [ "${1:-}" = "--once" ]; then
  offsite_once
  exit $?
fi

# Give db-backup a head start on first boot so the very first pass already
# has a dump to ship.
sleep "${INITIAL_DELAY_S:-300}"

while true; do
  offsite_once
  sleep 86400
done
