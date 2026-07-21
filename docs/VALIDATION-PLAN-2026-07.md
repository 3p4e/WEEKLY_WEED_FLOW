# Validation file (Phase 0) — eCoA → CoQ QC LIMS on GrowFlow/WWF (2026-07-21)

Prepared per **PP_eCoA_CoQ_System_Architecture_URS_v0.1** §10.4 (intended-use
statement + AI inventory) and the URS Phase-0 artefact list (approved URS, FMEA,
validation plan). GAMP-5 framed; governed by **QCSOP 012 v3 / QCSOP 010**;
built around the draft **EU GMP Annex 22 (AI)** boundary and **Annex 11**
(computerised systems).

> **Status of this document.** This is the *validation basis*, authored from the
> as-built system — every control below points to a migration, an endpoint, and
> an automated test that exists on branch `claude/weekly-read-flow-setup-yft7if`
> and is deployed to both stacks. It is **not** an executed/approved validation
> report: IQ/OQ/PQ execution signatures, the approved URS, and the QA sign-off
> are owner-side steps. Nothing here is aspirational — where a capability is not
> built, it is listed under §12 Open items, not claimed.

---

## 1. Intended-use statement

The system is the **quality-control records layer** of the GrowFlow/WWF platform
for a cannabis-for-medicine facility: it captures material **specifications**,
**samples** and their custody, ingests supplier **electronic Certificates of
Analysis (eCoA)**, grades results **deterministically** against the approved
specification, records **Out-of-Specification (OOS)** investigations, and issues
the house **Certificate of Quality (CoQ)** via the DocEngine.

**Intended use (in scope, GMP records zone):**
- Determine conformance of a batch against its approved specification — always by
  deterministic server-side computation, never by copying a lab's verdict and
  never by AI.
- Maintain the certificate register, supersession chain, retention windows, and
  numbering integrity (QCLB 020 §6.13).
- Capture Annex-11 electronic signatures for the QC approval acts.
- Retain source documents with tamper-evident digests (ALCOA+ "Original").

**Explicitly out of scope / NOT the system's function:**
- It does **not** make the QP's Annex-16 batch-release decision (the QP *receives*
  the approved CoQ; release is a separate act outside the app, with a qualified
  eIDAS signature).
- It does **not** use generative AI anywhere on the value or release path.
- The task-management, facility, and analytics surfaces are a **planning zone**
  (two-zone scope per `docs/SCOPE.md`), not controlled QC records.

**As-built scale (branch head):** 24 `qc_*` tables, 75 QC endpoints, 101 QC
automated tests; migrations `0028`–`0036` deliver the URS gap closure on top of
the Phase-2/3 base (`0018`–`0027`).

---

## 2. System description & architecture

| Layer | Implementation | Control relevance |
|---|---|---|
| Data | Two PostgreSQL DBs (users / tasks). Every tenant table carries `org_id`; **FORCE + ENABLE row-level security** with an `org_isolation` policy | Tenant isolation is DB-enforced, not app-enforced (verified by `test_rls_coverage`) |
| Audit | Global **hash-chained** append-only `audit_log` via `app.fn_audit_row()` (`to_jsonb(NEW)` + previous-row hash); `/audit/verify` walks the whole chain | Annex 11 §9 audit trail; tamper-evident; audit rows are **never** deleted |
| Identity | 13-role model; transaction-scoped GUCs set by `rls(user)`; JWT with `password_set_at` invalidation | Access control + segregation |
| Determinism | Conformance graded in `qc.py` against the spec parameter limits; the eCoA path **recomputes**, never copies | Annex 22 deterministic-core principle |
| AI (edge only) | Dedicated Letta instance (`wwf_letta`) for assistive functions; DocEngine renders the CoQ; grounded FTS Q&A | AI touches no release data (see §3) |
| Deploy | Two stacks — `wwf_mass` (validation) + `wwf_app` (production, 25 users). Alembic migrations; `schema.tasks.sql` kept drift-equal (CI gate) | Change control (§10) |

---

## 3. AI inventory (URS §10.4 / EU GMP Annex 22)

