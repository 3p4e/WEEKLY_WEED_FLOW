# In-Depth Application Review — 2026-07-14

A full-stack review of WWF/GrowFlow "on all levels" (auth & org isolation,
data model & RLS, the hash-chained audit subsystem, the Document Engine /
executive-report path, the frontend, deploy/ops, and the recently landed
Mass Weed + Phase-A work). Five specialist passes plus live checks against the
production deployment. This document is the canonical record: what is real,
what has already been remediated in this change set, and what is **confirmed
but deliberately deferred pending explicit owner go-ahead** because it changes
the integrity subsystem on a live system and is not a demo-blocker.

**Headline:** no critical issue. There is **no clean auth / org-isolation
bypass.** The security core — two-DB RLS, parameterized SQL, the forced
password-change gate, token/identity handling, and DB-enforced lock
immutability — held up under adversarial review. The real exposures sit at the
**department** boundary (which the codebase itself treats as a security line)
and in a set of correctness/hardening gaps.

---

## 1. Findings — severity-ranked

### HIGH

| # | Finding | Status |
|---|---------|--------|
| **H1** | **Audit hash-chain forks under concurrency.** `app.fn_audit_row()` reads the chain tail with `SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1` **and no lock** (`backend/schema.tasks.sql`, `fn_audit_row`). Two concurrent writers read the same tail → both insert with the same `prev_hash` → the id-ordered chain forks. `/audit/verify` (`backend/app/api/audit.py`, `_CHAIN_SQL`) then reports linkage "breaks" that are an artifact of the fork, giving real tampering cover. Live check: **12 forks / 38 id-order breaks over 3,143 entries**, but every entry re-hashed authentic (200/200 spot-sample) — data integrity is intact; the *linkage* is what forks. | ✅ **FIXED (batch 2)** — `PERFORM pg_advisory_xact_lock(...)` before the tail read in `fn_audit_row`, both DBs (migrations tasks-0012 / users-0006 + schema files; CI schema-diff byte-exact). Proven with a 320-concurrent-write probe: **unlocked → 299 breaks / 56 forks; locked → 0 / 0.** |
| **H2** | **Offsite backup will silently die in 2026.** The `wwf-backup-offsite` rclone crypt sync authenticates with rclone's *shared* Google OAuth `client_id`, which Google is retiring during 2026. Backups run today; they stop without warning when the shared client is revoked. | **USER ACTION** — ~15 min: create an owner-owned Google Cloud OAuth client_id and drop it into `rclone.conf`. Steps can be written up on request. |
| **H3** | **The executive report is a shell with no data plumbing** *(the strategic finding).* The Document Engine renders the owner's exact six-topic weekly structure, but every metric cell is hand-typed — there is no structured cultivation/production/equipment dataset behind it. It turns "retype the numbers weekly" into a rendering step, not a generated report. | **DEFERRED** (product) — minimal path: 3 snapshot tables + a resolver feeding `content.metrics`. Larger than a hardening fix; belongs in a scoped feature cycle. |

### MEDIUM

