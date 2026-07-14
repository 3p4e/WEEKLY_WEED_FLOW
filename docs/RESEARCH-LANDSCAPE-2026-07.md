# Landscape Research — Building & Operating WWF's Class of Application Well

Deep-research pass, 2026-07-14. Method: fan-out web searches across 12
dimensions → source fetch → claim extraction → **3-vote adversarial
verification per claim** (105 agents; claims below survived; one was refuted).
Only cited, verified material is included — several circulating "statistics"
in the source pool were identified as fabricated and excluded.

## Verified findings

### High confidence (primary/authoritative sources, unanimous votes)

**R1 · Postgres RLS pitfalls (dept-scoped visibility).** RLS fails closed once
enabled with no policy, but **silently exposes ALL rows on any table where RLS
was never enabled**; it is bypassed by superusers, `BYPASSRLS` roles, and (by
default) the **table owner** unless `FORCE ROW LEVEL SECURITY` is set.
*(postgresql.org/docs/current/ddl-rowsecurity.html + 3 corroborating)*
→ WWF applied check: our `app_user` is NOBYPASSRLS and non-owner and we use
per-request GUCs — but every NEW work-data table must have RLS explicitly
enabled; a forgotten table is exactly how department scoping silently breaks.

**R2 · The RLS pattern WWF uses is the recommended one.** Single shared app
role + per-transaction session variable (`SET LOCAL` GUC read via
`current_setting()`), NOT a role per tenant. `SET LOCAL` inside a transaction
is mandatory — plain `SET` leaks one request's scope into the next under
connection pooling. *(Crunchy Data, Microsoft Learn, + 2)* → WWF already does
this correctly (`SET LOCAL app.*`); context-leakage is the #1 isolation break
to guard in review.

**R3 · Regulated audit-trail vocabulary (Part 11 / Annex 11).** The
substantive expectations: secure computer-generated time-stamped trails;
**changes must not obscure previously recorded information**; risk-based
capture of GMP-relevant changes/deletions **with documented reasons**;
convertible to readable form; **reviewed regularly**; users must not be able
to disable/edit logs. Tamper-resistance = WORM storage or cryptographic
chaining. *(eCFR 21 CFR 11.10(e); Annex 11 Cl. 9 — note Annex 11 is in an
active 2024–26 revision cycle)* → WWF's hash chain provides tamper-EVIDENCE;
the honest gaps vs the ceiling are reason-for-change capture and a regular
review ritual. Keep saying "tamper-evident, not a validated Part-11 system."

**R4 · Offline PWA caching is a deliberate per-resource choice.** Cache-first
= fast but stale-risk (app shell); network-first = fresh with offline fallback
(task/plan data). *(MDN)* → WWF's sw.js already splits exactly this way.
**Surviving evidence covers READ caching only — offline WRITE sync/conflict
resolution is an open gap** (see priorities).

### Medium confidence (design-system consensus; directional)

**R5 · Constrained status lifecycle.** A small status set with EXPLICIT valid
transitions (state machine), not arbitrary jumps. *(+ Symfony Workflow, Jira
model)* → WWF's 6 statuses currently cycle freely; a defined transition map is
a durable backbone against "patchwork."

**R6 · Progressive disclosure + visible primary action.** Cards show
title/due/status + an at-a-glance subtask count ("3/5"); tap reveals detail;
**"mark complete" must never be buried in an overflow menu** — "when you need
to hunt through a three-dot menu just to mark a task complete, the UI has
already failed." → Validates the Phase-0 subtask checkbox fix and the popup
chooser direction.

**R7 · Keep subtask nesting shallow.** One level covers most professional
work; two for complex projects; deeper = it's really a project. → WWF's
theme→document→version capture hierarchy is at the sensible maximum; don't go
deeper.

**R8 · Notifications: signal what matters, non-intrusively** (assignments,
comments, due-date changes) — avoid bombardment/notification fatigue. →
Directionally clear but thin; the mechanisms (inbox vs feed split, digest
cadence, quiet hours) were NOT covered by surviving evidence — a dedicated
pass is warranted before building.

### Refuted (do NOT build this)

**✗ "A parent task can only be marked complete when all its subtasks are
done" — refuted 0-3.** Hard-enforcing parent/child completion coupling is
wrong (blocks legitimate managerial closure, orphan subtasks, changed scope).
The right shape: parent completion stays manual and free; offer
auto-complete-when-children-done as an OPTIONAL automation, never a
constraint. (This refines the earlier Linear-pattern note.)

## Evidence gaps = the prioritized deeper-research shortlist

Five requested dimensions produced NO surviving claims — they are
unresearched, not settled. Ranked by tie-in to the owner's stated pains:

1. **Notifications & team awareness mechanisms** (inbox vs activity feed,
   digest cadence, quiet hours, role-appropriate routing) — the "no
   notifications / COO can't see the team's work" pain; R8 is directional
   only. Research BEFORE building Phase-1 notifications.
2. **Onboarding, credential delivery & lockout recovery for non-technical
   staff** — the six locked-out accounts pain; OTP-by-hand demonstrably
   fails; needs a researched flow (delivery channel, expiry, self-service
   recovery vs admin-mediated) suited to a single-tenant self-hosted app.
3. **Offline WRITE sync & conflict resolution** (queue-and-replay mutations,
   last-write-wins vs per-field merge vs CRDT) — shop-floor operators logging
   time/completing subtasks offline; read-caching is solved, writes are not.
4. **Bilingual EN/МК event modeling** — structured/semantic event records
   rendered per-locale at display time vs pre-composed strings, especially
   for audit entries and the AI executive report, so history stays legible in
   both languages without re-translation drift. Prerequisite for the activity
   feed.
5. **AI-assistant guardrails in a regulated-adjacent context** — grounding to
   WWF's own data (partially done: dept-scoped corpus), hallucination control
   in summaries, and explicit no-automation zones (audit entries, compliance
   claims).
6. **Self-hosted small-scale ops hardening** (backup/restore drills, secrets,
   deploy safety, Traefik/LE posture) — much already done in prior cycles;
   verify against external best practice rather than assume.
7. **Incremental modernization** (Vite/TS/store/components) — internal agent
   research exists (REVISION-PLAN-2026-07.md §3) but no adversarially-verified
   external evidence; validate before committing to the Phase-4 refactor.

## Immediate applied actions from the verified set
- Add a CI/test guard: **every table in the tasks DB must have RLS enabled**
  (catches the "forgotten table" failure mode). (R1)
- When building notifications: visible-but-calm surfaces, no bombardment;
  research pass #1 first. (R8)
- Subtask/parent completion: keep both independently completable; optional
  auto-complete automation only. (✗ refuted claim)
- Audit honesty: document "reason for change" and a weekly review ritual as
  the known deltas vs the Part-11 ceiling; never claim validation. (R3)
- Status lifecycle: define the allowed transition map when reworking the
  status picker (chooser makes explicit transitions natural). (R5)

*Full machine-readable result (claims, votes, evidence, 23 sources) retained
in the session workflow output; this document is the durable record.*
