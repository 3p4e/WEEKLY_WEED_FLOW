# Cultivation department — design record (2026-07-30)

**Status: BUILT (migrations 0045–0047), not deployed.** This began as a
pre-design record written before the CEO's plan arrived, and the analysis in §1–§4
is kept as written because it is what the design was reasoned from — but §1's
"no schema" framing is historical now. What actually exists:

| | |
|---|---|
| **0045** | cultivation identity — cultivar master, batch codes, per-plant rows, phase events (§5a) |
| **0046** | decontamination campaign — signed room cycle, bleach log, swab release gate (§5b) |
| **0047** | frozen positive controls + tool-sterilisation log |
| API | `app/api/cultivation.py`, `app/api/decon.py` |
| UI | `web/gf/decon-view.js` (decon board); cultivation is API-only so far |
| Adherence | see the requirement-by-requirement table in §5c, including what is **not** built |

The ⟨PLAN⟩ items in §4 were answered by a combination of the plan itself (room
register, biosecurity gates) and the owner directly (the identity scheme) — §5a
records which came from where, because the plan turned out to be a
*decontamination* plan rather than the plant-tracking spec §4 anticipated.

Owner decisions already taken (2026-07-30):

| decision | answer |
|---|---|
| granularity | **individual plant IDs**, plus a batch number **per flowering room** |
| primary goal | **both** — batch records first, then phase-driven tasks on top |
| records in scope | **all four** (harvest/yield, plant-count reconciliation, irrigation/feeding, IPM/pesticide) **and possibly more** |

## 1. What already exists

Cultivation is not greenfield. It exists as **two halves that do not reference
each other.**

**Task half** — the departments already *are* the phases
(`web/gf/data.js`, `GF.DEPTS`): `clone` (Cloning & Nursery), `veg`
(Vegetation), `flower` (Flowering), `irr` (Irrigation). Every existing task
facility applies to them already: weekly planning, owner/helpers, status
workflow, progress notes, approvals, audit.

**Facility half** — `backend/app/api/facility.py` (240 lines) over two tables:

- `rooms` — `code`, `name`, `name_mk`, `kind ∈ {nursery, veg, flower, mother,
  dry, other}`, `sort`, `is_active`.
- `plant_batches` — `room_id`, `strain` (**free text**), `plant_count`,
  `phase ∈ {clone, veg, flower, mother, drying}`, `phase_since` (date),
  `note`, `is_active`.

`GET /facility` returns occupancy; rooms are admin-provisioned; batches are
writable by elevated roles. `web/gf/facility-view.js` renders a read-mostly
occupancy board (plants per room, phase, days-in-phase).

Both tables **do** carry `app.fn_audit_row()` triggers
(`audit_plant_batches`, `audit_rooms`).

**QC half, already waiting** — `qc_batch_genealogy` links batches by **text**
batch code and already defines `relation = 'CULTIVATION'`. The receiving end of
cultivation traceability is built. Nothing upstream produces the identifier.

## 2. Structural gaps

1. **`plant_batches` has no code.** This is the load-bearing gap: with no stable
   identifier, a cultivation batch cannot appear in `qc_batch_genealogy`, so it
   cannot reach a CoA or CoQ. Cultivation is currently an island next to a
   traceability chain built to accept it.
2. **Tasks and batches never reference each other.** A task in department
   `flower` is not attached to any batch, so the work performed on a batch
   accumulates nowhere. This is the gap that makes "records, then tasks" coherent
   — the batch record is what a task should write into.
3. **No lifecycle events.** `phase_since` records only the *current* phase.
   There is no dated transition history, so "when did batch X enter flower" is
   answerable only by reading `audit_log` diffs — which is a forensic tool, not a
   queryable batch record.
4. **No terminal states.** `phase` has no `harvested` and `rooms.kind` has no
   `cure`/`trim`. A finished batch can only be flipped `is_active = false`, which
   loses the distinction between harvested, destroyed, and mistakenly created.
5. **No reconciliation.** Nothing enforces that plants started = plants
   harvested + culled + destroyed. For a per-plant regime this is normally the
   central regulatory invariant.
6. **`strain` is free text.** Per-cultivar reporting fragments on the first typo.
   Needs a cultivar master table with the batches referencing it.

## 3. The constraint per-plant tracking runs into — read this before designing

`app.fn_audit_row()` (identical in both databases; see tasks-0012 and
users-0006) does, **per row**:

