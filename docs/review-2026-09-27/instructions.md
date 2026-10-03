# Review — conformance with the owner's instructions

Branch `claude/weekly-read-flow-setup-yft7if` @ `807d60f`. Read-only static review.

## Summary

The owner's floor-level instructions from 2026-09-05 are mostly in the code: the department model (CU/PR/IR, sub-departments, rooms), QA on the floor, batch registration, the journey lanes, the mother bank and the owner's ID conventions, phase windows, trichome records, the date picker and the `[NEEDS INPUT]` contract. Where it breaks down is **potency**. The plan's backend landed (`qc_products`, conformance and history endpoints), but its two QC steps never did: plan commit 2 (the product A4 page and CoQ product conformance) and plan commit 6 (the product catalogue UI). Git history goes 0ad6230 → b4c0dee → 7fe5418 → cd15825 → 08c2209 → 87c3053, with no QC-frontend or CoQ-product commit. So:

- a CoQ still grades only against the August ladders, which the owner superseded;
- approving the catalogue silently removes the grade from every later CoQ;
- the owner's later potency decisions are in none of the code: no block on issuance (09-06), regrade + OOS + deviation (09-06), and fitted tolerances "everywhere" (09-18).

`HANDOFF.md` lists several questions the owner already answered as open. SCOPE, README and SPEC still describe a non-GMP task tracker.

Counts: **3 high, 7 medium, 4 low**.

Sources:
- **M** = owner message (`owner-messages.md`).
- **Q** = the owner's answer to an AskUserQuestion prompt, recovered from the session transcript.
- **P** = `/root/.claude/plans/drifting-wibbling-bentley.md`.
- **D** = a decision recorded in `docs/`.

Credentials that appear in the messages are omitted.

---

## 1. Instruction register

