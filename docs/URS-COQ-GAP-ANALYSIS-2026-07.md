# URS comparison — PP_eCoA_CoQ_System_Architecture_URS_v0.1 vs the platform (2026-07-20)

Source: `PP_eCoA_CoQ_System_Architecture_URS_v0.1.html` (Drive id
`1NeUzbrGZ1cieZvzBzvunPYDnn1L9ro7m`), authored by the Head of QC,
07 June 2026 — a GAMP-5-framed design/URS for the eCoA→CoQ system,
governed by QCSOP 012 v3 / QCSOP 010, and explicitly built around the
draft **EU GMP Annex 22 (AI)** boundary: only static deterministic code on
the release-critical path; generative AI/LLMs excluded from critical
applications; AI allowed solely as an assistive proposer with a 100%
human-verification gate.

The platform's Phase-3 certificate pipeline (QC LIMS + eCoA intake +
COQ generation on the DocEngine, live on both stacks) was built in
July from the assimilated repos — the URS is the *formal requirements
view* of the same system. Verdict: **the architectures agree on the
load-bearing principle** (deterministic core, AI at the edge), the
platform already implements most of URS Phases 0–1 intent, and the URS
supplies a corrected, SOP-grounded backlog that supersedes parts of the
previous parity backlog.

## 1. Where the platform already satisfies the URS

