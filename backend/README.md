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
| `app/config.py`      | Pydantic settings (four DSNs — two databases x two roles, JWT, Letta, CORS) |
| `app/db.py`          | Four asyncpg pools over two databases + `rls()` / `rls_users()` identity GUCs |
| `app/roster.py`      | App-side name joins across the users-tasks database boundary |
| `app/worktime.py`    | Work-session regular/overtime/night/weekend classification |
| `app/security.py`    | bcrypt hashing + JWT (HS256) create/decode |
| `app/deps.py`        | `get_current_user`, `require_role`, `require_password_set` |
| `app/api/auth.py`    | Login, change-password, user provisioning (OTP, forced first-login change) |
| `app/api/tasks.py`   | Departments, calendar weeks, task lifecycle (RLS-scoped) |
| `app/api/ai.py`      | AI functions proxied to a bound Letta agent |
| `app/api/audit.py`   | Read-only, tamper-evident audit trail (see below) |
| `app/api/reports.py` | Weekly report/plan: per-person time-class hours, overdue, time band |
| `schema.users.sql` / `schema.tasks.sql` | Generated per-database schema dumps (tables, RLS, audit trigger) |

## Security model

- **Two databases.** Identity (organizations, profiles, reset codes) lives in
  `wwf_users`; all work data in `wwf_tasks` — separate Postgres containers, no
  cross-database FKs (bare uuids across the boundary; `app/roster.py` merges
  names app-side). Each database keeps its own hash-chained audit trail.
- **Two roles per database, four pools.** Request handlers use `app_user`
  (NOBYPASSRLS); every query runs inside `rls()` (tasks DB) or `rls_users()`
  (users DB), which stamps `app.user_id / app.org_id / app.role` as
  transaction-local GUCs so RLS policies and the audit trigger see the caller.
  Auth lookups and provisioning use `app_admin` (BYPASSRLS).
- **No self-signup.** Accounts are provisioned by an `ADMIN` (any non-admin
  role, any department) or by a department manager (only `USER` staff, only in
  their own department — see `app/roles.py`); the creator is shown a one-time
  password once, and the user must set their own on first login
  (`must_change_password`).
- **Audit trail.** Every write to audited tables fires `app.fn_audit_row`, which
  appends a hash-chained row to `audit_log`
  (`entry_hash = sha256(prev_hash || actor || op || table || record_id || ts ||
  new || old)`). Deleting or reordering a row breaks every later link.
  Two hardenings are worth knowing before touching this function:
  **H1** (tasks-0012 / users-0006) takes a transaction-scoped advisory lock before
  the chain-tail read, without which concurrent writers fork the chain;
  **H2** (tasks-0050 / users-0009) pins the function's own `TimeZone` to `UTC`,
  because `ts` is `now()::text` and a `timestamptz` renders under the *session's*
  zone — so before H2 a row's hash depended on the timezone of whoever wrote it and
  could not be recomputed elsewhere. Both were found the hard way in production;
  see the audit-chain finding in [`../docs/DEPLOY.md`](../docs/DEPLOY.md).

## Audit endpoints (`app/api/audit.py`)

| Method | Path             | Access | Purpose |
|--------|------------------|--------|---------|
| GET    | `/audit`         | elevated¹ | Merged two-chain trail (`source: users/tasks`), filterable by `table_name` / `record_id` / `action` / `source`, keyset-paginated via `before` (created_at) |
| GET    | `/audit/tables`  | elevated¹ | Distinct table names + counts (drives the filter UI) |
| GET    | `/audit/verify`  | `ADMIN`   | Walks BOTH global chains: recomputes every row's hash from its stored content, checks pointer linkage, and anchors the head. `ok` is false only for a genuine failure — `hash_breaks`, `link_orphans` or `head_breaks`. `hash_legacy_tz` (intact, written pre-H2 under a non-UTC session) and `link_forks` (pre-H1 concurrency, with `fork_id_range`) are reported alongside as explained history, not as breaks |

¹ elevated = every role except `USER` (`ADMIN`, the `OWNER`/`CEO`/`COO` executives,
the department managers `QA_MGR`/`QC_MGR`/`PR_MGR`/`WH_MGR`/`SE_MGR`/`CU_MGR`/`MU_MGR`,
and `QP`) — mirrors the DB `audit_read` policy (`app.is_elevated()`), defined once in
`app/roles.py`. Secret columns (e.g. `password_hash`) are redacted from the
payload server-side.

## Run locally (dev)

The full stack (db + backend + frontend) is defined at the repo root:

```bash
cp .env.example .env           # repo root: set POSTGRES_PASSWORD / *_DATABASE_URL / SECRET_KEY
docker compose up -d --build   # db-users + db-tasks (load their schema files) + backend (:8000) + frontend
curl localhost:8000/health     # if you publish the backend port for local testing
```

