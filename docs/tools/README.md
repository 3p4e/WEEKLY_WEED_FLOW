# Standalone tools

Single-file HTML tools. Each one opens directly in a browser — download the
file and double-click it. No build step, no server, no install.

## `potency-range-builder.html`

Builds Total Δ⁹-THC potency grade ranges for a strain against its measured
results. Used to decide the ladders that will eventually populate `qc_products`
(see [`../PRODUCT-CATALOGUE-2026-09.md`](../PRODUCT-CATALOGUE-2026-09.md) and
[`../RANGE-BUILDER-INTEGRATION-2026-09.md`](../RANGE-BUILDER-INTEGRATION-2026-09.md)).

**The data it ships with** is a snapshot, embedded in the file: 106 Total Δ⁹-THC
results across 72 batches and 20 strains, read from `CoQ_Analysis_Master_v10.xlsx`
(sheet "CoQ Parameter Tracker v10", column M), plus the 42 specification nominals
from `QCSP 001 v.03`. It is a **working copy, not a live view** — the app is the
system of record, and this file does not update itself.

**What it does**

- One strain per scale, every measured result plotted as a dot on a 5–33 % axis.
- Toggle any whole-number nominal on or off; each starts at its full ±10 %.
- Drag either end of a band to set its tolerance — both ends move together, and
  the ±10 % ceiling is drawn as a dashed outline you cannot cross.
- Between neighbours: pink where bands overlap, green where they leave a gap,
  with the width in percentage points.
- Drag the diamond between two neighbours to set a border — they snap to meet
  there exactly, and both tolerances recalculate.
- **Analyse & propose** searches the ladder itself, not just the tolerances:
  it groups the results, then finds the nominal set and tolerances that cover
  the most results with the widest usable bands. Toggles control whether it
  picks the nominals, whether it prefers even numbers, whether it avoids gaps,
  the narrowest band it will accept, and how many grades at most.
- Add or remove results on any strain, and create new strains from scratch.

**Conventions it obeys** — the same ones the specification pages print:
a nominal `N` with tolerance `t` covers `N − t` to `N + t − 0.01`
(20.00 ± 2.00 → 18.00–21.99); tolerance never exceeds 10 % of the nominal;
neighbouring grades never overlap once a border is set between them.

**Why gaps are sometimes unavoidable.** Two adjacent nominals `L < H` with
relative ±10 % bands are disjoint only when `H/L > 11/9 ≈ 1.2222` — a step of
at least 22.22 %. A 2-point step stops working above a nominal of 9, a 4-point
step above 18. The tool reports such a gap as forced rather than pretending a
tolerance could close it.

**Where your work is kept.** Choices are saved in the browser that made them.
Published as an artifact with the `db` capability, they are also written into
the artifact's own store so they survive across browsers and can be read back.
Opened as a plain file, only the browser copy applies.
