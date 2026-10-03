# Review 2 — conformance with the owner's instructions, and the truth of the documentation

Branch `claude/weekly-read-flow-setup-yft7if` @ `0984dc8`. Read-only static review; no production contact; no pytest run.
Sources: the 246 owner messages (`the owner's messages (agent session, 2026-08-27 → 09-27; not in the repo)`; credentials in the 09-09/09-10/09-11 messages are referred to, never copied), the plan `drifting-wibbling-bentley.md`, `docs/DECISIONS-2026-09.md`, `docs/review-2026-09-27/instructions.md`, `docs/REVIEW-2026-09-27.md` §6/§7, and the PR #52 body read live through the GitHub App (read only).

## Summary

The potency gap that dominated the first report is closed in code: a CoQ now names a product, is judged against that product's stored window, is regraded to the product whose window holds the value, notifies Cultivation and Production, and the catalogue has a screen with import (ImB pages and the fitted export), approval, supersession, history and the A4 page. The owner's 09-18 decision is recorded and the server side for it exists (`/qc/products/ladder`, `/qc/products/import-fitted`, explicit windows, ±10 % as a ceiling only). Cleanliness grades are seeded and drawn; the strain renames the owner settled are applied.

Where it is still wrong is mostly in what the record says versus what the code does: the register and three docs say an out-of-window CoQ "is not blocked from issuance" while the code refuses approval — and therefore rendering — until a formal OOS is opened *and closed* (the owner said "NO for now" twice); `HANDOFF.md` lists a settled spelling as disputed and omits one that is; the register says the clone-run date "has no default" while the form pre-fills today; the register says QC batch fields carry the strain head while the two CoQ forms the first review cited are still plain inputs; `PROPAGATION.md`, `README.md`, `SPEC.md` and `DEPLOY.md`'s "Deploying" section still describe the pre-fix (in places the pre-August) system; the PR #52 body the owner will read before merging is two review rounds stale. Of the 14 first-round findings: 7 CLOSED, 6 PARTIAL, 1 NOT FIXED.

Counts: **2 high, 13 medium, 8 low** (INS2-01 … INS2-23).

---

## Closure table (INS-01 … INS-14)

| Id | Status | Evidence at HEAD |
|---|---|---|
| INS-01 CoQ never grades against the catalogue | **CLOSED** | `qccoa-view.js:617-622,657-661,792-798` (compile form offers APPROVED products, sends `product_id`); `coq_aggregation.py:172-202` `_coq_product_disposition`, `:279-280` `_coq_disposition` product branch, `:415-433` compile validates the product; test `backend/tests/test_potency_coq.py:140` `test_coq_graded_against_a_product_reports_conformance`, `:168` (docx line `REGRADED from … to …`), `tests/frontend/qccoa-coq-potency.test.js:109,149`. Commits `97f75f4`, `a85a94b`. Ladder-approval-after-product no longer hides the grade: `potency.py:222-234` `_refuse_when_products_live`. |
| INS-02 No catalogue UI; ladder re-approval unguarded; `/document` route missing | **CLOSED** | `qcpotency-view.js` is the catalogue (import dry-run/real `:110-153`, approve/supersede `:95-105`, A4 `:188-200`, ladders read-only `:206-213`; ladder import offered only while no product exists `:156-166`); route `spec_html.py:179` `GET /qc/products/{id}/document`; guards `potency.py:222-234` (create/approve) and `potency_import.py:156-160` (import) → 409; tests `test_products.py:212,228`, `tests/frontend/qcpotency-view.test.js:64-304` (13 tests). `cultivation-view.js` "QC → Product catalogue" now resolves (nav test `:304`). |
| INS-03 09-18 fitted decision absent | **PARTIAL** | Recorded: `DECISIONS §1` (2026-09-18), `PRODUCT-CATALOGUE` "Decisions recorded 2026-09-27", `POTENCY-DATA` "Decided since", `RANGE-BUILDER-INTEGRATION:107`. Built: `products.py:644-696` `POST /qc/products/ladder` (transactional, explicit windows, provenance), `:819-908` `import-fitted`, `ProductIn.window_min/max` required (`:97-98`), `imb_products.json.window_rule` "REFERENCE ONLY"; tests `test_products.py:361,426,479`. Remaining: the fitted specifications are not in the app (owner must export from the live service and state the document code/version — `HANDOFF` rollout 6); `POST /qc/products` still accepts a single product overlapping its siblings (INS2-06); the ImB ±10 % pages remain the first thing the rollout imports. |
| INS-04 Out-of-grade rule not built | **CLOSED (with INS2-01)** | `coq_aggregation.py:215-240` (deviation to every CU_MGR/PR_MGR at compile), `:243-267` + `:749-751` (approval refused until an OOS naming Total Δ9-THC exists), `products.py:222-263` `nearest_of` / `conformance_of` (`regrade_to`); chips `qccoa-view.js:713-732`; test `test_potency_coq.py:168-230`, `:233`. The sequencing contradicts the owner's "NO for now" — INS2-01. |
| INS-05 Strain names | **CLOSED for PUM/CLE; 4 still with the owner** | `imb_products.json`: PUM `strain="Pure Michigen"` (retired "Pure Michigan"), CLE `"Clemosa A Bud"` (retired "Clemosa"); `products.py:725-748` renames on import; test `test_products.py:535`. JD/GRC/SJ/WC flagged `spelling_disputed`. But SJ carries only "Sleepy Joe" in every field, so the "both spellings resolve to one cultivar" claim fails for it (INS2-03), and `HANDOFF.md:126-128` misstates the four. |
| INS-06 Mother "tested so far" empty | **CLOSED (code)** | `propagation.py:362-431` `_strain_history` reads the three sources (product CoQs, cultivar CoQs, certificates by batch-code head) and rolls them up per lot; `:503-524` `_tested_for` fills the bank column; `:966` `mother_potency`; test `test_propagation.py:304`. Empty until CoQs/certificates exist and R10 (workbook sync) lands — by design, not a defect. |
| INS-07 Cleanliness grades not applied | **CLOSED** | `facility_layout.json`: 28 rooms `D`, 6 `CNC`, 157 null (34 = `FACILITY-LAYOUT` table); notes quote the 2026-09-06 rule; `facility-view.js:177-202,227-228,308,368-399` colour-by-grade + legend/filter; test `tests/frontend/facility-plan.test.js`, `backend/tests/test_facility_layout.py:78-81`. Commit `28049c0`. De-bucking C153 / E80 / E81 graded D by extension — INS2-18. |
| INS-08 HANDOFF shows answered questions as open | **PARTIAL** | Rewritten (`0984dc8`): grades, spellings, block-on-non-conformance now under "Answered and applied"; fitted decision, OOS rule, missing commits, relaxations (via `DECISIONS §3`), #53 staleness (via PRODUCT-CATALOGUE) covered. New errors: Clemosa listed as disputed, Sleepy Joe/Joy omitted (INS2-03); "six CoQs" still "unanswered" though the owner answered 09-18 19:14 (INS2-17); `KVM4_RUNNER_TOKEN` "read by nothing" while two workflows read the GitHub secret of that name (INS2-02); rollout step 6 tells the operator to approve the ImB products the owner retired (INS2-13); "not blocked from issuance" (INS2-01). |
| INS-09 SCOPE/README/SPEC contradict the GxP features | **PARTIAL** | `SCOPE.md:3-30` status section added (accurate); `README.md:3-14` and `SPEC.md` "Document export" corrected. Still false: `SCOPE.md:27` claims the zone decision "is recorded as open in DECISIONS-2026-09.md" — it is not (INS2-08); `README.md` and `SPEC.md` retain the pre-fix statements listed in INS2-09/INS2-10. |
| INS-10 Temporary relaxations untracked | **PARTIAL** | `DECISIONS §3` rows 1–2; `TEST-ACCOUNTS.md:3-8` note. Missing: `admin`/`admin` (owner 2026-09-14T10:09 "just for a short while"), the trial `qc_mgr` deletion the owner scheduled (2026-09-04T14:32 "after the trial period this account will be deleted"), and `HANDOFF.md`'s security list does not point at §3 (INS2-20). `provision_test_accounts.py:1-10` still `tt.*`, as §3 records. |
| INS-11 Journey label "cure" | **CLOSED** | `cultivation-view.js:335` `Harvest · coarse trim · defoliation` / `Жетва · грубо кастрење · дефолијација` (no duplicated "сушење"); `PROPAGATION.md:163-170` keeps the wording `[NEEDS INPUT]`. No frontend test pins the label. |
| INS-12 Code pre-fill missing on QC batch fields | **PARTIAL** | `GF.batchCodeField` in `qcecoa-view.js:679`, `qcsample-view.js:385`, `qcoos-view.js:273` (commit `f73bba7`). Not applied to `qccoa-view.js:796` (`qcq-batch`, CoQ compile) and `:849` (`qco-batch`, certificate) — the two lines the first review cited (INS2-05). |
| INS-13 ±10 % ceiling | **PARTIAL** | Ceiling: `products.py:266-278` `_check_window`, used by create/patch/ladder/import/import-fitted; test `test_products.py:125`. Overlap: `_validate_grade_set` (`:312-326`) only on `/ladder` and `import-fitted`; `POST /qc/products` (`:506-534`) has no sibling check (INS2-06). |
| INS-14 Builder `-28` build not in git | **NOT FIXED** | `origin/claude/sync-potency-spec-service` still `63474db`; no `buildTwoPerPage` anywhere in the tree. Acknowledged in `PRODUCT-CATALOGUE` (INS-14, "the export must come from the live service") and `POTENCY-DATA`; `HANDOFF.md:32` still presents #53 without saying it is stale (INS2-22). |

