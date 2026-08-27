# eCOA_INGEST_SUMMA — regenerated per-batch summaries (2026-08-17)

The last parity difference against the old Letta eCoA RAG was its 14 curated
`Bundle_*_full_panel` documents plus a `List_of_COAs` index. These are derived aggregations, not
source records, so they were **regenerated from RAGflow's own certificates** rather than copied
across — RAGflow holds the fuller corpus, and regenerating means the summaries exclude the
now-separated stability data by construction.

## What was built

RAGflow dataset **`eCOA_INGEST_SUMMA`** (`e2db97129a2811f19e4939a816aa1a3b`) — **81 documents,
1,704 chunks**, all parsed, 0 failures:

- **80 per-batch bundles**, one for every batch in the register, against Letta's 14. Each
  consolidates that batch's full analytical panel from its source certificates, lists each
  contributing report with laboratory, report number, scope and issue date, preserves the
  Macedonian qualifiers verbatim (`Одговара`, `н.д.`, `BLQ`), and ends with a `SOURCE FILES:` line
  naming every certificate used. 117 distinct certificates are drawn on.
- **`LIST_OF_COAS_index.txt`** — batch, P-number, strain, register CoA code and the source
  certificates held in RAGflow, for all 80 batches.

Kept as a separate dataset deliberately. Loading them into `eCOA_INGEST` would state every value
twice — once in the certificate, once in the summary — which degrades retrieval. The dataset
description records that these are derived convenience records and that the certificates in
`eCOA_INGEST` remain the source of truth.

## Batch-to-certificate matching

Matching batches to their certificates took four iterations, because the identifiers collide:

- `GG1024_01` vs `GG1024_02` — distinct batches, near-identical codes
- `BSS1024` is a substring of `BSS10240_01`, itself a typo for `BSS1024_01`
- ` 2` / ` 3` file-version suffixes look like part of a batch code
- the certificate writes `GRC102501/2` where the register writes `GRC102501-2`

Final precedence: P-number is authoritative → exact batch code with identifier boundaries → CoA
number → content match for shared series reports, rejecting any certificate whose name or text
names a *different* batch. **80/80 batches matched.** Earlier, looser rules pulled one batch's
certificate into another's bundle, which for a summary document is worse than a gap.

## Fidelity audit

Every decimal number and every `N × 10ⁿ` value in the 80 bundles was checked against the text of
the certificates that bundle cites:

| Check | Result |
|---|---|
| decimal values | 768 of 770 present in source; the 2 exceptions are spec limits written `50.000` / `500.000` |
| exponent values (`N × 10ⁿ`) | 17 of 17 present in source |

So the bundles do not invent values. They are, however, only as good as the OCR beneath them.

## The limit worth knowing: superscripts

`BUNDLE_BlueGelato_BG1024` records TYMC **1 × 10⁴ CFU/g**. That is exactly what RAGflow's text of
`BG1024 2.pdf` says in its result column:

```
Резултат
1,6 x 10⁴ CFU/g     <- TAMC
1 x 10⁴ CFU/g       <- TYMC
```

But the register records TYMC **1 × 10³** for that batch, and Letta's independent OCR of the same
certificate also reads **1 × 10³**. Two sources against one, and 1 × 10⁴ would sit exactly on the
≤ 10⁴ limit, so the likely truth is 1 × 10³ and RAGflow misread the superscript.

This is the same superscript weakness seen throughout these scans, and it is why the earlier
register cross-check treated order-of-magnitude micro differences as OCR artefacts rather than
register errors. Nothing was changed in the register on the strength of a single OCR.

**Use the bundles as summaries and as a route to the right certificate. For a numeric value that
matters, the certificate governs** — and where an exponent is involved, confirm against a second
source or the paper original.