| # | Finding | Status |
|---|---------|--------|
| **M1** | **Dept managers can read org-wide task content via `/audit`.** Audit rows carry the full `old_values`/`new_values` task JSON and are RLS-scoped by `app.is_elevated()` (org-wide), **not** department-filtered — the one place the department boundary leaks. | ✅ **FIXED (batch 2)** — `audit.py` `list_audit` now filters dept-scoped managers to rows whose payload `department_id` matches theirs and drops the users (identity) chain for them; org-wide roles unchanged. Tests pin both scoping and non-over-restriction. |
| **M2** | **AI corpus context isn't dept-scoped.** A department manager's AI answer is grounded in *all* departments' tasks, not just their own. | ✅ **FIXED (batch 2)** — `ai.py` `_task_context` takes the caller's `dept_scope()` and filters the grounding corpus to their department; execs/QP/ADMIN stay org-wide. Tests assert the marker task from another department never reaches the prompt. |
| **M3** | **Clickjacking** — no `frame-ancestors`; the authenticated exec app was framable. | ✅ **FIXED (v51)** — `frame-ancestors 'self'` added to both CSP `add_header` lines in `web/nginx.conf` (server + static-asset location) and mirrored in `web-next/nginx.conf`. `'self'` preserves the same-origin design/edit harness. Verified live (header present on test + prod). |
| **M4** | **The e2e test tree is served publicly** (`/e2e/seed.js` → 200 live) — discloses API flows and selectors. | ✅ **FIXED (v51)** — `web/Dockerfile` now `rm -rf`s `/e2e` (and drops the shipped `Dockerfile`/`nginx.conf`/loose `.md`) from the web root regardless of build context; `web/.dockerignore` also excludes `e2e/`, `node_modules`, `*.cjs`. Verified live: `/e2e/seed.js` → **404** on test + prod. |
| **M5** | **The audit chain is forgeable by the `app_admin` role the app runs as** (no HMAC key; the role holds `UPDATE`/`DELETE` on `audit_log`). "Tamper-evident" overstates the guarantee against a privileged insider. | **DEFERRED** (design) — a keyed HMAC over the payload (key outside the app role) would close it; a scale/scope decision, not a demo fix. |
| **M6** | **`department` is dual-keyed** (a `department` text label *and* a `department_id`, fuzzy-matched in places) — a rename/mismatch can misroute a report section. | **DEFERRED** — converge on `department_id` as the sole key; low-risk but a data-touching refactor. |
| **M7** | **The non-GMP disclaimer is PDF-only**, not shown in-app; a locked document reads like a signed "SUBMITTED RECORD." | **DEFERRED** — surface the informational/non-GMP banner in the in-app locked view. Frontend, low-risk; batched with the next UI pass. |

### LOW (correctness / hardening)

| # | Finding | Status |
|---|---------|--------|
| L1 | Calendar "today" used `Date.toISOString()` → off-by-one for `+` UTC offsets *(new-code bug from the Mass Weed calendar view)*. | ✅ **FIXED (v51)** — `web/gf/calendar-view.js` now uses facility-local `GF.todayISO()`. |
| L2 | Service worker precache omitted 3 shipped view files (`execreport-view.js`, `dept-templates.js`, `depthome-view.js`) *(new-code omission)*. | ✅ **FIXED (v51)** — added to `SHELL` in `web/sw.js`; `VERSION` bumped `v3.12.0` → `v3.13.0` to invalidate stale caches. Verified live. |
| L3 | Unbounded `recurrence.interval` → a 500 that reverts a completion. | ✅ **FIXED (batch 2)** — `_check_recurrence` bounds interval to `1..1000` (422). |
| L4 | Unescaped task-id in a citation `href`. | ✅ **HARDENED (batch 2)** — already regex-constrained + `GF.esc`/`_e()` in both renderers; added a UUID-shape guard in `document-view.js` so any non-UUID id degrades to an inert chip instead of an inline handler. |
| L5 | Unbounded `tags`. | ✅ **FIXED (batch 2)** — `_check_tags` bounds count (≤32) and per-tag length (≤64) on create + patch (422). |
| L6 | No throttle on the heavy AI endpoints. | **DEFERRED** — extend the existing in-process limiter. |
| L7 | `profiles_self` full-column RLS policy (latent), and child-table RLS `WITH CHECK` trusting only `org_id`. | **DEFERRED** (design) — tighten policy scope; no live exposure today. |
| L8 | `web-next/` dead scaffold; CI lacks image-CVE + secret scanning. | **DEFERRED** — housekeeping / CI hardening. |

---

## 2. Remediated in this change set (v51 frontend — deployed test + live)

All frontend, one image, low risk. Chosen as the *safe, demo-relevant* subset
to land immediately before the executive demo. Deployed to **test (`wwf_mass`)**
and **live (production)**, then verified: index `200`; `frame-ancestors 'self'`
header present; `/e2e/seed.js` → `404`; service-worker `VERSION` =
`wwf-shell-v3.13.0`; `mass-weed.css` `200` — on both hosts.

- **M3** clickjacking → `frame-ancestors 'self'` (both nginx confs).
- **M4** e2e-tree exposure → `Dockerfile` strip + `.dockerignore`.
- **L1** calendar off-by-one → `GF.todayISO()`.
- **L2** service-worker precache gap → SHELL + `VERSION` bump.

