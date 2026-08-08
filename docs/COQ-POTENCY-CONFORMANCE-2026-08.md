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

## Deployed to production — 2026-08-08

Shipped from `02f1460` as **backend v87 / scheduler v87 / frontend v127**, tasks
chain **0055 → 0058** (users already at `0010`). Actions dispatch is owner-only, so
this went out directly through the kvm4-runner `/shell` endpoint following
`deploy.yml`'s own sequence (see `CLAUDE.md` → "Deploying without Actions").

- Verified snapshot (rollback): `/opt/wwf-deploy/snapshots/20260808T185724Z-manual-02f1460/`
- Image assertion: built backend resolves `users=0010`, `tasks=0058` — the repo's
  heads at that SHA; both images grepped for symbols only this commit has.
- Migrations ran BEFORE the image swap; services recreated one at a time,
  `--no-deps`; no database container touched, no volume pruned.
- Post-deploy: `https://wwf.srv1231216.hstgr.cloud/health/ready` →
  `{"ready":true,"databases":{"users":"ok","tasks":"ok"}}`; index `200`; the live
  JS serves this commit; `/qc/potency-specs` and `/qc/potency-disposition` answer
  `401` (registered) vs `404` for a nonexistent route.

Note on ordering: `0056` drops `qc_ecoa_id_seq`, which the *old* v86 image still
used, so migrate-before-swap opened a brief window where old code could hit a
missing sequence. Production data was near-empty and the swap followed
immediately; on a busier system, swap first or split that migration.
