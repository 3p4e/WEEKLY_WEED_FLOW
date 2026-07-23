# GrowFlow / WWF — In-Depth Code Review & Full Examination (2026-07-22)

Hands-on deep review at head `42450e7` (backend v77 / frontend v107 / migration
0041, live on both stacks). This is the *execution* pass that follows the graded
professional review (`docs/APP-REVIEW-2026-07.md`): real tool output, live
dynamic probing, and five parallel adversarial bug-hunt reviews of the
highest-risk modules — every finding tagged by how it was verified.

**Verification legend:**
`✅ VERIFIED` — I independently confirmed it by reading the current code or by a
live request against the running stack.
`◆ TRACED` — a reviewer traced it end-to-end with file:line; high confidence, I
did not re-verify independently.
`✗ DISPROVEN` — claimed by a reviewer, checked, and found not to hold against
current code (kept here for transparency).

---

## 1. Examination battery — tool & live results (facts, not opinion)

| Examination | Tool / method | Result |
|---|---|---|
| Dependency CVEs | `pip-audit` (runtime + dev) | **0 known vulnerabilities** |
| Security static | `bandit -ll -ii` | **0 high**, 0 medium/high-confidence; 69 medium are all B608 (f-string SQL) at **low confidence** — verified false positives (whitelisted identifiers + bound `$n`) |
| Lint (real bugs) | `ruff --select F` | 2 unused imports (`ai.py:20`, `capture.py:26`); nothing else |
| Dead code | `vulture --min-confidence 80` | **0** |
| Complexity | `radon cc/mi` | avg **B (5.68)**; hotspots `qc.py`, `documents.py` MI **0.00**; F-rated fns: `_coq_markdown` (58), `generate_coq` (57), `_compile_coq_tx` (56), `update_coa` (47) |
| Frontend syntax | `node --check` (×51) | all parse clean |
| Frontend bug-rules | `eslint` (dupe-keys/unreachable/isnan/…) | **0 errors**, 42 warnings (all empty `catch{}`) |
| Committed secrets | `git grep` credential patterns | **1 CRITICAL** (see C-SEC-1); primary trees clean, no tracked non-example `.env` |
| Test coverage | `pytest --cov=app` (458 tests, fresh 2-DB cluster) | **89% lines** (5163/5801 stmts); lowest: qms 80%, notifications 80%, ai 83%, facility 84% |
| Live TLS/headers | `curl` both stacks | TLS1.3, HSTS, CSP, nosniff, gzip, http→301; `/docs`+`/openapi.json` **public on prod**; nginx version disclosed |
| Live auth/limits | `curl` fuzz | rate-limit fires **8→429**; all methods **405**; `alg=none` JWT **rejected**; malformed/oversized/injection bodies → clean 4xx |
| Live fuzz for 500s | `curl` negative | **7 endpoints 500 on malformed UUID** (H7); `year=` query unbounded (LOW) |

Mechanically the codebase is exceptionally clean — the defects below are
**logic/GxP-control** issues that no linter or scanner detects, which is exactly
why the adversarial reviews were run.

---

## 2. CRITICAL

**C-GxP-1 · ✅ VERIFIED (live + code) · Issued certificates are freely
PATCH-editable, including the PASS/FAIL `decision`.**
`qc.py` `update_coa` (~line 1119): the immutability freeze fires only for
`status in ("VOIDED","SUPERSEDED")`. An **APPROVED** or **RELEASED** certificate's
substantive fields — `decision`, all dates, lab, sampling location, metadata,
notes, language — are writable by any `_WRITERS` role (not even QP), bypassing
the mandated revise/supersede flow. *Repro:* drive a cert to RELEASED with
`decision=PASS`, generate the CoQ .docx ("Approved for Release"), then
`PATCH {"decision":"FAIL"}` → 200; the stored record and the issued document now
contradict each other with no supersession trail. *Fix:* freeze content at
APPROVED/RELEASED (register fields excepted); route changes through `/revise`.

