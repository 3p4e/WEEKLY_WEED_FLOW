# Review: cultivation domain + database schema

Reviewed at `807d60f`. Scope: `backend/app/api/{cultivation,propagation,harvest,trichome,irrigation,facility,facility_layout}.py`, `backend/app/plantids.py`, `backend/app/data/*.json`, both alembic chains, `schema.*.sql`, `backend/tests/conftest.py` purge order, the cultivation design docs and the owner's 2026-09-05 decisions (including the AskUser answers in `review/_askuser.txt`).

## Summary

The cultivation side is layered cleanly: a batch record, plant rows materialised in resumable chunks, dated batch-level phase events, a PHI gate on the harvest, and a mother bank whose IDs the server builds from columns. The schema is in good shape:
- All 73 tasks tables have RLS, FORCE and an org policy, and an audit trigger wherever one is expected. Every post-baseline table carries guarded grants.
- Both alembic chains upgrade and then `downgrade base` cleanly on PG 16.13. At head, the alembic-built dump matches `schema.*.sql` line for line after CI normalisation.
- The `purge_org` order satisfies the FK graph and is identical to `demo_org`'s wipe order.
- `facility_layout.json` satisfies every CHECK in 0068/0069.
- Every product window equals `window_for(nominal)`.

The weak spots are in the application code:
- Dates are unbounded. A future `harvested_on` or a backdated room move defeats the PHI gate.
- The identity scheme breaks at the edges: legacy plant IDs collide, the default mother path breaks lineage, and clone IDs are only resumable while the clone runs never change.
- There is no phase state machine, and a move resets the phase clock even when only the room changes.

Production is already at tasks 0069 / users 0012, so no pending migration puts production data at risk.

Verification setup: I loaded the schema into a scratch database on the local PG16 cluster (not the shared test DBs) to reproduce findings, and I ran a full alembic round trip there. I did not run pytest.

---

### CS-01 [high] security/data-integrity — The recorder can bypass the pre-harvest-interval gate with a future `harvested_on` or a backdated room move

**Where:** `backend/app/api/harvest.py:180` (`HarvestIn.harvested_on`, no bound), `:579` (`when = body.harvested_on or …`), `:399-418` (`_PHI_BLOCK_SQL`: blocks only when `clear_on > $4 = when`; the room is resolved from `plant_phase_events` by `occurred_on`), `:609-626`; `backend/app/api/cultivation.py:156` (`MoveIn.occurred_on`, no bound), `:769-785`; UI `web/gf/harvest-view.js:372` (`GF.dateField('hv-c-date', {})`, no `max`).

**What happens:**
1. CU_MGR sprays room F1 today with a 21-day PHI.
2. `/harvest-clearance` tells them it "clears on 2026-10-18".
3. They POST `/cultivation/harvests` with `harvested_on: "2026-10-18"` while cutting today. The block list is empty, no QA override is needed, and the lot is written with a future date.

Second route: move the batch within the same phase to room F2 with `occurred_on` set to yesterday. The PHI query now finds F2 as the batch's room on the application date, and the room-scoped spray no longer blocks.

The module states that "a recorder cannot wave away their own block — if they could, the gate would be decoration." This finding is exactly that.

**Evidence:** I ran the verbatim `_PHI_BLOCK_SQL` against the scratch schema:
- 1 blocking row on the site's today, 0 rows on today + 21.
- After inserting the event `move_batch` writes for a room move backdated to yesterday: 0 rows (1 before the move).
- `test_harvest.py` has no future-date or backdated-move case.

**Fix:** Return 422 when `harvested_on` or `occurred_on` is after the site's today. Return 422 when a move's `occurred_on` is earlier than the batch's current `phase_since`, so phase events stay monotonic. Optionally, evaluate PHI at `max(harvested_on, site today)`.

### CS-02 [high] correctness — Legacy plant IDs collide across batches of the same cultivar with the same clone date, and the second batch's plant fill 500s permanently

**Where:** `backend/app/plantids.py:66-67` (`<date>_<cultivar>_<seq>`, seq per batch); `backend/app/api/cultivation.py:651-655`, `:687`, `:707-712` (`ON CONFLICT (batch_id, seq)` only); `plants_org_id_plant_code_key UNIQUE (org_id, plant_code)` (0045:128); `backend/app/main.py:41-49` (only the custody indexes are mapped to 409; everything else is re-raised).

