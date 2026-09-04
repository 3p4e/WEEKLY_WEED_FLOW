# CoQ Parameter Tracker — built from RAGflow eCoA_DB

`CoQ_Parameter_Tracker_eCoA_DB.xlsx` mirrors the owner's *CoQ Analysis Master v9*
sheets — **Batch Coverage**, **CoQ Parameter Tracker v9**, **Parameters** — and adds a
flat **Results Register**, an **eCOA Document Index**, a formula-driven **Summary
Dashboard** and a **Data Quality** sheet. Every value comes from the certificate text
held in the RAGflow dataset `eCOA_DB` (the corpus granted to `gf_app_assistant` on
letta-6ou3): 253 documents, 308 chunks, read once by machine.

Nothing is invented. A value the corpus does not hold is `—`; a page read that
contradicts the certificate's own arithmetic is `held for review`; every difference
against the owner's tracker is listed, never silently adopted.

`parse_master_v9.py` reads the owner's own *CoQ_Analysis_Master_v9.xlsx* (the real layout, via
openpyxl) into the same canonical shape — batches, certificates, results — for the
app sync described in `docs/ECOA-MASTER-SYNC-DESIGN-2026-09.md`.

## Regenerate after the next ingestion

```
# 1. dump the dataset's chunks (run where RAGFLOW_BASE_URL / RAGFLOW_API_KEY are set,
#    e.g. docker exec -i wwf-docengine python -)  -> ecoa_db_chunks.json
# 2. parse, consolidate, build
python3 parse_ecoa.py          # -> extracted.json   (per document determinations)
python3 consolidate.py         # -> consolidated.json (batches, coverage, register)
python3 build_workbook.py      # -> CoQ_Parameter_Tracker_eCoA_DB.xlsx
```

`consolidate.py` and `build_workbook.py` also read `ref_coverage.json` /
`ref_oracle.json`, the owner's v9 Batch Coverage and per-certificate values, for the
cross-check sections of Data Quality; regenerate them from the owner's file or leave
them as they are (they only feed the comparison, never a result cell).

## Rules the workbook applies

- **Batch names** as printed on the certificate; documents filed by P batch are
  assigned to the CU batch named inside them, else keyed by the P batch.
- **Kinds**: eCoA (accredited laboratory), Stability (eCoA dated ≥ 270 days after
  the batch's first certificate, marked ᴿ), In-house (PP / NGP, marked ᴵ).
- **Coverage** counts only release eCoA certificates as ✓; ✓ᴿ and ✓ᴵ are shown
  but are not release coverage.
- **OOS** only when a result provably exceeds the global criterion; microbial
  counts use the Ph. Eur. 5.1.4 maximum acceptable count (2 × the stated limit);
  Total Δ⁹-THC is per target grade and never flagged.
- Formulas (counts, status, dashboard) recalculate on open; LibreOffice could not
  run in the build sandbox, so cached values are not embedded.
