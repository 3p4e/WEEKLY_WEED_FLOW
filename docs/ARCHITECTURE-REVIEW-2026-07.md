# WWF — Critical Architecture & Compliance Review

**Date:** 2026-07-03 · **Scope:** entire system as deployed at wwf.srv1231216.hstgr.cloud
(purpose, backend, frontend, AI layer, data/server/connectivity, database, eGMP posture,
and a comparison against modern task-management platforms).
**Stance:** deliberately adversarial. Strengths are stated once; weaknesses get the ink.

---

## 1. Purpose & scope — what this system actually is

WWF is a **single-tenant-in-practice, org-scoped weekly task tracker** for a GMP
medical-cannabis facility (cultivation / QC / QA), with an AI layer that turns the week's
task activity into an org rollup report, per-person reports, and a next-week plan on a
Fri→Thu work-week cycle (submission Thursday 14:00 Europe/Skopje).

That purpose is coherent and the core loop now works end-to-end. The honest framing,
however, is that WWF sits **between two stools**:

- It is *more* than a to-do app: hash-chained audit log, RLS multi-tenancy, forced
  password rotation, AI reporting with RAG memory.
- It is *less* than what its own content demands: the tasks it tracks are CAPAs, SOP
  authoring, validation programmes, and a GMP submission package to MALMED — i.e.
  **GMP-relevant records are being managed in a tool that has not been validated as a
  GxP computerized system** (see §7).

The scope decision that most needs making is not technical: either WWF is formally an
*operational planning aid* (non-GMP, no regulated records live here — then CAPA/SOP
status tracking belongs in the eQMS), or it is a GxP system and must be treated as one.

## 2. Backend — FastAPI + asyncpg + RLS

**What is genuinely good.** Postgres RLS as the real security boundary (two DB roles,
`NOBYPASSRLS` for request handlers, forced RLS on every table); per-request identity via
GUCs; Alembic migrations with a CI drift check that diffs an alembic-built schema against
`schema.sql` byte-for-byte; token invalidation on password change via the `pwv` claim;
login rate limiting; timing-side-channel-hardened login; a hash-chained audit log. For a
hand-rolled system this is an unusually defensible security core.

**Where it is weak.**

1. **Duplicated business logic is the top structural risk.** The Fri→Thu window math,
   the "activity in window" 4-way OR predicate, and the Letta wire-protocol parsing all
   exist twice (`app/api/reports.py` vs `scripts/weekly_snapshot.py` / `app/api/ai.py`).
   The duplication is documented and deliberate (the script is dependency-light so its
   helpers are unit-testable), but nothing but comments keeps the copies in sync. One
   diverging edit silently makes the AI report describe a different week than the UI.
   A shared `wwf_core` module importable by both is the eventual right answer.
2. **Status vocabulary drift.** Queries hedge with `status IN ('completed','done')` and
   `('working','ongoing')` — two synonym pairs live in the data. There is no DB CHECK
   constraint on `tasks.status` (unlike `profiles.role`). Every consumer must remember
   both spellings forever, and one day one of them won't.
3. **In-process state doesn't scale past one replica.** The login rate limiter is a
   process dict; horizontal scaling or a second uvicorn worker silently halves it.
   Fine today (one container), a landmine later.
4. **No observability.** Structured request logging exists, but there are no metrics,
   no error aggregation, no alerting. The scheduler dead-loop bug (fixed this week)
   is exactly the class of failure that monitoring — "no weekly_report pin created in
   8 days" — would have caught and nothing else did.
5. **Auth is single-factor.** 15-min JWTs + remember-device is reasonable UX, but there
   is no MFA option; for a system holding QA records, that is below current baseline.

## 3. Frontend — vanilla JS, `window.GF`, monkey-patch integration

**The good.** Zero build step, zero runtime dependencies (no supply-chain surface),
same-origin nginx proxy (no CORS in production), bilingual en/mk throughout, CSV export
hardened against formula injection.

**The blunt assessment: this is the weakest layer of the system.**

1. **`integrate.js` is a 1,100-line monkey-patch.** The architecture is "load a legacy
   app, then override its globals from a file that must load last." Ordering-dependent
   script tags, no module system, no types, shared mutable `GF.*` state mutated from
   five files. Every feature (hours capture, pins panel, collab) is another override
   grafted on. It works, and the e2e tests protect the critical paths, but each addition
   raises the marginal cost of the next; this codebase punishes contributors.
2. **DOM by string concatenation.** HTML is assembled with template literals and
   `innerHTML`. Escaping is handled where it was noticed; the pattern makes every new
   interpolation a potential XSS until proven otherwise. (Task titles — free text —
   flow through several of these paths.) A `textContent`-first helper, or any small
   templating discipline, would eliminate the class.
3. **No frontend unit tests.** The pyramid is API-heavy (96 backend tests, solid),
   4 Playwright e2e specs, and zero unit coverage of `transform`, status/priority
   mapping tables (`S_OUT`/`P_OUT` — the site of a past data-corrupting bug), or i18n.
