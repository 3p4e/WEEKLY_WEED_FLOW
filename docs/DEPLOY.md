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

## QMS Studio federation (unification Phase 1)

New internal service `qms-api` — the QMS Creator backend built from this
repo's `qms-creator/` (image `wwf-qms-api:vN`). It is **never published**:
its only client is the platform backend's authed proxy (`backend/app/api/
qms.py`), which injects the service's `X-API-Key` server-side.

Compose service (added to the stack's compose.yaml):

```yaml
  qms-api:
    image: wwf-qms-api:v1
    environment:
      API_KEY: ${QMS_API_KEY}
      LETTA_BASE_URL: http://host.docker.internal:8283
      LETTA_API_KEY: ${LETTA_API_KEY}
    extra_hosts:
      - host.docker.internal:host-gateway
    volumes:
      - qms_data:/app/data
      - qms_output:/app/output
    networks: [internal]
```

Backend env (app.env): `QMS_API_URL=http://qms-api:8000` and
`QMS_API_KEY=<same secret as the service's API_KEY>`. An EMPTY
`QMS_API_KEY` disables the federation cleanly — the proxy answers
503 "QMS service unavailable" and the QMS Studio views show a labeled
unavailable state.

### Status & prod promotion (owner-gated)

Deployed to **wwf_mass (test) only**. Production (`wwf_app`) is promoted
ONLY after the owner's additional tests and explicit approval. The
promotion is exactly:

1. `wwf_app/compose.yaml`: add the `qms-api` service block above (+ the two
   named volumes at the bottom `qms_data: {}`, `qms_output: {}`).
2. `wwf_app/app.env`: add `QMS_API_URL` + `QMS_API_KEY` (generate a fresh
   secret; also export it for compose interpolation or inline it).
3. `docker compose up -d qms-api && docker compose up -d --no-deps backend
   frontend` with the same backend/frontend image tags already verified on
   wwf_mass.
4. Verify: /qms 401 unauthenticated, registry + knowledge views load for an
   elevated account, USER gets no QMS Studio group.

Note: the `qms-api` container in the `/opt/stacks/letta` project is an
unrelated April prototype (18KB main.py) — not this service, not touched by
this deployment; cleanup candidate at unification Phase 4.

## GrowFlow DocEngine (dedicated document AI service)

New internal service `docengine` (`docengine/`, image `growflow-docengine:vN`)
— a dedicated FastAPI service powered by Letta with an additive `gf_*` agent
fleet. It adopts the pp-document-suite formatting engine COMPLETELY (canon:
`docs/DOCENGINE-CANON-2026-07.md`) and merges the questionnaire-driven
SOP/Annex authoring workflow with per-section regulatory checks. Every
produced document is gated on `pp_verify`'s `RESULT: PASS` — a failing build
is deleted server-side and never reaches the API. **Never published**; its
only client is the platform backend's `/qms/studio/*` proxy routes (same
X-API-Key server-side injection pattern as `qms-api`).

