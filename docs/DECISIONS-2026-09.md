# Decision register — September 2026

One place for three things the 2026-09-27 review found scattered or missing:
the product decisions the owner made (with dates, so nobody re-asks them),
the decisions the agent made on its own that still need the owner's yes or
correction, and the temporary relaxations that must not be forgotten.
Dates are the owner's messages in the agent session; no credentials are
recorded here.

## 1. Owner decisions (settled — do not re-ask)

| Date | Decision |
| --- | --- |
| 2026-07-30 | Production data wiped on the owner's order; the app restarts with real records only. |
| 2026-09-04 | Pre-created accounts renamed to `<department>_<function>`; a trial `qc_mgr` account exists; password rules relaxed "for now, not production" (see §3). |
| 2026-09-05 | The two ImB specification PDFs are the official product catalogue: one product per strain × nominal Total Δ9-THC, code `<ABBR>_THC<nominal>:CBD1`, document QCSP 001 v.03; the August ladders are superseded. |
| 2026-09-05 | QA may move batches through their phases and edit the cultivar master and the mother bank. |
| 2026-09-05 | The journey shows every open batch at once. Mothers show the potency tested so far for their strain (average and individual Total THC values). |
| 2026-09-05 | Batch number = strain abbreviation + mmyy (the cloning month) + nn. Mother ID `GP26_S1M03-2_nnn` (product, facility-wide selection campaign, mother number of that campaign, the mother's own generation, stock number 001–999). Clone ID `<mother>-xx.nnn`, xx = consecutive cutting 00–99, nnn = clone within the cutting 001–999. |
| 2026-09-05 | Phase durations: cloning 7–14 d (imported clones may stay some days more for quarantine); vegetation 14–17 d; flowering 6–9 weeks in one of six flowering rooms; harvest date from documented trichome-maturation records; "harvest, course and defoliating" (his words) = end of GACP → start of GMP — read as "harvest · coarse trim · defoliation" (D-6, unconfirmed). |
| 2026-09-06 | Out-of-grade rule: a batch whose Total THC falls outside its product window drops to the next grade, is flagged visually, gets a formal OOS on the batch disposition, and a deviation goes to Cultivation and Production. **"NO for now": an out-of-window CoQ is not blocked from issuance** (16:29 and 18:02) — the OOS is opened alongside, not before. |
| 2026-09-06 | Strain names as printed in the specifications are canonical (e.g. "Pure Michigen", "Clemosa A Bud"). |
| 2026-09-06 | Cleanliness grades per area type as the owner listed them; trimming/drying treated as Grade D; the plan coloured by grade. |
| 2026-09-18 | The flat ±10 % rule is not the grading method; the fitted (data-derived) tolerances apply everywhere; a strain with sparse data gets the full tolerance. The finished specs in the Potency Spec Service are the controlled state. |
| 2026-09-24 | DocEngine canvas amendments: option A (earlier approvals stand; sections written before an amendment are flagged and confirmed at signing). |
| 2026-09-27 | The agent may use the owner's fine-grained GitHub token through `ops/agent/gh_api.py`, and the runner through `ops/agent/rsh.py`. |

## 2. Decisions the agent made — need the owner's yes or a correction

From `docs/review-2026-09-27/instructions.md` §3. Each is in the code today.

| # | What the code does | Owner's words, if any |
| --- | --- | --- |
| AD-1 | Imported clones get up to 7 extra quarantine days on the cloning leg. | "some days more" |
| AD-2 | Nursery shares the cloning leg's 7–14-day window. | no nursery duration given |
| AD-3 | (Corrected 2026-09-27, tasks 0070: a mother number names ONE plant line per campaign; stock number counts per campaign, mother number and generation; the product is derived from the line.) | "alternative naming convention provided" |
| AD-4 | Cuttings are numbered from 01 (kept on 2026-09-27; see §2b D-1). | "xx = 00–99" |
| AD-5 | Clone numbers `.nnn` restart per cutting, not per mother. | wording ambiguous |
| AD-6 | Caps: generation ≤ 9, mother number ≤ 99, ≤ 999 clones per cutting. | — |
| AD-7 | (Corrected 2026-09-27: batch-code month is now the cloning month.) | mmyy = cloning month |
| AD-8 | Journey step label wording for the GACP→GMP step (now "Harvest · coarse trim · defoliation", D-6). | "harvest, course and defoliating" |
| AD-9 | The production manager may open only `dry` rooms; no room kinds for trimming, curing, packaging. (2026-09-27: production also records waste, decon and gowning for `dry` rooms — §2b A-2.) | — |
| AD-10 | Trichome verdict vocabulary (immature / approaching / ready / overripe); clear+cloudy+amber must sum to 98–102; never a gate. | "documented records" |
| AD-11 | Harvest moisture-loss plausibility band 60–92 %, reported not refused. | — |
| AD-12 | (Refined 2026-09-27: the product whose window holds the value is the match, the closest nominal if several, the lower nominal on a tie; outside every window, the nearest window edge — §2b C-1/C-2.) | "the next grade above or below, suitably" |
| AD-13 | A batch or clone run may target only an APPROVED product; a mother requires one. | — |
| AD-14 | Approving a strain's first product supersedes its ladder. | ladders superseded (09-05) |
| AD-15 | (Withdrawn 2026-09-27: trimming/drying/de-bucking rooms carry grade D in the register with the note "officially CNC, operated as D".) | "treat as Grade D" |
| AD-16 | QA is the classification authority on the facility register. | — |
| AD-17 | RAGflow dataset named `DB3_PP_CURRENT_unified`; the Drive folder is `DB3_PP_CURRENT`. | name never chosen |
| AD-18 | The weekly GMP document stays per department, exact match. | — |
| AD-19 | (Corrected 2026-09-27, both sides: the clone-run date has no default on the server and the form opens empty with today only highlighted; the initiator sets it.) | "has to set" |

Open questions the code already answers, unanswered by the owner:

| Question | What the code assumes |
| --- | --- |
| Security manager write access to decon / waste | read-only |
| Should the DocEngine regulatory check block a document? | advisory |
| Are the six repeated ImB pages reprints? | yes — 42 products |
| May QC compile a CoQ against a product other than the batch's target? | allowed, unenforced (the compile form offers every APPROVED product of the strain) |
| Where does the CoQ workbook sync land, with which credential, how is stability handled? | nothing built |
| Which document code / version are the fitted specifications issued under? | `POST /qc/products/import-fitted` refuses to run without one |
| Are the QC/LIMS, cultivation and DocEngine records operated as **controlled electronic records**, or as a working system whose outputs are transcribed into the paper QMS? (`SCOPE.md`; the owner's 2026-09-24 09:41 question about a validated, self-updating issuance tracker is the same question) | The code behaves as the former: e-signatures with a role of record, CoQ issuance, DocEngine registration with provenance; `SCOPE.md` still says the latter |

## 2b. Decisions made by the 2026-09-27 fix workstreams — need the owner's yes or a correction

Each is in the code today. The letter is the workstream (A backend core,
B QC, C product catalogue, D cultivation, E frontend, F DocEngine/infra); the
finding ids are those of `docs/REVIEW-2026-09-27.md`.

| # | What the code does now | Findings |
| --- | --- | --- |
| C-1 | Out-of-grade rule as built (corrected in fix round 2 to the owner's "NO for now"): the regrade target is the product whose window holds the value (none in a dead band); a deviation notification goes to every CU_MGR and PR_MGR at compile; the CoQ carries a visible `regrade_oos_pending` flag until a formal OOS naming Total Δ9-THC exists on the batch, and the document prints the regrade and the OOS state; neither approval nor rendering is blocked by the regrade, and the regrade's own open OOS does not trigger the §6.4.1 open-OOS gate (other open OOS still do). | QC-04, INS-01, INS-04, INS2-01 |
| C-2 | `nearest` tie-break: the lower nominal wins (never over-label); outside every window, the nearest edge, lower nominal on a tie. | AD-12 |
| C-3 | Version-level supersession: approving the first product of a new `doc_version` retires the strain's products of the old version — a strain's fitted set should be approved in one sitting. | INS-03 |
| C-4 | The ±10 % ceiling applies to fitted products too: refused, not flagged. | INS-13 |
| C-5 | Names: PUM → "Pure Michigen" and CLE → "Clemosa A Bud" applied and renamed on import; JD / GRC / SJ / WC keep the August spelling and both spellings resolve to one cultivar until the owner picks. | INS-05 |
| C-6 | The A4 product page prints only the recorded author and approver, with role and date; the legacy ladder page prints the recorded approver and says the QA review is not captured. No locked names anywhere. | QC-16, QC-22 |
| C-7 | Ladder import is refused org-wide once any product is APPROVED; ladder create/approve refused per cultivar with an APPROVED product. | QC-04 |
| C-8 | The fitted import treats service ids that are not plain acronyms (`V_*`, the partner catalogue) as not this facility's strains. | INS-14 |
| D-1 | Cuttings count 01–99 (owner wrote "00–99"); if the floor labels the first cutting 00, the two check constraints are the one place to change. | AD-4 |
| D-2 | Backward phase moves are a correction right of ADMIN, the executives and QA_MGR, with a reason (the task said "ADMIN/QA"). | CS-06 |
| D-3 | Forward moves are strictly one stop at a time; nursery and drying are the only skippable stops; clone→flower is refused. | CS-06 |
| D-4 | PHI is evaluated on `harvested_on` (which must be ≤ today), not on max(cut, today); a backdated cut is judged on its own day. | CS-01 |
| D-5 | Grades (after fix round 2): cultivation rooms stay ungraded (GACP has no class); the whole named E wing is D by the owner's "E = Grade D" (air locks, wardrobes, utility, waste and egress, sampling rooms, the halls), the unnamed polygon E34 stays null; F-wing IPC labs, wardrobes and corridors stay null because no rule named them; trimming/drying recorded as D with the "officially CNC" note, and de-bucking C153 / E80 / E81 graded D by analogy — confirm. | INS-07, CS2-06 |
| D-6 | Journey step reads "Harvest · coarse trim · defoliation" (owner wrote "course"). | INS-11 |
| D-7 | Closing a batch as harvested settles the manifest's destroyed plant count off the END of the batch (the manifest names no plants); the reason text says so. | CS-07 |
| D-8 | (Fix round 2) A harvested close settles "destroyed" plants only from SEALED waste-manifest lines and is refused (409) while a DRAFT line still names the batch; a destroyed close never reads manifests. | CS2-03 |
| D-9 | (Fix round 2) A mother line is its product CODE, not a catalogue row: a later generation or a new stock plant registers against the live APPROVED page of that code, and the line's mothers still pointing at a retired page are re-pointed to the live one (audited) when that happens. | CS2-01 |
| D-10 | (Fix round 2) The plant fill and every run-linking path take one advisory lock per batch, and the first chunk is written inside the locked plan transaction, so a run cannot join between the plan read and the insert. | CS2-04 |
| B-1 | Only an OOS whose Phase I `invalidated=true` licenses a re-test; a CLOSED OOS with disposition REJECT blocks any CoQ for the batch. | QC-01 |
| B-2 | Voiding a cited certificate, or releasing a revision of one, requires voiding the DRAFT/APPROVED CoQ first (then recompile). | QC-02 |
| B-3 | A FAIL-dispositioned source compiles a non-conforming CoQ record (not a 409); PASS cannot be recorded on a certificate with no results — WATER/OTHER certificates included. | QC-06 |
| B-4 | The COQ certificate type is retired for creation; legacy COQ rows are approved by HoQC; the single-certificate CoQ render is kept for the UI (retire vs register-numbering still open). | QC-07 |
| B-5 | The header THC window must equal the total_thc parameter's limits for QA approval; the CoQ prints the parameter's window. | QC-08 |
| B-6 | Promote refuses an eCoA without `report_date`; an undated legacy result sorts by its facility day of entry. | QC-09 |
| B-7 | Electronic signatures are enforcement: the role of record must sign; ADMIN is not exempt. | QC-12 |
| B-8 | CoQ purpose INITIAL/RETEST + free-text timepoint + explicit `source_coa_ids`; no date-window selection. | QC-15 |
| B-9 | The date printed for the ladder page's QC signatory is `effective_date` (no `approved_at` column). | QC-16 |
| B-10 | Result units must match the parameter's unit exactly (normalised); no conversion table. | QC-17 |
| B-11 | A water verdict is set once; a wrong verdict is corrected by a new record. | QC-24 |
| B-12 | No ADMIN exemption for third-party custody entries: the recorder must be the giver or the receiver. | QC-29 |
| B-13 | Eight `qc_*_id_seq` sequences dropped by tasks 0071 (0062 precedent). | QC-28 |
| A-1 | The login limiter trusts the X-Forwarded-For header only on the Traefik-side interface (172.16.31.20); a sibling container's header is dropped. A successful login clears the account's budget. | BC-01 |
| A-2 | PR_MGR records waste manifests and runs decon / gowning for `dry` rooms; witnessing, swabs and release stay QA's. | BC-12 |
| A-3 | A department's head is maintained by the roster: the first department-scoped manager provisioned into or moved into it becomes head; an existing head is never displaced; ADMIN may set it. | BC-04 |
| A-4 | Org-wide weekly AI pins (`weekly_snapshot`, `weekly_report`, subject-less) are readable by org-wide elevated roles only. | BC-02 |
| A-5 | A work session is split at 06:00, 08:00, 17:00, 22:00 and midnight and each segment bucketed by its own start; a session is at most 24 h. | BC-24 |
| A-6 | The weekly window is named after the Monday it contains (`W40 2026`, never `W53`). | BC-16 |
| A-7 | `GET /audit` pages on an opaque per-chain cursor; `before` stays as the documented lossy legacy until the audit view switches. | BC-08 |
| A-8 | Org-wide weekly pins are hidden from department-scoped roles even when they hold no department, and from every USER. | BC-02 |
| A-9 | A pending handoff puts the task in the receiving manager's read AND write scope; the status board lists top-level departments only. | BC-04, BC-05 |
| A-10 | `PATCH /reports/documents/{id}` (whole-document replace), `GET /tasks/tree`, `remember_device` and the legacy qms-api proxy with its settings are deleted outright, not kept behind a role. | BC-07, BC-19 |
| A-11 | Both users-DB write policies on `profiles` are dropped rather than narrowed (users 0013): `app_user` keeps `profiles_read` only. | BC-21 |
| A-12 | The production password floor is 12; `PASSWORD_POLICY_OVERRIDE=true` lowers it deliberately and is warned at startup. | BC-23 |
| A-13 | A work session is at most 24 h (422 on entry; the capture importer skips a longer one with a reason). Snapshot labels and pin titles are Monday-based from now on — a one-time visible change. | BC-24, BC-16 |
| E-1 | QC batch-id fields carry the cultivar code as their constant head (as on the cultivation form). | INS-12 |
| E-2 | WITHDRAWN (fix round 2): it contradicted B-12 — the recorder of a custody hop must be the giver or the receiver, and the form now offers only what the server accepts. | FE-02, QC-29 |
| E-3 | The SOP Registry / Knowledge stub views (which only printed "retired") are deleted from the shell. | FE-21 |
| E-4 | The biosecurity board loads the 200 most recent events unfiltered (a backend `pending_only` filter would be cleaner). | FE-10 |
| E-5 | The "handoffs to your department" list is derived from notifications (a backend `GET /handoffs?to_dept=mine` would be cleaner). | FE-06 |
| E-6 | Executives land in the Analytics module (executive overview) on a fresh browser. | FE-12 |
| E-7 | (Fix round 2) Approvals lives in the Tasks module's Management group and is reachable by every manager role; a handoff notification opens it only for a role that can, a plain assignee jumps to the task. | R2-FE-01 |
| E-8 | (Fix round 2) The production manager's waste/decon/biosecurity actions mirror the server's `dry`-room rule client-side and FAIL OPEN when the room registry cannot be read — the server's 403 stays the gate. | R2-FE-03 |
| E-9 | (Fix round 2) `GET /audit`'s legacy `before` parameter has no client any more (the view pages by cursor); the backend may retire it. | R2-BC-02 |
| E-10 | (Fix round 2) A changed shell file without a service-worker VERSION bump fails the frontend suite (hash fixture in `tests/frontend/fixtures/shell-hash.json`). | FE-13 |
| F-1 | Canon D5 content floor: a revision with fewer words/characters than its source fails, so the "tighten" / "simplify" presets usually fail with a D5 message — accept, or relax D5 for wording-only edits. | DI-07 |
| F-2 | Direct `/build` documents stay unaudited (`audited=false` recorded) rather than running the §6A audit synchronously. | DI-06 |
| F-3 | DocEngine is fail-closed on organisation scope: backend and docengine must ship together. | DI-13 |
| F-4 | The deploy workflow refuses a commit whose workflow files differ from the default branch's (merge first). | DI-02 |
| F-5 | DI-02 remediation choice: separate runner VM vs required PR approval (`ops/README.md`). | DI-02 |
| F-6 | Revision version bumping `1.0→1.1`, `01→02`. | DI-07 |
| F-7 | The capture import acts as the account named by `CAPTURE_IMPORT_USER` only; no fallback name in code. | DI-22 |

## 3. Temporary relaxations (must be reverted or made permanent deliberately)

| Since | What | Where | Revert when |
| --- | --- | --- | --- |
| 2026-09-04 | Production password floor lowered; several accounts carry trivial credentials the owner set for the trial period. | Production environment file and the users database (set by hand, not by code). | Before real use by staff; the owner said "for now, not production". |
| 2026-09-04 | Accounts renamed by a direct database write, outside the provisioning script. | `backend/scripts/provision_test_accounts.py` still creates `tt.*` names. | Align the script or record the scheme as the standard. |
| 2026-09-25 | The self-hosted CI runner lives on the production host with the docker socket. | `ops/gh-runner/` | When a separate runner host exists (review DI-02). |
| 2026-09-26 | `wwf-backup-offsite` was not recreated on the new VM; offsite backups are not running. | `docs/BACKUP.md` | As soon as the rotated Drive credential exists. |
| 2026-09-14 | The `admin` account carries the trivial password the owner set "just for a short while" (10:09). | Production users database. | The owner said he would change it; no record that he did — the BC-23 floor (12) does not touch existing hashes. |
| 2026-09-04 | The trial `qc_mgr` account exists "for the trial period" and "will be deleted by an admin" (14:32). | Production users database. | End of the trial period; soft-delete through the app so the audit trail keeps it. |

## 4. Owner requests with no code yet

1. DocEngine canvas (asked 09-04, 09-16, 09-24) — design in `DOCENGINE-CANVAS-DESIGN-2026-09.md`.
2. QC database ↔ `CoQ_Analysis_Master` workbook sync (09-04) — design in `ECOA-MASTER-SYNC-DESIGN-2026-09.md`.
3. Range builder inside the app (09-07) — analysis in `RANGE-BUILDER-INTEGRATION-2026-09.md`.
4. Bringing the spec / CoQ / iCoA template work into the app as one function (09-18).
5. Live self-updating tracker of QC certificate issuance (09-24).
