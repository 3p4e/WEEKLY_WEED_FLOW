# App-wide code review — 2026-07-28

## Method

Eight independent, read-only "fresh-eyes" review agents ran in parallel, each scoped to a
distinct slice of the application, with instructions to cover the full range of what a
professional application review checks: correctness, security (authN/authZ, injection,
SSRF/path traversal, secrets), concurrency/race conditions, performance, error handling,
observability, data integrity (this is a GxP pharmaceutical QC LIMS — ALCOA+/Annex 11/Annex
16 considerations were explicitly in scope for the QC slice), test coverage, code quality,
accessibility, i18n, and infra/CI/CD hygiene. Findings below are what survived — agents were
told to skip pure style nits and cap at their most impactful ~12-18 findings each.

This is a **second-round** review: the codebase has already been through five prior rounds
(see `docs/CODE-REVIEW-2026-07-24.md`, `docs/CODE-REVIEW-DEEP-2026-07.md`, and this
session's own Phase 0-4 remediation) that closed two blockers, 21 highs, ~30 mediums, and a
lows/dead-code batch. Reviewers were briefed on that history and told to find *new* issues,
not re-litigate settled decisions. Two findings below were independently discovered by two
separate reviewers each (noted inline) — a useful corroboration signal.

Slices reviewed:
1. Backend core & security (`config.py`, `main.py`, `deps.py`, `security.py`, `db.py`,
   `notify.py`, `roles.py`, `roster.py`, `worktime.py`, `automation.py`, `auth.py`)
2. TMS routers (`tasks.py`, `collab.py`, `documents.py`, `reports.py`, `facility.py`,
   `capture.py`, `intake.py`, `ai.py`, `qms.py`, `duescan.py`, `notifications.py`, `demo_org.py`)
3. QC LIMS package (`backend/app/api/qc/*.py`, all 15 files)
4. DocEngine microservice (`docengine/app/*.py`, `docengine/engine/scripts/*.py`)
5. Frontend core/shell + data layer (`core.js`, `main.js`, `api.js`, `integrate.js`,
   `entry.js`, `render.js`, `views.js`, `data.js`, `chooser.js`, `sw.js`, etc.)
6. Frontend feature views (all `qc*-view.js`, `report-view.js`, `analytics-view.js`,
   `execreport-view.js`, `document-view.js`, `worklog.js`, `notifications-view.js`, etc. — 31 files)
7. Migrations, schema (RLS + audit-trigger completeness), and test coverage
8. Infra: `docker-compose.yml`, Dockerfiles, CI/CD workflows, docs, dependencies, dead code

---

## Blockers (2)

### B1 — CoQ masked-failure gate is keyed on "any closed OOS on the batch," not the masked parameter's own investigation
**`backend/app/api/qc/coq_aggregation.py:226-249`**

`_compile_coq_tx` is supposed to block CoQ compilation for a masked (failed-then-retested)
parameter unless a matching closed OOS covers it — the code even carries a comment
documenting this as a prior fix (H5). But the entire masking-verification block sits inside
`if not closed_oos:`, where `closed_oos` is just "does this batch have *any* closed OOS at
all," unrelated to the specific masked parameter.

**Failure scenario:** Batch X has an unrelated microbial OOS closed months ago. Potency
fails, is retested, and passes. `compile_coq` sees `closed_oos > 0` and skips the masking
check entirely — the CoQ is issued asserting overall conformance while the potency failure
was never investigated. This defeats the §6.4.1 "investigation-confirmed result set"
control the code exists to enforce.

**Fix:** scope the closed-OOS check to the masked result's specific `test_name`/`parameter_id`,
or require `oos_reference` unconditionally whenever `masked_fails` is non-empty, verified
against a closed OOS for that specific test.

### B2 — eCoA extraction values remain editable after Head-of-QC ACCEPTED sign-off, with no re-lock
**`backend/app/api/qc/ecoa.py:592-650` (`update_extraction`) / `458-498` (`decide_checklist`)**

`decide_checklist` requires every affirmation true and no discrepancies before ACCEPTING,
and locks the checklist row. `update_extraction` only blocks writes once the *document* is
PROMOTED/REJECTED — it never checks the checklist's outcome.

**Failure scenario:** checklist ACCEPTED while the document is still REVIEWED; a writer
then PATCHes an extracted value (e.g. nudges a borderline number under a limit); the
certificate is later minted from the now-different data, while the ACCEPTED checklist —
not tied to any content hash/version — silently attests to data that no longer matches
what was promoted. This is the textbook Annex-11 "signature must bind to the specific
content it attests to" failure.

**Fix:** block extraction edits once a document has an ACCEPTED checklist, or reset
`qc_ecoa_checklist.outcome` to PENDING on any extraction change (mirroring how `update_coa`
already resets `translation_verified_by/at` on content change).

---

## Highs (14)

### Security / correctness

**H1 — DocEngine/QMS Studio proxy routes are missing the path-traversal guard the sibling routes already carry** *(found independently by two reviewers, one with a reproduced exploit)*
`backend/app/api/qms.py:190-257` — `studio_questionnaire`, `studio_workflow`,
`studio_document`, `studio_download`, `studio_pdf` forward `key`/`jid`/`did` straight into
an f-string path with only a length cap. The older `document(code)`/`download(path)` routes
in the same file explicitly reject `..`, leading `/`/`\` with a comment citing exactly this
risk. One reviewer confirmed httpx 0.28 (pinned) collapses `../` on URL join, and that a raw
`..` path segment reaches the handler unmodified via Starlette's routing. **Any elevated
user** (not just admins) can reach internal DocEngine/qms-api endpoints the docstring says
are deliberately not exposed yet. **Fix:** move the traversal guard into the shared
`docengine.de_forward()` choke point so every caller inherits it.

**H2 — `capture.py` department-scoping bypass on task creation**
`backend/app/api/capture.py:158-207` — `POST /capture/import` has no `dept_scope(actor)`
check, unlike `POST /tasks`, which restricts a dept-scoped manager to their own department
(and has a dedicated regression test for exactly this). Any authenticated user can
self-import a task tagged with any department. **Fix:** enforce `dept_id == dept_scope(actor)`
for new tasks in `import_capture`, mirroring `create_task`.

**H3 — Unlinked QC result graded against caller-supplied, unvalidated limits**
`backend/app/api/qc/certificates.py:314-356` (`add_result`) — when `parameter_id` is
omitted, `lo`/`hi` come straight from the request body with no cross-check against a
registered specification, and the result still renders as a normal pass/fail line on the
certificate. **Fix:** require `parameter_id`, or add an explicit "informational, not
spec-graded" flag that suppresses the pass/fail rendering.

**H4 — Certificate signature `meaning` is never validated against the certificate's actual status**
`backend/app/api/qc/signatures.py:41-71` — any writer can attach a signature claiming
`meaning="RELEASED"` to a DRAFT certificate; `coq_docx.py` renders every captured signature
verbatim, so a spurious early "released by" attestation can coexist with a later, real one.
**Fix:** validate `meaning` against `qc_certificates.status` (or a snapshot of it) before insert.

**H5 — Water/stability/transport records have no freeze once relied upon**
`backend/app/api/qc/leaves.py` — `qc_water_tests` has no status column at all (editable
indefinitely); `update_stability`/`update_transport` only guard the status transition
itself, not the analytical fields, so a CLOSED stability study's shelf-life/report stays
writable with no versioning. **Fix:** apply the same freeze-on-terminal-status pattern
already used for certificates/specs/OOS.

### Duplicate-submission / data-integrity (GMP compliance weight)

**H6 — Duplicate task creation on double-click**
`web/gf/integrate.js:405-410, 485-508` — `GF.submitAdd` re-enables the Save button before
the actual create/update request completes (only the translation `await` is guarded). A
fast double-click fires two `POST /tasks`. **Fix:** keep the button/a `_submitting` flag
disabled for the whole async chain.

**H7 — Duplicate account creation on double-click**
`web/gf/integrate.js:943-971` — `GF.submitUser` has no guard at all around
`GF.API.createUser`. Two accounts, two different one-time passwords, one orphaned. **Fix:**
same pattern as H6.

**H8 — VOIDED certificates still expose decision + metadata-edit controls**
`web/gf/qccoa-view.js:363,375` — the Mark‑PASS/Mark‑FAIL buttons and the CoQ-metadata edit
panel both fail to exclude `VOIDED`, while the Void and Verify-translation controls three
lines below correctly do. A voided (archived) certificate can still be re-decided or
re-dated through the UI. **Fix:** add `&& c.status !== 'VOIDED'` to both conditions.

### Infra / CI

**H9 — The CI schema-drift check can silently pass when it should fail**
`.github/workflows/ci.yml:174-176, 186-188` — the pattern `diff a b && echo "... matches"`
inside a loop does not abort under bash's `set -e` semantics when the failing command isn't
the list's final command; reproduced locally (`false && echo ok` exits 0 under `set -e`).
This is the job whose entire purpose is proving migrations match the schema files. **Fix:**
capture exit codes explicitly (`if ! diff a b; then exit 1; fi`).

**H10 — DocEngine and the capture-mcp connector have zero CI coverage**
`.github/workflows/ci.yml` — `pip-audit`/`bandit`/`pytest`/image-build all target `backend/`
only. `docengine/` ships its own 527-line test suite that never runs in CI; `connector/`
(internet-exposed) has no build check or scan at all. **Fix:** add both to the CI matrix.

**H11 — DocEngine's pinned FastAPI drags in the same vulnerable Starlette range backend already moved off**
`docengine/requirements.txt:2` — `fastapi==0.115.6` with no explicit Starlette pin resolves
to the 0.40.x-0.42.x range backend's own comment says it deliberately avoided ("0.41.x
carried 8 advisories"). The fix was applied to one sibling service, not the other. **Fix:**
bump docengine's fastapi + pin starlette matching backend's, re-run pip-audit.

**H12 — Backend/scheduler have no health-check, and the documented rationale doesn't apply to them**
`backend/Dockerfile:4-6`, `docker-compose.yml` — the "no HEALTHCHECK, Traefik handles it"
comment is copy-pasted onto `backend`/`scheduler`, which have no Traefik labels (only
`frontend`/`capture-mcp` do). A wedged-but-alive backend or a silently-dead scheduler has no
automated detection. **Fix:** add a real liveness healthcheck independent of Traefik.

### DocEngine

**H13 — Cross-process filename collision breaks the artifact/document-ID binding**
`docengine/app/builder.py:119,128` + `docengine/Dockerfile:25` — the output path is derived
deterministically from caller-supplied `out_name`/`code`, guarded only by a
`threading.Lock` (process-local), while the Dockerfile runs `--workers 2`. Two concurrent
builds landing on different workers with the same default/reused name can corrupt each
other's `.docx`, or leave a document's registry row (id, verify report, byte count)
pointing at bytes that no longer match. **Fix:** name on-disk files from the immutable
job/document UUID; write to temp + `os.replace()` after PASS.

**H14 — `run_workflow` blocks the event loop during build+verify**
`docengine/app/pipeline.py:229` — unlike `/build`'s handler (which correctly wraps
`builder.build` in `asyncio.to_thread`), the background-job path calls it directly,
stalling the entire worker's event loop (health checks, other jobs' polls) for the seconds
a full build+verify takes. **Fix:** wrap in `asyncio.to_thread` here too.

---

## Mediums (20, grouped)

**Backend core/security**
- `notify.py:45-93` — `emit()`'s per-recipient loop only catches `UniqueViolationError`;
  any other error rolls back the *entire* event + every other recipient's already-inserted
  notification, not just the offending one, contradicting the migration comment that
  documents the intended "one bad recipient never fails the whole fan-out" behavior.
- Forced (first-login/post-reset) password change never rejects reusing the one-time
  password itself as the new permanent password — only length is checked.

**TMS routers**
- `auth.py:274-286` `create_user`'s `except Exception` catches *any* DB error and reports
  it to the caller as a fake 409 conflict, masking real bugs (the same anti-pattern already
  documented as fixed in `collab.py`).
- `CapturePayload.tasks` (and nested subtasks/links/sessions) has no size bound, unlike
  every other write surface's explicit DoS caps.
- `capture.py`'s per-task import loop opens one DB transaction + several dedup queries per
  task with no batching, unlike the owners/departments batching already applied nearby.

**QC LIMS**
- `_COQ_ROLES` in `common.py` excludes QP, contradicting the module's own docstring ("QP
  may also issue" a CoQ) and matching no test coverage for QP-issued CoQs.
- `custody.py`'s continuity check only fires when `to_user_id` is populated (it's
  optional), and never validates location continuity at all — a chain can silently skip
  personal custody entirely.

**DocEngine**
- Bilingual-presence check (`pp_verify.py`) is whole-document, not per-section — a section
  missing its English half is undetected if Cyrillic/Latin both exist *somewhere* in the doc.
- No stale-job reaper: a hard-killed (OOM/redeploy) job sticks at `status="running"` forever
  with no timeout/lease/sweep.
- The preamble-stripper regex (`pipeline.py:38-43`) can match and delete legitimate SOP
  prose openers ("Note: …", "Based on…"), and the §5A fidelity check runs against the
  *already-cleaned* text, making the loss structurally invisible to the one safeguard meant
  to catch content impoverishment.

**Frontend feature views**
- `qmsstudio-view.js` polling loop never stops on view-navigation and retries forever even
  on permanent errors (401/500), not just transient ones.
- `qcregister-view.js` and `qcleaves-view.js` load functions lack the `lseq` stale-response
  guard every sibling QC view has.
- `report-view.js`/`execreport-view.js` use a weaker `if (st.loading) return` guard instead
  of the `lseq` pattern — a click during an in-flight load is silently *dropped* rather than
  the stale response being discarded, leaving the toolbar and content mismatched.
- Executive Report's task drill-down status pill isn't run through `GF.statusLabel()`,
  showing raw English enum values on an otherwise fully-Macedonian screen.

**Frontend core/shell**
- `assistant.js`'s scope logic reads from an undefined `window.APP` global — a recurrence
  of a previously-fixed dead-code pattern — permanently disabling the QC-specific quick
  actions for everyone.
- `leaf3d.js` memoizes a *failed* fetch Promise forever; one transient network blip during
  boot permanently downgrades the 3D leaf logo app-wide for the rest of the session.
- `GF.kpiTile()` doesn't run its params through `GF.esc()`, unlike every sibling markup
  helper in the same file — currently safe (only fed static/numeric data) but a silent XSS
  trap for the next caller.
- Single-card status-toggle clicks (`GF.cycleStatus`, etc.) trigger a full `#panels`
  innerHTML rebuild rather than patching one card — visible flicker and can discard
  unrelated in-progress input on a large board.
- Modals/chooser popup lack real ARIA semantics (no `role="dialog"`, no focus trap, no
  `role="option"`).
- `sw.js`'s entire cache-freshness guarantee depends on a hand-maintained `VERSION` string
  with no content-hash backstop.

**Migrations/schema/tests**
- Three migrations (`0029`, `0040`, `0042`) widen a CHECK constraint and downgrade by
  unconditionally re-narrowing it with no data migration — on a production DB that has ever
  used the newly-added values (SUPERSEDED/VOIDED certs, workflow notifications), a real
  downgrade would abort mid-migration with no warning comment (unlike migration 0010, which
  explicitly flags this same risk class).
- No automated test asserts audit-trigger completeness the way `test_rls_coverage.py`
  already does for RLS — this is the exact gap that already required two remediation
  migrations (0043/0007) this session.
- `test_rls.py`'s docstring claims `handoffs`/`ai_agent_bindings` have "no API routes at
  all" and are out of scope — both now have live HTTP routes (`collab.py`, `ai.py`) with no
  dedicated cross-org isolation test (code inspection shows they're correctly scoped today,
  but the safety net other org-scoped tables have is missing here).

**Infra**
- No CPU/memory limits on any of the 8 compose services.
- No `timeout-minutes` on any CI job, on a single shared self-hosted runner — one hung job
  can block every other branch's CI for hours.
- `connector/requirements.txt` is unpinned (`>=`), unlike every sibling service's exact pins.
- The ephemeral `GITHUB_TOKEN` in `deploy.yml` is embedded in a plaintext git URL sent to an
  external `/shell` endpoint (short-lived/scoped, but argv/log-visible).
- `README.md`'s deploy table describes 3 services; the actual compose file has 8 (no DB
  split, no backups, no capture connector mentioned).

