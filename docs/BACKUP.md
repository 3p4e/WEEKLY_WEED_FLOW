# Database backups

Prior to this document, WWF had **no backup mechanism at all** — this was the
single largest operational gap flagged by the 2026-07 architecture review.
This document describes what exists now, its scope, and its honest limits.

## Scope

Backs up **only WWF's own Postgres database** (`weekly_weed_flow`, running in
the `db` container / `weekly_weed_flow-db-1` on KVM4). It does **not** cover:

- Letta's own Postgres (a separate, pre-existing stack on the same host,
  outside this repo).
- Qdrant's vector store.
- The Docker volumes for any other service on the box.

## Mechanism

`backend/scripts/db_backup.sh`, run in the `db-backup` container
(`docker-compose.yml`): a loop that dumps the database with `pg_dump`, gzips
it, deletes anything older than `RETENTION_DAYS` (default 14), then sleeps 24
hours and repeats. Files land in the `weekly_weed_flow_backups` named Docker
volume as `weekly_weed_flow_<UTC timestamp>.sql.gz`.

The loop is a plain `sleep 86400`, not a fixed time-of-day cron — it drifts
slowly against wall-clock across restarts. That's an accepted trade-off: it's
simpler than adding a cron daemon to the image, and a same-day rotating
backup doesn't need to fire at a precise minute.

Run a backup on demand (e.g. before a risky migration) with:

```bash
docker exec wwf-db-backup sh /usr/local/bin/db_backup.sh --once
```

## Retention and the residual risk — read this before relying on it

**14 rotating daily dumps, on the same host's local disk, with no offsite
copy.** This is a deliberate, documented scope limit, not an oversight: no
offsite storage target (S3 bucket, remote host, etc.) is provisioned for this
single-VPS deployment. In plain terms — **if the KVM4 host is lost, destroyed,
or its disk fails, these backups are lost with it.** This covers accidental
data loss, a bad migration, or an operator mistake; it does not cover host-
level disaster recovery. Provisioning an offsite copy (e.g. a nightly `scp`/
`rclone` of the volume to another host or object storage) is the natural next
step if that risk needs closing.

## Restore procedure (tested — see below)

1. Stop the app so nothing writes during the restore:
   ```bash
   docker stop weekly_weed_flow-backend-1 wwf-scheduler
   ```
2. Pick a dump from the volume and restore it into a **fresh** database
   (never restore over the live one in place — create a new DB, verify it,
   then swap):
   ```bash
   docker exec wwf-db-backup ls /backups
   docker exec weekly_weed_flow-db-1 psql -U postgres -c "CREATE DATABASE weekly_weed_flow_restored;"
   docker exec wwf-db-backup gunzip -c /backups/weekly_weed_flow_<TIMESTAMP>.sql.gz | \
     docker exec -i weekly_weed_flow-db-1 psql -U postgres -d weekly_weed_flow_restored -v ON_ERROR_STOP=1
   ```
3. Spot-check row counts against what you expect before cutting over:
   ```bash
   docker exec weekly_weed_flow-db-1 psql -U postgres -d weekly_weed_flow_restored -tAc \
     "SELECT 'organizations',count(*) FROM organizations UNION ALL SELECT 'profiles',count(*) FROM profiles UNION ALL SELECT 'tasks',count(*) FROM tasks UNION ALL SELECT 'ai_pins',count(*) FROM ai_pins"
   ```
4. Only once satisfied, rename databases (or repoint `DATABASE_URL`/
   `ADMIN_DATABASE_URL`) to cut the app over, then restart the two containers
   stopped in step 1.

**This was actually run, not just written down.** As part of shipping this
feature: a real dump of the local test database was taken with
`db_backup.sh --once`, restored into a fresh scratch database
(`wwf_restore_test`) with `gunzip -c <dump> | psql -d wwf_restore_test`, and
every table's row count was confirmed to match the source exactly
(`organizations`: 4/4, `profiles`: 9/9, `tasks`: 3/3, `ai_pins`: 0/0) before
the scratch database was dropped. The restore completed with no errors.

See also `docs/DEPLOY.md` for how the rest of the stack is provisioned on
KVM4.