**C-SEC-1 · ✅ VERIFIED · A complete Google + OpenAI session-cookie jar is
committed to the repo.** `qc-lims-ao/.a0proj/cookies.txt` (248 KB) and
`cookies.json` (440 KB), introduced in commit `50f9fc3`, contain a full Google
account cookie jar (`__Secure-1PSID`, `__Secure-3PSID`, `SAPISID`, `SID`, `HSID`,
`SSID`) plus OpenAI/next-auth session cookies — not a single cookie. Anyone with
repo read access can hijack the Google account until those sessions are revoked.
The tree is **staging-only** (not referenced by any compose/Dockerfile, never
deployed) and **not in `.gitignore`**. *Fix:* `git rm`, gitignore `.a0proj/`,
and **revoke the Google + OpenAI sessions** — git history retains the values.

---

## 3. HIGH

**H1 · ✅ VERIFIED (code) · eCoA promotion skips the QCT-018 review checklist
(§6.3.2).** `promote_coa_document` (qc.py:3186) gates only on
`status in ('EXTRACTED','REVIEWED')` + `promoted_coa_id IS NULL` — **no checklist
check**. The §6.3.2 "eCoA fed forward only after ACCEPTED review" gate exists
*only* at CoQ compile. So an external CoA whose checklist is PENDING, absent, or
explicitly **REJECTED** can be promoted into a DRAFT→…→RELEASED certificate that
is usable standalone and via `get_inherited_results`. `decide_checklist(REJECTED)`
sets no document state despite its docstring. *Fix:* require an ACCEPTED
`qc_ecoa_checklist` in `promote` (and in single-cert `generate_coq`).

**H2 · ✅ VERIFIED (code) · Sample batch-release has no open-OOS / all-comply
gate.** `update_sample` (qc.py:540-548) gates `APPROVED→RELEASED` on the QP role
only. A failing result auto-quarantines the sample, but
`QUARANTINE→IN_TEST→TESTED→REVIEWED→APPROVED→RELEASED` is fully reachable with an
OOS still OPEN — the exact condition every CoQ path blocks. There is also **no
analyst≠reviewer** second-person check on `TESTED→REVIEWED` (certificates have
one). *Fix:* assert no non-CLOSED OOS for the batch before RELEASED; add the
second-person check.

**H3 · ✅ VERIFIED (code) · An OOS can be CLOSED hollow, unlocking
certification.** `update_oos` (qc.py:2247) on `CLOSED` stamps `closed_by`/
`qp_approved_by` but never requires `disposition`, `root_cause_description`, or
`impact_assessment` (all optional/nullable). Because every downstream gate merely
counts `status<>'CLOSED'`, an empty-body close of a real OOS immediately unlocks
CoQ compile/approve/render for the batch. *Fix:* require a non-null disposition
(+ Phase-II fields when closing from PHASE_II) on close.

**H4 · ✅ VERIFIED (code) · Workflow sign-off notifications are silently
dropped — a whole feature never fires.** `workflow_transition` (tasks.py:966)
emits with `reason="workflow"`, but `notifications_reason_check`
(schema.tasks.sql:282) permits only
`assigned|mentioned|comment|status|due|report|capa_stuck|validation_stuck`. Each
per-recipient insert violates the CHECK and is swallowed by `emit()`'s
savepoint-wrapped `except: pass`. The SUMA v2 approval workflow's core "you have
something to approve" alert reaches **no one's inbox**; only the activity feed
records it. *Fix:* add `'workflow'` to the CHECK + `_REASONS`, or emit `'status'`.

**H5 · ✅ VERIFIED (code) · Rendered CoQ fabricates a signature block.**
`_coq_markdown` (qc.py:1670): when no `qc_signatures` rows exist, the "Signatures"
table is filled from `analyst_id/reviewer_id/approver_id` — ids stamped
automatically on lifecycle transitions **with no re-authentication**. The issued
GMP document asserts Prepared/Reviewed/Approved signatures that were never
executed. No transition requires an e-signature; `/sign` is optional. *Fix:*
require captured signatures before rendering the table, or print an explicit
"audit-trail only, not e-signed" statement.