Every AI touchpoint, its criticality, and the control that keeps it off the
record path. **No item is on the conformance/release value path.**

| # | AI touchpoint | What it does | Criticality | Control / gate |
|---|---|---|---|---|
| A1 | DocEngine section authors (Letta `gf_*`) | Draft SOP/report prose | Non-critical (assistive) | 100% human authoring/review before a controlled record; `pp_verify` PASS gate on render |
| A2 | Bilingual translation | MK⇄EN drafting aid | Non-critical | Human-editable; never the source of a measured value |
| A3 | AI planning / workload (Letta) | Task suggestions in the planning zone | Non-critical | Planning zone only (not a QC record); advisory |
| A4 | Grounded CoA Q&A (`/qc/coa-qa`) | Cites indexed passages `[doc#idx]` | Non-critical | **Non-generative** — returns cited passages or `grounded=false` empty; never synthesises a value |
| A5 | Intake candidate extraction (`/intake/extract`) | Text → task candidates (planning) | Non-critical | Human adopts each candidate; planning zone |
| — | **Conformance grading** | Determine `complies` | **CRITICAL** | **Deterministic code only — no AI.** `_evaluate()` vs spec limits |
| — | **CoQ issuance** | Emit the certificate | **CRITICAL** | Deterministic gates (§5) + `pp_verify`; no AI content on the value path |

**Divergence to decide (D5):** the URS mandates local/air-gapped models
(vLLM/Qwen, no egress). The platform currently uses cloud LLM providers via the
dedicated Letta — **acceptable while AI touches no release data (current state)**;
the planned OCR/extraction phase must run on local models (Docling/Surya + local
VLM) **or** the air-gap requirement must be consciously amended. Implicates GPU
sizing (owner decision D5). Not yet built — see §12.

---

## 4. GAMP-5 categorisation

| Component | GAMP category | Rationale |
|---|---|---|
| PostgreSQL, Letta, Gotenberg, Traefik | Cat 1 (infrastructure) | Standard platform software |
| Alembic migrations / RLS / audit trigger | Cat 4→5 (configured/bespoke) | Bespoke schema + the hash-chained audit function |
| `qc.py` conformance & CoQ engine | **Cat 5 (bespoke)** | Custom GxP logic — the validation focus |
| DocEngine (pp-document-suite vendored + `pp_verify`) | Cat 4/5 | Configured house-style engine with a hard PASS gate |
| AI assistive layer (Letta agents) | Cat 3/4 (non-GxP) | Off the record path; not validated as a GxP function |

Validation effort concentrates on the **Cat 5 bespoke conformance/CoQ path** and
the data-integrity controls.

---

## 5. Critical control points (the CoQ cannot issue unless ALL hold)

`generate_coq` enforces, in order (each an automated test):
1. Certificate is **RELEASED** (re-asserted at stamp time — TOCTOU-safe).
2. **No open OOS** on the batch (item 1, mig 0028) — 409 with reason.
3. Every result **complies** — a FAIL/unmeasured result blocks (never fabricate a
   conformant CoQ).
4. **Completeness** — every spec parameter is covered by a cited result.
5. **WHO/Annex-16 content manifest** (item 10, increment 6) — material name, spec
   reference, batch, report date, PASS disposition, approver, testing lab (eCoA),
   analytical method per test.
6. DocEngine **`pp_verify` PASS** (house-style gate; FAIL → 422).

Ph. Eur. 3028 derived totals (total THC/CBD, item 3) are **computed by the
engine** from component results at this point, never transcribed.

---

## 6. Requirements traceability matrix (URS gap items → as-built)

