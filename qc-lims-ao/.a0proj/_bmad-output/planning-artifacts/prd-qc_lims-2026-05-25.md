---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
inputDocuments:
  - /a0/usr/projects/qc_lims/.a0proj/_bmad-output/planning-artifacts/product-brief-qc_lims-2026-05-25.md
  - /a0/usr/projects/qc_lims/.a0proj/_bmad-output/planning-artifacts/research/domain-eu-gmp-pharma-qc-lims-cannabis-research-2026-05-25.md
  - /a0/usr/projects/qc_lims/.a0proj/_bmad-output/implementation-artifacts/spec-p0-foundation.md
  - /a0/usr/projects/qc_lims/_bmad-output/planning-artifacts/coa_track_analysis_and_recommendations.md
  - /a0/usr/projects/qc_lims/_bmad-output/planning-artifacts/coa_track_integration_sop_grounded_roadmap.md
  - /a0/usr/projects/qc_lims/_bmad-output/planning-artifacts/ux-design-specification.md
  - /a0/usr/projects/qc_lims/QC_LIMS_Comprehensive_Vision_and_Architecture.md
workflowType: prd
lastUpdatedAt: '2026-05-25T03:58:00+02:00'
classification:
  projectType: web_app
  domain: healthcare / pharmaceutical QC
  complexity: high
  projectContext: brownfield
---

# Product Requirements Document - QC_LIMS

**Author:** User
**Date:** 2026-05-25

## Executive Summary

QC_LIMS is an **ALCOA++ data integrity engine** with a web interface, purpose-built for EU GMP cannabis QC laboratories. It serves the full analytical lifecycle of dried cannabis flower products — from raw material sampling through finished product release, stability studies, water system QC, and OOS investigation — at Purely Plant GmbH, a licensed cannabis API manufacturer in North Macedonia.

**The Core Problem:** QC analysts spend disproportionate time on regulatory documentation rather than analytical science. Every test result must be manually verified against specification limits, every SOP clause cross-referenced, every calibration status checked, every review step initiated — creating cognitive overhead that slows throughput and introduces compliance risk. Existing commercial LIMS platforms (LabWare, LabVantage) are generic pharma systems requiring 18-month implementations at €200K+ license costs, without cannabis-specific methods or bilingual support.

**The Solution:** QC_LIMS makes compliance the path of least resistance. Analysts scan a barcode and the system loads full sample context — specification limits, SOP requirements, calibration status, and test methods. Data entry uses high-density grid interfaces with keyboard navigation for 50+ results per batch. Letta RAG agents provide advisory SOP guidance with verifiable citations in <5 seconds. Reviews are exception-based — reviewers see only deviations, not 100% of passing results. Every action is automatically documented with cryptographic audit trail integrity that satisfies EU GMP Annex 11 and 21 CFR Part 11 without analyst effort.

### What Makes This Special

1. **Compliance-as-Infrastructure, Not Features:** The audit trail is not a module — it's a foundational WORM (Write Once Read Many) layer with cryptographic hash chaining. The system is physically incapable of audit tampering, not merely policy-prohibited.

2. **AI-Assisted, Human-Confirmed:** 191+ SOPs ingested in Qdrant vector DB provide AI guidance at the point of work — but every RAG response includes source citation verification. The AI advises; the analyst decides. This avoids both automation complacency and hallucination risk.

3. **Transparent Automation:** Every background check (calibration status, spec validation, escalation timer) is surfaced with visible indicators. The user is never unaware of what the system has done.

4. **Exception-Based Review:** Reviewers process 20+ COAs daily by seeing only flagged deviations and boundary conditions — not scrolling through 100% of passing results.

5. **QP Release Dossier:** A one-page auto-generated compliance attestation summarizing every check, SOP version, and data integrity validation — compressing 10,000 audit events into 10 attestation bullets for batch release.

6. **Inspector-Ready by Default:** Pre-packaged compliance views (Validation Master Plan summary, Audit Trail Integrity Proof, Software Update History with change control links) that answer the three questions every inspector asks in <5 minutes.

7. **Bilingual Infrastructure (MK/EN):** Every label, COA, SOP reference, and UI element serves both Macedonian primary speakers and English-speaking inspectors — stored as canonical keys with dual translations, not a translation layer.

8. **No Time Pressure, Progressive Review:** Data entry is fast; release actions require deliberate ritual (MFA signature). Reviews flow through stages (auto-check → analyst → reviewer → QP) with clear handoff at each relay — no countdown timers, no urgency nags.

The following classification sets the engineering context for downstream architecture and implementation.

| Attribute | Value |
|-----------|-------|
| **Project Type** | Web App (desktop-first responsive SPA, tablet-capable for cleanroom use) |
| **Domain** | Healthcare / Pharmaceutical QC (EU GMP regulated cannabis laboratory) |
| **Complexity** | High — GxP regulated system requiring validation, audit trail immutability, and electronic signatures |
| **Project Context** | Brownfield — extends existing backend scaffold (FastAPI models, COA tracker, QMS API, Letta daemon) |

## Success Criteria

### User Success

**QC Analyst (Blagoj, 28):**
- Complete sample data entry for a full batch (5 samples × 12 parameters) in under 15 minutes, with barcode scan → context load in <2 seconds
- Resolve ambiguous RAG guidance by verifying source citation without leaving the data entry screen
- Submit an OOS result and know within 1 click what the next required action is (Phase I wizard)
- Never lose work — every keystroke is saved as an audit entry; no data entry session is lost due to timeout or crash
- Feel confident the system has validated calibration status, spec limits, and reviewer assignments without manually checking each one

**QC Reviewer (Sofija, 35):**
- Review 20 COAs per day by seeing only flagged deviations and boundary conditions — not scrolling through 100% of passing results
- Complete a review decision (approve/request amendment) in 30 seconds per COA
- See the full data lineage of any result (who entered it, who amended it, why) in 2 clicks
- Batch-compare 10 sample results side-by-side to detect patterns or anomalies

**QC Manager (Valter, 42):**
- Open a risk telemetry dashboard that shows: overdue OOS investigations, analyst error rates (spec-adjusted), calibration overdue alerts, and stability pull schedule for the next 30 days
- Identify the top 3 compliance risks in the lab in under 60 seconds
- Trend cannabinoid or microbial results across batches and detect drift before it becomes a spec violation

**Qualified Person (Dr. Petrova, 50):**
- Generate a one-page QP Release Dossier for any batch in under 10 seconds — summarizing every compliance check, SOP version, data integrity validation, and personnel involved
- Review and approve a COA with two-component electronic signature (password + token) in under 2 minutes
- Demonstrate to an inspector that the audit trail is cryptographically intact and immutable, without involving IT

**EU GMP Auditor (external):**
- Answer the three inspection questions (validation master plan, audit trail integrity proof, software update history) in under 5 minutes from a pre-packaged Inspector Mode view
- Export any record (COA, OOS report, training log, calibration cert) as PDF/A in under 30 seconds
- Search 10+ years of records and find any specific result within 5 seconds

**System Admin (part-time IT contractor):**
- Deploy a software update (Docker Compose pull + restart) in under 10 minutes without data loss or downtime
- Diagnose a service issue from health-check endpoints and structured logs without SQL access
- Run a database migration automatically as part of deployment with verified rollback capability

### Business Success

**3-Month Success (Post-Go-Live Validation):**
- All 6 QC SOP-referenced modules (Sample, Spec, COA, OOS, Stability, Audit Trail) validated per EU GMP Annex 11 Category 4 (IQ + OQ + PQ)
- First batch released using system-generated COA with electronic QP signature
- Average COA creation time reduced by 40% (from 4h manual to 90 min system-assisted)
- Zero audit trail integrity gaps identified during internal QA audit

**12-Month Success (Established Operation):**
- 100% of batches tracked end-to-end in the LIMS (no parallel paper system)
- OOS investigation cycle time reduced by 60% (from 8h to 3h) through structured wizard and RAG-guided root cause analysis
- Inspector Mode validated during a real or mock EU GMP inspection — all three inspection questions answered in under 5 minutes
- System uptime ≥ 99.5% (excluding planned maintenance) with RTO ≤ 24 hours
- QP signs 100% of batch releases electronically (no paper COAs)
- Staff training time for new analysts reduced by 50% (SOP guidance at point of work reduces memorization burden)

**ROI Justification:**
- Preventing one failed EU GMP inspection justifies the entire system cost (inspection failure → product hold → revenue loss + remediation cost)
- Elimination of paper logbooks saves 2 FTE-hours/day in documentation overhead
- Reduction of OOS investigation cycle time from days to hours means faster batch disposition and reduced inventory holding costs

### Technical Success

**Data Integrity (ALCOA++):**
- Every state transition in the system produces a cryptographically signed audit entry with hash chaining — zero gaps detectable by an automated verification tool
- The audit trail infrastructure is physically WORM (Write Once Read Many) — no user role, including System Admin, can modify or delete audit records
- Raw data (HPLC chromatograms, balance readings) stored immutably as received; any transformation produces a new record with a supersession link

**Performance:**
- Barcode scan → full sample context load (specs, calibration status, SOP references): <2 seconds
- COA PDF generation (python-docx → Gotenberg): <15 seconds for a full COA with 30 parameters
- RAG query (question → cited SOP answer): <5 seconds at p95
- Global search across 10 years of records: return results in <5 seconds
- Audit trail integrity verification (full hash chain walk for a batch): <30 seconds

**Reliability:**
- System uptime ≥ 99.5% (excluding planned maintenance)
- Recovery Time Objective (RTO): ≤ 24 hours
- Recovery Point Objective (RPO): ≤ 1 hour (daily incremental backups + point-in-time recovery)
- Backup restore tested and documented quarterly

**Security & Compliance:**
- Authentication: Password (8 chars, complexity, 90-day expiry) + MFA for release/approve actions
- Automatic lockout: 5 failed attempts, inactivity timeout 15 minutes with 2-minute warning
- Role-based access: Each role (Analyst, Reviewer, Manager, QP, Auditor, Admin) has precisely defined permissions — no role overlap, no shared accounts
- Electronic signatures: Two-component (password + token) required for: COA approval, batch release, OOS closure, specification approval
- All data transmitted over TLS 1.3; audit trail entries encrypted at rest with independent key management

**Maintainability:**
- Deployed via Docker Compose with health-check endpoints for all services
- Database migrations run automatically as part of deployment with verified rollback capability
- All services produce structured JSON logs consumable by standard log aggregators
- Operational runbooks documented and tested during validation

## User Journeys

### 1. Blagoj — QC Analyst (Primary User — Success Path)

**Opening Scene:** Blagoj, 28, starts his morning shift at the QC lab. There are 3 batches of dried cannabis flower awaiting release testing — each with 5 samples, each requiring 12 analytical parameters (loss on drying, cannabinoid profile, heavy metals, microbial limits). Yesterday he spent 4 hours cross-referencing SOPs to confirm which specs apply to which sample type. Today, he opens QC_LIMS.

