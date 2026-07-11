# External-Audit Triage — 2026-07-12

Three external AI audit reports of WWF (two "Comprehensive Multi-Agent Audit
Reports" dated 07-11/07-12 and one "Master Audit & Review" dated 07-12) were
fact-checked claim-by-claim against this codebase on 2026-07-12. This document
is the canonical record of which findings are **real**, which are **false or
stale**, and which are **deliberate design choices** — so that future reviews
(human or AI) do not re-chase settled items.

> Meta-finding: the 07-12 "Master" report cites four specialist sub-reports
> (`docs/analysis/requirements-analysis-2026-07-12.md`,
> `docs/analysis/security-audit-2026-07-12.md`,
> `docs/analysis/test-coverage-analysis-2026-07-12.md`,
> `docs/ARCHITECTURE-REVIEW-2026-07-12-WINSTON.md`) **that do not exist in
> this repository**. Several claims trace to our own
> `docs/ARCHITECTURE-REVIEW-2026-07.md` (Jul 3) describing code that has since
> been fixed. Treat external-report provenance with suspicion.

## 1. FALSE or hallucinated findings — do not act on these

| External claim | Reality |
|---|---|
| "CRITICAL: XSS — no centralized escapeHtml(), task titles flow unescaped" | `GF.esc` exists (`web/gf/core.js:5`) and is applied at effectively every user-content sink (render.js, views.js, worklog.js, report-view.js, collab.js, integrate.js). Residual nits fixed 2026-07-12: `'` added to `GF.esc`; `integrate.js` purge-button username now attribute-safe. |
| "JWT stored in localStorage" | Token lives in **sessionStorage** (`web/gf/api.js:8`), cleared on tab close. localStorage holds only theme/lang/UI prefs. |
| "ON DELETE CASCADE on organizations destroys the audit trail" | `audit_log.org_id` has **no FK at all** in either DB (`schema.users.sql`, `schema.tasks.sql`) — no cascade path exists. There is also no org-delete endpoint. |
| "No CHECK constraint on tasks.status; 'completed'/'done' synonyms in data; consumers hedge queries" | `tasks_status_check` exists (`schema.tasks.sql`, baseline 0001) with 6 canonical values. 'working'/'done' are **display labels** mapped 1:1 via `S_IN`/`S_OUT` (`web/gf/integrate.js:8-9`). The only "hedge queries" found live inside the audit document itself. |
| "progress_notes jsonb duplicates task_progress — dual source of truth" | The column was **dropped**; `list_tasks` aggregates live from `task_progress` (`backend/app/api/tasks.py`), pinned by a regression test (`tests/test_tasks.py:100-131`). |
| "deps uuid[] allows dangling references" | `deps` was dropped as a dead column (same regression test). |
| "marked lib loaded from unpkg CDN in web/report-viewer.html" | File does not exist; **zero** CDN references anywhere; three.js is vendored locally (`web/gf/vendor/three.min.js`). |
| "Single GrowFlow theme — theming not started" / "6 visual themes" | **33 themes** exist (`web/gf/core.js:284-321`) over CSS custom properties with picker + persistence. |
| "Executive analytics dashboard missing" | Built 2026-07: Executive Overview with KPI row, per-dept matrix, COO ops strip, CEO strategy strip, 6-week sparkline, WoW delta (`web/gf/views.js` `exec()`). |
| "Weekly snapshot scripts not deployed as cron/service" | Runs as the standalone `wwf-scheduler` compose service (`docker-compose.yml`, `backend/scripts/scheduler.py`) with missed-run recovery. |
| "X-Content-Type-Options header missing" | Set in both nginx configs (`web/nginx.conf:14`, re-asserted for static at `:62`), as is `Referrer-Policy`. |
| "dept_scope() ambiguity on sensitive surfaces" | Fixed 2026-07-11: `is_dept_scoped_role()` (`backend/app/deps.py:57`) — sensitive document surfaces refuse department-less managers; regression tests in `tests/test_audit_fixes.py`. |
| "Duplicated Fri→Thu week logic reports.py vs scheduler.py" | Centralized in `backend/app/api/weekwindow.py`, imported by reports + documents. The one mirror in `backend/scripts/weekly_snapshot.py` is deliberate (separate container, documented "kept in sync"). |
| "Two competing deploy mechanisms can drift" | `deploy.yml` **drives** kvm4-runner (`POST $RUNNER_URL/shell`) — one chained path, not two. |
| "GET /tasks/{id} IDOR" (implied by earlier reviews) | Department-scope guard added 2026-07-11 (`tests/test_audit_fixes.py::test_manager_cannot_read_foreign_department_task_by_id`). |

## 2. Deliberate design choices the auditors misread

- **X-Frame-Options omitted** — documented decision (`web/nginx.conf:10-13`):
  the design/edit-mode panel is driven from a parent frame. Revisit only if
  that embedding is dropped.
- **OTP returned in the create/reset API response** — the SUMA provisioning
  model: no self-signup, no email delivery; the creator hands the OTP to the
  user, `must_change_password` forces rotation on first login, and the OTP is
  bcrypt-hashed at rest. Deliberate, not a leak.
- **Snapshot script's `fri_thu` mirror** — the scheduler container cannot
  import app code; the mirror is annotated with its source of truth.
- **Zero frontend npm dependencies** — conscious supply-chain choice; vendored
  three.js is the only third-party JS.
- **Failed logins are logged to structured JSON logs, not `audit_log`** —
  the audit tables are populated by hash-chained DB triggers; manual inserts
  would fight the chain. Forensics use the JSON request log (see §3).

## 3. CONFIRMED findings — remediated 2026-07-12 (this change set)

| Finding | Remediation |
|---|---|
| No CSP / HSTS headers | Added in `web/nginx.conf` + `web-next/nginx.conf`. CSP allows `'unsafe-inline'` script/style (inline handlers are the app's idiom) — the enforcement value is `connect-src`/`object-src`/`base-uri`, which neuter exfiltration and plugin/script injection. Google Fonts hosts allowed explicitly. |
| python-jose 3.3.0 unmaintained | Migrated to PyJWT (`backend/app/security.py`, `requirements.txt`). Alg pinned HS256 before and after; claim structure unchanged so live tokens stay valid. |
| No rate limiting on user-create / password endpoints | `create_user`, `change_password`, `reset_password` now use the same in-process limiter as login, plus a stale-key sweep so the dict cannot grow unbounded. |
| No failed-login forensic trail | Failed logins now emit a structured JSON log line (identifier + client IP). |
| Unbounded string inputs on user/task models | `max_length` bounds on user-facing string fields. |
| `days text[]` unvalidated | Validated against the canonical `{Mon..Sun}` token set → 422. |
| No security scanning in CI | New `security` job: `pip-audit` (blocking) + `bandit -ll`. |
| E2E login boilerplate ×5, no negative-auth spec | Shared `login()` helper; new `auth-negative.spec.js` (wrong-password rejection). |
| *(found during verification, not in any report)* Wrong-password login gave **no visible feedback** — the 401 handler rebuilt the login card, detaching the node the error was written to, silently bouncing the user to the splash | `web/gf/api.js`: a failed `/auth/login` no longer tears down the card; the error renders on the live element. Pinned by `auth-negative.spec.js`. |
| *(found during verification)* "Delete permanently" purge button emitted a malformed `onclick` for every username (raw JSON quotes terminated the attribute) | `web/gf/integrate.js`: attribute-safe `GF.esc(JSON.stringify(...))`. |
| No offsite backups | `backup-offsite` compose service — nightly `rclone` **crypt**-encrypted sync of the local dump volume to Google Drive. Restore procedure + crypt-key custody documented in `docs/BACKUP.md`. |
| kvm4-runner audit trail; `.env` modes | Host-side: structured command logging on the runner; `.env` files restricted to 0600. Documented in `docs/DEPLOY.md`. |

## 4. CONFIRMED but deferred at current scale (5 users, 1 org, 1 VPS)

| Item | Rationale / trigger to revisit |
|---|---|
| MFA (TOTP) for elevated roles | Worth doing before external exposure or GxP-lite scope change. |
| kvm4-runner token rotation / network restriction | Rotation must be coordinated with GitHub secrets + deploy tooling in one window; binding to VPN/localhost would sever the only deploy path. Logged as a coordinated future step. |
| Redis-backed rate limiter | Needed only past one backend replica. |
| Internal TLS nginx↔backend | Docker-internal traffic on one host; MITM requires host compromise, which already grants everything. |
| Monitoring/metrics stack (Prometheus etc.) | JSON logs + `/health` exist; a metrics stack exceeds ops budget today. |
| Load/perf testing | 5 concurrent users; revisit at 10× scale. |
| API versioning (`/v1/`) + pagination envelopes | No external consumers; revisit before any API is offered externally. |
| Viewer role | Real feature request (auditors/board) — schedule as product work. |
| Self-service password reset | `password_reset_codes` table exists, endpoint does not; the SUMA model (admin-mediated reset) is the current policy. |
| RS256 JWTs | Single-service issuer/verifier; symmetric HS256 is appropriate. |
| Frontend unit tests / React (`web-next/`) migration | Strategic decision pending; `web-next` remains a preview scaffold. |
| Hierarchical task tree, RAG/Qdrant, notifications | SPEC future phases, correctly not started. |

## 5. Scores context

The external reports rate WWF 8.0–8.4/10 with verdict "disciplined remediation,
not rewrite" — a fair conclusion even after correcting their errors. What they
consistently credit as exceptional (DB-level RLS, hash-chained audit, `pwv`
token invalidation, timing-safe login, CI schema drift check, domain depth,
bilingual EN/MK) matches our own assessment and must be preserved.