> The schema files carry structure + RLS + the audit trigger only; the
> `app_user` / `app_admin` roles and their GRANTs are a one-time bootstrap
> **in each database** (see [`../docs/DEPLOY.md`](../docs/DEPLOY.md)).

## Tests

`tests/` runs against a real Postgres database — RLS is the app's actual
security model, so it can't be meaningfully exercised against a mock. Each
test gets its own fresh organization (`org` fixture in `tests/conftest.py`);
teardown deletes it from the users DB (cascade) and explicitly purges its
rows from the tasks DB (`purge_org()`), so tests never share or leak state
even though they run against shared databases.

```bash
# one-time: the two local test databases + the app_user/app_admin roles
# (same roles as docs/DEPLOY.md's production bootstrap, test-only passwords)
sudo -u postgres psql -c "CREATE ROLE app_user  LOGIN PASSWORD 'testpw_user';"
sudo -u postgres psql -c "CREATE ROLE app_admin LOGIN PASSWORD 'testpw_admin' BYPASSRLS;"
for w in users tasks; do
  sudo -u postgres psql -c "CREATE DATABASE wwf_${w}_test OWNER postgres;"
  sudo -u postgres backend/scripts/load_schema.sh $w wwf_${w}_test
  sudo -u postgres psql -d wwf_${w}_test -c "
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO app_user, app_admin;
    GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO app_user, app_admin;
    GRANT USAGE ON SCHEMA app TO app_user, app_admin;
    ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user, app_admin;
    ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user, app_admin;"
done

python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

ENVIRONMENT=development \
SECRET_KEY=local-test-secret-not-for-production \
USERS_DATABASE_URL=postgresql://app_user:testpw_user@localhost:5432/wwf_users_test \
USERS_ADMIN_DATABASE_URL=postgresql://app_admin:testpw_admin@localhost:5432/wwf_users_test \
TASKS_DATABASE_URL=postgresql://app_user:testpw_user@localhost:5432/wwf_tasks_test \
TASKS_ADMIN_DATABASE_URL=postgresql://app_admin:testpw_admin@localhost:5432/wwf_tasks_test \
  python -m pytest -v
```

CI runs the same steps against a `postgres:16` service container on every PR
(fresh for every run). `tests/test_audit.py`'s last tests deliberately
tamper with / delete rows in BOTH `audit_log` chains to prove
`/audit/verify` catches (and doesn't catch) specific things — safe for CI
since it always starts from empty databases, but running the suite twice
locally against the *same* test databases will fail the chain-intact
assertions on the second run. Recreate both test databases between local
runs if you've run the full suite (drop both `wwf_*_test` DBs +
redo the schema-load step above), or just run everything except
`test_audit.py` while iterating on something else
(`.github/workflows/ci.yml`).

## Migrations (Alembic — two chains)

The schema files are raw `pg_dump`s **generated from the alembic-built
databases** — human-readable references, never hand-edited. Schema changes
go through the per-database chains `alembic_users/versions/` and
`alembic_tasks/versions/`, hand-written (no ORM models in this app, so no
`--autogenerate`), selected via `-n users|tasks` against the shared
`alembic.ini`.

Each chain's `0001_*_baseline.py` builds that database's full v2 schema. An
environment initialized from a schema file is pointed at it with
`alembic -n users|tasks stamp 0001` (records the version without re-running
DDL); a genuinely empty database (CI) runs `alembic -n ... upgrade head`.

Migrations need DDL privileges the app's own `app_user`/`app_admin` roles
intentionally don't have (see "One-time DB bootstrap" in
[`../docs/DEPLOY.md`](../docs/DEPLOY.md)) — each env.py connects with its
own `USERS_MIGRATION_DATABASE_URL` / `TASKS_MIGRATION_DATABASE_URL` (a
`postgres`-superuser-or-equivalent DSN), kept separate from
`app.config.Settings` on purpose (that module's own startup checks — e.g.
refusing to run with a placeholder `SECRET_KEY` in production — have
nothing to do with running a migration).

```bash
USERS_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@HOST:5432/wwf_users \
  alembic -n users upgrade head    # apply pending users-DB migrations
TASKS_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@HOST:5432/wwf_tasks \
  alembic -n tasks upgrade head    # apply pending tasks-DB migrations
  alembic -n tasks current         # what's applied now
  alembic -n tasks downgrade -1    # revert the most recent migration
```

Every new migration needs a working `downgrade()` — the baselines don't
`DROP SCHEMA public CASCADE` despite `upgrade()` being "create everything";
that would also drop Alembic's own `alembic_version` tracking table (it
lives in `public` too), breaking Alembic's bookkeeping in the same
transaction. They drop exactly the tables `upgrade()` created instead.

## Production (KVM4)

Built as `weekly_weed_flow-backend:latest` and run as a standalone container on a
shared docker network with the two Postgres containers and the GrowFlow nginx
frontend; the frontend is published over HTTPS by Traefik (Let's Encrypt). The
Letta stack is pre-existing and reached via `host.docker.internal`.
