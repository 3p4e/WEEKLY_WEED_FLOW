# Measured Total Δ⁹-THC per strain — extraction, distribution, and the range-building tool

Companion to `PRODUCT-CATALOGUE-2026-09.md`. That document establishes what the
**specification** says; this one establishes what the **plants actually did**, and
records how the figures were obtained so the extraction is reproducible rather
than a one-off.

The two exist for one decision: the issued catalogue's grade windows overlap (16
of 20 adjacent pairs), so the owner is re-cutting the potency ladders. That work
needs the measured distribution, not the specification.

## Source and extraction

**`CoQ_Analysis_Master_v10.xlsx`** on Drive, sheet **“CoQ Parameter Tracker v10”**,
column **M** (`#4 Assay — Total Δ⁹-THC*`, Ph. Eur. 2.2.29 HPLC). Header rows 1–4;
data from row 5.

Five rules make the extraction correct. Each was found by reading the sheet, and
skipping any one of them changes the answer:

1. **Column A is sparse and must be forward-filled.** A batch names itself on its
   first row only; every additional certificate for that batch is a continuation
   row with A empty. Reading A per-row drops most results.
2. **Strain comes from the head of the CU batch code**, matched longest-first
   against the known abbreviations — `J31` before `J`, `CLE` before `C`,
   `GRC` before `GG`. A naive leading-alpha match mis-assigns Jokerz 31.
3. **`OMP1024_01` is a transposition of `OPM`.** The same transposition appears in
   the batch register, so it is a typo and belongs to Orange Punch Mimosa, not a
   22nd strain.
4. **One certificate is listed twice and must be counted once.** `ППК26065`
   (Jelly Donuts, 13.93 %) appears under `JD112501` as *on file, not credited* and
   again under `JD112501＊` as credited. It is one measurement. De-duplicate on
   (strain, certificate, value).
5. **Two placeholder strings carry no value** and are excluded: `not on this
   certificate` (10 cells) and `— MISSING —` (4 cells).

Results marked *on file, not credited* **are** included. They are real
measurements from real certificates; they were simply not credited to that batch's
CoQ, which is a documentation status, not a doubt about the number.

## What came out

| | |
| --- | --- |
| Results | **106** |
| Batches | **72** |
| Strains | **20** |
| Span | **7.91 – 26.32 %** |

Per strain, ordered by weight of evidence:

| Strain | n | Observed range |
| --- | --: | --- |
| Grape Pie | 24 | 13.16 – 25.98 |
| Cap Junky | 12 | 14.93 – 24.96 |
| Orange Punch Mimosa | 10 | 7.91 – 20.03 |
| Gorilla Glue | 8 | 15.35 – 18.98 |
| Jelly Donuts | 7 | 13.93 – 20.54 |
| Fat Bastard | 6 | 12.39 – 20.83 |
| Jokerz 31 | 6 | 17.32 – 25.27 |
| Scrambler | 6 | 17.13 – 26.32 |
| Blue Sunset Sherbet | 4 | 20.39 – 25.01 |
| High Pro Amnesia | 4 | 17.31 – 22.43 |
| Permanent Marker | 4 | 10.01 – 14.06 |
| Sleepy Joe | 3 | 9.20 – 11.20 |
| Blue Gelato, Cash Cow, Motor Breath, Wedding Crusher | 2 each | — |
| Apple and Banana, Clemosa A Bud, Grapes And Cream, Kush Crasher | 1 each | — |

**Coverage is very uneven, and that constrains what the data can settle.** Grape
Pie and Cap Junky together are a third of every result. Four strains have a single
data point, so their "distribution" is one dot. Three strains that have
specifications — **Amnesia Core Cut, Chem Flyer, Pure Michigen** — have **no
results at all**. One strain, **Apple and Banana**, has a result but no
specification page anywhere in the archive.

## Two things the results say about the specification

**Batches routinely land outside their own grade.** Scrambler's specification tops
out at Grade I (20.00 %, window 18.00–21.99), yet four of its six results sit
between 21.92 and 26.32 — above everything the strain is specified to produce.
Jokerz 31 is specified at one grade only (18.00 %, 16.20–19.79) and has results at
21.84 and 25.27.

**The dead bands are real, not theoretical.** Orange Punch Mimosa's issued ladder
leaves 10.99–16.20 uncovered, and the strain has measured results at 14.16 and
15.38 — inside that hole. Those batches match no grade as the specification stands.

## The tools

Two published artifacts, both fed from the data above.

**THC Results by Strain** — read-only. Every result as a dot on an empty 6–30 %
scale, one scale per strain, no windows or limits drawn. This is the picture used
to judge where the ladders should fall.

**Potency Range Builder** — interactive, and the working surface for the decision.
Every whole number 6–30 is a switch (○ off, ● on) over the same dots; each nominal
that is on shows its band, draggable at either end with the two ends moving
together, capped at ±10 % of nominal and floored at ±0.01. Between neighbours it
draws the overlap (pink) or gap (green) with its width, and a border diamond that
snaps two neighbours to meet at a chosen point, recomputing both tolerances. The
arithmetic follows the specification's own convention: `N ± t` covers `N − t` to
`N + t − 0.01`.

Choices are written to the artifact's own store under `ranges/<abbr>`, so the
decided ladders can be read back directly rather than transcribed.

## Reproducing this

The extraction is a short script over the workbook — forward-fill column A, match
the strain prefix longest-first with the `OMP → OPM` alias, take the leading number
out of column M, de-duplicate on (strain, certificate, value). Nothing about it
depends on the state of the app, and it should be re-run whenever the master
workbook is updated; the counts above are as of **`CoQ_Analysis_Master_v10.xlsx`,
modified 2026-09-06**.

`docs/coq-tracker/parse_master_v9.py` reads the *v9* layout of the same workbook
for the fuller parameter set; this note covers only the Total Δ⁹-THC column of v10.

## Open

- The ladders themselves. The owner is building them in the range tool; nothing is
  loaded into `qc_products` from this analysis.
- Strain spellings remain contested between two controlled documents — see
  `PRODUCT-CATALOGUE-2026-09.md`. Names here follow the merged master.
- Whether a batch assaying outside every grade of its strain should regrade to the
  nearest, and raise an OOS against batch disposition. The owner has described
  this behaviour; it is not built, and it is not buildable while 16 of 20 adjacent
  pairs overlap, because "the next grade" is then ambiguous.
