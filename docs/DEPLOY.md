# Deploying the WWF stack to KVM4

[`docker-compose.yml`](../docker-compose.yml) describes the deployed stack:

| Service    | Container                     | Image                        | Role |
|------------|-------------------------------|------------------------------|------|
| `db`       | `weekly_weed_flow-db-1`       | `postgres:17-alpine`         | RLS policies + hash-chained audit trigger |
| `backend`  | `weekly_weed_flow-backend-1`  | `weekly_weed_flow-backend`   | FastAPI API (:8000, internal) |
| `frontend` | `wwf-gf-frontend`             | `wwf-growflow`               | nginx + GrowFlow UI, published by Traefik over HTTPS |

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

`schema.sql` (mounted into the db container's init dir) carries **structure +
RLS policies + the audit trigger only**. The two login roles and their table
privileges are a separate, one-time step — without them the API cannot connect:

```sql
-- passwords must match DATABASE_URL / ADMIN_DATABASE_URL in .env
CREATE ROLE app_user  LOGIN PASSWORD '...';                 -- NOBYPASSRLS
CREATE ROLE app_admin LOGIN PASSWORD '...' BYPASSRLS;       -- provisioning + audit verify
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO app_user, app_admin;
GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO app_user, app_admin;
GRANT USAGE ON SCHEMA app TO app_user, app_admin;           -- helper fns (is_elevated, current_org_id)
```

(RLS still constrains `app_user`; `app_admin` bypasses it for auth/provisioning.)

## Schema changes (Alembic)

`schema.sql` was the only source of schema truth up to the point
`backend/alembic/versions/0001_baseline.py` was introduced as a frozen
snapshot of it. Production and every other already-provisioned environment
already has that exact schema, so it's stamped rather than re-applied:

```bash
MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@HOST:5432/weekly_weed_flow \
  alembic stamp 0001
```

Every schema change from here on is a new file in `backend/alembic/versions/`
(see `backend/README.md`'s "Migrations" section), applied with
`alembic upgrade head` using the same `postgres`-superuser-class
`MIGRATION_DATABASE_URL` — DDL privileges the app's own `app_user`/
`app_admin` roles don't have. `schema.sql` stays as the human-readable
"current shape of the DB" reference; regenerate it after a migration lands
(`pg_dump --schema-only`) rather than hand-editing it.

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

nginx serves the UI and reverse-proxies `/auth /departments /weeks /tasks /ai
/audit /health` to the backend same-origin (resolved at request time via Docker
DNS), so the browser only ever talks to one origin.