**H6 · ◆ TRACED · eCoA auto-map ignores the document's specification → results
graded against a *different* spec's limits reach the certificate.** `mapped_by_label`
(qc.py:3011) is built from MAPPED placeholders **org-wide, no spec filter**, and
takes precedence over the same-spec name map. A label once mapped to spec A's
parameter auto-maps on a spec-B document, grades the value against spec A's
limits, and `promote` inserts it straight into `qc_results` — bypassing the
same-spec guard the manual `add_result` path enforces. The verify loop reports
VERIFIED (result and extraction agree), so the wrong `complies` is never
surfaced. *Fix:* only apply a label mapping whose parameter's `spec_id` matches
the document's.

**H7 · ✅ VERIFIED (live) · 7+ endpoints return HTTP 500 on a malformed UUID.**
Missing `_uuid_or_404`/`_uuid_or_422` guards. Live-confirmed 500s:
`PATCH /qc/water-tests/{id}`, `PATCH /qc/stability-studies/{id}`,
`POST /qc/certificates/{id}/verify`, `POST /qc/coa-documents/{id}/extractions`,
`POST /qc/coa-qa` (body `document_id`), `GET …/verifications`, `GET …/chunks`
(agent also flags `update_transport`, `update_placeholder`, `submit_extractions`,
`index_chunks`, `list_chunks`). A garbage id is bound to a `uuid` column →
asyncpg `InvalidTextRepresentation` → 500. *Fix:* add the guard at each entry
(used correctly 73× elsewhere).

---

## 4. MEDIUM

**M1 · ◆ TRACED · Cross-department task disclosure via the `dependency_advisor`
AI function.** `ai.py` `invoke`→`_family_context` (`:339-382`) loads a task by the
caller-supplied **body** `context.task_id` under an org-wide elevated RLS session
with **no `_assert_scope_visible`**. The structural guard test keys on `{task_id}`
*path* params, so a body-param route slipped through. A dept-scoped manager can
read another department's task family via the agent (only when an AI binding
exists). *Fix:* call `_assert_scope_visible` before `_family_context`.

**M2 · ◆ TRACED · QMS proxy `download/{path:path}` defeats its own allowlist.**
`qms.py:124` forwards `{path:path}` (slashes allowed, only length-capped) to
`/api/download/{path}`; httpx RFC-3986 joining collapses `../`, so
`GET /qms/download/../../api/workflows` reaches arbitrary internal `qms-api`
endpoints the allowlist exists to block (authenticated internal-SSRF). *Fix:*
reject `..`/leading-`/` before forwarding.

**M3 · ◆ TRACED / SUSPECTED · Arbitrary Letta agent binding.** `set_binding`
(ai.py:196) stores any `letta_agent_id` with no org-ownership check; `invoke`
POSTs to it with the shared platform key; `GET /ai/agents` lists every agent on
the instance. On a shared Letta, a tenant ADMIN — or the demo-org ADMIN handed to
an anonymous `/demo/start` visitor — can bind and invoke another tenant's agent.
*Fix:* validate the agent id against an org-owned registry; drop AI-binding from
the demo role.

**M4 · ◆ TRACED · `weekly_snapshot.py` window is UTC-anchored, not
facility-local.** `gather()` (`:331-381`) compares `created_at >= $::date` with
**no `AT TIME ZONE`**, unlike `reports.py`/`weekwindow.py` — the very drift those
carry a comment warning about. A task worked Friday 00:30 Europe/Skopje is
excluded from that week; the **archived/AI report and the live `/reports/weekly`
screen list different task sets for the same week**. *Fix:* apply
`activity_window_sql`/`AT TIME ZONE $tz` in `gather()`.

**M5 · ◆ TRACED · `external_ref` duplicate → 500, idempotency broken.**
`tasks.py` create (`:416`) / patch (`:624`) catch `_FK_ERRORS` but **not
`UniqueViolationError`**, so a repeated `external_ref` (at-least-once integration
retry) raises an uncaught 500 despite the unique index signalling idempotency was
intended (`capture.py` handles this correctly). *Fix:* map to 409 or `ON
CONFLICT … DO UPDATE` + re-select.