**Rising Action:** Blagoj scans the barcode on Sample PP-SMP-2026-0087-A. In under 2 seconds, the screen populates: the full specification (cannabinoid limits from QCSOP 010, microbial limits from QCSOP 024), the HPLC calibration status ("Calibrated: 2 days ago — valid"), and the assigned reviewer (Sofija). He clicks "Enter Results" and the keyboard-navigable grid opens — 12 rows, each with a parameter label (MK/EN), spec limits displayed as guardrails, and immediate validation as he types. When he enters "12.3" for THC content, the field turns amber — the spec upper limit is 1.0. A tooltip appears: "Value exceeds specification limit. This will require OOS investigation." He re-checks the sample prep and realizes he mislabeled the vial. He enters the correct result: "0.7" — the field turns green.

**Rising Action — RAG Guidance:** On the moisture balance result, he pauses. He's unsure about the exact drying time per Ph. Eur. 2.02.12. He types in the guidance panel: "Drying time for cannabis flower loss on drying?" Within 3 seconds, a response appears: "Per QCSOP 016 Section 5.3: Dry at 105°C to constant weight (typically 2-4 hours for cannabis flower). Ph. Eur. 2.02.12 specifies drying at 100-105°C. [Verify Citation]" A click on "Verify Citation" opens the SOP PDF at the exact paragraph. He confirms and proceeds.

**Climax — OOS Detection:** On the fifth sample, the CBD result is below the specification lower limit (4.2% vs. 5.0% minimum). A red badge appears: "OOS DETECTED — QCSOP 019 Phase I required." With one click, the Phase I investigation wizard opens — a structured form pre-populated with the result, spec, analyst name, and timestamp. The wizard asks: "Did you observe any of the following during sample preparation? (checklist)" Blagoj checks "Possible extraction error — solvent volume miscalculated." The system auto-logs the entry to the OOS Register (QCSOP 019-A03) and triggers notification to his supervisor (QCSOP 019-A04).

**Resolution:** Blagoj submits his batch. All results are saved, every keystroke is in the audit trail. The system shows: "Completed: 5/5 samples. Pending: Reviewer (Sofija)." He logs out confident that he hasn't left an undocumented result, missed a calibration check, or created a future finding for the QP. The batch took 22 minutes to enter, down from his usual 60+ minutes.

**Journey Requirements Revealed:**
- Barcode-triggered context load with calibration status, spec limits, reviewer assignment
- Keyboard-navigable grid data entry with in-cell validation
- RAG guidance panel with citation verification
- One-click OOS Phase I wizard with pre-populated fields
- Audit trail logging of every keystroke and value change
- Status tracking showing workflow handoff point

---

### 2. Sofija — QC Reviewer (Secondary User — Throughput Path)

**Opening Scene:** Sofija, 35, opens QC_LIMS at 14:00. Her queue shows 18 COAs awaiting review. On paper, this would be a 3-hour task of scrolling through result after result, cross-checking specs, and hoping she doesn't miss a deviation. She opens the "Review Queue" view.

**Rising Action:** Instead of 18 individual screens, she sees the **Exception-Based Review Dashboard**. For each COA, the system shows a single line: Batch ID, Sample Count, Results Total, Deviations (highlighted in amber), and OOS (highlighted in red). 14 of 18 COAs show "Deviations: 0, OOS: 0." She bulk-approves these 14 with two clicks (select all → approve → MFA confirm). The system records each approval with her electronic signature. Now she has 4 COAs with exceptions to review in detail.

**Climax — Investigating a Deviation:** One COA shows "Deviations: 1 — Loss on Drying result 8.7% (spec limit ≤8.0%)" with amber highlight. She opens the full result view. In 2 clicks, she sees the data lineage: Blagoj entered 8.7 at 10:23, the system auto-flagged it at 10:23, and the auto-calculated deviation percentage (8.75%) confirms it's a real exceedance. She also sees side-by-side: the same parameter across all 5 samples from the batch — 8.7%, 7.9%, 7.8%, 8.1%, 7.9%. One outlier sample. She clicks into the OOS record that Blagoj already opened and sees his Phase I note: "Possible extraction error — solvent volume miscalculated." She confirms the Phase I investigation is underway and approves the other 3 COAs.

**Resolution:** Sofija completes her review queue in 18 minutes. The system generates review metrics: "Reviewed: 18 COAs. Bulk-approved: 14. Exception-inspected: 4. Time per exception: 2.5 minutes." She feels confident that she hasn't missed a deviation because the system highlighted every one for her.

**Journey Requirements Revealed:**
- Exception-based review dashboard (show only deviations, not 100% of passing results)
- Bulk-approve with MFA-signed electronic signature
- Data lineage view (who entered, when, why it was amended)
- Side-by-side sample comparison for pattern detection
- Auto-calculated deviation percentages
- Review session metrics for continuous improvement

---

### 3. Valter — QC Manager (Management — Risk Telemetry Path)

**Opening Scene:** Valter, 42, has 15 minutes before the weekly management meeting where he must report on QC lab performance. He opens QC_LIMS to the **Manager Risk Telemetry Dashboard**.

**Rising Action:** The dashboard loads immediately with live data. The top section shows **Critical Alerts:** "1 Overdue OOS Investigation: PP-OOS-2026-0014 (Phase II — 3 days overdue)." He expands it and sees that the CAPA effectiveness check was due on May 20. The investigator is assigned but the step is stalled. He clicks "Send Reminder" and an automated notification goes to the investigator with a CC to his own email.

The second section — **Analyst Performance Metrics** — shows a bar chart of OOS invalidation rates per analyst over the last quarter. Blagoj: 2.3%, Marko: 1.8%, Ana: 5.1%. Ana's rate is elevated. He notes to discuss root cause with her (training gap? technique issue?). The system auto-calculated these rates from the OOS register, filtering out confirmed-lab-error invalidations from true OOS.

The third section — **Calibration Status** — shows 2 balances due for calibration in the next 7 days. He clicks "Generate Calibration Request" and the system populates a pre-formatted work order with equipment IDs, last calibration dates, and due dates.

**Climax — Trend Detection:** The **Specification Drift Dashboard** shows a sparkline chart of CBD content across the last 30 batches. A subtle downward trend is visible — from 7.2% average to 6.5% over the last 8 batches. All results are within spec (≥5.0%), so no OOS has triggered, but the trend is clear. He clicks "Flag for Stability Review" and the system creates a linked note referencing the stability study for the most recent batch — a potential long-term stability issue caught before it becomes an OOS.

**Resolution:** Valter generates a 1-page "Manager's Weekly Report" with one click. It includes the overdue OOS, analyst metrics, upcoming calibrations, and the CBD trend alert. He walks into the management meeting with data-driven insights, not gut feelings.

**Journey Requirements Revealed:**
- Live risk telemetry dashboard with categorized alerts
- Automated notification triggering for overdue items
- Analyst performance metrics auto-calculated from OOS/audit data
- Calibration status overview with work order generation
- Specification drift trend detection with sparkline visualization
- One-click weekly report generation

---

### 4. Dr. Petrova — Qualified Person (Release Authorization Path)

**Opening Scene:** Dr. Petrova, 50, is responsible for certifying every batch before release to the EU market. A batch rejection doesn't just cost money — it triggers regulatory reporting. She opens the QP workspace at 16:30 to review Batch PP-BCH-2026-0042, a 15 kg lot of medical cannabis flower destined for a German pharmacy.

**Rising Action:** She clicks "Generate Release Dossier" for the batch. Within 10 seconds, a single-page summary appears:

| Check | Status | Detail |
|-------|--------|--------|
| Specification Version | ✓ | QCSOP 010 v3.2, effective 2026-01-15 |
| COA Parameters Complete | ✓ | 12/12 parameters tested |
| Results Comply with Spec | ✓ | All results within limits |
| 2nd Person Verification | ✓ | Verified by Sofija (Reviewer) at 2026-05-25 14:23 |
| OOS Events | ⚠ | 1 Phase I OOS (PP-OOS-2026-0042A) — lab error, invalidated |
| Audit Trail Integrity | ✓ | Hash chain verified, 847 entries, last entry #847 |
| Calibration Status | ✓ | All instruments within calibration window at time of testing |
| Personnel Training | ✓ | All personnel qualified on relevant methods |
| Stability Data | ℹ | Batch entered long-term study — Month 3 pull due 2026-08-01 |

**Climax — OOS Review:** She expands the OOS entry to verify the invalidation was properly documented. The system shows the full Phase I form, Blagoj's entry, Sofija's confirmation, and Valter's approval — all with timestamps and electronic signatures. She's satisfied the invalidation follows QCSOP 019 procedure. She clicks "Approve for Release."

**Resolution:** The system prompts for her two-component electronic signature: password + SMS token. She enters both. The COA is digitally signed, the batch status changes to "RELEASED," a 21 CFR Part 11-compliant signature block is appended to the COA PDF (name, date/time, meaning: "Approved for EU market release"), and the release event is immutably logged in the audit trail with her cryptographic signature.

**Journey Requirements Revealed:**
- One-click Release Dossier generation
- Data-integrity verification summary (hash chain check, calibration window validation)
- Drill-down capability for each attestation check
- Two-component electronic signature (password + token)
- Part 11-compliant signature block in final document
- Immutable release event logged in audit trail

---

### 5. EU GMP Inspector — Auditor (Compliance Verification Path)

**Opening Scene:** A BfArM inspector arrives for an unannounced EU GMP inspection at Purely Plant GmbH. Their first question: "Show me your validation evidence for the computerised system."

**Rising Action:** The QA Manager opens QC_LIMS, logs in as the read-only Auditor role, and navigates to **Inspector Mode**. This is a pre-packaged view designed explicitly for inspections. The first screen shows the **Validation Master Plan Summary** — a one-page overview of the IQ/OQ/PQ results, the Category 4 classification, and the most recent periodic review date. The inspector clicks into the IQ report, reviews the infrastructure qualification evidence, and returns to the main screen.

The inspector asks a second question: "Prove to me that the audit trail cannot be tampered with." The QA Manager opens the **Audit Trail Integrity Proof** view. The system performs a real-time hash chain walk for the most recent complete batch, displaying the cryptographic verification: "Hash chain integrity: VERIFIED. Total entries: 847. First entry hash: a3f2... Last entry hash: 9b1e... Chain: UNBROKEN." The system also shows that "No role, including System Administrator, has write or delete permissions on the audit storage tier."

**Climax — Third Question:** The inspector asks: "Show me the change log for all software updates in the last 12 months." The QA Manager opens **Software Update History** — a timeline view showing: v1.0.3 (2025-07-12 — "Patch: OOS wizard form validation fix"), v1.1.0 (2025-09-03 — "Feature: Stability pull schedule automation"), each with a link to the corresponding Change Control record, the approval signatures, and the validation evidence for the update.

**Resolution:** All three questions answered in under 4 minutes. The inspector moves on to the next system. The inspection ends with no computerised-systems findings.