```
PERFORM pg_advisory_xact_lock(4019283746);   -- one GLOBAL lock id
SELECT entry_hash INTO v_prev FROM audit_log ORDER BY id DESC LIMIT 1;
INSERT INTO audit_log(...);
```

Three properties matter here:

- The lock id is a **single global constant**, so it serialises audited writes
  across the *entire* database, not per table.
- It is `pg_advisory_**xact**_lock`, so it is held **until the transaction
  commits** — not released between rows.
- The trigger is `FOR EACH ROW`.

Consequence: **a bulk per-plant operation blocks every other audited write in
the database for the whole transaction.** Moving 500 plants from veg to flower in
one statement takes the chain lock, then serialises 500 tail-read+insert pairs
before committing — and for that entire window every task update, QC result
entry, and profile change waits.

This is not a reason to abandon per-plant tracking. It is a reason the design
must decide, up front:

- **Bulk operations must be chunked** into bounded transactions (e.g. 25–50
  plants), accepting that a chunked move is not atomic, and defining what a
  partially-moved batch means.
- **High-frequency records belong at room or batch level, not plant level.**
  Environmental readings and irrigation/feeding are per-room-per-day by nature;
  making them per-plant would multiply audit volume by the plant count for no
  informational gain.
- **Per-plant rows should carry lifecycle events only** — created, phase moves,
  cull/destruction, harvest. That is roughly 7 events per plant lifetime, which
  is affordable; a daily per-plant record is not.

⚠️ This has **not** been measured, only read from the source. Before committing
to a bulk-move design, benchmark `fn_audit_row()` throughput against a
realistically-sized `audit_log` on a restored production dump, and record the
per-row cost here. The nightly migration-rehearsal workflow already restores such
a dump and is the natural place to do it.

## 4. What the CEO plan needs to settle ⟨PLAN⟩

Listed so the plan can be checked for them, and so anything absent is a known
open question rather than an assumption someone made quietly:

1. **Plant ID format** — scheme, who assigns it, whether it is human-readable,
   whether it is physically tagged, and whether it survives a room move.
2. **Batch numbering per flowering room** — the owner decision is a batch number
   *per flowering room*. Needs pinning down: does the number reset per room, per
   year, or per cycle? Is it allocated at clone or at flower entry? What happens
   when one flowering room holds two cultivars, or when a batch is split across
   two rooms?
3. **Phase list and legal transitions** — the current set is
   clone/veg/flower/mother/drying. The plan should confirm whether nursery is
   distinct from clone, whether cure and trim are phases or rooms, and which
   transitions are permitted (can a batch return to veg?).
4. **Room layout** — count and kind of rooms, plant capacity per room, and
   whether sub-zones/benches/rows need to be addressable.
5. **Cultivar list** — the actual cultivars, to seed the master table and retire
   the free-text `strain`.
6. **Reconciliation rules** — what must balance, at what point, who signs it, and
   what an unexplained discrepancy blocks.
7. **Record formats for the four record types** — specifically the fields the
   floor is expected to fill and which are mandatory, since these become forms
   used many times a day.
8. **Who does what** — the app enforces department scope at the application
   layer; the plan should say which roles may record vs approve each record type.

## 5. Proposed build order

Deliberately foundation-first, because items 2–5 all hang off item 1 and
retrofitting an identifier is the expensive kind of rework.

**Phase 1 — identity and lifecycle (unblocks everything).**
Batch code on `plant_batches`, cultivar master replacing free-text `strain`,
per-plant table parented to the batch, dated phase-transition events, terminal
states (`harvested`, `destroyed`). Join cultivation into `qc_batch_genealogy` via
the new code, which is what finally connects cultivation to the existing
CoA/CoQ chain.

**Phase 2 — the records.**
Harvest/yield first, because it closes the loop into the QC lot. Then
reconciliation/destruction (the regulatory invariant), then irrigation/feeding
and IPM, both room-level and dated. IPM carries re-entry and pre-harvest
intervals, which the harvest step must then be able to *block* on — that
interaction should be designed with harvest, not bolted on after.

**Phase 3 — tasks on top.**
Phase transitions generate the per-phase task sets, and tasks reference the batch
they act on, so the batch record accumulates from work actually performed. This
is the half that makes the two existing halves one department.