| ID | Date · src | Instruction (paraphrase) | Status | Evidence |
|---|---|---|---|---|
| R01 | 07-30 · D | Individual plant IDs, and a batch number per flowering room (`CULTIVATION-DESIGN-2026-07.md:31-37`) | SUPERSEDED by R33 (09-05 batch number = strain + MMYY + nn) | `cultivation.py:454-473` |
| R02 | 07 · D | WWF is a non-GMP planning tool, not part of the QMS; e-signature out of scope (`SCOPE.md`) | CONTRADICTED by the code: CoQ issuance plus Annex 11 signatures. The owner never re-decided | `qc/signatures.py:13-27`; INS-09 |
| R03 | 08-29 · M | DB1_REGULATORY and DB3_PP_CURRENT go into RAGflow for the app and the Letta agents | PARTIAL. Declared `pending_ingest`; the owner deferred the ingestion (Q 08-29 18:03) | `docengine/agents/fleet.yaml:251-271` |
| R04 | 08-29 · Q | Leave letta-scy7 alone; tell the owner which agents lack sources | IMPLEMENTED | no `scy7` in code; `fleet.yaml:251-257` |
| R05 | 08-29 · Q | Fix the custody gap: one physical sample, one custody record | IMPLEMENTED | tasks `0063`; `qc/custody.py:205-230` |
| R06 | 08-29 · Q | Configure the orchestrator's host-exec tool properly | IMPLEMENTED (tool detached) | `docengine/tests/test_fleet.py:1031` |
| R07 | 08-29 · Q | Retrieval for both corpora lives in RAGflow; the owner ingests DB3/DB01 himself | IMPLEMENTED | `fleet.yaml:258-271` |
| R08 | 09-02 · M | eCOA_SS = stability dataset; eCOA_DB = eCoA_DATABASE; link water testing later | IMPLEMENTED | `fleet.yaml:229-237,266` |
| R09 | 09-04 · M | Excel tracker (CoQ Parameter Tracker v9, Batch Coverage, Parameters) for the eCoA agents | IMPLEMENTED (outside the app) | `docs/coq-tracker/*` |
| R10 | 09-04 · M | Sync the in-app DB with the Drive `CoQ_Analysis_Master` | NOT IMPLEMENTED. Design only. The owner asked 09-06 16:29/18:02 what the blocking decisions mean; no answer is on record | `docs/ECOA-MASTER-SYNC-DESIGN-2026-09.md:106-132` |
| R11 | 09-04 · M | Rename pre-created accounts to `<dept>_<function>` with a temporary credential relaxation (details held by the owner) | PARTIAL. Done by a direct DB write on the old VM (transcript 09-04 14:26). The repo provisioner still makes `tt.<dept>.mgr` with random passwords | `backend/scripts/provision_test_accounts.py:2-10,88-99`; INS-10 |
| R12 | 09-04 · M | Trial `qc_mgr` account with a temporary credential relaxation; drop the password rules "for now, not production" | IMPLEMENTED in the production env only (production password floor lowered; frontend floor removed in `03222f7`). Nothing tracks reverting it | `config.py:44`; INS-10 |
| R13 | 09-04 · M+Q | DocEngine UI: chat, canvas, comments, presets. Q: "chat + presets first", "chat edits the doc directly" | IMPLEMENTED (the agreed first slice) | `web/gf/qmsstudio-view.js:207-280`; `docengine/app/main.py:286,336,356` |
| R14 | 09-05 · M | Never invent facility specifics: put `[placeholder]` and report it; existing dev content may stay | IMPLEMENTED | `docengine/app/needs.py:1-63`; `qmsstudio-view.js:387-417` |
| R15 | 09-05 · M | Date picker (day/month/year) that always opens on today, highlighted | IMPLEMENTED; no native date inputs remain | `web/gf/datepicker.js:95-200` |
| R16 | 09-05 · M | Certificate-of-quality code fields: pre-fill the constant part, caret after it | PARTIAL | `codefield.js`, used only at `cultivation-view.js:754,816` and `qmsstudio-view.js:354`; INS-12 |
| R17 | 09-05 · Q | SOP code uses underscore (`QASOP_031`); sub-lot separator `_01` | IMPLEMENTED | `cultivation.py:136` (pattern rejects `/`); commit `9e99643` |
| R18 | 09-05 · M | CU_MGR can open cultivation rooms and register/initiate batches | IMPLEMENTED | `facility.py:52-56`; `cultivation.py:78-82,531` |
| R19 | 09-05 · M | PR_MGR owns everything from harvest onward, nothing before | PARTIAL. Dry/close only; can open only `dry` rooms; trimming, curing and packaging not modelled | `harvest.py:117`; `facility.py:53-56` |
| R20 | 09-05 · M+Q | CU runs clone/import/seed up to and including the cut ("cultivation records the cut") | IMPLEMENTED | `harvest.py:106-113` |
| R21 | 09-05 · M+Q | Cloning and Nursery are sub-departments of Cultivation | IMPLEMENTED (tasks `0064` `dept_family`). Production departments still to be created per rollout (UNVERIFIED) | `demo_org.py:383`; `DEPARTMENT-MODEL` rollout |
| R22 | 09-05 · M+Q | Irrigation department; only IR_MGR writes feeds | IMPLEMENTED | `irrigation.py:48`; `roles.py` `MANAGER_ROLES` |
| R23 | 09-05 · Q | Department managers open/edit their own rooms | IMPLEMENTED | `facility.py:48-56` |
| R24 | 09-05 · M | Batch initiation available to everyone involved, not admin-only | IMPLEMENTED for managers, executives and QA. Base `USER` cultivation staff cannot see the board (`list_batches` needs `ELEVATED_ROLES`). Whether they should is UNVERIFIED intent | `cultivation.py:478`; `modules.js:41` |
| R25 | 09-05 · M | QA, CEO, COO and CU register a batch: number, strain from the ImB specs, plant count | IMPLEMENTED | `cultivation.py:78-82,125-141`; `cultivation-view.js:737-816` |
| R26 | 09-05 · M | Animated bar at the top: current position and next step | IMPLEMENTED (label defect, INS-11) | `cultivation-view.js:272,307-416` |
| R27 | 09-05 · M | CU and QA start a clone run with its propagation-material spec; the initiator sets the date | IMPLEMENTED (date defaults to facility today) | `propagation.py:88-92,152-163` |
| R28 | 09-05 · M | Mother bank: strain, phenotype, count per strain, unique ID, last cut, generations, room/pot, age | IMPLEMENTED | `propagation.py:307-373` |
| R29 | 09-05 · M+Q | The two ImB PDFs are official; grade nominals must match them | PARTIAL, and SUPERSEDED on tolerance by R45. Data and tables exist; CoQ grading and UI never left the ladders | `imb_products.json`; `qc/products.py`; INS-01, INS-02 |
| R30 | 09-05 · M | QA moves batches through phases and edits the cultivar master (and the mother bank) | IMPLEMENTED | `cultivation.py:78,412,429,755`; `propagation.py:88` |
| R31 | 09-05 · M | Many batches at different stages on the board at once | IMPLEMENTED | `cultivation-view.js:388-416` |
| R32 | 09-05 · M | Mothers show the strain's potency tested so far (average and individual values) | PARTIAL. Empty in practice | `propagation.py:301-331,740-800`; INS-06 |
| R33 | 09-05 · M | Batch number `GP072501` = abbreviation + MMYY + nth cloning batch of that month | IMPLEMENTED. Agent choice: period = registration month (AD-7) | `cultivation.py:454-473` |
| R34 | 09-05 · M+Q | Mother ID `GP26_S1M03-2_nnn`, campaigns numbered facility-wide; clone ID `…-xx.nnn` with xx = 00–99 | IMPLEMENTED. Cuttings start at 01 (AD-4) | `plantids.py:56-63`; `propagation.py:429-448` |
| R35 | 09-05 · M+Q | Cloning 7–14 d (imported clones "some days more"); veg 14–17 d; flower 6–9 wk; trichome checks with documented records; harvest/"course"/defoliation = GACP→GMP | IMPLEMENTED. The "7 days" is the agent's number; label issue in INS-11 | `cultivation.py:102-110`; `trichome.py:88-112` |
| R36 | 09-06 · M | A CoQ outside its product window is **not** blocked from issuance | Vacuously true: no product verdict exists at all | `qc/coq_aggregation.py:89-124`; INS-01 |
| R37 | 09-06 · M | Tolerance at most ±10 % of nominal; 1–6 grades per strain, not overlapping | NOT IMPLEMENTED as validation | `qc/products.py:278-292`; INS-13 |
| R38 | 09-06 · M | Optionally pick a Product Specification at batch registration (or none, for a clone work order) | IMPLEMENTED | `cultivation.py:130-135,215-229` |
| R39 | 09-06 · M | Out-of-grade result → falls to the next grade, shown visually, formal OOS on batch disposition, deviation handed to Cultivation and Production | NOT IMPLEMENTED | INS-04 |
| R40 | 09-06 · M | Grade scheme (E = D; F trim/dry officially CNC but run as D; curing/packaging D; corridors …; C rooms unclassified); colour-code the layout by grade | NOT IMPLEMENTED | INS-07 |
| R41 | 09-06 · M | Strain spellings "as in the specifications" | CONTRADICTED for PUM and CLE; open for the 4 disputed names | INS-05 |
| R42 | 09-06 · M | "Another representation" of the floor plan | IMPLEMENTED | tasks `0069`; commit `488b869` |
| R43 | 09-07 · M | Analyse where the range builder fits in the app | IMPLEMENTED as analysis; none of its gaps built | `docs/RANGE-BUILDER-INTEGRATION-2026-09.md` |
| R44 | 09-18 · M | Analyse all the spec/CoQ/iCoA/template work and adopt it into the app as one function | PARTIAL. Analysis given in chat (transcript 09-18 15:57–16:23); no repo artefact; nothing built | — |
| R45 | 09-18 · M | Flat ±10 % is stale; the fitted approach applies **everywhere**; a sparse strain gets full tolerance (e.g. nominal 26) | NOT IMPLEMENTED; HANDOFF recasts it as a timing question | INS-03 |
| R46 | 09-16/09-24 · M | Engine UI showing processes and reasoning; canvas with edits, interruptions, approvals | NOT IMPLEMENTED (design only; trace is on PR #55) | `docs/DOCENGINE-CANVAS-DESIGN-2026-09.md` |
| R47 | 09-24 · M | People act only after a step completes | IMPLEMENTED in design | design doc, "Decided" 1 |
| R48 | 09-24 · M | Fresh audit gate; amendments per option A; update the design doc | IMPLEMENTED (doc) | commit `bee6ae6` |
| R49 | 09-24 · M | How to build a live, human-checked QC certificate tracking system under EU GMP/CSV (question) | Advisory. Conflicts with SCOPE.md | INS-09 |
| R50 | 09-16 · Q | "Sync the potency builder into the repo" | PARTIAL. PR #53 has build `2026.09.16-27`; the later `-28` (two-per-page PDF) is not in git | INS-14 |
| B01–B16 | 09-07 → 09-16 · M/Q | Potency Range/Spec Builder: toggles, sliders, borders, auto-propose, new strain, pills (SPC DRAFTS Purely→Tetra / Tetra→Versa / FINISHED + PP/Versa split + compare), credentials footer (work email, no phone, inconspicuous), splash screen, Mass Effect theme, revert to the PP leaf, random colour scheme, WWF font, mobile swipe, Versa nominals preselected at ±10 %, stability results in PP / out of Versa, `＊` experiment batches excluded, colour and height per initial/retest pair, PDF 2–3 strains per A4 page | OUT OF THIS BRANCH (separate app, `tools/potency-spec-service` on PR #53). Spot-check on `63474db`: work email present, no `+389` number, pills, Compare, splash and Mass Effect present; B16 exists only in `-28` | `origin/claude/sync-potency-spec-service` |

---

## 2. Findings

### INS-01 [high] owner-instruction — CoQs never grade against the official product catalogue; approving the catalogue removes the grade from every later CoQ

**Where**
- `web/gf/qccoa-view.js:762-765` and `642-653`. The compile form offers `qcq-cultivar`, captioned "Freezes the APPROVED potency ladder", plus free-text `qcq-product`. It never sends `product_id`.
- `backend/app/api/qc/coq_aggregation.py:89-124`. `_coq_disposition` handles ladders only.
- `backend/app/api/qc/coq_docx.py:184-205`. `_coq_grade_value` renders ladder grades only.
- `backend/app/api/qc/products.py:387-391`. Approving a product supersedes the cultivar's ladder.

**What happens**
1. The Head of QC approves `GP_THC26:CBD1`. The GP ladder becomes SUPERSEDED (products.py:388-391).
2. QC compiles a GP CoQ from the UI with cultivar GP. `coq_aggregation.py:238-245` looks for an APPROVED ladder, finds none, and stores `potency_spec_id = NULL`.
3. `_coq_disposition` returns `None`, so both the CoQ and the .docx carry **no grade line at all**.

Before any product is approved, CoQs keep grading on the August ladders. The owner declared those superseded on 09-05. In the Q of 22:37 he was asked where the official specs should apply, including CoQ grading, and answered that nominals must be the ones in the PDFs.

The 09-06 decisions assume a product verdict exists: "outside the window prints but is not blocked", and regrade + OOS. That verdict does not exist.

**Evidence**
- Read the compile path end to end.
- `git log` since 09-05 has no commit for plan step 2 ("Product A4 page + CoQ conformance") or step 6 ("Frontend QC").
- `docs/PRODUCT-CATALOGUE-2026-09.md` "Open" admits "a product-graded CoQ today shows no grade at all".

**Fix**
- Add a product select to the compile form that sends `product_id`.
- Add a product branch to `_coq_disposition`: window containment, plus `matching`/`nearest` taken from `products.product_conformance`.
- Add `product_code` / `product_conforms` to `_coq_out`, and a product string to `_coq_grade_value`.

### INS-02 [high] owner-instruction — The catalogue has no UI; the only visible potency import is the superseded ladder set, and nothing stops a ladder being re-approved

**Where**
- `web/gf/qcpotency-view.js:1-13,160-175`. The view is still "per-cultivar potency ladders" with "Import the owner catalogue (71 strains, DRAFT)".
- `web/gf/api.js:371-380`. Of 10 product helpers, only `qcProducts` has a caller (`propagation-view.js:318`).
- `qcProductDocumentUrl` points at `/qc/products/{id}/document`, a route that does not exist. The routes in `qc/products.py` are at lines 145-432; `spec_html.py` only has `:71,:198`.
- `web/gf/cultivation-view.js:696-697` sends users to "QC → Product catalogue", a view that does not exist.
- `backend/app/api/qc/potency.py:314-343`. Ladder approval has no `qc_products` guard.

**What happens**
- **Mother bank.** Registering a mother requires an APPROVED product (`propagation-view.js:322-325`; `MotherIn.product_id` is required). No screen can import or approve a product. On any org where nobody has hand-called `POST /qc/products/import` and `/approve`, the bank the owner asked for (R28) cannot be used from the app.
- **Wrong import.** The single import button in QC loads the August ladders the owner retired. A DRAFT ladder approved after the products restores the retired scheme as the only grading path the UI has (see INS-01). The doc's own rule, "two live schemes would be two answers to one question", is not enforced.

**Evidence**
- `grep` for product API callers across `web/` and `tests/frontend`.
- Route list from `@router` in `qc/*.py`.
- Plan commit 6 is absent from `git log`.

**Fix**
- Build plan commit 6: a product-catalogue mode on `qcpotency` with import (dry-run, then real), list, approve/supersede, potency history and the A4 link. Implement the `/document` route or drop the helper.
- Hide the ladder import once products exist.
- In `approve_potency_spec`, return 409 when the cultivar has an APPROVED product.

### INS-03 [high] owner-instruction — The 09-18 decision (flat ±10 % is stale; fitted tolerances everywhere) appears nowhere in the app

**Where**
- `backend/app/plantids.py:35-38` (`window_for` = ±10 %).
- `backend/app/api/qc/products.py:278-292` (±10 % default).
- `backend/app/data/imb_products.json` (`window_rule` ±10 %, 42 rows).
- `docs/HANDOFF.md`, "Product questions" (only "whether to extract the DP code now or after #52").

**What happens**
The owner (M 2026-09-18 16:21) said the old ±10 % flat grading "is not gonna work", the fitted approach "is applicable everywhere", and a sparse strain gets full tolerance. The agent restated it at 16:23: "the fitted DP algorithm becomes the one way ranges get computed anywhere in the app, and the ImB PDFs' flat ±10 % rule and the old per-cultivar ladder are both retired as grading methods."

Nothing changed. The facility now has two potency specifications with different numbers:

| Source | Cap Junky grades | CJ28 window top |
|---|---|---|
| The owner's finished specs (separate service, fitted) | 14/17/20/24/28 | 29.59 % |
| WWF `qc_products` | 20/24/26/28 | 30.79 % |

Everything in WWF that reads a window uses the retired numbers: batch target product, mother IDs (the grade in `GP26`), conformance, and any future CoQ grade. None of the four integration gaps in `RANGE-BUILDER-INTEGRATION-2026-09.md` is built:
- ladder-level create;
- cultivar-level history;
- window provenance;
- a server-side solver.

**Evidence**
- Transcript 2026-09-18T16:13–16:23.
- `grep -ri "fitted\|solveTolerances"` over code: nothing outside `docs/tools/`.

**Fix**
- Record the decision in PRODUCT-CATALOGUE and HANDOFF.
- Add `POST /qc/products/ladder` (transactional, explicit windows, provenance in `source`/`notes`).
- Load the FINISHED fitted specs as DRAFT products and approve them with a second person.
- Mark `imb_products.json` as reference-only.

### INS-04 [medium] owner-instruction — The out-of-grade rule (next grade, visual flag, formal OOS, deviation to CU+PR) is not built and not tracked

**Where**
- `backend/app/api/qc/products.py:213-250`: `/conformance` returns `matching`/`nearest` and has no caller.
- `qc/oos.py`: no potency or product hook.
- `docs/POTENCY-DATA-2026-09.md:126-129` admits "not built".

**What happens**
When a batch's Total THC falls outside its target product:
- no regrade is shown;
- no OOS is opened against the batch disposition;
- no deviation reaches Cultivation or Production.

This is exactly the case the owner described on 09-06 18:02. `HANDOFF.md` does not list it as open work.

**Evidence**
- `grep` for regrade/next-grade/OOS-on-potency.
- Read `oos.py` and `products.py`.

**Fix**
After INS-01, at compile or approve, when the value is outside the product window:
- show a "regraded to <nearest>" chip;
- raise an OOS draft linked to the batch disposition;
- `safe_emit` a deviation to the cultivation and production departments.

This needs non-overlapping windows (INS-03) for "next grade" to be unambiguous.

### INS-05 [medium] owner-instruction — Strain names ignore the owner's "as in the specifications" answer, including two names both controlled sources agree on

**Where**
- `backend/app/data/imb_products.json`: `strain` is `Pure Michigan` and `Clemosa`; `strain_printed` is `Pure Michigen` and `Clemosa A Bud`.
- `backend/app/api/qc/products.py:446`: the import uses `row["strain"]`.

**What happens**
- The owner answered on 09-06 18:02: "CORRECT AS IN THE SPECIFICATIONS FOR EVERY STRAIN AND POTENCY GRADE".
- `PRODUCT-CATALOGUE-2026-09.md` itself says PURE MICHIGEN is the spelling in both controlled sources, that "Pure Michigan" is wrong either way, and that "A Bud" is part of the Clemosa name.
- The import still creates cultivars `Pure Michigan` and `Clemosa`, and those names print on boards and CoQs.
- For the four names the two sources dispute, HANDOFF lists the question as "still unanswered" without recording that the owner did answer (pointing at the per-strain folder) or what the remaining conflict is.

**Evidence**
- Parsed `imb_products.json`.
- Read the import loop.

**Fix**
- Use `strain_printed` for PUM and CLE.
- For JD, GRC, SJ and WC, re-ask with the concrete choice ("per-strain folder: Jelly Donutz / Graps and Creme / Sleepy Joy / Wedding Crasher" versus the merged PDF), then patch the existing cultivar names.

### INS-06 [medium] owner-instruction — "Potency tested so far" on mothers is empty in practice

**Where**
- `backend/app/api/propagation.py:301-331` (`_MOTHER_SQL` tested) and `740-800` (`mother_potency`: product plus traced only).
- `web/gf/propagation-view.js:94-96,466-492`.

**What happens**
Both the bank column and the panel count only APPROVED CoQs whose `product_id` equals the mother's product. Three things keep that empty:
- The UI never sets `product_id` on a CoQ (INS-01).
- The certificate-level source that `products._potency_history` already computes is not used for mothers.
- The historical results live in the workbook, and the sync is unbuilt (R10).

The owner asked (09-05 22:28) for the average and the individual Total THC % of the "Specification Strain". Grape Pie has dozens of results in the workbook, yet every GP mother reads "not tested yet".

**Evidence**
- Read the SQL.
- Checked that no UI code path creates a product-bearing CoQ.

**Fix**
- Add labelled cultivar-level and certificate-level sources to the mother potency endpoint and column, reusing `_potency_history`.
- Land INS-01 and R10.

### INS-07 [medium] owner-instruction — The owner's cleanliness grades are not applied, and there is no grade colouring

**Where**
- `backend/app/data/facility_layout.json`: `grade` absent on all 191 rooms.
- `web/gf/facility-view.js:429-453,479-499`: grade appears only as a detail-panel field and a free-text edit; the plan colours by zone.
- `docs/FACILITY-LAYOUT-2026-09.md`, "Grades — ANSWERED".

**What happens**
- The owner (09-06 16:29) wants to colour-code the layout by grade, and (18:02) gave the rules: E = D; F trimming/drying "officially CNC but we consider it as Grade D and we act like it is"; curing/packaging D; perimeter and cultivation corridors CNC; C rooms unclassified.
- None of this is seeded or drawn.
- The doc recommends recording trimming/drying as `grade = "CNC"`, the opposite of how the owner said the site treats them. That is the agent's call, not the owner's (AD-15).
- HANDOFF still lists "which scheme" as unanswered.

**Evidence**
- Parsed the register.
- Read the view.

**Fix**
- Seed grades for the rooms the rules cover unambiguously; leave the three documented gaps null.
- Add a "colour by grade" mode.
- Confirm with the owner how trimming/drying are recorded (CNC with a note, or D).

### INS-08 [medium] stale-doc — HANDOFF shows answered questions as open, makes one false claim and omits owner decisions; a new session will re-ask

**Where**: `docs/HANDOFF.md`, "Product questions (from #52's body, still unanswered)" and "Work not started".

**What happens**
- **Grades**: answered 09-06 18:02. FACILITY-LAYOUT says "ANSWERED".
- **Spellings**: answered 09-06 18:02.
- **CoQ blocking**: answered "NO" on 09-06 16:29 and 18:02. HANDOFF's "today it prints 'does not conform' and still renders" is false (INS-01).
- **Omitted entirely**:
  - the 09-18 fitted-tolerance decision (INS-03);
  - the out-of-grade OOS rule (INS-04);
  - the missing plan commits 2 and 6 (INS-02);
  - the temporary credentials to revert (INS-10);
  - the builder build that is not in git (INS-14).

The owner complained explicitly (09-27 02:23/02:25) that new sessions forget prior work. HANDOFF is the file meant to prevent that.

**Evidence**: cross-read against the owner messages and the code cited above.

**Fix**: rewrite the list as "answered → action pending", with dates and quotes.

### INS-09 [medium] stale-doc — SCOPE, README and SPEC contradict the GxP features the owner asked for (still open, from `docs/APP-REVIEW-2026-07.md` F-3)

**Where**
- `docs/SCOPE.md:1-8,52-62`.
- `README.md:5-8,36`.
- `docs/SPEC.md` (the e-signature and PDF lines).

**What happens**
- **The docs say**: WWF is "not part of the QMS", has "none of the QC-laboratory / CoA / compliance modules", and e-signatures are out of scope.
- **The app does**: issues CoQs as QP-release input with Annex 11 re-authenticated signatures (`qc/signatures.py:13-27`), runs OOS investigations, and hosts a QMS Studio zone that SCOPE itself calls "authoritative".
- **The owner** (09-24 09:41) asks how to make certificate issuance EU-GMP/CSV grade.

An inspector reading SCOPE concludes these signatures and certificates have no regulated standing. Either the scope or the features is wrong, and only the owner can decide which.

**Evidence**: read the three docs and the signatures and CoQ modules.

**Fix**: put the zone decision to the owner. Then rewrite SCOPE with three zones (the QC LIMS as a GxP computerized system), and update README and SPEC.

### INS-10 [medium] owner-instruction — Temporary credential relaxations ("for now", "just for a short while") are untracked

**Where**
- The production env password floor (transcript 09-04 15:10).
- The frontend floor removed (`03222f7`).
- Ten accounts with a temporary credential relaxation (09-04 14:26/14:56).
- `admin`/`admin` requested for "a short while" (09-14 10:09).
- `backend/scripts/provision_test_accounts.py:2-10,88-99`; `docs/TEST-ACCOUNTS.md:8-20`; `docs/HANDOFF.md` security list.

**What happens**
The owner scoped all of these as temporary because "this is not a production version". The site is production.
- HANDOFF's security list omits every one of them.
- The repo's provisioner and TEST-ACCOUNTS still produce `tt.<dept>.mgr` with random passwords, so the owner's naming scheme cannot be reproduced after the 2026-09-19 VM rebuild.
- Nobody owns deleting the trial `qc_mgr` account.

UNVERIFIED: whether these settings survived the VM migration (production was not contacted).

**Evidence**
- Transcript excerpts.
- `config.py:44`; `auth.py:260`.

**Fix**: add a dated "temporary relaxations to revert" item to HANDOFF (min length back to 12, rotate the ten plus admin, delete `qc_mgr`), and document the owner's naming scheme in TEST-ACCOUNTS.

### INS-11 [low] owner-instruction — The journey's GACP→GMP step reads "Harvest · cure · defoliation", putting curing before drying

**Where**: `web/gf/cultivation-view.js:290-293`, and the Drying step at `:295`.

**What happens**
- The owner wrote "harvest, course and defoliating end of GACP". "Course" more plausibly means coarse trim / de-bucking.
- The owner graded curing rooms GMP Grade D, and FACILITY-LAYOUT puts curing (F108) in the GMP wing after drying.
- The bar shows curing on the cultivation side of the handoff, before Drying.
- The MK label is `Жетва · сушење · дефолијација`: "drying" appears inside the cut step and again as the next step.

The owner's meaning is UNVERIFIED; the MK duplication is verified.

**Fix**: confirm with the owner, then relabel (e.g. "Harvest · coarse trim · defoliation") and fix the MK text.

### INS-12 [low] owner-instruction — The code pre-fill is missing from the QC fields the owner named

**Where**
- `web/gf/qccoa-view.js:762,814`
- `qcecoa-view.js:678`
- `qcsample-view.js:385`
- `qcoos-view.js:273`

**What happens**
- The owner's example was the certificate-of-quality code.
- CoA and CoQ numbers are minted by the server (`qc/certificates.py:44-55,317`), which is fine.
- Every QC batch-id input is still plain text; `GF.codeField` is used only for cultivation batch codes and SOP codes.

**Evidence**: `grep codeField`.

**Fix**: ask the owner for the certificate and batch conventions, then apply `codeField` with the established head.

### INS-13 [low] owner-instruction — Product windows are not checked against the owner's ±10 % ceiling

**Where**: `backend/app/api/qc/products.py:278-292`.

**What happens**: `POST /qc/products` with `GP_THC26`, `window_min` 10, `window_max` 40 passes (only `max > min` and nominal-inside are checked), and a second person can approve it. The owner (09-06 18:02) set the ceiling at ±10 % of nominal.

**Evidence**: read `_resolve_window`.

**Fix**: reject a tolerance above 10 % of nominal (with `_EPS`). Flag overlaps with sibling DRAFT/APPROVED products of the same cultivar.

### INS-14 [low] owner-instruction — The live potency-spec-service is newer than the only copy in git

**Where**: `origin/claude/sync-potency-spec-service` @ `63474db` (09-16 09:28, `__APP_VERSION 2026.09.16-27`), compared with the build shipped at 09-16 13:33 (`-28`, `buildTwoPerPage`).

**What happens**: the owner's 09-16 13:16 request (two strains per A4 page, and export of all PP finished specs) exists only in the deployed image and the session scratchpad. A rebuild from PR #53 silently loses it. HANDOFF presents #53 as the builder's source.

**Evidence**: diffed the PR #53 file against the scratchpad `potency-spec-service/web/index.html` (190 diff lines, including `buildTwoPerPage`). Current production content is UNVERIFIED.

**Fix**: commit the `-28` build to PR #53.

---

## 3. Product decisions the agent made and presented as settled

- **AD-1** `_IMPORT_QUARANTINE_DAYS = 7` (`cultivation.py:107`). The owner said imported clones stay "some days more" (Q 09-05 22:37). The plan flags it `[NEEDS INPUT]`, but `PROPAGATION-2026-09.md` lists "up to 7 days more" under "settled by the owner".
- **AD-2** Nursery shares the clone leg's 7–14-day window (`cultivation.py:102-103`). The owner gave no nursery duration.
- **AD-3** `stock_no` is numbered per (campaign, product, mother_no, generation) (`propagation.py:429-448`). The owner's answer to the scope question was "alternative naming convention provided".
- **AD-4** Cuttings are numbered from 01 (1 + prior runs). The owner wrote xx = 00–99.
- **AD-5** Clone numbers `.nnn` restart per cutting rather than per mother. The owner's wording ("incremental number of clones produced from that mother plant") is ambiguous.
- **AD-6** Limits: generation ≤ 9, mother_no ≤ 99, more than 999 clones per cutting → 422 (`propagation.py:124-126`).
- **AD-7** The batch-code period is the MMYY of the registration day, not the cloning month the owner defined. Sub-lot codes count toward the sequence (`cultivation.py:459-473`, `LIKE prefix%`).
- **AD-8** Journey label "cure" (INS-11).
- **AD-9** PR_MGR may open only `dry` rooms (`facility.py:55`). No kinds exist for trimming, curing or packaging.
- **AD-10** Trichome vocabulary and limits: verdicts immature/approaching/ready/overripe; percentages must sum to 98–102; never a gate (`trichome.py:47-50,112`).
- **AD-11** Harvest moisture-loss plausibility band 60–92 %, reported not refused (`harvest.py:132-133`).
- **AD-12** With overlapping windows, `nearest` = the highest-nominal product the value satisfies (`products.py:213-250`). The owner's rule is "the next grade above or below, suitably".
- **AD-13** A batch or clone run may target only an APPROVED product; a mother requires one (`cultivation.py:215-229`; `MotherIn`).
- **AD-14** Approving a product supersedes the cultivar's ladder (`products.py:387-391`).
- **AD-15** Trimming/drying recommended as `grade="CNC"` (FACILITY-LAYOUT), against the owner's "treat as Grade D".
- **AD-16** QA is the classification authority on the facility register (`PATCH /facility/layout`: ADMIN, executives, QA).
- **AD-17** The RAGflow dataset name `DB3_PP_CURRENT_unified` is kept (`fleet.yaml:271,507,560,643,681,790`). The owner's Drive folder is `DB3_PP_CURRENT`, and the owner never picked a name (Q 08-29 18:03 deferred ingestion). If he ingests under the folder name, every DB3 agent stays ungrounded.
- **AD-18** The weekly GMP document stays per-department, exact match ("a new capability nobody asked for", DEPARTMENT-MODEL).
- **AD-19** The clone-run date defaults to the facility's today. The owner said the initiator "has to set" it.

**Open questions put to the owner, still unanswered, where the code already assumes an answer**

| Question | What the code assumes |
|---|---|
| Security manager write access to decon/waste (DEPARTMENT-MODEL "Still open") | read-only |
| Whether the DocEngine regulatory check should block (DOCENGINE-CANVAS-DESIGN §1) | advisory |
| Whether the six repeated ImB pages are reprints (plan "Assumptions") | reprints; the catalogue is 42 products |
| Whether QC may compile against a product other than the batch's target (plan) | assumed allowed; unenforced |
| The eCoA sync's landing zone, credential and stability handling (R10) | nothing built |

---

## 4. Project docs that are now false

1. **`docs/SCOPE.md`** (whole document): non-GMP, not QMS, no e-signature. See INS-09.
2. **`README.md:5-8`**: "none of the QC-laboratory / CoA / compliance modules". Wrong: there are 11 `web/gf/qc*-view.js` views.
   - `README.md:36`: roles "admin · HOD · QA · QP · operator · viewer". `roles.py` defines 14 roles.
3. **`docs/SPEC.md`** stack table:
   - React 18/TS/Vite (the frontend is vanilla-JS `web/gf`);
   - SQLAlchemy + psycopg3 (it is `asyncpg`);
   - Qdrant/VoyageAI (RAGflow, per `fleet.yaml`);
   - "hand-authored idempotent SQL" migrations (two alembic chains);
   - "six roles";
   - e-signature and PDF "out of scope" (`qc/signatures.py`; docengine `/documents/{did}/pdf`).
4. **`docs/HANDOFF.md`**: see INS-08. Also, "DocEngine canvas — implementation not requested yet" understates the owner's repeated "I want" (09-04, 09-16, 09-24); it is better framed as "owner to schedule".
5. **`docs/PRODUCT-CATALOGUE-2026-09.md`**:
   - Header "Status: implemented".
   - The routes table lists `GET /qc/products/{id}/document`, which does not exist.
   - Rollout step 5, "compile CoQs with `product_id`", has no UI.
   - `[NEEDS INPUT]` on "which is the controlled state" was answered 09-18.
6. **`docs/PROPAGATION-2026-09.md`**:
   - "What the ImB Product Specifications are in this system" still says ladders (`qc_potency_specs`).
   - The "Who registers" table denies QA moves, cultivar master and mother bank; its own later section and `cultivation.py:78` grant them.
   - `clone_runs.potency_spec_id` was dropped in `0067`.
   - **Rollout says "import via `POST /qc/potency-specs/import`, then approve per cultivar"**. Following it imports and approves the superseded ladders.
7. **`docs/DEPARTMENT-MODEL-2026-09.md`**: the matrix row "Create cultivar / batch / plants, move phase" shows QA_MGR as "—". QA was added on 09-05 22:28.
8. **`docs/RANGE-BUILDER-INTEGRATION-2026-09.md`**: "The decision this does not settle … until the owner settles that". Settled on 09-18.
9. **`docs/TEST-ACCOUNTS.md`**: `tt.*` naming and random passwords, plus "API-only, never direct SQL". The 09-04 change was a direct DB write using the owner's naming scheme.
10. **`CLAUDE.md`**, Disk section ("/opt on kvm4 … 93 % / ~14 GB free"): describes the pre-2026-09-19 VM. HANDOFF says `/app` is at 55 % with 87 GB free.
11. **Code comments that now mislead**:
    - `backend/app/api/cultivation.py:42-49`: "registers from … ladders in `qc_potency_specs`".
    - `web/gf/cultivation-view.js:283-286`: "Durations are NOT in this list … the app has not been told the plan's phase lengths". The server now supplies them.
    - `web/gf/qcpotency-view.js:1-13`: presents the 71-strain ladder catalogue as the specification.