**M6 · ✅ VERIFIED (code) · Audit `/verify` checks only pointer linkage, never
recomputes `entry_hash`.** `_CHAIN_SQL` (audit.py:145) tests `prev_hash <>
lag(entry_hash)` only. It never re-derives the row hash, so an in-place edit of
`new_values`/`old_values` that leaves the hash columns intact passes, and
oldest-row (head) truncation is missed (the new first row's dangling `prev_hash`
is filtered out). Middle deletions *are* caught. The append-only INSERT-only
policy + advisory lock block app-level tampering, so residual risk is a
BYPASSRLS/DBA edit — precisely the threat a hash chain exists to detect. *Fix:*
recompute each row's hash in SQL and compare; anchor row 1 to a genesis constant.

**M7 · ◆ TRACED · Audit list pagination drops rows at page boundaries.**
`audit.py:113` keysets on `created_at < before` (strict) with no unique
tiebreaker; every row from one operation shares the same transaction-stable
`created_at`, so a boundary inside such a cluster permanently omits the rest.
*Fix:* composite `(created_at, source, id)` keyset.

**M8 · ◆ TRACED · Cyrillic filename → 500 on CoA original download.**
`download_document_file` (qc.py:2630) puts the raw filename in
`Content-Disposition: filename="…"`; Starlette latin-1-encodes headers, so any
Cyrillic character (routine here) raises `UnicodeEncodeError` → 500, making the
original CoA undownloadable. *Fix:* RFC 5987 `filename*=UTF-8''…` + ASCII
fallback.

**M9 · ◆ TRACED · OOS notification ack has no recipient authorization and no
acknowledger attribution.** `ack_oos_notification` (qc.py:2335) updates
`acknowledged=true` for any writer, never checks the caller is in `recipients`,
and the table has no `acknowledged_by` column — a forgeable GxP acknowledgement
with no record of who clicked. *Fix:* enforce recipient membership; add and stamp
`acknowledged_by_id`.

**M10 · ◆ TRACED (frontend) · Stale-response race in every QC detail panel and
list.** Each `qc*Pick(id)`/`qc*Status(v)` (`qccoa-view.js:93,78`; and qcecoa/
qcoos/qccustody/qcsample/qcspec) assigns `st.detail`/`st.rows = await …` with no
post-await selection/sequence guard. Click certificate A then B: if A's response
lands last, the panel shows **A's number + results while row B is highlighted** —
a wrong-record-under-wrong-identity hazard on a QP release surface. *Fix:* a
per-load monotonic token; ignore non-latest responses.

---

## 5. LOW / MINOR (verified or traced; batch these)

- **Batch-release genealogy edges are hard-deletable** by any writer, no
  soft-delete/guard, even feeding a released cert's inherited-results (qc.py:2697).
- **Leaf state machines have no transition guard** — `CLOSED→IN_PROGRESS`
  (stability), `received→draft` (transport) accepted; `qc_water_tests.passed` is a
  client-supplied bool with no grading of `parameters` vs limits (qc.py:4026/4091/4135).
- **`revise_certificate` drops `lab_verdict`** from carried-forward results, losing
  the §6.3.2 reconciliation flag after a revise (qc.py:1284).
- **`upload_coa_original` decodes base64 before the size cap** — `content_b64` has
  no `max_length`, so a huge body is materialized before the 20 MB check (qc.py:2554).
- **Chain-of-custody append-only is not DB-enforced** (policy has no `FOR` clause →
  in-org UPDATE/DELETE allowed; safe only because no route exposes them) and
  `add_custody` doesn't check from→to continuity (qc.py:3878; mig 0025).
- **Genealogy cycle check + dependency cycle check are TOCTOU** — concurrent
  inserts can each pass and together close a loop (qc.py:2676, tasks.py:831).
- **`patch_section` lost-update** — read-modify-write of the whole content jsonb
  with no `FOR UPDATE`; concurrent section approvals clobber (documents.py:851).
- **`assign()` masks all DB errors as 400** and leaks the exception class name
  (collab.py:173).
- **Recurrence materializes next instance with `week_id=NULL`** — resolves the week
  by a non-Monday `starts_on` and doesn't upsert like everywhere else (tasks.py:521);
  reopen+re-complete can spawn an extra instance (`:635`).