**Journey Requirements Revealed:**
- Pre-packaged Inspector Mode with three mandatory compliance views
- Read-only auditor role with no write access to any GxP data
- Real-time hash chain integrity verification
- Audit trail non-tamperability demonstration (permission audit)
- Software update history with change control links
- PDF/A export of any view for inspection evidence

---

### 6. Ljupcho — System Admin (Operations Path)

**Opening Scene:** Ljupcho, part-time IT contractor, receives a notification: "New QC_LIMS version v1.3.0 available. Includes: Cannabinoid calculation engine fix (THCA→THC conversion). Requires database migration." He has a 30-minute maintenance window at 19:00.

**Rising Action:** He SSHs into the Docker host and runs the documented update procedure:

```bash
cd /opt/qc_lims
docker compose pull
docker compose up -d
```

The deployment script runs automatically. The database migration executes within 15 seconds. Health checks on all services return green: API (200 OK), worker (heartbeat detected), Letta bridge (connected). The previous version containers remain as warm standbys. If health checks had failed, the rollback command would have restored the previous version in under 2 minutes.

**Climax — Validation Post-Deploy:** The deployment script triggers the post-deployment validation suite. It runs automated tests against the API — creating a test sample, entering results, generating a COA, and verifying the audit trail hash chain. All tests pass. The deployment is logged with version number, timestamp, migration scripts executed, and rollback capability verified.

**Resolution:** Ljupcho's total involvement: 4 minutes of active work. His total maintenance window: 12 minutes including validation. The system sends an automated deployment notification to the QC Manager: "QC_LIMS v1.3.0 deployed successfully. Change: Cannabinoid THC conversion fix. Validation: All tests passed. No action required."

**Journey Requirements Revealed:**
- Docker Compose deployment with automated migrations
- Health-check endpoints for all services
- Automated post-deployment validation suite
- Verified rollback capability
- Versioned deployment log
- Automated deployment notification to stakeholders

## Journey Requirements Summary

| Journey | User Type | Key Capabilities Required |
|---------|-----------|--------------------------|
| Blagoj (Success Path) | Primary — Analyst | Barcode context load, grid data entry, in-cell validation, RAG guidance, one-click OOS wizard, keystroke-level audit |
| Sofija (Throughput) | Secondary — Reviewer | Exception-based review dashboard, bulk-approval, data lineage, side-by-side comparison, review metrics |
| Valter (Risk Telemetry) | Management — Manager | Live alerts dashboard, analyst performance metrics, calibration overview, trend detection (sparklines), weekly report generation |
| Dr. Petrova (Release) | Authorization — QP | Release Dossier generation, data-integrity verification, drill-down attestation, two-component e-signature, Part 11 signature block |
| Inspector (Compliance) | External — Auditor | Inspector Mode (pre-packaged views), hash chain integrity proof, software update history, read-only auditor role, PDF/A export |
| Ljupcho (Ops) | Operations — Admin | Docker Compose deployment, health checks, automated migrations, post-deploy validation suite, rollback capability, deployment logging |

## Domain-Specific Requirements

### Compliance & Regulatory

**Primary Regulatory Framework — EU GMP (EudraLex Volume 4):**

| Annex | Title | LIMS Mandate |
|-------|-------|-------------|
| **Annex 1** | Manufacture of Sterile Medicinal Products | Cleanroom classification tracking, environmental monitoring schedules with alert/action limits for Grade A/B/C/D areas |
| **Annex 11** | Computerised Systems | Validation (IQ/OQ/PQ Category 4), immutable audit trail, user access control, backup/restore, business continuity, change control, time synchronization (NTP) |
| **Annex 15** | Qualification & Validation | Method validation records, cleaning validation records, process validation data — all must be traceable within LIMS |
| **Annex 16** | Certification by QP & Batch Release | QP review workflow, batch release decision logging, COA electronic signing with 21 CFR Part 11 compliance |

**ICH Q10 — Pharmaceutical Quality System:**
- CAPA system: OOS → CAPA workflow, root cause analysis tracking, effectiveness check scheduling
- Change management: Spec versioning, method updates, document revision control — all changes logged and linked
- Quality risk management: Risk assessment templates (FMEA), risk-based decision justification for deviations and changes

**Data Integrity — ALCOA++ (WHO TRS 996, MHRA Guidance, PIC/S PI-041):**
- **Attributable:** Every action tied to authenticated user identity with cryptographic signature
- **Legible:** All records permanently readable in open formats (UTF-8, PDF/A, PNG); no proprietary binary blobs without extraction path
- **Contemporaneous:** Server-side timestamps only; client clocks untrusted; no batch entry or backdating modes
- **Original:** Immutable raw data store (append-only); corrections create supersession records, never in-place edits
- **Accurate:** Range checks, mandatory fields, 2nd-person verification for all release-critical data; e-signature requires re-authentication
- **Complete:** All data including repeats, recalculations, and re-injections; version stack for every calculated result
- **Consistent:** Logical clock ordering (Lamport); session UUIDs propagated across all related records; no gaps in sequence numbers
- **Enduring:** 10+ year retention with format migration plan tested annually; independent checksum storage for integrity verification
- **Available:** Sub-5-second search across full retention period; read-only auditor role; PDF/A export in <30 seconds

**21 CFR Part 11 — Electronic Records & Signatures (US benchmark):**
- §11.10: Validation, audit trail, authority checks, device checks
- §11.50: Signed electronic records must include printed name, date/time, meaning of signature
- §11.70: Signatures linked to records to prevent falsification
- §11.100: Electronic signatures uniquely tied to individuals
- §11.200: Two distinct identification components (password + token or biometric)

**EU Pharmacopoeia (Ph. Eur.) — Cannabis Testing Monographs:**

| Ph. Eur. Monograph | Method | Data Capture Requirement |
|--------------------|--------|-------------------------|
| 2.02.12 | Loss on Drying | Weight readings, temperature, drying time, % calculation |
| 2.02.32 | Water by Karl Fischer | Titrator output, water content % |
| 2.04.05 | Heavy Metals | ICP-MS/OES raw data, calibration curves, spec limits |
| 2.06.13 | Microbiological Examination (TAMC/TYMC) | Plate counts, dilution factors, spec limits per organism |
| 2.06.14 | Specified Micro-Organisms | Detection result, confirmation steps, enrichment media |
| 2.08.10 | Cannabinoid Profile (HPLC-DAD) | Peak areas, retention times, resolution, tailing factor, concentration calculations |
| 2.08.11 | Terpene Profile (GC-MS) | Peak identification, quantification against internal standard |
| 2.08.12 | Residual Solvents (GC-HS) | Class 1/2/3 limit checks per ICH Q3C |
| 2.08.13 | Mycotoxins (LC-MS/MS) | Aflatoxin B1/B2/G1/G2, Ochratoxin A quantification |
| 2.08.14 | Pesticide Residues (GC-MS/MS, LC-MS/MS) | 200+ pesticide screening against Ph. Eur. limits |

**WHO TRS 902 Annex 9 — GMP for Herbal Medicinal Products:**
- Section 4.8: QC of starting materials — botanical identity and purity verification
- Section 5.3: Stability testing of herbal preparations — cannabis-specific degradation pathways
- Section 6.1: Documentation requirements specific to botanical products — country of origin, cultivation method, harvest date

### Technical Constraints

**Data Integrity Infrastructure (Non-Negotiable):**
- Audit trail must be a foundational WORM (Write Once Read Many) layer, not an application feature
- Cryptographic hash chaining (SHA-256) between all audit entries — tamper-evident by construction
- No role, including System Administrator, has write or delete permissions on audit storage tier
- Raw instrument data (chromatograms, spectra, balance readings) stored immutably as-received; transformations create derived records with supersession links
- Independent integrity verification checksums stored in a separate system with quarterly validation

**Electronic Signatures (21 CFR Part 11 §11.200):**
- Two-component authentication for all release/approve/reject actions: password + time-based token (TOTP)
- Signature block appended to all signed documents: printed name, date/time (ISO 8601), meaning of signature (e.g., "Approved for EU market release"), cryptographic signature hash
- Signature lifecycle: Sign → Lock → Verify (no modification possible after signing)
- Password complexity: ≥8 characters, mixed case, digit, special character, 90-day expiry

**Authentication & Access Control:**
- MFA required for all users with release/approve permissions (Analyst data entry exempt but password-protected)
- Automatic lockout: 5 consecutive failed attempts → account locked for 30 minutes (audit logged)
- Inactivity timeout: 15 minutes with 2-minute countdown warning, server-enforced (not client-dependent)
- Role-based access control: Six roles with precisely defined, non-overlapping permissions
- Read-only Auditor role for inspector/external auditor access — zero write capability on any GxP record

**Time Synchronization:**
- All timestamps server-generated in UTC with local time offset (CEST) stored separately
- NTP synchronization mandatory with audit log of time server health
- Client clocks untrusted; batch entry timestamps rejected if session timestamp diverges from server by >5 seconds

**Backup & Business Continuity:**
- Daily incremental backups + weekly full backups with point-in-time recovery capability
- RPO (Recovery Point Objective): ≤1 hour
- RTO (Recovery Time Objective): ≤24 hours
- Backup restore tested and documented quarterly — test log stored in audit trail
- Off-site archive copy with 10+ year retention, format-migration plan tested annually

**Data Privacy:**
- All data transmitted over TLS 1.3 minimum
- Audit trail entries encrypted at rest with independent key management (separate from application database encryption)
- Personally identifiable information (PII) of personnel limited to: name, employee ID, role, training records, signature certificate
- No patient data — product is B2B cannabis API manufacturer (no direct patient interaction)

### Integration Requirements

**Letta Agent Platform (KVM4 Hostinger Server):**
- Letta API (port 8283) — synchronous RAG queries with <5 second p95 response time
- Qdrant vector DB (port 6333) — `pp_qms_sops` collection with 1024-dimensional voyage-3 embeddings
- Letta MCP Rust bridge (port 6507) — agent-to-agent communication protocol
- SSH tunnel from Docker container to KVM4 with automatic reconnection (ServerAliveInterval 60s)
- Graceful degradation: If Letta API unavailable, system operates with cached SOP references and degrades to manual SOP lookup — not a hard failure

**Document Generation:**
- python-docx for DOCX creation (COA, investigation forms, reports)
- Gotenberg PDF microservice (Hostinger server) for DOCX → PDF/A conversion
- PDF/A-3 format for long-term archival compliance
- Bilingual template rendering: canonical key → MK/EN translation at render time, not stored twice

**Existing System Integration:**
- coa_tracker/ — extend existing backend models (Sample, Specification, Certificate), do not rewrite
- qms-api/ — FastAPI microservice for QMS document generation, integrated via service layer
- letta-daemon/ — Letta agent daemon bridge for async agent orchestration

**Instrument Integration (Vision Phase — Post-MVP):**
- HPLC/CDS (Chromeleon/Empower) → direct data capture via file watcher or API
- Analytical balances → RS-232/USB data capture with balance ID → sample ID linking
- pH/conductivity meters → result import with calibration context
- LIMS as integration hub, not instrument controller

### Domain-Specific Risk Mitigations

