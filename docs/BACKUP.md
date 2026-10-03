# Database backups

Prior to this document, WWF had **no backup mechanism at all** — this was the
single largest operational gap flagged by the 2026-07 architecture review.
This document describes what exists now, its scope, and its honest limits.

## Scope

Backs up **WWF's own two Postgres databases** (`wwf_users` in `wwf-db-users`
and `wwf_tasks` in `wwf-db-tasks` on KVM4) **and the DocEngine output volume**
(`docengine_out` — every controlled document the `docengine.documents`
registry points at: SOPs, annexes and every released certificate's COQ
artefact). Until 2026-09-27 the volume was in no backup at all, so a host or
volume loss would have restored the registry rows from the `wwf_tasks` dump
with every `.docx` they name gone and every download answering 410
(review DI-10). It does **not** cover:

- Letta's own Postgres (a separate, pre-existing stack on the same host,
  outside this repo).
- RAGflow's datasets and vector store.
- The Docker volumes for any other service on the box.

## Mechanism

`backend/scripts/db_backup.sh`, run in the `db-backup` container
(`docker-compose.yml`): a loop that dumps BOTH databases with `pg_dump`
back-to-back, gzips them, archives the DocEngine output volume (mounted
read-only at `/docengine-out`) as one tarball, deletes anything older than
`RETENTION_DAYS` (default 14), then sleeps 24 hours and repeats. Files land in
the `weekly_weed_flow_backups` named Docker volume as
`wwf_users_<UTC timestamp>.sql.gz` + `wwf_tasks_<UTC timestamp>.sql.gz` +
`docengine_out_<UTC timestamp>.tar.gz` (plus the two `*_globals_*` role
dumps). A cycle in which any of these fails skips the rotation, so the last
good set is kept. If the volume is not mounted the script says so on every
cycle and backs up the databases anyway — the watchdog's `backup_fresh`
check reports the missing archive as a WARN (`ops/README.md`).

**Freshness is watched.** `ops/watchdog.sh` (`backup_fresh`, `offsite_fresh`)
FAILs when the newest local dump is older than 30 h and, when the offsite
container is running, when the newest remote object is older than 48 h. Before
2026-09-27 the only freshness signal was a warning inside the nightly
migration rehearsal.

The two dumps are **not atomic as a pair** — they run seconds apart, so a
restore of both can disagree by whatever happened in that gap (e.g. a
profile created between dumps whose tasks-side rows exist). Acceptable for
this planning tool; restore-time reconciliation is: users DB wins on
identity, orphaned tasks-side uuids just render as "—".

The loop is a plain `sleep 86400`, not a fixed time-of-day cron — it drifts
slowly against wall-clock across restarts. That's an accepted trade-off: it's
simpler than adding a cron daemon to the image, and a same-day rotating
backup doesn't need to fire at a precise minute.

Run a backup on demand (e.g. before a risky migration) with:

```bash
docker exec wwf-db-backup sh /usr/local/bin/db_backup.sh --once
```

## Retention

**Local:** 14 rotating daily dumps in the `weekly_weed_flow_backups` volume.
**Offsite:** 60 days on Google Drive (encrypted), independent of local — see
next section. Local rotation covers accidental data loss, a bad migration, or
an operator mistake; the offsite copy covers host-level disaster (disk
failure, fire, VPS loss).

## Offsite copy (Google Drive, encrypted)

The `backup-offsite` container (`docker-compose.yml`) runs
`backend/scripts/offsite_backup.sh`: a daily `rclone copy` of the local dump
volume to an **rclone-crypt-encrypted** folder on Google Drive (filenames and
contents both encrypted — Google never sees plaintext GMP-adjacent data).

Key properties:

