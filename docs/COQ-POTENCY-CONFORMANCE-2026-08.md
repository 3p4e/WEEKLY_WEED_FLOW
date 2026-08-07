# CoQ ↔ Draft-CoQ conformance + per-cultivar potency ladders (2026-08)

Work to make the app's Certificate of Quality output conform to the **Draft CoQ**
(CoQ-PP-2026-0005, Navy&Gold Variation F) and to the **PP-QC-SPEC-001 v5.2**
per-cultivar THC grade ladders the owner supplied. Grounded throughout in the
actual data model + the shared documents — nothing invented (GxP).

## What landed (branch `claude/weekly-read-flow-setup-yft7if`)

### Phase A — per-cultivar potency ladders (stored, approved spec data)
`4199c4f`. Migration **0057**: `qc_potency_specs` (versioned parent, one APPROVED
per cultivar) + `qc_potency_spec_ranges` (tier rows). RLS + `app.fn_audit_row()`
+ guarded grants, exactly like the other QC tables; schema.tasks.sql regenerated
and byte-verified against `alembic upgrade head`. API `app/api/qc/potency.py`:
author → approve → supersede lifecycle, ladder-integrity validation (the ladder
must **tile [floor, 30 %]** with no gap; Spec I tops at 30 %; tiers meet;
adjacent nominals inside their range), **segregation of duties** on approval
(approver ≠ author), and a pure `disposition_for()` resolver + `/qc/potency-disposition`.
The owner's decision (2026-08-07): these ladders are **human-authored and
APPROVED**, read as-is when a certificate issues — never recomputed on the fly.

### Phase B — grade the batch on the CoQ
`814df80`. The CoQ carries a `cultivar_id` and **freezes** the cultivar's APPROVED
ladder (`potency_spec_id`) at compile time, so a later ladder revision never
retro-changes an issued certificate. Disposition is resolved against the frozen
ladder from the CoQ's **Total Δ9-THC** (= Δ9-THC + 0.877·Δ9-THCA, Ph. Eur. 3028)
— the same derived total the engine already computes. Absent a mapped cultivar or
an APPROVED ladder, the grade is simply absent (never invented).

### Phase C — CoQ document conforms to the Draft
`92a5ff1`, `388cac5`, `eb91fdf`. The meta grid now shows a dedicated **Cultivar**
row and a grade-only **Grade** row — e.g. `Spec II · nominal 24.0% (Total Δ9-THC
23.98%) — PP-QC-SPEC-001 v5.2` — placed right after Potency. The batch-disposition
line was corrected to the Draft's precise wording:

> **Conforms to Specification — QC Disposition (not QP batch release)**

A CoQ is a QC-level disposition **against specification**; it is **not** the
Qualified Person's Annex-16 batch certification/release. The old "Approved for
Release" overclaimed that authority; the new wording states the scope honestly in
both languages. The frontend already shows a neutral conformance chip (no release
claim), so no parallel change was needed there.

The Variation-F **structure** is already emitted by `_coq_markdown` (identity meta
grid → §01 Analytical Results → §02 Laboratory & CoA cross-reference → disposition
→ QC compliance statement → Annex-11 e-signatures) and dressed by the DocEngine
`FORM` annex renderer (leaf-logo header, navy `#2B547E` section banners, MK-GMP
footer). Signatories are populated **only** from genuine captured Annex-11
e-signatures — the two named signatories on the Draft are an *example* of executed
signatures, and hard-coding names would fabricate signatures that were never
applied, so the honest attribution path is kept.

## Verification
Full backend suite **673 passed / 0 failed** on `92a5ff1`; focused CoQ+potency
re-run **179 passed / 0 failed** on `eb91fdf`. New `tests/test_potency.py` (10) +
`tests/test_potency_coq.py` (5). RLS-coverage, audit-coverage, facility-clock
(naive-`CURRENT_DATE`) static guards and bandit all green. `conftest.purge_org`
extended for the two new tables.

## Phase D/E finding — no iCoA/eCoA/Spec document to conform
"eCoA + iCoA + Spec document conformance" does **not** map to an existing render
surface. The app renders exactly **one** document — the CoQ — via two paths
(`POST /qc/certificates/{id}/coq`, `POST /qc/coq/{id}/render`), both through
`_coq_markdown`. The **eCoA** is an *ingested external PDF* (we store/verify it,
we don't render it); the **iCoA** is internal result data that *feeds* the CoQ;
**specifications** have no rendered document output. Conforming those as standalone
documents would be a **new feature**, and it needs the owner's target designs —
only the Draft **CoQ** (plus the grade ladders) was provided. Not started, to
avoid guessing a design that wasn't shared.

## Owner-gated: deploy
The agent cannot dispatch Actions in this environment (see `CLAUDE.md`). To ship
this increment, the owner runs **Deploy WWF stack to KVM4** with:
`scope=full`, `sha=<branch head>`, `run_migrations=true`,
`confirm_destructive_migrations=true` — migration **0057** is purely additive
(two new tables), so the destructive-migration path is a formality here.
