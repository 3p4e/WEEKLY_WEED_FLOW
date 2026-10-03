# Re-review: cultivation domain + tasks database schema

Reviewed at `0984dc8` (branch `claude/weekly-read-flow-setup-yft7if`), against the first review at `807d60f` (`docs/review-2026-09-27/cultivation-schema.md`, CS-01…CS-20, and the CS/INS/FE-11/AD entries of `docs/REVIEW-2026-09-27.md`). Scope as briefed: `cultivation.py`, `propagation.py`, `harvest.py`, `trichome.py`, `irrigation.py`, `facility.py`, `facility_layout.py`, `plantids.py`, `facility_layout.json`, the tasks alembic chain (0070, 0071), `schema.tasks.sql`, `conftest.purge_org`, `demo_org._TASKS_WIPE_ORDER`, the area's tests, and the four views only for their contract with these routes.

## Summary

The cultivation fixes (cf33801, 1c5c884, 80d4e0a, ce7ecdb, 28049c0, d186c01) are real, not cosmetic: every date a recorder supplies is now bounded by the facility clock, phase moves walk a declared path under a row lock, a room change keeps the phase clock, the legacy plant id carries the batch code, the mother line key drops the product (0070) with the next-number reads under an advisory lock, and the mother's "tested so far" is the strain's three-source history. 19 of the 20 CS findings are closed with a pinning test each; CS-11 stays open by a recorded decision (D-1) that needs the owner. The schema is sound: on a scratch database `alembic upgrade head` reaches 0071, its dump is byte-identical to `schema.tasks.sql` under CI's normalisation (4 365 lines), and `downgrade base` leaves nothing (0 tables / sequences / functions / policies / enum types). 0070 and 0071 touch disjoint objects; 0071's `DROP SEQUENCE` is safe (no column default or app code referenced the eight sequences at 549b617 or at HEAD).

One new problem is serious: the mother-bank checks introduced by ce7ecdb compare **product row ids**, while the product workstream's C-3 (a2c0084) retires every old-version row when a new document version is approved. The first fitted-spec approval will therefore freeze the bank: no later generation can be registered from any existing mother and no new stock plant can join any existing line, with 422s whose message names the same product code on both sides. The rest is small: a garbled activity sentence, draft manifest lines settling plants, a narrow fill race, a correction route the UI cannot reach, and a decision-register row that under-reports what was left ungraded.

Verification: static reading of every file above; `python3` summary of the layout register; `node`-free reading of the views; the alembic round trip and dump diff on two throw-away databases (`wwf_review2_cs_*`, created and dropped on the local cluster, never the shared `wwf_*_test` databases); no pytest, no production, no GitHub writes.

---

## Closure table