- **`copy`, never `sync`** — the offsite pass only ever ADDS files. A local
  wipe (disk failure mid-rotation, ransomware, `docker volume rm`) cannot
  propagate deletions to Drive. Remote retention is enforced separately by
  age (`OFFSITE_RETENTION_DAYS`, default 60) — and **only while the newest
  local dump is under 30 h old, this cycle's `rclone copy` succeeded, and
  the remote listing shows that newest dump**. Unconditionally, a wedged
  `db-backup` with a working `rclone` would have aged the offsite set to
  empty in 60 days, exactly when it was the only backup left (DI-10); a
  remote that kept accepting deletes while refusing uploads — quota
  exhausted, an OAuth token revoked for writes — would have done the same
  under the first guard (DI2-05). Now the remote rotation pauses and the
  script says why on every cycle. `offsite_backup.sh --once` runs one cycle
  and exits with the copy's status.
- **The DocEngine mount is part of the backup once it has been.** A lost
  `docengine_out` mount on `db-backup` is a warning only on a stack that has
  never archived documents; once a `docengine_out_*.tar.gz` exists the cycle
  FAILS (rotation stops, the last archive is kept), and `ops/watchdog.sh`
  reports `backup_fresh` as FAIL whenever `wwf-docengine` is running with no
  archive at all (DI2-05).
- **Status as of 2026-09-27:** the `wwf-backup-offsite` container has not run
  since the 2026-09-19 VM migration (`docs/HANDOFF.md`). Until it is brought
  back — `./rclone/rclone.conf` restored on the new host with the same crypt
  password pair, then `docker compose up -d backup-offsite` — there is **no
  offsite copy**, and the watchdog reports it as a WARN naming this state.
- **Config custody:** `./rclone/rclone.conf` on the deploy host (mode 0600,
  git-ignored) holds the Drive OAuth token and the crypt password pair.
  ⚠️ **Losing the crypt password means every offsite backup becomes
  unreadable ciphertext.** Keep an offline copy of the two crypt password
  values (they are stored obscured in rclone.conf; recover the plain values
  with `rclone reveal <obscured>`).
- **One-time setup:** `rclone authorize "drive"` on any machine with a
  browser → paste the token into the `[wwf-gdrive]` remote; the `[wwf-crypt]`
  remote wraps `wwf-gdrive:wwf-backups` with generated passwords.

Verify the offsite copy / restore from it:

```bash
# list what's offsite (decrypted names)
docker exec wwf-backup-offsite rclone ls wwf-crypt:
# pull one dump back and check it's a real SQL dump
docker exec wwf-backup-offsite rclone copy wwf-crypt:wwf_tasks_<TIMESTAMP>.sql.gz /tmp/
docker exec wwf-backup-offsite sh -c 'gunzip -c /tmp/wwf_tasks_<TIMESTAMP>.sql.gz | head -5'
```

Then restore exactly as in the procedure below. Run this drill after setup
and periodically (monthly is reasonable) — a backup that has never been
restored is a hope, not a backup.

## Restore procedure (tested — see below)

1. Stop the app so nothing writes during the restore — **including DocEngine**,
   which writes its registry into `wwf_tasks` (schema `docengine`) and its
   documents into `docengine_out`:
   ```bash
   docker stop weekly_weed_flow-backend-1 wwf-scheduler wwf-docengine
   ```
2. Pick a matching-timestamp PAIR of dumps from the volume and restore each
   into a **fresh** database in its own container (never restore over the
   live one in place — create a new DB, verify it, then swap):
   ```bash
   docker exec wwf-db-backup ls /backups
   docker exec wwf-db-users psql -U postgres -c "CREATE DATABASE wwf_users_restored;"
   docker exec wwf-db-backup gunzip -c /backups/wwf_users_<TIMESTAMP>.sql.gz | \
     docker exec -i wwf-db-users psql -U postgres -d wwf_users_restored -v ON_ERROR_STOP=1
   docker exec wwf-db-tasks psql -U postgres -c "CREATE DATABASE wwf_tasks_restored;"
   docker exec wwf-db-backup gunzip -c /backups/wwf_tasks_<TIMESTAMP>.sql.gz | \
     docker exec -i wwf-db-tasks psql -U postgres -d wwf_tasks_restored -v ON_ERROR_STOP=1
   ```
