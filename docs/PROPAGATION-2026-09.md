# Registering a batch from the product specification, the batch journey, and the mother-plant bank

**Date:** 2026-09-05 · **Status:** implemented on
`claude/weekly-read-flow-setup-yft7if` (PR #52) · **Ships as:** tasks migration
`0065`, `app/api/propagation.py`, changes to `app/api/cultivation.py`,
`web/gf/cultivation-view.js`, new `web/gf/propagation-view.js`.

## What the owner asked for (2026-09-05)

1. The QA manager, the CEO, the COO and the cultivation manager **register a
   batch**: the batch number, the cultivar chosen **from the ImB Product
   Specifications** (where each strain's name and potency grades live), the
   number of plants, and the initiation of the batch.
2. When a batch is registered, **show it at the top of the UI as an animated
   bar**: where the batch is, and what and where the next step of the
   cultivation / production procedure is.
3. The cultivation manager and QA **initiate a clone run**, designating the
   cultivar / propagation-material specification, with a **mother-plant bank**:
   the strains and phenotypes of mother plants, the number of mothers per
   strain, every mother with a unique ID, and per mother — when it was last cut
   for clones and how many generations of clones it has produced, which mother
   room it stands in and the pot number or location within it, how old it is —
   and a **date of cloning initiation** the initiator sets.

## What "the ImB Product Specifications" are in this system

The **product catalogue** — `qc_products`, one row per product (a strain at a
nominal Total Δ9-THC, coded `GP_THC26:CBD1`) with its acceptance window,
document code and version, and an APPROVED / DRAFT / SUPERSEDED status
(`docs/PRODUCT-CATALOGUE-2026-09.md`, `app/api/qc/products.py`). The owner
confirmed on 2026-09-05 that the two ImB Specification documents are the
official pages, and on 2026-09-18 that the **fitted specifications** (the
Potency Spec Service export, imported through `POST /qc/products/import-fitted`)
are the controlled state everywhere — the flat ±10 % of the issued v.03 pages
survives only as the ceiling a window may not exceed. So "choose the cultivar
from the product specifications" means: **the cultivar chooser shows each
cultivar with its APPROVED products** (`GET /cultivation/cultivars` folds them
in as `products`), the batch records the product it is grown to
(`plant_batches.product_id`), the clone run records the product the material is
propagated against (`clone_runs.product_id`), and a mother plant belongs to a
product (`mother_plants.product_id`; its id's head `GP26` is the product code's
acronym and grade).

The per-strain **ladders** (`qc_potency_specs`, `PP-QC-SPEC-001`, imported from
`app/data/imb_grade_ladders.json`) are the scheme this section used to
describe. They are retired: a cultivar's first APPROVED product supersedes its
ladder, and no ladder can be authored, approved or imported for a cultivar
that has one (review QC-04, C-7). Nothing in propagation or cultivation reads
them any more (review CS-18).

**Versions.** Approving the first product of a new document version — the
fitted `GP_THC26:CBD1` after the ImB v.03 page — supersedes the strain's rows
of the old version. A product is therefore identified by its **code**, not its
row: the mother line, the parent check and the parent chooser all compare the
code, a later generation registers against the live page of its parent's code,
and the line's mothers are moved onto that page when it does (review CS2-01).

## Design

### Who registers

| Action | ADMIN | OWNER / CEO / COO | CU_MGR | QA_MGR | others |
|---|---|---|---|---|---|
| Register a batch, generate its plant ids | ✅ | ✅ | ✅ | ✅ | — |
| Initiate / finish a clone run | ✅ | ✅ | ✅ | ✅ | — |
| Move a batch forward through its phases, change its room | ✅ | ✅ | ✅ | ✅ | — |
| Move a batch **backwards** (a correction, reason required) | ✅ | ✅ | — | ✅ | — |
| Cultivar master | ✅ | ✅ | ✅ | ✅ | — |
| Register / edit a mother plant (the bank) | ✅ | ✅ | ✅ | ✅ | — |
| Read all of it | every role above USER | | | | |

`_REGISTRARS` in `cultivation.py` and `_INITIATORS` in `propagation.py` are the
same set as `_WRITERS`: a clone run is how a batch begins, so whoever registers
one initiates the other, and the owner (2026-09-05) put QA on the floor for all
of it — "QA should be able to move a batch through its phases or edit the
cultivar master". The one asymmetry is the backward move: it rewrites what the
record says happened, so it is QA authority's (`_CORRECTORS` in
`cultivation.py`: ADMIN, the executives, QA_MGR), with a reason on the event.
(The table above used to deny QA the moves, the master data and the bank — that
was stale against the code since 2026-09-05; review CS-20.)

### Registering from the specification

- `GET /cultivation/cultivars` returns each cultivar **with** `products`: its
  APPROVED and DRAFT products (approved first, each with code, grade, nominal,
  window and status). One query (a folded sub-select). There is no `spec`
  key any more (review CS-18).
- `GET /cultivation/batch-code?cultivar_id=&clone_date=` suggests the next
  batch number for the CLONING month.
- The batch form: the cultivar chooser's sub-text lists the products
  (`THC 26 · THC 18`, `(DRAFT)` when one is, "no product specification yet"
  when there is none); the target-product chooser offers the APPROVED ones
  with their windows; the panel beneath shows the strain and its products —
  code, window, nominal, APPROVED / DRAFT. Picking a cultivar re-fills the
  batch number through `GF.codeField` with the cultivar code as the fixed
  head. The product can also be set later (`PATCH /cultivation/batches/{id}`,
  "Edit batch" on the card) because the catalogue arrives after the batches do.

### The batch journey strip

`GF.WWF.cultJourney(batch)` draws the plan as a line:

    Registered → Clones → Nursery → Vegetation → Flowering → ◆ Harvest cut → Drying → Lot closed
    └──────────────────── cultivation ─────────────────────┘ └──── production ────┘

- **Position comes from the batch's phase and nothing else** (`clone`=1,
  `nursery`=2, `veg`=3, `flower`=4, `drying`=6, `harvested`=7). A step the batch
  has passed is filled whether or not it stopped there.