- **Weekly-report "overdue" counts not-yet-due tasks** for a mid-week `ref_date`
  (reports.py:151).
- **`POST /ai/{fn}` accepts unbounded `input`** (no `max_length`) — LLM cost/DoS
  (ai.py:135).
- **Login limiter keyed on the typed identifier**, not the resolved account — an
  attacker knowing both username and email multiplies the per-account cap
  (auth.py:143).
- **`export_range.pdf` 500-instead-of-4xx** on non-numeric `days` / malformed
  `start` in client `content` (documents.py:979).
- **Locked-document existence oracle** — `patch_section` distinguishes
  locked-vs-missing before the scope guard (documents.py:854).
- **`/qc/register/gaps?year=` unbounded** — accepts `-1` / `999999999999` (200/empty);
  no `ge/le` (live-confirmed).
- **Frontend:** revise-reason validation disagrees with backend (prompt says min 5,
  code checks only non-empty → raw 422 leaks; qccoa-view.js:168); weekly-report
  status chip shows the raw enum code not a label (report-view.js:316); auth screens
  + server error toasts are English-only for MK users; modal close doesn't restore
  focus (core.js:445); SW `skipWaiting`+`claim` can mix shell versions mid-session
  and atomic `addAll` fails install on one 404.
- **Ph. Eur. 3028 derived total** has no guard that component_a=neutral /
  component_b=acid — a backwards assignment silently miscomputes (qc.py:290, advisory).
- **No approver≠reviewer separation** on the certificate lifecycle — one non-analyst
  QP can review+approve+release the same cert (confirm against SOP; qc.py:1192).

---

## 6. Disproven / corrected during verification

**✗ Audit hash-chain "unlocked read-then-insert race" — DOES NOT hold.** A
reviewer flagged `fn_audit_row` as lacking serialization (chain forks under
concurrency). The **current** function (schema.tasks.sql, deployed) holds
`PERFORM pg_advisory_xact_lock(4019283746)` before the tail read — "H1: serialize
tail read; prevents concurrent hash-chain forks" (added in a later migration; the
reviewer read the `0001` baseline). No fork race exists. *(The separate M6 —
verify checks linkage not content — is real and distinct.)*

---

## 7. What the deep pass confirms is genuinely solid

- **No cross-organization isolation hole** — every BYPASSRLS admin-pool query
  filters `org_id` or keys on the caller's own id; RLS + NOBYPASSRLS request role
  hold; cross-org id probes return 404 not data (independently verified).
- **SQL injection: none** — every dynamic clause is whitelisted identifiers + bound
  `$n`; the 69 bandit B608 hits are all false positives.
- **Frontend XSS: none slipped** — every server-string sink (`void_reason`,
  `coa_number`, lab names, notes, comments, AI output) passes through `GF.esc`;
  `aiHtml` escapes-first then whitelists.
- **Live runtime hardening works** — rate-limit fires at the documented threshold,
  method discipline (405), `alg=none` JWT rejected, no unexpected 500s beyond H7.
- **Numbering, compile atomicity, TOCTOU stamping, second-person cert review,
  advisory-locked mint, dept-scope guard coverage (bar M1), division-by-zero
  guards, scheduler durability, PDF SSRF mitigation** — all verified correct.
- **Dependencies, dead code, lint** — effectively spotless.

---

## 8. Fix roadmap (by risk × effort)

**P0 — now (each ≤1 day):**
1. C-SEC-1: `git rm` the cookie jar, gitignore, **revoke** Google + OpenAI sessions.
2. C-GxP-1: freeze APPROVED/RELEASED cert content (+ CLOSED OOS, H3) to
   register-fields-only.
3. H7: add the missing UUID guards (11 endpoints) — trivial, kills the 500 class.
4. H4: add `'workflow'` to the notification reason CHECK — restores a dead feature.

**P1 — this month:**
5. H1 promote checklist gate + H6 spec-scoped auto-map (both let un-vetted external
   data become certificates).
6. H2 sample-release OOS gate + second-person; H5 e-signature preconditions /
   remove fabricated block.