---

## 1. Instruction register — what changed against HEAD

Basis: the 50-row register of the first report. Grades that change:

| Id | Was | Now | Why |
|---|---|---|---|
| R02 SCOPE: non-GMP, no e-signature | CONTRADICTED | PARTIAL | `SCOPE.md` status section says the July text no longer describes the software; the decision is still the owner's and is *not* on the decision register (INS2-08). |
| R16 code pre-fill | PARTIAL | PARTIAL | three QC views done; both CoQ/certificate forms not (INS2-05). |
| R19 PR_MGR from harvest onward | PARTIAL | PARTIAL | + waste manifests, decon, gowning for `dry` rooms (`decon.py:62`, §2b A-2); trimming/curing/packaging still unmodelled (`DEPARTMENT-MODEL` "Still open"). |
| R26 animated bar | IMPLEMENTED (label defect) | IMPLEMENTED | label fixed. |
| R27 initiator sets the clone date | IMPLEMENTED (defaults today) | PARTIAL | server requires it (`propagation.py:198` `started_on: date`); the form pre-fills today (`propagation-view.js:589`) — INS2-04. |
| R29 nominals as in the PDFs; grading | PARTIAL | IMPLEMENTED (code) | product grading path exists; superseded on tolerance by R45. |
| R32 mothers show potency tested | PARTIAL | IMPLEMENTED (code) | three sources; data empty until R10. |
| R33 batch number = cloning month | IMPLEMENTED (AD-7 registration month) | IMPLEMENTED | `cultivation.py:513-541` takes `clone_date`; form sends it (`cultivation-view.js:904-905`). |
| R36 out-of-window CoQ not blocked | vacuous | **CONTRADICTED in part** | approval, hence render, waits for a CLOSED OOS — INS2-01. |
| R37 ≤ ±10 %, 1–6 grades, non-overlapping | NOT IMPLEMENTED | PARTIAL | ceiling everywhere; non-overlap only on ladder/fitted paths (INS2-06). |
| R39 regrade + OOS + deviation | NOT IMPLEMENTED | IMPLEMENTED | with the sequencing question of INS2-01. |
| R40 grade scheme + colouring | NOT IMPLEMENTED | IMPLEMENTED | 34 rooms; three rule gaps remain open in `FACILITY-LAYOUT` (T/M/W wings, E/F warehouses & wardrobes, interior vs perimeter corridors) — the owner asked on 09-06 16:29 to be told them; they are written, not asked. |
| R41 spellings as in the specifications | CONTRADICTED | IMPLEMENTED for PUM/CLE | four disputed remain; SJ alias gap (INS2-03). |
| R45 fitted everywhere | NOT IMPLEMENTED | PARTIAL | server side built; the fitted specs are not loaded; the retired ±10 % pages are still the first rollout import. |
| R50 builder synced to git | PARTIAL | PARTIAL | unchanged (INS-14). |

Rows the first register did not carry, found in the messages:

| Id | Date | Instruction | Status |
|---|---|---|---|
| R51 | 09-11 15:28 | "we will issue the needed iCOA and COQs for initial and/or retest periods for every produced batch" | IMPLEMENTED by §2b B-8 (`coq_aggregation.py:268` `_COQ_PURPOSES`, `:397-403` purpose/timepoint validation, tasks `0071`). Nobody linked B-8 to this message; it should be in §1. |
| R52 | 09-11 15:28 | "update the Tranche ledger of course" (T1/T2 list; 09-12/09-14 the Tetra→Versa names, product codes and final nominals; 09-16 five downgraded specs) | UNVERIFIED which ledger was meant. The app's ledger (`backend/app/data/portfolio_master.json`, 78 rows, Q28 in the inventory) still prints placeholder labels such as `"final_label": "STEADY BG XY/1"` where the owner's 09-14 07:10 table gives `STEADY BG 26/1`; the commercial-identity list/import/edit still has no UI caller. If the app's ledger was meant, the instruction is not honoured. |
| R53 | 08-29, 08-31, 09-07 ×2, 09-16, 09-17 | "commit, review, merge to main, deploy" (six times) | NOT DONE: PR #52 open (92 commits, `mergeable_state: unstable`), default branch is still the feature branch, production unchanged since v92/v133/v26. The agent cannot merge (read-only App; `gh_api.py` allow-list has no PUT) — `HANDOFF` says so — but the standing instruction should be listed as open, not only as "owner merges it". |
| R54 | 09-16 05:46 | results of `＊` (hand-trim experiment) batches are not used unless the batch is the certifying one | Builder rule (out of branch). In the app, `_CERT_SQL` (`propagation.py:377-388`) matches certificates to `plant_batches.code` exactly, so a `JD112501＊` certificate is excluded by accident, not by rule; `POTENCY-DATA.md:478-480` still says "on file, not credited" results ARE included (INS2-21). |