- The current step pulses; the fill animates to its width one frame after the
  render inserts it; the cut is drawn as a diamond because it is the handoff
  (cultivation records the cut, production takes the lot — the department
  model of 2026-09-05).
- "Now" shows the step, the room and days in phase; "Next" names the step and
  **whose it is**. A destroyed batch is off the plan; mother stock is not on it.
- The strip follows the batch just registered (else the newest open one), with
  a chip per open batch to switch. Every batch card carries the compact bar.
- If the propagation record links a clone run to the batch, the strip says
  which run, from how many mothers, with how many cuttings, against which
  product (the run's `product_code`).

### The mother bank and clone runs (migration 0065)

- `mother_plants` — one row per mother: `code` (the unique ID), `cultivar_id`,
  `phenotype` (free text, nullable), `room_id` + `position` (the mother room
  and the pot / location), `started_on` (established; age is derived from it),
  `source`, `status` active / retired / destroyed, `note`.
- `clone_runs` — one cutting event: `cultivar_id`, `started_on` (**the date of
  cloning initiation** — required, no default: the owner said the initiator
  "has to set" it), `planned_count`, `room_id`, `batch_id` (the registered
  batch it feeds, SET NULL), `code` (optional), `product_id` (the official
  ImB product the material is propagated against, since 0066/0067; the
  ladder snapshot `potency_spec_id` of 0065 is gone), `status` started /
  transplanted / failed, `finished_on`, `note`.
- `clone_run_mothers` — which mothers the run was cut from, `cuttings` per
  mother (nullable = not counted per mother) and `cutting_no`, the xx of the
  clone id, stamped when the run is created.

**Derived, never stored:** a mother's `age_days`, `last_cut_on`, `times_cut`
(runs it was cut in) and `cuttings_total` are computed from `started_on` and
`clone_run_mothers` on every read. A stored counter would drift from its
evidence. So is "tested so far": the strain's potency history from the three
sources the product catalogue defines (CoQs naming a product of the cultivar,
CoQs naming only the cultivar, certificate results attributed by the batch
code's head), one measurement per lot, with the subset that named the mother's
own product beside it (`GET /mothers/{id}/potency`; review CS-08).

Rules the server enforces: a run's mothers must be active and of the run's
cultivar; the batch a run feeds must be open and of the same cultivar; a
duplicate mother ID is a 409; a destroyed mother is not reinstated; a finished
run does not change again; **a batch's runs are frozen once it has plant ids**
(linking, relinking or unlinking a run is a 409 — the clone ids were numbered
from the runs laid end to end, and a change would rename plants that exist;
review CS-05); a run that failed contributes no clone ids.

Routes (all under `/cultivation`): `GET/POST /mothers`, `GET /mothers/next-code`,
`PATCH /mothers/{id}`, `GET /mothers/{id}/potency`, `GET/POST /clone-runs`,
`PATCH /clone-runs/{id}`, `GET/POST/PATCH /campaigns`.

## Conventions — settled by the owner (2026-09-05/06)

- **Batch number.** `GP072501` = strain abbreviation + `MMYY` + sequence, the
  nth cloning batch of that strain in that month. `MMYY` is the month of the
  **cloning date** (the form re-asks the server when the date changes), the
  sequence is max + 1 over the codes already on file for that head and month
  (never a count), 99 is the last, and the head is enforced on save: a batch
  code must start with its cultivar's code (review CS-09).
- **Mother ID.** `GP26_S1M03-2_020`: strain abbreviation + potency grade (the
  product) · `S1` the selection campaign, numbered **facility-wide** · `M03`
  mother plant number of that campaign · `-2` the mother's own generation ·
  `_020` its clone number in stock. Composed by the server from columns
  (migration 0067), not typed. The abbreviation is the product code's acronym
  (`GP` of `GP_THC26:CBD1`), and the form previews from the same server
  answer. **M03 names one line per campaign, whatever the strain** (migration
  0070): an OPM mother cannot take a number a GP line holds, and a later
  generation registered from a parent inherits the parent's campaign and
  mother number — only `-2` advances (review CS-03, CS-04).
- **Clone ID.** `GP26_S1M03-2_020-03.147`: the mother's id + the cutting
  number (01–99) + the clone within that cutting (001–999). A mother is cut
  6–9+ times at 200–300 clones each. **Cuttings count from 01** — the owner
  wrote "xx = 00–99"; whether the floor labels its first cutting 00 or 01 is
  `[NEEDS INPUT]`, and the CHECK on `clone_run_mothers.cutting_no` is the one
  place that changes if it is 00 (review CS-11).
- **Plant ID with no known mother.** `<clone-date>_<batch number>_<seq>`
  (`20260927_GP092601_0001`) — the batch number, not the cultivar, so two
  batches of one strain cloned on the same day never compute the same id
  (review CS-02). Production held no plants when the format changed.
- **Phase durations.** Cloning 7–14 days, with imported clones allowed up to 7
  days more for quarantine and acclimatisation (they leave at roughly the same
  time); vegetation 14–17 days; flowering 42–63 days, ended by trichome
  maturation tracked under a stereo or digital microscope with documented
  records. Harvest, coarse trim and defoliation are the GACP → GMP boundary
  (the owner's "harvest, course and defoliating"; the journey step used to
  read "cure", which comes after drying in the GMP wing — INS-11, wording
  `[NEEDS INPUT]`).
- **The phase path.** clone → nursery → veg → flower → drying → harvested,
  one stop at a time; nursery and drying are optional stops, destroyed is
  reachable from anywhere, mother stock is off the path. A move to the same
  phase is a **room change** and keeps the phase clock; a move backwards is a
  correction (QA authority, reason required); a terminal move needs a reason;
  flowering is only in a `flower` room; every move takes a row lock on the
  batch and is dated no later than the facility's today and no earlier than
  the batch's latest phase event (review CS-01, CS-06, CS-16, CS-17).
- **Closing a batch.** The plants a waste manifest declared destroyed are
  settled as `destroyed` (counted off the end of the batch, the manifest named
  in the reason); the rest of the active plants as `harvested` (review CS-07).
- **Potency grades.** The official ImB product pages — see
  `docs/PRODUCT-CATALOGUE-2026-09.md`.
- **Phenotype.** Still free text on the mother; the app carries no verified
  phenotype list.

## Who does what (amended 2026-09-05)

QA (`QA_MGR`) is a floor writer: it registers batches, generates their plant
ids, **moves them through their phases**, edits the cultivar master, keeps the
mother bank and initiates clone runs. QC still writes none of it.

## A name that was wrong

The bank derived `generations` meaning "how many clone runs this mother was cut
in" — which is not the `-2` in the owner's id. That reading is now `times_cut`;
`generation` means only the mother's own generation.

## The specification files the owner sent (2026-09-05) — historical

*This section is the analysis made on 2026-09-05, kept as the record of how
the pages were read. The question it raised was answered the same evening
(the pages ARE the ImB specification; they were imported as products, C-1)
and overtaken on 2026-09-18 (the fitted specifications replace the flat ±10 %
windows everywhere). The catalogue comparison below is against the retired
ladders. Do not act on it; see `PRODUCT-CATALOGUE-2026-09.md`.*

`PP_ImB_Specifications_Tran01-1-19.pdf` and `PP_ImB_Specifications_Tran02-20-48.pdf`
(Drive, 2026-08-31) — 48 one-page ImB Product Specifications, read through the
Drive connector's text extraction (the PDFs themselves were too large for the
connector to hand over, so the layout was not seen; the text was).

What they are: **one page per product**, not one page per strain. A product
is a strain at a nominal Total Δ9-THC, coded `<strain>_THC<nominal>:CBD1`
(e.g. `BG_THC26:CBD1`), with an acceptance window of **nominal ± 10 %
relative** (`23.40 – 28.59 %` for 26; every page's window is 0.90× to 1.10×
its nominal). Assay "per target grade as per Section 01"; the rest of the page
is the shared analytical table (CBD ≤ 1.0 %, CBN ≤ 1.0 %, foreign matter,
LoD ≤ 12 %, microbiology cat. C, …), 400 g triplex alu bag. Document code
`QCSP 001 v.03` on every page — the same code the app's catalogue import
defaults to.

How they compare with the catalogue the app holds (`app/data/imb_grade_ladders.json`,
imported into `qc_potency_specs` as tiered ladders):

- The 48 pages cover **22 strains**, all of which exist in the catalogue as
  strains (all BASE family). No strain is missing.
- As **products**, 39 of the 47 codes the text yields are **not in the
  catalogue** (the catalogue's Grape Pie products are THC28 / 24 / 20 / 16;
  the PDFs sell Grape Pie as THC26, THC24, THC18, THC16 and THC28). Of the 8
  codes that do match, **7 have a different window**: the catalogue's tiers
  are absolute bands (Spec II 22.00–26.00) where the PDF's are ± 10 %
  relative (21.60–26.39).
- So the two sources described the same strains with two different grade
  schemes. **Answered by the owner on 2026-09-05 (22:28):** the per-product
  pages are the ImB specification and were imported as products
  (`POST /qc/products/import`); a batch carries a TARGET product at
  registration. **Superseded on 2026-09-18:** the ±10 % windows of these pages
  are retired in favour of the fitted specifications (`import-fitted`), which
  approve as a new document version and retire the v.03 rows.

What was built follows the catalogue: the batch form registers against the
cultivar and its APPROVED products; a clone run names the product the
material is propagated against (`clone_runs.product_id`; the ladder snapshot
`potency_spec_id` of 0065 was dropped in 0067).

<details>
<summary>All 48 pages as extracted (strain · product code · window · catalogue match)</summary>

| # | Strain | Product code | Window | Catalogue |
|---|---|---|---|---|
| 1 | Blue Gelato | `BG_THC26:CBD1` | 23.40–28.59 % | not in the catalogue |
| 2 | Blue Sunset Sherbet | `BSS_THC24:CBD1` | 21.60–26.39 % | not in the catalogue |
| 3 | Cap Junky | `CJ_THC24:CBD1` | 21.60–26.39 % | not in the catalogue |
| 4 | Cap Junky | `CJ_THC20:CBD1` | 18.00–21.99 % | not in the catalogue |
| 5 | Fat Bastard | `FB_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 6 | Gorilla Glue | `GG_THC16:CBD1` | 14.40–17.59 % | not in the catalogue |
| 7 | Gorilla Glue | `GG_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 8 | Grape Pie | `GP_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 9 | Grape Pie | `GP_THC24:CBD1` | 21.60–26.39 % | catalogue II: 22.0–26.0 % |
| 10 | Grape Pie | `GP_THC16:CBD1` | 14.40–17.59 % | catalogue IV: 13.83–18.0 % |
| 11 | High Pro Amnesia | `HPA_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 12 | High Pro Amnesia | `HPA_THC22:CBD1` | 19.80–24.19 % | catalogue II: 19.39–24.75 % |
| 13 | Jelly Donutz | `JD_THC20:CBD1` | 18.00–21.99 % | same window |
| 14 | — | — | — | text extraction found no product code on this page |
| 15 | Orange Punch Mimosa | `OPM_THC22:CBD1` | 19.80–24.19 % | catalogue II: 19.0–25.0 % |
| 16 | Orange Punch Mimosa | `OPM_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 17 | Orange Punch Mimosa | `OPM_THC8:CBD1` | 7.20–8.79 % | not in the catalogue |
| 18 | Permanent Marker | `PM_THC12:CBD1` | 10.80–13.19 % | not in the catalogue |
| 19 | Scrambler | `SCR_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 20 | Amnesia Core Cut | `ACC_THC12:CBD1` | 10.80–13.19 % | not in the catalogue |
| 21 | Blue Sunset Sherbet | `BSS_THC20:CBD1` | 18.00–21.99 % | not in the catalogue |
| 22 | Cap Junky | `CJ_THC24:CBD1` | 21.60–26.39 % | not in the catalogue |
| 23 | Cap Junky | `CJ_THC28:CBD1` | 25.20–30.79 % | catalogue I: 25.25–30.0 % |
| 24 | Cap Junky | `CJ_THC26:CBD1` | 23.40–28.59 % | not in the catalogue |
| 25 | Cash Cow | `CC_THC14:CBD1` | 12.60–15.39 % | not in the catalogue |
| 26 | Chem Flyer | `CF_THC10:CBD1` | 9.00–10.99 % | not in the catalogue |
| 27 | Clemosa | `CLE_THC8:CBD1` | 7.20–8.79 % | not in the catalogue |
| 28 | Fat Bastard | `FB_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 29 | Gorilla Glue | `GG_THC16:CBD1` | 14.40–17.59 % | not in the catalogue |
| 30 | Grape Pie | `GP_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 31 | Grape Pie | `GP_THC28:CBD1` | 25.20–30.79 % | catalogue I: 26.0–30.0 % |
| 32 | Grape Pie | `GP_THC26:CBD1` | 23.40–28.59 % | not in the catalogue |
| 33 | Grape Pie | `GP_THC26:CBD1` | 23.40–28.59 % | not in the catalogue |
| 34 | Graps & Crème | `GRC_THC10:CBD1` | 9.00–10.99 % | not in the catalogue |
| 35 | High Pro Amnesia | `HPA_THC20:CBD1` | 18.00–21.99 % | not in the catalogue |
| 36 | Jelly Donutz | `JD_THC22:CBD1` | 19.80–24.19 % | not in the catalogue |
| 37 | Jelly Donutz | `JD_THC14:CBD1` | 12.60–15.39 % | not in the catalogue |
| 38 | Jelly Donutz | `JD_THC16:CBD1` | 14.40–17.59 % | not in the catalogue |
| 39 | Kush Crasher | `KC_THC16:CBD1` | 14.40–17.59 % | not in the catalogue |
| 40 | Motor Breath | `MB_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 41 | Orange Punch Mimosa | `OPM_THC18:CBD1` | 16.20–19.79 % | not in the catalogue |
| 42 | Orange Punch Mimosa | `OPM_THC10:CBD1` | 9.00–10.99 % | catalogue IV: 7.09–13.0 % |
| 43 | Orange Punch Mimosa | `OPM_THC20:CBD1` | 18.00–21.99 % | not in the catalogue |
| 44 | Permanent Marker | `PM_THC10:CBD1` | 9.00–10.99 % | not in the catalogue |
| 45 | Pure Michigan | `PUM_THC14:CBD1` | 12.60–15.39 % | not in the catalogue |
| 46 | Scrambler | `SCR_THC20:CBD1` | 18.00–21.99 % | not in the catalogue |
| 47 | Sleepy Joe | `SJ_THC10:CBD1` | 9.00–10.99 % | not in the catalogue |
| 48 | Wedding Crasher | `WC_THC24:CBD1` | 21.60–26.39 % | not in the catalogue |

</details>

## Tests

- Backend: `tests/test_propagation.py` (17) — gating, derived fields, the
  facility-wide campaign numbers, the next-code rules, the inherited line of
  a later generation, one line per mother number, concurrent registrations,
  the caps, the acronym head, the null-vs-empty ids, the frozen runs of a
  filled batch, the run lifecycle, and the re-issued catalogue page
  (CS2-01) — plus the propagation cases in `tests/test_cultivation.py` (the
  clone ids of a filled batch, a failed run, the fill lock).
- Frontend: `tests/frontend/propagation-view.test.js` — who is offered what,
  the chooser's product lines and the panel, the pre-filled batch number, the
  strip's position / next step / handoff / animation / focus, the bank's
  derived columns and its segments, the parent chooser by product code, the
  run form's filtering and null-vs-zero, the unset run date, finishing a run.

## Rollout

- Migrations `0065`, `0066`, `0067` and `0070` (three new tables; the id
  segments; the line key without the product). `0067` and `0070` refuse to
  run over pre-existing mother rows; production has none.
- The demo seeder does not seed mothers or runs; the bank starts empty and is
  filled from the Mother bank tab. A mother needs an APPROVED product and an
  open selection campaign first.
- A cultivar shows its products once they are in the catalogue — follow the
  rollout in `PRODUCT-CATALOGUE-2026-09.md`: import the ImB pages **for the
  strain renames only, without approving them**, import the fitted export
  (`POST /qc/products/import-fitted`), then approve each strain's fitted set
  in one sitting as a second QC person or the QP. Do **not** import or
  approve the retired ladders (`POST /qc/potency-specs/import` is refused once
  any product is APPROVED, and before that it would install the scheme the
  owner retired on 2026-09-18).
