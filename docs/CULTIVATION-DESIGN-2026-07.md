# Cultivation department — design record (2026-07-30)

**Status: ALL of it is LIVE in production** — migrations 0045–0049, the
cultivation identity board, the destruction register and the corridor cadence
panel (backend v80 / frontend v111, 2026-07-30; see `docs/DEPLOY.md` for the
deploy record and its verification). The **schema and code are deployed; the
DATA is empty** — an owner-ordered full wipe on 2026-07-30 cleared every
application record, including the room register, so the module is live and
waiting to be populated rather than in use. Everything deleted is archived at
`/opt/wwf-backups/prewipe-20260730/`. This began as a pre-design record written before
the CEO's plan arrived, and the analysis in §1–§4 is kept as written because it is
what the design was reasoned from — but §1's "no schema" framing is historical
now. What actually exists:

| | |
|---|---|
| **0045** | cultivation identity — cultivar master, batch codes, per-plant rows, phase events (§5a) |
| **0046** | decontamination campaign — signed room cycle, bleach log, swab release gate (§5b) |
| **0047** | frozen positive controls + tool-sterilisation log |
| **0048** | destruction / waste manifest — witnessed disposal + batch reconciliation (§5d) |
| **0049** | corridor cleaning **cadence** — trigger-classified, joined to waste movements (§5e) |
| API | `app/api/cultivation.py`, `app/api/decon.py`, `app/api/waste.py` |
| UI | `web/gf/cultivation-view.js` (identity board), `web/gf/decon-view.js` (decon board), `web/gf/waste-view.js` (destruction register) |
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

> **Status 2026-07-30.** Reconciliation/destruction landed first (migrations 0048
> and 0049) because the campaign's destruction window forced it. Harvest/yield and
> IPM landed together as migration 0051 — see §5f, which explains why the PHI
> interaction made shipping them separately the wrong call rather than merely the
> slower one. Irrigation/feeding (migration 0052) closed Phase 2. **Phase 2 is
> complete.**

**Phase 3 — tasks on top.**
Phase transitions generate the per-phase task sets, and tasks reference the batch
they act on, so the batch record accumulates from work actually performed. This
is the half that makes the two existing halves one department.

> **Status 2026-08-05.** Built as migration 0054: `tasks.batch_id` (nullable,
> `ON DELETE RESTRICT`, same convention as harvests/IPM/irrigation/biosecurity's
> own batch_id columns) plus `_generate_phase_tasks` in `app/api/cultivation.py`,
> which fires on `POST /batches/{id}/move`. Static, code-defined templates for
> `veg`/`flower` (the two phases with a well-known task set); other phases
> generate nothing, which is the correct outcome, not a gap. Idempotent per
> (batch, phase) via an `attributes.phase_gen` marker, so a correction (a move
> back and forward again) never duplicates a set. Never raises — a missing
> `cultivation` department or calendar week is a reason to generate nothing,
> never a reason to fail the move itself. `GET /batches/{id}/tasks` reads back
> the accumulated set (auto-generated or hand-linked via the ordinary task
> create/PATCH endpoints).

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

## 5d. Destruction / waste manifest (migration 0048)

The campaign's destruction window is 30.07-01.08 and it moves several tonnes off
site. Migration 0045 can mark a batch `destroyed`, which says the batch is gone
but not what left the building, how much it weighed, who watched it go, or who
took it. Destruction is the one phase transition where the material stops being
auditable afterwards — a missing harvest record can be reconstructed from the
lot, a missing destruction record cannot be reconstructed from anything — so
this is the regulatory invariant the §5c table names.

**Header + lines, not one table.** One consignment routinely empties several
batches, and the reconciliation question is per BATCH while the weighbridge
ticket and carrier docket are per CONSIGNMENT. One table would force either a
duplicated carrier reference across rows (two rows able to disagree about one
physical load) or per-batch quantities in free text (nothing reconciles).

