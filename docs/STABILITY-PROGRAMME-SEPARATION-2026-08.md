# Stability testing programme — separated from batch-release eCoA data (2026-08-17)

## Why

The stability certificates report the *same analytes* as batch release — `Вкупно Δ⁹-THC`,
`CBN`, `Губиток при сушење` — but they are timepoint analyses of stored material under ICH
conditions, not release results. Held in the same dataset they are indistinguishable from
release CoAs at retrieval time, and can be read back as if they were a batch's release values.

## What changed

The 10 stability certificates were moved out of `eCOA_INGEST` into a dedicated RAGflow dataset
**`STABILITY_PROGRAMME`** (`2e15c4ea9a2011f18808996aeceb1f29`) and renamed to state the
programme, batch, timepoint and storage condition on the face of the filename.

| Certificate | Batch | Timepoint | Condition | Document name |
|---|---|---|---|---|
| ППК26032 | P050022 | 6 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050022_m6_25C-60RH_PPK26032.pdf` |
| ППК26033 | P050022 | 6 months | 40 °C / 75 % RH | `STABILITY_GrapePie_P050022_m6_40C-75RH_PPK26033.pdf` |
| ППК26059 | P050022 | 9 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050022_m9_25C-60RH_PPK26059.pdf` |
| ППК26034 | P050072 | 6 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050072_m6_25C-60RH_PPK26034.pdf` |
| ППК26035 | P050072 | 6 months | 40 °C / 75 % RH | `STABILITY_GrapePie_P050072_m6_40C-75RH_PPK26035.pdf` |
| ППК26060 | P050072 | 9 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050072_m9_25C-60RH_PPK26060.pdf` |
| ППК26036 | P050202 | 3 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050202_m3_25C-60RH_PPK26036.pdf` |
| ППК26037 | P050202 | 3 months | 40 °C / 75 % RH | `STABILITY_GrapePie_P050202_m3_40C-75RH_PPK26037.pdf` |
| ППК26057 | P050202 | 6 months | 25 °C / 60 % RH | `STABILITY_GrapePie_P050202_m6_25C-60RH_PPK26057.pdf` |
| ППК26058 | P050202 | 6 months | 40 °C / 75 % RH | `STABILITY_GrapePie_P050202_m6_40C-75RH_PPK26058.pdf` |

### The certificates state the timepoint themselves

Each certificate carries the study point in its sample description, so the designation is taken
from the record rather than inferred:

```
примерокот: Сув цвет од медицински канабис од сорта Grape Pie
            (стабилност месеци 6, 25С/60% RH), серија: Р050022