| Risk | Mitigation | Validation Method |
|------|-----------|-------------------|
| **Inspector Unfamiliarity with Custom System** | Pre-packaged Inspector Mode with Validation Master Plan, Audit Trail Integrity Proof, and Software Update History. All views exportable as PDF/A. User manual written for auditor audience with EU GMP inspector checklist. | Mock inspection by external GMP consultant before go-live |
| **AI RAG Hallucination or Stale Guidance** | All RAG responses include source citation with version verification. "Verify Citation" button opens original PDF. Advisory-only policy — analyst must confirm. RAG accuracy audit quarterly with known-answer test set. Multi-step retrieval with cross-encoder re-ranking. | RAG accuracy audit results ≥95% on known-answer test set |
| **Audit Trail Tampering (Insider Threat)** | WORM storage at infrastructure level. Cryptographic hash chain. No role has write/delete on audit tier. Independent checksum verification in separate system. Tampering attempt logged and triggers alert. | Quarterly hash chain integrity verification with automated tool |
| **Software Update Introducing Compliance Gap** | All updates go through documented change control. Post-deploy validation suite runs automated compliance tests (audit chain walk, COA generation, OOS wizard). Rollback capability verified before each deployment. Update history with change control links visible in Inspector Mode. | Change control record + validation evidence required before production deployment |
| **Regulatory Method Change (Ph. Eur. Monograph Update)** | Specification versioning with effective dates. When a Ph. Eur. monograph updates, affected specs flagged for review. Results always linked to the specification version active at time of testing. | Annual spec review triggered by Ph. Eur. supplement calendar |
| **Data Loss or Corruption** | Daily incremental + weekly full backups with point-in-time recovery. Quarterly restore test with integrity verification. Off-site archive with format migration plan. Independent checksum for each backup. | Quarterly restore test results documented and stored in audit trail |
| **Bilingual Content Inconsistency** | All labels stored as canonical keys with dual translations. Translation changes are version-controlled. COA rendering validates both MK/EN output before PDF generation. | Bilingual review step in COA approval workflow |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Compliance-as-Infrastructure Architecture**

The pharmaceutical LIMS market (LabWare, LabVantage, STARLIMS) treats compliance as configurable features — audit trail modules, permission settings, signature workflows. QC_LIMS inverts this: the system is an **ALCOA++ data integrity engine first**, with a web interface layered on top. The audit trail is not a module — it's a cryptographic WORM storage layer at the infrastructure level with SHA-256 hash chaining between every state transition, independently verifiable by an automated tool. No human role, including System Administrator, can bypass it. This is architecturally novel for a GxP regulated system where historically compliance has been policy-enforced, not physically enforced.

**2. RAG-Augmented SOP Guidance in GMP Context**

Existing LIMS systems display SOP references as static links. QC_LIMS ingests 191+ SOPs into a Qdrant vector database (voyage-3 embeddings, 1024d) and provides cited, contextual answers at the point of work in <5 seconds. The innovation isn't the RAG technology itself — it's the **safety architecture around it**: mandatory citation verification (one click opens PDF at cited paragraph), advisory-only policy (AI advises, analyst decides), multi-step retrieval with cross-encoder re-ranking, sentence-preserving chunking, and quarterly RAG accuracy audits against known-answer test sets. This bridges AI assistance with GMP compliance requirements where no existing LIMS does.

**3. QP Release Dossier — Compressed Trust Evidence**

Instead of requiring the Qualified Person to manually review a 50-page audit trail before batch release, QC_LIMS generates a **one-page compliance attestation** that compresses 10,000 audit events into 10 attestation bullets: specification versions, calibration status windows, personnel training verification, audit chain integrity proof, and OOS event summaries — all with drill-down capability behind each attestation. This concept of "summarized trust evidence" for regulatory certification is novel in the LIMS space and directly addresses the QP's primary pain point.

**4. Inspector Mode — Pre-Packaged Compliance Demonstration**

Every GMP inspector asks the same three questions: (1) Show me your validation, (2) Prove the audit trail is immutable, (3) Show me your change control. QC_LIMS bakes these into a dedicated **Inspector Mode** — a read-only auditor role with pre-built views that answer all three questions in under 5 minutes, with PDF/A export of every view as inspection evidence. No existing LIMS ships with an inspector-facing interface; inspectors are typically given ad-hoc screen shares or exported reports.

**5. Transparent Automation with Progressive Review**

Automation in regulated systems is dangerous if invisible. QC_LIMS surfaces every automated action (calibration check, spec validation, escalation timer, review assignment) with visible indicators and audit trail entries. The progressive review flow (auto-check → analyst → reviewer → QP) is a relay race with clear handoff at each stage — inspired by the principle that the system should never silently make decisions that belong to humans. Combined with the no-time-pressure UX (no countdown timers, no urgency nags) and scan-first data entry, this creates a new interaction paradigm for lab software.

### Market Context & Competitive Landscape

**Existing Solutions:**
- **LabWare LIMS:** 20+ year market leader. Generic pharma platform requiring extensive configuration, 18-month implementation timelines, and €200K+ license costs. No cannabis-specific methods, no bilingual support, no AI guidance features.
- **LabVantage:** Similar feature set to LabWare. Stronger analytics but equally generic. No domain-specific cannabis modules.
- **Benchling:** Cloud-native but focused on R&D labs, not QC/production release. Lacks GMP batch release workflow and regulatory submission features.

**White Space:**
No existing LIMS system combines (a) cannabis-specific analytical methods (Ph. Eur. 2.08.10-2.08.14), (b) AI-assisted SOP guidance with safety guardrails, (c) foundational audit trail infrastructure with cryptographic immutability, and (d) bilingual (MK/EN) support in a single, deployable system designed for small-to-medium GMP facilities. Purely Plant GmbH's specific need — affordable, cannabis-native, EU GMP validated — is unserved by commercial vendors.

### Validation Approach

**For Compliance-as-Infrastructure:** Construct a formal proof: (1) Identify every code path that writes to the audit storage tier, (2) Verify no code path bypasses it, (3) Verify the storage tier accepts only INSERT (WORM), (4) Run automated hash chain verification tool on a full batch lifecycle after every deployment. This is testable and verifiable.

**For RAG-Augmented SOP Guidance:** Quarterly accuracy audits against a known-answer test set of 50 regulatory queries curated by QC Manager and QP. Target ≥95% accuracy on source citation correctness and ≥98% on "no fabricated clauses" (synthetic citation detection). Run the test set manually and compare RAG output against authoritative SOP documents.

**For QP Release Dossier:** Validate with real batch data: generate a Release Dossier, then manually verify every attestation claim against the underlying audit trail entries. A single false attestation = validation failure. Conduct with 10 representative batches during PQ.

**For Inspector Mode:** Conduct a mock inspection with an external GMP consultant who has EU inspector experience. Measure time-to-answer for all three standard questions. Target: all three answered in under 5 minutes without IT assistance.

**For Transparent Automation:** Usability testing with 3-5 actual QC analysts from the facility. Observe whether they correctly identify what actions the system performed automatically vs. what they performed. Target: 100% of automated actions correctly identified by analysts without prompting.

### Risk Mitigation

| Innovation | Risk | Mitigation |
|-----------|------|-----------|
| Compliance-as-Infrastructure | If hash chain algorithm changes or WORM storage format becomes obsolete | Annual format migration testing with integrity verification; two independent checksum stores |
| RAG-Augmented SOP Guidance | Hallucinated guidance leads to incorrect SOP compliance | Advisory-only policy + mandatory citation verification + quarterly accuracy audits + confidence scoring |
| QP Release Dossier | False attestation (system claims check passed but it didn't) | Every attestation claim is programmatically derived from audit trail, not manually authored; automated verification run pre-release |
| Inspector Mode | Inspector finds pre-packaged views insufficient or misleading | All views have drill-down to raw data; Auditor role can access full audit trail; system does not restrict what inspector can see |
| Transparent Automation | Users develop automation blindness and miss indicators | Progressive disclosure design; automation actions are displayed before results are accepted; confirmation required for any automated action with compliance impact |

## Web Application Specific Requirements

### Project-Type Overview

QC_LIMS is a **desktop-first responsive Single Page Application (SPA)** built with React (TypeScript) and Vite, deployed to a local Docker host accessible via the facility's internal network. It is not a public-facing SaaS product — it serves a single facility (Purely Plant GmbH) with internal users (analysts, reviewers, managers, QP) and occasional external auditors (inspectors). There is no mobile app component; tablet access is supported for cleanroom environments where desktop workstations are impractical.

### Technical Architecture Considerations

**SPA Architecture:**
- **Framework:** React 18+ with TypeScript, Vite for build tooling
- **Routing:** React Router v6 for client-side routing with role-based route guards
- **State Management:** React Query (TanStack Query) for server state (API data caching, background refetch, optimistic updates for audit trail events)
- **Backend:** FastAPI (Python 3.12) with three-layer architecture (Controller → Service → Repository)
- **API Communication:** RESTful JSON over HTTPS, with WebSocket support for real-time audit event streaming and dashboard updates
- **Authentication:** JWT (access + refresh tokens) with HttpOnly refresh cookies; MFA via TOTP for release/approve actions

**Browser Support:**

| Browser | Minimum Version | Notes |
|---------|----------------|-------|
| Google Chrome | 90+ | Primary development target. Full WebSocket support. |
| Microsoft Edge | 90+ | Chromium-based, feature parity with Chrome. |
| Mozilla Firefox | 88+ | Secondary target. Tested for parity but not primary dev browser. |
| Safari | N/A | Not required — facility does not use macOS. |
| Mobile Browsers | N/A | No mobile use case. Tablet cleanroom access via Chrome on managed Android tablets. |

**Responsive Design:**
- **Primary Viewport:** Desktop 1280px+ (laboratory workstations and office computers)
- **Secondary Viewport:** Tablet 768-1024px (cleanroom-appropriate sealed tablets for sample scanning and result viewing in Grade C/D areas)
- **Breakpoints:** 768px (tablet), 1024px (small desktop), 1280px (standard desktop), 1440px+ (wide)
- **Approach:** Desktop-optimized layouts that gracefully collapse to tablet; no mobile (<768px) optimization needed. Data entry grids (50+ parameters per batch) are the dominant UI pattern and require full desktop real estate.
- **Input Methods:** Keyboard-first design (Tab navigation, Enter to confirm, Escape to cancel, F-keys for common actions). Mouse for review and dashboard navigation. Barcode scanner as keyboard emulation (USB HID). No touch-optimized interactions required for tablet use — stylus or keyboard cover acceptable.

**Performance Targets:**

| Operation | Target | Rationale |
|-----------|--------|----------|
| Initial page load (SPA bootstrap) | <3 seconds | Acceptable for lab workstation; not consumer-facing |
| Route transition (client-side) | <200ms | Analyst flows between sample entry and COA review fluidly |
| Data entry grid render (60+ cells) | <500ms | Keyboard navigation must feel instant; no cell render lag |
| API response (sample context load) | <2 seconds | Barcode scan → full context (specs, calibrations, reviewer, SOP references) |
| API response (COA PDF generation) | <15 seconds | python-docx → Gotenberg pipeline; acceptable for a deliberate action |
| RAG guidance query | <5 seconds p95 | Letta API + Qdrant retrieval + LLM response |
| Audit trail search (10 years) | <5 seconds | Indexed PostgreSQL with pg_trgm for text search |
| Dashboard metrics load | <3 seconds | Aggregated queries with Redis caching layer |
| Audit event streaming (WebSocket) | <1 second latency | Real-time for compliance-critical actions |

**SEO Strategy:**
- **Not applicable.** QC_LIMS is an internal laboratory system deployed on a local network, not a public-facing website. No SEO considerations are required. No public URLs, no sitemaps, no meta tags for search engines. The application is accessed via internal IP or hostname behind the facility's firewall.

**Accessibility Level:**
- **Target:** WCAG 2.1 Level AA compliance
- **Rationale:** As a GMP-regulated system, accessibility is both a regulatory expectation (EU Directive 2016/2102 on accessibility of public sector bodies, applied as best practice) and a practical requirement — QC analysts may have varying visual acuity, motor control, or color vision. Additionally, inspectors may have accessibility needs during audits.
- **Specific Requirements:**
  - **Keyboard Navigation:** All interactive elements must be reachable and operable via keyboard alone (Tab, Enter, Escape, arrow keys). This aligns with the scan-first, keyboard-first design principle. No mouse-dependent interactions.
  - **Color Contrast:** All text meets WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text). Validation pass/fail indicators use both color (green/amber/red) AND shape/icon/text (✓ / ⚠ / ✗) — not color alone.
  - **Screen Reader Support:** All form fields, data tables, alerts, and navigation elements include appropriate ARIA labels and roles. Dynamic content updates (WebSocket audit events, status changes) are announced via ARIA live regions.
  - **Focus Management:** Visible focus indicators on all interactive elements. Focus is managed programmatically after modal opens, wizard step transitions, and page navigation.
  - **Form Validation:** Error messages are associated with their input fields via `aria-describedby`. Validation occurs on blur and on submit — errors are announced to screen readers.
  - **Data Tables:** All data entry grids and result tables include proper `<th>` scope attributes, captions, and row/column headers for screen reader navigation.
  - **Time Limits:** The inactivity timeout (15 minutes) provides a 2-minute warning with the option to extend. This is WCAG 2.1 SC 2.2.1 compliant (Adjustable Time). No other time-pressure elements exist per the no-time-pressure UX principle.
  - **Language:** The `<html lang>` attribute reflects the user's language preference (mk or en) and is set at login. Individual content blocks may receive `lang` attributes when displaying bilingual content (e.g., MK SOP text in an EN interface).

