# The official ImB product catalogue

**Date:** 2026-09-06 · **Status:** implemented on
`claude/weekly-read-flow-setup-yft7if` (PR #52) · **Ships as:** tasks migrations
`0066`/`0067`, `app/api/qc/products.py`, `app/plantids.py`,
`app/data/imb_products.json`.

## What the owner said

> "The two specification PDFs are official regarding the strains and potency
> ranges and grades and codes."
> "The nominal values for every potency grade range per strain needs to be the
> same as in the 2 pdf documents with ImB Specifications I provided."

## What the documents are

`PP_ImB_Specifications_Tran01-1-19.pdf` and `PP_ImB_Specifications_Tran02-20-48.pdf`
(Drive, 2026-08-31): **48 one-page product specifications**. One page is one
strain at one nominal Total Δ9-THC:

| | |
|---|---|
| Product code | `<ABBR>_THC<nominal>:CBD1` — `GP_THC26:CBD1` |
| Nominal | `26.00 % ± 2.60 %` |
| Window | `23.40 – 28.59 %` = nominal × 0.90 … nominal × 1.10 − 0.01 |
| Document | `QCSP 001 v.03` |
| Packaging | 400 g triplex alu bag, `PET 12 · ALU 7 · PE 80` |

The ± 10 % relative rule holds on **all 48 pages** (verified by extraction).
Six pages are reprints of a product that also appears elsewhere, so the
catalogue is **42 distinct products across 22 strains**. Eight pages print a
strain name that differs slightly from the August handoff catalogue (Jelly
Donutz / "Jelly Donuts", Wedding Crasher / "Wedding Crusher", Pure Michigan /
"Pure Michigen", Graps & Crème / "Grapes And Cream", Clemosa / "Clemosa A
Bud"); both spellings are kept in the seed file, the August name as `strain`
and the page's as `strain_printed`. `[NEEDS INPUT: which spelling is
canonical?]`

## Why a new table rather than the existing ladders

`qc_potency_specs` models a per-cultivar **ladder**: tiers I…IV tiling
`[floor, 30 %]`, **one APPROVED ladder per cultivar**, non-overlapping, top
exactly 30.00 %. The official scheme breaks all three:

- a strain sells as several products at once (Grape Pie: THC 28, 26, 24, 18, 16);
- their windows **overlap** (GP26 23.40–28.59 and GP24 21.60–26.39);
- `CJ_THC28`'s window reaches **30.79 %**.

So `qc_products` is its own table and the ladders are left exactly as they are,
readable, so CoQs issued before the catalogue keep printing the grade they were
issued with. **Approving a cultivar's first product supersedes that cultivar's
APPROVED ladder** — two live grade schemes would be two answers to one question.

## The table

`qc_products`: `cultivar_id`, `product_code`, `grade`, `nominal_pct`,
`window_min`, `window_max` (**stored, not derived** — the printed page is the
specification), `doc_code` / `doc_version`, `source` (the pages it came from),
`status` DRAFT → APPROVED → SUPERSEDED, `effective_date`, `approved_by`,
`notes`. `UNIQUE(org, product_code, doc_version)` plus a partial unique index
for one APPROVED row per code. No 30 % cap anywhere.

## Routes

| Route | Who | What |
|---|---|---|
| `GET /qc/products[?cultivar_id&status]` | elevated | the catalogue + `tested {n, avg, min, max}` |
| `GET /qc/products/{id}` · `…/potency-history` | elevated | the product + its measured history |
| `POST` / `PATCH /qc/products` | QC writers | author a page; DRAFT only for edits |
| `POST …/approve` · `…/supersede` | head of QC | approver ≠ author; approve retires the ladder |
| `POST /qc/products/import {dry_run}` | head of QC | the packaged 42 pages, idempotent |
| `GET /qc/products/conformance?cultivar_id&total_d9_thc[&product_id]` | elevated | which products a value satisfies |
| `GET /qc/products/{id}/document` | elevated | the A4 page |

**Conformance replaces disposition.** The ladder answered "which tier?" and
there was exactly one. Official windows overlap, so the answer is a **list**,
plus `nearest` (the highest-nominal product the value satisfies) for a reader
who wants one name. Which product a lot ships as is a packaging decision.

## "Tested so far"

Three sources, each labelled, never blended:

1. **product-level** — APPROVED CoQs that name the product;
2. **cultivar-level** — APPROVED CoQs that name only the cultivar;
3. **certificate-level** — Total Δ9-THC results on APPROVED/RELEASED
   certificates of that cultivar's batches, reached through the batch code.
   A text join, and it says so.

The measured value is always `qc_coq_lines.result_numeric` for the parameter
with `computed_kind='total_thc'` (Ph. Eur. 3028: THC + 0.877 × THCA), the same
read the CoQ's own grade uses. A lot with no measured total contributes nothing.

Per mother plant, `GET /cultivation/mothers/{id}/potency` reports the product's
figures plus a `traced` subset — lots descended from a batch that mother was
cut into. Usually empty, and it never borrows the strain's number.

## Identity strings

`app/plantids.py` composes every one:

| | |
|---|---|
| Product | `GP_THC26:CBD1`, window from `window_for(26)` |
| Mother plant | `GP26_S1M03-2_020` |
| Clone | `GP26_S1M03-2_020-03.147` |
| Legacy plant | `20260706_GP_0001` |

## Rollout

1. Deploy `0066` and `0067` (0067 refuses to run over pre-existing mother rows;
   production has none).
2. `POST /qc/products/import {"dry_run": true}` as a QC manager, then for real.
   Expect 42 created, 22 cultivars resolved or created.
3. Approve per product as a **different** QC person or the QP. Each cultivar's
   first approval supersedes its ladder.
4. Set target products on open batches (`PATCH /cultivation/batches/{id}`).
5. Compile CoQs with `product_id` from then on.

## Verified against the controlled specifications (2026-09-06)

The owner supplied the specification archive: one folder per strain, one PDF per
grade, document code `QCSP_001_<ABBR>-<TIER>_v.01`. Read directly from those
PDFs.

### Strain spellings — RESOLVED

Neither column of the seed file was uniformly right; the correct set is a mix.
The specification header is the authority:

| Specification header | was `strain` | was `strain_printed` |
| --- | --- | --- |
| **JELLY DONUTZ** | Jelly Donutz ✓ | Jelly Donuts ✗ |
| **WEDDING CRASHER** | Wedding Crasher ✓ | Wedding Crusher ✗ |
| **PURE MICHIGEN** | Pure Michigan ✗ | Pure Michigen ✓ |
| **GRAPS AND CREME** | Graps & Crème ✗ | Grapes And Cream ✗ |
| **CLEMOSA A BUD** | Clemosa ✗ | Clemosa A Bud ✓ |
| **SLEEPY JOY** | — | — |

"A Bud" is part of the strain name, not a phenotype marker. `Sleepy Joy` was not
previously known to be contested; a companion file in the archive calls it
"Sleepy Joe" and that is wrong.

### Grade sets and nominals — CONFIRMED CORRECT

`imb_products.json`'s nominals match the specification archive on **all 22
strains, zero differences** (checked programmatically). Grape Pie I–V =
28/26/24/18/16, Cap Junky I–IV = 28/26/24/20, Jelly Donutz I–IV = 22/20/16/14.

### The windows DO overlap, and the documents say so

Every specification PDF sampled prints the window as **±10 % relative**, upper
bound `nominal × 1.10 − 0.01`:

| Document | Header | Window |
| --- | --- | --- |
| `QCSP_001_GP-I_v.01` | `GRAPE PIE 28.00% ± 2.80%` | 25.20 – 30.79 % |
| `QCSP_001_GP-II_v.01` | `GRAPE PIE 26.00% ± 2.60%` | 23.40 – 28.59 % |
| `QCSP_001_GP-III_v.01` | `GRAPE PIE 24.00% ± 2.40%` | 21.60 – 26.39 % |
| `QCSP_001_CJ-I_v.01` | `CAP JUNKY 28.00% ± 2.80%` | 25.20 – 30.79 % |
| `QCSP_001_GG-I_v.01` | `GORILLA GLUE 18.00% ± 1.80%` | 16.20 – 19.79 % |
| `QCSP_001_GG-II_v.01` | `GORILLA GLUE 16.00% ± 1.60%` | 14.40 – 17.59 % |

GP I and GP II overlap across 25.20–28.59; GG I and GG II across 16.20–17.59.
**This is a quality finding, not a modelling choice.** A measured 26.00 % Grape
Pie satisfies Grade I, Grade II *and* Grade III as issued, so "which grade is
this batch?" has three correct answers and the certificate cannot be derived
from the result alone.

### `_grades_data.json` is NOT the issued specification

The archive root also holds `_grades_data.json`, which encodes a **different,
non-overlapping** scheme — per-grade absolute tolerances (Grape Pie II `26 ±
0.6` → 25.40–26.60; Cap Junky I `28 ± 1` → 27.00–29.00), every one of them ≤ 10 %
and chosen so neighbouring grades do not touch. It matches the owner's stated
intent exactly. It does **not** match the PDFs:

- Grape Pie IV nominal **20**, but the PDF says **18**;
- Cap Junky given **five** grades, but only four PDFs exist (I–IV);
- Jelly Donutz given **three** grades, but four PDFs exist (I–IV);
- no PDF prints any of its tolerances.

Its **strain names are the correct ones**, which is how the spellings above were
cross-checked. Read it as a proposal for a future `v.02`, not as the current
specification. `_master_spec.json`'s `gr` block matches the PDFs' grade sets, but
its `names` map has all six spellings wrong.

**[NEEDS INPUT]** Which is the controlled state: the issued `v.01` PDFs
(overlapping ±10 %), or the non-overlapping tolerances in `_grades_data.json`?
The app currently implements the PDFs. Adopting the non-overlapping scheme is a
data change, not a code change — `qc_products` already stores `window_min` /
`window_max` per product and never assumes ±10 %.

**[NEEDS INPUT]** The archive PDFs are `v.01`; the 48-page consolidated document
this catalogue was originally seeded from is `QCSP 001 v.03`. Which supersedes
which?

## Open

- ~~Canonical strain spellings.~~ **RESOLVED 2026-09-06** — see above.
- ~~Whether a CoQ whose Total THC falls outside its product's window should be
  blocked from issuance.~~ **DECIDED 2026-09-06 (owner): no, do not block.**
  A Total Δ9-THC outside the chosen product's window is reported on the CoQ and
  printed on the document; it does not stop issuance.

  Two separate rules are easy to confuse here, and this decision touches only
  the second:

  | rule | what it judges | blocks issuance? |
  | --- | --- | --- |
  | `overall_conform` | every CoQ line against its **specification** limit | **yes** — `coq_aggregation.py` returns 409 rather than render a certificate asserting conformance for a batch that does not conform. Unchanged; it is a GxP control. |
  | product-window conformance | Total Δ9-THC against the **product's** ± 10 % window | **no** (this decision) |

  **Not yet built.** An earlier revision of this file claimed the window verdict
  "currently prints *does not conform* and is still renderable". That was wrong.
  `qc_coq.product_id` is validated at compile and stored, but nothing reads it
  back: `_coq_disposition()` returns `None` unless the CoQ carries a frozen
  *ladder* id, and `_coq_grade_value()` renders only the ladder disposition. So
  a product-graded CoQ today shows **no grade at all**, rather than a
  non-conforming one. Outstanding work: a product branch in `_coq_disposition`,
  `product_code` / `product_conforms` on `_coq_out`, and a product string in
  `_coq_grade_value`.
- The header document code on the rendered A4 product page
  (`QCSP 001_GP-THC26_v.03`) follows the archive's per-page style; the v.03
  pages' exact header was not visible in the text extraction.
