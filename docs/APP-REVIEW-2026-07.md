# GrowFlow / WWF — Comprehensive Application Review (2026-07-22)

Full-platform professional review at head `42450e7` (backend v77 / frontend v107 /
migration 0041, live on both stacks). Method: five independent read-only expert
reviews — backend architecture, application security, GxP/CSV data integrity,
frontend/UX, data layer & operations — run in parallel over the whole repo, plus
live surface checks against both running stacks (headers, TLS, latency,
unauthenticated exposure). Every finding below was verified against actual code
(file:line) or observed live; the two most serious GxP claims were independently
re-verified before publication. Nothing in this report is speculative.

---

## 1. Scorecard

| Dimension | Grade | Verdict in one line |
|---|---|---|
| Application security | **A–** | Mature: RLS + auth hardening + SQL/XSS discipline verified; held back by committed legacy credentials |
| Schema & migrations | **A–** | FORCE RLS on 51/51 tables, byte-diff drift gate, executed downgrade checks — best-in-class hygiene |
| Robustness engineering | **A–** | Advisory locks, second-person controls, idempotency, UUID guards, 458 real-Postgres tests |
| Testing | **B+** | Broad, RLS-real, near 1:1 router coverage; no coverage metric, no frontend unit tests, purge fixture drifted |
| Backend architecture | **B** | Excellent core (db.py/auth); debt concentrated in the 4,799-line `qc.py` and missing pagination |
| Frontend engineering | **B–** | Disciplined, well-commented, XSS-safe; full-re-render pattern and 10× duplicated view boilerplate |
| CI/CD | **B–** | Surprisingly complete pipeline incl. security scans; one flaky self-hosted runner + normalized merge-on-red |
| Operations | **B–** | Genuinely good backup design; **zero monitoring/alerting**; single-host SPOF; artisanal root-shell deploys |
| Accessibility | **D** | 8 aria attributes in the whole app; keyboard-unreachable nav; no modal focus traps; silent toasts |
| **GxP / CSV inspection readiness** | **D+** | Technical controls ≈B+, but scope statement disowns GxP status, no executed validation, issued-record freeze incomplete, e-signatures optional |
| **Overall engineering** | **B** | Unusually disciplined for its size; risks are enumerable and mostly cheap to fix |
| **Overall regulatory readiness** | **D+** | Set by the documentary layer, not the code — see §4 |

---

## 2. Live production-surface results (both stacks)

Verified live 2026-07-22:

- **Good:** TLS 1.3; HTTP→HTTPS 301; HSTS (1y); CSP with `frame-ancestors`,
  `object-src 'none'`, `base-uri`; `nosniff`; referrer-policy; gzip on; static
  etag caching; API endpoints return clean 401 unauthenticated and with bogus
  tokens; health ~0.6–0.8 s; SPA fallback on unknown routes.
- **Findings:**
  - `/docs` and `/openapi.json` are **publicly reachable on production** — the
    complete API schema of a GxP system is browsable unauthenticated. Gate or
    disable in production (FastAPI `docs_url=None` when `ENVIRONMENT=production`,
    or nginx auth).
  - `/tasks` returned **267 KB in 1.7 s** — live confirmation of the unbounded
    list-endpoint finding (§5.2).
  - `server: nginx/1.27.5` version disclosure (`server_tokens off`).
  - CSP requires `script-src 'unsafe-inline'` (inline handlers) — mitigated by
    `connect-src 'self'`, but blunts XSS defense-in-depth.
  - HSTS lacks `includeSubDomains`.

---

## 3. Critical & high findings (cross-dimension, ranked)

**F-1 · HIGH · Security — Live Google session cookies committed to the repo.**
`qc-lims-ao/.a0proj/cookies.txt` / `cookies.json` / `cookies header string.txt`
(git-tracked) contain a real Google `COMPASS` session cookie; `auth_url.txt`
exposes an OAuth client_id/redirect/code_challenge. Anyone with repo read access
can replay the session until it expires. **Action: `git rm`, gitignore, and
rotate/revoke the Google session — history retains the values, so treat the
credential as compromised.**

