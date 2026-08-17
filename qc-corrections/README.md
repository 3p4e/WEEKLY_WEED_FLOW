# Batch Release QC Register — corrections + THC-by-strain consolidation (2026-08-17)

`PP_Batch_Release_QC_Register_CORRECTED.xlsx` contains two sheets:

1. **`Batch Release QC`** — the register with four confirmed value corrections applied.
2. **`THC by Strain`** — `PP_THC_by_Strain.xlsx` rebuilt complete and correct, added as a new sheet
   in the same workbook, in the source document's own format.

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
