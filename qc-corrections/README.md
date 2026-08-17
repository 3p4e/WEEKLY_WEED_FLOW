# Batch Release QC Register — eCoA cross-check corrections (2026-08-17)

`PP_Batch_Release_QC_Register_CORRECTED.xlsx` is a corrected copy of the Purely Plant
**Batch Release QC Register** (Drive: `1-cO46XTqrmcZsxhl1vDLSGzqKSNxAJ3G`), produced from a
full cross-check of **80 batches × 17 parameters** against source Certificates of Analysis.

The original Drive file was **not** modified — the OAuth connector holds `drive.readonly`,
and in-place overwriting of a GMP batch-release record would destroy the audit trail.

## Sources used

| Source | Content |
|---|---|
| RAGflow dataset `eCOA_INGEST` | 260 CoA PDFs from Drive folder `16oMK…`, parsed with `gpt-4.1` vision (scanned Macedonian Cyrillic), 1,262 chunks / 262 docs |
| Letta source `ImB_QC_COAs` (72.60.35.12) | 120 files — per-batch full-panel bundles, per-P-number PurelyPlant CoAs, Farmahem lab reports, UKIM certs |

Reference specification: the register's own embedded spec row (row 5) — stricter EU/Ph. Eur.
limits. Note the production `qc_spec_parameters` / `qc_specifications` tables are **empty**, and
the limits in `qms-creator/sops_created/QC_01.04` are marked "example" and disagree with the
register (e.g. Pb ≤2.0 vs ≤0.5), so they were not used as the reference.

Streptococcus and Pseudomonas were excluded from scope by request.

## Corrections applied (4)

Each corrected cell is highlighted amber and carries a cell note with its original value and
evidence. A `Correction Log` sheet records the same, with status `Pending QC approval`.

| Cell | Batch | Parameter | Original | Corrected | Basis |
|---|---|---|---|---|---|
| `G36` | HPA1024_01 | CBD % | 24.70 | **0.10** | CoA P050052 `Вкупно CBD*** = 0.10`; the 24.70 is the Δ9-THCA value from the same table (wrong-column entry). Confirmed in both sources. |
| `H9` | BG1024 | CBN % | 0.28 | **0.02** | CoA BG1024 (ППК25050) and full-panel bundle both state `CBN 0.02%`. |
| `U31` | OPM1024_01 | Hg mg/kg | 0.001 | **0.011** | CoA P050042 `Mercury: <0.1 mg/kg | 0.011 mg/kg` — decimal-place error. |
| `H285` | HPA1024 | CBN % | 0.36 | **N.D.** | CoA HPA1024 (bulk) `Cannabinol | <1.0% | N.D.` |

## Findings deliberately NOT applied

- **OPM122501 Pb 0.049 / Cd 0.165 — the register is correct.** The Farmahem report states
  `олово 0,049` and `кадмиум 0,165`. The Letta `OPM122501_eCoA.txt` summary claiming
  "Pb н.д., Cd н.д." is the inaccurate document.
- **FB012603 / GG012603 potency** — the matched CoAs belong to *different* batches
  (FB012601, GG112501); the apparent mismatches are wrong-batch matches, not register errors.
- **TAMC / TYMC "order-of-magnitude" flags** — mostly OCR artifacts: the scanned CoAs lost
  superscripts (`5.1×10⁴` → `5.1x10`). The typed register is right in these cases.
- **CBN `<LOQ` vs `0.02%` (~14 batches)** — the CoAs quantify CBN at ~0.01–0.02% while the
  register records `<LOQ` or blank. This is a reporting-convention decision for QC, not a
  transcription error, so it was left untouched.

## Reproducing

Working artefacts live under `/tmp` in the `ragflow-ragflow-cpu-1` container:
`docA.json` (extracted register), `coas.json` (Letta CoA texts), `ragcoas.json` (RAGflow CoA
texts), `factcheck2.json` (Letta run), `factcheck_rag.json` (RAGflow run).
