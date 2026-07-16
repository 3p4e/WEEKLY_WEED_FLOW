# GrowFlow Unified

A standalone, EU-GMP / ISO 17025 / 21 CFR Part 11–aligned **task-management QMS**,
converged from the two prior iterations in this workspace:

- **T_PLAN** — the furthest-along standalone planner (recursive task tree,
  gateway→Letta agents, weekly board). **Adopted as the base.**
- **Weekly Weed Flow** — contributed its **auth methodology** (SUMA-style
  bcrypt+JWT, OTP provisioning, forced first-login change, two-role Postgres RLS,
  hash-chained audit).

Seeded with the **real 195-task Quality Control corpus**, imported under the
**Head of QC** (Blagoj Nikolov) account.

## Layout

| Dir | What |
|---|---|
| `db/` | **P1** adaptive data layer — recursive tree + extensible attributes + governed change-control + the QC import (586 nodes). `0000→0002→0004→0003→0005→0006`. |
| `agents/` | **P2** stateful-agent roster + the governed change-control contract. |
| `server/` | **P3** converged FastAPI backend — adaptive tree API, governance, AI invocation, RLS-hardened auth. |
| `web/` | **P4** converged React/Vite SPA — GrowFlow Unified shell, Task Tree, Governance, AI Assistant, Settings, bilingual EN/МК. |
| `docker-compose.yml` | **P5** the 4-service stack (db · planner-api · web · Letta wiring) behind Traefik. |

## The five pillars

1. **Adaptive depth** — the task tree is 1..N deep *by the nature of each node*,
   never forced uniform: a plain task is a leaf; an SOP's annex is a controlled
   document that carries the Draft→Review→Approve GMP lifecycle.
2. **Extensible columns** — a stable core + a JSONB `attributes` tail cataloged in
   `field_registry`; nothing is frozen.
3. **Governed evolution** — agents *propose* schema/workflow changes into
   `change_proposal`; a human *approves*; only then is a migration applied. Agents
   never mutate the schema.
4. **Stateful AI** — a bound roster of Letta agents (task-intelligence, governance,
   GMP-compliance), always-on with graceful degradation.
5. **Regulated auth** — no self-signup, OTP provisioning, forced first-login change,
   lockout, two-role RLS, ALCOA+ hash-chained audit.

## Deploy

```sh
# on the host, with db/server/web/docker-compose.yml present:
cat > .env <<EOF
POSTGRES_PASSWORD=...        # generated
GROWFLOW_APP_PASSWORD=...    # generated (sets the NOBYPASSRLS role)
PLANNER_JWT_SECRET=...       # generated
APP_HOST=wwf.srv1231216.hstgr.cloud
LETTA_BASE_URL=http://letta:8283
EOF
docker compose -p growflow_unified up --build -d
```

The web (nginx) is the only Traefik-exposed service; it reverse-proxies the API
path-prefixes (`/auth`, `/planner`, `/governance`, `/ai`, `/health`) same-origin
to `planner-api:8765`. The API entrypoint applies the SQL migrations in order and
sets the `growflow_app` role password.

### Live

Deployed at **https://wwf.srv1231216.hstgr.cloud** (Traefik + Let's Encrypt).
Verified end-to-end through the public endpoint: SPA, health, login, the 586-node
adaptive tree, and the governance queue all respond 200.

Seed login: `blagoj / ChangeMe!23` (Head of QC) — change on first use.