Compose service (added to the stack's compose.yaml):

```yaml
  docengine:
    image: growflow-docengine:v1
    environment:
      DOCENGINE_API_KEY: ${DOCENGINE_API_KEY}
      DOCENGINE_DATABASE_URL: postgresql://...@wwf-tasks-db:5432/wwf_tasks  # docengine schema
      LETTA_BASE_URL: http://host.docker.internal:8283
      LETTA_API_KEY: ${LETTA_API_KEY}
      GOTENBERG_URL: http://gotenberg:3000
      # A stateful-agent generation can take minutes; the read timeout covers
      # ONE agent turn (the pipeline makes ~11 sequential calls per SOP as a
      # polled background job). Connect stays short so a down server fails fast.
      LETTA_READ_TIMEOUT: "300"     # optional; default 300s
      LETTA_CONNECT_TIMEOUT: "15"   # optional; default 15s
    extra_hosts:
      - host.docker.internal:host-gateway
    volumes:
      - docengine_out:/data/docengine-out
    networks: [internal]
```

The workflow-state schema lives in the `wwf_tasks` DB under a dedicated
`docengine` schema, auto-created at startup. This requires the service's DB
role to hold `CREATE ON DATABASE wwf_tasks` (granted once per stack:
`GRANT CREATE ON DATABASE wwf_tasks TO app_admin;`). Without it the service
still boots and serves `/health`, `/questionnaires`, and direct `/build`, but
`/workflows` answers 503 "DocEngine storage unavailable".

Backend env (app.env): `DOCENGINE_URL=http://docengine:8000` and
`DOCENGINE_API_KEY=<same secret as the service's DOCENGINE_API_KEY>`. An
EMPTY key disables it cleanly — `/qms/studio/*` answers 503 "DocEngine
unavailable" and the Create view shows the labeled unavailable state with a
retry, same UX contract as QMS Studio Phase 1.

Role gates (enforced server-side in `backend/app/api/qms.py`, UI only
mirrors them): reading questionnaires/documents = any elevated role; STARTING
a workflow or a direct build (authoring a controlled document) = `ADMIN`,
`OWNER`, `QP`, `QA_MGR` only.

### Status & prod promotion (owner-gated)

Deployed to **wwf_mass (test) only**, same governance as QMS Studio Phase 1:
production promotion only after the owner's tests + explicit approval.
Promotion mirrors the qms-api steps above (add the compose service + two env
vars, `docker compose up -d docengine && docker compose up -d --no-deps
backend frontend` with already-verified tags, then verify a full
questionnaire→SOP round trip produces a PASS .docx with the house header,
citations from the real DB1/DB3 sources, and that the authoring gate holds
for a non-QA/QP manager account).

## Task-Management System v2 (TMS T1–T3, unification Phase 1 priority #1)

Owner-priority-#1 upgrade to the task-management core, built additively on
the existing model (no rebuild — see the delta analysis in
`docs/PLATFORM-ROADMAP-2026-07.md` §3/§6 Phase 1). Currently on
**wwf_mass only**: backend v44 / frontend v66 / migration 0017.

- **T1 — task tree + dependency graph + handoffs.** `tasks.node_kind`
  (task|annex|step, additive column) + new `task_dependencies` table (a
  real blocker graph — WWF previously had only free-text `blocker_reason`)
  + `GET /tasks/tree` + `POST/DELETE /tasks/{id}/dependencies` (recursive
  cycle guard) + surfaced the pre-existing `handoffs` table via
  `POST /tasks/{id}/handoffs` / `POST /handoffs/{id}/resolve` (accept
  re-homes the task's department).
- **T2 — in-app team digest.** `GET /notifications/digest?window=daily|weekly`
  over the `events` table, same dept/org-wide scoping as `/activity`. Also
  fixed a stale regex bug: migration 0016 widened `notifications.reason`'s
  CHECK to include `capa_stuck`/`validation_stuck` but the `/notifications`
  query-param validator was never updated. Emailed digests and
  quiet-hours-gated push are explicitly deferred (no SMTP / push channel
  exists yet — see `docs/RESEARCH-NOTIFICATIONS-2026-07.md`'s own v2 path).
- **T3 — AI-native planning.** Two new entries in the existing data-driven
  AI catalog (`app/api/ai.py` — a capability is a `CATALOG` entry + an
  admin-bound Letta agent via `/ai/bindings`, no new endpoint):
  `workload_balance`, `next_week_plan` (on-demand version of the
  `weekly_snapshot.py` scheduled reasoning). `dependency_advisor` now
  accepts `context.task_id` to ground on that task's family (itself +
  parent + siblings) instead of the whole corpus — pairs the existing
  advisory function with T1's real graph. Advisory only; no auto-apply.

### Migration 0017

Additive: `tasks.node_kind` column + `task_dependencies` table (own RLS
policy + hash-chained audit trigger + guarded grants, same shape as 0015).
Verified: upgrades/downgrades cleanly, `schema.tasks.sql` regenerated from
alembic head with zero drift.

### Status & prod promotion (owner-gated)

Deployed to **wwf_mass (test) only**; same governance as every other
unification-era feature. Local gate: 298 backend tests pass, node --check
clean, zero schema-tasks.sql drift. Live-verified on wwf_mass with a real
auth token and real data for every T1/T2/T3 piece (tree, cycle-rejecting
dependency add, handoff accept re-homing a task, digest counts, catalog
functions degrading gracefully when unbound).

Promotion to `wwf_app` (prod) — after the owner's tests + explicit approval:
1. Apply migration 0017 to prod's `wwf_tasks` (superuser `TASKS_MIGRATION_DATABASE_URL`,
   `alembic -n tasks upgrade head` — same recipe as every prior migration).
2. `wwf_app/compose.yaml`: bump backend to the verified tag (`v44`+) and
   frontend to the verified tag (`v66`+).
3. `docker compose up -d --no-deps backend frontend`.
4. Verify: `/tasks/tree` returns real data, a dependency add+cycle-reject
   round-trips, a handoff accept moves a task's department, the digest
   endpoint returns non-error counts, `/ai/functions` lists the two new
   catalog entries.

T4 (this polish pass) is the last increment before that promotion gate.

## QC LIMS module (Phase 2 U1–U6 + Phase 3 U1–U4, native rebuild)

Native rebuild of the `qc-lims-ao` prototype domain on the WWF spine, same
facility-module pattern (uuid PK + org_id, FORCE/ENABLE RLS + org_isolation,
`audit_<tbl>` trigger, guarded GRANT block). Currently on **wwf_mass only**:
backend `v53` / frontend `v74` / migrations `0018`–`0027` (tasks DB head). The
Phase-3 certificate pipeline is complete end-to-end: **CoA in (U2) →
certificate → COQ out (U1), verified (U3), retrieval Q&A (U4)**; U5 adds the
field-to-lab custody cluster (ALCOA++), U6 the three standalone JSONB leaves.

- **U1 — Specifications.** `qc_specifications` (8-stage lifecycle
  INITIATED→…→ACTIVE, partial-unique one-ACTIVE-per-material) +
  `qc_spec_parameters` (acceptance criteria, locked once past authoring).
- **U2 — Samples.** `qc_sampling_plans` + `qc_samples` (aggregate root,
  self-FK genealogy, 10-state lifecycle incl. QUARANTINE).
- **U3 — CoA + results.** `qc_certificates` (DRAFT→REVIEWED→APPROVED→
  RELEASED, decision PASS/FAIL) + `qc_results` (auto-evaluated `complies`;
  a failing result quarantines the linked sample — the OOS hook). GxP
  guardrails: RELEASE/APPROVE are QP-only (`_QP_ROLES`); the DRAFT→REVIEWED
  transition rejects if the reviewer is the same person as the analyst.
- **U4 — OOS + CAPA.** `qc_oos_records` (two-phase investigation
  PHASE_I→PHASE_II→CLOSED) + append-only `qc_oos_register` +
  `qc_oos_notifications` (migration 0021); CAPA is a read-time view over OOS
  (no separate table). Close + disposition are QP-only.
- **U5 — custody cluster (field-to-lab traceability, ALCOA++).**
  `qc_sampling_requests` (RQS, `PP-RQS-YYYY-NNNN`; OPEN→REGISTERED→IN_PROGRESS→
  COMPLETED/CANCELLED; a 24-hour QC registration window per PP-QC-SOP-017 is
  tracked — `registration_deadline` + a computed `registration_window_met`) +
  `qc_sample_field_records` (SFR, `PP-SFR-YYYY-NNNN`; field location/GPS,
  `barrel_numbers` jsonb, destination, transport times; CREATED→IN_FIELD→
  COMPLETED/CANCELLED) + `qc_chain_of_custody` (per-sample handoff log; from/to
  user+location, reason, `transfer_type` FIELD_TO_LAB/LAB_INTERNAL/
  LAB_TO_DISPOSAL/STABILITY_TRANSFER; CASCADE child of the sample, append-only)
  — migration 0025. Frontend `qccustody-view.js` ("QC custody").
- **U6 — water / stability / transport leaves (standalone JSONB records).**
  Three independent QC registers that reference no other QC table (migration
  0026): `qc_water_tests` (`PP-WT-YYYY-NNNN`; `grade` TW/BW/TR/RO, `parameters`
  jsonb, `passed`/`ooe`, `result_date`), `qc_stability_studies` (`PP-STB-…`;
  `study_type` LT/ACC/INT, `batches` jsonb, IN_PROGRESS→CLOSED carrying a
  `shelf_life` on close, protocol/schedule/report refs), and
  `qc_sample_transports` (`PP-TRN-…`; free-text `sample_id`/`batch_id` refs,
  `external_lab`, `tests` jsonb, draft→in_transit→received, the annex-form
  booleans SAR/MOIA/TMCOC/COO/FIN, `tracking`). Guarded PATCH via a shared
  `_patch_update(patch, nullable, date_cols)` helper (date columns typed
  `date | None`; jsonb through the global codec). Frontend `qcleaves-view.js`
  ("QC water/stability", three tabs). Writers-gated, never fabricates a value.
- **P3-U1 — Certificate of Quality (COQ) generation.** `POST
  /qc/certificates/{id}/coq` renders a RELEASED certificate to a bilingual
  house-style `.docx` through the DocEngine (migration 0022 adds per-result
  provenance `source_document_code`/`source_document_date`/`source_institution`
  and the artifact pointer `coq_document_id`/`coq_generated_at`). **Two gates
  apply:** a GxP *data* gate in the app — every result must `complies is True`
  (a FAIL or an unmeasured value blocks with 409, so a conformant COQ is never
  fabricated for a non-conforming/incomplete batch); and the DocEngine's own
  `pp_verify` house-style PASS gate (a non-PASS doc is deleted, never returned;
  a FAIL surfaces as 422). Issuing a COQ is a Qualified-Person act
  (`require_role(*_QP_ROLES)`). The DocEngine client is single-sourced in
  `backend/app/docengine.py` (shared with the `/qms/studio/*` proxy).
- **P3-U2 — eCOA / CoA ingestion (the "CoA in" half).** `qc_coa_documents`
  spine (`PP-ECOA-YYYY-NNNN`; status UPLOADED→EXTRACTED→REVIEWED→PROMOTED/
  REJECTED) + `qc_coa_extractions` staging + `qc_field_placeholders` adaptive
  discovery queue (migration 0023). An incoming supplier / contract-lab CoA is
  registered, its fields transcribed and **server-graded against the material
  spec** (`POST /coa-documents/{id}/extractions` auto-maps a raw label to a
  spec parameter by an existing human mapping then by name, grades `complies`
  against the limits, and queues unknown labels); a human maps a discovered
  label once (`PATCH /coa-placeholders/{id}`) → future CoAs with that label
  auto-map; `POST /coa-documents/{id}/promote` mints a **DRAFT `ECOA`
  certificate + `qc_results`**, each carrying `source_document_code`/
  `source_institution` — feeding the U1 COQ's per-line provenance. GxP: the
  server never fabricates a value; unmapped/unmeasured fields are queued or
  left blank, never guessed; PROMOTED is reachable only through the promote
  endpoint. Frontend `qcecoa-view.js` ("QC eCOA intake").
- **P3-U3 — verify loop (source reconciliation).** `POST
  /qc/certificates/{id}/verify` reconciles a certificate promoted from an
  ingested eCoA (U2) against its source document — every promoted `qc_result`
  is matched by spec parameter to the `qc_coa_extraction` it came from and the
  numeric value / `complies` verdict / limits are compared. The outcome is
  written to `qc_coa_verifications` (migration 0024) as an auditable GxP second
  check: `verdict` VERIFIED / DISCREPANCY, a per-line `details` jsonb, and
  `verified_by`/`verified_at`; a new run is a new row so the history is
  preserved. Nothing is recomputed or silently corrected — a mismatch is
  surfaced (`GET .../verifications` lists prior runs). 409 if the certificate
  was not promoted from an eCoA. Surfaced in `qcecoa-view.js` as a "Verify vs
  source" button + verdict on a PROMOTED document.
- **P3-U4 — retrieval Q&A over ingested CoAs (in-app FTS, no external RAG).**
  `qc_coa_chunks` (migration 0027) stores a document's text passages with a
  Postgres `tsvector` generated column (`to_tsvector('english', content)`) + a
  GIN index. `POST /coa-documents/{id}/chunks` (re)indexes a document's chunks
  — the write deletes then re-inserts, so re-indexing is idempotent; `GET`
  lists them. `POST /coa-qa` retrieves the top-ranked passages for a question
  (`websearch_to_tsquery` + `ts_rank`), org-scoped by RLS and optionally
  document-scoped, and returns them **cited** (`[doc_number#chunk_index]`) as
  the grounded answer. GxP: the answer is assembled strictly from the retrieved
  passages — **never a fabricated synthesis**; no match returns
  `grounded=false` with an empty answer. `websearch_to_tsquery` uses AND
  semantics across query terms (a term absent from the corpus yields no match),
  which is the conservative behaviour for a records zone — better a blank than
  a loose match. Surfaced in `qcecoa-view.js` as an "Ask the CoA" panel. This
  is app-local retrieval over structured records; the DocEngine's Letta fleet
  still owns free-form document authoring.

Router `backend/app/api/qc.py` (prefix `/qc`), registered in `main.py`.
Frontend: `web/gf/qcspec-view.js` / `qcsample-view.js` / `qccoa-view.js`
(with the "Generate COQ" + COQ `.docx`/PDF download controls, shown to a QP
on a RELEASED cert) / `qcoos-view.js` / `qcecoa-view.js` ("QC eCOA intake", with the U4 "Ask the CoA"
retrieval panel) / `qccustody-view.js` ("QC custody") / `qcleaves-view.js`
("QC water/stability"), wired into `index.html` + the SW precache list
(`wwf-shell-v3.36.0`), under the QMS Studio nav group.

**Bug found + fixed during the wwf_mass live smoke (backend v46):**
`effective_date`/`sampling_date`/`report_date`/`result_date` were typed
`str` in the Pydantic models but bound against an explicit `::date` SQL
cast — asyncpg requires a real `date` object for that cast, so any request
supplying an actual date value 500'd. No existing test exercised a non-null
value for any of the four fields. Fixed by typing all four `date | None`
(FastAPI/Pydantic parses the ISO string before it reaches asyncpg); added
a regression test (`test_date_fields_accept_real_iso_dates`) covering all
four creation/patch paths with real dates. `v45` (pre-fix) was replaced by
`v46` before this smoke passed — `v45` was never left running.

### Migrations 0018–0027

0018–0020 (additive, same shape as 0015/0017): `qc_spec_id_seq`/
`qc_sampling_plan_id_seq`/`qc_sample_id_seq`/`qc_coa_id_seq` sequences (human
ids `PP-<TYPE>-YYYY-NNNN`), FORCE/ENABLE RLS + `org_isolation` +
`audit_<tbl>` trigger on every table, guarded GRANT block extended to the new
sequences. 0021 adds the OOS cluster (`qc_oos_records`/`qc_oos_register`/
`qc_oos_notifications` + `qc_oos_id_seq`). **0022** is column-only —
additive `source_document_code`/`source_document_date`/`source_institution`
on `qc_results` and `coq_document_id`/`coq_generated_at` on `qc_certificates`
(no new tables; new columns inherit the existing table grants). **0023** adds
the eCOA-ingestion cluster (`qc_coa_documents`/`qc_coa_extractions`/
`qc_field_placeholders` + `qc_ecoa_id_seq`), same facility canon. **0024** adds
`qc_coa_verifications` (the U3 reconciliation record). **0025** adds the U5
custody cluster (`qc_sampling_requests`/`qc_sample_field_records`/
`qc_chain_of_custody` + `qc_rqs_id_seq`/`qc_sfr_id_seq`), same canon. **0026**
adds the three U6 leaves (`qc_water_tests`/`qc_stability_studies`/
`qc_sample_transports` + `qc_wt_id_seq`/`qc_stb_id_seq`/`qc_trn_id_seq`), same
canon. **0027** adds `qc_coa_chunks` (the U4 retrieval store) — a `tsvector`
generated column + GIN index, FK CASCADE off `qc_coa_documents`, same
RLS/audit/GRANT canon. Verified: upgrades/downgrades cleanly, `schema.tasks.sql`
regenerated from alembic head with zero drift (checked against a locally
stood-up PG16 two-DB cluster).

> **Applying 0022+ on a host** — the tasks alembic env uses an *async* engine
> and `alembic_version` is owned by the `postgres` superuser (app_admin is
> DML-only), so run it with a superuser async URL:
> `TASKS_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:…@wwf-<stack>-db-tasks:5432/wwf_tasks
> alembic -n tasks upgrade head` (a one-off `docker run` off the new backend
> image on the stack's `internal` network).

### Status & prod promotion (owner-gated)

Deployed to **wwf_mass (test) only**; same governance as every other
unification-era feature. Local gate: full backend suite (323 tests, incl.
25 in `test_qc.py`) passes locally against real Postgres with the date-field
fix applied — no regressions; CI also green on PR #23 for the pre-fix
commit (schema-drift, e2e, security scan); `node --check` clean on the
three QC views. Live-
verified on wwf_mass with real `tt.qc.mgr` (QC_MGR) / `tt.qp` (QP) tokens:
a spec created with a real `effective_date` and driven to ACTIVE, a sample
registered with a real `sampling_date`, a CoA issued with a real
`report_date` linking both, a passing result (sample untouched) and a
failing result (sample auto-QUARANTINE) each with a real `result_date`,
QC_MGR blocked (403) from CoA REVIEWED (self-review) and APPROVED (QP-only),
QP succeeding (200) on both.

**P3-U1 COQ live smoke (wwf_mass, backend v48 / frontend v69, 2026-07-16).**
With real `tt.qc.mgr` (analyst) + `tt.qp` (QP) tokens: spec→ACTIVE →
certificate → a passing result carrying its `source_document_code` → COQ
refused before RELEASE (409) → REVIEWED/APPROVED(+decision PASS)/RELEASED
driven by the QP (reviewer ≠ analyst held) → analyst (QC_MGR, not QP) blocked
from certifying (403) → **QP generated the COQ (201): the DocEngine returned
a real `document_id`, `RESULT: PASS`, and a 57,907-byte `.docx` (5 paragraphs
· 7 tables · min font 6.0 pt [OK] · bilingual MK+EN OK)**; `coq_document_id`
persisted on the certificate. Prod (`wwf_app`) untouched — its tasks DB is at
alembic `0016` and has none of the QC tables.

**P3-U2 eCOA-ingestion live smoke (wwf_mass, backend v49 / frontend v70,
2026-07-16).** With a real `tt.qc.mgr` token: a spec with two parameters →
register an incoming eCoA (`PP-ECOA-2026-0001`) → transcribe two fields
(`Total THC` auto-mapped by name → **graded PASS**; `Metals (Pb)` an unknown
label → **unmapped**, count 2 / unmapped 1) → the unknown label appears in the
discovery queue → map it to the Heavy-Metals parameter → **a new eCoA with the
same label auto-maps + grades** (adaptive discovery loop) → promote the first
document → a **DRAFT `ECOA` certificate `PP-COA-2026-0003`** with one result
carrying `source_document_code=PP-ECOA-2026-0001` + `source_institution`
(1 unmapped correctly **skipped**, never fabricated); the document moved to
PROMOTED with `promoted_coa_id` set. This closes the CoA-in → certificate →
(U1) COQ-out pipeline end-to-end.

**P3-U3 verify-loop live smoke (wwf_mass, backend v50 / frontend v71,
2026-07-16).** With a real `tt.qc.mgr` token: promote an ingested eCoA into a
certificate (`PP-COA-2026-0004`) → `verify` → **VERIFIED** (checked 1,
mismatches 0) → a hand-built (non-promoted) certificate has no source →
`verify` refused (409) → re-grade the source extraction so it disagrees →
`verify` → **DISCREPANCY** (1 mismatch, reason "value, verdict") → the
verification history preserves both runs `[DISCREPANCY, VERIFIED]`.

**U5 custody-cluster live smoke (wwf_mass, backend v51 / frontend v72,
2026-07-16).** With a real `tt.qc.mgr` token: an RQS (`PP-RQS-2026-0001`) OPEN
with the 24-hour deadline set → register within the window (`REGISTERED`,
`registration_window_met=true`) → assign (`IN_PROGRESS`) → complete
(`COMPLETED`); an illegal OPEN→COMPLETED transition on a second RQS → 409; an
SFR (`PP-SFR-2026-0001`) with jsonb `barrel_numbers` driven CREATED→IN_FIELD→
COMPLETED; a sample's chain of custody logged twice (`FIELD_TO_LAB`,
`STABILITY_TRANSFER`) and listed back, a bad `transfer_type` rejected (422).

**U6 leaves + P3-U4 retrieval live smoke (wwf_mass, backend v52 / frontend v73,
2026-07-16).** With a real `tt.qc.mgr` token: a water test (`PP-WT-2026-0001`,
grade RO) created with a jsonb `parameters` block that round-tripped, patched
`passed=false` + an `ooe` note, a bad `grade` rejected (422); a stability study
(`PP-STB-2026-0001`, type LT) with jsonb `batches` driven IN_PROGRESS→CLOSED
carrying a `shelf_life`, a bad `study_type` rejected (422); a sample transport
(`PP-TRN-2026-0001`) with a jsonb `tests` list driven draft→in_transit (annex
forms `sar`+`coo` set) →received, a bad `status` rejected (422). For U4: an
eCoA (`PP-ECOA-2026-0004`) registered, 4 text chunks indexed then **re-indexed
idempotently (still 4)**, a document-scoped question retrieved a **cited**
passage (`grounded=true`), and a gibberish question returned `grounded=false`
with an **empty answer — never fabricated**.

Promotion to `wwf_app` (prod) — after the owner's tests + explicit approval:
1. Apply migrations 0018–0027 to prod's `wwf_tasks` (`alembic -n tasks
   upgrade head`; 0022–0027 need the superuser async URL — see the note above).
2. `wwf_app/compose.yaml`: bump backend to the verified tag (`v52`+, NOT
   `v45` — see the date-field fix above) and frontend to the verified tag
   (`v73`+). Prod must also run the `growflow-docengine` container (already
   on wwf_mass) for COQ generation, with `DOCENGINE_URL`/`DOCENGINE_API_KEY`
   set on the backend.
3. `docker compose up -d --no-deps backend frontend`.
4. Verify: the spec→sample→CoA→pass/fail-result→quarantine round trip plus
   the RELEASED-cert → COQ round trip above, against prod data, with real
   accounts.

**Phase 3 is complete** (U1 COQ-out, U2 CoA-in, U3 verify loop, U4 retrieval
Q&A) and both the custody cluster (U5) and the water/stability/transport leaves
(U6) are in, all on wwf_mass — the QC-LIMS domain rebuild is now feature-complete
against the `qc-lims-ao` prototype.

### Phase 4 hardening (backend v53 / frontend v74, 2026-07-16)

A code-only hardening pass over the whole QC + certificate surface (no schema
change). An adversarial backend + frontend review confirmed the foundations
clean — authorization gating, SQL-injection safety (every dynamic clause uses
hardcoded identifiers + bound params), transaction atomicity (`rls()` opens a
transaction, so multi-statement writes commit-or-roll-back together), jsonb/date
handling, enum/state guards, and the second-person (reviewer ≠ analyst) check.
The fixes close a class of **write-side FK-validation asymmetries** that
returned a raw 500 (and could persist a dangling cross-org reference) instead of
a clean 422: `add_result` now checks the cited spec parameter exists AND belongs
to the certificate's own specification; `update_placeholder` validates
`mapped_parameter_id` whenever supplied (not only on a MAPPED transition);
`create_sfr`/`update_rqs`/`update_sfr` validate `sample_id` like their sibling
creates. Plus: `generate_coq` re-asserts the certificate is still RELEASED when
stamping the artifact after the (≤120 s) DocEngine build (TOCTOU), and the
`chunks`/`items` batch inputs are length-capped so one request can't drive an
unbounded INSERT loop in a single transaction. Frontend: the transport row's
nested annex-form access is null-guarded (one malformed row no longer blanks the
Transport tab) and the water-test jsonb `parameters` are now displayed (they were
captured but never shown); the retrieval passages' numerics are escaped
(defense-in-depth). **Deliberately NOT changed:** eCoA documents/extractions stay
editable after PROMOTED — the U3 verify loop is the intended control that
*detects* post-promotion source divergence, so a hard freeze would remove its
input. Local gate: full backend suite **364 passed** (+4 hardening regressions),
`node --check` clean, SW `wwf-shell-v3.37.0`. Live-smoked on wwf_mass with a real
`tt.qc.mgr` token: a bad `parameter_id`, a bad placeholder `mapped_parameter_id`
(no status), a bad SFR/RQS `sample_id`, and an over-cap chunk batch each return
**422** (previously 500 / dangling), while a valid result still posts 201.

### ✅ Production cutover — DONE (wwf_app → v53 / v74 / alembic 0027, 2026-07-16)

On the owner's explicit go, the full validated wwf_mass stack was promoted to
production (`wwf_app`, the live 25-user system), bringing prod from
v39 / v63 / alembic `0016` up to the unified platform:

1. **Backup first** — fresh `pg_dump -Fc` of both prod DBs
   (`/opt/stacks/wwf_app/backups/pre-cutover-{tasks,users}-20260716181747.dump`;
   tasks 2.9 MB) on top of the automated `wwf-db-backup` sidecar + offsite rclone.
2. **Migrations 0017→0027** applied to prod `wwf_tasks` via a one-off `docker run`
   off `v53` with the postgres-superuser async URL — all **additive** (11
   migrations: TMS `0017`, QC LIMS `0018`–`0027`). Verified afterwards: head
   `0027`, 20 QC tables, **existing 556 task rows intact**, grants present.
3. **DocEngine added** to the prod stack (`wwf-docengine`, image
   `growflow-docengine:v3`, own `docengine.env`, `internal` network) so COQ
   generation works. One-time grant needed on first boot:
   `GRANT CREATE ON DATABASE wwf_tasks TO app_admin` (the engine creates its own
   schema — same as wwf_mass). Backend `app.env` gained `DOCENGINE_URL` +
   `DOCENGINE_API_KEY`.
4. **Images bumped**: backend + scheduler `v39`→`v53`, frontend `v63`→`v74`;
   `docker compose up -d`. (`compose.yaml`/`app.env` backed up as
   `*.bak.pre-cutover-v39`.)
5. **Live smoke** (real `tt.qc.mgr` on `https://wwf.srv1231216.hstgr.cloud`):
   **existing** flows still green (`/tasks`, `/departments`, `/reports/analytics`
   all 200 — the 25-user system is unaffected); **new** QC read+write green
   (`/qc/specifications` 200; created `PP-SPEC-2026-0001` then deleted the smoke
   spec — sequences/audit/RLS/grants all work on prod); **DocEngine** reachable
   (`/qms/studio/questionnaires` 200; engine `db:true, letta:true`).

Rollback path if needed: revert the three images to `v39`/`v63` — the additive
migrations are harmless to leave in place, and the pre-cutover dumps restore the
DB. The QMS **registry** federation (`qms-api`) was intentionally NOT promoted;
`QMS_API_KEY` is unset on prod so `/qms/documents`-style registry reads degrade
gracefully (503) while the DocEngine Studio path works.

### ✅ qms-api (Phase-1 QMS registry) retired — lighter retirement (2026-07-16)

The Phase-1 `qms-api` federation was the **strangler-façade** stopgap for a QMS
document registry (docs/UNIFICATION-ANALYSIS §7). A mapping exercise found its
registry read-path to be low-value and internally inconsistent (three data
sources trapped in the container's image/volumes; `/api/document-families`
served a hardcoded constant), and prod already ran fine without it. Rather than
re-implement a messy legacy read-path, it was **formally retired** (owner
decision):

- **wwf_mass:** `QMS_API_KEY` blanked, the `qms-api` service removed from
  `compose.yaml`, the `wwf-mass-qms-api` container dropped, `backend` recreated.
  The registry/knowledge proxy now answers a clean 503; the frontend (v75, SW
  `wwf-shell-v3.38.0`) shows an honest **"SOP Registry retired — use Document
  Studio"** panel instead of a raw error. **DocEngine Studio remains the live
  QMS surface.** Verified: `/qms/documents`·`/qms/stats`·`/qms/rag-query` → 503;
  `/qms/studio/questionnaires` → 200; `/qc/*` + `/tasks` unaffected.
- **prod:** already ran without `qms-api` (never promoted) — no infra change;
  promoting frontend v75 later would swap its registry-tab message to the
  retired panel (optional cosmetic; prod functions as-is).
- **Letta sprawl resolved:** retiring `qms-api` removed the source of the
  `GMP *` agent duplication. After a `letta` DB snapshot (`pg_dump -Fc`,
  198 MB), the **45 orphaned `GMP *` agents were deleted** (107 → 62 agents;
  the DocEngine `gf_*` fleet of 8 and the `planner-*`/`wwf_*` agents untouched).
  See `docs/LETTA-OPS-BACKLOG.md`.

## SUMA assimilation — GMP Audit-Prep Readiness tracker (2026-07-16)

The **SUMA / ISO17verSUMA** corpus (3 owner repo variants: `WEEKLY_SUMA_ISO17_v2`
canonical, `suma-platform` dev-history, `01_TASKMASTA_ISO17025` legacy HTML +
exec-report pipeline) was analysed in depth. Finding: **SUMA is the direct
ancestor of WWF/GrowFlow** — `docs/SPEC.md` is titled *"WWF / SUMA"* — so its
task model, roles, approval workflow, ALCOA+ audit, and executive dashboard are
already assimilated and surpassed by the platform (two-DB RLS, hash-chained
audit, offline PWA, DocEngine, QC LIMS). A read-only delta map (three analysis
agents over the SUMA snapshots + the live `backend/app` + `web/gf`) isolated the
**one genuinely-absent, SUMA-defining capability worth porting**: the executive
**GMP audit-preparation readiness** view (SUMA's "GMP & SOP Preparation Tracker"
+ "Audit Preparation Timeline"). e-signatures / report-versioning were dropped —
cosmetic schema-only in SUMA, and superseded by the DocEngine + two-zone scope.

**What shipped (pure read layer — NO migration, NO schema change):**
- **`GET /reports/audit-prep`** (`backend/app/api/reports.py`) — over the existing
  `tasks.tags` facet: per-programme (`MK-GMP` / `EU-GMP` / `SOP-writing`, or
  `?programs=`) rollup (total / completed / ongoing / stuck / pending / overdue +
  completion rate), a due-date **milestone timeline** with an overdue flag, and
  planning telemetry (`status_distribution`, `busiest_day` from `tasks.days`, and
  an **outcome-traceability** check = completed tasks missing an `outcome`).
  Elevated-only (base `USER` → 403); dept-scoped managers pinned to their own
  department exactly like `/reports/analytics`.
- **`web/gf/auditprep-view.js`** ("Audit readiness") — bilingual full-page view
  (nav beside Analytics, guard = above-USER), reusing the `ana-*` CSS. Readiness
  KPIs + per-programme progress bars + the milestone timeline. `api.js` +
  `data.js` i18n; SW `wwf-shell-v3.39.0`.
- **Scope guard:** this is a **planning aid, not a controlled record** — the tags
  are a *pointer* to audit-prep work; the QMS/DocEngine zone owns the controlled
  audit deliverables (per SUMA ADR-001 §2 + `docs/SCOPE.md`'s two-zone note). The
  view and endpoint say so in-UI.
- **Deferred (documented follow-on):** the heavier SUMA v2 coordination layer —
  activating the inert `tasks.workflow_state` into a manager submit→approve/reject
  sign-off + a QP-remark approval block. Backend/DB-only + frontend-less even in
  SUMA's own `suma-platform`, and GxP-scope-sensitive; a separate migration-bearing
  increment, not bolted on here.

**Local gate:** new `backend/tests/test_audit_prep.py` (8 tests: role gate, per-
programme rollup incl. zero-task programme, `programs=` bounds, timeline ordering
+ overdue, traceability, busiest-day, dept-scope) — green against a local PG16
two-DB cluster; full backend suite **371 passed**; `node --check` clean on all
changed JS. `_a0` SUMA snapshots stay in scratchpad (analysis fixtures), not
committed.

**Deployed to wwf_mass ONLY** (backend `v54` / frontend `v76`, **no migration** —
pure read). DocEngine (`v3`) + both DBs untouched. **Live smoke green** (via the
kvm4-runner): `/health` 200; `/reports/audit-prep` → **401** (route deployed +
auth-guarded, NOT 404) both with and without `?programs=`; a bogus route → 404
(confirms the 401 is real routing, not a catch-all); frontend serves SW
`wwf-shell-v3.39.0`, `gf/auditprep-view.js` (8.7 KB), the `auditprep` i18n keys,
and the `index.html` script include. CI red = same GitHub workflow-startup infra
failure (all 7 jobs died in ~5s); merged/verified on the local gate + live
wwf_mass smoke, as #23–#34.

**✅ Promoted to PRODUCTION (`wwf_app`) 2026-07-16, on the owner's explicit go.**
Image-only, **no migration** (the endpoint is a pure read over existing `tasks.tags`).
Backup-first: pre-promotion `pg_dump -Fc` of the prod tasks DB
(`/tmp/wwf_tasks_pre_v54_*.dump`, 3 MB) + baseline 556 live task rows recorded.
Bumped `/opt/stacks/wwf_app/compose.yaml` **backend `v53`→`v54`** + **frontend
`v74`→`v76`** and recreated only those two (`docker compose up -d --no-deps backend
frontend`). The **`scheduler` was deliberately left on `v53`** — identical code
minus the unused audit-prep route, and 2026-07-16 is its Thursday weekly-digest
fire day, so the singleton was not disturbed (it converges to `v54` on its next
natural recreate). DocEngine (`v3`) + both DBs untouched. **Live prod smoke green:**
`/health` 200; existing `/tasks`·`/reports/weekly`·`/reports/analytics` 401
(intact + guarded); new `/reports/audit-prep` → **401** (deployed, not 404); bogus
route 404; **556 live tasks unchanged** (data intact); frontend serves SW
`wwf-shell-v3.39.0` + `gf/auditprep-view.js`. Frontend `v76` also carries the
qms-registry "retired — use Document Studio" panel (from PR #33, which had never
been promoted) — the intended cosmetic improvement; prod functions as before.
**Rollback** = revert the two image tags to `v53`/`v74` + `docker compose up -d
--no-deps backend frontend` (no DB step, since no migration).