**What happens:** Two flowering rooms of Grape Pie are cloned the same day, giving batches GP092601 and GP092602. (Two imported batches of one strain on one day behave the same way.) The owner's model is "one cultivar in one flowering room", so this is a normal plan.
- Batch 1 fills as `20260927_GP_0001…`.
- Batch 2 computes the same codes. The first chunk raises `UniqueViolationError` on `plants_org_id_plant_code_key`, which reaches the client as a 500.
- Every retry fails at the same chunk, so batch 2 never gets plant IDs.

The legacy remainder of a mother-fed batch collides the same way.

**Evidence:** Reproduced in scratch PG16: the second insert fails with `duplicate key value violates unique constraint "plants_org_id_plant_code_key" … (…, 20260927_GP_0001)`. `test_clones_carry_their_mothers_id_…` uses different clone dates (09-01 and 09-20), so the collision is never exercised.

**Fix:** Make the legacy ID unique by construction. The smallest change is `<clone-date>_<batch code>_<seq>`: the batch code is unique per org and already starts with the cultivar abbreviation. The alternative is to continue the suffix across the `(cultivar, date)` prefix. Confirm the format with the owner; the design doc says "seq incrementing from 1 within the batch".

### CS-03 [high] owner-convention/data-integrity — A later-generation mother registered from a parent gets a new mother number (and any campaign), so its permanent ID names the wrong selection line