New tally (same 48 graded rows + the 16 builder rules as one line): **34 implemented, 10 partial, 2 not implemented (R10 workbook sync, R46 canvas), 1 contradicted (R36), 1 superseded** (was 31 / 8 / 6 / 2 / 1).

Owner instructions still not honoured at HEAD: R10 (sync — the owner asked twice, 09-06 16:29 and 18:02, what the "three blocking decisions" are; `ECOA-MASTER-SYNC-DESIGN.md:112-119` names them — landing zone, credential, batch key — but no record shows they were put to him in those words); R27/AD-19 (form default); R36 (INS2-01); R44 (spec/CoQ/iCoA "one function" — analysis in chat only, no repo artefact); R45 (fitted data not loaded; the first rollout import is still the retired scheme); R46 (canvas); R50/INS-14; R52; R53.

---

## 2. Audit of `DECISIONS-2026-09.md` §2b (48 rows) and the §2 rows the fixes touched

Every row was read against the code. Rows not listed below match the code and contradict no owner message or §1 row: C-2 (`products.py:222-243` — lower nominal on tie, nearest edge outside), C-4 (`_check_window` called from `import_fitted` `:863`), C-6 (`spec_html.py:179-215`), C-7 (`potency.py:222-234`, `potency_import.py:156-160`), C-8 (`products.py:852-854`), D-1 (`plantids.py:94`, 0070 keeps `cutting_no` 01–99 — owner wrote "00–99", correctly listed for his yes), D-2 (`cultivation.py:121` `_CORRECTORS`), D-3 (`:117-118,149,209-227`), D-4 (`harvest.py:40-49`), D-6 (`cultivation-view.js:335`), A-3 (`auth.py:361-388`), A-5 (`worktime.py:77`), A-6 (`reports.py:270`), A-7, B-1 (`coq_aggregation.py:588-598`), B-4 (`certificates.py:20-32`), B-7 (`signatures.py:83-126`), B-10 (`common.py:235`, `certificates.py:448`), B-13 (`0071`, four `DROP SEQUENCE` statements each naming pairs — count not re-derived), E-3 (`qmsregistry`/`qmsknow` absent from `index.html`, `modules.js`, `core.js`, `views.js`), F-4 (`deploy.yml:225-275`), F-7 (`capture.py:122`, no fallback name). A-1's `172.16.31.20` lives in `docker-compose.yml:100` (`FORWARDED_ALLOW_IPS`), not in Python — the row is right, the reader will look in the wrong place.

Rows that contradict an owner message, a §1 row, or the code:

| Row | Register says | Owner / code | Finding |
|---|---|---|---|
| **C-1** | "…until a formal OOS naming Total Δ9-THC exists on the batch, then the existing §6.4.1 gate holds until it is CLOSED; **issuance is not blocked**." | Owner 2026-09-06T16:29: "a non-conforming CoQ should be blocked from issuance. — **NO for now**"; 18:02: "**NO for now**: a Total Δ9-THC outside the product's ±10 % window does not block issuance". Code: `review_coq` 409 (`coq_aggregation.py:749-751`) and `render_coq` requires APPROVED (`:834`) → nothing issues until the OOS is opened and CLOSED. | INS2-01 |
| §1 2026-09-06 | "An out-of-window CoQ is not blocked from issuance." | same | INS2-01 |
| §1 2026-09-05, **AD-8** | "harvest/cure/defoliation"; AD-8 "Owner's words: 'harvest, cure and defoliation'" | Owner 2026-09-05T22:28 wrote "**harvest, course and defoliating** end of GACP"; D-6 quotes it correctly. §1 puts a word in the owner's mouth that the same file's D-6 withdraws. | INS2-07 |
| **AD-19** | "Corrected 2026-09-27: the clone-run date has **no default**; the initiator sets it." | Owner 2026-09-05T20:08: "they have to set the date of cloning initiation". Server: `CloneRunIn.started_on: date` required (`propagation.py:198`). Form: `GF.dateField('cr-date', { value: today(), clearable: false })` (`propagation-view.js:589`) — the date is today unless changed. | INS2-04 |
| **E-1** | "QC batch-id fields carry the cultivar code as their constant head." | `qccoa-view.js:796` and `:849` are plain `<input>`s. | INS2-05 |
| **C-5** | "both spellings resolve to one cultivar until the owner picks" | For SJ, `imb_products.json` holds "Sleepy Joe" as both `strain` and `strain_printed`; "Sleepy Joy" (the per-strain folder spelling per `PRODUCT-CATALOGUE:233`) is nowhere, so `catalogue_aliases()['SJ'] == ('Sleepy Joe',)` and a fitted export named "Sleepy Joy" takes the conflict branch of `resolve_or_create_cultivar` (`potency_import.py:103-114`) and is skipped. | INS2-03 |
| **C-3** | "a strain's fitted set should be approved in one sitting" | Not contradicted, but neither `HANDOFF` rollout 6 nor the UI says so; approving one fitted product retires every v.03 product of the strain (`products.py:604-608`) while the other fitted grades are DRAFT. Any batch/mother pointing at a v.03 product then points at a SUPERSEDED row. Design question for the product-catalogue reviewer; recorded here because the rollout text hides it. | INS2-13 |
| §2 open question "May QC compile against a product other than the batch's target? — the compile form offers every APPROVED product **of the strain**" | `qccoa-view.js:622` `qcProducts({ status: 'APPROVED' })` — every APPROVED product org-wide, no cultivar filter; `compile_coq` checks `cultivar_id` against the product only when the form sends one, and it does not (test `qccoa-coq-potency.test.js:149` "sends product_id, not cultivar_id"). Nothing ties the product's cultivar to the batch. | INS2-12 |
| **D-5** | "trimming/drying recorded as D" | Also de-bucking `C153` (regime GMP, wing C) and `E80`/`E81` (`facility_layout.json`); the owner named "Trimming and Drying Rooms". Extension, not the owner's word. | INS2-18 |
| §2b row for A-2 vs `DEPARTMENT-MODEL` | PR_MGR records waste/decon/gowning | `DEPARTMENT-MODEL` matrix (`:445-457`) has no such row; "Still open: Security manager … read-only by accident" is still true (`decon.py:62-63`, no `SE_MGR`). | INS2-21 |

Rows that quietly answer a question the owner was asked and never answered: D-1 (00 vs 01), AD-1/AD-2 (7-day import allowance, nursery window), AD-12→C-2 (tie-break), C-3 (version-level supersession), the reprint assumption (42 products), and — new — the clone-run date default in the form and the org-wide product picker on the CoQ form.

---