### Implementation Considerations

**Development Approach:**
- Brownfield project — extend existing backend scaffold (FastAPI models in `backend/app/models/`, API routes in `backend/app/api/`, core infrastructure in `backend/app/core/`). Do not rewrite.
- Frontend is greenfield — React + TypeScript + Vite project created within the monorepo structure. Component library: Tailwind CSS + Headless UI for accessible primitives.

**Build & Deployment:**
- Docker Compose multi-service deployment (API, Worker, Frontend, PostgreSQL, Redis)
- CI/CD via GitHub Actions: lint → test → build → deploy to Docker host
- Environment configuration via `.env` files with documented variables; no hardcoded secrets

**Testing Strategy:**
- **Unit Tests:** Pytest for backend services and models; Vitest for React components and hooks
- **Integration Tests:** Pytest + httpx for API endpoints against test database; Playwright for critical frontend flows (login, sample entry, COA generation, OOS wizard)
- **Validation Tests:** Automated post-deployment validation suite — creates test sample, enters results, generates COA, verifies audit chain hash — runs as part of CI/CD pipeline
- **Accessibility Tests:** axe-core automated checks in Playwright; manual testing with screen reader (NVDA) during UAT

**Compliance with Project Type Best Practices:**
- SPA routing preserves browser history for back/forward navigation — each step in a wizard (OOS Phase I, COA review) is a distinct route
- JWT token refresh is transparent to the user — no interruption during active data entry
- WebSocket connections auto-reconnect with exponential backoff; audit events are queued locally during disconnection and flushed on reconnect
- All API responses include CORS headers restricted to the known internal origin; no public CORS wildcard

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — reduce compliance friction for the most painful workflow (COA generation and batch release). The system must prove that compliance-as-infrastructure works end-to-end before adding more modules.

**Resource Requirements:** 1-2 full-stack developers, 1 GMP QA consultant (part-time validation), QP access for workflow validation and signature testing.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Blagoj (Analyst — Success Path): Sample registration, result entry, OOS detection, RAG guidance
- Sofija (Reviewer — Throughput): Exception-based review, bulk approval, deviation investigation
- Dr. Petrova (QP — Release): COA review, electronic signature, batch release
- Inspector (Auditor — Compliance): Audit trail search, PDF/A export (basic inspector access)
- Ljupcho (Admin — Ops): Deploy, health checks, backup

**Must-Have Capabilities:**

1. **Sample Management + Chain of Custody** (QCSOP 011) — barcode/QR label printing, sample registration, lifecycle tracking, chain of custody logging
2. **Specification Management** (QCSOP 010) — spec creation, versioning, approval workflow, parameter limits with Ph. Eur. references
3. **COA Generation** (QCSOP 012, QCCoA 001) — auto-comparison of results against specs, 2nd person verification, PDF generation, electronic signature
4. **Audit Trail Infrastructure** — cryptographic hash-chain audit logging as a foundational layer (not a module), WORM storage, immutable record of all GxP actions
5. **User Management + Authentication** (QCSOP 001) — role-based access, MFA, inactivity timeout, account lockout
6. **OOS Investigation** (QCSOP 019 + Appendices A01-A04) — Phase I/Phase II wizard, root cause guidance (RAG), investigation form generation, OOS register

**MVP Compliance Minimums:**
- Audit trail satisfies all ALCOA++ principles and 21 CFR Part 11 §11.10
- Electronic signatures satisfy §11.100 and §11.200
- Bilingual (MK/EN) for all labels, COAs, and SOP references
- Basic Inspector Mode with pre-packaged compliance views (Validation Master Plan summary, Audit Trail Integrity Proof, Software Update History)

**Success Gates:**
- First batch released electronically with QP signature
- Audit trail integrity verification passes automated hash chain walk test
- Passes internal QA audit of Annex 11 compliance
- RAG guidance accuracy ≥95% on known-answer test set

### Post-MVP Features

**Phase 2 — Growth (Complete QC Workflows):**

7. **Stability Studies** (QCSOP 018) — automated pull schedules, chamber monitoring, trending charts, ICH Q1A/Q1B compliance
8. **Water System QC** (QCSOP 014 — pending upload) — sampling point management, conductivity/TOC/microbial trending, alert/action limit exceedance alerting
9. **Microbiological Monitoring** (QCSOP 023, QCSOP 024) — environmental monitoring schedules, settle plates/contact plates, organism identification, grade classification (A/B/C/D)
10. **Cannabinoid Testing Module** (QCSOP 016 — pending upload) — HPLC/GC data capture, moisture-adjusted calculations, Ph. Eur. 2.08.10 profile
11. **Risk Telemetry Dashboard** — real-time metrics for QC Manager (OOS cycle time, analyst error rates, calibration status, stability pull schedule)
12. **QP Release Dossier** — one-page auto-generated compliance attestation summarizing all checks per batch
13. **Inspector Mode (Full)** — pre-packaged compliance views with comprehensive drill-down, mock inspection validation

**Success Gates:**
- Full QC lab coverage (all Ph. Eur. methods with spec limits)
- Manager risk dashboard providing real-time lab health metrics
- Inspector Mode validated in mock EU GMP inspection
- 100% of batches tracked end-to-end in LIMS (no parallel paper system)

**Phase 3 — Vision (Intelligent LIMS):**

14. **AI QMS Orchestration** (Letta agent ensemble) — QMS Orchestrator routes user queries to specialist agents; CAPA Manager auto-suggests root causes and corrective actions from historical patterns
15. **Predictive Quality Analytics** — machine learning on historical data to predict: OOS likelihood per batch, stability failure risk, seasonal microbial trends
16. **Instrument Integration** — direct data capture from HPLC, GC, balances, pH meters (LIMS → instrument bridge)
17. **Multi-Site Deployment** — centralized deployment serving multiple Purely Plant facilities with site-specific SOP collections
18. **Regulatory Submission Package Generator** — auto-generate CTD Module 3 quality sections for regulatory submissions

**Success Gates:**
- AI-powered root cause analysis reduces OOS investigation cycle time by 60%
- Predictive stability failure alerts prevent batch losses
- Paperless regulatory submissions for at least one product registration

### Risk-Based Scoping

**Technical Risks:**
- **Audit trail immutability implementation buggy:** Mitigated by fully automated hash chain verification test in CI/CD pipeline; quarterly manual verification with independent tool
- **Electronic signature compliance with Part 11 §11.200:** Mitigated by two-component auth via standard TOTP library (no custom crypto); signature block format reviewed by GMP consultant before go-live
- **RAG hallucination undermines trust:** Mitigated by advisory-only policy + mandatory citation verification + quarterly accuracy audits + confidence scoring; system degrades gracefully to manual SOP lookup if RAG unavailable

**Market Risks:**
- **Inspector unfamiliarity leads to rejection:** Mitigated by pre-packaged Inspector Mode with three mandatory compliance views; mock inspection with external GMP consultant before go-live; all views exportable as PDF/A for inspection evidence

**Resource Risks:**
- **Only one developer available:** Mitigated by strict MVP scope lock (6 modules only); no Phase 2 work until MVP validated and released; brownfield approach leverages existing backend scaffold to reduce greenfield work
- **Missing SOP documents delay Water/Micro modules (QCSOP 014, QCSOP 016):** Mitigated by gating Phase 2 modules on document upload; proceed with data model design but postpone full UI until documents available; Phase 1 modules not dependent on missing SOPs

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — reduce compliance friction for the most painful QC workflow: COA generation and batch release. The system must prove that compliance-as-infrastructure works end-to-end before adding more modules.

**Resource Requirements:** 1-2 full-stack developers, 1 GMP QA consultant (part-time validation), QP access for workflow validation and signature testing.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Blagoj (Analyst — Success Path): Sample registration, result entry, OOS detection, RAG guidance
- Sofija (Reviewer — Throughput): Exception-based review, bulk approval, deviation investigation
- Dr. Petrova (QP — Release): COA review, electronic signature, batch release
- Inspector (Auditor — Compliance): Audit trail search, PDF/A export (basic inspector access)
- Ljupcho (Admin — Ops): Deploy, health checks, backup

**Must-Have Capabilities:**