4. **State reconciliation is manual.** Optimistic updates with hand-rolled revert
   (`saveHours`) next to non-reverting siblings (`paraphraseTask`) — the same PATCH
   boilerplate hand-copied six times with different failure semantics.

## 4. AI functions — Letta agents, pins, scheduler

**The good.** This is the most differentiated part of WWF, and its failure model is
right: Letta being down never breaks a run (deterministic digest fallback, always
pinned); prompts are versioned and self-heal at boot; the digest archive doubles as RAG
memory; per-user reports are now RLS-protected; the Thursday fire is DST-correct and
missed-run-recoverable.

**Where to stay critical.**

1. **No evaluation loop.** Prompt v3 ships on the same evidence v2 did: one person
   eyeballing outputs. There is no golden-set regression ("does the report still name
   all stuck tasks?"), no structured scoring, not even a persisted record of which
   prompt version produced which pin. Add `prompt_version` to `ai_pins`.
2. **JSON extraction is a regex.** `_extract_json_field` greps `{.*}` out of prose. It
   tolerates fences, but a reply containing two JSON objects, or braces inside the
   markdown body, degrades to fallback. Letta supports structured outputs; use them.
3. **AI content has no human gate.** Reports are auto-pinned and displayed as fact. In
   a GMP context (see §7) an unreviewed generated report about CAPA/validation status
   is itself a data-integrity hazard — one hallucinated "completed" is a false record.
   The pins panel should mark AI output as *draft* and record an explicit human
   acknowledgement.
4. **The whole layer is single-host, single-agent-server.** Letta, Qdrant, Postgres,
   and the app share one VPS. Letta down = degraded (handled); host down = everything
   down (not handled anywhere).

## 5. Data, server & connectivity

One KVM4 VPS runs: Traefik (TLS), the WWF stack, Letta + its Postgres + Qdrant, Ollama,
several unrelated services, **and the `kvm4-runner` remote-execution service**.

1. **The runner is the largest single attack surface on the box.** It executes
   arbitrary shell as root over HTTPS with a static bearer token. It is an ops
   convenience that de facto holds every secret on the host. It should be network-
   restricted (allowlist/VPN), audit-logged, and its token rotated on a schedule —
   or replaced with a proper CI deploy path (a `deploy.yml` workflow already exists
   in-repo; two parallel deploy mechanisms means drift).
2. **No visible backup/restore story.** Nothing in the repo or on the host indicates
   automated Postgres backups, tested restores, or offsite copies. For a system whose
   value is its history (audit chain, pins archive, task records), this is the most
   consequential operational gap in the entire review.
3. **Secrets management is env-files-on-disk** (`app.env`, `db.env`, container env).
   Acceptable for a single-admin VPS; document it and restrict file modes at minimum.
4. **Single point of failure everywhere** — one host, one DB, one Traefik. That is a
   cost/benefit choice a 5-person facility may reasonably make, but it should be a
   *written* choice with an RTO/RPO statement, not an accident.

## 6. Database

**Good:** RLS forced on every table incl. new ones; org-scoped policies; hash-chained
`audit_log` with a verifier; sensible indexes (now including the AI context sort path);
domain invariants moving into the DB (role CHECK, status CHECK on handoffs, hours CHECK
as of migration 0003); soft-delete on tasks.

**Critical notes:**

1. **`calendar_weeks` (ISO Mon→Sun) vs the Fri→Thu work week is a semantic mismatch.**
   Pins are keyed to the ISO week containing the window's Thursday. It's now consistent
   and never-NULL, but "which week is this report for?" has two answers in the data
   model. A `report_windows(starts_on, ends_on)` table would say what it means.
2. **`deps uuid[]` and `days text[]`** are unvalidated arrays — no FK integrity, no
   enum check. Dangling task references are representable and nothing cleans them.
3. **`progress_notes jsonb` duplicates `task_progress` rows** — two sources of truth
   for the same concept, already the cause of one shipped bug (codec string-vs-list).
4. Org deletion is a hard `ON DELETE CASCADE` through everything, including the audit
   log — one admin action can erase the org's entire audit history. For §7 purposes,
   audit records should survive subject deletion (or deletion should be soft).

## 7. eGMP / computerized-systems posture (Annex 11 / 21 CFR Part 11 lens)

This is the section that matters most and flatters least. The facility operates under
EU-GMP-style oversight (MALMED); the tasks WWF tracks are QA/QC records-adjacent
(CAPAs, SOPs, qualification protocols, a certification submission). If WWF is used to
*decide or evidence* anything GMP-relevant, it is a GxP computerized system and today it
would not pass a serious Annex 11 inspection:

| Annex 11 / Part 11 expectation | WWF today | Gap |
|---|---|---|
| Validation (URS→testing→release, or CSA) | CI tests exist; no URS/FS, no validation plan/report, no release procedure | **Major** — no documented validation lifecycle |
| Audit trail | Hash-chained `audit_log` + verifier — genuinely strong foundation | Needs: coverage review (all GMP-relevant mutations?), periodic review SOP, survives org deletion |
| Electronic signatures | None — no signing meaning, no re-authentication at signature, no signature manifest | **Major** if any record here requires signature (e.g., task = "SOP approved") |
| Access control | Roles + RLS + forced password change + rate limit | MFA absent; no periodic access review procedure |
| Data integrity (ALCOA+) | Attributable (user_id) ✓, contemporaneous ✓ (timestamps), original/accurate: mostly | AI-generated pins presented without human verification undermine "accurate"; no data-retention policy |
| Backup / disaster recovery | Not evidenced | **Major** — no tested restore, no RPO/RTO |
| Vendor/supplier assessment | Self-built + Letta + open-source stack | No supplier qualification file; AI component especially undocumented |
| Time synchronization, records retention, training | Unaddressed in repo/docs | Documentation gaps |

**The pragmatic recommendation** (repeated from §1 because it is the review's central
conclusion): pick one —

- **Option A (recommended, cheap):** formally scope WWF as a *non-GMP planning tool*.
  Write that scope statement. Keep the authoritative CAPA/SOP/validation records in the
  QMS; WWF tasks merely *point* at them. Mark AI pins "informational draft — not a GMP
  record". Most of the table above then stops applying.
- **Option B (expensive):** treat it as GxP — validation file, e-signature workflow,
  MFA, backup SOP with tested restores, AI-output human-approval gate, retention policy.
  Only worth it if WWF is to *replace* parts of the paper/QMS process.

Doing neither — the current state — is the worst position: the tool looks authoritative
enough that people will treat its records as real.

## 8. Against modern platforms — Linear, Asana, Jira, ClickUp, Monday (+ eQMS)

**What they have that WWF lacks** (and users will feel): real-time multiplayer sync and
presence; notifications of any kind (email/push/digest — WWF has none, which for a
*deadline-driven weekly cycle* is a genuine functional hole); file attachments; full-text
search; threaded comments with mentions; dependency graphs/Gantt; dashboards; recurring
tasks; sub-tasks (WWF removed its non-functional ones — honest, but the need remains);
automation rules; mobile apps/offline; SSO/SCIM; a public API with webhooks; audit-trail
*UX* (WWF has the data, no UI). Against GMP eQMS products (Veeva QMS, MasterControl,
Qualio), WWF lacks everything in §7's table — which is precisely why Option A above is
the right scoping.

**What WWF has that none of them do, for this facility:** database-enforced RLS rather
than application-level permissions; full data sovereignty on owned hardware (relevant
for a cannabis operation whose data residency and vendor-risk options are constrained);
an integrated, facility-specific AI weekly-report/plan loop with an accumulating RAG
memory of every week ever worked; native Macedonian; zero per-seat cost; a hash-chained
audit trail stronger than any mainstream PM tool's. The AI reporting loop in particular
is not replicable in Asana/Jira without stitching 3–4 SaaS products together — it is
the system's moat and the reason it should exist at all.

**Verdict.** As a product, WWF would lose to every platform above on breadth. As a
purpose-built internal tool, its differentiators are real. The comparison's actionable
output: the two platform features whose absence hurts *this* workflow most are
**notifications** (Thursday-cycle reminders, stuck-task alerts, "your AI report is
ready") and **attachments/links on tasks** (SOPs and CAPAs live in files). Those two,
not Gantt charts, are the highest-value roadmap items.

## 9. Super-critical programming assessment — the honest list

Ranked by how much each one will cost if left alone:

1. **Frontend integration-by-monkey-patch** (§3.1) — the compounding-interest debt.
2. **No backups** (§5.2) — the catastrophic-tail debt.
3. **Duplicated week/report logic across app and script** (§2.1) — the silent-divergence debt.
4. **GMP scope ambiguity** (§7) — the regulatory debt.
5. **Status synonym pairs + missing status CHECK** (§2.2) — small, corrosive, cheap to fix.
6. **No notifications** (§8) — the biggest pure-feature gap for the stated purpose.
7. **AI output ungated by humans, unversioned in storage** (§4.1, §4.3).
8. **Runner service as root-shell-over-HTTPS** (§5.1) — one leaked token from disaster.
9. **innerHTML-by-concatenation** (§3.2) — an XSS class waiting for its instance.
10. **Two sources of truth for progress notes; unvalidated array columns** (§6.2–6.3).

None of these invalidate the system. The security core (RLS, audit chain, auth
hardening), the test discipline on the backend, the CI drift check, and the now-verified
scheduler/AI loop are all better than typical for a tool of this size. But the list
above is real, ordered, and should be worked top-down.

---

*Prepared as part of the 2026-07-03 post-ship review cycle; companion to the fixes in
migration 0003 and commit b79ceca (scheduler dead-loop, pin privacy RLS, PATCH
null-clear, week-key provisioning, prompt v3).*
