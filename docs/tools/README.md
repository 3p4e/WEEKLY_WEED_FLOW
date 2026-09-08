# Standalone tools

Single-file HTML tools. Each one opens directly in a browser — download the
file and double-click it. No build step, no server, no install, and no network:
open one on a machine that has never been online and it behaves identically.

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

**Appearance.** Light / Auto / Dark, and five colour schemes — Paper, Graphite,
Bloom, Sepia, High contrast — each with its own light and dark palette. Auto
means no choice is recorded, so the page follows the device whenever the device
changes its mind. Two colours never move: **an overlap is pink and a gap is
green in every scheme and both modes.** Those two carry the meaning of the
picture, so a scheme may change their temperature but never their hue —
otherwise two people on different schemes would read the same chart differently.
That constraint is also why no scheme's bands are pink or green.

**Conventions it obeys** — the same ones the specification pages print:
a nominal `N` with tolerance `t` covers `N − t` to `N + t − 0.01`
(20.00 ± 2.00 → 18.00–21.99); tolerance never exceeds 10 % of the nominal;
neighbouring grades never overlap once a border is set between them.

**Why gaps are sometimes unavoidable.** Two adjacent nominals `L < H` with
relative ±10 % bands are disjoint only when `H/L > 11/9 ≈ 1.2222` — a step of
at least 22.22 %. A 2-point step stops working above a nominal of 9, a 4-point
step above 18. The tool reports such a gap as forced rather than pretending a
tolerance could close it.

### Where your work is kept

Everything you change is written to the browser you changed it in. Nothing is
sent anywhere — the file has no network code at all.

That is enough for one person on one machine, and not enough for anything else,
so the bar at the top offers three ways out:

| | |
| --- | --- |
| **Save a copy with my work in it** | writes a fresh copy of the whole page with your ladders, tolerances and typed results already inside it. Send that file to someone and they open it and see what you saw — no import step, nothing to install. |
| **Save work…** | just your changes, as a small `.json`. |
| **Load work…** | reads such a `.json` back, on any machine. |

A saved copy fills in only the entries the opening browser does not already
hold, so opening a colleague's copy never silently overwrites work in progress;
use **Load work…** when you do want theirs to win.

Some browsers refuse `localStorage` to a page opened from a `file://` path, and
a private window can quietly hand back an empty one. The page detects that and
says so in the bar rather than letting you find out later — in that state the
work lasts until the tab closes, and **Save a copy** is the way to keep it.

### The published version

The same tool is published as an artifact, which is the copy to send to someone
who should not have to download a file first. Two differences, both forced by
the sandbox a published page runs in:

- it cannot hand you a file, so it has no save/load bar — work stays in the
  browser that made it;
- it can ask Claude to explain a proposal, which this file cannot, there being
  no Claude on the other end of a local file.