| Module | SOP Basis | Key Features |
|--------|-----------|-------------|
| Sample Management + Chain of Custody | QCSOP 011 | Barcode/QR label printing, sample registration, lifecycle tracking, chain of custody logging |
| Specification Management | QCSOP 010 | Spec creation, versioning, approval workflow, parameter limits with Ph. Eur. references |
| COA Generation | QCSOP 012, QCCoA 001 | Auto-comparison of results against specs, 2nd person verification, PDF generation, electronic signature |
| Audit Trail Infrastructure | Annex 11, 21 CFR Part 11 | Cryptographic hash-chain audit logging as foundational WORM layer, immutable record of all GxP actions |
| User Management + Authentication | QCSOP 001 | Role-based access, MFA for release/approve, inactivity timeout, account lockout, 6 roles |
| OOS Investigation | QCSOP 019 + Appendices A01-A04 | Phase I/Phase II wizard, root cause guidance (RAG), investigation form generation, OOS register |

**MVP Compliance Minimums:**
- Audit trail satisfies all ALCOA++ principles and 21 CFR Part 11 §11.10
- Electronic signatures satisfy §11.100 and §11.200
- Bilingual (MK/EN) for all labels, COAs, and SOP references
- Basic Inspector Mode with pre-packaged compliance views (Validation Master Plan summary, Audit Trail Integrity Proof, Software Update History)
- Automated hash chain verification test in CI/CD pipeline

**Success Gates:**
- First batch released electronically with QP signature
- Audit trail integrity verification passes automated hash chain walk test
- Passes internal QA audit of Annex 11 compliance
- RAG guidance accuracy ≥95% on known-answer test set

### Post-MVP Features

**Phase 2 — Growth (Complete QC Workflows):**

| Module | SOP Basis | Key Features |
|--------|-----------|-------------|
| Stability Studies | QCSOP 018 | Automated pull schedules, chamber monitoring, trending charts, ICH Q1A/Q1B compliance |
| Water System QC | QCSOP 014 (pending) | Sampling point management, conductivity/TOC/microbial trending, alert/action limit exceedance alerting |
| Microbiological Monitoring | QCSOP 023, QCSOP 024 | Environmental monitoring schedules (air/surface/personnel), grade classification (A/B/C/D), organism ID |
| Cannabinoid Testing Module | QCSOP 016 (pending), Ph. Eur. 2.08.10 | HPLC/GC data capture, moisture-adjusted calculations, profile quantification |
| Risk Telemetry Dashboard | — | Real-time metrics: OOS cycle time, analyst error rates, calibration status, stability pull schedule |
| QP Release Dossier | — | One-page auto-generated compliance attestation summarizing all checks per batch |
| Inspector Mode (Full) | — | Pre-packaged compliance views with comprehensive drill-down, mock inspection validated |

**Success Gates:**
- Full QC lab coverage (all Ph. Eur. methods with spec limits)
- Manager risk dashboard providing real-time lab health metrics
- Inspector Mode validated in mock EU GMP inspection
- 100% of batches tracked end-to-end in LIMS (no parallel paper system)

**Phase 3 — Vision (Intelligent LIMS):**

| Module | Description |
|--------|-------------|
| AI QMS Orchestration | Letta agent ensemble: QMS Orchestrator routes user queries to specialist agents; CAPA Manager auto-suggests root causes and corrective actions from historical patterns |
| Predictive Quality Analytics | ML on historical data: OOS likelihood per batch, stability failure risk, seasonal microbial trends |
| Instrument Integration | Direct data capture from HPLC, GC, balances, pH meters (LIMS → instrument bridge) |
| Multi-Site Deployment | Centralized deployment serving multiple facilities with site-specific SOP collections |
| Regulatory Submission Package Generator | Auto-generate CTD Module 3 quality sections for submissions |

**Success Gates:**
- AI-powered root cause analysis reduces OOS investigation cycle time by 60%
- Predictive stability failure alerts prevent batch losses
- Paperless regulatory submissions for at least one product registration

### Risk-Based Scoping

**Technical Risks:**
- **Audit trail immutability implementation buggy:** Mitigated by fully automated hash chain verification test in CI/CD; quarterly manual verification with independent tool
- **Electronic signature compliance with Part 11 §11.200:** Mitigated by two-component auth via standard TOTP library (no custom crypto); signature block format reviewed by GMP consultant before go-live
- **RAG hallucination undermines trust:** Mitigated by advisory-only policy + mandatory citation verification + quarterly accuracy audits + confidence scoring; system degrades gracefully to manual SOP lookup if RAG unavailable

**Market Risks:**
- **Inspector unfamiliarity leads to rejection:** Mitigated by pre-packaged Inspector Mode with three mandatory compliance views; mock inspection with external GMP consultant before go-live; all views exportable as PDF/A for inspection evidence

**Resource Risks:**
- **Single developer:** Mitigated by strict MVP scope lock (6 modules only); no Phase 2 work until MVP validated; brownfield approach leverages existing backend scaffold to reduce greenfield work
- **Missing SOP documents (QCSOP 014, QCSOP 016):** Mitigated by gating Phase 2 modules on document upload; proceed with data model design but postpone full UI until documents available; Phase 1 modules not dependent on missing SOPs

## Functional Requirements

### Sample Management & Chain of Custody

- **FR1:** Analysts can register a new sample by scanning a barcode, which auto-populates the sample record with batch ID, material code, and specification references.
- **FR2:** Analysts can register samples manually when barcode is unavailable, entering batch ID, material code, sample type, and sampling date.
- **FR3:** The system generates a unique sample identifier (PP-SMP-YYYY-NNNN) at registration and renders a printable barcode/QR label.
- **FR4:** The system tracks sample lifecycle status through defined states: COLLECTED → IN_TEST → TESTED → APPROVED/REJECTED (or OOS → INVESTIGATING → CLOSED).
- **FR5:** The system logs every transfer of sample custody (analyst-to-analyst, analyst-to-storage) with timestamp and electronic signatures of both parties.
- **FR6:** Analysts can view a sample's complete lifecycle timeline showing all status transitions with timestamps and responsible users.
- **FR7:** The system supports sample types: RAW_MATERIAL, IPC, FINISHED_PRODUCT, STABILITY, WATER, ENVIRONMENTAL.
- **FR8:** Analysts can flag a sample as a retention sample with an expiry date, and the system alerts when retention period ends.

### Specification Management

- **FR9:** QC Managers can create new specifications for any material type (raw, finished, packaging, IPC) with versioning support.
- **FR10:** The system supports specification parameters with numeric bounded limits (lower/upper), numeric max/min, categorical values, and text specifications.
- **FR11:** Each specification parameter references a test method and pharmacopoeia monograph (e.g., Ph. Eur. 2.08.10).
- **FR12:** The system enforces an approval workflow for specifications: DRAFT → REVIEWED → APPROVED → ACTIVE, requiring electronic signatures at each transition.
- **FR13:** When a new specification version is approved, the previous version is automatically marked SUPERSEDED and remains immutable.
- **FR14:** Any result entered against a sample references the specification version active at the time of result entry, preserved immutably for COA traceability.
- **FR15:** QC Managers can view the full version history of any specification with change reasons and approver details.

### Certificate of Analysis (COA) Generation

- **FR16:** Analysts can enter test results for all parameters defined in the active specification, with the system auto-validating each result against spec limits in real-time.
- **FR17:** The system auto-calculates compliance (pass/fail) for each result based on the specification active at entry time and displays visual indicators (pass/amber-warning/fail).
- **FR18:** The system requires 2nd person verification of all analytical results before a COA can be generated — the reviewer must provide an electronic signature.
- **FR19:** The system generates a bilingual (MK/EN) COA PDF document following the QCCoA 001 template format, including product/batch information, test parameters table with specification and compliance columns, decision statement, and signature blocks.
- **FR20:** The COA PDF is generated in PDF/A-3 format for long-term archival compliance.
- **FR21:** The system assigns a unique COA number (PP-COA-YYYY-NNNN) and prevents duplicate COA generation for the same sample without a justification reason.
- **FR22:** The Qualified Person (QP) can review and approve a COA for batch release with a two-component electronic signature (password + TOTP token).
- **FR23:** Once a COA is approved, the COA PDF, all underlying results, and the approval signature are locked — no modifications are possible without creating a new revision with full audit trail.
- **FR24:** Any user can export an approved COA as PDF/A with a single action.

### Audit Trail & Data Integrity

- **FR25:** The system automatically logs every CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, and PRINT action on any GxP-relevant record with: timestamp, user identity, action type, record identifier, field name (if applicable), old value, new value, IP address, and session ID.
- **FR26:** The audit trail storage is WORM (Write Once Read Many) — no user role, including System Administrator, has write or delete permissions on the audit storage tier.
- **FR27:** Each audit entry is cryptographically linked to the previous entry via SHA-256 hash chaining, enabling automated integrity verification.
- **FR28:** An authorized auditor can run an automated hash chain integrity verification for any batch or time range and receive a pass/fail result with the full verification report.
- **FR29:** Auditors with the dedicated read-only Auditor role can search the audit trail by date range, user, record type, action, and record identifier.
- **FR30:** Every corrected result creates a supersession record (new entry linking to the original) — the original raw data is never overwritten or deleted.
- **FR31:** The system records a reason for any modification to a result or specification, and this reason is visible in the audit trail.

### User Management & Authentication

- **FR32:** The System Admin can create, disable, and manage user accounts with assigned roles: Analyst, Reviewer, QC Manager, QP, Auditor, System Admin.
- **FR33:** The system enforces password complexity (≥8 chars, mixed case, digit, special character) and a 90-day password expiry with forced rotation.
- **FR34:** Users performing release, approval, or rejection actions must authenticate with two factors: password plus time-based one-time password (TOTP).
- **FR35:** The system automatically locks an account after 5 consecutive failed authentication attempts and logs the lockout event in the audit trail.
- **FR36:** The system enforces an inactivity timeout of 15 minutes, providing a 2-minute countdown warning with the option to extend the session.
- **FR37:** Each role has precisely defined, non-overlapping permissions — no shared accounts are permitted, and the system prevents concurrent sessions for the same user.
- **FR38:** The Auditor role has read-only access to all GxP records and audit trail; this role cannot create, modify, or delete any record.

### OOS Investigation

- **FR39:** When a test result exceeds specification limits, the system immediately flags it as OOS, highlights it in red, and prompts the analyst to open the Phase I investigation wizard.
- **FR40:** The Phase I investigation wizard presents a structured checklist of possible laboratory errors (extraction error, dilution error, equipment malfunction, standard degradation, calculation error) for the analyst to evaluate.
- **FR41:** If an assignable laboratory error is identified and documented in Phase I, the system allows the analyst to invalidate the OOS result and log a retest result, with full documentation of the error.
- **FR42:** If no laboratory error is identified in Phase I, the system transitions the OOS to Phase II and triggers a notification to the QC Manager.
- **FR43:** The Phase II investigation wizard guides the investigator through root cause analysis (Fishbone categories or 5-Whys), impact assessment on other batches, and CAPA definition.
- **FR44:** The system auto-generates OOS investigation forms (QCSOP 019-A01 for internal, QCSOP 019-A02 for external) pre-populated with result data, spec limits, analyst identity, and timestamp.
- **FR45:** Every OOS event is automatically logged to the OOS Register (QCSOP 019-A03) with a unique OOS number (PP-OOS-YYYY-NNNN) and real-time status tracking.
- **FR46:** The system sends automated notifications for OOS events: immediate notification to QC Manager upon detection, and escalation notification if Phase I is not completed within 1 working day.
- **FR47:** QC Managers can view an OOS dashboard showing: open OOS events, overdue investigations, Phase I vs Phase II status, and closure rates by analyst.

