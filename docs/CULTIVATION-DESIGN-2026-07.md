# Cultivation department — design record (2026-07-30)

**Status: pre-design.** No schema has been written. The CEO's cultivation plan is
pending and will settle the decisions marked ⟨PLAN⟩ below; this document exists so
that plan can be mapped onto known ground rather than read cold, and so the
constraints discovered in the existing code are on the table before anything is
built.

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

## 6. Not yet decided

- Whether per-plant identity applies to all phases or only from flower entry
  (the owner decision names flowering rooms specifically).
- Whether mother plants are per-plant tracked indefinitely.
- Whether the "and maybe more" records include waste/trim disposal, drying-room
  environmentals, or pruning/training logs.
