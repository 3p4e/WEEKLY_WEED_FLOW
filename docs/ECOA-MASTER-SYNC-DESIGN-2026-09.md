# Syncing the app's QC database with `CoQ_Analysis_Master_v9.xlsx` — design (2026-09-04)

The owner's master file lives at
`1. PP/DATA_B/QC_eCoA/CoQ_Analysis_Master_v9.xlsx` on Google Drive (file id
`1o7ipvDg5Pp38fwRS_aiK7Xb86Uc9Yd1s`; the Windows path `D:\GOOGLE\AZU_DRIVE\…` is the
Drive client's local mirror of the same file). The request is to keep the app's QC
database in step with it.

## 1. What each side holds today

**The master file (v9, 501,542 bytes, sha256 `c9510fce…`)** — read with
`docs/coq-tracker/parse_master_v9.py` on 04.09.2026:

| sheet | content |
| --- | --- |
| Batch Coverage | 81 batches: CU batch, P batch, strain, 12 coverage flags |
| CoQ Parameter Tracker v9 | 78 batch blocks, 1,337 credited results citing 250 certificates (CNP 73, IJZ-MB 56, IJZ 54, FHM-K 41, FHM-M 22, DFL 2, NGP 1, PP 1); 141 results marked stability (ᴿ), 57 marked derived (ᴰ); 47 "on file, not credited" cells |
| Mikro CoQ Parameter | 30 blocks, physical + microbiology only — to be confirmed as a subset |
| Parameters | the 21 determinations with method, global criterion, source, tracker column |
| Credit Audit / Credit Corrections / Work Order | 12 / 133 / 9 rows of the desk's review state |

Every citation parses (`code, (dd.mm.yyyy) [LAB]`), so the file is machine-readable
as it is, without changing the owner's layout.

**The app (tasks DB, org `purely-plant`)** — the QC model is complete and *empty*:
`qc_certificates`, `qc_coa_documents`, `qc_coa_extractions`, `qc_results`, `qc_coq`,
`qc_coq_lines`, `qc_specifications`, `qc_spec_parameters`, `qc_laboratories`,
`qc_samples`, `plant_batches`, `batch_commercial_identities` all hold 0 rows. Only
`qc_potency_specs` (71 cultivar ladders, DRAFT) and `cultivars` (71) are populated.

The app already has the pipeline the sync needs, end to end
(`backend/app/api/qc/ecoa.py`): register an external certificate as a
`qc_coa_documents` row → transcribe its results as `qc_coa_extractions` (auto-mapped
to `qc_spec_parameters`, graded server-side) → QCT 018 checklist → *promote* to a
DRAFT `qc_certificates` + `qc_results` → CoQ compile. What it lacks is any way to
load that from a file: there is no spreadsheet import anywhere under `/qc`, and no
Google Drive client in the backend.

## 2. Gaps between the file and the model (must be closed for a lossless sync)

1. **The laboratory's own certificate number has no column.** `qc_coa_documents.doc_number`
   is minted by the app (`PP-ECOA-YYYY-NNNN`); `ППК25050` / `752-2025` / `197-1-K-26`
   can only be parked in `notes`. → migration: `qc_coa_documents.lab_doc_number text`
   plus a unique `source_ref` for idempotent upserts.
2. **One batch string.** `batch_id` is free text and does not distinguish CU (`BG1024`)
   from P (`P050192`). → convention: `batch_id` = CU batch as the owner names it;
   the P batch recorded as a `qc_batch_genealogy` edge (`relation='PROCESSING'`) and
   in `notes`. The owner's `PP_CU_P_Batch_CrossReference.xlsx` is the authority
   (90 register rows; 8 open items, notably the sub-lot separator `/01` vs `_01`).
3. **Qualitative criteria and results.** `"Absence / 25 g"`, `"Conforms to Ph. Eur.
   3028"`, `"≤ LOQ"`, `"1,6 x 10⁴ CFU/g"`, `"Одговара"` have no numeric home;
   `_evaluate` grades them `unknown`. → the sync writes the printed value to
   `raw_value`, parses counts and numbers into `numeric_value`, and carries the
   laboratory's own verdict in `lab_verdict`; the textual criterion goes to
   `qc_spec_parameters.pharmacopoeia_ref`/`notes` and the numeric part to
   `lower_limit`/`upper_limit`.
4. **Parameter/determination is one level.** The 21 determinations become 21
   `qc_spec_parameters` rows under one specification ("CoQ global criteria",
   material `DRY-FLOWER`), named exactly as the Parameters sheet names them.
5. **Kind (release / stability / in-house).** No column. → `qc_coa_documents.kind`
   (`RELEASE`, `STABILITY`, `INHOUSE`); stability documents are imported for the
   record and never offered for promotion.

## 3. Direction and landing zone

**One way, Drive → app, landing in the ingestion layer, never in issued records.**

- The master file is the owner's record of what the laboratories printed; the app's
  `qc_certificates` / `qc_results` are *issued* records with signatures, review
  states and a supersession chain. The sync therefore writes only
  `qc_laboratories`, the specification and its 21 parameters, `qc_coa_documents`
  (one per cited certificate, status `EXTRACTED`, kind set), `qc_coa_extractions`
  (one per credited result), and `qc_batch_genealogy` edges. Checklist decisions,
  promotion and CoQ compilation stay human actions in the app, exactly as the
  SOPs require.
- Cells the owner marks "on file, not credited" (•) create the document but no
  extraction. "held for review" and "not ingested" cells create nothing and are
  listed in the sync report.
- A document the app has already reviewed or promoted is never overwritten: a
  changed value in the file is reported as a conflict for a person to resolve.

## 4. Mechanics

- **Fetch.** `rclone copyto "wwf-gdrive:1. PP/DATA_B/QC_eCoA/CoQ_Analysis_Master_v9.xlsx"`
  works today from the `wwf-backup-offsite` container — proven 04.09.2026 — but
  that remote is the backup credential with full-Drive scope, and it uses rclone's
  shared client id, which Google retires during 2026. The sync gets its own remote:
  the owner's own OAuth client id, scope `drive.readonly`, stored only in the
  scheduler container's environment.
- **Where it runs.** `backend/scripts/ecoa_master_sync.py` in the scheduler
  container (weekly, after the Thursday snapshot) and on demand through
  `POST /qc/master-sync` (HoQC roles), both with `dry_run` returning the diff.
- **Idempotency.** `source_ref = "master:{lab}|{code}|{date}|{cu}"` on documents;
  extractions are replaced per document only while the document is `UPLOADED` /
  `EXTRACTED`.
- **Audit.** A `qc_master_sync_runs` row per run: file sha256 and modified time,
  counts (created / updated / unchanged / conflicts / skipped), the run's report,
  who triggered it. The existing hash-chained audit triggers cover every row the
  sync writes.
- **Dependencies.** `openpyxl` in the backend image (already the reader used by
  `parse_master_v9.py`), one migration (`lab_doc_number`, `source_ref`, `kind`,
  `qc_master_sync_runs`).
- **UI.** A "Sync from master" action and a last-sync banner (file version, counts,
  conflicts) on the eCoA screen; the sync report downloadable.

## 5. What is ready, what is decided, what is not

Ready: the v9 reader (`docs/coq-tracker/parse_master_v9.py`, validated on the real
file), the batch cross-reference, the laboratory list, the 21 parameters with
criteria, and the eCoA-side reader for the certificate corpus.

Decisions the owner has to make before the first write to production:

1. **Landing zone** — the ingestion layer as above (recommended), or straight into
   issued certificates and results (not recommended: it bypasses the checklist,
   promotion and signature controls the SOPs mandate).
2. **Credential** — a dedicated read-only Drive remote with the owner's own client
   id (recommended), or reuse of the backup token (works today, wrong scope).
3. **Batch key convention** — CU batch as `batch_id`, and one sub-lot separator
   (`/01` as the manufacturing register writes it, or `_01` as the certificates
   do).
4. **Stability results** — import as `STABILITY` documents for the record
   (recommended) or leave out.

Effort once decided: one migration, the sync module and its tests, the scheduler
job, the endpoint and the UI action — roughly two working days, one deploy
(backend + frontend), no downtime.
