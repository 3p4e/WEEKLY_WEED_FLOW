# WEEKLY_WEED_FLOW — backend API

**FastAPI** (async) + **asyncpg** over **Postgres** (RLS-enforced), with JWT auth,
no-self-signup provisioning, a hash-chained audit trail, and an always-on AI
layer backed by **Letta** stateful agents. It is the real backend behind the
GrowFlow UI in [`../web`](../web); nginx serves the UI and reverse-proxies the
API paths below same-origin.

```
 Browser (GrowFlow UI) ──HTTPS──▶ nginx (wwf-gf-frontend) ──┬─▶ FastAPI API (:8000)
   web/gf/*.js                     same-origin proxy         │      app/ (this dir)
                                                             │         │
                                              static files ──┘         ├─▶ Postgres (RLS, audit trigger)
                                                                       └─▶ Letta agent (AI functions)
```

## Layout

| File | Role |
|------|------|
| `app/main.py`        | App factory, lifespan (pool init), router wiring |
| `app/config.py`      | Pydantic settings (two DSNs, JWT, Letta, CORS) |
| `app/db.py`          | Two asyncpg pools (`app_user` RLS / `app_admin` BYPASSRLS) + `rls()` identity GUCs |
| `app/security.py`    | bcrypt hashing + JWT (HS256) create/decode |
| `app/deps.py`        | `get_current_user`, `require_role`, `require_password_set` |
| `app/api/auth.py`    | Login, change-password, user provisioning (OTP, forced first-login change) |
| `app/api/tasks.py`   | Departments, calendar weeks, task lifecycle (RLS-scoped) |
| `app/api/ai.py`      | AI functions proxied to a bound Letta agent |
| `app/api/audit.py`   | Read-only, tamper-evident audit trail (see below) |
| `schema.sql`         | Full DB schema: roles, tables, RLS policies, audit trigger |

## Security model

- **Two roles, two pools.** Request handlers use `app_user` (NOBYPASSRLS); every
  query runs inside `rls()`, which stamps `app.user_id / app.org_id / app.role`
  as transaction-local GUCs so RLS policies and the audit trigger see the caller.
  Auth lookups and provisioning use `app_admin` (BYPASSRLS).
- **No self-signup.** `ADMIN` / `DEPT_HEAD` provision accounts; the creator is
  shown a one-time password once, and the user must set their own on first login
  (`must_change_password`).
- **Audit trail.** Every write to audited tables fires `app.fn_audit_row`, which
  appends a hash-chained row to `audit_log`
  (`entry_hash = sha256(prev_hash || actor || op || table || record_id || ts ||
  new || old)`). Deleting or reordering a row breaks every later link.

## Audit endpoints (`app/api/audit.py`)

| Method | Path             | Access | Purpose |
|--------|------------------|--------|---------|
| GET    | `/audit`         | elevated¹ | Org-scoped trail, filterable by `table_name` / `record_id` / `action`, keyset-paginated via `before_id` |
| GET    | `/audit/tables`  | elevated¹ | Distinct table names + counts (drives the filter UI) |
| GET    | `/audit/verify`  | `ADMIN`   | Walks the **global** chain and reports the first linkage break, if any |

¹ elevated = `ADMIN`, `DEPT_HEAD`, `PROJECT_LEAD`, `QA_AUDITOR` — mirrors the DB
`audit_read` policy (`app.is_elevated()`). Secret columns (e.g. `password_hash`)
are redacted from the payload server-side.

## Run locally (dev)

The full stack (db + backend + frontend) is defined at the repo root:

```bash
cp .env.example .env           # repo root: set POSTGRES_PASSWORD / *_DATABASE_URL / SECRET_KEY
docker compose up -d --build   # db (loads schema.sql) + backend (:8000) + frontend
curl localhost:8000/health     # if you publish the backend port for local testing
```

> `schema.sql` carries structure + RLS + the audit trigger only; the
> `app_user` / `app_admin` roles and their GRANTs are a one-time bootstrap
> (see [`../docs/DEPLOY.md`](../docs/DEPLOY.md)).

## Production (KVM4)

Built as `weekly_weed_flow-backend:latest` and run as a standalone container on a
shared docker network with the Postgres container and the GrowFlow nginx
frontend; the frontend is published over HTTPS by Traefik (Let's Encrypt). The
Letta stack is pre-existing and reached via `host.docker.internal`.