**F-2 · CRITICAL (GxP) — Issued certificates are not actually immutable.**
`update_coa` freezes only VOIDED/SUPERSEDED; an APPROVED or RELEASED
certificate's substantive fields (`decision`, dates, metadata, notes) remain
PATCH-editable by any writer, bypassing the mandated revise/supersede flow
(QCSOP 012 §6.6/§6.7). The audit trail records the change but the control is
absent. Same class: CLOSED OOS investigations are fully editable. **Action:
extend the content freeze to APPROVED/RELEASED (register fields excepted) and
to CLOSED OOS; compute overall disposition from results instead of hand-typing.**

**F-3 · CRITICAL (GxP) — Scope/validation documents contradict the system's GMP use.**
`docs/SCOPE.md` declares WWF "not a validated GxP system, not part of the QMS"
while the same backend issues CoQs feeding QP batch release and captures "Annex
11 e-signatures". No executed validation package exists (URS unapproved, no
signed IQ/OQ/PQ, no periodic-review SOP) with 25 real users in production. An
inspector cites this on day one. **Action: three-zone SCOPE rewrite declaring
the QC LIMS a GxP computerized system + execute and sign the validation file.**

**F-4 · CRITICAL (Ops) — No monitoring or alerting exists anywhere (verified absent).**
Nothing polls `/health`; no error tracking; no log aggregation; and no alert if
the daily backup loop or offsite rclone copy silently fails — failures print to
container stdout only. A dead backend or dead backup is discovered by a user, or
never. **Action (days of work, biggest single risk reduction): external uptime
check on `/health`, backup-freshness alert (>26 h ⇒ notify), and error tracking
(Sentry or email-on-exception).**

**F-5 · MAJOR (GxP) — E-signatures are optional; rendered CoQs can fabricate a signature block.**
Lifecycle transitions REVIEWED→APPROVED→RELEASED are role-gated PATCHes with no
re-authenticated signature (Annex 11 §14); worse, when no e-signature was
captured the CoQ render synthesizes Prepared/Reviewed/Approved rows from
roles-of-record — a printed GMP certificate showing signatory names for signing
acts never executed. **Action: make a re-authenticated signature a hard
precondition of APPROVED/RELEASED/CoQ-review; never render an uncaptured
signature block.**

**F-6 · MAJOR (GxP+Ops) — Audit-trail perimeter gaps.**
9 tables lack audit triggers — materially: `qc_document_files` (the ALCOA+
"Original" store), `events` (where §6.16 deviation events land — and `app_user`
holds UPDATE/DELETE on it), `task_comments`, `task_assignees`. Deviation emits
are additionally wrapped in silent `except: pass` (~40 sites), so "attempt
recorded as a deviation" is not guaranteed. `audit_log` itself has no
`created_at` index despite keyset-paginated DESC listing, and `/audit/verify`
is ADMIN-only so QA cannot self-verify chain integrity. **Action: one migration
adding the triggers + the index; a `safe_emit()` that logs failures; deviations
into an audited append-only table; open verify to QA roles.**

**F-7 · MAJOR (CI/Ops) — Merge-on-red-CI normalization + single flaky runner.**
A dozen+ PRs merged on "CI infra-red, local gate instead" (documented in
DEPLOY.md). The local gate is real, but the practice destroys CI signal —
genuine failures now look like infra noise. Everything runs on one self-hosted
runner on the production host. **Action: move infra-independent jobs to
GitHub-hosted runners so green is achievable again; require pasted local-gate
evidence for any red-run merge; move the runner off the prod host.**

**F-8 · MAJOR (Ops) — Single-host SPOF + untested two-DB restore.**
One VPS hosts prod, test stack, Letta, the CI runner, and the backup source;
only the encrypted offsite Drive copy survives host loss — and the current
two-database restore procedure has never been drilled (only the legacy v1
single-DB restore was ever executed). **Action: run the documented two-DB
restore drill on a second machine now, then monthly; write the from-scratch
host-rebuild runbook.**