Every new table needs an `app.fn_audit_row()` trigger — not as a convention but
because `backend/tests/test_audit_coverage.py` is default-deny and will fail the
build otherwise. Any deliberate exemption goes in that test's `_EXEMPT` set with
a stated reason.

## 5a. Owner-confirmed identity scheme (2026-07-30) — now built as migration 0045

The plan (`Final COMPLETE_Plan_interactive`, the HLVd eradication campaign) turned
out to be a **decontamination** plan, not the plant-tracking spec — so it settles
the room register and the biosecurity/quarantine gate, but the identity scheme
came directly from the owner:

- **Batch = one cultivar in one flowering room.** Usually a whole flowering room
  is a single cultivar and therefore a single batch; occasionally a room holds
  several cultivars, and then **each cultivar in that room is its own batch.**
- **~2000 plants per flowering room.**
- **Batch code** like `GP072501` — site prefix + period + sequence.
- **Plant ID** `<clone-date>_<cultivar>_<seq>`, `seq` incrementing from 1 within
  the batch.

Migration `0045_cultivation_identity_lifecycle` implements the shape:

- `cultivars` — the master that retires free-text `plant_batches.strain`.
- `plant_batches` gains `code` (unique per org where present) and `cultivar_id`;
  its `phase` vocabulary is widened to add `nursery` (split from `clone`) and the
  terminal states `harvested`/`destroyed`.
- `plants` — one row per plant, `plant_code` unique per org, `(batch_id, seq)`
  unique. **It deliberately has NO `phase` column.**
- `plant_phase_events` — dated, batch-level transition history; `plant_id` is set
  only for a per-plant exception.

**Why `plants` has no phase — this is the resolution of the §3 audit-lock
constraint, now concrete.** With ~2000 plants per room, a phase column on the
plant would make a room move veg→flower into 2000 UPDATEs, i.e. 2000 audited
writes serialized under `fn_audit_row()`'s single global chain lock, freezing
every other audited write in the database for that transaction. Instead the
phase is the **batch's**: a whole-room move is one `plant_batches` update plus one
`plant_phase_events` row. Per-plant rows change only on bounded exceptions
(this plant culled/destroyed/harvested). Batch CREATION is still ~2000 inserts,
so the **API must chunk** it into bounded transactions (25–50 plants) — the
migration defines the shape, the API owns the chunking, and a chunked create is
not atomic, so a partially-filled batch must be a defined, resumable state.

Verified before commit: upgrade + downgrade clean on a real PG16, the
alembic-head dump matches the regenerated `schema.tasks.sql` under CI
normalization, and `test_audit_coverage` + `test_rls_coverage` pass — all three
new tables carry the audit trigger and org-isolation RLS.

## 5b. The decontamination campaign is a SEPARATE, earlier record — now built (migration 0046)

The plan is a live campaign: destruction 30.07, cleaning through 09.08, genetics
13.08/19.08. It demands structured records this app should hold, and even names
the QMS documents — **QASOP 032** (master plan) and **QASOP 032 A01** (per-room
decontamination batch record), plus **QCSOP 024** (HLVd sampling/RT-qPCR). Those
records — the 5-step signed room cycle with the white-cloth gate and clean-lock,
the strip-verified bleach-bucket log, the swab/RT-qPCR verification that gates
QA room release — are a distinct module from plant tracking. It does not touch
`plant_batches`/`plants`/`cultivars` at all; it precedes the new genetics rather
than tracking them.