| URS item | Requirement | Migration | Key endpoint(s) | Evidence (test / live smoke) |
|---|---|---|---|---|
| 1 | OOS gate on CoQ | 0028 | `POST /qc/certificates/{id}/coq` | `test_coq_blocked_by_open_oos` |
| 2 | Supersession chain (§6.7) | 0029 | `POST …/revise` | `test_coa_revision_supersession_chain` |
| 3 | Derived totals (Ph. Eur. 3028) | 0029 | `generate_coq` compute engine | `test_coq_computes_total_thc` (+ fail/missing) |
| 4 | Laboratory entity (Ch. 7) | 0030 | `/qc/laboratories` CRUD | `test_ecoa_doc_promote_carries_laboratory`, scope tests |
| 5 | Batch genealogy, m:n (D2) | 0036 | `/qc/genealogy`, `…/inherited-results` | `test_genealogy_chain_and_inherited_results`, blend, cycle |
| 6 | Register completeness (QCLB 020) | 0031 | `/qc/register`, `/qc/register/gaps` | `test_certificate_register_filters`, numbering gaps |
| 7 | 5-working-day review clock (§6.3.1) | 0032 | eCoA register/review transitions | `test_ecoa_review_clock_met` / `_missed_and_overdue` |
| 8 | Lab verdict captured + reconciled | 0028+0033 | eCoA extraction + `qc_results.lab_verdict` | `test_ecoa_lab_verdict_reference_only`, `test_promote_carries_lab_verdict_onto_result` |
| 9 | Code-pattern alignment | — (decision) | — | Resolved: `PP-ECOA-`/`PP-COA-` canonical; amend SOP, don't renumber |
| 10 | CoQ mandatory-content manifest (WHO TRS 1010) | — (backend) | `_coq_manifest` in `generate_coq` | `test_coq_manifest_blocks_missing_content`, `_requires_method` |
| 11 | iCoA record type + signatures | 0034 | `POST /qc/certificates/{id}/sign` | `test_certificate_esignature_records_and_lists` (type exists via `cert_type`) |
| 12 | PDF originals custody + SHA-256 | 0035 | `/qc/coa-documents/{id}/originals`, `/qc/document-files/{id}/download` | `test_coa_original_upload_download_and_integrity` |
| §3 | E-signatures reopened (Annex 11 §14) | 0034 | `POST …/sign` (re-authenticated) | `test_certificate_esignature_reauth_required` |

---

## 7. Risk assessment / FMEA (eCoA → CoQ pipeline)

Severity/likelihood qualitative; every high-severity mode has an implemented,
tested control (RPN driven low by design).

| # | Failure mode | Effect | Sev | Implemented control | Residual |
|---|---|---|---|---|---|
| F1 | A non-conforming batch is certified | Patient safety; regulatory | High | Comply gate + completeness gate + PASS-disposition manifest (§5) | Low |
| F2 | A value is fabricated / transcribed wrongly | Data integrity | High | Never-fabricate rule (unknown → null); eCoA path recomputes; derived totals computed not transcribed | Low |
| F3 | Lab's verdict silently overrides the in-house determination | Wrong conformance | High | Lab verdict is reference-only; `lab_verdict_mismatch` surfaces disagreement (item 8) | Low |
| F4 | Approval by an unauthorised or non-independent person | Segregation breach | High | Role gates + second-person (reviewer ≠ any result analyst); re-authenticated e-signature (item 11) | Low |
| F5 | A record is altered after the fact undetectably | Data integrity | High | Hash-chained audit_log; `/audit/verify`; immutable post-RELEASE/PROMOTED; supersession not edit | Low |
| F6 | Source document lost or tampered | ALCOA+ Original | Med | `qc_document_files` bytea + SHA-256; re-hash on download → `X-Integrity` (item 12) | Low |
| F7 | Cross-tenant data leakage | Confidentiality | High | FORCE RLS `org_isolation` on every table (`test_rls_coverage`) | Low |
| F8 | Certificate numbering gap hides a lost record | Data integrity | Med | `/qc/register/gaps`; honest shared-sequence caveat (a gap flags investigation, never asserts loss) | Low |
| F9 | Review deadline missed silently | Timeliness (§6.3.1) | Med | Deadline stamped at registration; `review_overdue`/`review_window_met` (item 7) | Low |
| F10 | Blended-batch lineage lost | Traceability | Med | m:n genealogy + cycle guard + ancestor-result inheritance (item 5) | Low |
| F11 | AI introduces content onto the record path | Annex 22 breach | High | AI is edge-only; conformance/CoQ are deterministic (§3) | Low |

---

