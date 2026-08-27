# Application-wide code review — 2026-07-24

**Method:** 8 independent, read-only fresh-eyes passes run in parallel, each scoped to a slice
of the app (backend core/security, backend TMS routers, the QC LIMS package, the DocEngine
microservice, frontend core/shared JS, frontend TMS/collab views, frontend QC/QMS views,
and a migrations/schema/dead-code/test-coverage audit). Every finding below was verified by
reading the actual code path (and, where noted, by reproducing the defect against a crafted
input) — nothing here is speculative. This is a "tell it straight" pass: real bugs, real
inconsistencies, real sloppiness, ranked by what actually breaks or lies to a user, not by
how the code reads.

No file was changed as part of this review — it is a findings document only. Fixes are a
separate, deliberately unstarted follow-up (see the priority order at the bottom).

---

## BLOCKER

### B1. DocEngine's `pp_verify` "hard gate" cannot detect missing, incomplete, or non-bilingual content — only a font-size floor actually blocks a build
`docengine/engine/scripts/pp_verify.py:63-77`, `docengine/app/builder.py:61-76`

The bilingual check only ever prints a `WARN` — it's never ANDed into the pass/fail verdict.
The content-completeness/no-impoverishment check only runs `if a.source`, and
`builder.run_verify()` **never passes `--source`**, so it never runs at all in this service.
The only thing that can flip the verdict to FAIL is a sub-6pt font run. Reproduced directly:
a document containing nothing but an empty `<!--HEADERDATA-->` block, a document with zero
Macedonian content, and a document that's pure whitespace all returned `RESULT: PASS`.

This is the gate the whole pipeline's safety claim rests on ("a FAIL never leaves the
service," "the app never fabricates data"). As built, it doesn't check for the thing it's
named after. Any LLM hiccup, context blow-out, or an over-aggressive preamble-stripper
leaving a section blank produces a stamped-PASS controlled document.

### B2. DocEngine's document metadata block is parsed with a non-greedy regex that stops at the first `-->` anywhere in a field's own value — silently corrupts the document
`docengine/app/pipeline.py:87-104` (writes the block), `docengine/engine/scripts/build_from_md.py:35` (parses it, `<!--HEADERDATA(.*?)-->`)

Reproduced: a title of `"Опис --> на процедура"` truncates the parsed header to
`{'mk_title': 'Опис'}` — the English title, document code, version, and doctype are silently
dropped from the header and instead leak into the document **body** as garbage paragraphs
(`"en_title: desc"`, `"code: X-1"`, etc., rendered as bogus content). No exception anywhere.
Per B1, `pp_verify` still reports PASS on the corrupted output. Any human-entered title/code/
version string containing `-->` (arrow notation, copy-paste artifacts) silently ships a
document with the wrong code/version stamp and garbled body text, with zero signal anything
went wrong.

---

## HIGH

### Backend — auth & core

