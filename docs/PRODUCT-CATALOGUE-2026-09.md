# The official product catalogue

**Date:** 2026-09-06, revised 2026-09-27 (and again after the second review,
fix round 2: INS2-01, INS2-03, INS2-06, INS2-12, QR-02, QR-09, QR-11) ·
**Status:** backend and QC screens
implemented (review 2026-09-27, §2.1 / §2.11 — plan commits 2 and 6, INS-03,
INS-04, INS-05, INS-13, QC-30, AD-12); the fitted specifications themselves are
loaded by the owner from the Potency Spec Service export (see "Decisions
recorded 2026-09-27") · **Ships as:** tasks migrations `0066`/`0067`,
`app/api/qc/products.py`, `app/api/qc/spec_html.py`, `app/plantids.py`,
`app/data/imb_products.json`, `web/gf/qcpotency-view.js`, `web/gf/qccoa-view.js`.

## Decisions recorded 2026-09-27

Three owner decisions that the earlier revisions of this file, `HANDOFF.md`
and PR #52 either left open or claimed done. What is built for each:

1. **Windows are explicit; the flat ±10 % rule is retired as a grading method
   (owner, 2026-09-18: "±10 % flat is not gonna work so the fitted approach is
   applicable everywhere").** `POST /qc/products`, `POST /qc/products/ladder`
   and both importers store the window they are given and derive nothing;
   `plantids.window_for` is reference-only (it describes what the v.03 pages
   print). ±10 % of the nominal survives as the **ceiling** a window may not
   exceed (owner, 2026-09-06 — `products._TOLERANCE_CEILING`), fitted or not.
   The fitted specifications enter through `POST /qc/products/import-fitted`,
   whose body is the Potency Spec Service's own export
   (`GET /api/specs?status=finished` on the service, source on branch
   `claude/sync-potency-spec-service`, `tools/potency-spec-service/`), plus the
   document version they were issued under. Each range becomes one DRAFT
   product `<ID>_THC<nominal>:CBD1` with the window the service prints
   (`N − t … N + t − 0.01`), checked against the service's own arithmetic, the
   ceiling and non-overlap within the strain; `source` records the service id,
   finish date and result count, `notes` the fitted tolerance and the
   decision. Nothing is loaded from git: the copy of the service on the branch
   is older than the live one (INS-14), so the export is the source of truth.
   **One specification version is live per strain, and supersession only runs
   forward** (see "The version rule" below): approving a product supersedes
   the cultivar's APPROVED products of an *older* `doc_version` (and, as
   before, the same code's older row and the cultivar's ladder); a product of
   a version older than the strain's live one is refused.
2. **Strain names as in the specifications (owner, 2026-09-06).** Where both
   controlled sources agree, `imb_products.json` now carries the printed
   spelling as canonical — `Pure Michigen` (was "Pure Michigan") and `Clemosa A
   Bud` (was "Clemosa") — with the retired spelling under `retired_spellings`;
   the import renames a cultivar still carrying it and keeps the old spelling
   in the cultivar's note. Those two are **settled** (owner 2026-09-06T18:02,
   "CORRECT AS IN THE SPECIFICATIONS"). Four names are **still disputed**,
   because the two controlled sources disagree (table under "Strain
   spellings" below); each keeps the August spelling as `strain`, is flagged
   `spelling_disputed`, and both spellings resolve to the ONE cultivar (an
   alias, never a second cultivar, never a rename):

   | code | `strain` (kept) | other spelling | where the other spelling lives in the file |
   | --- | --- | --- | --- |
   | `JD` | Jelly Donutz | Jelly Donuts | `strain_printed` |
   | `GRC` | Graps & Crème | Grapes And Cream | `strain_printed` |
   | `WC` | Wedding Crasher | Wedding Crusher | `strain_printed` |
   | `SJ` | Sleepy Joe | Sleepy Joy (per-strain folder) | `disputed_spellings` |

   SJ is the odd one: the page and the cultivar master both print "Sleepy
   Joe", and "Sleepy Joy" is the per-strain folder's spelling, so it could not
   live in `strain_printed`. The fix round added a `disputed_spellings` list
   to the SJ row; `products._spellings` / `catalogue_aliases` read it, so an
   `import-fitted` body naming "Sleepy Joy" resolves to the SJ cultivar
   instead of being reported as a conflict and skipped
   (`test_import_fitted_resolves_sleepy_joy_to_sleepy_joe`). The owner still
   has to pick the four spellings.
3. **The out-of-grade rule (owner, 2026-09-06)** — see "Conformance" below.

Decisions the agent made in building this, to confirm with the owner:

- `nearest` (AD-12): the product whose window **contains** the value; when
  several do (the v.03 windows overlap), the one whose nominal is closest,
  the **lower** nominal on a tie (never over-label); when none does, the
  window whose edge is nearest above or below. `regrade_to` is `nearest`
  only when its window actually holds the value — a value in a dead band is
  not regraded to a grade that does not hold it.
- The formal OOS is a **person's act, tracked as a follow-up**, not opened by
  the system and not a gate (see "The out-of-grade rule as built"). The
  deviation itself is sent at compile to every Cultivation and Production
  manager (`potency_deviation`). Approval and issuance are not blocked
  ("NO for now", 2026-09-06).
- Which OOS settles the follow-up: one on the batch (case-insensitive), whose
  test name names Total Δ9-THC, that did not `invalidate` the result, and
  that belongs to this CoQ — opened at or after its compile, raised on a
  result it aggregated, or cited as its `oos_reference`. An older
  investigation of the same batch (say, the initial period's) does not settle
  a later re-test CoQ.
- Versions are ordered by the numbers they carry (`v.03` < `v.04` <
  `fitted 2026-09-15`), `products._version_key`; a version string with no
  digits sorts first. Name fitted versions so they sort after `v.03`.
- A fitted tolerance above the ceiling is refused on import rather than
  flagged: the service caps at 10 % itself, so nothing legitimate is refused.
- Version-level supersession on approval (point 1), which retires a strain's
  ImB products the moment its first fitted product is approved — forward
  only since fix round 2.

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
Bud"). Pure Michigen and Clemosa A Bud are settled and canonical; the other
four pairs are still disputed — see "Decisions recorded 2026-09-27" point 2.

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
| `POST` / `PATCH /qc/products` | QC writers — **API only**, no authoring screen | author a page with its **explicit** window; DRAFT only for edits; code ↔ grade ↔ nominal must agree (QC-30); no overlap with the strain's DRAFT/APPROVED siblings of the same `doc_version` (422; the v.03 pages exempt); validated before the write |
| `POST /qc/products/ladder` | QC writers — API only | a strain's whole grade set in one transaction — explicit windows, no overlap (within the body and with same-version products already on file), ceiling; overlaps with other versions reported |
| `POST …/approve` · `…/supersede` | head of QC | approver ≠ author; a product of a version older than the strain's newest APPROVED/SUPERSEDED version is refused (409); approve retires the same code, the cultivar's older document version and its ladder |
| `POST /qc/products/import {dry_run}` | head of QC | the packaged 42 v.03 pages, idempotent; renames retired spellings; refused (409) once any catalogue strain holds a later version — a dry run lists those strains under `refused` |
| `POST /qc/products/import-fitted {specs, doc_version, dry_run}` | head of QC | the Potency Spec Service export → DRAFT products with provenance |
| `GET /qc/products/conformance?cultivar_id&total_d9_thc[&product_id]` | elevated | `matching[]`, `nearest`, and per product `conforms` / `regrade_to` |
| `GET /qc/products/{id}/document` | elevated | the A4 page (`spec_html.py`, shared renderer with the ladder page) |

Once a cultivar has an APPROVED product, `POST /qc/potency-specs`,
`POST /qc/potency-specs/{id}/approve` and `POST /qc/potency-specs/import`
answer 409: the ladder is retired for that strain (QC-04). The QC screen
offers the ladder import only while the org has no product at all, and
withdraws the "Import ImB pages" button (keeping the dry run) once any
strain holds a product of a later version than v.03.

**The version rule (owner 2026-09-18; review QR-02).** One specification
version is live per strain and it only moves forward. Approving a product
supersedes the strain's APPROVED products of any *older* version; approving
a product of a version *older* than the newest version the strain has ever
had APPROVED (or since SUPERSEDED) is refused with 409 naming that version —
approving a retired v.03 ImB page can no longer retire a strain's fitted set.
The packaged v.03 import is refused once a later version exists for one of
its strains. Pinned by `test_an_older_version_is_never_approved_over_the_live_set`.

**The overlap rule (owner 2026-09-06 "ranges not overlapping"; review QR-09 /
INS2-06).** Every version except the packaged v.03 pages must be a set of
non-overlapping windows. `/ladder` and `import-fitted` check the whole set;
single-product `POST` and `PATCH` check the product against the strain's
DRAFT/APPROVED siblings of the same `doc_version` and answer 422 on an
overlap. The v.03 pages overlap as issued and are exempt
(`test_several_products_of_one_strain_coexist_with_overlapping_windows`,
`test_a_single_product_may_not_overlap_its_siblings_of_the_same_version`).

**Conformance.** The ladder answered "which tier?" and there was exactly one.
The v.03 windows overlap, so `matching` is a **list**; `nearest` is the one
product the value belongs to under the owner's next-grade rule (AD-12, above).
A CoQ compiled with `product_id` carries `potency.kind = "product"` with
`product_code`, `nominal`, `window_min/max`, `total_d9_thc`, `conforms`,
`matching`, `nearest`, `regrade_to`, and `product_code` / `product_conforms` /
`regrade_to` on the CoQ row; `matching` and `nearest` are computed against the
same **document version** the product belongs to, so an issued certificate's
verdict does not drift when the catalogue is re-cut. The document's Grade cell
reads `GP_THC26:CBD1 · nominal 26.00 % · window 23.40–28.59 % — conforms (Total
Δ9-THC 23.98 %) — QCSP 001 v.03`, or `… — does NOT conform (Total Δ9-THC
22.10 %) · REGRADED from GP_THC26:CBD1 to GP_THC24:CBD1 — …`.

**The out-of-grade rule as built (owner 2026-09-06; review INS2-01).** The
owner's words: "NO for now: a Total Δ9-THC outside the product's window does
not block issuance … a formal OOS regarding the batch disposition should be
opened and the value accepted and handed over as a deviation". When the
CoQ's Total Δ9-THC is outside the chosen product's window:

- the lot falls to `regrade_to` (the product whose window holds it, or none);
- at compile a `potency_deviation` notification goes to every Cultivation
  and Production manager of the org with the batch, product, value, window
  and regrade;
- the formal OOS on the batch disposition is a **tracked follow-up, never a
  gate**: the CoQ carries `regrade_oos_pending` (true while no such OOS
  exists, false once one does) and `regrade_oos` (its number) on the detail,
  compile and review responses; `GET /qc/coq?regrade_oos_pending=true` lists
  the regraded CoQs still owing one (`false` lists those that have it); the
  screen shows "formal OOS … pending" or the OOS number, and flags "OOS
  pending" on the CoQ list;
- approval and rendering go ahead without it. The §6.4.1 open-OOS gate at
  review and render exempts an open OOS naming Total Δ9-THC on a *regraded*
  CoQ's batch — it is the follow-up being done — while every other open OOS
  on the batch still blocks, and a Total Δ9-THC OOS on a CoQ that conforms
  to its product still blocks too;
- the .docx Grade cell prints `… · REGRADED from GP_THC26:CBD1 to
  GP_THC24:CBD1 — formal OOS on the batch disposition: PP-OOS-2026-0007`, or
  `… — formal OOS on the batch disposition: NOT YET OPENED`.

Pinned by `test_out_of_window_coq_is_regraded_flagged_investigated_and_handed_over`,
`test_regrade_oos_exemption_is_for_the_regraded_coq_only` and
`test_regrade_oos_match_is_case_insensitive_and_scoped_to_the_coq`
(`backend/tests/test_potency_coq.py`).

**The compile-form rule (review INS2-12).** A CoQ is certified against a
product of the batch's own strain. The compile form's product picker offers
only the products whose cultivar code is the typed batch number's head (the
longest match: `GPX0926…` is GPX, not GP); an unrecognised head shows every
product. The server refuses (422) a `product_id` whose cultivar is not the
batch's when the batch is registered in `plant_batches`; a batch id that is
not registered (a legacy or external lot) is not checked, because there is
nothing to check it against
(`test_compile_refuses_a_product_of_another_strain_for_a_registered_batch`).
The same form offers the testing period (initial release or a re-test with
its timepoint) and an optional explicit list of the batch's usable source
certificates.

## "Tested so far"

Three sources, each labelled, never blended:

1. **product-level** — APPROVED CoQs that name the product;
2. **cultivar-level** — APPROVED CoQs that name only the cultivar;
3. **certificate-level** — APPROVED/RELEASED certificates of that cultivar's
   batches. The certificate's Total Δ9-THC is **derived from its two
   component results** (Ph. Eur. 3028, the same `derived_total` every CoQ
   path uses; a transcribed total is refused everywhere since QC-10, so the
   old read of stored total rows was structurally empty). The certificate is
   attributed to the strain by the batch number's head — `batch_id` or
   `cultivation_batch` matching `^<code>[0-9]`, case-insensitively — or by an
   exact match with one of the cultivar's registered batch codes. A lot
   marked as an experiment (`＊`, owner 2026-09-16) is not used. A text join,
   and it says so (`test_certificate_level_history_is_derived_by_the_batch_code_head`).

For the two CoQ sources the measured value is `qc_coq_lines.result_numeric`
for the parameter with `computed_kind='total_thc'` (Ph. Eur. 3028: THC +
0.877 × THCA), the same read the CoQ's own grade uses. A lot with no measured
total contributes nothing.

Per mother plant, `GET /cultivation/mothers/{id}/potency` reports the product's
figures plus a `traced` subset — lots descended from a batch that mother was
cut into. Usually empty, and it never borrows the strain's number.

## Identity strings

`app/plantids.py` composes every one:

| | |
|---|---|
| Product | `GP_THC26:CBD1`; the window is stored per product (`window_for(26)` only describes what the v.03 page prints) |
| Mother plant | `GP26_S1M03-2_020` |
| Clone | `GP26_S1M03-2_020-03.147` |
| Legacy plant | `20260706_GP072501_0001` — the middle segment is the batch code (CS-02) |

## Rollout

1. Deploy `0066` and `0067` (0067 refuses to run over pre-existing mother rows;
   production has none). No further migration: the fitted windows are data in
   `qc_products`.
2. QC → Product catalogue: **Import ImB pages** — dry run, then for real (or
   `POST /qc/products/import`), **before** any fitted product exists: the
   import is refused once a strain holds a later version. It creates the v.03
   pages as DRAFT reference rows (idempotent) and renames an existing `PUM`
   "Pure Michigan" / `CLE` "Clemosa". Whether production already holds the
   v.03 rows is UNVERIFIED — an earlier revision of this file said it did,
   the 2026-09-27 inventory says `qc_products` is empty; read it off the host
   (`SELECT doc_version, count(*) FROM qc_products GROUP BY 1`) first. Do
   **not** approve the v.03 pages: the owner retired them (2026-09-18), and
   once the fitted set is approved they can no longer be approved at all.
3. Export the FINISHED fitted specs from the Potency Spec Service
   (`GET /api/specs?status=finished`), paste them into **Fitted
   specifications**, state the document version the owner issued them under
   (one that sorts after `v.03`, e.g. `v.04`), dry run, then import. Each
   strain's grades land as DRAFT products.
4. Approve per product as a **different** QC person or the QP. A cultivar's
   first approval supersedes its ladder; the first approval of the fitted
   version supersedes that cultivar's APPROVED v.03 products, if any — approve
   a strain's whole fitted set in one sitting.
5. Set target products on open batches (`PATCH /cultivation/batches/{id}`).
6. Compile CoQs choosing the product in the compile form from then on.

## Verified against the controlled specifications (2026-09-06)

The owner supplied the specification archive: one folder per strain, one PDF per
grade, document code `QCSP_001_<ABBR>-<TIER>_v.01`. Read directly from those
PDFs.

### Strain spellings — STILL OPEN (an earlier revision of this file wrongly said "resolved")

There are **two controlled sources and they disagree**. Both are dated
`01.06.2026`, both carry per-page document code `QCSP_001_<ABBR>-<TIER>_v.01`,
both are prepared by the QC Manager and reviewed by the QA Manager — so neither
supersedes the other on any evidence available here:

| Product | Per-strain folder document | `ImB_Specifications…Merged.pdf` |
| --- | --- | --- |
| `JD_THC22` | JELLY DONUT**Z** | JELLY DONUT**S** |
| `GRC_THC10` | **GRAPS AND CREME** | **GRAPES AND CREAM** |
| `SJ_THC10` | SLEEPY JO**Y** | SLEEPY JO**E** |
| `WC_THC24` | WEDDING CR**A**SHER | WEDDING CR**U**SHER |
| `CLE_THC8` | CLEMOSA A BUD | CLEMOSA A BUD — agree |
| `PUM_THC14` | PURE MICHIGEN | PURE MICHIGEN — agree |

Settled regardless of which source wins: **"A Bud" is part of the Clemosa strain
name**, and **PURE MICHIGEN** is the spelling in both (the seed file's "Pure
Michigan" is wrong either way). `Sleepy Joy` / `Sleepy Joe` was a sixth contested
spelling nobody had previously flagged.

**Still open with the owner:** which of the two controlled documents governs
the four disputed names (JD, GRC, SJ, WC). This is not cosmetic: the name
resolves to a cultivar row whose abbreviation is the head of every batch code
(`GP072501`) and mother ID (`GP26_S1M03-2_nnn`), and potency history is
attributed to a strain by that head. Until he picks, both spellings of each
pair resolve to one cultivar (point 2 at the top), so no strain's tested
history splits.

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

### The HTML copies say the same thing (checked exhaustively)

Each strain folder holds an HTML alongside every PDF (HTML written 09:16, PDF
11:21 the same morning — the PDF is rendered from the HTML). Every HTML for
every **multi-grade** strain was parsed; single-grade strains cannot overlap by
definition and are excluded.

| | |
| --- | --- |
| HTML documents parsed | **28**, across 9 multi-grade strains |
| at exactly ±10.00 % | **28 / 28** |
| adjacent grade pairs | 19 |
| pairs that **overlap** | **15** |
| pairs with a clean gap | 4 |

```
BSS   I/II   21.60–21.99      JD    I/II   19.80–21.99
CJ    I/II   25.20–28.59      JD  III/IV   14.40–15.39
CJ   II/III  23.40–26.39      OPM   I/II   19.80–21.99
CJ  III/IV   21.60–21.99      OPM  II/III  18.00–19.79
GP    I/II   25.20–28.59      PM    I/II   10.80–10.99
GP   II/III  23.40–26.39      SCR   I/II   18.00–19.79
GP   IV/V    16.20–17.59
HPA   I/II   19.80–21.99      HPA  II/III  18.00–19.79
```

The HTML and PDF renderings agree on every value. There is no third reading of
the issued specification, and no document anywhere in the archive prints a
tolerance other than ±10 %.

### Why the windows overlap: it is the ladder spacing, not the tolerance

The owner's hand-drawn study (2026-09-06) plots two candidate THC ladders from
6 % to 30 % with ±10 % bands, colouring each junction **green** where consecutive
grades leave a clean gap and **pink** where they overlap. Both drawn ladders turn
green→pink partway up. The arithmetic behind that:

> Two adjacent nominals `L < H` carrying a **relative** ±p band are disjoint
> **iff** `H/L > (1+p)/(1−p)`.
> At p = 10 % that threshold is **11/9 = 1.2222** — a step of **22.22 % or more**.

The constraint is on the **ratio**, not the absolute step, which is why a fixed
step stops working as the ladder climbs:

| step | works while | fails from |
| --- | --- | --- |
| 2 points | nominal < 9 % | 10 → 12 upward |
| 4 points | nominal < 18 % | 20 → 24 upward |

The drawing's ladders reproduce this exactly, including `18 → 22` (ratio
1.2222…) landing on a **zero-width touch** — neither gap nor overlap.

At ±10 % only about **seven** non-overlapping grades fit between 8 % and 30 %,
and they must be geometric, e.g. `8.00, 9.78, 11.95, 14.61, 17.86, 21.83, 26.68`
— not round numbers. So a catalogue of round nominals spaced 2 apart at the top
of the range **cannot** be non-overlapping at ±10 %. Grape Pie I/II is a ratio of
1.0769 against a required 1.2222.

**The issued catalogue read the same way — 20 junctions:**

| | |
| --- | --- |
| **pink** (overlap) | **16** |
| **green** (dead band — a result here fits NO grade) | **4** |

The four dead bands are already in the issued specification, so "continuous
coverage" was never a property of the current scheme either:

| strain | between | dead band |
| --- | --- | --- |
| Orange Punch Mimosa | IV → III | **10.99 – 16.20** (5.21 wide) |
| Grape Pie | IV → III | 19.79 – 21.60 (1.81) |
| Jelly Donuts | III → II | 17.59 – 18.00 (0.41) |
| Orange Punch Mimosa | V → IV | 8.80 – 9.00 (0.21) |

So the real choice is not "overlap or not". It is: **keep ±10 % and respace the
nominals geometrically**, or **keep the round nominals and let the tolerance
shrink where grades sit close together**. The second is what the derived
proposal does; the first is what the drawing tests.

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

**Answered 2026-09-18:** the fitted, non-overlapping specification is the
controlled state everywhere ("±10 % flat is not gonna work so the fitted
approach is applicable everywhere"); it enters through `import-fitted` (point 1
at the top). The issued v.03 pages remain importable only as reference rows
and only until a strain's fitted version exists.

### The merged master document — the catalogue is exact against it

`ImB_Specifications_Tran01-Tran02_Merged.pdf` (48 pages, 11.5 MB) is the
consolidated specification. Parsed in full:

| | |
| --- | --- |
| pages | 48 → **42 distinct products**, 22 strains, 6 reprints |
| pages where tolerance ≠ 10.00 % of nominal | **0 / 48** |
| pages where window ≠ `[nom − tol, nom × 1.10 − 0.01]` | **0 / 48** |
| adjacent grade pairs | 20 — **16 overlap**, 4 clean |
| `imb_products.json` vs this document | **42 / 42 exact** on code, nominal and window |

So what is loaded in production is a faithful transcription of the master
document. The reprinted pages are `CJ-III`, `FB-I`, `GG-II`, `GP-II`, `GP-IV`,
`OPM-III`.

Worst ambiguity: a Grape Pie or Cap Junky batch assaying **exactly its own
nominal, 26.00 %**, satisfies **three** grades (I, II and III). The mildest is
Permanent Marker I/II, a 0.19-point sliver at 10.80–10.99.

**Jokerz 31 — CONFIRMED.** Page 14: `J31_THC18 : CBD1  16.20 – 19.79 %
QCSP_001_J31-I_v.01`, Grade I, nominal 18.00 ± 1.80. The seed file's
`needs_confirmation` flag can be cleared.

**Document versions — RESOLVED, they are not competing.** `QCSP 001 v.03` is the
*parent* specification document; `QCSP_001_<ABBR>-<TIER>_v.01` is the individual
product page's own code. Both appear on the same page. Neither supersedes the
other.

## Open

- Canonical strain spellings for the four disputed names — **still open**
  (see above); PURE MICHIGEN and CLEMOSA A BUD are settled and applied.
- ~~Whether a CoQ whose Total THC falls outside its product's window should be
  blocked from issuance.~~ **DECIDED 2026-09-06 (owner): no, do not block.**
  A Total Δ9-THC outside the chosen product's window is reported on the CoQ and
  printed on the document; it does not stop approval or issuance. **Built
  2026-09-27, corrected in fix round 2 (INS2-01)** — the first build refused
  approval until an OOS existed and then until it closed, which blocked
  issuance for the life of the investigation; the formal OOS is now a tracked
  follow-up (`regrade_oos_pending`), see "The out-of-grade rule as built".
  To confirm with the owner: which OOS counts as the follow-up (the rule
  above), and that the deviation goes to CU/PR at compile.

  Two separate rules are easy to confuse here, and this decision touches only
  the second:

  | rule | what it judges | blocks issuance? |
  | --- | --- | --- |
  | `overall_conform` | every CoQ line against its **specification** limit | **yes** — `coq_aggregation.py` returns 409 rather than render a certificate asserting conformance for a batch that does not conform. Unchanged; it is a GxP control. |
  | product-window conformance | Total Δ9-THC against the **product's** stored window | **no** (this decision) — flagged, regraded, deviation sent, formal OOS tracked as a follow-up (`regrade_oos_pending`); the regrade OOS itself does not trigger the open-OOS gate |
- The document code and version the owner issued the fitted specification
  under (the 2026-09-18 `Potency_specifications_25.pdf`): the fitted import
  asks for it rather than inventing one.
- The live Potency Spec Service holds the finished specs (INS-14: newer than the
  git copy — e.g. Wedding Cake at nominal 26 exists only there); the export has
  to come from the running service.
- The header document code on the rendered A4 product page
  (`QCSP 001_GP-THC26_v.03`) follows the archive's per-page style; the v.03
  pages' exact header was not visible in the text extraction.
- The A4 product page prints only the people the system recorded (author,
  approver) with the recorded role and date, never the two named signatories
  the ladder template carried; confirm that is the intended signature block
  for the fitted specification.