---

## 4. GxP/CSV assessment (grade D+ — the review's headline)

The paradox: the *technical* controls would grade ≈B+ — deterministic
server-side conformance (`complies` computed, never typed; lab verdicts
reference-only with mismatch surfacing; Ph. Eur. totals derived, never
transcribed), genuine second-person enforcement (reviewer ≠ analyst ≠ any
result-enterer; CoQ compiler ≠ approver), dual hash-chained tamper-evident
audit trails with a real QA review UI, SHA-256 original custody with re-hash on
download, append-only OOS register, and disciplined change control (39 dated
DEPLOY.md entries, test-stack-first promotion). Spot-checks of the QCSOP-012
adherence doc's claims against code: 2 of 3 fully true, 1 partial (the promised
gap-deviation emit is report-only).

But inspection readiness is set by the weakest documentary layer:
F-2/F-3/F-5/F-6 above, plus — closed-record mutability (OOS), hard-deletable
genealogy edges, user hard-purge eroding attributability on historical records,
no MFA for signing roles, no audit-trail-review or retention SOP, and a hash
chain with no external anchor (a DB admin could rewrite and recompute it).

**Top 5 before facing an inspector:** (1) SCOPE rewrite; (2) executed/signed
validation file; (3) APPROVED/RELEASED + CLOSED-OOS freezes; (4) mandatory
re-authenticated signatures + remove the fabricated signature fallback;
(5) close the audit perimeter (triggers, transactional deviations, QA-accessible
verify, retention + periodic-review SOPs, MFA for signers).

---

## 5. Engineering findings (selected majors)

### 5.1 Backend architecture (B)
- **`qc.py` monolith:** 4,799 lines, 86 endpoints, all domain logic in HTTP
  handlers, no service layer — the single largest maintainability risk.
  Remediation: split into a `qc/` sub-router package + extract state-machine/
  compilation logic into plain async functions.
- **Event-loop blocking:** bcrypt runs synchronously in async handlers
  (~100–300 ms per login, doubled by the timing-safety dummy), and WeasyPrint
  PDF renders (multi-second) run inline — each stalls every concurrent request.
  Fix: `asyncio.to_thread` (two lines per site).
- **No pagination** on ~27 of 30 list endpoints (live-measured: 267 KB `/tasks`);
  GxP data only accumulates. Fix: bounded `limit/offset` defaults, pattern
  already exists in `audit.py`.
- No API versioning, zero `response_model` declarations; constraint violations
  matched by string; base64-in-JSON file uploads into bytea (scaling debt).

### 5.2 Frontend (B–; accessibility D)
- **Accessibility:** 8 aria attributes total; nav/dept/card controls are
  `<div onclick>` (keyboard-unreachable); modals lack `role="dialog"`/focus
  trap/restore; toasts not `aria-live` (the save confirmation is invisible to
  screen readers); `--ink-4` on `--bg` ≈2.5:1 contrast. 1–2 days of work for a
  step-change; also an audit-readiness argument.
- **`prompt()` for GxP reasons** (void/revise) with three different min-length
  rules across sibling actions; deserves a shared `GF.reasonDialog` on the
  existing modal system.
- **Full `GF.render.all()` per search keystroke** through a ~25-layer
  view-registration wrapping chain; caret jumps on mid-string edits; breaks
  Cyrillic IME composition. Debounce + scoped re-render + a 3-line request-
  sequence token (stale-response race).
- ~1,200 LOC of duplicated registry-view boilerplate across 10 `qc*` views —
  one factory would collapse it. Google-Fonts `@import` breaks the default
  skin offline (self-host like Comfortaa already is). Nav shows ~30 items to
  managers; the Cmd-K palette exists but is undiscoverable.
- Genuinely strong: near-total bilingual coverage with good MK GxP terminology,
  consistent `GF.esc` XSS hygiene, optimistic writes with rollback, real SW
  versioning discipline, state machines mirrored so illegal transitions are
  never offered.