## 3. Findings

### INS2-01 [high] owner-instruction — The out-of-grade rule blocks issuance until an OOS is opened and closed; the owner said "NO for now" twice, and the register, HANDOFF and two docs say "not blocked"

**Where**
- `backend/app/api/qc/coq_aggregation.py:243-267` (`_regrade_needs_oos`), `:749-751` (review refuses 409 until an OOS naming Total Δ9-THC exists), `:781-795` (review refuses while any OOS is open), `:819-836` (render only from APPROVED).
- `docs/DECISIONS-2026-09.md:21` (§1) and `:73` (C-1); `docs/HANDOFF.md:130-134`; `docs/PRODUCT-CATALOGUE-2026-09.md:58-63,156-164,413-427`; `docs/POTENCY-DATA-2026-09.md:577-585`.

**What happens**
A GP lot assays 22.10 % against `GP_THC26:CBD1`. QC compiles the CoQ (201, regraded to GP24, deviation sent). The Head of QC cannot approve it (409 "a formal OOS naming Total Δ9-THC must be recorded"). QC opens the OOS; approval is still refused by the §6.4.1 open-OOS gate until Phase I/II and the QP disposition close it. Only then can the CoQ be approved and rendered. The certificate is blocked from issuance for the whole life of the investigation — exactly what the owner declined on 2026-09-06T16:29 ("NO for now") and 18:02 ("NO for now: … does not block issuance"). The same message does ask for "a formal OOS regarding the Batch disposition" — so the disagreement is about sequencing (OOS *alongside* issuance, or *before* it), and the owner has not been asked in those terms. Every document the owner will read says the opposite of what the code does, so he cannot see there is anything to decide.

**Evidence**: read the compile → review → render path end to end; `test_potency_coq.py:168-230` pins exactly this order (review 409 → closed OOS → review 200 → render 201) while its own docstring says "The certificate is NOT blocked".

**Fix**: either (a) move the OOS requirement off the approval gate and make it a tracked follow-up (the deviation notification already exists; add an "OOS pending" flag on the CoQ and a report of regraded CoQs without one), or (b) keep the gate and rewrite §1, C-1, HANDOFF, PRODUCT-CATALOGUE and POTENCY-DATA to say plainly "issuance waits for the OOS to close — the owner's 'NO for now' is overridden by his own OOS requirement; confirm". Ask the owner which.

### INS2-02 [high] stale-doc / operational — HANDOFF tells the owner `KVM4_RUNNER_TOKEN` "is read by nothing; the owner may delete it" — the GitHub secret of that name drives the deploy and the nightly rehearsal

**Where**: `docs/HANDOFF.md:96-97`; `.github/workflows/deploy.yml:58,130` (`RUNNER_TOKEN: ${{ secrets.KVM4_RUNNER_TOKEN }}`); `.github/workflows/migration-rehearsal.yml:47,142,330,434,473,846`; `ops/agent/rsh.py:33-34` (reads `RUNNER_URL`/`RUNNER_TOKEN`).

**What happens**: the owner asked at 2026-09-27T02:20 whether to delete "KVM4_RUNNER_TOKEN" from his environment variables. The cloud-environment variable is indeed read by nothing. A GitHub Actions secret with the same name is read by both workflows; if the owner acts on "may delete it" in the wrong place, `deploy.yml` refuses to run ("KVM4_RUNNER_URL / KVM4_RUNNER_TOKEN secrets are not set", `migration-rehearsal.yml:142`) and the nightly drift check goes red. If the GitHub secret still holds the pre-migration value, that too is unstated. UNVERIFIED whether the GitHub secret is current (no GitHub write/secret access).

**Fix**: one sentence in HANDOFF: "the *cloud-environment* variable `KVM4_RUNNER_TOKEN` is unused (the helpers read `RUNNER_TOKEN`); the *GitHub secret* `KVM4_RUNNER_TOKEN` is required by deploy.yml and migration-rehearsal.yml and must hold the current runner token."

### INS2-03 [medium] stale-doc / data — HANDOFF lists a settled spelling as disputed and omits one that is; the SJ alias the register promises does not exist

**Where**: `docs/HANDOFF.md:126-128` ("Jelly Donutz/Donuts, Wedding Crasher/Crusher, Graps & Crème/Grapes And Cream, **Clemosa vs Clemosa A Bud**"); `docs/DECISIONS-2026-09.md:22` and `:77` (C-5); `backend/app/data/imb_products.json` SJ row (`strain` = `strain_printed` = "Sleepy Joe", `spelling_disputed: true`); `backend/app/api/qc/products.py:707-722`; `backend/app/api/qc/potency_import.py:103-114`.

**What happens**: (1) A new session reading HANDOFF re-asks the owner about Clemosa, which he settled on 2026-09-06T18:02 ("CORRECT AS IN THE SPECIFICATIONS") and the code already applies (rename on import, `test_products.py:535`), and never asks about Sleepy Joe/Joy. (2) C-5 and `PRODUCT-CATALOGUE:43-47` say both spellings of each disputed pair resolve to one cultivar; for SJ only "Sleepy Joe" is known, so an `import-fitted` body naming the strain "Sleepy Joy" (the per-strain folder spelling) is reported as a conflict and skipped — a fitted specification silently not loaded.

**Evidence**: parsed the JSON; read `_spellings`, `catalogue_aliases`, `resolve_or_create_cultivar`.

**Fix**: HANDOFF: replace "Clemosa vs Clemosa A Bud" with "Sleepy Joe/Joy". JSON: add `"strain_printed": "Sleepy Joy"` (or a `disputed_spellings` list) so the alias path covers it; a test that imports `{"id":"SJ","name":"Sleepy Joy"}` and expects the existing cultivar.

### INS2-04 [medium] owner-instruction / register≠code — The clone-run date "has no default" (AD-19) only on the server; the form pre-fills today

**Where**: `web/gf/propagation-view.js:589` (`GF.dateField('cr-date', { value: today(), clearable: false })`), `:688`; `backend/app/api/propagation.py:198`; `docs/DECISIONS-2026-09.md:52`.

**What happens**: the owner (2026-09-05T20:08): the initiator "has to set the date of cloning initiation". A user who opens the clone-run form and saves records today's date without ever choosing one — the behaviour AD-19 says was corrected. The register tells the owner it is fixed.

**Evidence**: read the form builder and the submit handler; `clearable: false` means the field cannot even be emptied.

**Fix**: `value: ''` with the picker opening on today highlighted (the FE-08 convention already in `datepicker.js`), and refuse submit without a date; amend AD-19.

### INS2-05 [medium] owner-instruction / register≠code — The two CoQ forms the first review named still have plain batch inputs; E-1 claims otherwise

**Where**: `web/gf/qccoa-view.js:796` (`<input id="qcq-batch" placeholder="Batch id">`, CoQ compile) and `:849` (`qco-batch`, new certificate); `docs/DECISIONS-2026-09.md:108`; `docs/FRONTEND-DESIGN-HANDOVER.md` appendix ("a batch id uses `GF.batchCodeField`").