## 8. Data integrity — ALCOA+ mapping

- **Attributable** — every mutation records the actor; e-signatures snapshot the
  signer name/role; audit_log is per-row.
- **Legible / Contemporaneous** — timestamps `now()` server-side; review/sign at
  the moment of the act.
- **Original** — source documents retained with SHA-256 (item 12); the lab's own
  verdict retained verbatim (item 8).
- **Accurate** — deterministic grading; derived totals computed; re-hash
  integrity check on download.
- **Complete / Consistent / Enduring / Available** — append-only audit chain,
  supersession (never delete), retention windows + register (QCLB 020), two-DB
  backups (pg_dump) incl. stored originals.

---

## 9. Roles, segregation & access

- Read (QC domain): elevated roles (`ELEVATED_ROLES`). Write: `ADMIN`, executives,
  `QC_MGR`, `QP`. QP-only acts (release/reject/OOS disposition) gated tighter.
- **Second-person review:** the reviewer must differ from the analyst *and* from
  any analyst who entered a result on the certificate (compared by actor id).
- **CoQ issuance** is a QC-Manager function; the QP does **not** issue it (drops
  the earlier QP-issue path) — QP receives it for the separate release act.
- Annex-11 e-signature requires **re-authentication** (account password) at sign
  time (item 11 / §3).

---

## 10. Validation approach (IQ/OQ/PQ) & change control

- **IQ** — reproducible infrastructure: pinned images, Alembic head, compose on
  both stacks; `schema.tasks.sql` is a full pg_dump kept **byte-drift-equal** to
  the alembic-built schema (CI gate: alembic-built vs schema-file-built diff).
- **OQ** — the automated suite is the OQ evidence base: **101 QC tests** (part of
  the full backend suite, currently 422 passing) exercise every control in §5–§7;
  migration up/down/base reversibility is verified each increment.
- **PQ** — per-increment **live behavioral smoke on wwf_mass** with real QC roles
  (spec→sample→CoA→OOS→CoQ; e-signature; custody; genealogy) documented in
  `docs/DEPLOY.md`; production verified for health + auth-gating each deploy.
- **Change control** — every increment: delta → additive migration → tests → local
  gate (pytest + drift + reversibility + `node --check`) → deploy to wwf_mass then
  production → live smoke → `DEPLOY.md` entry → commit. **Rollback** is documented
  per increment (image revert + additive-migration downgrade; all 0028–0036 are
  additive/reversible).

---

## 11. Regulatory position

The AI-boundary story — deterministic record path, assistive AI at the edge, a
dedicated Letta instance, role-gated functions, non-generative grounded RAG — is
aligned with draft **Annex 22** and revised **Annex 11** (expected ~mid-2026).
This document is the intended-use statement + AI inventory the URS §10.4 calls
for; the FMEA (§7) and validation approach (§10) seed the validation plan. The
approved URS, executed IQ/OQ/PQ with signatures, and QA approval remain owner-side
to complete the file.

---

## 12. Open items (not built — need an input, not fabricated)

| Item | Blocker | Owner input needed |
|---|---|---|
| OCR / extraction value-path (URS proposer → 100% human verify → commit) | Needs local models per the air-gap requirement + GPU | **D5** (GPU sizing + air-gap vs cloud amendment); the custody hook (`qc_document_files`, page/bbox-ready) is in place |
| CoQ rendered layout parity | Needs the house template | **D1** — provide `CoQ_Template_v02_VariationF.html` |
| Local/air-gapped AI migration | Hardware + model selection | **D5** |
| Letta ops (0.17 upgrade, master-key rotation, PQ1 re-embed) | No driver | Maintenance window + a driver (held per `docs/LETTA-OPS-BACKLOG.md`) |
| TMS manager submit→approve/reject + QP-remark sign-off (inert `tasks.workflow_state`) | New module on the live TMS | Explicit owner request to build it (GxP-scope-sensitive; touches 25 live users' approval flow) |
| Executed validation file (approved URS, IQ/OQ/PQ signatures, QA approval) | Human sign-off | Owner starts the formal validation file using this document as the basis |