**The status ladder is in the schema**: `draft -> sealed -> witnessed ->
disposed`. Each rung is a different person's assertion, so "who has signed off"
is a query rather than an interpretation of timestamps. Row-level CHECKs refuse a
status without the timestamp that evidences it, so a manifest cannot read
`disposed` with every signature column null.

Four gates, enforced in `app/api/waste.py` rather than left to discipline:

- **An empty manifest cannot be sealed.** A sealed manifest asserts "this is what
  left the building"; with no lines it asserts nothing while looking complete.
- **A sealed manifest accepts no line changes.** That is what sealing means, and
  without it the witness signed something that can still change underneath them.
- **The witness must differ from the weigher.** The two-person rule is the entire
  point of a destruction witness; one person doing both is not a witnessed
  destruction whatever their role. Checked in the API, not as a CHECK, because
  `weighed_by` is null until the seal and a row-level `<>` would silently permit
  the equal-and-null case.
- **Disposal follows witnessing.** The carrier reference closes a chain that has
  to exist first.

**The reconciliation invariant** — plants declared destroyed per batch, summed
across every manifest including drafts, may not exceed the batch's plant count —
also lives in the API. It spans two tables, and the alternative (a counter column
on `plant_batches`) would be a second source of truth for a derivable number.

`GET /waste/reconciliation` is the report that closes the loop, and it flags the
one discrepancy neither module can see alone: a batch **closed as destroyed in
cultivation with nothing ever manifested**. Cultivation says the plants are gone;
the waste register says nothing left the building. Only the join notices.

The report's `unaccounted` field is plain arithmetic (`plant_count` minus declared
destroyed) and is a discrepancy **only for a batch in the `destroyed` phase** —
for a live batch it equals the whole batch, because the plants are in the room.
The first version of the board rendered it unconditionally, which labelled every
healthy batch "2000 unaccounted" and would have buried the handful of rows the
report exists for. It now interprets the number by phase in a single predicate
shared by the row rendering and the summary count, so the banner and the
highlighted rows cannot disagree, and it treats a *partly* manifested destroyed
batch as a problem too — "has a manifest, therefore fine" is exactly the reading
that lets 70 of 100 plants leave unrecorded.

Tested with 14 backend tests against a real Postgres (`tests/test_waste.py`) and
26 frontend tests (`tests/frontend/waste-view.test.js`). Twelve backend mutations
and sixteen frontend mutations were each applied one at a time and each failed the
test intended to catch it; two early mutation attempts were silent no-ops (a
quoting mismatch), which is why the mutation harness now refuses to run a
mutation whose pattern is absent.

## 5e. Corridor cleaning cadence (migration 0049)

§25 requires the cultivation corridors (C146/C152/C155/C169/C170) cleaned **after
every waste movement, every 4 hours, and at shift changeover** during the
campaign. That is a *cadence* requirement, and a cadence requirement is not
satisfied by a log: a log answers "was it cleaned", the requirement asks "was it
cleaned OFTEN ENOUGH, and after the specific events that demand it". The whole
design follows from that distinction.

**The trigger is a column, not free text.** Without it the four-hourly rule and
the after-a-movement rule are indistinguishable in the data, so a shift that moved
waste four times and swept four times looks identical to one that swept on the
clock and never after a movement — and only the second is a breach.

**A `waste_movement` clean must cite the manifest it followed** — enforced in both
the row (CHECK) and the API. Without the link it cannot discharge "after every
waste movement", because nothing ties it to a movement. This only became possible
once 0048 made the movements records, which is why the two migrations belong
together.

**The cadence is DERIVED at read time**, not stored as a due-date and not driven
by a scheduler row. A stored due-date is a second source of truth that goes stale
the moment someone cleans early, and a due-date row implies something will act on
it. The 4-hour interval lives in exactly one place (`_CORRIDOR_INTERVAL_MIN`) and
is *reported*, never enforced: software cannot make anyone mop a corridor, and a
board that implied otherwise would show a false green.