**What happens**: the owner's 2026-09-05T17:00 rule ("already include in the text box the part that is the same") is applied in eCoA, samples and OOS but not on the two forms that create the certificates themselves — INS-12's exact citations (`qccoa-view.js:762,814` at 807d60f).

**Evidence**: grep for `batchCodeField`/`codeField` in `qccoa-view.js` returns nothing.

**Fix**: use `GF.batchCodeField('qcq-batch', …)` / `('qco-batch', …)` as in `qcsample-view.js:385`.

### INS2-06 [medium] owner-instruction — A single product may still overlap its siblings; the owner's "ranges not overlapping" holds only for ladders and the fitted import

**Where**: `backend/app/api/qc/products.py:506-534` (`create_product` calls `_check_window` only), `:537-576` (`update_product` likewise); `_validate_grade_set` at `:312-326` is called only from `create_ladder` (`:668`) and `import_fitted` (`:867`).

**What happens**: `POST /qc/products` for `GP_THC24:CBD1` with window 21.60–26.39 succeeds beside an approved `GP_THC26:CBD1` 23.40–28.59 of the same `doc_version`; a second person approves it; `nearest_of` then has to tie-break inside an overlap the owner said must not exist (2026-09-06T18:02: "their ranges not overlapping"). INS-13's second half ("flag overlaps with sibling DRAFT/APPROVED products") was not built for this route.

**Evidence**: read both routes; no test in `test_products.py` posts an overlapping single product (the overlap test at `:156` asserts overlap *is allowed*).

**Fix**: in `create_product`/`update_product`, fetch the cultivar's non-SUPERSEDED products of the same `doc_version` and run `_validate_grade_set` over them plus the new row; the ImB v.03 import stays exempt (the pages overlap by issue, documented).

### INS2-07 [medium] stale-doc — The decision register misquotes the owner on the GACP→GMP step