### 5.3 Data layer & testing (A–/B+)
- 51/51 tables FORCE RLS with real per-table policy semantics; enum-as-CHECK
  throughout; partial unique indexes encoding business invariants; CI byte-diff
  drift gate + executed downgrade-to-base check.
- `purge_org` test fixture drifted: purges 24 of 47 tables — derive the list
  from catalog metadata (same disease as the 7 one-off SQL scripts that bypass
  alembic entirely).
- `batch_id` is denormalized free text across ~10 QC tables with no master
  batch table — typos silently fork genealogy.
- No coverage metric or gate; no Python lint/type-check in CI; no frontend unit
  tests (Playwright e2e is real, 13 specs).
- Capacity is honestly sized for 25 users (single worker ↔ in-process rate
  limiter is consistent but a landmine for whoever adds `--workers`); the
  audit-trigger advisory lock serializes all writes — fine now, the eventual
  throughput ceiling; `audit_log` grows unbounded by design with no archival
  plan.

---

## 6. What is genuinely excellent (keep doing this)

1. The RLS/dual-pool/auth core (`db.py`, `deps.py`, `security.py`) — verified
   production-grade, with NOBYPASSRLS request role and transaction-scoped GUCs.
2. Comment discipline — nearly every non-obvious decision carries its rationale,
   often with an SOP citation; rare at any scale.
3. Migration hygiene — raw SQL, symmetric downgrades, byte-diff drift gate.
4. Backup design — integrity-checked dumps, rotation-skip-on-failure,
   copy-never-sync encrypted offsite, honest residual-risk documentation.
5. GxP data-truthfulness in code — verdicts computed never typed, unknowns stay
   null, derived totals computed, second-person rules enforced structurally.
6. DEPLOY.md as an append-only ops journal with per-release rollback recipes.

---

## 7. Prioritized remediation roadmap

**P0 — this week (each ≤1 day):**
1. Remove + rotate the committed Google credentials (F-1).
2. Freeze APPROVED/RELEASED certificate content + CLOSED OOS records (F-2).
3. Baseline monitoring: uptime check on `/health`, backup-freshness alert,
   error tracking (F-4).
4. Gate `/docs` + `/openapi.json` in production; `server_tokens off`;
   HSTS `includeSubDomains` (§2).
5. Migration: audit triggers on `qc_document_files`/`events`/`task_comments`/
   `task_assignees` + `audit_log(created_at)` index; revoke UPDATE/DELETE on
   `events` from `app_user` (F-6).

**P1 — this month:**
6. Mandatory re-authenticated e-signatures at APPROVED/RELEASED/CoQ-review;
   remove the fabricated CoQ signature fallback (F-5).
7. SCOPE.md three-zone rewrite + begin executing the validation file (F-3).
8. Pagination defaults on list endpoints; `asyncio.to_thread` for bcrypt +
   WeasyPrint; `safe_emit()` with logging (§5.1).
9. Accessibility pass (buttonized nav, modal focus trap, `aria-live` toasts,
   contrast) + shared `GF.reasonDialog` replacing `prompt()` (§5.2).
10. CI de-flake: split hosted-runner jobs, end merge-on-red; run the two-DB
    restore drill; regenerate `purge_org` from catalog (F-7/F-8).

**P2 — this quarter:**
11. `qc.py` split + service-layer extraction; registry-view frontend factory.
12. Deviations as an audited append-only table; genealogy soft-retirement;
    OOS-ack recipient binding; checklist author≠decider.
13. MFA for signing roles; audit-chain external anchoring; retention +
    periodic audit-trail-review SOPs.
14. `qc_batches` master table; API versioning + response models before any
    external integration; self-hosted fonts + CSP tightening; IA cleanup
    (QC LIMS hub / collapsible nav groups).

---

*Review artifacts: five reviewer reports (architecture, security, GxP, frontend,
data/ops) synthesized here; live checks executed against
wwf-mass.srv1231216.hstgr.cloud and wwf.srv1231216.hstgr.cloud on 2026-07-22.*