```

i.e. `(стабилност месец|месеци N, TT°C/RR% RH), серија: PXXXXXX`. All ten were checked against
this line and every timepoint and storage condition matches the assigned filename:

| Certificate | Sample description says | Assigned |
|---|---|---|
| ППК26032 | стабилност месеци 6, 25С/60% RH, серија Р050022 | P050022 m6 25C-60RH |
| ППК26033 | стабилност месец 6, 40C/75% RH, серија P050022 | P050022 m6 40C-75RH |
| ППК26059 | стабилност месец 9, 25C/60% RH, серија PO50022 | P050022 m9 25C-60RH |
| ППК26034 | стабилност месец 6, 25C/60% RH, серија P050072 | P050072 m6 25C-60RH |
| ППК26035 | стабилност месеци 6, 40С/75% RH, серија P050072 | P050072 m6 40C-75RH |
| ППК26060 | стабилност месеци 9, 25С/60% RH, серија P050072 | P050072 m9 25C-60RH |
| ППК26036 | стабилност месец 3, 25C/60% RH, серија P052022 | P050202 m3 25C-60RH |
| ППК26037 | стабилност месец 3, 40C/75% RH, серија P052022 | P050202 m3 40C-75RH |
| ППК26057 | стабилност месец 6, 25С/60% RH, серија PO50202 | P050202 m6 25C-60RH |
| ППК26058 | стабилност месец 6, 40C/75% RH, серија PO52002 | P050202 m6 40C-75RH |

The batch number is the only field that scans unreliably: `PO50022`, `PO50202` read the leading
zero as the letter O, and `P052022` / `PO52002` transpose digits. Only three batches are on
stability — P050022, P050072 and P050202 — and each garbled form resolves to one of them, with
the m3 and m6 pairs agreeing across their two storage arms. The filenames carry the resolved
number; the certificates keep whatever they printed.

All ten are Grape Pie, covering three batches at 3/6/9-month timepoints under long-term
(25 °C/60 % RH) and accelerated (40 °C/75 % RH) conditions. `ППК26036` prints its batch as
`P052022`, an OCR transposition of `P050202`; the filename carries the corrected number.

The dataset description records the constraint explicitly: stability records only, not
batch-release results, not to be used as release or CoA-register values.

## Verification

| | before | after |
|---|---|---|
| `eCOA_INGEST` | 262 docs / 1,262 chunks | **252 docs / 1,232 chunks** |
| `STABILITY_PROGRAMME` | — | **10 docs / 387 chunks** |

Exactly the ten documents and their thirty stale chunks left the release dataset. A prefix
query for `STABILITY*` against `eCOA_INGEST` returns **0** hits. The certificates were
re-parsed in place with `gpt-4.1` vision (0 failures); chunking is far finer than before
(34–52 per document against 3), because they now take the naive+VLM path rather than the
dead Docling pipeline.

## Parity with the old Letta eCoA RAG — closed

The earlier "9 stability certificates missing from RAGflow" finding was wrong. It came from
matching filenames, and RAGflow names these files by their Cyrillic report number
(`ППК26032.pdf`), so a name search could not see them. Searching document *text* found all of
them. RAGflow is in fact a superset: it holds **ППК26037**, the 3-month 40 °C/75 % RH arm,
which the Letta source does not have.

Remaining difference is 15 curated Letta artifacts — 14 `Bundle_*_full_panel` aggregations and
`List_of_COAs` — which are derived convenience documents, not source records. Every underlying
certificate behind them is present in RAGflow.

## Checked and cleared — the register's CBN 0.23 is a release value

An earlier revision of this note raised a suspicion that `ППК26032` (P050022, 6 months,
25 °C/60 % RH), which reports **CBN 0.23 %**, might have leaked into the batch-release register,
because the register records CBN **0.23** for GP0824_02 — the same batch — while the UKIM
release certificate reports CBN as **BLQ**.

**That suspicion is wrong and is withdrawn.** Re-extracting the CBN line from every P050022
document shows the Farmahem release cannabinoid report `197-11-К/26` states:

| | | value | U |
|---|---|---|---|
| Вкупен Cannabinol | Total CBN | **0.23** | 0.01 |
| Вкупно Δ⁹-Tetrahydrocannabinol | Total Δ⁹-THC | **22.61** | 1.39 |

The register's 0.23 is that release figure. The corroboration is the second number: the same
report gives Total Δ⁹-THC 22.61, which is exactly the second THC result the register already
carries for GP0824_02 (`22.61 %w/w (U 1.39) | 197-11-К/26 | Farmahem`). Both values come from
the same release certificate, so no stability result is involved.

The coincidence with `ППК26032` is only that — and the two are not even the same measurand:
the stability certificate reports `Содржина на CBN` (CBN content), the release report
`Вкупен Cannabinol` (Total CBN).

Worth knowing for future comparisons: P050022 has several release documents that legitimately
disagree on CBN, because they are different analyses — UKIM reports `BLQ`, the in-house bulk
CoA `0.02 %`, and Farmahem `0.23`. A cross-check that picks the wrong one of these will report
a false mismatch, which is what happened here.

No change to `PP_Batch_Release_QC_Register_CORRECTED.xlsx` is required; the register is correct
as it stands.