### RAG Guidance & AI Assistance

- **FR48:** Analysts can ask natural-language questions about SOP procedures from within any data entry or investigation screen and receive a cited response in under 5 seconds.
- **FR49:** Every RAG response includes a source citation with document number, section reference, and a one-click "Verify Citation" button that opens the original SOP at the relevant paragraph.
- **FR50:** The RAG guidance is advisory-only — the analyst must confirm understanding before proceeding; the system never auto-executes an action based on RAG output.
- **FR51:** If the Letta RAG service is unavailable, the system degrades gracefully to manual SOP lookup with a visible warning indicator and still allows all data entry and review workflows to proceed.
- **FR52:** The system supports bilingual RAG queries (MK and EN) and returns responses in the query language with bilingual source citations as available.

### Review & Approval Workflows

- **FR53:** Reviewers can view an exception-based review dashboard showing only COAs with deviations or OOS events, with the ability to bulk-approve passing COAs in a single action.
- **FR54:** Reviewers can drill into any result to see its full data lineage: who entered it, when, whether it was amended, and why.
- **FR55:** Reviewers can compare results side-by-side across multiple samples from the same batch to detect patterns or anomalies.
- **FR56:** The QP can generate a Release Dossier for any batch — a single-page summary listing: specification version, COA parameter completeness, result compliance, 2nd person verification status, OOS events (with invalidation status), audit trail integrity, calibration status at time of testing, and personnel training status.
- **FR57:** Every approval, rejection, or release action requires a two-component electronic signature and is immutably logged in the audit trail with the printed name, date/time, and meaning of the signature.

### Compliance Demonstration (Inspector Mode)

- **FR58:** An Auditor can access Inspector Mode — a set of pre-packaged views including: Validation Master Plan summary, Audit Trail Integrity Proof (with real-time hash chain verification), and Software Update History (with change control links).
- **FR59:** Every view in Inspector Mode is exportable as PDF/A for use as inspection evidence.
- **FR60:** The Audit Trail Integrity Proof performs a live hash chain walk for a selected batch or time range and displays cryptographic verification results.

### System Administration & Operations

- **FR61:** The System Admin can deploy software updates via Docker Compose with automated database migrations and post-deployment health checks.
- **FR62:** The system provides health-check endpoints for all services (API, database, Letta bridge, Qdrant) and exposes structured JSON logs for monitoring.
- **FR63:** The System Admin can configure automated daily incremental backups and weekly full backups with point-in-time recovery capability.
- **FR64:** The system runs an automated post-deployment validation suite that creates a test sample, enters results, generates a COA, verifies the audit trail hash chain, and reports pass/fail.
- **FR65:** The system logs every deployment (version, timestamp, migrations executed, validation result) immutably in a deployment log visible in Inspector Mode.

## Functional Requirements

### Sample Management & Chain of Custody

- **FR1:** Analysts can register a new sample by scanning a barcode, which auto-populates the sample record with batch ID, material code, and specification references.
- **FR2:** Analysts can register samples manually when barcode is unavailable, entering batch ID, material code, sample type, and sampling date.
- **FR3:** The system generates a unique sample identifier (PP-SMP-YYYY-NNNN) at registration and renders a printable barcode/QR label.
- **FR4:** The system tracks sample lifecycle status through defined states: COLLECTED → IN_TEST → TESTED → APPROVED/REJECTED (or OOS → INVESTIGATING → CLOSED).
- **FR5:** The system logs every transfer of sample custody (analyst-to-analyst, analyst-to-storage) with timestamp and electronic signatures of both parties.
- **FR6:** Analysts can view a sample's complete lifecycle timeline showing all status transitions with timestamps and responsible users.
- **FR7:** The system supports sample types: RAW_MATERIAL, IPC, FINISHED_PRODUCT, STABILITY, WATER, ENVIRONMENTAL.
- **FR8:** Analysts can flag a sample as a retention sample with an expiry date, and the system alerts when retention period ends.

### Specification Management

- **FR9:** QC Managers can create new specifications for any material type (raw, finished, packaging, IPC) with versioning support.
- **FR10:** The system supports specification parameters with numeric bounded limits (lower/upper), numeric max/min, categorical values, and text specifications.
- **FR11:** Each specification parameter references a test method and pharmacopoeia monograph (e.g., Ph. Eur. 2.08.10).
- **FR12:** The system enforces an approval workflow for specifications: DRAFT → REVIEWED → APPROVED → ACTIVE, requiring electronic signatures at each transition.
- **FR13:** When a new specification version is approved, the previous version is automatically marked SUPERSEDED and remains immutable.
- **FR14:** Any result entered against a sample references the specification version active at the time of result entry, preserved immutably for COA traceability.
- **FR15:** QC Managers can view the full version history of any specification with change reasons and approver details.

### Certificate of Analysis (COA) Generation

- **FR16:** Analysts can enter test results for all parameters defined in the active specification, with the system auto-validating each result against spec limits in real-time.
- **FR17:** The system auto-calculates compliance (pass/fail) for each result based on the specification active at entry time and displays visual indicators (pass/amber-warning/fail).
- **FR18:** The system requires 2nd person verification of all analytical results before a COA can be generated — the reviewer must provide an electronic signature.
- **FR19:** The system generates a bilingual (MK/EN) COA PDF document following the QCCoA 001 template format, including product/batch information, test parameters table with specification and compliance columns, decision statement, and signature blocks.
- **FR20:** The COA PDF is generated in PDF/A-3 format for long-term archival compliance.
- **FR21:** The system assigns a unique COA number (PP-COA-YYYY-NNNN) and prevents duplicate COA generation for the same sample without a justification reason.
- **FR22:** The Qualified Person (QP) can review and approve a COA for batch release with a two-component electronic signature (password + TOTP token).
- **FR23:** Once a COA is approved, the COA PDF, all underlying results, and the approval signature are locked — no modifications are possible without creating a new revision with full audit trail.
- **FR24:** Any user can export an approved COA as PDF/A with a single action.

### Audit Trail & Data Integrity

- **FR25:** The system automatically logs every CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, and PRINT action on any GxP-relevant record with: timestamp, user identity, action type, record identifier, field name (if applicable), old value, new value, IP address, and session ID.
- **FR26:** The audit trail storage is WORM (Write Once Read Many) — no user role, including System Administrator, has write or delete permissions on the audit storage tier.
- **FR27:** Each audit entry is cryptographically linked to the previous entry via SHA-256 hash chaining, enabling automated integrity verification.
- **FR28:** An authorized auditor can run an automated hash chain integrity verification for any batch or time range and receive a pass/fail result with the full verification report.
- **FR29:** Auditors with the dedicated read-only Auditor role can search the audit trail by date range, user, record type, action, and record identifier.
- **FR30:** Every corrected result creates a supersession record (new entry linking to the original) — the original raw data is never overwritten or deleted.
- **FR31:** The system records a reason for any modification to a result or specification, and this reason is visible in the audit trail.

### User Management & Authentication

- **FR32:** The System Admin can create, disable, and manage user accounts with assigned roles: Analyst, Reviewer, QC Manager, QP, Auditor, System Admin.
- **FR33:** The system enforces password complexity (≥8 chars, mixed case, digit, special character) and a 90-day password expiry with forced rotation.
- **FR34:** Users performing release, approval, or rejection actions must authenticate with two factors: password plus time-based one-time password (TOTP).
- **FR35:** The system automatically locks an account after 5 consecutive failed authentication attempts and logs the lockout event in the audit trail.
- **FR36:** The system enforces an inactivity timeout of 15 minutes, providing a 2-minute countdown warning with the option to extend the session.
- **FR37:** Each role has precisely defined, non-overlapping permissions — no shared accounts are permitted, and the system prevents concurrent sessions for the same user.
- **FR38:** The Auditor role has read-only access to all GxP records and audit trail; this role cannot create, modify, or delete any record.

### OOS Investigation

- **FR39:** When a test result exceeds specification limits, the system immediately flags it as OOS, highlights it in red, and prompts the analyst to open the Phase I investigation wizard.
- **FR40:** The Phase I investigation wizard presents a structured checklist of possible laboratory errors (extraction error, dilution error, equipment malfunction, standard degradation, calculation error) for the analyst to evaluate.
- **FR41:** If an assignable laboratory error is identified and documented in Phase I, the system allows the analyst to invalidate the OOS result and log a retest result, with full documentation of the error.
- **FR42:** If no laboratory error is identified in Phase I, the system transitions the OOS to Phase II and triggers a notification to the QC Manager.
- **FR43:** The Phase II investigation wizard guides the investigator through root cause analysis (Fishbone categories or 5-Whys), impact assessment on other batches, and CAPA definition.
- **FR44:** The system auto-generates OOS investigation forms (QCSOP 019-A01 for internal, QCSOP 019-A02 for external) pre-populated with result data, spec limits, analyst identity, and timestamp.
- **FR45:** Every OOS event is automatically logged to the OOS Register (QCSOP 019-A03) with a unique OOS number (PP-OOS-YYYY-NNNN) and real-time status tracking.
- **FR46:** The system sends automated notifications for OOS events: immediate notification to QC Manager upon detection, and escalation notification if Phase I is not completed within 1 working day.
- **FR47:** QC Managers can view an OOS dashboard showing: open OOS events, overdue investigations, Phase I vs Phase II status, and closure rates by analyst.

### RAG Guidance & AI Assistance

- **FR48:** Analysts can ask natural-language questions about SOP procedures from within any data entry or investigation screen and receive a cited response in under 5 seconds.
- **FR49:** Every RAG response includes a source citation with document number, section reference, and a one-click "Verify Citation" button that opens the original SOP at the relevant paragraph.
- **FR50:** The RAG guidance is advisory-only — the analyst must confirm understanding before proceeding; the system never auto-executes an action based on RAG output.
- **FR51:** If the Letta RAG service is unavailable, the system degrades gracefully to manual SOP lookup with a visible warning indicator and still allows all data entry and review workflows to proceed.
- **FR52:** The system supports bilingual RAG queries (MK and EN) and returns responses in the query language with bilingual source citations as available.

### Review & Approval Workflows

- **FR53:** Reviewers can view an exception-based review dashboard showing only COAs with deviations or OOS events, with the ability to bulk-approve passing COAs in a single action.
- **FR54:** Reviewers can drill into any result to see its full data lineage: who entered it, when, whether it was amended, and why.
- **FR55:** Reviewers can compare results side-by-side across multiple samples from the same batch to detect patterns or anomalies.
- **FR56:** The QP can generate a Release Dossier for any batch — a single-page summary listing: specification version, COA parameter completeness, result compliance, 2nd person verification status, OOS events (with invalidation status), audit trail integrity, calibration status at time of testing, and personnel training status.
- **FR57:** Every approval, rejection, or release action requires a two-component electronic signature and is immutably logged in the audit trail with the printed name, date/time, and meaning of the signature.