| Finding | Status | Evidence (file:line at 0984dc8; commit; pinning test) |
|---|---|---|
| CS-01 future `harvested_on` / backdated move defeats PHI (§2.2) | **CLOSED** | `harvest.py:594-599` refuses `harvested_on > today`; `cultivation.py:884-894` refuses a move after today or before `max(last event, phase_since)`; `harvest-view.js:372` (`max: GF.facilityToday()`), `:492`. 80d4e0a. Tests `test_harvest.py:792 test_a_cut_cannot_be_dated_past_the_interval`, `test_cultivation.py:738 test_a_move_is_bounded_by_the_facility_clock_and_stays_in_order`. D-4 (PHI judged on the cut's own day) is a defensible reading of the "optionally" in the original fix. |
| CS-02 legacy plant ids collide across same-day batches (§2.8) | **CLOSED** | `plantids.py:81-84` `<clone-date>_<batch code>_<seq>`; `cultivation.py:787`; a cross-batch `(org, plant_code)` violation now answers 409 with the id (`:819-827`). 80d4e0a. Test `test_cultivation.py:771` asserts `20260927_GP092601_0001` vs `…GP092602_0001` and a disjoint set. `docs/CULTIVATION-DESIGN-2026-07.md:229` updated (1c5c884). |
| CS-03 later generation gets a new mother number (§2.9) | **CLOSED** (see CS2-01 for a new hole in the same path) | `propagation.py:682-702`: campaign and mother_no come from the parent, a contradicting body is 422; `propagation-view.js:466-475` pre-fills and locks both fields. ce7ecdb / d186c01. Test `test_propagation.py:418` (`GP26_S1M03-2_001`, 422 on S2 or M05). |
| CS-04 "M03 of S1" names several mothers; unlocked next-number read | **CLOSED** (residual in CS2-01) | 0070 line key `(org, campaign, mother_no, generation, stock_no)` (`schema.tasks.sql:2481`, verified on the scratch DB); `propagation.py:710` `pg_advisory_xact_lock('mother:<campaign>')` before `_line_owner_or_422` (`:614-625`) and `_next_numbers` (`:583-611`); campaign cultivar enforced `:575-580`; unique violation → 409 `:733-737`. cf33801 / ce7ecdb. Tests `test_propagation.py:456`, `:486` (two concurrent registrations get M01/M02). |
| CS-05 clone ids consistent only while runs never change; failed runs; fill after close | **CLOSED** | `propagation.py:261-272` `_batch_unfrozen_or_409`, called at `:850` (new run → filled batch), `:939-942` (relink either side); `cultivation.py:741-743` closed batch → 409; `:760-762` failed run excluded unless plants already carry it. 80d4e0a / ce7ecdb. Tests `test_propagation.py:575`, `test_cultivation.py:977`. |
| CS-06 room move resets clock; no transition rules; race | **CLOSED** | `cultivation.py:208-235` `_transition` (`_PATH`, `_OPTIONAL_STOPS`, backward only for `_CORRECTORS` `:902-910`); `:896-901` same-phase move = room change, `:925` keeps `phase_since`; `:405` `FOR UPDATE OF b`; UI "Change room" `cultivation-view.js:1112-1140`, corrector list `:125`. 80d4e0a / d186c01. Tests `test_cultivation.py:791`, `:817`, `:857`; `tests/frontend/cultivation-view.test.js:542,599`. |
| CS-07 destroyed plants stamped "harvested" | **CLOSED** per D-7 | `cultivation.py:946-978`: manifest plant count settled `destroyed` off the end of the seq order with the manifest codes in `plants.reason`, remainder `harvested`, plus a `destroy` phase event. 80d4e0a. Test `test_cultivation.py:877` (15 destroyed / 25 harvested). Residual: `plants.status` `culled`/`moved`, `plant_phase_events.plant_id` and the `cull`/`note` event kinds are still never written (dead schema, unchanged); see also CS2-03. |
| CS-08 / INS-06 mother "tested so far" empty in practice | **CLOSED** | `propagation.py:356-429` three labelled sources (`_COQ_PRODUCT_SQL` any product of the cultivar, `_COQ_CULTIVAR_SQL`, `_CERT_SQL`), one measurement per lot; bank column reads the strain figure (`:496-499`, `propagation-view.js:105-108`); `/mothers/{id}/potency` returns `strain`, `sources`, `product`, `traced` (`:1010-1015`, UI `:539-556`). ce7ecdb / d186c01. Test `test_propagation.py:304` — pins the `coq_product` source with real data; the cultivar-level and certificate sources are asserted only at `n == 0`, so `_CERT_SQL`'s batch-code attribution never runs against a matching row. Compared line by line with `qc/products.py:335-397` (`_TOTAL_LINE`, cultivar-level and certificate reads identical; the product read differs by design: any product of the cultivar vs one row). No drift since a2c0084. |
| CS-09 batch number count/registration month/no cap/head | **CLOSED** | `cultivation.py:527` MMYY from `clone_date`; `:529-534` max+1 over `^<head><MMYY>(\d{2})$`; `:535-538` 422 past 99 (review suggested 409 — either is fine); `:617-620` head enforced; `:640-644` unique → 409. 80d4e0a. Tests `test_cultivation.py:906`, `:927`. |
| CS-10 mother/stock caps as 500s | **CLOSED** | `propagation.py:597-610` 422 with the cap named; `MAX_*` in `plantids.py:90-95` used in both the typed and parent-derived generation bound (`:164`, `:697-700`); cutting cap → 409 `:897-900`. Test `test_propagation.py:506`. |
| CS-11 cuttings 01–99 vs owner's "00–99" | **NOT FIXED — open by decision D-1 / AD-4** | `schema.tasks.sql:300` CHECK 1..99 unchanged; `propagation.py:894-896` starts at 01; 0070's docstring and `docs/PROPAGATION-2026-09.md:154-156` say so. Needs the owner's answer, correctly parked. |
| CS-12 id head from `cultivar.code` vs form's acronym | **CLOSED** | `propagation.py:558-563` `_head` = product-code acronym (fallback cultivar code); next-code returns `acronym` and the form uses it (`propagation-view.js:433`). Test `test_propagation.py:534`. |
| CS-13 trichome dates unbounded, no correction, no phase check | **CLOSED** (phase check was optional; see CS2-05 for the UI half) | `trichome.py:151`, `:198` `_not_after_today`; PATCH `:178-217` validates the three percentages as they will stand; "latest" pickers ignore future rows (`cultivation.py:568-570`, `harvest.py:477-480`). 80d4e0a. Test `test_trichome.py:126`. |
| CS-14 `status_since` from UTC `CURRENT_DATE` | **CLOSED** | `cultivation.py:817` and `propagation.py:727` bind `SITE_TODAY_SQL`; `update_mother` `:774-775`. Asserted in `test_propagation.py:548`. |
| CS-15 null / empty-string 500s | **CLOSED** | `facility_layout.py:190-191`; `propagation.py:764-765`, `:933-936`, `:943-944` (`is not None`). Tests `test_facility_layout.py:342`, `test_propagation.py:551`. |
| CS-16 flowering not tied to flower rooms | **CLOSED** | `cultivation.py:125`, `:238-244`, `:612`, `:916-921` (checked with and without a room change). Test `test_cultivation.py:944`. `docs/DEPARTMENT-MODEL-2026-09.md:168` marks it closed. |
| CS-17 terminal reason only in UI | **CLOSED** | `cultivation.py:911-914`; `MoveIn.reason` `min_length=1` (`:200`). Test `:817` line 831/845. |
| CS-18 legacy ladder on `GET /cultivars` | **CLOSED** | `_ROMAN`/`_spec_out`/LATERAL join gone (grep), docstring `:439-446` and module header rewritten; `propagation.py:83-90` corrected. Test `test_cultivation.py:968`; no `.spec` reader in `web/gf`. |
| CS-19 unscoped `UPDATE mother_plants SET parent_id=NULL` in `purge_org` | **CLOSED** | Removed, comment explains why (`conftest.py:89-96`); order from `decon_tool_log` to `departments` identical to `demo_org.py:82-90`. cf33801. |
| CS-20 permission tables deny QA | **CLOSED** | `docs/PROPAGATION-2026-09.md:41-58`, `docs/DEPARTMENT-MODEL-2026-09.md:131-135` now show QA ✅ and the backward-move asymmetry. 1c5c884. |
| INS-07 grades not applied, no grade colouring | **CLOSED** (D-5; see CS2-06) | `facility_layout.json`: 34 rooms graded (20 E-wing D, 7 trim/de-buck/dry D with the "officially CNC" note, 5 curing/packaging D, 6 cultivation corridors CNC), none duplicated; `facility_layout.py:286` `COALESCE(grade, $17)` fills only nulls, never overwrites QA; `facility-view.js:177-202` "by grade" colouring + legend. 28049c0 / d186c01. Tests `test_facility_layout.py:302`, `:323`; `facility-plan.test.js:363,394,419`. |
| INS-11 journey step "Harvest · cure · defoliation" | **CLOSED** (D-6) | `cultivation-view.js:335` `Harvest · coarse trim · defoliation` / `Жетва · грубо кастрење · дефолијација` (the MK "сушење" duplication is gone). d186c01. |
| FE-11 backend half (batch ↔ product link after registration) | **CLOSED** | `PATCH /cultivation/batches/{id}` (`cultivation.py:667-701`, pre-existing) now has a caller: "Edit batch" `cultivation-view.js:1166-1194`; product validated against the batch's cultivar and APPROVED (`:681-682`). Test `cultivation-view.test.js:632`. |
| AD-1, AD-2 | as recorded | `cultivation.py:141` (`nursery` shares 7–14), `:146` (`_IMPORT_QUARANTINE_DAYS = 7`). |
| AD-3 | corrected as recorded | 0070 + `propagation.py:583-611` (stock per campaign/mother_no/generation; product a property of the number). |
| AD-4 | open (D-1) | see CS-11. |
| AD-5 `.nnn` per cutting | as recorded | `cultivation.py:786` (`n - first + 1` per segment). |
| AD-6 caps | as recorded | `plantids.py:90-95`. |
| AD-7 registration month | corrected as recorded | `cultivation.py:527`. |
| AD-8 | superseded by D-6 | see INS-11. |
| AD-9 PR_MGR opens `dry` rooms only | as recorded | `facility.py:52-56`. |
| AD-10 trichome vocabulary, 98–102 sum, never a gate | as recorded | `trichome.py:56-59`, `:121-127`; `harvest.py:469-473` (not counted into `clear`). |
| AD-11 60–92 % band, reported not refused | as recorded | `harvest.py:136-137`, `:223-226`. |
| AD-13 APPROVED product only; mother requires one | as recorded | `cultivation.py:349-351`, `propagation.py:552-554`, `:874-876`. This is what CS2-01 turns into a lock. |
| AD-15 | withdrawn as recorded | register carries `D` with the "Officially CNC; operated and recorded as Grade D" note on E80, E81, F96, F104–F106, C153. |
| AD-16 QA classifies the register | as recorded | `facility_layout.py:49`. |
| AD-19 run date has no default | corrected as recorded | `propagation.py:198` (`started_on: date`, required); UI refuses an empty date before the request (`propagation-view.js:672`). |

**Chain check (0069 → 0070 → 0071).** `0070.down_revision = "0069"`, `0071.down_revision = "0070"`; 0070 only swaps `mother_plants_line_key`, 0071 only touches `qc_coq`, `qc_signatures`, `qc_oos_register` and eight sequences — no shared object, so 0070's key change cannot conflict with anything 0071 assumes. The old sequences had no `OWNED BY` and no `nextval()` default in the 549b617 schema and no reference in `backend/app` at HEAD, so `DROP SEQUENCE IF EXISTS` without CASCADE is correct. Round trip verified as described in the summary. 0070's safety argument ("a table holding two mothers on one line across products makes `ADD CONSTRAINT` refuse") is the right failure mode: the deploy's migrate-before-swap step would abort with the data intact.

**Instruction conformance of the fixes (DECISIONS §1 vs §2b D-1…D-7).** D-2 (backward moves are QA authority's), D-3 (one stop at a time), D-4, D-6, D-7 do not contradict any §1 row; the owner's 2026-09-05 phase list is clone → veg → flower and "QA should be able to move a batch through its phases", which the code honours (QA_MGR is in `_WRITERS` and `_CORRECTORS`). D-1 keeps the owner's "00–99" unanswered rather than contradicted. D-5 is honest about what is null but incomplete about the E wing — CS2-06.

---

## Findings

### CS2-01 [high] data-integrity/design — Approving a new document version of the catalogue freezes the mother bank: no later generation, no new stock on any existing line

**Where:** `backend/app/api/propagation.py:552-555` (`_product_or_422` accepts APPROVED only), `:673-681` (parent must have the SAME `product_id` row), `:614-625` (`_line_owner_or_422` compares `m.product_id <> $3` — row ids), `:641-642` (next-code runs the same check); `web/gf/propagation-view.js:443` (parent chooser filters `x.product_id === pid`); `backend/app/api/qc/products.py:601-611` (approving a product supersedes the same code's other rows AND every APPROVED product of the cultivar with another `doc_version`); `schema.tasks.sql:2793` (`UNIQUE (org, product_code, doc_version)` — a new version is a new row id), `:3609`.

**What happens:** The owner's 2026-09-18 decision makes the fitted specifications the controlled state and C-3 records that approving the first product of a new `doc_version` retires the strain's old-version rows (`test_products.py:189` pins exactly this). Take the bank as it will be used: `GP26_S1M03-1_001` registered against `GP_THC26:CBD1` v.03 (row A). QC then imports and approves the fitted set — `GP_THC26:CBD1` "fitted 2026-09-15" (row B) — and row A becomes SUPERSEDED.
1. Register generation 2 from `S1M03`: the form offers only APPROVED products, so `product_id = B`; `parent.product_id (A) != B` → 422 "`GP26_S1M03-1_001` is not a `GP_THC26:CBD1` mother — a clone cannot change its specification strain". Sending A instead → 422 "`GP_THC26:CBD1` is SUPERSEDED". The UI never offers the parent at all (`:443` filters on the row id).
2. Register a second stock plant on line M03 (`mother_no=3`, product B): `_line_owner_or_422` finds row A's code → 422 "M03 of this campaign is a `GP_THC26:CBD1` line — a mother number names one line, and `GP_THC26:CBD1` cannot take it". `GET /mothers/next-code?mother_no=3` refuses the same way, so the form cannot even preview.
3. Nothing repairs it: `update_mother` (`:747-787`) cannot change the segments or the product, there is no DELETE, and the FKs are RESTRICT.
Every line registered before a re-issue is therefore closed to growth, which contradicts the owner's convention that a line continues across generations (`GP26_S1M03-2_…`), and the message on both refusals names the same product code on both sides.

**Evidence:** Traced both refusal paths and the UI filter; read the supersession statements in `approve_product`; confirmed the partial unique index allows one APPROVED row per code so a re-issue is necessarily a new id. `test_propagation.py:418/456` use one product row throughout, so the version case is untested. Production has no mothers yet (0070 docstring), so no row is broken today; the trigger is the first fitted approval after the first mother.

**Fix:** Compare product identity by `product_code` (the acronym+grade the id prints), not by row id: in `_line_owner_or_422` join and compare `pr.product_code <> $3`; in the parent path compare `parent_product_code != pr["product_code"]`, and let the parent path default `product_id` to the current APPROVED row of the parent's code (or accept the parent's own row even when SUPERSEDED — the id's grade comes from the nominal, which the code fixes). Mirror the filter in `propagation-view.js:443` (`x.product_code === prod.product_code`). Add a test that approves a new `doc_version` between two registrations on one line.

### CS2-02 [low] contract — The `batch_added` and `batch_moved` activity sentences print `undefined` for the room, strain and count

**Where:** `backend/app/api/cultivation.py:654-658` (params `code, cultivar, plant_count, phase, product_code`), `:988-992` (params `code, old_phase, phase, room_change, generated_tasks`); `web/gf/notifications-view.js:150-155` (reads `p.plant_count`, `p.strain`, `p.room`, `p.old_room`).

**What happens:** Every batch registration renders as "X added 96 × undefined to undefined (flower)" and every move as "X moved undefined × undefined: undefined (veg) → undefined (flower)". The `room_change` flag the fix added is not rendered, so a room change reads as a move to the same phase.

**Evidence:** Both sides read at 549b617 and HEAD — the sentence templates date from the retired `facility.py` write path (which emitted `strain`/`room`), and neither review nor the frontend workstream's 3854447 ("name every event") touched these two cases. Not in the first review.

**Fix:** Emit `room_name`/`to_room_name` and `plant_count` from cultivation.py (the row is already loaded), and rewrite the two templates to `code` + phases + `room_change`; or the converse. Either side alone is a one-line change; the pair is the contract.

### CS2-03 [low] data-integrity — Closing a batch settles plants "destroyed" from DRAFT manifest lines, which can still be deleted afterwards

**Where:** `backend/app/api/cultivation.py:950-952` (sums `waste_manifest_lines.plant_qty` with no manifest status filter), `:959-967`; `backend/app/api/waste.py:92` (`draft → sealed → witnessed → disposed`), `delete_line` (`:361-372`, allowed while draft), `add_line` (`:302-360`, does not refuse a closed batch).

**What happens:** A CU_MGR opens manifest WM-9 and adds a draft line "GP092601: 150 plants" before the count is confirmed. The batch is closed as harvested: 150 plants are stamped `destroyed` with reason "declared destroyed on waste manifest WM-9". The line is then removed (draft lines may be) or the manifest is never sealed. The plant rows now say 150 destroyed on a manifest that lists none, permanently — there is no route that un-settles a plant. The mirror case: a line added after the close (allowed) leaves those plants `harvested`. The yield report (`harvest.py:780-781`) and the destruction reconciliation count lines the same status-blind way, so the *counts* stay consistent; the per-plant record is what drifts.

**Evidence:** Read the settlement, the waste lifecycle and `delete_line`. `test_cultivation.py:877` uses a draft manifest (never sealed) and passes — the test demonstrates the scenario's first half.

**Fix:** Count only lines of `sealed`/`witnessed`/`disposed` manifests in the settlement (and say so in the reason), and have `waste.add_line` refuse a batch in a terminal phase (as `create_harvest` Gate 5 does).

### CS2-04 [low] race — The plant fill reads its allocation plan once, but a run can still join the batch between that read and the chunk loop

**Where:** `backend/app/api/cultivation.py:735-763` (plan read in one `rls()` transaction), `:810-818` (each chunk its own transaction); `backend/app/api/propagation.py:265-272` (`_batch_unfrozen_or_409` counts plants, no lock).

**What happens:** Batch X has run R1 (M1, 60) and 0 plants. `POST /batches/X/plants` reads the plan `[M1 1–60]` and starts writing chunk 1. Concurrently `POST /clone-runs {batch_id: X, started_on: earlier than R1, mothers: [M0 × 30]}` passes the freeze check (still 0 plants committed) and commits. The fill finishes with plants 1–60 = M1 and legacy from 61; the batch's runs now say M0 comes first. A later resume (or any re-read of `per_mother`) computes `[M0 1–30, M1 31–90]` — plant 31 is on file as `M1-01.031` but the plan says `M1-01.001`; nothing is renamed, but `per_mother` and the ids disagree and any resumed fill writes the shifted names.

**Evidence:** Read both paths; the freeze check is a plain count outside any lock. Narrow window, but the module's own promise is "a pure function of seq".

**Fix:** Take `pg_advisory_xact_lock(hashtext('fill:'||batch_id))` in the plan-reading transaction and in `_batch_unfrozen_or_409`'s callers, or `SELECT … FOR UPDATE` the batch row in both.

### CS2-05 [low] dead route / contract — The trichome correction route has no API wrapper and no UI

**Where:** `backend/app/api/trichome.py:178-217` (`PATCH /cultivation/trichome-checks/{id}`), module docstring `:18-21` ("corrected in place rather than left as a second, contradicting row"); `web/gf/api.js:222-223` (only `trichomeChecks`, `trichomeCheck`); no `trichome-checks/` PATCH anywhere in `web/gf` (grep).

**What happens:** A mistyped percentage or date on a check can be corrected only by a direct API call; from the app the operator's only option is a second check, which is exactly what the route was written to avoid. The `trichome_corrected` notification text (`notifications-view.js:98`) describes an event the app cannot produce.

**Evidence:** grep of `web/gf` and `api.js`. (The trichome *history* list, `GET /trichome-checks`, remains UI-less too — already noted in the first review's frontend report.)

**Fix:** `trichomeCheckPatch(id, b)` in api.js and a correction action on the latest-check line of the batch card; frontend reviewer's area for the form itself.

### CS2-06 [low] instruction-conformance — DECISIONS D-5 under-reports what was left ungraded: the owner said "E means Extraction so it must be Grade D", and 31 E-wing rooms are null

**Where:** `backend/app/data/facility_layout.json` (E wing: 20 rooms D — production, quality labs, warehouses, post-harvest; **null**: 7 airlocks, 8 personnel, 6 utility, 3 waste, 6 circulation, 1 egress, 2 quality); `docs/DECISIONS-2026-09.md` §2b D-5 (names only "F-wing IPC labs, sampling rooms, wardrobes and corridors"); `docs/FACILITY-LAYOUT-2026-09.md:196-205` (does raise the E question — "would sweep in … are they CNC?").

**What happens:** The owner's rule (message 2026-09-06 18:02) has no qualifier for E. The workstream applied it to the rooms whose zone reads as production/quality/warehouse/post-harvest and left the wing's gowning, technical and waste rooms unclassified — a reasonable reading, but a reading. The decision register, which is the place the owner is meant to confirm or correct such readings, does not mention the E-wing exclusions, so the owner reading D-5 will assume E is done.

**Evidence:** `python3` tally of the register by (wing, zone, grade); `test_facility_layout.py:302` asserts `E23` null and 34 graded rooms, so the partial application is pinned as intended behaviour.

**Fix:** Extend D-5 to say which E rooms stay null and why (GMP airlocks and wardrobes are graded by the room they serve; interior vs perimeter corridors cannot be read off the drawing), and ask the owner the FACILITY-LAYOUT §"Open" question explicitly.

---

## Also checked and found sound

- `_transition` is total over the phase vocabulary: terminal phases are refused before it (`:882-883`), `mother` is refused on either side except → `destroyed`, `_PATH.index` cannot raise; `floor = max(...)` cannot see an empty sequence because `plant_batches.phase_since` is NOT NULL (`schema.tasks.sql:806`).
- The batch-code suggestion uses `left(code, n) = head` plus a strict regex, so `GP0826X1`, `GP-SUB` and another cultivar with a longer code are neither counted nor mis-suggested; two saves of one suggestion resolve to 201/409 (`test_cultivation.py:939-941`).
- `_strain_history` and `qc/products.py::_potency_history` still read the same `_TOTAL_LINE`, the same cultivar-level and certificate predicates (including `status IN ('APPROVED','RELEASED')` and the `cultivation_batch`/`batch_id` text join); 0071's `purpose`/`timepoint` columns do not affect either. The two differ only where intended (strain-wide vs one product row).
- The harvest-close settlement and the waste/harvest headcount gates all count the same `waste_manifest_lines` sum, so the numbers agree with each other (CS2-03 is about the per-plant record, not the counts).
- The facility board (`facility.py`) is read-only over `plant_batches` and tolerant of every phase value; `_KINDS_BY_ROLE` still confines PR_MGR to `dry`.
- `facility_layout.py` import: zone written only on insert, grade/notes filled only where null (`:286`), `dry_run` writes nothing; every register row's `wing`/`zone` is in the vocab (the import would 422 otherwise, and the tests import it).
- `purge_org` and `_TASKS_WIPE_ORDER` are identical from `decon_tool_log` to `departments` and satisfy the FK graph (plants before mother_plants, lines before batches/rooms, facility_rooms before departments); `test_demo_wipe_coverage.py` still enumerates the live catalogue.
- Frontend contracts: `cultivationMove` sends `{to_phase, to_room_id, occurred_on, reason}` and reads `kind`/`phase`/`room_id`; the room-change form sends `to_phase: b.phase`; the batch form sends `clone_date`, `product_id`, `clone_source`; the mother form sends the five segments plus `parent_id` and reads `acronym`, `mother_no`, `next_stock_no`, `suggested`, `head`; the potency panel reads `strain`, `sources`, `product`, `traced`, `window`; `harvest-view` caps the date at `GF.facilityToday()`. Status codes assumed by the views (422 past 99, 409 on close race) match the routes.
- The e2e seed (254c7f1) moved to `GGE092701` because the head is now enforced — consistent with the rule, not a test bent to pass. The one-word cultivar-code edits in `test_waste.py`/`test_irrigation.py` are the same.
