# Batch Release QC Register — corrections + THC-by-strain consolidation (2026-08-17)

`PP_Batch_Release_QC_Register_CORRECTED.xlsx` contains three sheets:

1. **`Batch Release QC`** — the register with four confirmed value corrections applied.
2. **`THC by Strain`** — `PP_THC_by_Strain.xlsx` rebuilt complete and correct, added as a new sheet
   in the same workbook, in the source document's own format.
3. **`Stability Testing Programme`** — the stability study results, kept as a separate sheet so they
   are never read as release values.

Working copy only; not an approved QMS record. Drive file versioning is the change history.

## Sheet 1 — corrections applied

Verified against source Certificates of Analysis (both eCoA corpora):

| Cell | Batch | Parameter | Was | Now | Evidence |
|---|---|---|---|---|---|
| `G36` | HPA1024_01 | CBD % | 24.70 | **0.10** | CoA P050052 `Вкупно CBD*** = 0.10`; 24.70 is the Δ9-THCA value from the same table |
| `H9` | BG1024 | CBN % | 0.28 | **0.02** | CoA BG1024 (ППК25050) + full-panel bundle both state `CBN 0.02%` |
| `U31` | OPM1024_01 | Hg mg/kg | 0.001 | **0.011** | CoA P050042 `Mercury: <0.1 mg/kg \| 0.011 mg/kg` |
| `H285` | HPA1024 | CBN % | 0.36 | **N.D.** | CoA HPA1024 (bulk) `Cannabinol \| <1.0% \| N.D.` |

Not changed, on evidence:

- **OPM122501 Pb 0.049 / Cd 0.165 — register is correct.** The Farmahem report states
  `олово 0,049` and `кадмиум 0,165`; the Letta `OPM122501_eCoA.txt` summary claiming
  "Pb н.д., Cd н.д." is the inaccurate document.
- **FB012603 / GG012603 potency** — matched CoAs belong to different batches (FB012601,
  GG112501); apparent mismatches were wrong-batch matches.
- **TAMC / TYMC order-of-magnitude flags** — OCR artefacts; the scanned CoAs lost superscripts
  (`5.1×10⁴` → `5.1x10`). The register is right.
- **CBN `<LOQ` vs `0.02%` (~14 batches)** — reporting-convention decision, not a transcription
  error. Left for QC to rule on.

## Sheet 2 — `THC by Strain`, what was corrected

Source: `PP_THC_by_Strain.xlsx` (Drive `1x3gArmDBJnrNL7rvDYlIoXa8MiGuV4v3`).
Rebuilt in the same layout: title, description, dark header row, teal merged strain-group
headers carrying batch count + THC range, zebra data rows, per-batch vertical merges,
identical column widths, frozen header.

- **80 batches / 97 Total Δ⁹-THC results** — every result on file retained, one row per result,
  re-sequenced 1–80. Matches the register's 80 batches exactly (no batch missing).
- **20 strain groups, down from 30.** Eight duplicate groups were spacing/concatenation variants
  of one strain and were merged: `CashCow`→Cash Cow, `FatBastard`→Fat Bastard,
  `GorillaGlue`→Gorilla Glue, `GrapePie`→Grape Pie, `HighProAmnesia`→High Pro Amnesia,
  `JellyDonutz`→Jelly Donutz, `Jokerz31`→Jokerz 31, `OrangePunchMimosa`/`OPM`→Orange Punch Mimosa.
  The same duplication exists in the register's own strain column. `Cap Junkie` and `Cap Junky`
  were additionally merged into **Cup Junky** — see below.
- **Batch counts and THC ranges recomputed** per merged group; BLQ/`<LOQ`/ND excluded from ranges.
- **Stability results included, marked, and excluded from the release range.** The ten stability
  Total Δ⁹-THC values appear as extra rows against their own batches — P050022 = GP0824_02,
  P050072 = GP0824_03, P050202 = GP062501 — shaded, italic, with the timepoint and storage
  condition in the value cell and `STABILITY — not a release value` in the spec column. The group
  header range is computed from release results only and is labelled "(release)". A stability value
  is never entered as a release value.
- **Three OCR-garbled CoA codes resolved** against the certificate text:
  `ППК52211 (likely OCR misread…)`→**ППК25211**, `ППК21554`→**ППК25154**, `ППК52557`→**ППК25257**.
  `НИК22155` (HPA1024_01) carries no ППК number in its certificate text and is left as found.
- **P-number rows confirmed, not errors.** For `P060152`, `P060212`, `P060242`, `P060332`,
  `P060352`, `P060382`, `P060402`, `P160012/22/32` the Drive batch folders name only a strain,
  so the P-number *is* the batch identifier. Verified against the 81 batch subfolders of
  `16oMK…`, which also supplied the P-number↔batch-code mapping.

### Cup Junky — cultivar name resolved by QC