**Corridors come from the room register, not a hardcoded list.** A literal
C146/C152/... list in the query would silently ignore a corridor added later —
the failure mode of every embedded facility list. `rooms` has no corridor `kind`
(they are `other`), so the query reads the name in either language.

`GET /decon/corridors` returns, per corridor, when it was last cleaned, how long
ago, and whether that is inside the interval — plus
`movements_without_cleaning`: **disposed waste manifests with no corridor cleaning
recorded after them.** Two properties of that join are load-bearing and each has
its own test:

- *Never cleaned is overdue, not unknown.* During a campaign a corridor with no
  record is precisely the case the requirement is aimed at; reporting it as blank
  would let it sit unnoticed beside a green row.
- *An earlier movement's sweep does not discharge a later movement.* Movement A is
  disposed, the corridor is swept citing A, then B is disposed and nothing is
  swept — B is still a breach. This is what makes the `cleaned_at >= disposed_at`
  comparison load-bearing, and the first version of the test file did **not**
  cover it: the earlier clean it used was a four-hourly one whose trigger fails
  the condition anyway, so deleting the time comparison changed nothing and the
  mutation survived. The test that catches it was written from that finding.

`cleaned_at` is server-stamped and deliberately not client-settable — a crew that
can backdate its own cleaning satisfies the cadence on paper only. A below-spec
strip reading is recorded rather than refused, the same reasoning as the bleach
and tool logs: a refused entry is one the crew simply does not make, and an
unlogged weak bucket is invisible.

**Two more findings came out of mutation testing, and both changed the code rather
than the tests:**

- The join originally also accepted *any* cleaning with
  `trigger='waste_movement'`, on the theory that one sweep covers whatever moved.
  That is a hole — a sweep attesting to movement A, timed after movement B, would
  silently discharge B — and it made the mandatory manifest citation pointless.
  Removing the loose clause made a mutation fail nothing, which is how the hole
  surfaced: no test depended on the weaker reading because the weaker reading was
  not what anyone wanted. "After EVERY waste movement" now means per movement, so
  one physical sweep after two movements is two attestations.
- The overdue boundary at exactly 240 minutes was undefined — a mutation flipping
  `>` to `>=` survived. It is now `>=` (cleaned every 4 hours makes it *due* at the
  four-hour mark, not a minute after) and pinned at 239/240/241.

Tested with 16 backend tests (`tests/test_corridors.py`) and 13 frontend tests
(appended to `tests/frontend/decon-view.test.js`). 17 mutations applied one at a
time; the three that survived each pointed at a real defect rather than a missing
assertion, and all three were fixed in the code.

## 5f. Harvest / yield, and the IPM applications it blocks on (migration 0051)

Phase 2 item 1, and the first piece of this build that is not a cultivation
record in isolation. **Creating a harvest writes a `qc_batch_genealogy` edge
`batch code → lot code` with `relation='CULTIVATION'`.** That relation has been
defined since migration 0036 (2026-07-21) with nothing upstream producing the
identifier for it, so until now a finished-product CoQ could not trace past the
processing lot. It can now: cultivar → batch → harvest lot → processing →
packaging, with no gap.

**Why IPM ships in the same migration.** §5's own build order says the PHI
interaction "should be designed with harvest, not bolted on after". A pre-harvest
interval is not an IPM feature that harvest consults — it is a *harvest gate*
whose evidence happens to live on the IPM row. Shipping harvest first with a
`phi_acknowledged` boolean would have produced a gate with nothing to read, an
override with nothing to override, and an IPM table later shaped around a
placeholder. Both tables land together and the gate reads real rows from day one.

`ipm_applications.applied_at` is a **timestamptz, not a date**, because REI is
measured in hours: a room sprayed at 08:00 with a 12-hour re-entry is enterable at
20:00 the same day. A date column rounds that to "not today", which is wrong on
the permissive side — the side that puts people in a treated room.

**The five gates**, all refusals rather than warnings:

