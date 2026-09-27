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
| 2026-09-05 | Phase durations: cloning 7–14 d (imported clones may stay some days more for quarantine); vegetation 14–17 d; flowering 6–9 weeks in one of six flowering rooms; harvest date from documented trichome-maturation records; harvest/cure/defoliation = end of GACP → start of GMP. |
| 2026-09-06 | Out-of-grade rule: a batch whose Total THC falls outside its product window drops to the next grade, is flagged visually, gets a formal OOS on disposition, and a deviation goes to Cultivation and Production. An out-of-window CoQ is not blocked from issuance. |
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
| AD-3 | Stock number counts per (campaign, product, mother number, generation). | "alternative naming convention provided" |
| AD-4 | Cuttings are numbered from 01. | "xx = 00–99" |
| AD-5 | Clone numbers `.nnn` restart per cutting, not per mother. | wording ambiguous |
| AD-6 | Caps: generation ≤ 9, mother number ≤ 99, ≤ 999 clones per cutting. | — |
| AD-7 | (Corrected 2026-09-27: batch-code month is now the cloning month.) | mmyy = cloning month |
| AD-8 | Journey step label wording for the GACP→GMP step. | "harvest, cure and defoliation" |
| AD-9 | The production manager may open only `dry` rooms; no room kinds for trimming, curing, packaging. | — |
| AD-10 | Trichome verdict vocabulary (immature / approaching / ready / overripe); clear+cloudy+amber must sum to 98–102; never a gate. | "documented records" |
| AD-11 | Harvest moisture-loss plausibility band 60–92 %, reported not refused. | — |
| AD-12 | With overlapping windows, the product that contains the value is the match; if none, the closest window above or below. | "the next grade above or below, suitably" |
| AD-13 | A batch or clone run may target only an APPROVED product; a mother requires one. | — |
| AD-14 | Approving a strain's first product supersedes its ladder. | ladders superseded (09-05) |
| AD-15 | Trimming/drying recommended as CNC in the layout doc. | "treat as Grade D" — corrected to D on 2026-09-27 |
| AD-16 | QA is the classification authority on the facility register. | — |
| AD-17 | RAGflow dataset named `DB3_PP_CURRENT_unified`; the Drive folder is `DB3_PP_CURRENT`. | name never chosen |
| AD-18 | The weekly GMP document stays per department, exact match. | — |
| AD-19 | (Corrected 2026-09-27: the clone-run date has no default; the initiator sets it.) | "has to set" |

Open questions the code already answers, unanswered by the owner:

| Question | What the code assumes |
| --- | --- |
| Security manager write access to decon / waste | read-only |
| Should the DocEngine regulatory check block a document? | advisory |
| Are the six repeated ImB pages reprints? | yes — 42 products |
| May QC compile a CoQ against a product other than the batch's target? | allowed, unenforced |
| Where does the CoQ workbook sync land, with which credential, how is stability handled? | nothing built |

## 3. Temporary relaxations (must be reverted or made permanent deliberately)

| Since | What | Where | Revert when |
| --- | --- | --- | --- |
| 2026-09-04 | Production password floor lowered; several accounts carry trivial credentials the owner set for the trial period. | Production environment file and the users database (set by hand, not by code). | Before real use by staff; the owner said "for now, not production". |
| 2026-09-04 | Accounts renamed by a direct database write, outside the provisioning script. | `backend/scripts/provision_test_accounts.py` still creates `tt.*` names. | Align the script or record the scheme as the standard. |
| 2026-09-25 | The self-hosted CI runner lives on the production host with the docker socket. | `ops/gh-runner/` | When a separate runner host exists (review DI-02). |
| 2026-09-26 | `wwf-backup-offsite` was not recreated on the new VM; offsite backups are not running. | `docs/BACKUP.md` | As soon as the rotated Drive credential exists. |

## 4. Owner requests with no code yet

1. DocEngine canvas (asked 09-04, 09-16, 09-24) — design in `DOCENGINE-CANVAS-DESIGN-2026-09.md`.
2. QC database ↔ `CoQ_Analysis_Master` workbook sync (09-04) — design in `ECOA-MASTER-SYNC-DESIGN-2026-09.md`.
3. Range builder inside the app (09-07) — analysis in `RANGE-BUILDER-INTEGRATION-2026-09.md`.
4. Bringing the spec / CoQ / iCoA template work into the app as one function (09-18).
5. Live self-updating tracker of QC certificate issuance (09-24).