3. Spot-check row counts against what you expect before cutting over:
   ```bash
   docker exec wwf-db-users psql -U postgres -d wwf_users_restored -tAc \
     "SELECT 'organizations',count(*) FROM organizations UNION ALL SELECT 'profiles',count(*) FROM profiles"
   docker exec wwf-db-tasks psql -U postgres -d wwf_tasks_restored -tAc \
     "SELECT 'tasks',count(*) FROM tasks UNION ALL SELECT 'work_sessions',count(*) FROM work_sessions UNION ALL SELECT 'ai_pins',count(*) FROM ai_pins"
   ```
4. Only once satisfied, rename databases (or repoint the four
   `*_DATABASE_URL`s) to cut the app over, then restart the three containers
   stopped in step 1.
5. **DocEngine documents.** Restore the archive taken with the same timestamp
   as the `wwf_tasks` dump you restored — the registry rows in that dump name
   exactly the files in that archive:
   ```bash
   docker exec wwf-db-backup ls /backups | grep docengine_out_
   # into a scratch directory first, never straight over the live volume
   docker run --rm -v weekly_weed_flow_backups:/backups:ro -v weekly_weed_flow_docengine_out:/out \
     alpine sh -c 'mkdir -p /out/.restore && tar -xzf /backups/docengine_out_<TIMESTAMP>.tar.gz -C /out/.restore && ls /out/.restore | wc -l'
   ```
   Spot-check a few `path` values from `docengine.documents` against the
   restored files, then move them into place (`mv /out/.restore/* /out/`) and
   remove `.restore`. A row whose file is missing answers 410 on download;
   `SELECT id, code, version, path FROM docengine.documents` lists what to
   expect.

**The single-DB version of this procedure was actually run, not just
written down** (v1: dump via `db_backup.sh --once`, restore into a scratch
DB, all row counts matched, no errors). The two-DB variant above is the
same mechanics applied per database.

See also `docs/DEPLOY.md` for how the rest of the stack is provisioned on
KVM4.

## Rotating the offsite backup credentials

Two secrets in `./rclone/rclone.conf` are worth rotating on a schedule, and
must be rotated immediately after any event where the file (or a copy of it)
left the deploy host — a VM restore/rebuild that staged it on an intermediate
machine, for instance:

- **The Google Drive OAuth token** (`[wwf-gdrive]` remote). Revoke and
  reissue:
  1. Revoke the existing grant at
     https://myaccount.google.com/permissions (find the app tied to
     `wwf-gdrive`, remove access).
  2. On any machine with a browser: `rclone authorize "drive"`, then paste
     the new token into `[wwf-gdrive]` in `./rclone/rclone.conf` on the
     deploy host (mode stays `0600`).
  3. `docker restart wwf-backup-offsite`.
  4. Verify: `docker exec wwf-backup-offsite rclone ls wwf-crypt:` still
     lists the existing dumps (proves the new token can read what the old
     one wrote) and `db_backup.sh --once` followed by a same-day offsite
     pass adds one more.

- **The crypt password pair** (`[wwf-crypt]`'s `password`/`password2`,
  wrapping `wwf-gdrive:wwf-backups`). Rotating this password does **not**
  re-encrypt files already on Drive — it only changes what new writes use —
  so treat it as opening a new vault next to the old one, not re-keying the
  old one:
  1. Generate two new obscured values: `rclone obscure <new-password>` (run
     once for `password`, once for `password2`).
  2. Point `[wwf-crypt]` at a **new** remote path (e.g.
     `wwf-gdrive:wwf-backups-2` — reusing the old path with a new password
     makes existing files unreadable through the new config, since crypt
     derives per-file keys from the password) and set the two new obscured
     values.
  3. Keep the **old** password pair recorded offline (a password manager,
     not this repo) until every backup that used it has aged out of
     `OFFSITE_RETENTION_DAYS` and is no longer needed — a rotated-away
     password is the only way to read what was written before rotation.
  4. `docker restart wwf-backup-offsite`; verify with the same `rclone ls` /
     round-trip check as above, against the new path.

Either rotation is a config-and-restart change to `wwf-backup-offsite` only —
it never touches the local `db_backup.sh` loop, the Postgres containers, or
running application traffic.