7. M1 AI scope guard; M2 proxy traversal reject; M6 hash-recompute verify; M8
   RFC-5987 filename; M4 snapshot timezone; M5 external_ref idempotency; M9 ack
   authorization.
8. M10 frontend request-sequence tokens across QC views.

**P2 — this quarter:**
9. The LOW batch (transition guards, cycle-check locks, patch_section FOR UPDATE,
   base64 cap, custody append-only policy, unbounded inputs, i18n, focus restore).
10. `safe_emit()` with logging (kills the silent-swallow class behind H4);
    `qc.py` split (the MI-0.00 monolith behind most GxP findings); coverage gate.

---

*Method: `pip-audit`/`bandit`/`ruff`/`vulture`/`radon`/`eslint`/`node --check`
+ `pytest --cov` on a fresh two-DB PG16 cluster; live `curl` probing of both
production stacks; five parallel adversarial module reviews (QC lifecycle,
auth/RLS, TMS, facility/custody/audit, frontend). All ✅ items re-verified against
current code or live requests before publication.*

---

## 9. Remediation status (2026-07-23)

The P0→P2 roadmap from §8 was executed on branch
`claude/weekly-read-flow-setup-yft7if` (commits `2e713aa`, `a7dd839`, and the P2
follow-up). Gate for each batch: `schema.tasks.sql` drift-clean, alembic up/down
clean, full pytest on a fresh PG16 two-DB cluster, `node --check` on changed views.

**P0 — DONE** (`2e713aa` / `ca9b588` / `b0bb79e`): C-SEC-1 (cookie jar removed +
gitignored — account-side session revocation remains a manual owner action),
C-GxP-1 + H3 (issued-cert set-once freeze + CLOSED-OOS disposition gate), H7 (11
UUID guards), H4 (mig 0042 `workflow` reason + custody append-only policy).

**P1 — DONE** (`a7dd839`): H1 (promote requires ACCEPTED §6.3.2 checklist;
REJECTED voids the doc; generate_coq defense-in-depth), H6 (spec-scoped eCoA
auto-map), H2 (sample second-person TESTED→REVIEWED + batch-release OOS gate, mig
0042 `tested_by`/`reviewed_by`), H5 (honest CoQ signature block), M1 (AI scope +
uuid guard), M2 (qms proxy traversal reject), M4 (snapshot AT TIME ZONE), M5
(external_ref → 409), M6 (audit `/verify` hash recompute + head anchor), M8
(RFC-5987 filename), M9 (OOS-ack recipient membership + `acknowledged_by_id`).
M10 frontend QC-view races were fixed in `2e713aa`.

**P2 — PARTIAL (this batch):** `safe_emit()` with logging (kills the
silent-swallow class behind H4; swept across qc/tasks/collab/documents/facility/
duescan); `/ai/{fn}` input cap; `/qc/register/gaps` year bounds; base64 size cap
before decode; `revise_certificate` carries `lab_verdict`; `patch_section` FOR
UPDATE + scope-guard-before-locked-oracle; frontend revise-reason min-5 +
report status-chip label + modal focus restore.

**P2 — DEFERRED (tracked, not yet done), with rationale:**
- `qc.py` monolith split — explicitly its own reviewed refactor (roadmap §10).
- Leaf transition guards (stability/transport) + water `passed` server-grading —
  the latter needs a limit model for the free-form water jsonb params.
- Genealogy/dependency cycle checks are TOCTOU (advisory-lock fix) + genealogy
  edge delete guard + custody from→to continuity.
- Login limiter resolved-account key; `assign()` 400-masking; `export_range.pdf`
  4xx validation; recurrence `week_id` upsert; weekly-report mid-week overdue.
- Full i18n of auth screens / error toasts; SW `skipWaiting`+`claim` version-mix.
- **Owner/SOP input needed:** approver≠reviewer separation on the certificate
  lifecycle ("confirm against SOP", §5); Ph. Eur. 3028 component-order guard is
  advisory (the app fixes A=neutral/B=acid at spec authoring).

**Deploy:** none of the above is deployed yet — both live stacks remain at their
prior images. Deployment (migration 0042 + backend + frontend to wwf_mass and, on
the owner's go, production) is a separate owner-gated step.