1. **Pre-harvest interval.** A batch inside a PHI cannot be cut. Overridable only
   by QA authority and only with a written reason, both stamped on the harvest row
   (`harvests_phi_override_check` makes the three columns arrive together or not
   at all — there is no anonymous override and none with a blank reason). A
   recorder sending a reason gets 403: if they could clear their own block the
   gate would be decoration.
2. **Headcount, across BOTH registers.** Harvested plants plus plants declared
   destroyed may not exceed the batch. Checking either alone lets both be
   individually valid and jointly impossible — 2000 cut into lots and the same
   2000 destroyed. `waste.add_line` gained the mirror of this check in the same
   change; it previously counted destruction only.
3. **Yield arithmetic.** Dry output cannot exceed wet input. This one is a schema
   CHECK, not just an application guard: four columns of one row, so nothing can
   put a lot that gained mass in a dry room into the table by any route, including
   a direct SQL fix.
4. **Closing needs a yield.** A closed record with no dry weight looks finished,
   which is worse than an open one.
5. **Terminal batches.** The manager closes the batch after the final pull, not
   before.

**Room scope is resolved as of the application date, not as of now.** A room-scoped
spray restricts whatever was standing in that room *when it was sprayed*. A batch
that moved in afterwards was never treated; one that moved out still carries the
interval. `plant_phase_events` already dates every move, so the batch's room on
the application date is a lookup rather than a guess — and resolving against the
current room gets both cases backwards.

**Deliberately NOT gated: closing a lot needs no second person.** The destruction
witness exists because destroyed material stops being auditable the moment it
leaves; a harvest lot is still physically present and still re-weighable, so the
same friction buys far less and would be routed around. If a second signature is
wanted it belongs on the CoA, where it already exists.

**What is reported and not refused:** moisture loss outside 60–92%. Fresh material
is roughly three-quarters water and dries to ~10–12% moisture, so 70–80% loss is
ordinary; the band is wider than that on purpose, because a report that cries wolf
on ordinary variation gets ignored on the day it is right.

`GET /cultivation/yield` closes the loop the same way the destruction register
does: per batch, planted vs harvested vs destroyed, and
`harvested_without_record` — a batch closed as harvested in cultivation with no
lot recorded. Cultivation says the crop came off; the yield register says nothing
did, and there is no lot for a certificate to be issued against. Neither module
sees that alone.

**Access is widened by exactly one action.** QA_MGR can create a harvest — because
the PHI release is written on the harvest row, so whoever releases the block must
be the one who signs the record carrying it. Recording the yield, closing the lot
and logging IPM applications all stay with the cultivation crew.

Routes hang off the existing `/cultivation` prefix (a second FastAPI router on the
same prefix), so nginx's allowlist and `sw.js`'s `API_RE` needed no change — a
new prefix missing from either is the exact class of live bug the route drift
detector was written for on 2026-07-30.