**Where:** `backend/app/api/propagation.py:489-515` (only the parent's product is checked; `_next_numbers(…, body.mother_no=None, …)` returns the next free mother number, `:442-443`); `web/gf/propagation-view.js:410`, `:424` (the parent chooser filters on product and generation only; the mother-number placeholder is the next free number); `update_mother` (`:537-574`) cannot change segments; there is no DELETE route and the FKs are RESTRICT.

**What happens:** GP26_S1M03-1_001 exists and S1 already has M01–M04. The user registers generation 2, picks that parent and leaves "mother no." blank. The server stores **GP26_S1M05-2_001** with `parent_code = GP26_S1M03-1_001`. Choosing campaign S2 instead gives GP26_S2M01-2_001.

The owner wrote: "-2 second generation clone from the initial mother plant clone … all clones made from this -2 (second) cloning generation of motherplant selection S1M03 will have codes like GP26_S1M03-2_020-xx.nnn". Every clone later cut from this plant carries the wrong M number, and nothing can correct it.

**Evidence:** Traced the server path and the form. `test_the_id_segments_are_chosen_or_suggested` passes `mother_no=1` explicitly, so the default path is untested.

**Fix:** When `parent_id` is given, take `campaign_id` and `mother_no` from the parent. Return 422 if the body contradicts them, and have the form do the same. Keep `stock_no` counting per line.

### CS-04 [medium] data-integrity — "M03 of campaign S1" can name several different mothers, and the next-number read is unlocked

**Where:** `backend/app/api/propagation.py:429-448`, `:511-528`; `backend/alembic_tasks/versions/0067_mother_identity.py:95-96` (the line key includes `product_id`). Only `create_campaign` (`:250`) and the cutting counter (`:678`) take advisory locks; the plan said "next-number rules under advisory locks".

**What happens:**
- **Explicit mother number:** with GP26_S1M03-1_001 in the bank, registering an OPM22 mother with `mother_no=3` in S1 is accepted as OPM22_S1M03-1_001. The product differs, so the line key does not collide, even though `mother_no` is meant to count per campaign across strains.
- **Two auto-numbered registrations at once for different products:** both read max = 4, and both become M05.
- **Two registrations on the same line at once:** both read the same next stock number. The second hits `mother_plants_line_key` / `mother_plants_org_id_code_key` and gets a 500, not the documented 409.
- A campaign's `cultivar_id` is never checked against the mother's product.

**Evidence:** Read the code path and constraints. The global audit lock does not serialise this because the `max()` read happens before any audited write.

**Fix:** Take `pg_advisory_xact_lock(hashtext('mother:'||campaign_id))` before `_next_numbers`. Return 422 when a `mother_no` is already used in the campaign by another product or cultivar, and enforce the campaign cultivar. Map the unique violation to 409.

### CS-05 [medium] correctness — Clone-ID allocation is "a pure function of seq" only while the batch's clone runs never change, and nothing freezes them

**Where:** `backend/app/api/cultivation.py:657-687` (segments are recomputed on every call from every run linked to the batch, with no `cr.status` filter), `:644-650` (no terminal or inactive check); `backend/app/api/propagation.py:700-738` (PATCH can relink `batch_id` while a run is `started`), `:624-697` (new runs can be linked to a batch that is already filled).

**What happens:**
- **(a) Relinked run:** run R (mother M, cutting 01, 60 cuttings) feeds batch X, and X is filled with M-01.001…060. Someone PATCHes `R.batch_id = Y` (same cultivar) and fills Y. Y computes M-01.001 again, gets a `UniqueViolation` and a 500, and can never be filled, while X's plants still claim mother M.
- **(b) Earlier run added to a part-filled batch:** the segments shift, so the resume writes codes that already exist, and it 500s. On a complete batch the new run's clones never get their mother IDs, yet `per_mother` reports that they did.
- **(c) Failed runs:** the mothers of a `failed` run (cuttings that did not root) still name plants.
- **(d) Filled after close:** `POST /batches/{id}/plants` on a harvested batch creates `active` plants in a closed batch.

**Evidence:** Read the code path together with `plants_org_id_plant_code_key`. None of these paths is tested.

**Fix:**
- Once any plant carries a run's lineage, refuse (409) to relink that run or to link new runs to the batch; or persist the allocation plan on the first fill.
- Exclude `status='failed'` runs.
- Refuse the fill on terminal or inactive batches.

### CS-06 [medium] correctness/contract — A room change always resets the phase clock, the UI cannot change a room without changing phase, and moves have no transition rules or row lock

**Where:** `backend/app/api/cultivation.py:755-811` (`phase_since` is reset unconditionally at `:771`; no from→to rules; the phase is read without `FOR UPDATE`); `web/gf/cultivation-view.js:869` (the current phase is excluded from the move targets).

**What happens:**
- **Room-only move resets the clock:** a flowering batch on day 30 is moved F1→F2 through the API with `to_phase=flower`. `phase_since` becomes today, the board's harvest window restarts at 42–63 days from the move, and `days_in_phase` shows 0. The UI cannot express this move at all.
- **No transition rules:** any-to-any moves are accepted (flower→clone, clone→harvested, veg→mother). A future `occurred_on` produces a negative `days_in_phase`.
- **Race with a terminal move:** a move that lands after a concurrent terminal move leaves `phase='flower', is_active=false`. The batch drops off the board without being terminal, and its plants have already been marked `harvested`.

**Evidence:** Read both sides of the contract.

**Fix:**
- When `to_phase == phase`, change the room only and keep `phase_since`; offer this in the UI.
- Use `SELECT … FOR UPDATE`, or `WHERE id=$ AND phase=$old`, in the move.
- Bound `occurred_on` (see CS-01).
- Define the forward transitions and require an explicit correction flag for backward ones.

### CS-07 [medium] data-integrity — Per-plant status cannot record partial destruction, the terminal move stamps destroyed plants "harvested", and the per-plant exception schema is never written

**Where:** `backend/app/api/cultivation.py:789-796`; `backend/app/api/waste.py:279-317` (batch-level `plant_qty` only). Nothing in `backend/app` writes `plants.reason`, the `plants.status` values `culled`/`moved`, `plant_phase_events.plant_id`, or the `cull`/`note` event kinds (grep: the only `UPDATE plants` is the terminal settle).

**What happens:** A batch of 2000 plants has 150 destroyed on a waste manifest and 1850 harvested. The move to `harvested` sets all 2000 plant rows to `harvested`. The plant-level record contradicts the destruction register, and the card shows `plants_active = 2000` until the close.

**Fix:** Settle only the undeclared remainder, or add the per-plant cull/destroy route that `0045` designed for (`plant_id`, `reason`). At minimum, document that per-plant status is not authoritative.

### CS-08 [medium] owner-instruction — A mother's "tested so far" shows only CoQs that name the exact product row, not the strain's history

**Where:** `backend/app/api/propagation.py:301-334` (`_MOTHER_SQL`: `q.product_id = m.product_id`), `:741-804`. Compare `backend/app/api/qc/products.py:161-211`, which already computes `cultivar_level` and `certificate_level`.

**What happens:** `qc_coq.product_id` has existed only since 0066 and is set only on CoQs compiled against the new catalogue. Every earlier CoQ and every certificate result is invisible on the mother, including the tracker data the plan calls "the 'tested so far' data" (BG1024 → 21.80, …). A mother of a strain with test history therefore shows `n=0`. The owner asked for "Total THC% scores tested so far from that Specification Strain". Re-issuing a product under a new `doc_version` creates a new row id, which also splits the history by version.

**Evidence:** Read the code path. The production row counts are UNVERIFIED (production was not queried).

**Fix:** Serve the product's `_potency_history` (the three labelled levels) from `/mothers/{id}/potency`, and key the product level on `product_code` rather than on the row id.

### CS-09 [medium] numbering — The next batch number counts rows instead of taking the max, uses the registration month, has no 99 cap, and the head is not enforced

**Where:** `backend/app/api/cultivation.py:454-475` (`count(*) … LIKE head||mmyy||'%'`, month from `facility_today()`, `{seq:02d}`); `:531-560` (the code is checked against a pattern only).

**What happens:**
- **Count, not max:** with GP092601 and GP092603 on file, the count is 2, so the suggestion is GP092603 and the save returns 409.
- **Registration month:** a batch cloned on 30 Sep and registered on 1 Oct is suggested as GP1026xx. The owner defines nn as "the nth cloning batch of that strain in that month".
- **No cap:** the 100th batch becomes `GP0926100`.
- **Head not enforced:** the server accepts any code for a cultivar (for example `XYZ` for GP). That breaks the prefix count and the plan's attribution of a lot's strain from its batch-code head.
- **Concurrent saves:** two saves of the same suggestion hit `plant_batches_org_code_key` and return a 500.

**Evidence:** Read the code path.

**Fix:**
- Take `max(nn)+1` over `^<head><mmyy>(\d{2})$`, using a regex rather than LIKE because `_` is a LIKE wildcard.
- Take mmyy from `clone_date` when one is given.
- Return 409 past 99.
- Return 422 unless the code starts with the cultivar code.
- Map the unique violation to 409.

### CS-10 [low] numbering — Mother-number and stock-number caps surface as 500s

**Where:** `backend/app/api/propagation.py:439-448`, `:513`, `:520`; 0067 CHECKs `mother_no <= 99` and `stock_no <= 999`.

**What happens:** For the 100th mother in a campaign, `_next_numbers` returns 100 (it is unbounded). The insert raises `CheckViolationError`, which becomes a 500, and `next-code` suggests "M100". The 1000th stock plant fails the same way. A generation derived from a parent is unbounded, while the API caps explicit generations at 9.

**Fix:** Return 409 with an explanation when the next number exceeds the cap, and apply one generation bound in both places.

### CS-11 [low] owner-convention — Cutting numbers run 01–99, but the owner said "xx is 00-99"

**Where:** `0066_product_catalogue.py:210-211`, `:220-221` (CHECK 1–99); `propagation.py:679-684`; `plantids.py:62-63`.

**What happens:** The first cutting prints `-01` and a 100th cutting is impossible. If the floor labels its first cutting `-00`, every printed clone ID differs from the app by one.

**Fix:** Confirm with the owner. If the numbering is zero-based, change the CHECK to 0–99 and start at 0.

### CS-12 [low] contract — The mother ID's head comes from `cultivar.code`, but the form's preview uses the product-code acronym

**Where:** `backend/app/api/propagation.py:514` (`pr["cultivar_code"]`); `web/gf/propagation-view.js:417-418` (`product_code.split('_')[0]`); `backend/app/api/qc/potency_import.py:99-110` (the product import attaches a product to a cultivar found **by name**, which may have a different code).

**What happens:** Suppose a pre-existing cultivar has code "gp" and name "Grape Pie". GP_THC26 attaches to it, so the saved ID is `gp26_S1M01-1_001` while the preview showed `GP26_S1M01-1_001`. Whether any production cultivar code differs from its acronym is UNVERIFIED.

**Fix:** Compose the ID from one source; the owner's "strain abbreviation" is the product acronym. Alternatively, flag an acronym/cultivar-code mismatch at import.

### CS-13 [low] correctness — Trichome check dates are unbounded, there is no correction route, and the phase is not checked

**Where:** `backend/app/api/trichome.py:53-141`; "latest" is chosen by `ORDER BY checked_on DESC` in `cultivation.py:501-503` and `harvest.py:471-473`.

**What happens:** A check typed as 2027-09-27 stays "latest" on the board and the harvest form forever, and there is no PATCH or DELETE to fix it. Checks are also accepted on clone and veg batches.

**Fix:** Reject `checked_on` later than the site's today, and ignore future-dated rows when picking the latest check. Optionally allow a check only in `flower`/`drying`.

### CS-14 [low] facility-clock — Mother and plant `status_since` come from the database's `DEFAULT CURRENT_DATE` (UTC)

**Where:** `backend/app/api/propagation.py:521-528` (the column is omitted), `backend/app/api/cultivation.py:709-712`; `schema.tasks.sql:753`, `:865`.

**What happens:** A mother registered at 00:30 Skopje time (22:30 UTC) gets yesterday's `status_since`. `test_facility_clock.py` bans `CURRENT_DATE` in app code, but these database defaults slip past it.

**Fix:** Bind `SITE_TODAY_SQL` explicitly, as `create_batch` does.

### CS-15 [low] correctness — Explicit null or empty-string values cause 500s

**Where:**
- `backend/app/api/facility_layout.py:196-205`: `{"is_active": null}` is written as NULL into a NOT NULL column.
- `backend/app/api/propagation.py:552-561`: `room_id: ""` skips validation because the check is truthy, then fails as an invalid UUID.
- `backend/app/api/propagation.py:717-725`: the same for `batch_id: ""` and `room_id: ""`.

**Fix:** Skip None for non-nullable columns, and validate with `is not None`, as `facility_layout.py:184-190` already explains.

### CS-16 [low] owner-instruction — Flowering is not tied to the flowering rooms

**Where:** `backend/app/api/cultivation.py:541`, `:766-768` (any active room is accepted). The gap is acknowledged as open in `docs/DEPARTMENT-MODEL-2026-09.md` ("Room ↔ phase coupling").

**What happens:** The owner said flowering happens "in one of the 6 available flowering rooms", but a batch can be created in, or moved to, `flower` in a dry or veg room.

**Fix:** Return 422 when the room kind does not match the target phase.

### CS-17 [low] permission/contract — The terminal move's "needs a reason" rule is enforced only in the UI

**Where:** `backend/app/api/cultivation.py:153-157` (`reason` is optional); `web/gf/cultivation-view.js:936-939`.

**What happens:** A direct API call can close or destroy a batch of 2000 plants with no recorded reason.

**Fix:** Return 422 on a move to `harvested`/`destroyed` without a reason.

### CS-18 [low] dead-code — The legacy ladder data on `GET /cultivation/cultivars` is unused, and several docstrings are stale

**Where:**
- `backend/app/api/cultivation.py:345-364` (`_ROMAN`, `_spec_out`), `:385-395` (the LATERAL join over `qc_potency_specs` plus the folded tiers), `:408` (`"spec"`).
- The module docstring at `:42-49` still describes registering from ladders.
- `propagation.py:629`: "Snapshots the cultivar's APPROVED product specification" is no longer true.

**What happens:** No frontend file reads `cv.spec` (grep), and no test asserts it. The plan's commit 7 said to drop it.

**Fix:** Remove the join, the helpers and the field, and correct the docstrings.

### CS-19 [low] test-hygiene — `purge_org` clears `parent_id` on every org's mothers, and the update is unnecessary

**Where:** `backend/tests/conftest.py:97-104` (`UPDATE public.mother_plants SET parent_id=NULL` with no `WHERE org_id`).

**What happens:** The update rewrites lineage for every org in the shared test DB. The comment's premise is wrong: PG16 deletes parent and child in one statement despite the self-referencing RESTRICT FK.

**Evidence:** Scratch test: `DELETE FROM m WHERE org=1` over a 3-level self-FK chain with RESTRICT deleted all 3 rows. `demo_org.py`'s identical wipe order has no such update and works.

**Fix:** Delete the block, or add `WHERE org_id=$1`.

### CS-20 [low] doc-drift — Two permission tables still deny QA the floor writes the owner granted on 2026-09-05

**Where:** `docs/DEPARTMENT-MODEL-2026-09.md:133` (QA "—" for "Create cultivar / batch / plants, move phase"); `docs/PROPAGATION-2026-09.md:45-47`, `:52`. The same PROPAGATION doc contradicts itself at `:140`.

**What happens:** The code (`_WRITERS` including `QA_MGR` in `cultivation.py:78` and `propagation.py:88`) matches the owner, but the docs a reviewer or auditor reads say the opposite.

**Fix:** Update both tables.

---

**Checked and found sound:**
- RLS, FORCE, org policy and audit trigger on every tasks table (the only exemptions are the intended `audit_log`, `events`, `notifications` and the custom-policy tables).
- Guarded grants on every post-baseline table (0041 and 0057 use loops).
- Both chains round-trip (`upgrade head` → `downgrade base` leaves only `alembic_version`), and the dumps match `schema.*.sql`.
- The 0067 guard runs as the superuser, so it sees every row despite FORCE RLS.
- The `purge_org` order satisfies the FK graph (no RESTRICT or NO ACTION inversions).
- The layout import is idempotent on (floor, code) and preserves the judgement columns.
- The product import is idempotent on (code, version), and the JSON has no duplicate codes.
- Campaign numbering and cutting numbering are correctly serialised.
- `_plan_out` uses the site clock and plain date arithmetic, so it has no DST exposure.
- The imported-clone +7 days on the cloning maximum matches the owner's AskUser answer ("both should leave … at roughly the same time, plus the imported clones can stay some days more").