### Compliance Demonstration (Inspector Mode)

- **FR58:** An Auditor can access Inspector Mode — a set of pre-packaged views including: Validation Master Plan summary, Audit Trail Integrity Proof (with real-time hash chain verification), and Software Update History (with change control links).
- **FR59:** Every view in Inspector Mode is exportable as PDF/A for use as inspection evidence.
- **FR60:** The Audit Trail Integrity Proof performs a live hash chain walk for a selected batch or time range and displays cryptographic verification results.

### System Administration & Operations

- **FR61:** The System Admin can deploy software updates via Docker Compose with automated database migrations and post-deployment health checks.
- **FR62:** The system provides health-check endpoints for all services (API, database, Letta bridge, Qdrant) and exposes structured JSON logs for monitoring.
- **FR63:** The System Admin can configure automated daily incremental backups and weekly full backups with point-in-time recovery capability.
- **FR64:** The system runs an automated post-deployment validation suite that creates a test sample, enters results, generates a COA, verifies the audit trail hash chain, and reports pass/fail.
- **FR65:** The system logs every deployment (version, timestamp, migrations executed, validation result) immutably in a deployment log visible in Inspector Mode.

## Non-Functional Requirements

### Performance

- **NFR1:** Barcode scan to full sample context load (specifications, calibration status, reviewer) completes in ≤2 seconds.
- **NFR2:** Data entry grid (60+ cells) renders and becomes interactive in ≤500 ms.
- **NFR3:** API response for RAG guidance (question to cited answer) is ≤5 seconds at p95.
- **NFR4:** COA PDF generation (python‑docx → Gotenberg) completes in ≤15 seconds.
- **NFR5:** Audit trail search across 10 years of records returns results in ≤5 seconds.
- **NFR6:** Manager risk telemetry dashboard loads all widgets in ≤3 seconds.
- **NFR7:** WebSocket audit event streaming latency is ≤1 second.

### Security & Compliance

- **NFR8:** All data in transit is encrypted using TLS 1.3.
- **NFR9:** All audit trail entries are encrypted at rest with a separate encryption key from the application database.
- **NFR10:** User passwords must be stored using Argon2id hashing.
- **NFR11:** Two‑factor authentication (password + TOTP) is required for all release, approval, rejection, and signature actions.
- **NFR12:** Automated account lockout after 5 consecutive failed login attempts; lockout duration 30 minutes.
- **NFR13:** Inactivity timeout of 15 minutes enforced server‑side, with a 2‑minute warning and session extension option.
- **NFR14:** Role‑based access control with six non‑overlapping roles; the Auditor role has read‑only access to all GxP data.
- **NFR15:** Electronic signatures must comply with 21 CFR Part 11 §11.50 and §11.200: include printed name, timestamp, meaning, and cryptographic hash.
- **NFR16:** Audit trail storage is WORM — no role, including System Admin, can modify or delete audit records.
- **NFR17:** Audit entries are chained with SHA‑256; automated hash‑chain verification must succeed with 100% integrity on every deployment.

### Reliability & Availability

- **NFR18:** System uptime ≥ 99.5% (excluding planned maintenance).
- **NFR19:** Recovery Time Objective (RTO) ≤ 24 hours.
- **NFR20:** Recovery Point Objective (RPO) ≤ 1 hour (daily incremental backups + point‑in‑time recovery).
- **NFR21:** Backup restore is tested and documented quarterly; test results are stored in the audit trail.
- **NFR22:** Graceful degradation: if Letta RAG service is unavailable, all core workflows (data entry, COA generation, review) remain fully functional with a visible warning.

### Accessibility

- **NFR23:** The entire user interface must meet WCAG 2.1 Level AA.
- **NFR24:** All interactive elements are keyboard‑accessible (Tab, Enter, Escape, arrow keys); no mouse‑only interactions.
- **NFR25:** Color is never the sole means of conveying status — pass/fail indicators include icons and text.
- **NFR26:** All dynamic content updates (audit events, status changes) are announced to screen readers via ARIA live regions.
- **NFR27:** Forms and data tables include proper ARIA labels, `scope` attributes, and captions.

### Integration

- **NFR28:** Letta API (port 8283) integration must be stateless and support synchronous RAG queries with a timeout of 10 seconds.
- **NFR29:** Qdrant vector DB (port 6333) must accept upserts and searches for the `pp_qms_sops` collection; search latency ≤100 ms.
- **NFR30:** Gotenberg PDF conversion endpoint must accept DOCX and return PDF/A‑3 within 15 seconds.
- **NFR31:** All external service failures (Letta, Qdrant, Gotenberg) must be logged and surfaced in the health‑check dashboard; they must not cause core workflow failure.

### Maintainability & Operations

- **NFR32:** Deployment is performed via `docker compose up -d` with automated database migrations and health‑check verification in ≤10 minutes of active admin time.
- **NFR33:** All services expose a `/health` endpoint returning JSON status within 1 second.
- **NFR34:** Structured JSON logging is used by all services; log levels are configurable at runtime.
- **NFR35:** Post‑deployment validation suite (create test sample → enter results → generate COA → verify audit chain) runs automatically and reports pass/fail.
- **NFR36:** Verified rollback capability (previous version containers remain as warm standbys; rollback completes in ≤2 minutes).

### Data Retention & Archival

- **NFR37:** All GxP records, including raw instrument data and audit trail, must be retained for a minimum of 10 years.
- **NFR38:** Annual format migration testing must be performed to ensure long‑term readability (PDF/A, CSV, JSON).
- **NFR39:** Independent checksums of audit trail data are stored in a separate system and verified quarterly.

### Bilingual Support

- **NFR40:** All user‑visible labels, COA templates, specification names, and SOP references must be available in Macedonian (mk‑MK) and English (en‑GB).
- **NFR41:** Language preference is set at user login and persists across sessions; switching language does not require re‑authentication.
- **NFR42:** Bilingual content is stored as canonical keys with dual translations; both languages must be rendered correctly in PDF output.

## Non-Functional Requirements

### Performance

- **NFR1:** Barcode scan to full sample context load (specifications, calibration status, reviewer) completes in ≤2 seconds.
- **NFR2:** Data entry grid (60+ cells) renders and becomes interactive in ≤500 ms.
- **NFR3:** API response for RAG guidance (question to cited answer) is ≤5 seconds at p95.
- **NFR4:** COA PDF generation (python‑docx → Gotenberg) completes in ≤15 seconds.
- **NFR5:** Audit trail search across 10 years of records returns results in ≤5 seconds.
- **NFR6:** Manager risk telemetry dashboard loads all widgets in ≤3 seconds.
- **NFR7:** WebSocket audit event streaming latency is ≤1 second.

### Security & Compliance

- **NFR8:** All data in transit is encrypted using TLS 1.3.
- **NFR9:** All audit trail entries are encrypted at rest with a separate encryption key from the application database.
- **NFR10:** User passwords must be stored using Argon2id hashing.
- **NFR11:** Two‑factor authentication (password + TOTP) is required for all release, approval, rejection, and signature actions.
- **NFR12:** Automated account lockout after 5 consecutive failed login attempts; lockout duration 30 minutes.
- **NFR13:** Inactivity timeout of 15 minutes enforced server‑side, with a 2‑minute warning and session extension option.
- **NFR14:** Role‑based access control with six non‑overlapping roles; the Auditor role has read‑only access to all GxP data.
- **NFR15:** Electronic signatures must comply with 21 CFR Part 11 §11.50 and §11.200: include printed name, timestamp, meaning, and cryptographic hash.
- **NFR16:** Audit trail storage is WORM — no role, including System Admin, can modify or delete audit records.
- **NFR17:** Audit entries are chained with SHA‑256; automated hash‑chain verification must succeed with 100% integrity on every deployment.

### Reliability & Availability

- **NFR18:** System uptime ≥ 99.5% (excluding planned maintenance).
- **NFR19:** Recovery Time Objective (RTO) ≤ 24 hours.
- **NFR20:** Recovery Point Objective (RPO) ≤ 1 hour (daily incremental backups + point‑in‑time recovery).
- **NFR21:** Backup restore is tested and documented quarterly; test results are stored in the audit trail.
- **NFR22:** Graceful degradation: if Letta RAG service is unavailable, all core workflows (data entry, COA generation, review) remain fully functional with a visible warning.

### Accessibility

- **NFR23:** The entire user interface must meet WCAG 2.1 Level AA.
- **NFR24:** All interactive elements are keyboard‑accessible (Tab, Enter, Escape, arrow keys); no mouse‑only interactions.
- **NFR25:** Color is never the sole means of conveying status — pass/fail indicators include icons and text.
- **NFR26:** All dynamic content updates (audit events, status changes) are announced to screen readers via ARIA live regions.
- **NFR27:** Forms and data tables include proper ARIA labels, `scope` attributes, and captions.

### Integration

- **NFR28:** Letta API (port 8283) integration must be stateless and support synchronous RAG queries with a timeout of 10 seconds.
- **NFR29:** Qdrant vector DB (port 6333) must accept upserts and searches for the `pp_qms_sops` collection; search latency ≤100 ms.
- **NFR30:** Gotenberg PDF conversion endpoint must accept DOCX and return PDF/A‑3 within 15 seconds.
- **NFR31:** All external service failures (Letta, Qdrant, Gotenberg) must be logged and surfaced in the health‑check dashboard; they must not cause core workflow failure.

### Maintainability & Operations

- **NFR32:** Deployment is performed via `docker compose up -d` with automated database migrations and health‑check verification in ≤10 minutes of active admin time.
- **NFR33:** All services expose a `/health` endpoint returning JSON status within 1 second.
- **NFR34:** Structured JSON logging is used by all services; log levels are configurable at runtime.
- **NFR35:** Post‑deployment validation suite (create test sample → enter results → generate COA → verify audit chain) runs automatically and reports pass/fail.
- **NFR36:** Verified rollback capability (previous version containers remain as warm standbys; rollback completes in ≤2 minutes).

### Data Retention & Archival

- **NFR37:** All GxP records, including raw instrument data and audit trail, must be retained for a minimum of 10 years.
- **NFR38:** Annual format migration testing must be performed to ensure long‑term readability (PDF/A, CSV, JSON).
- **NFR39:** Independent checksums of audit trail data are stored in a separate system and verified quarterly.

### Bilingual Support

- **NFR40:** All user‑visible labels, COA templates, specification names, and SOP references must be available in Macedonian (mk‑MK) and English (en‑GB).
- **NFR41:** Language preference is set at user login and persists across sessions; switching language does not require re‑authentication.
- **NFR42:** Bilingual content is stored as canonical keys with dual translations; both languages must be rendered correctly in PDF output.