## 3. Production data operations recorded in this change set

Direct-SQL data corrections applied to the live tasks DB this week, each
run inside a single transaction with `SET LOCAL app.*` GUCs so the
hash-chained audit trigger attributes the change to the admin actor, and each
rehearsed on the `wwf_mass` test DB and snapshotted (`pg_dump -Fc`) before the
live `COMMIT`. Committed here as canonical records (matching the existing
`oneoff_*_20260713.sql` convention), **not** re-runnable migrations:

- `backend/scripts/oneoff_reassign_qcm_by_department_20260714.sql` — Phase B:
  redistribute qcm.blani's non-QC captured SOP subtrees to the correct
  department managers (QA→qam.jovana, Cultivation→cum.elen, Logistics→whm.log,
  Maintenance→mam.rez); QC stays with qcm.blani.
- `backend/scripts/oneoff_ceo_order_delegation_20260714.sql` — Phase C: the 4
  "CEO Order" theme roots move to `ceo.kes` (org-wide, no department); their
  execution sub-tasks are delegated to the department that does the work via
  the app's native cross-department delegation (parent_id untouched).
- `backend/scripts/oneoff_enrich_task_weekstart_20260714.sql` — honest
  `week_start` fill: version-level tasks inherit their parent document's
  `week_start`. Deliberately does **not** fabricate `due_date` or work-session
  `ended_at` (no honest duration exists for single-save events).
- `backend/scripts/oneoff_mirror_profiles_to_mass_20260714.sql` — mirror the 6
  touched account rows (4 new managers + ceo.kes/own.jc refresh) into the
  `wwf_mass` users DB, exact UUIDs, upsert-by-id, no deletes.

---

## 4. Delivery — two batches

**Batch 1 (frontend, demo-safe)** was applied and deployed first (§2): M3, M4,
L1, L2 — all frontend, one image (v51), low risk, before the executive demo.

**Batch 2 (backend/schema, integrity subsystem)** was applied after explicit
owner go-ahead, as one coordinated backend + prod-migration window:

1. **H1** — `pg_advisory_xact_lock` in `fn_audit_row`, both DBs
   (migrations tasks-0012 / users-0006 + schema files).
2. **M1** — department predicate on `/audit` for dept-scoped roles.
3. **M2** — dept-scope the AI retrieval corpus.
4. **L3 / L4 / L5** — bound `recurrence.interval`, harden the citation
   renderer (UUID guard), bound `tags`.

Local gate before deploy: `pg_dump` schema-diff **byte-exact** for both DBs
(alembic-built vs schema file); full pytest **243 passed** (incl. new M1/M2/L3/L5
tests); a 320-concurrent-write H1 probe (**unlocked → 299 breaks / 56 forks;
locked → 0 / 0**); `node --check` clean.

Deployed as backend image **v32** to **test (`wwf_mass`) then live (production)**,
each DB snapshotted (`pg_dump -Fc`) first. All four DBs migrated
(tasks 0011→0012, users 0005→0006); both trigger copies confirmed carrying
`pg_advisory_xact_lock`. Post-deploy: backend + scheduler boot clean, prod
`/health` 200, index 200, bad-login 401. `/audit/verify` on prod still reports
the **38 pre-existing historical breaks** — expected: the lock prevents *new*
forks; it does not (and must not) rewrite immutable audit history. The users
chain shows 0 breaks.

Deferred as product/design (own cycle): **H3** report data plumbing, **M5**
HMAC-keyed audit, **M6** department single-key convergence, **M7** in-app
disclaimer, **L6–L8**.

**Owner action, independent of the above:** **H2** — own the Google OAuth
client_id so offsite backups don't stop in 2026 (tracked separately).

---

## 5. What must be preserved

Consistent with `docs/AUDIT-TRIAGE-2026-07-12.md`: the DB-level RLS, the
hash-chained audit trail, `pwv` token invalidation, timing-safe login, the CI
schema-drift check, the domain depth, and bilingual EN/МК are the load-bearing
strengths. None of the fixes above weaken them; H1 and M5 *strengthen* the
audit guarantee rather than replace it.