| URS requirement | Platform status |
|---|---|
| Deterministic conformance (never AI; never the lab's verdict) | ✅ `qc.py` grades `complies` server-side against the PP spec parameter limits; the eCoA grading path recomputes, never copies |
| All-or-nothing batch conformance | ✅ COQ comply gate (any non-complying/unmeasured result → 409) |
| Completeness gate (no CoQ with missing parameters) | ✅ built round-3: "batch is not fully tested" 409 when any spec parameter lacks a cited result |
| Sequential per-year numbering, transactional, no reuse | ✅ Postgres sequences allocate PP-ECOA/PP-COA-YYYY-NNNN (gap **reporting** not yet built) |
| Compiler ≠ approver / reviewer ≠ analyst segregation | ✅ enforced in-app (second-person checks) |
| Immutability after approval | ✅ round-3: PROMOTED/REJECTED docs + extractions locked; promote race-safe |
| Human review of extractions; unknown values stay null | ✅ review/placeholder queue; GxP never-fabricate rule is platform law |
| Letta strictly non-critical (assistant/search; never writes records) | ✅ and stronger: dedicated app-only Letta instance (docs/LETTA-DEDICATED-PLAN.md), read-only role in the record path |
| RAG demoted off the critical path | ✅ /qc/coa-qa is grounded FTS citation (non-generative — stricter than the URS asks) |
| Audit trail (Annex 11 §9) | ✅ and stronger: hash-chained append-only audit_log |
| Bilingual EN/MK; multilingual corpus | ✅ app-wide |
| Spec versioning + one-ACTIVE + grade-dependent THC criteria | ✅ qc_specifications version/status + thc_grade + acceptance range |
| CoQ disposition must not assert release | ✅ our COQ text: "This batch CONFORMS against the approved specification" — no "approved/certified for release" (F1 avoided by construction) |
| OOS as first-class investigation records | ✅ two-phase OOS + append-only register (QC-U4) |

Note on AI exposure: today the platform is **more conservative than the
URS target** — eCoA extraction is human transcription (no OCR/LLM on the
value path at all); AI only drafts documents, translates, plans, and
searches. The planned OCR/extraction feature must be built exactly as
the URS specifies (proposer → 100% human verify → commit).

## 2. Genuine gaps the URS adds or sharpens (new canonical backlog)

Priority order; SOP citations are the binding source.

1. **OOS gate on CoQ generation** (QCSOP 012 §6.4.1/§6.6; URS 9.1) —
   `generate_coq` does not check for an open OOS on the batch. Highest
   value, smallest change: 409 with an explicit reason when an open OOS
   references the batch.
2. **Supersession chain for certificates/CoQs** (§6.7) — Revised/
   Superseded statuses, new number + "Supersedes [n] — reason", original
   never deleted. We lock but do not supersede.
3. **Derived-value computation** — total THC = Δ9-THC + 0.877×THCA (Ph.
   Eur. 3028), total CBD analogously, computed by the engine from acid/
   neutral components, never transcribed.
4. ~~**Laboratory entity** (Chapter 7)~~ ✅ **DONE (increment 3, mig 0030,
   v64/v95)** — `qc_laboratories` master (accreditation body/number, ISO
   17025 scope with out-of-scope result flagging, quality-agreement ref,
   per-lab decimal separator + locale); `laboratory_id` on certificates +
   eCoA docs; the free-text `source_institution`/`source_lab` kept alongside
   (immutable-record safety), with the structured lab preferred on the COQ.
5. ~~**Batch genealogy chain**~~ ✅ **DONE (increment 10, mig 0036, v71/v101)** —
   `qc_batch_genealogy` holds directed parent→child edges between batch codes
   (variety → cultivation AB… → processing P… → packaging); **decision D2
   resolved: blending SUPPORTED as an m:n graph** (a batch may have several
   parents). `POST/DELETE /qc/genealogy` (cycle-guarded), `GET /qc/genealogy/
   {batch}` (recursive ancestors/descendants), and `GET …/inherited-results`
   surface the RELEASED-certificate results of a batch's ancestor lots for a
   finished-product CoQ to inherit (QCSOP 012 D3) — advisory, never auto-copied.
   `qcgenealogy-view.js` renders the lineage graph + inheritance.
6. ~~**Register completeness (QCLB 020, §6.13)**~~ ✅ **DONE (increment 4,
   mig 0031, v65/v96)** — retention start/expiry + archive_ref on the
   certificate; `GET /qc/register` serves the §6.13 canned queries (year/
   quarter/type/lab; pending; OOS-linked; end-of-retention) with OOS +
   supersession cross-refs per row; `GET /qc/register/gaps` is the
   numbering-gap data-integrity report (honest about the shared-sequence
   caveat — a gap flags an investigation, never asserts a lost record).
7. ~~**5-working-day eCoA review clock** (§6.3.1)~~ ✅ **DONE (increment 5,
   mig 0032, v66/v97)** — `qc_coa_documents.review_deadline` stamped 5
   working days ahead at registration; `reviewed_at` + `review_window_met`
   stamped on the REVIEWED transition; computed `review_overdue` flag +
   view badges. Same deadline-window control as the 24h RQS window.
8. ~~**Lab's stated verdict captured as reference** (`acceptance_as
   _reported`) and reconciled~~ ✅ **DONE (increment 1 mig 0028 + increment 7
   mig 0033, v68/v98)** — the lab's own pass/fail is captured verbatim on the
   eCoA extraction (`qc_coa_extractions.lab_verdict`) and reconciled there
   (`lab_verdict_mismatch`); increment 7 carries it onto the promoted result
   (`qc_results.lab_verdict`) and settable on a manual iCoA result, so the
   reconciliation lives on the permanent certificate — reference-only, it never
   feeds the in-house `complies` determination (QCSOP 012 §6.3.2).
9. **Code-pattern alignment** — SOP patterns are `eCoA-PP-YYYY-NNNN` /
   `CoQ-PP-YYYY-NNNN` / `QCCoA-…`; ours are `PP-ECOA-…`/`PP-COA-…`.
   ✅ **RESOLVED (decision, no code change)** — the app's `PP-ECOA-`/`PP-COA-`
   format is CANONICAL and the SOP is to be amended to match it. Rationale:
   certificate numbers are immutable GxP records already issued in this format
   on both stacks (incl. live production); renumbering an issued record is
   forbidden (ALCOA+ "Original"). No migration; the SOP text is the artefact to
   update, owner-side.
10. ~~**Mandatory-field manifest for the CoQ render** (WHO TRS 1010 +
    Annex 16 + §9.3)~~ ✅ **DONE (increment 6, backend v67, no migration)** —
    `_coq_manifest()` gates `generate_coq` with a deterministic
    content-completeness check (layered on the existing data/completeness/
    pp_verify gates): material name, specification reference, batch number,
    report date, recorded PASS disposition, authorised approver, testing
    laboratory (eCoA-sourced only), and an analytical-method reference per
    reported test (computed Ph. Eur. 3028 totals excused — they cite their
    monograph). A gap → 409 naming each absent element; nothing is invented.
11. **iCoA as a distinct record type** — internal CoA with analyst +
    Head-of-QC signature capture, merged with eCoA results in the
    parameter master (the URS: "first-class, not an afterthought").
    Partly DONE: the record type already exists (`cert_type` ICOA/ECOA,
    results unified in `qc_results`), and the **signature-capture** half is
    delivered by the Annex 11 e-signature increment (§3 below, increment 8).
    Remaining: a dedicated iCoA authoring surface if the owner wants one
    beyond the shared certificate flow.
12. ~~**PDF originals custody**~~ ✅ **DONE (increment 9, mig 0035, v70/v100)**
    — `qc_document_files` stores the source document as bytea with a
    server-computed SHA-256; `POST /qc/coa-documents/{id}/originals` (20 MB cap)
    + `GET /qc/document-files/{id}/download` re-hashes on read and reports an
    `X-Integrity` verdict; the eCoA intake carries an upload/download custody
    panel. Insert-only; the custody act + digest are recorded in the hash-chained
    audit_log via emit() (the blob itself is kept out of the chain). Page/bbox
    traceability per extracted value attaches here when OCR lands.

## 3. Conflicts / decisions the URS resolves or reopens

- **E-signatures: REOPENED → required.** ✅ **DONE (increment 8, mig 0034,
  v69/v99)** — Annex 11-compliant e-signatures for QC approvals: `POST
  /qc/certificates/{id}/sign` records a re-authenticated (§14 "executed by the
  signer") attestation carrying name, meaning, date/time, permanently linked to
  the certificate, in an append-only `qc_signatures` log; surfaced on the cert
  detail with a signing panel. The QP qualified e-signature (eIDAS) stays
  OUTSIDE the app, in the separate release act (unchanged).
- **Per-sample potency grading: SETTLED as spec-level.** The URS's
  grade_tier model puts Grade I–V THC criteria on the specification,
  not per-sample — matching what we built and closing the qc-lims-ao
  prototype question in our favour.
- **QP role on the CoQ: adjust.** URS/QCSOP 012: CoQ is compiled by a
  senior analyst, approved by Head of QC, and carries **no QP
  signature** (the QP *receives* it). Our `_COQ_ROLES` lets the QP
  issue the COQ. Keep QC_MGR; drop QP from the issuing gate (QP keeps
  read + the separate release act).
- **Air-gapped AI: divergence to decide.** URS mandates local models
  (vLLM/Qwen, no egress). We use cloud LLM providers via the dedicated
  Letta — acceptable while AI touches no release data (current state),
  but the OCR/extraction phase per the URS should run on local models
  (Docling/Surya + local VLM) or the URS's air-gap requirement must be
  consciously amended. Also implicates GPU sizing (owner decision D5).
- **Client shape.** URS proposes a Tauri/PySide desktop client; the
  platform is a web PWA. The verification UX the URS actually needs
  (source-region beside value) is buildable in the PWA; treat the
  desktop client as NOT adopted unless the owner says otherwise.
- **Renderer.** URS: Jinja2+WeasyPrint → PDF/A from the house HTML CoQ
  template. Platform: DocEngine bilingual .docx (pp-document-suite
  canon) + PDF via Gotenberg. Functionally equivalent output with a
  stronger style gate; the manifest check (gap #10) closes the real
  requirement. Ask for `CoQ_Template_v02_VariationF.html` (URS D1) to
  align the rendered layout with the issued certificates.

## 4. URS decisions D1–D6 — current answers

- **D1** (CoQ template HTML): request the file; until then DocEngine
  house style stands.
- **D2** (blending m:n?): ✅ **RESOLVED — YES, m:n** (increment 10). The
  genealogy graph supports multiple parents per batch; a 1:n tree is the special
  case. A blended packaging lot links to every processing lot it draws from.
- **D3** (CoQ at IMB *and* FP, FP inherits IMB): ✅ built —
  `GET /qc/genealogy/{batch}/inherited-results` surfaces the RELEASED-cert
  results of a batch's ancestor lots for the finished-product CoQ to inherit
  (advisory; a human decides what a blend carries forward).
- **D4** (client): PWA already exists; desktop client not planned.
- **D5** (GPU): needed only when local OCR/VLM lands; owner decision.
- **D6** (design vs prototype): superseded by reality — the deterministic
  core is live software; the URS becomes the validation basis (its
  Sections 4–10 map cleanly onto what exists + the gap list above).

## 5. Regulatory note

Draft Annex 22 / revised Annex 11 adoption was expected ~mid-2026 —
i.e., around now. The platform's AI-boundary story (deterministic
record path, assistive AI, dedicated instance, role-gated functions)
is aligned, but should be written up as a formal **intended-use
statement + AI inventory** per the URS's §10.4 when the owner starts
the validation file (URS Phase 0 artefacts: approved URS, FMEA,
validation plan).