**H1. `SECRET_KEY` placeholder guard is an allow-list on the literal string `"production"`, not a deny-list on `"development"` — anything else fails open to a warning.**
`backend/app/config.py:78`
```python
if settings.environment.strip().lower() == "production":
    raise RuntimeError(...)
logging.getLogger(__name__).warning(...)   # falls through here for anything else
```
`environment` is an unconstrained `str`. A box shipped with `ENVIRONMENT=prod` (a very common
shorthand), or a typo, or a platform-injected value that isn't the exact string, boots
successfully with the shipped placeholder secret still active. Since this is the sole JWT
signing key, anyone who knows the public placeholder (it's in `.env.example`) can forge a
valid token for any `sub`/`role`/`org_id`, including `ADMIN` — a full auth bypass. CI only
ever exercises the literal default. **Fix direction: invert the condition — raise unless
`environment` is exactly `"development"`.**

**H2. `/docs`, `/redoc`, `/openapi.json` are always reachable, including in production — a previously-flagged, still-open finding.**
`backend/app/main.py:25` — `FastAPI(...)` has no `docs_url`/`openapi_url` gating on environment.
`docs/APP-REVIEW-2026-07.md:42-45` already called this out; it's still unfixed. Anyone
unauthenticated can browse the complete route/schema map of a regulated QC LIMS.

**H3. `notify.py`'s per-recipient insert swallows every exception with no logging — defeats the exact failure mode `safe_emit()` exists to prevent.**
`backend/app/notify.py:66-73`
```python
except Exception:  # unique_violation → already an open identical row
    pass
```
This catches *any* exception, not just the intended unique-violation — including a
`notifications_reason_check` CHECK-constraint failure (the exact H4 incident class the
module's own docstring cites as the reason it exists). Not firing today (all current call
sites pass valid reasons), but the safety net for the next typo is structurally broken:
**catch `UniqueViolationError` specifically; log/re-raise anything else.**

### Backend — QC LIMS (GxP-critical)

**H4. CoQ template metadata is freely editable — even after content is edited — on a RELEASED certificate, with no set-once limit, despite being what's literally printed on the issued document.**
`backend/app/api/qc/certificates.py:386-429`
Every analytical field on an issued cert is set-once (back-fill from blank only; changing an
already-set value 409s — enforced, tested). But `cultivation_batch`, `product_code`,
`packaging`, `packaging_date`, `manufacture_date`, `expiry_date`, `retest_date`,
`botanical_type`, `chemotype` are unconditionally editable post-release, no old-value check.
This is documented-intentional today ("metadata is editable... it's descriptive, not a
result") — but `expiry_date`/`manufacture_date` are exactly what prints on the distributed
certificate. Any `_WRITERS` user (not just QP) can silently change a RELEASED cert's printed
expiry date with no new cert number, no sign-off, no revision trail.

**H5. `oos_reference` is an unverified free-text bypass for the CoQ masked-failure gate.**
`backend/app/api/qc/coq_aggregation.py:222-239`
When a failing result was superseded by a passing retest, compile requires a closed-OOS
record OR a supplied `oos_reference` string — but that string is never checked against
`qc_oos_records` for existence, closure, or relevance. Proven by the repo's own test
(`test_coq_masked_fail_requires_oos_trail`): a reference number that is never created
anywhere is enough to pass. A THC FAIL (99.0 vs. 10–30 limit) superseded by a PASS retest,
with **zero actual investigation ever opened**, can be certified by typing any string into
that field.

**H6. No second-person check on the certificate APPROVED transition — self-approval is possible.**
`backend/app/api/qc/certificates.py:487-511`
The REVIEWED transition correctly blocks reviewer == analyst. APPROVED just stamps
`approver_id=user["id"]` with no comparison to the analyst or reviewer at all — contrast
`coq_aggregation.py`'s `review_coq`, which does block `compiled_by == approver` correctly.
A QP who authored/entered results can move their own CoA straight through to APPROVED.

**H7. No second-person check on the eCoA §6.3.2 checklist decision.**
`backend/app/api/qc/ecoa.py:418-458` vs. `461-501`
Filling the checklist (`_WRITERS`) and deciding it (`_HOQC`) use overlapping role sets with
no comparison of who filled it vs. who decides it. A single QC_MGR can fill every
affirmation themselves and immediately self-decide ACCEPTED.

### Backend — task management

**H8. `workflow_transition`'s sign-off state machine has a TOCTOU race that can write a self-contradictory audit trail.**
`backend/app/api/tasks.py:919-987`
The current-state read is a plain `SELECT` (no `FOR UPDATE`), and the terminal write has no
`WHERE workflow_state=$cur` guard — unlike this same file's own recurrence-materialization
guard 200 lines earlier, which explicitly takes `FOR UPDATE` for exactly this race class.
Two concurrent APPROVE/REJECT calls on the same "submitted" task can both pass the
precondition check, both append to `task_workflow_events` (unconditional insert, no
conflict), and both update `workflow_state` — leaving an append-only "evidence" log that
contains both an APPROVE and a REJECT from the same prior state. This is the one workflow
explicitly built for compliance sign-off.

**H9. `capture.py`'s idempotent re-import silently downgrades `priority`/`type` on every re-import.**
`backend/app/api/capture.py:242-253`
Every other field in this merge is "fill blank only" (`COALESCE`). `priority` and
`task_type` are set unconditionally, and both default to `"medium"`/`"other"` when omitted
from the payload (rather than `None`). A task first imported as `priority: critical,
task_type: capa`, then re-imported later (e.g. to log a new work session on the same
`external_ref` — the module's own stated idempotency contract) with those fields simply
omitted, gets silently downgraded to medium/other. No error, no log. Silently losing a
CAPA classification on a routine re-import is a real data-integrity bug in a GxP system.

**H10. `POST /intake/extract` performs the identical capability as `/ai/task_extract` but skips the elevated-role gate the latter explicitly enforces.**
`backend/app/api/intake.py:217-250` vs. `backend/app/api/ai.py:116-128,375-378`
`ai.py`'s `FUNCTION_ROLES` restricts bulk task extraction to `ELEVATED_ROLES` "regardless of
the client." `intake.py`'s `extract_tasks` resolves the same Letta binding and does the same
thing, gated only by `require_password_set` — any authenticated `USER` role. A base operator
403'd by one endpoint gets the same capability through the other.

**H11. Pervasive missing UUID path-param validation on write paths — systemic 500s instead of 404s.**
`backend/app/api/tasks.py` (`update_task`, `add_progress`, `add_session`, `list_sessions`,
`delete_session`, `add_link`, `delete_link`, `add_dependency`, `delete_dependency`),
`backend/app/api/collab.py` (essentially every route — shared `_task_or_404` never validates
first), `backend/app/api/facility.py` (`update_room`, `create_batch`, `update_batch`).
The house idiom (`_uuid_or_422`/`_require_uuid`) is applied inconsistently — some sibling
endpoints in the same files are fixed, most aren't. `PATCH /tasks/not-a-uuid` and similar
calls 500 instead of 404, for any caller.

### Frontend — request-race / data-integrity bugs

**H12. `audit-view.js` and `report-view.js` have no "already loaded" guard — any global re-render (e.g. the language toggle) re-fetches from scratch and, for audit, silently discards paged-in history.**
`web/gf/report-view.js:17-22`, `web/gf/audit-view.js:60-65`
Every sibling view (`analytics-view.js`, `auditprep-view.js`, `facility-view.js`,
`approvals-view.js`, `execreport-view.js`, `myday-view.js`) guards against this. A GxP
auditor reviewing the audit trail who simply clicks the EN/MK toggle loses their pagination
position back to page 1 with no warning.

**H13. `qcgenealogy-view.js` has no request-sequence guard at all — a slow batch lookup can silently overwrite the currently-displayed batch's inherited-results panel with a different batch's data.**
`web/gf/qcgenealogy-view.js:18-29`
Every sibling QC master-detail view uses a sequence token to discard stale responses; this
one has none. A reviewer can end up looking at inherited ancestor-results feeding a CoQ
decision that don't actually belong to the batch shown in the search box.

**H14. `qclab-view.js` has no sequence guard and unconditionally overwrites the detail panel — the wrong lab's accreditation data can render under a different lab's row header.**
`web/gf/qclab-view.js:31-49`
Every sibling panel re-checks `st.sel === id` after the await; this one doesn't.

**H15. `worklog.js`'s modal-open handler is missing the exact stale-write guard present 300 lines later in the same file.**
`web/gf/worklog.js:37-47` vs. `:355-356`
Opening the worklog for Task A, closing it, and opening it for Task B before Task A's
`/sessions` fetch resolves can land Task A's logged hours under Task B's open modal — a user
could delete the wrong session entry believing it belongs to the task they're looking at.
Classic copy-paste drift: one function in the file got the fix, its sibling didn't.

**H16. `execreport-view.js`'s per-department cache invalidation is broken, not just racy — an expanded section can get stuck loading forever.**
`web/gf/execreport-view.js`
"Refresh" and date-change both reset the doc cache but not the "which sections are expanded"
state, and nothing re-fetches an already-open section after its cache entry is wiped. An
already-expanded department in the Executive Report shows a permanent loading spinner until
manually collapsed and reopened — deterministic, not theoretical.

**H17. Frontend shows "Generate COQ" to QP, but the backend 403s it — a genuine, ironic frontend/backend role-gate drift on a core release-adjacent action.**
`web/gf/qccoa-view.js:27,30` (`_COQ = ['ADMIN','QC_MGR','QP']`) vs. `backend/app/api/qc/common.py:15` (`_COQ_ROLES = (ADMIN, "QC_MGR")` — no QP).
The frontend's own comment claims "QP may also issue one" — the opposite of what the backend
enforces. A QP clicks the button the app shows them and gets a 403, on the action the CoQ
module itself describes as "an input to the QP release decision."

**H18. `qcspec-view.js` has no UI path to move a spec to SUPERSEDED — blocking the routine spec-versioning workflow the backend requires.**
`web/gf/qcspec-view.js:178-194`
The backend allows `ACTIVE → SUPERSEDED` and enforces one-ACTIVE-per-material. There is no
button anywhere to supersede the old version before activating a new one — a QC author
following the normal versioning flow hits a raw 409 with no in-app way to unblock it.

**H19. Water-test creation always defaults to `passed: true` with no way to enter the OOE (out-of-expectation) reason through the UI at all.**
`web/gf/qcleaves-view.js:34-42,94,154-157`
No pass/fail input exists on the create form; a failing result can only be flagged afterward
via a separate toggle, and even then there is no field anywhere to enter the mandatory
justification the render code displays a placeholder for. An analyst who forgets the extra
toggle step after a failed test leaves a GxP record silently reading PASS.

**H20. `qcgenealogy-view.js` hides Add/Delete-edge actions from OWNER, unlike every sibling QC view.**
`web/gf/qcgenealogy-view.js:12` — `_WRITERS` is missing `'OWNER'`, present in every other QC
view and in the backend's actual gate. One specific role is silently under-permissioned in
one specific view via copy-paste drift.

**H21. `audit-view.js`'s bare top-level `AL` translation helper is silently depended on by 154 call sites across three other files that load *earlier* in `index.html`, undocumented.**
`web/gf/audit-view.js:12` vs. `export.js`/`views.js`/`integrate.js`
The code's own comment says this global is for "collab.js/report-view.js only." In reality
it's relied on much more widely. It only works today because none of those call sites
execute at parse time. One missing/reordered `<script>` tag — or `audit-view.js` failing to
load — throws `ReferenceError` the first time a user opens Board/Timeline/Dashboard/Team/
Executive or exports data, likely aborting the render mid-way and leaving the panel stuck
empty. Latent, but a much wider blast radius than the documented dependency implies.

---

## MEDIUM

### Backend
- **RQS registration role-gating shown to roles the backend will reject** (`web/gf/qccustody-view.js:269-270`): the button is shown to all writers, but the backend restricts release-related RQS registration to QP only (excluding QC_MGR) and general registration to QC_MGR/QP/ADMIN (excluding OWNER/CEO/COO) — `backend/app/api/qc/custody.py:312-320`.
- **`reports.py`'s department scoping is plain equality**, missing the "personally owned / assigned / multi-department family" membership `tasks.py`'s own scope clause includes — a dept-scoped manager's weekly report/analytics/audit-prep numbers can under-count their own visible work (`backend/app/api/reports.py`).
- **`notifications.py`'s `/activity` and `/digest` silently restrict a department-less manager to only their own actions** — reproducing, in this one file, the exact "manager sees nothing" failure mode `app/deps.py`'s `dept_scope()` docstring says must never happen (`backend/app/api/notifications.py:125-205`).
- **`activity_window_sql` never counts comments, assignments, acknowledgments, or a rejected/cancelled handoff as "activity"** — a task discussed/assigned/acknowledged entirely within the reporting window but never status/progress/hour-touched won't appear in the weekly report (`backend/app/api/weekwindow.py`).
- **`documents.py`'s `patch_document` allows a full-content overwrite with no optimistic-concurrency guard**, unlike its own sibling `patch_section`, which was explicitly hardened against this exact lost-update class (`backend/app/api/documents.py:808-828` vs. `842-912`).
- **`qms.py`'s internal-proxy path segments are only length-checked**, not traversal-guarded, on 6 of 7 forwarding endpoints — the one sibling endpoint (`download()`) that *was* hardened against this exact risk shows the author knew about it (`backend/app/api/qms.py`).
- **`duescan.py` derives "is a department manager" via a `LIKE '%_MGR'` string pattern** instead of importing `roles.py`'s canonical role tuples — a silent-drift risk the codebase has already been bitten by twice per `roles.py`'s own docstring (`backend/app/duescan.py:34-36`).
- **`demo_org.py`'s seed phase isn't transactional** — a mid-seed exception (e.g. a future cast dict shape mismatch) leaves a half-seeded demo org and surfaces as a raw 500 to the visitor (`backend/app/demo_org.py:253-336`).
- **Aggregation CoQ's "primary source" fallback picks the alphabetically-last certificate number**, not the newest, despite the docstring claiming "fall back to the newest" (`backend/app/api/qc/coq_aggregation.py:119,464-472`).
- **Chain-of-custody continuity check has no advisory lock** — every comparable check-then-insert sequence elsewhere in the QC package takes one; two concurrent custody adds for the same sample can both pass the "must continue from the last custodian" check (`backend/app/api/qc/custody.py:486-517`).
- **DocEngine's §6A content-quality audit verdict is generated but never enforced** — `FIX` never blocks the build (`docengine/app/pipeline.py:192-199`).
- **DocEngine's background workflow task reference is discarded** (`asyncio.create_task(...)` with no strong reference held) — a long-running job can be silently GC'd mid-pipeline with no error recorded (`docengine/app/main.py:91`).
- **DocEngine's test suite has zero coverage of `run_workflow`'s error paths** — the verify-FAIL, LettaError, and cleanup-on-failure branches of the highest-risk code in the service are untested (`docengine/tests/`).
- **DocEngine health check reports liveness, not readiness** — DB/Letta connectivity is never re-verified after startup (`docengine/app/main.py:47-54`).
- **DocEngine's regulatory-check loop redundantly re-parses `fleet.yaml` and re-fetches the full agent/source list from Letta on every section** — up to 9× per job (`docengine/app/fleet.py:90-141`).
- **DocEngine hardcodes named individuals as function-default sign-off parameters**, directly contradicting the fleet's own stated rule that "personnel names are never hardcoded" (`docengine/engine/scripts/pp_report.py:349,401-423`).
- **6 tasks-DB tables** (`ai_agent_bindings`, `ai_pins`, `calendar_weeks`, `task_links`, `task_assignees`, `task_comments`) **lack the standard audit trigger with no documented rationale**, unlike every other exclusion in the schema, which explains itself inline. `task_assignees` is the most concrete gap — it's actively mutated via `collab.py` with zero tamper-evident trail for who-was-assigned/accepted.
- **`conftest.py::purge_org()` is missing 20 of 47 org-scoped tasks-DB tables** (essentially the entire QC LIMS surface) — every reused local test database accumulates orphaned rows across every test run.

### Frontend
- **`report-view.js`'s AI-insight loader has no staleness guard** — quickly switching weeks can display AI commentary for a different week than the stats shown above it.
- **`report-view.js`'s week-navigation drops (not queues) a click while a load is in-flight**, but the ref-date has already advanced — double-clicking "next week" can jump two weeks.
- **`analytics-view.js`'s range picker has no sequence guard** — clicking 4-weeks then 8-weeks quickly can leave the chart under-reporting history while the "8 weeks" button stays highlighted.
- **`notifications-view.js`'s 75s poll has no staleness guard against user actions** — clicking "mark done" right as a poll is in flight can resurrect the just-cleared notification.
- **`qcleaves-view.js` has no sequence guard and bleeds errors across tabs** — a Stability-tab error can render under the Water tab if the user switches quickly.
- **`qcoos-view.js` and `qclab-view.js` silently swallow a detail-fetch failure** with no retry affordance, unlike every sibling panel — the row is stuck on a loading skeleton forever.
- **`export.js`'s CSV/JSON export is stuck on the pre-v2 task schema** — no due date, type, reference code, tags, or archived flag; references a `deps` field that no longer exists.
- **`integrate.js`'s "Show archived" toggle has no request-sequence guard** — a race can leave the toggle showing "off" while archived rows remain in the list.
- **An in-tab 401-triggered relogin never resets search/department/tag filters or the search box** — on a shared/kiosk workstation, the next user to log in on the same tab silently inherits the previous user's filter state.
- **Several bilingual gaps**: modal footer Cancel/Save/Close buttons never localize; the header "Today" button is hardcoded English with a dead i18n key; the Assistant drawer title/placeholder never localize; Dashboard's empty-blockers state is hardcoded English while its sibling Executive Overview correctly translates the identical pattern three times over; session `classification` ("overtime"/"night"/etc.) renders untranslated even inside the Macedonian half of a translation call; AI Intake's priority/type dropdowns bypass the app's existing label helpers.
- **Service worker `clients.claim()` triggers a reload on every first-ever visit**, not just genuine updates — a brand-new user typing their username mid-install can get force-reloaded, losing what they typed.
- **`report-view.js`'s "days late" calculation uses a UTC-anchored `Date` parse**, inconsistent with every other date-only parse in the same review slice (which all anchor to local midnight) and inconsistent with `worklog.js`'s own explicit comment about avoiding this exact class of bug — under-reports lateness by up to a day for a UTC+1/+2 facility.
- **KPI-tile rendering is duplicated four times** (report/analytics/auditprep/execreport views) with no shared helper — a fix to one won't propagate.
- **~8 QC views hand-roll the same load/pick/retry CRUD-panel triplet independently** — the structural root cause of several of the race/retry findings above (H13, H14, plus the two swallowed-error findings): a fix applied to one copy doesn't propagate to its siblings.

---

## LOW / NIT

- `security.py`'s `create_access_token(days=0)` is treated the same as `days=None` due to a truthy check — a latent footgun, not currently triggered.
- `CORS_ORIGINS` isn't trimmed for whitespace after splitting on `,` — a space-separated config value silently produces an origin that never matches.
- `db.py`'s `init_pools()` doesn't clean up already-created pools if a later one fails.
- `duescan.py`'s admin-actor lookup filters `is_deleted` but not `is_active` — audit attribution can point at a deactivated account indefinitely.
- `config.py`'s `app_host` setting is defined but never read anywhere — dead config.
- Redundant `try/except: pass` wrapped *around* already-safe `safe_emit()` calls in 4 files/12 sites — currently dead code, but a silent-failure trap if anything above the call raises.
- `resolve_handoff` doesn't actually distinguish "reject" from "cancel" by actor.
- `ai.py`'s `_letta_message` swallows every failure mode with zero logging — an outage and a misconfiguration are operationally indistinguishable.
- `documents.py`/`qms.py` hardcode role-name literals instead of importing `app.roles`'s tuples.
- `capture.py` duplicates `weekwindow.ensure_week`'s upsert logic instead of importing it — a third copy also exists in `scripts/weekly_snapshot.py`.
- DocEngine: unreachable `pp_report.py` report-engine path whose only dependency (`matplotlib`/`numpy`) isn't even in `requirements.txt` — would ImportError the moment it's ever reached; malformed workflow/document ids 500 instead of 404; the Gotenberg PDF call has no failure wrapping, unlike every other external call in the same file; `build_json` is dead code; a couple of file handles aren't used via context managers in a now-persistent-process code path.
- Frontend: CSV export writes the task id unescaped/unquoted (the one field on the row that isn't); a handful of numeric fields interpolated without the house `GF.esc()` wrapper (not currently exploitable — all are server-typed/bounded — but inconsistent with the rest of the codebase); an unreachable, English-only duplicate login/change-password UI left in `integrate.js` (superseded by `entry.js` but would activate as a bilingual regression if the latter ever failed to load); global arrow-key week navigation stays live behind an open modal; a guaranteed double-render/flash-of-empty-shell on every boot with a saved session; one `onclick` string interpolates a raw id without escaping (server-issued, low risk).

---

## Dead code / cleanup (confirmed, not guessed)

- **`web-next/`** — confirmed genuinely unwired (not referenced by `docker-compose.yml`, any Dockerfile, or CI). Tracked footprint is **3.3MB**, not the 163MB the working directory shows (that's gitignored `node_modules`/build output from a local `npm install`, not repo bloat). Already on the team's own deferred-cleanup list in two prior audit docs — this just re-confirms it's still true.
- **`qc-lims-ao/`** — confirmed fully dead: zero imports anywhere in `backend/`/`docengine/`, not in any compose/Dockerfile/CI. Its schema/logic were natively rebuilt as this repo's own `qc_*` tables; the prototype itself was never deployed. Safe to consider removing outright (12MB tracked). Note: a previously-committed secrets file inside it (`qc-lims-ao/.a0proj/cookies.txt`) was already remediated on disk in an earlier commit but may still be recoverable from git history if that repo is ever made public — worth a deliberate look before any history rewrite, separate from this review.
- **`qms-creator/`** — **correction to the working assumption going in: this is NOT dead code.** It's unreferenced by *this repo's* compose/CI, but it's the source for `qms-api`, which is deployed out-of-band on the production host and is live, tested (`test_qms_proxy.py`), production infrastructure today. Don't touch it as part of any "clean up dead code" pass without also handling the live `qms-api` container.

---

## What's genuinely solid (so the above isn't read as "everything's broken")

- Migration/schema hygiene is strong: clean linear revision chains, real (non-stub) downgrades everywhere, no SQL-injection risk in any migration, CI already round-trips upgrade→downgrade and diffs against the checked-in schema files.
- Test coverage is unusually thorough for a system this size — every router has substantive, non-tautological tests; the QC package alone has 144 tests across its 86 endpoints.
- Most of the QC LIMS package's core guardrails (never-fabricate evaluation, advisory-lock-protected numbering, the cert-numbering/CoQ-numbering shared series, the genealogy cycle check, the eCoA supersession-chain walk) are correct and were specifically checked and found clean, not just assumed.
- The frontend's XSS posture is solid everywhere reviewed — every user-controlled string that reaches `innerHTML` goes through the shared escape helper first, including the markdown-lite AI-narrative renderer.
- The 401 recovery pipeline is a single, correctly-guarded choke point with no bypasses found anywhere across 38+ frontend files.
- DocEngine's actual security boundary (API-key constant-time compare, path-traversal guarding on output filenames, no SSRF surface) is solid — the problems are in content-integrity guarantees, not access control.

---

## Suggested fix order

1. **B1, B2** (DocEngine verify gate + HEADERDATA corruption) — these undermine the core
   safety claim of a service that stamps controlled pharmaceutical documents as PASS.
2. **H1–H3, H6, H7, H10** — auth/authorization-adjacent: the SECRET_KEY fail-open, the two
   missing second-person checks, and the intake role-gate bypass are the closest things to
   an actual compliance/security incident waiting to happen.
3. **H8, H9, H11** — the workflow-transition race, the capture priority/type downgrade, and
   the systemic UUID-validation gaps are correctness bugs with real GxP audit-trail
   consequences.
4. **H4, H5, H12–H21** — the remaining HIGHs, roughly in the order listed; several of the
   frontend ones (H13–H16, H20) share a root cause (no shared QC master-detail helper — see
   the MEDIUM note on duplicated CRUD-panel boilerplate) and could be fixed together by
   extracting that helper once rather than patching 5+ files individually.
5. **MEDIUM batch**, then **LOW/nit** as time allows.
6. **Dead-code cleanup** (`web-next/`, `qc-lims-ao/`) is low-risk and can happen any time —
   just leave `qms-creator/` alone per the correction above until its production disposition
   is handled deliberately.

Nothing in this document has been fixed yet. This is the audit; the remediation is a
separate, explicit next step.
