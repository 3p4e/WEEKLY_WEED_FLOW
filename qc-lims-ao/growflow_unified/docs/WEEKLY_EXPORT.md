# Weekly task snapshot (Fri→Thu) — scheduled export + Letta wiring

A scheduled job captures each work week's task **creations, progress notes,
descriptions and outcomes**, writes a **JSON file** and a **Markdown digest**,
upserts the snapshot into the app's own PostgreSQL (`planner_weekly_snapshot`),
and **pushes the digest to a Letta source** so the dedicated agents can reason
over it. It targets `PLANNER_DATABASE_URL` (the GrowFlow database), **never** the
SUMA Supabase project.

- Job: `server/planner_api/jobs/weekly_export.py` (digest: `weekly_digest.py`)
- Table: `planner_weekly_snapshot` (migration `db/0009_weekly_snapshot.sql`)
- Work week: **Friday → Thursday**. Runs after the week closes (Thursday 18:00 UTC)
  to snapshot the week that just finished.

## Letta wiring
The Markdown digest (totals, by-status/priority/department/owner rollups,
assignment acknowledgment, blocked/declined/outcome items) is uploaded to the
Letta source **`GrowFlow_Weekly_Snapshots`**, attached to the
`weekly_summary` (coordinator) and `executive_analytics` agents. Controlled by
(all must be set, else the push is skipped):

| env (PLANNER_*) | meaning |
|---|---|
| `PLANNER_LETTA_BASE_URL` | Letta server, e.g. `http://letta:8283` |
| `PLANNER_LETTA_API_KEY` | Letta server password (bearer) |
| `PLANNER_LETTA_SNAPSHOT_SOURCE_ID` | `source-…` id of the snapshot source |
| `PLANNER_ENABLE_WEEKLY_SCHEDULER` | `1` to run the in-process Thursday scheduler |

The push is idempotent (it replaces the prior same-named digest in the source).

## Run manually (inside the API container)
```bash
# current Fri→Thu week
docker compose -p growflow_unified exec -T planner-api python -m planner_api.jobs.weekly_export
# the previous week / an explicit window / JSON file only
docker compose -p growflow_unified exec -T planner-api python -m planner_api.jobs.weekly_export --offset -1
docker compose -p growflow_unified exec -T planner-api python -m planner_api.jobs.weekly_export --from 2026-06-26 --to 2026-07-02
docker compose -p growflow_unified exec -T planner-api python -m planner_api.jobs.weekly_export --no-db   # file only
```
JSON files are written to `GROWFLOW_EXPORT_DIR` (default `/app/exports/` inside the
container). Mount a named volume on the `planner-api` service to persist them (the DB
snapshot in `planner_weekly_snapshot` already persists in `pgdata` regardless):
```yaml
  planner-api:
    volumes:
      - gf_exports:/app/exports
# …and add  gf_exports:  to the top-level volumes: block
```

## Scheduling
The export runs **in-process** inside `planner-api` (FastAPI lifespan task) every
Thursday at 18:00 UTC when `PLANNER_ENABLE_WEEKLY_SCHEDULER=1`. No host cron or
systemd timer is required (the KVM4 host exposes only the Docker socket to the
runner). On restart the loop recomputes the next Thursday, so a missed window is
simply picked up the following week — trigger a catch-up manually if needed.

Alternative (host cron, if ever available):
```cron
0 18 * * 4  cd /opt/growflow_unified && /usr/bin/docker compose -p growflow_unified exec -T planner-api python -m planner_api.jobs.weekly_export >> /opt/gf_weekly_export.log 2>&1
```

## Read snapshots back
```sql
SELECT week_from, week_to, task_count, created_count, completed_count, note_count, generated_at
FROM planner_weekly_snapshot ORDER BY week_from DESC;

SELECT payload FROM planner_weekly_snapshot WHERE week_to = '2026-07-02';
```
