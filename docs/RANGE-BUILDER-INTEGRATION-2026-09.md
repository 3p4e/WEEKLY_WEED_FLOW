# Integrating the potency range builder into the app (2026-09-07)

The range builder currently lives outside the app, as a published artifact:
one strain per Total Δ⁹-THC scale, every measured result as a dot, nominals
switched on and off, a symmetric tolerance handle on each band, a border point
between neighbours, and a solver that proposes the tolerances covering the most
results without overlap. It reads a static snapshot of
`CoQ_Analysis_Master_v10.xlsx` and writes nowhere.

This note is the analysis of where it belongs inside the app — for the 22
strains already in the catalogue and for strains that do not exist yet.

## The headline: the backend was already written for this

`qc_products` (migration tasks `0066`) stores `window_min` and `window_max` as
**explicit numerics**, not as a rule applied to the nominal. And
`_resolve_window()` in `backend/app/api/qc/products.py` already honours a
supplied pair rather than forcing ± 10 %, with this reasoning in its docstring:

> nominal and window default to the printed rule (± 10 % relative); an
> explicitly supplied pair is kept as given, because the page is the
> specification and a page that prints something else must be recordable.

That sentence was written to record what the ImB pages print. It happens to be
exactly the hook a range builder needs. **No migration and no schema change is
required to store a built ladder** — a proposal is a set of
`(cultivar, product_code, grade, nominal_pct, window_min, window_max)` rows,
which is precisely what `POST /qc/products` already accepts.

This is the difference between a feature and a rewrite, so it is worth stating
first.

## Four seams, in the order they matter

### 1. The dots already have an endpoint

`GET /qc/products/{id}/potency-history` returns every measured Total Δ⁹-THC that
bears on a product's strain, in three labelled strengths of evidence:

| key | what it is |
| --- | --- |
| `tested` | APPROVED CoQs that name **this product** |
| `cultivar_level` | APPROVED CoQs naming only the cultivar |
| `certificate_level` | Total THC on RELEASED/APPROVED certificates, reached through the batch code (a text join, and it says so) |

Each row carries `total_thc`, `lot_code`, a date and a `conforms` flag. **That is
the builder's dot data**, live, already conformance-annotated, and already
careful about provenance in a way the workbook snapshot is not.

Wiring the builder to this replaces the 106 frozen values with whatever the QC
database holds at the moment the page opens, and the three sources map onto three
dot styles rather than one.

### 2. The write path exists, and it is already two-person

The builder proposes; the app records. That flow is:

1. `POST /qc/products` per grade — DRAFT, with the built window supplied
   explicitly (`window_min` / `window_max`).
2. `POST /qc/products/{id}/approve` — the backend **refuses the author**, so a
   second QC person or the QP has to approve.
3. Approving a strain's first product retires that strain's legacy ladder.

So a built ladder enters as DRAFT and becomes effective only under the existing
GxP control. Nothing new has to be invented for the approval discipline.

### 3. New strains resolve through the importer's own function

`resolve_or_create_cultivar()` in `backend/app/api/qc/potency_import.py` is
already shared by both catalogue importers. It creates a cultivar from acronym +
strain name, and — importantly — **refuses to reassign an acronym** that another
strain already holds, because "a mis-assigned acronym would print a wrong plant
id forever". The builder's *"create a new strain"* maps straight onto it, and
inherits that guard for free.

The builder's own strain code (`PS` for Purple Sunrise) becomes the cultivar
`code`, which is the head of every batch number and mother ID for that strain.
That is a heavier consequence than it looks in the artifact, and the UI should
say so at the point of creation.

### 4. The UI home is the potency view

`web/gf/qcpotency-view.js` registers a full-page view keyed `qcpotency` in the
QMS Studio zone, guarded to any role that is not `USER`, with role gates already
imported from core (`GF.QC_HOQC`, `GF.QC_WRITERS`). It is 196 lines and owns the
ladder list, the detail panel, approve/supersede and the A4 document link.

The builder becomes a **third mode** on that view, beside the ladder list and the
product catalogue — not a new nav entry. The reasons: the role gate is already
right, the strain list is already loaded there, and a range builder that lives
somewhere other than where grades are approved would be a tool people forget.

## What actually has to be built

Everything above is a seam that exists. These are the gaps.

| # | Gap | Why it matters |
| --- | --- | --- |
| 1 | **A ladder-level create.** `POST /qc/products` writes one product; a proposal is 3–5 at once. | Creating five products one call at a time can half-fail, leaving a strain with a partial ladder and no record of intent. A `POST /qc/products/ladder` that validates the whole set (non-overlap, ≤ 10 %, nominal inside window) and writes it in one transaction is the honest shape. |
| 2 | **Cultivar-level potency history.** `potency-history` is keyed on a product id. A strain with no product yet has no endpoint that returns its results. | This is exactly the case the builder is for — building a ladder for a strain that does not have one. Needs `GET /qc/cultivars/{id}/potency-history`, reusing `_potency_history`'s last two queries. |
| 3 | **Window provenance.** Nothing records that a window came from the builder, against how many results, on what date. | `source` (text, 300) can carry a sentence, and `notes` can carry the summary. That is enough to start and worth doing deliberately rather than leaving blank — an auditor asking "why is this ± 1.17?" needs an answer in the row. |
| 4 | **The solver has to move server-side** if the app is to propose, not just record. | It is ~80 lines of integer DP with no dependencies. It belongs in `backend/app/plantids.py` beside `window_for`, where it can be unit-tested against the real catalogue instead of only in a browser. |

Note what is **not** on this list: no migration, no new table, no change to
`qc_coq`, no change to conformance. The catalogue's shape already fits.

## The decision this does not settle

The builder makes it easy to author non-overlapping ladders. The issued
specification is ± 10 % and **16 of its 20 adjacent grade pairs overlap**, with
four dead bands on top (see `docs/PRODUCT-CATALOGUE-2026-09.md`). Building this
integration does not answer which of those is controlled — it only makes either
one cheap to express.

Until the owner settles that, the honest default is: **the builder writes DRAFT
products and never touches an APPROVED one.** A proposal is a proposal.

## Sequence, if it is built

1. Cultivar-level potency history endpoint (gap 2) — smallest, unblocks the rest.
2. Solver into `plantids.py` with tests against all 22 strains (gap 4).
3. `POST /qc/products/ladder`, transactional, with the non-overlap validation
   (gap 1) and provenance written into `source`/`notes` (gap 3).
4. The builder as a third mode on `qcpotency`, reading live results and writing
   DRAFT ladders.
5. Retire the artifact, or keep it as the offline sketchpad it is good at.

## Provenance of the tool this describes

- Artifact: *Potency Range Builder* — nominals, tolerance handles, border points,
  overlap/gap strips, per-strain result editing, new-strain creation, and an
  exact integer solver with an optional Claude-written explanation of each
  proposal. The ranges are computed, never generated; the model only interprets
  them.
- Result data: `CoQ_Analysis_Master_v10.xlsx`, sheet "CoQ Parameter Tracker v10",
  column M — 106 results across 72 batches and 20 strains, de-duplicated.
