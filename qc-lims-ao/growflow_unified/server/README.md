# GrowFlow Unified — Backend (P3)

The converged API: **T_PLAN's `planner_api`** (FastAPI, async SQLAlchemy/psycopg3,
JWT+RBAC, gateway→Letta) extended with the adaptive tree, the governed
change-control loop, the stateful-agent layer, and the **SUMA/WWF auth
methodology** (OTP provisioning, forced first-login change, lockout, two-role RLS).

## Layout

```
server/planner_api/
  config.py        Settings (PLANNER_* env): db urls, jwt, gateway, letta, RLS, lockout
  db.py            admin engine + RLS app engine + identity stamping
  auth_deps.py     JWT/RBAC + require_password_set guard + rls_session dependency
  audit.py         append-only hash-chained audit_event (ALCOA+)
  gateway_client.py  planner-* agents via the Letta gateway
  routers/
    auth.py        login (lockout), change-password (forced), provision (OTP), me
    tasks.py       departments, users, tasks, /planner/tree (adaptive), telemetry
    governance.py  change_proposal list + approve/reject, field_registry
    ai.py          /ai/functions + /ai/{function_key} (bound agents, graceful)
    reports.py     weekly reports + AI drafts (gateway)
    exec.py        executive analytics
    health.py      liveness
```

## Auth & RLS (grafted methodology)

- **No self-signup.** `POST /auth/provision` (admin/hod/manager) creates an account
  with a one-time temp password (returned once) and `must_change_password=true`.
- **Forced first-login change.** `require_password_set` returns `403
  password_change_required` until `POST /auth/change-password` is called.
- **Lockout.** `max_login_attempts` failures → `423 Locked` for `lockout_minutes`.
- **Two-role RLS.** When `PLANNER_APP_DATABASE_URL` is set, data routers use the
  NOBYPASSRLS `growflow_app` role via `rls_session`, which stamps `app.user_id` /
  `app.role` so the policies in `db/0006_auth_rls.sql` apply. Login, provisioning
  and migrations use the admin/owner role (`PLANNER_DATABASE_URL`). Unset →
  single-engine fallback (RLS still defined; app connects as owner).
- **Audit.** Login, change-password, provisioning, and proposal decisions append a
  hash-chained `audit_event`.

## Adaptive tree

`GET /planner/tree?root_id=&department_id=&week_start=` returns a forest of
`PlannerTreeNode` with nested `children` (task → annex → Draft/Review/Approve).
Tasks carry `node_kind`, `is_sop`, `annex_count`, and the extensible `attributes`
(JSONB). Create/update accept `parent_id`, `node_kind`, `is_sop`, `attributes`.

## Governance (change-control loop)

- `GET /governance/proposals?status=` — the agent-proposed schema changes.
- `POST /governance/proposals/{id}/decision` `{decision: approved|rejected}` —
  approver-only (reviewer/qp/manager/hod/admin), enforced in code **and** by RLS.
- `GET /governance/field-registry` — recognized variable params.

Approval is the gate; the migration is applied as a controlled, audited DB op.

## Configuration (PLANNER_* env)

| Var | Purpose |
|---|---|
| `PLANNER_DATABASE_URL` | admin/owner async URL (login, provisioning, migrations) |
| `PLANNER_APP_DATABASE_URL` | NOBYPASSRLS app URL (RLS-enforced data path) |
| `PLANNER_JWT_SECRET` | JWT signing key (override outside dev) |
| `PLANNER_GATEWAY_URL` / `_TOKEN` | Letta gateway for planner-* agents |
| `PLANNER_LETTA_BASE_URL` / `_API_KEY` | direct Letta for governance/compliance agents |
| `PLANNER_MAX_LOGIN_ATTEMPTS` / `_LOCKOUT_MINUTES` / `_OTP_TTL_HOURS` | auth hardening |
| `PLANNER_CORS_ORIGINS` | allowed web origins |

## Migrations & run

The image applies `db/*.sql` in order (`0000 → 0002 → 0004 → 0003 → 0005 → 0006`)
via `docker-entrypoint.sh`, sets the `growflow_app` password from
`GROWFLOW_APP_PASSWORD`, then serves on `:8765`.

## Validation

Integration smoke (`smoke_gf.py`, in-process ASGI against a live Postgres as the
`growflow_app` RLS role) — **17/17 checks pass**: health, login, adaptive tree
(586 nodes incl. depth-3 steps), governance (1 pending proposal), AI graceful
degradation, OTP provisioning, forced-change guard + clearance, and lockout.