Tested with 26 backend tests (`tests/test_harvest.py`) and 36 frontend tests
(`tests/frontend/harvest-view.test.js`). 12 mutations applied one at a time, all
killed; the first attempt at the ladder mutation was **unreachable** (the `wet`
branch returns before the `dried` branch is evaluated) and so proved nothing — it
was replaced with one that actually renders two rungs. Building the frontend
suite also surfaced two real defects, both fixed in the code rather than the
tests: `harvestForm()` resolved before its own clearance box had rendered, and one
test asserted on a spy that only existed in the tests expecting a call, so its
"must not call" assertion was vacuous.

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
| Room register / codes | **script ready, currently NOT loaded.** Owner confirmed the codes against the detailed facility layout, resolving Appendix B's open item, and the 19 rooms (C171/C176-C179/C180-C185/C88/C150/C158 + 5 corridors) were seeded on 2026-07-30 — then removed by the owner-ordered full data wipe later the same day (see `docs/DEPLOY.md`). Re-seeding is one idempotent command: `backend/scripts/oneoff_seed_purelyplant_rooms_20260730.sql` plus the two follow-ups named in its header |
| Rooms-1-6 ↔ C180-C185 reconciliation (§10) | **resolved, re-applied by the seed script** — the layout drawing positions `FLOWERING PREMISE 1.N` within 2-11 columns of `C(179+N)` while adjacent rooms sit 60-100 apart, so the pairing is geometrically forced and agrees with the plan's §08 zone map. Room names now carry all three designations (`Flowering 1.1 · C180 · Room 1`); see `oneoff_restore_flowering_room_numbers_20260730.sql`. QA's signature on the one-page table is **still open** — evidence is not a controlled document |
| Cultivation batch identity + per-plant IDs (owner scheme) | **built** — migration 0045 |
| Cultivation board a grower can actually use | **built 2026-07-30** — `web/gf/cultivation-view.js`: cultivar registry, coded batches, chunked/resumable plant-id generation, whole-batch phase moves, paginated plant roster. 29 unit tests (`tests/frontend/cultivation-view.test.js`), ten mutations verified to fail the intended test |
| Destruction / waste manifest (several tonnes, 30.07-01.08) | **built 2026-07-30** — migration 0048 + `app/api/waste.py` + `web/gf/waste-view.js`: header/lines, the draft→sealed→witnessed→disposed ladder, the two-person witness rule, and per-batch reconciliation incl. the closed-as-destroyed-but-never-manifested flag (§5d) |
| Corridor cleaning cadence (after every waste movement, 4-hourly, shift changeover) | **built 2026-07-30** — migration 0049 + `/decon/corridors` + a panel on the decon board. A *cadence* record, not a log: trigger-classified, derived overdue against a single interval constant, and joined to 0048's movements so a disposal with nothing swept after it is surfaced (§5e) |
| Harvest / yield record, and the cultivation→QC join | **built 2026-07-30** — migration 0051 + `app/api/harvest.py` + `web/gf/harvest-view.js`: harvest lots with wet/dry weights on a wet→dried→closed ladder, and the `qc_batch_genealogy` edge that finally fills the `relation='CULTIVATION'` slot migration 0036 has carried since before cultivation had an identifier (§5f) |
| Plant protection (IPM) applications, with re-entry and pre-harvest intervals | **built 2026-07-30** — same migration, deliberately: the PHI is a *harvest gate*, and shipping it later would have meant an untestable placeholder (§5f) |
| Irrigation / feeding record | **built** — migration 0052 + `app/api/irrigation.py` (third router on `/cultivation`) + a Feeding tab on the harvest board: dated, room-level solution log (volume, feed/runoff EC/pH, recipe, method), optional batch scope for a multi-cultivar room. The last remaining Phase 2 record named above |
| AHU filter pull/refit record (§18) | **built** — migration 0053, `biosecurity_events` (`kind='ahu_filter'`) |
| Disinfection-mat refill + strip verification (§20) | **built** — migration 0053, `biosecurity_events` (`kind='disinfection_mat'`) |
| Contact plates (drying/curing) and sentinel bioassay (§27) | **built** — migration 0053, `biosecurity_events` (`kind='contact_plate'` / `kind='sentinel_bioassay'`) |
| Gowning / zone-crossing control (§23, §28 control 5) | **built** — migration 0053, `biosecurity_events` (`kind='gowning'`). All four land as ONE table with a `kind` discriminator, not four near-identical ones — see §5c intro. THE invariant: a `fail`/`below_spec` result cannot be recorded without a stated `action_taken` (CHECK constraint + API pre-check) |
| Tasks reference the batch they act on; phase transitions generate the per-phase task set | **built** — migration 0054, `tasks.batch_id` (RLS-scoped cross-org check, since the bare FK doesn't see RLS) + `_generate_phase_tasks` in `app/api/cultivation.py`'s `move_batch`, idempotent per (batch, phase). See §5, "Phase 3 — tasks on top" |
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