The source certificates disagree among themselves on this cultivar's name: `CAP JUNKY`,
`Cap Junkie`, `CUP JUNKIE`, `Cup Junky` and `Cupjunkie` all appear, in some cases on
certificates for the same batch. QC confirmed the correct name as **Cup Junky**, so the former
`Cap Junkie` (2 batches) and `Cap Junky` (3) groups are merged into it:

`CJ1024`, `CJ052501-1`, `CJ052501-2`, `CJ062501-1`, `CJ062501-2`, `CJ072501`, `CJ082501-1`,
`CJ082501-2`, `CJ092501` — **9 batches, Total Δ⁹-THC 14.93 – 24.96 %**.

## Sources

| Source | Content |
|---|---|
| RAGflow `eCOA_INGEST` | 260 CoA PDFs from Drive `16oMK…`, parsed with `gpt-4.1` vision (scanned Macedonian Cyrillic); 1,262 chunks / 262 docs |
| Letta `ImB_QC_COAs` (72.60.35.12:8283) | 120 files — per-batch full-panel bundles, per-P-number CoAs, Farmahem lab reports, UKIM certs |
| Google Drive folder `16oMK…` | 81 batch subfolders — authoritative P-number ↔ batch-code ↔ strain mapping |

Reference limits: the register's own embedded spec row. The production `qc_spec_parameters` and
`qc_specifications` tables are empty, and the limits in `qms-creator/sops_created/QC_01.04` are
marked "example" and disagree with the register (e.g. Pb ≤2.0 vs ≤0.5), so they were not used.
Streptococcus and Pseudomonas were out of scope by request.

## Sheet 3 — `Stability Testing Programme`

All ten stability analyses on file, grouped by batch and ordered by timepoint, transcribed from the
UKIM certificates held in the RAGflow dataset `STABILITY_PROGRAMME`. Columns: batch, variety,
timepoint, storage condition, report number, issue date, laboratory, then loss on drying, CBDA,
CBD, CBN, Δ⁹-THC, Δ⁹-THCA, Total CBD and Total Δ⁹-THC, with a remark column.

The sheet header states plainly that these are stability-study results, not batch-release results,
and that initial (t=0) values live in the `Batch Release QC` sheet. No release value was copied in.

Three batches are on stability, all Grape Pie — P050022 and P050072 at 6 and 9 months, P050202 at
3 and 6 months — each under long-term 25 °C/60 % RH and, at most points, accelerated 40 °C/75 % RH.

What the data shows, stated as the certificates state it:

- Under **long-term 25 °C/60 % RH** the material is stable. CBN stays at 0.04–0.30 % and Total
  Δ⁹-THC holds between 21.31 % and 25.98 % out to 9 months.
- Under **accelerated 40 °C/75 % RH** it degrades sharply. CBN rises to 2.35 %, 2.15 % and 2.05 %,
  above the ≤ 1.00 % limit printed on those same certificates — flagged in the remark column.
  Total Δ⁹-THC falls correspondingly: 21.31 → 13.16 % (P050022) and 24.62 → 14.99 % (P050072) at
  6 months.
- `ППК26058` (P050202, 6 months, 40 °C/75 % RH) reports Total Δ⁹-THC **1.17 %** against 24.51 % on
  its long-term counterpart. That figure is not a transcription error: the certificate gives
  Δ⁹-THC 0.29 % and Δ⁹-THCA 0.97 %, and 0.29 + 0.97 × 0.877 = 1.17, matching the formula the
  certificate itself prints. It is reported as found; interpreting it is QC's call.

## Confirming the stability values against the certificates

Each stability Total Δ⁹-THC was confirmed rather than taken on trust, by recomputing it from the
same certificate's own components: `Total Δ⁹-THC = Δ⁹-THC + Δ⁹-THCA × 0.877`, the formula each
certificate prints in its own footnote.

Seven of ten agree to within rounding. Three did not, and the reason was OCR damage in the RAGflow
text rather than anything wrong with the certificates:

| Certificate | RAGflow text | Problem |
|---|---|---|
| ППК26059 | Δ⁹-THC `0.01 %` | the CBD value was duplicated into the Δ⁹-THC row; 0.01 + 13.22 × 0.877 = 11.60, not the stated 23.08 |
| ППК26060 | Δ⁹-THC `0.01 %` | same duplication; 0.01 + 12.36 × 0.877 = 10.85, not the stated 25.98 |
| ППК26035 | no values | the result column did not OCR onto the label rows at all |

All three were resolved against the Letta corpus, an independent OCR of the same certificates, and
the arithmetic then closes exactly:

| Certificate | Δ⁹-THC | Δ⁹-THCA | computed | stated |
|---|---|---|---|---|
| ППК26059 | 11.49 | 13.22 | 23.09 | **23.08** |
| ППК26060 | 15.14 | 12.36 | 25.98 | **25.98** |
| ППК26035 | 14.98 | BLQ | 14.98 | **14.99** |

So all ten totals are confirmed — seven by internal arithmetic, three by two independent OCRs plus
arithmetic. The corrected component values are what appear in the `Stability Testing Programme`
sheet; the mis-OCR'd `0.01 %` figures were never carried into the workbook.
