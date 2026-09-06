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

The per-strain potency ladders in `qc_potency_specs` (`PP-QC-SPEC-001`), imported
from the owner's ImB handoff catalogue (`app/data/imb_grade_ladders.json`,
`qc/potency_import.py`) and joined to the cultivar master. A ladder carries the
strain (through `cultivars`) and its grades (`qc_potency_spec_ranges`: Spec I is
the top range, descending). `qc/spec_html.py` renders the same data as the ImB
specification document. So "choose the cultivar from the product
specifications" means: **the cultivar chooser shows each cultivar with its
ladder**, and the batch and the clone run record which ladder they were
registered / propagated against.

## Design

### Who registers

| Action | ADMIN | OWNER / CEO / COO | CU_MGR | QA_MGR | others |
|---|---|---|---|---|---|
| Register a batch, generate its plant ids | ✅ | ✅ | ✅ | ✅ | — |
| Initiate / finish a clone run | ✅ | ✅ | ✅ | ✅ | — |
| Move a batch through its phases | ✅ | ✅ | ✅ | — | — |
| Cultivar master | ✅ | ✅ | ✅ | — | — |
| Register / edit a mother plant (the bank) | ✅ | ✅ | ✅ | — | — |
| Read all of it | every role above USER | | | | |

`_REGISTRARS` in `cultivation.py` and `_INITIATORS` in `propagation.py` are the
same set: a clone run is how a batch begins, so whoever registers one initiates
the other. QA registers and initiates; it does not run the floor (moves,
master data, the bank stay `_WRITERS`).

### Registering from the specification

- `GET /cultivation/cultivars` returns each cultivar **with** `spec`: the
  APPROVED ladder if one exists, else the newest DRAFT (flagged), else `null`.
  One query (lateral join + folded grades).
- `GET /cultivation/batch-code?cultivar_id=` suggests the next batch number.
- The batch form: the cultivar chooser's sub-text is the grade line
  (`I 26.00–30.00 · II 22.00–26.00 · …`, `DRAFT` when it is one, "no product
  specification yet" when there is none); the panel beneath shows strain,
  `PP-QC-SPEC-001 vX`, APPROVED / DRAFT, and the grade table. Picking a
  cultivar re-fills the batch number through `GF.codeField` with the cultivar
  code as the fixed head.

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
  specification.

### The mother bank and clone runs (migration 0065)

- `mother_plants` — one row per mother: `code` (the unique ID), `cultivar_id`,
  `phenotype` (free text, nullable), `room_id` + `position` (the mother room
  and the pot / location), `started_on` (established; age is derived from it),
  `source`, `status` active / retired / destroyed, `note`.
- `clone_runs` — one cutting event: `cultivar_id`, `started_on` (**the date of
  cloning initiation**, defaults to the facility's today), `planned_count`,
  `room_id`, `batch_id` (the registered batch it feeds, SET NULL), `code`
  (optional), `potency_spec_id` (the APPROVED ladder snapshotted at
  initiation — the propagation-material specification), `status` started /
  transplanted / failed, `finished_on`, `note`.
- `clone_run_mothers` — which mothers the run was cut from, `cuttings` per
  mother (nullable = not counted per mother).

**Derived, never stored:** a mother's `age_days`, `last_cut_on`,
`generations` (runs it was cut in) and `cuttings_total` are computed from
`started_on` and `clone_run_mothers` on every read. A stored counter would
drift from its evidence.

Rules the server enforces: a run's mothers must be active and of the run's
cultivar; the batch a run feeds must be open and of the same cultivar; a
duplicate mother ID is a 409; a destroyed mother is not reinstated; a finished
run does not change again.

Routes (all under `/cultivation`): `GET/POST /mothers`, `GET /mothers/next-code`,
`PATCH /mothers/{id}`, `GET/POST /clone-runs`, `PATCH /clone-runs/{id}`.

## Conventions — settled by the owner (2026-09-05/06)

- **Batch number.** `GP072501` = strain abbreviation + `MMYY` + sequence, the
  nth cloning batch of that strain in that month. Confirmed as built.
- **Mother ID.** `GP26_S1M03-2_020`: strain abbreviation + potency grade (the
  product) · `S1` the selection campaign, numbered **facility-wide** · `M03`
  mother plant number of that campaign · `-2` the mother's own generation ·
  `_020` its clone number in stock. Composed by the server from columns
  (migration 0067), not typed.
- **Clone ID.** `GP26_S1M03-2_020-03.147`: the mother's id + the cutting
  number (01–99) + the clone within that cutting (001–999). A mother is cut
  6–9+ times at 200–300 clones each.
- **Phase durations.** Cloning 7–14 days, with imported clones allowed up to 7
  days more for quarantine and acclimatisation (they leave at roughly the same
  time); vegetation 14–17 days; flowering 42–63 days, ended by trichome
  maturation tracked under a stereo or digital microscope with documented
  records. Harvest, cure and defoliation are the GACP → GMP boundary.
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

## The specification files the owner sent (2026-09-05)

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
- So the two sources describe the same strains with two different grade
  schemes. Which one is the specification a batch is registered against —
  and released against — is the owner's call:
  `[NEEDS INPUT: are the per-product ± 10 % pages the current ImB
  specification, superseding the tiered ladders imported in August? If so the
  potency catalogue should be re-imported from these pages (one product =
  one nominal, window = ± 10 %), and a batch could carry a TARGET product at
  registration.]`

This does not change what was built: the batch form registers against the
cultivar and shows whatever ladder `qc_potency_specs` holds; a clone run
snapshots that ladder. When the catalogue is corrected, both follow it.

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

- Backend: `tests/test_propagation.py` (7) and three additions to
  `tests/test_cultivation.py` — gating, derived fields, the next-code rules,
  same-cultivar rules, the specification snapshot, the run lifecycle.
- Frontend: `tests/frontend/propagation-view.test.js` — who is offered what,
  the chooser's grade lines and the panel, the pre-filled batch number, the
  strip's position / next step / handoff / animation / focus, the bank's
  derived columns, the run form's filtering and null-vs-zero, finishing a run.

## Rollout

- Migration `0065` is additive (three new tables); nothing existing changes.
- The demo seeder does not seed mothers or runs; the bank starts empty and is
  filled from the Mother bank tab.
- A cultivar shows grades only once its ladder is in `qc_potency_specs`
  (import the ImB catalogue via `POST /qc/potency-specs/import`, then approve
  per cultivar).