Migration `0046_decontamination_campaign` + `app/api/decon.py` implement it:
`decon_room_cycles` (one per room per campaign — a partial unique index allows a
room to re-enter a LATER campaign once its current cycle is terminal),
`decon_step_signoffs` (append-only per attempt, since the plan's own rule is
"soiled cloth → wash again", so a step can be re-attempted), `decon_bleach_log`
(every bucket, strip-verified — the plan calls this "the cheapest, most valuable
record"), and `decon_swabs` (RT-qPCR result gating release).

Two gates are enforced in code, not left to discipline, because the plan is
explicit that either failing is how the campaign fails:

- **Steps are signed in order**, and `bleach` is rejected unless the latest
  `rinse1_whitecloth` attempt PASSED. A failed white-cloth check does not dead-end
  the cycle — it reopens `detergent_wash`, matching "wash again; the bleach does
  not go on" precisely.
- **Release requires every step signed AND every swab for the room negative** —
  a `pending` or `positive` swab blocks it outright, and release is gated to
  QA_MGR/executives/ADMIN only ("nobody else can release a room ... no room is
  released verbally"). Room codes are deliberately NOT seeded by the migration:
  the register is per-org operational data, so rooms stay provisioned through the
  existing ADMIN-only `POST /facility/rooms`, and Purely Plant's 19 real rooms
  were loaded by a reviewable one-off script instead (see §5c). At the time the
  migration was written the Rooms-1-6-to-C180-C185 mapping was also still an
  unconfirmed assumption per the plan's Appendix B; that has since been resolved
  by the layout drawing, which is a second reason the mapping does not belong in
  schema history.

Both gates and the campaign-scoped duplicate-cycle guard are tested
(`tests/test_decon.py`, 8 tests) against a real Postgres, including the full
soiled→re-wash→pass→bleach→release happy path and every one of the release
refusals (no swabs at all, pending, positive). 25 affected-area tests green
(decon + cultivation + facility + audit/RLS coverage); upgrade/downgrade clean;
schema-diff invariant holds.

## 5c. Plan-adherence status (2026-07-30)

What the campaign plan asks for, and whether the software now holds it. Kept
honest on purpose — the gaps matter more than the coverage.

| Plan requirement | Status |
|---|---|
| Per-room 5-step cycle, signed step by step (§10, §12; QASOP 032 A01) | **built** — `decon_step_signoffs`, order enforced |
| White-cloth gate before bleach (§12 step 3) | **built** — enforced server-side, bleach refused until it passes |
| Bleach bucket strip-verified and logged (§5, §13, §27) | **built** — `decon_bleach_log`, below-spec flagged |
| Clean-lock / seal on completion (§10) | **built** — `sealed_at`, set when the cycle completes |
| QA-only written room release against a complete record (§27) | **built** — all-negative swabs required, QA_MGR only |
| RT-qPCR swabs + results + action on positive (§27, QCSOP 024) | **built** — `decon_swabs`, positive needs a stated action |
| Frozen positive controls, taken before the cull (§11.7, §27) | **built** — `decon_positive_controls` |
| Tool sterilisation at 10,000 ppm (§28 control 2) | **built** — `decon_tool_log`, separate target from surfaces |
| Room register / codes | **seeded 2026-07-30** — owner confirmed the codes against the detailed facility layout, resolving Appendix B's open item. 19 rooms incl. C171/C176-C179/C180-C185/C88/C150/C158 + 5 corridors; see `backend/scripts/oneoff_seed_purelyplant_rooms_20260730.sql` |
| Rooms-1-6 ↔ C180-C185 reconciliation (§10) | **resolved in the data, signature outstanding** — the layout drawing positions `FLOWERING PREMISE 1.N` within 2-11 columns of `C(179+N)` while adjacent rooms sit 60-100 apart, so the pairing is geometrically forced and agrees with the plan's §08 zone map. Room names now carry all three designations (`Flowering 1.1 · C180 · Room 1`); see `oneoff_restore_flowering_room_numbers_20260730.sql`. QA's signature on the one-page table is **still open** — evidence is not a controlled document |
| Cultivation batch identity + per-plant IDs (owner scheme) | **built** — migration 0045 |
| Destruction / waste manifest (several tonnes, 30.07-01.08) | **NOT built** |
| Corridor cleaning cadence (after every waste movement, 4-hourly, shift changeover) | **NOT built** |
| AHU filter pull/refit record (§18) | **NOT built** |
| Disinfection-mat refill + strip verification (§20) | **NOT built** |
| Contact plates (drying/curing) and sentinel bioassay (§27) | **NOT built** |
| Gowning / zone-crossing control (§23, §28 control 5) | **NOT built** |
| The QMS documents themselves (§31) | **out of scope for software** — they are controlled documents to be authored |

The unbuilt rows are all *additional record types* of the same shape as those
already built, not changes to the model. None of them blocks the built ones. The
ordering above follows the plan's own priority ranking (§11), which is why the
bleach specification, the cycle, the swab gate, the positive controls and the tool
log came first.

## 6. Not yet decided

- Whether per-plant identity applies to all phases or only from flower entry
  (the owner decision names flowering rooms specifically).
- Whether mother plants are per-plant tracked indefinitely.
- Whether the "and maybe more" records include waste/trim disposal, drying-room
  environmentals, or pruning/training logs.