---

## Lows (grouped, abbreviated)

- bcrypt's 72-byte truncation isn't enforced as an input cap (256-char field accepted, only first 72 bytes verified)
- `delete_user`/`update_user`/`purge_user` lack the abuse-throttle their siblings (`create_user`/`change_password`/`reset_password`) have
- `reset_password`'s docstring ("nobody may reset an ADMIN") doesn't match `_can_manage`'s actual permissive behavior
- `SNAPSHOT_TZ` reads a bare env var at import time instead of going through the centralized `Settings` validation path
- `password_reset_codes` table (users DB) is fully dead — schema + RLS policy with zero application code touching it (flagged independently by two reviewers)
- QC LIMS: the `$PLACEHOLDER`-splice pattern for second-person-review fields is duplicated ad hoc across `certificates.py`/`oos.py` instead of factored into `common.py`
- DocEngine: internal filesystem paths leak into the `verify_report` API response; `BuildIn.out_name` has no length bound; `document_pdf` does blocking file I/O in an async handler; the HEADERDATA-parsing line-scan is duplicated in two files with nothing enforcing they stay in sync; pinned dependencies are plausibly a year+ behind upstream
- Frontend: the "list-load failed, retry" panel markup is copy-pasted near-verbatim across **18 files**; the "detail-fetch failed" row across **5 files** — both are exactly the kind of duplication `GF.kpiTile()` was already extracted to solve
- Frontend: several static UI strings (leaf-logo tooltips, assistant placeholder, "back to leaf") never route through `AL()`/`GF.t()`; `export.js` carries an undocumented dead shadow `GF.rollover` (every sibling shadow implementation elsewhere has an explicit "defined for real by integrate.js" comment — this one doesn't); `GF.submitAdd` has grown to 130+ mixed-concern lines; a mid-load token-expiry race in `loadAndRender()` triggers a wasted extra render behind the login screen
- Infra: a stale comment in `web/nginx.conf` still references the now-removed `web-next/`; CI's image-build job never prunes, letting images accumulate on the self-hosted runner's disk; `bandit` excludes `backend/scripts/` (1,410 lines, including the scheduler that ships as its own deployed container)

---

## What's holding up well

Every reviewer independently flagged real strengths worth preserving, not just defects:

- **RLS + audit-trigger + test-cleanup consistency**: all 47 tasks-DB and 4 users-DB tables
  have RLS enabled with policies; 43/46 org-scoped tables carry the audit trigger, and the 3
  deliberate exceptions are each explicitly commented; `purge_org()` is an exact match
  against the current schema's org-scoped table list.
- **Department-scoping discipline**: `tasks.py`, `collab.py`, `documents.py`, `reports.py`,
  and `ai.py` consistently apply the scope-visibility guard at exactly the boundaries the
  project's own structural test (`test_every_task_id_route_calls_the_scope_guard`) enforces
  — the two gaps found this round (H1, H2) are both routes *outside* that test's shape
  (proxy-forwarding, non-`{task_id}` create path), not failures of the pattern itself.
- **The `lseq`/`GF.esc()`/`AL()` conventions** are correctly applied in the large majority
  of call sites across 30+ frontend files — gaps found are concentrated in newer or
  less-visited views, not systemic.
- **GxP write-path care**: advisory-locked numbering, TOCTOU re-checks on long-running
  builds, append-only OOS registers, and the `pp_verify` PASS-gate all hold up structurally.
- Auth fundamentals (timing-safe login, DB-truth token invalidation on password change,
  consistent org-scoping on admin-pool queries, parameterized SQL throughout, a genuinely
  careful audit hash-chain verifier) are solid.

---

## Recommended remediation order

1. **Blockers (B1, B2)** — both are live GxP data-integrity gaps in the certificate/eCoA
   release path; fix before the next audit cycle regardless of anything else.
2. **H1, H2** (authz bypasses reachable by any elevated/authenticated user) and **H6, H7**
   (duplicate-record creation, real compliance weight for a GMP system) — next priority,
   all four are narrow, mechanical fixes.
3. **H9** (CI's safety net can't actually catch schema drift) — fix before trusting CI green
   on any future schema-touching PR.
4. Remaining highs (H3-H5, H8, H10-H14), then mediums, then lows — same phased-batch
   pattern as the five prior review rounds.

No fixes have been applied yet — this is the findings document. Say the word and I'll turn
this into the same kind of phased implementation plan (and execute it) as the prior review
rounds.