**Where**: `docs/DECISIONS-2026-09.md:20` (§1: "harvest/cure/defoliation") and `:41` (AD-8: owner's words "harvest, cure and defoliation") versus `:86` (D-6: owner wrote "course").

**What happens**: the owner wrote "harvest, course and defoliating" (2026-09-05T22:28). §1 presents "cure" as a settled owner decision ("do not re-ask") while D-6 in the same file asks him to confirm "coarse trim". A reader of §1 alone will restore "cure" — the INS-11 defect — and be able to cite the register for it.

**Fix**: §1 and AD-8: quote "harvest, course and defoliating"; note the reading is D-6's, unconfirmed.

### INS2-08 [medium] stale-doc — SCOPE.md says the operate-as-controlled-records decision "is recorded as open in DECISIONS-2026-09.md"; it is not

**Where**: `docs/SCOPE.md:24-28`; `docs/DECISIONS-2026-09.md` (§2 open questions `:54-63`, §4 `:131-137`) — no row mentions validation, controlled records, or SCOPE.

**What happens**: the one decision INS-09 said only the owner can make (are the QC/LIMS, cultivation and DocEngine records operated as controlled electronic records, or as a working system transcribed into the QMS?) is claimed to be on his list and is on no list. The owner's 2026-09-24T09:41 question ("live self-updating or human check tracking system for … QC laboratory for issuance of certificates … EU GMP and computer system validation") is the same question from his side, and it too is absent from §2/§4 except as "5. Live self-updating tracker" with no link to the scope decision.

**Fix**: add the row to §2 ("Are the QC, cultivation and DocEngine modules controlled electronic records? — code assumes yes: e-signatures, CoQ issuance, DocEngine registration; SCOPE says no").

### INS2-09 [medium] stale-doc — README still states four things that are false at HEAD

**Where / what**
- `README.md:118-122`: "A ninth service, `docengine`, runs on the deployed stacks but is **not** in this compose file" — `docker-compose.yml:208-222` defines it (commit `7102bfb`); HANDOFF `:69-70` says so.
- `README.md:124-127`: "the SSH-based `deploy.yml` is manual-dispatch only" — `deploy.yml` contains no `ssh`; it drives the kvm4-runner `/shell` endpoint with a `scope` choice (`:68-76`).
- `README.md:131-134`: "The full production target (React/TS, async FastAPI over the Letta Postgres, RLS/JWT, Qdrant RAG) is captured in `docs/SPEC.md`" — SPEC's stack table now says vanilla JS / RAGflow / asyncpg; README points at a target SPEC no longer states.
- `README.md:145-149` (Provenance): "the QC-laboratory, CoA, stability and OOS modules are intentionally excluded" — contradicted by the file's own first paragraph (`:5-8`) and by 11 `web/gf/qc*-view.js` views.

**Fix**: delete the compose caveat, the SSH sentence and the Provenance exclusion; point "Status & roadmap" at `SCOPE.md` and the inventory instead of the React/TS target.

### INS2-10 [medium] stale-doc — SPEC.md contradicts itself and the code in six places

**Where / what** (`docs/SPEC.md`)
- "Compliance & audit … electronic-signature metadata — *not implemented; out of scope per SCOPE.md, WWF is a non-GMP planning tool*" — `backend/app/api/qc/signatures.py` (append-only since tasks 0061; role-of-record enforcement B-7); the same file's "Document export" paragraph says "e-signatures ARE implemented".
- Stack row "Migrations | Hand-authored idempotent SQL (IF NOT EXISTS / ON CONFLICT)" — the "Driver" row two lines up says two alembic chains.
- "CI/CD | GitHub Actions → SSH deploy to VPS" — no SSH (see INS2-09).
- "JWT sessions (configurable TTL, 12 h default)" — `backend/app/config.py:66` `access_token_expire_minutes` default **15**.
- "six visual themes" — `FRONTEND-DESIGN-HANDOVER.md:242,310` documents 35 skins.
- "PDF (A4 table + GMP sign-off block …) — the weekly-document PDF is not implemented" beside "Export — CSV · JSON · PDF" in README `:47`: one of the two is wrong (UNVERIFIED which; `web/gf/export.js` exists).

**Fix**: rewrite the two paragraphs and the four rows; or head the document "historical target, superseded by SCOPE.md and the inventory" and stop maintaining it.

### INS2-11 [medium] stale-doc — PROPAGATION.md still describes the ladders as the specification and tells the operator to import and approve them

**Where**: `docs/PROPAGATION-2026-09.md:26-36` ("What 'the ImB Product Specifications' are in this system: The per-strain potency ladders in `qc_potency_specs`"), `:62-73` ("`GET /cultivation/cultivars` returns each cultivar **with** `spec`: the APPROVED ladder" — `cultivation.py:461-466` returns `products`, no `spec`), `:93-95` ("the strip says … against which specification" — the ladder snapshot), `:216-238` (the `[NEEDS INPUT: are the per-product ±10 % pages the current ImB specification …]` the owner answered 2026-09-05T22:28, and "a clone run snapshots that ladder" — `clone_runs.potency_spec_id` was dropped in 0067), `:296-300` ("`test_propagation.py` (7)" — 16), `:311-313` (Rollout: "import the ImB catalogue via `POST /qc/potency-specs/import`, then approve per cultivar").

**What happens**: the first review's item 6 listed four false statements; one (the "Who registers" table) was fixed, three were not, and the rollout instruction is still the one that installs the retired scheme (it now 409s only *after* a product is approved — before that it succeeds and the ladder grades CoQs). The "Conventions" section (`:135-185`) is accurate and contradicts the sections above it.

**Fix**: replace `:26-36` with a pointer to `PRODUCT-CATALOGUE.md`; delete `:216-238` or mark it "historical, answered 09-05"; replace the rollout line with the catalogue rollout; fix the `spec` claim and the test count.

### INS2-12 [medium] register≠code / data-integrity — PRODUCT-CATALOGUE contradicts itself, the inventory and plantids; the CoQ form offers every strain's products

**Where / what** (`docs/PRODUCT-CATALOGUE-2026-09.md`)
- `:97-98` "`[NEEDS INPUT: which spelling is canonical?]`" and `:373-377` "**[NEEDS INPUT]** Which is the controlled state: the issued v.01 PDFs … or `_grades_data.json`? The app currently implements the PDFs" — both answered (09-06, 09-18) and contradicted by the same file's `:12-48`.
- `:193` "Legacy plant `20260706_GP_0001`" — `plantids.py:81-84` now composes `<date>_<batch code>_<seq>` (CS-02; `PROPAGATION:159-162` has it right).
- `:203-204` "Production already holds the 42 v.03 rows, so this step reports 42 skipped" — `docs/review-2026-09-27/inventory.md:172,456,463` and `ECOA-MASTER-SYNC-DESIGN:28-31`: production holds 71 DRAFT ladders and 71 cultivars, `qc_products` empty; `HANDOFF` rollout 6 tells the operator to run the import. UNVERIFIED on the host; the two docs cannot both be right.
- `:130` route table "`POST`/`PATCH /qc/products` … QC writers" — no UI reaches them (`api.js` `qcProductCreate`/`qcProductPatch`/`qcProductLadderCreate`/`qcProductPotency` have no callers); the table implies an authoring screen that does not exist.
- §2 open question says the compile form offers "every APPROVED product **of the strain**"; `qccoa-view.js:622` loads every APPROVED product org-wide and the compile route never checks the product's cultivar against the batch. A GP lot can be certified against `CJ_THC28:CBD1` with one wrong click, and the CoQ then carries `cultivar_id` = CJ.

**Fix**: delete the two stale `[NEEDS INPUT]` blocks; fix the legacy id and the production claim (say "verify on the host"); mark the create/patch routes API-only; filter the picker by the batch's cultivar (look up `plant_batches.code = batch_id`) and refuse a product of another strain server-side when the batch is known.

### INS2-13 [medium] stale-doc — The PR #52 body the owner must read before merging is two review rounds stale, and HANDOFF's rollout step 6 approves the retired scheme

**Where**: PR #52 body (read live 2026-09-27; `updated_at` reflects pushes, the text is unchanged); `docs/HANDOFF.md:76-80`.

**What happens** (PR body): "Twenty-two commits" (92); "Conformance replaces disposition … Which product a lot ships as is a packaging decision, not something a measurement settles" (the built rule is the opposite: `nearest_of` settles it); "No grade is invented … a room with no grade says 'not classified'" (34 rooms now carry grades); Rollout "Deploy users 0012 and tasks 0064–0069" (now 0070, 0071, users 0013, the DocEngine role, the org backfill, `CAPTURE_IMPORT_USER`, the `db-backup` volume mount — HANDOFF `:54-83`); rollout step 2 has no fitted import; "Open for the owner" still asks the cleanliness scheme and the spellings (answered 09-06) and says an out-of-window CoQ "currently prints 'does not conform' and still renders" (false then — §7 of the first review — and not what it does now); test counts and "green on `488b869`" are stale. The REVIEW §7 finding was recorded but the body was not corrected.

**What happens** (HANDOFF `:76-80`): "`POST /qc/products/import` (dry run, then real) … approve each strain's products as a different QC person or the QP; the fitted specifications are loaded with `import-fitted`…" — read in order, the operator approves the 42 ±10 % pages (which the owner retired on 09-18) before the fitted set exists; each later fitted approval then supersedes them again (C-3) and any batch registered against a v.03 product in between points at a SUPERSEDED row. `PRODUCT-CATALOGUE` rollout `:200-212` has the right order (import ImB only for the renames, import fitted, approve fitted).

**Fix**: rewrite the PR body's §8, Rollout and "Open for the owner" (or replace them with a pointer to HANDOFF + DECISIONS); HANDOFF step 6: "import the ImB pages for the renames only — do **not** approve them; import the fitted export; approve each strain's fitted set in one sitting".

### INS2-14 [medium] stale-doc — FRONTEND-DESIGN-HANDOVER documents two views that were deleted and none of the views added since September

**Where**: `docs/FRONTEND-DESIGN-HANDOVER.md:224` (view inventory lists `qmsregistry`, `qmsknow`), `:697-708` (§9.22 describes them, with a "retired — use Document Studio" state); no entry for `qcpotency` (the product catalogue), `propagation`, `irrigation`, trichome checks, the floor plan tab, or `GF.batchCodeField` beyond the appendix.

**What happens**: E-3 removed both views from the shell (`index.html`, `modules.js`, `core.js`, `views.js` have no `qmsregistry`/`qmsknow`); a designer working from this handover designs two screens that cannot be reached and none of the cultivation/QC screens the owner asked for in September. The appendix (`:1036-1080`) is accurate.

**Fix**: strike §9.22 and the inventory entries; add one line each for the September views, or head §9 "inventory as of 2026-08; see `review-2026-09-27/inventory.md`".

### INS2-15 [medium] stale-doc — DEPLOY.md's "Deploying" section describes an SSH/rsync workflow that does not exist, and DocEngine "deployed to wwf_mass (test) only"

**Where**: `docs/DEPLOY.md:165-186` ("the SSH workflow is manual-dispatch only"; "Option B — GitHub Actions: Add secrets `KVM4_HOST`, `KVM4_USER`, `KVM4_SSH_KEY` … it rsyncs the repo to `/opt/wwf` … `docker compose up -d --build`"; Option A "Build context lives at `/opt/weekly_weed_flow/backend`, `/root/wwf-gf/web`"), `:417-427` ("Deployed to **wwf_mass (test) only** … Promotion mirrors the qms-api steps").

**What happens**: `deploy.yml` has no `ssh` and no such secrets; it runs through `KVM4_RUNNER_URL`/`KVM4_RUNNER_TOKEN` and `/shell` with a `scope` input; the build context is a tarball under `/opt/wwf-deploy/build-<sha>` (CLAUDE.md). `wwf_mass` was decommissioned 2026-07-29 (`:24`) and `growflow-docengine:v26` runs in production (HANDOFF `:43`). The three sections added 2026-09-27 (`:343-415`: DocEngine role, org backfill, `deploy.yml` docengine scope) are accurate and consistent with `docengine/sql/docengine_role.sql`, `docker-compose.yml:208-222,296-304` and `deploy.yml`; the `ainet`/`ai-net` wording is the compose key vs the network name (`docker-compose.yml:302-303`), not a conflict.

**Fix**: replace `:165-186` with a pointer to CLAUDE.md "Deploying without Actions" and the `deploy.yml` header; delete or date-stamp `:417-427`.

### INS2-16 [low] correctness — `_regrade_needs_oos` matches the batch id exactly while every other OOS gate is case-insensitive

**Where**: `backend/app/api/qc/coq_aggregation.py:256-258` (`WHERE org_id=$1 AND batch_id=$2`) versus `:44-54` (`upper(batch_id)=upper($1)`, "for rows written before batch_id was normalised on write").

**What happens**: an OOS row written before normalisation as `b-regrade` satisfies the open/rejected gates but not this one; the CoQ stays at 409 "a formal OOS … must be recorded" although one is. Low because new writes are normalised.

**Fix**: `upper(batch_id)=upper($2)`.

### INS2-17 [low] stale-doc — HANDOFF says "which 'six CoQs' the owner meant (2026-09-18)" is unanswered; the owner answered

**Where**: `docs/HANDOFF.md:125-126`. Owner 2026-09-18T19:14: "Six is regarding those six certificates of quality that you did not have something and I told you there is everything" (after 18:04's transliterated message).

**What happens**: the open item is inverted — the six are the six CoQs the *agent* reported missing on 09-18, and the owner says the data exists. The unanswered part is on the agent's side (which six it listed, and where the owner's "everything" is). A new session will re-ask the owner a question he has answered.

**Fix**: "Owner (09-18 19:14): the six are the six CoQs we reported missing; he says the certificates exist — locate them in the workbook (v35+) and close."

### INS2-18 [low] stale-doc / register — FACILITY-LAYOUT dates the owner's grade answer 09-07; D-5 omits the de-bucking extension

**Where**: `docs/FACILITY-LAYOUT-2026-09.md` "### Grades — ANSWERED by the owner 2026-09-07" (message is 2026-09-06T18:02); `facility_layout.json` C153/E80/E81 graded D with the "officially CNC" note; `docs/DECISIONS-2026-09.md:85` (D-5 names "trimming/drying").

**What happens**: the owner named trimming and drying rooms; de-bucking (C153, the first GMP room per `FACILITY-LAYOUT`) and E80/E81 were graded by analogy. Reasonable, but it is the agent's call and D-5 does not say so.

**Fix**: date fix; add "and de-bucking C153 / E80 / E81 by analogy — confirm" to D-5.

### INS2-19 [low] stale-doc — CLAUDE.md still advertises `gh_api.py GET|POST|PUT|PATCH` and "refuses DELETE"; HEAD is an allow-list

**Where**: `CLAUDE.md:42,47`; `ops/agent/gh_api.py:15-27,56-60,93-105` (GET anything under the repo; POST only rerun / rerun-failed-jobs / dispatches; everything else refused); `docs/HANDOFF.md:88-92` describes it correctly.

**What happens**: a session following CLAUDE.md tries `PATCH …/pulls/52` (e.g. to fix the PR body, INS2-13) or `PUT …/merge` and is refused by the helper; the doc says only DELETE is. The rest of CLAUDE.md is corrected (`:133-135` Alpine/wget, `:172-176` disk).

**Fix**: `GET|POST` and "refuses everything not on its allow-list (rerun, dispatch, issue comments)".

### INS2-20 [low] owner-instruction — The temporary-relaxation register omits two items the owner scoped as temporary, and HANDOFF does not point at it

**Where**: `docs/DECISIONS-2026-09.md:122-130` (§3); `docs/HANDOFF.md:101-115` (security list).

**What happens**: §3 has the password floor and the renames. Missing: `admin` / `admin` (owner 2026-09-14T10:09: "just for a short while, and I will change it with stronger password" — no record that he did) and the trial `qc_mgr` account the owner said "will be deleted by an admin after the trial period" (2026-09-04T14:32). HANDOFF's security list, which is where "do not act on these yourself" items live, does not mention §3 at all; a session reading only HANDOFF sees none of them.

**Fix**: two rows in §3; one line in HANDOFF's security list pointing at §3.

### INS2-21 [low] stale-doc — Smaller doc drifts: DEPARTMENT-MODEL matrix, POTENCY-DATA's inclusion rule, PROPAGATION test count

**Where / what**
- `docs/DEPARTMENT-MODEL-2026-09.md:445-457`: the matrix has no row for waste manifests / decon / gowning, which A-2 gave to PR_MGR for `dry` rooms (`decon.py:62`); `:475-479` "Still open: Security manager … read-only by accident" is still true and should say the fix round left it so deliberately (A-2 chose PR_MGR, not SE_MGR).
- `docs/POTENCY-DATA-2026-09.md:472-480`: "Results marked *on file, not credited* **are** included" and the JD112501＊ de-duplication predate the owner's 2026-09-16T05:46 rule (results of `＊` experiment batches are not used unless the batch is the certifying one); the doc is "as of v10" and says so, but the rule change is not recorded.
- `docs/PROPAGATION-2026-09.md:298` "`tests/test_propagation.py` (7)" — 16 tests.

**Fix**: one matrix row; one dated bullet under POTENCY-DATA "Decided since"; the count.

### INS2-22 [low] owner-instruction — INS-14 unchanged: the builder build in production is newer than git, and HANDOFF still presents #53 as its source

**Where**: `origin/claude/sync-potency-spec-service` @ `63474db` (`__APP_VERSION 2026.09.16-27`); `docs/HANDOFF.md:32-35`; acknowledged in `docs/PRODUCT-CATALOGUE-2026-09.md:33-34,431-433`.

**What happens**: the owner's 2026-09-16T13:16 two-per-page PDF export exists only in the deployed image (UNVERIFIED without production). "Agents must not push to the #53/#55 branches" (HANDOFF) means nobody will fix it unless the owner is told; HANDOFF's #53 row does not say the branch is stale.

**Fix**: HANDOFF #53 row: "stale — production runs `-28`; before merging #53, copy `web/index.html` off the running container into the branch (owner or an agent he authorises)".

### INS2-23 [low] owner-instruction — "Merge to main and deploy" was asked six times and remains open without being listed as an instruction

**Where**: owner 2026-08-29T12:19, 08-31T00:56, 09-07T06:02, 09-07T06:57, 09-16T09:24, 09-17T14:51; `docs/HANDOFF.md:26-36,150`; PR #52 `mergeable_state: unstable`, base `main` @ `7b95220`.

**What happens**: the branch has been production for three weeks while `main` is 92 commits behind; every "review, merge to main, deploy" the owner wrote ended with "owner merges it". The constraint is real (read-only App, allow-list without PUT), but the register lists none of these messages, so the standing instruction is invisible; HANDOFF frames the merge as a to-do for the owner without saying he asked the agent to do it.

**Fix**: add a §1 row: "Merge to `main` after each review — agent cannot (no merge scope); the owner merges or grants `pull_requests: write` on the fine-grained token and extends the `gh_api.py` allow-list to `PUT …/pulls/<n>/merge`."

---

## 4. Documentation — false or pre-fix statements at HEAD, per document

| Document | Verdict | Statements that are false or pre-fix (line refs above) |
|---|---|---|
| `docs/HANDOFF.md` | mostly right; 5 errors | Clemosa listed as disputed / SJ omitted (INS2-03); `KVM4_RUNNER_TOKEN` "read by nothing" (INS2-02); "six CoQs … still unanswered" (INS2-17); rollout 6 approves the retired ImB products (INS2-13); "not blocked from issuance" (INS2-01); #53 not marked stale (INS2-22). Verified true: production tags/alembic state (per the deploy records), `rsh.py`/`gh_api.py` behaviour, compose `docengine` + `ai-net`, `CAPTURE_IMPORT_USER` with no fallback, `docengine_role.sql`, migrations 0070/0071/0013, 34 graded rooms, watchdog WARN for the absent offsite container (`ops/watchdog.sh:627-635`). |
| `docs/PRODUCT-CATALOGUE-2026-09.md` | top half right, bottom half stale | two answered `[NEEDS INPUT]`s kept; legacy plant id; "production already holds the 42 rows"; create/patch routes with no screen; "issuance is not blocked" (INS2-12, INS2-01). |
| `docs/POTENCY-DATA-2026-09.md` | right | only the `＊` rule of 09-16 is unrecorded (INS2-21). The "non-overlapping by construction" arithmetic for CJ 14/17/20/24/28 checks out; the service's current state is UNVERIFIED. |
| `docs/PROPAGATION-2026-09.md` | ladders section, spec-on-cultivars, ladder snapshot, rollout, test count (INS2-11) | "Who registers" table now correct. |
| `docs/DEPARTMENT-MODEL-2026-09.md` | right except | matrix lacks A-2; SE_MGR note (INS2-21). QA_MGR row fixed (first review item 7 closed). |
| `docs/FACILITY-LAYOUT-2026-09.md` | right except | "ANSWERED … 2026-09-07" date; AD-15 withdrawal recorded correctly; the seeded-grades table matches the JSON exactly (34 rooms). |
| `docs/FRONTEND-DESIGN-HANDOVER.md` | appendix right; body stale | `qmsregistry`/`qmsknow` (INS2-14); no September views. The appendix's "`GF.batchCodeField` … as on the cultivation batch form" is true of three views, not the CoQ forms (INS2-05). |
| `docs/DEPLOY.md` | new sections right | "Deploying" Option A/B (SSH, rsync, secrets, build paths) and "wwf_mass only" (INS2-15). |
| `docs/BACKUP.md` | right | every claim checked against `db_backup.sh:20-86`, `offsite_backup.sh:21-48`, `ops/watchdog.sh:564-635`, compose container names. |
| `docs/SCOPE.md` | status section right; one false pointer | "recorded as open in DECISIONS" (INS2-08); "QMS Studio zone … SOP registry, knowledge search" in the July text now names deleted views (historical section, acceptable). |
| `README.md` | 4 false (INS2-09) | |
| `docs/SPEC.md` | 6 false / self-contradicting (INS2-10) | |
| `CLAUDE.md` | corrected for wget/disk; one stale | `gh_api.py GET\|POST\|PUT\|PATCH` / "refuses DELETE" (INS2-19). The kvm4-runner `/shell` body-key, payload-cap and classifier notes are unchanged and were not re-verified (no production contact). |
| `docengine/DEPRECATED.md` | right | `pp-document-suite/` is gone; `engine/PROVENANCE.md` exists; the "never in the image" claim is the DI-23 finding restated. |
| PR #52 body | stale in §8, Rollout, "Open for the owner", test plan (INS2-13) | |
| `docs/DECISIONS-2026-09.md` | 5 register≠owner/code rows | §1 2026-09-06 and C-1 "not blocked"; §1 2026-09-05 / AD-8 "cure"; AD-19 "no default"; E-1; C-5 for SJ; D-5 scope; the §2 "of the strain" open-question row (INS2-01, -03, -04, -05, -07, -12, -18). |
| `docs/TEST-ACCOUNTS.md` | right | the 09-04 note is accurate and points at §3. |
| `docs/RANGE-BUILDER-INTEGRATION-2026-09.md` | right | "settled by the owner on 2026-09-18" (`:107-113`). |

---

## 5. Owner requests still unbuilt, and questions the code answers silently

**Unbuilt** (owner's request → state):
1. DocEngine canvas with interruptions/approvals (09-04 23:06, 09-16 16:53, 09-24 10:11) — design only; `reviewed_by`/provenance columns exist (DI-14).
2. QC database ↔ `CoQ_Analysis_Master` sync (09-04 06:35; the owner asked what blocks it on 09-06 16:29 and 18:02) — design only; the three decisions are named in `ECOA-MASTER-SYNC-DESIGN.md:112-119`, no record they were put to him.
3. Range builder inside the app (09-07 06:57) — server side (`/ladder`, `import-fitted`); no in-app UI, no solver.
4. Spec / CoQ / iCoA / template work "as one function" (09-18 15:55) — chat analysis only, no repo artefact.
5. Live, human-checked certificate-issuance tracker under EU GMP/CSV (09-24 09:41) — advisory only; tied to the unregistered scope decision (INS2-08).
6. Fitted specifications loaded into the app (09-18 16:21) — the route exists; the data does not; needs the export and the document code/version from the owner.
7. Tranche ledger update with the T1/T2 lists and final product codes (09-11 15:28, 09-12, 09-14) — `portfolio_master.json` still carries `XY/1` placeholders (R52; target UNVERIFIED).
8. Merge to `main` (R53).
9. Builder `-28` build into git (INS-14).

**Questions the owner was asked (or should have been) that the code answers on its own**:

| Question | Code's answer | Where |
|---|---|---|
| Does the CoQ wait for the OOS before it can be issued? | yes, until CLOSED | `coq_aggregation.py:749-751` |
| Does the clone-run form propose a date? | today | `propagation-view.js:589` |
| Cuttings 00 or 01? | 01 | `plantids.py:94`, 0070 |
| Are de-bucking and E80/E81 Grade D? | yes | `facility_layout.json` |
| May a CoQ be compiled against another strain's product? | yes, nothing prevents it | `qccoa-view.js:622`, `coq_aggregation.py:415-433` |
| Which grade holds a value two windows contain? | closest nominal, lower on a tie | `products.py:222-243` |
| Does approving one fitted product retire the strain's v.03 products? | yes, all of them | `products.py:604-608` |
| Are the six repeated ImB pages reprints? | yes — 42 products | `imb_products.json` |
| Do the QC modules count as controlled electronic records? | yes (signatures, issuance, registration) | `signatures.py`, `coq_aggregation.py:819`, DocEngine registry — versus `SCOPE.md` |
| Which `KVM4_RUNNER_TOKEN` may be deleted? | HANDOFF: the variable; the workflows need the secret | INS2-02 |
