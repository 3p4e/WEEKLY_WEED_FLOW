# Deploying the WWF stack to KVM4

## Deploy order (binding, since 2026-07-13)

`https://wwf-mass.srv1231216.hstgr.cloud/` is the **test server** — every
change ships and gets verified there first (see "Parallel test instance —
wwf_mass" below for what it is and isn't).
`https://wwf.srv1231216.hstgr.cloud/` is **production** — real Purely Plant
user accounts and real work data. It is promoted to **only after**
verification on wwf_mass, never deployed to first.

[`docker-compose.yml`](../docker-compose.yml) describes the deployed stack:

| Service     | Container                     | Image                        | Role |
|-------------|--------------------------------|------------------------------|------|
| `db-users`  | `wwf-db-users`                | `postgres:17-alpine`         | Identity data (organizations, profiles) + its own audit chain |
| `db-tasks`  | `wwf-db-tasks`                | `postgres:17-alpine`         | Work data (tasks, work_sessions, pins, ...) + its own audit chain |
| `backend`   | `weekly_weed_flow-backend-1`  | `weekly_weed_flow-backend`   | FastAPI API (:8000, internal) |
| `scheduler` | `wwf-scheduler`               | `weekly_weed_flow-backend`   | Thursday 14:00 weekly snapshot job |
| `frontend`  | `wwf-gf-frontend`             | `wwf-growflow`               | nginx + GrowFlow UI, published by Traefik over HTTPS |
| `db-backup` | `wwf-db-backup`               | `postgres:17-alpine`         | Rotating local `pg_dump` backups of BOTH DBs — see [`docs/BACKUP.md`](BACKUP.md) |

The two databases are a deliberate v2 architecture decision: identity and
work data live in **separate Postgres containers** with no cross-database
foreign keys (bare uuids across the boundary; app-side joins via
`backend/app/roster.py`). Each database has its own independent
hash-chained `audit_log`; `/audit/verify` reports both chains.

The **Letta** stateful-agent layer (AI functions) runs in its own pre-existing
stack and is reached over `host.docker.internal` — it is not managed here.

## Live infrastructure (inventory)

| Resource | Detail |
|---|---|
| VPS | Hostinger **KVM 4**, `crimson.blaze`, **72.60.35.12** (`srv1231216.hstgr.cloud`) |
| Host OS | Ubuntu 24.04, template **"Docker + Traefik"** (Traefik provides routing + Let's Encrypt) |
| Resources | 4 vCPU · 16 GB RAM · 200 GB disk |
| Public URL | `https://wwf.srv1231216.hstgr.cloud` (Traefik `websecure` + `letsencrypt`) |
| AI | **Letta** on KVM4; WWF AI functions are bound to the `wwf_weekly_coordinator` agent |

## One-time DB bootstrap (roles + grants)

`schema.users.sql` / `schema.tasks.sql` (each mounted into its container's
init dir) carry **structure + RLS policies + the audit trigger only**. The
two login roles and their table privileges are a separate, one-time step
**in EACH database** — without them the API cannot connect:

```sql
-- run in BOTH wwf_users and wwf_tasks;
-- passwords must match the four *_DATABASE_URL values in .env
CREATE ROLE app_user  LOGIN PASSWORD '...';                 -- NOBYPASSRLS
CREATE ROLE app_admin LOGIN PASSWORD '...' BYPASSRLS;       -- provisioning + audit verify
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO app_user, app_admin;
GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO app_user, app_admin;
GRANT USAGE ON SCHEMA app TO app_user, app_admin;           -- helper fns (is_elevated, current_org_id)

-- ...and make it self-maintaining: every table a FUTURE migration creates
-- (migrations connect as `postgres`) auto-grants to the app roles. Without
-- this, each new CREATE TABLE migration is born permission-less and every
-- request against it 500s with "permission denied for table ..." until a
-- manual GRANT — the class of bug that hit weekly_documents.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user, app_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_user, app_admin;
```

(RLS still constrains `app_user`; `app_admin` bypasses it for auth/provisioning.
Default privileges are keyed to the role that CREATEs the object — `postgres`,
which is what both migration DSNs connect as.)

## Schema changes (Alembic — two chains)

Each database has its own migration chain: `backend/alembic_users/` and
`backend/alembic_tasks/`, selected with `-n users|tasks` against the shared
`backend/alembic.ini`. Each env.py reads its own superuser-class URL
(`USERS_MIGRATION_DATABASE_URL` / `TASKS_MIGRATION_DATABASE_URL`) — DDL
privileges the app's own `app_user`/`app_admin` roles don't have.

A database freshly initialized from its schema file is stamped, not
re-upgraded:

```bash
USERS_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:PW@wwf-db-users:5432/wwf_users \
  alembic -c backend/alembic.ini -n users stamp 0001
TASKS_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:PW@wwf-db-tasks:5432/wwf_tasks \
  alembic -c backend/alembic.ini -n tasks stamp 0001
```

Every schema change from here on is a new file in the relevant chain's
`versions/`, applied with `alembic -n users|tasks upgrade head`.
`schema.users.sql` / `schema.tasks.sql` are **generated** from the
alembic-built databases (`pg_dump --schema-only --no-owner --no-privileges
--exclude-table=alembic_version`), never hand-edited — CI byte-diffs the two
builds per database.

## v2 blank-state cutover (performed 2026-07)

The v2 rebuild replaced the single `weekly_weed_flow` database with the two
containers above, starting from a **blank state** (admin + qcm.blani only).
Runbook, for the record and for any future rebuild:

1. Final safety dump of the old DB: `docker exec wwf-db-backup sh /usr/local/bin/db_backup.sh --once`.
2. Stop backend/scheduler/db-backup; leave the old `weekly_weed_flow-db-1`
   container + volume in place (it is the archive) but disconnect it.
3. Start `wwf-db-users` / `wwf-db-tasks` (fresh volumes; initdb runs the
   schema files mounted at `/docker-entrypoint-initdb.d/10-schema.sql`).
4. Bootstrap roles + grants in both (SQL above), `alembic stamp 0001` twice.
5. Hand-insert: the organization row (users DB), the 7 departments rows
   (tasks DB, same org uuid), and the `admin` + `qcm.blani` profiles
   (users DB; qcm.blani gets a fresh OTP with must_change_password=true).
6. Rebuild the backend image, recreate backend/scheduler/frontend/db-backup
   with the new env (four DSNs — see `.env.example`).
7. Verify: both logins, create a task, log a weekend work session, confirm
   the report shows it in the per-person overtime buckets, `/audit/verify`
   reports both chains ok.

## Deploying

Production was provisioned **out-of-band** (containers created directly, behind
Traefik), so the SSH workflow is **manual-dispatch only** and does not run on
push to `main`.

### Option A — from this Claude environment (kvm4-runner)

The Claude sandbox only allows **outbound HTTPS through its proxy** (port 22 is
blocked), so a `kvm4-runner` HTTPS service on the host runs `docker`/`shell`
commands. Build context lives at `/opt/weekly_weed_flow/backend`, `/root/wwf-gf/web`;
the standard flow is: write the updated files, `docker build`, then recreate the
container (`--no-healthcheck`, Traefik labels + networks preserved).

### Option B — GitHub Actions ([`deploy.yml`](../.github/workflows/deploy.yml))

Manual dispatch only. Add secrets `KVM4_HOST`, `KVM4_USER`, `KVM4_SSH_KEY` (a
**private** deploy key), create `/opt/wwf/.env` from
[`.env.example`](../.env.example) once, then run the workflow: it rsyncs the repo
to `/opt/wwf` (preserving `.env`) and runs `docker compose up -d --build`. Note
this **converges the live containers onto compose** — dispatch it deliberately.

## Capture connector (wwf-capture-mcp)

`connector/` is a one-tool remote MCP server (`submit_capture`) that
claude.ai / Cowork chats call to deliver Master-Capture-Prompt output
straight into `POST /capture/import`. Its security model — explicitly
user-approved — is: reachable only at a secret random path
(`CAPTURE_MCP_PATH`, e.g. `/mcp-<16 hex>`) behind Traefik TLS on the wwf
host; it holds `CAPTURE_IMPORT_TOKEN`, a static credential the backend
accepts ONLY on `/capture/import`, acting as `CAPTURE_IMPORT_USER`
(qcm.blani); a small in-process rate limit caps abuse. Worst case if the
URL leaks: junk task rows (auditable, deletable) — no reads, no other
routes. Rotate by changing the token + path and recreating the container.

Enable it in a Claude client: claude.ai → Settings → Connectors → Add
custom connector → URL `https://<APP_HOST><CAPTURE_MCP_PATH>/mcp` (no
auth) → then any chat running the capture prompt v2.1 delivers
automatically. The Import view in WWF is the manual fallback.

## Routing (Traefik)

The frontend carries the Traefik labels (host-mode Traefik):

```
traefik.enable=true
traefik.http.routers.wwf.rule=Host(`wwf.srv1231216.hstgr.cloud`)
traefik.http.routers.wwf.entrypoints=websecure
traefik.http.routers.wwf.tls.certresolver=letsencrypt
traefik.http.services.wwf.loadbalancer.server.port=80
```

> Traefik in host-network mode will not route a container marked **unhealthy** —
> so the images intentionally ship **without a HEALTHCHECK** and containers run
> with `--no-healthcheck`.

nginx serves the UI and reverse-proxies `/auth /departments /weeks /tasks
/sessions /ai /audit /reports /health` to the backend same-origin (resolved at request time
via Docker DNS), so the browser only ever talks to one origin.

## Parallel test instance — wwf_mass (added 2026-07-13)

An isolated clone of the full app runs alongside production for validation
and experiments:

- **URL:** https://wwf-mass.srv1231216.hstgr.cloud · **Stack:** `/opt/stacks/wwf_mass`
- **Containers:** `wwf-mass-{db-users,db-tasks,backend,frontend}` on their own
  network `wwf_mass_internal` (172.16.37.0/24) with their own volumes
  (`wwf_mass_*_pgdata`, cloned from production 2026-07-13 via `pg_dumpall`).
- Runs the same images as production (`weekly_weed_flow-backend:v29`,
  `wwf-growflow:v45`). The backend carries the network-alias
  `weekly_weed_flow-backend-1` *inside its own network only* — the stock
  frontend nginx upstream resolves locally and can never cross to production.
- Fresh `SECRET_KEY` (tokens not interchangeable with production);
  **Letta AI disabled** (`LETTA_*` pointed at an unroutable address) so the
  test instance cannot drive the production AI agents; the operational
  singletons (scheduler, capture-mcp, backups) are deliberately not run —
  **the mass instance has no backups by design**.
- Accounts/passwords equal production at clone time (incl. the `tt.*` cast).
- Full teardown procedure: see `/opt/stacks/wwf_mass/README.md` on the host.
