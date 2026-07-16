---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - /a0/usr/projects/qc_lims/QC_LIMS_Comprehensive_Vision_and_Architecture.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/00-sop-index.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/01-gmp-compliance.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/02-letta-rag-pipeline.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/03-lims-modules.md
  - /a0/usr/projects/qc_lims/.a0proj/knowledge/main/bmad-architect/architecture-decisions.md
  - /a0/usr/projects/qc_lims/.a0proj/knowledge/main/bmad-dev/code-standards.md
  - /a0/usr/projects/qc_lims/.a0proj/knowledge/main/bmad-tech-writer/documentation-standards.md
  - /a0/usr/projects/qc_lims/.a0proj/knowledge/main/bmad-master/orchestration-notes.md
  - /a0/usr/projects/qc_lims/.a0proj/knowledge/main/project-context.md
  - /a0/usr/projects/qc_lims/_bmad-output/planning-artifacts/ux-design-specification.md
date: 2026-05-25
author: User
---

# Product Brief: qc_lims

## Executive Summary

**QC_LIMS** is a purpose-built Laboratory Information Management System for the EU GMP-licensed medical cannabis QC laboratory at Purely Plant GmbH (North Macedonia). The system transforms paper-based QC operations through barcode-activated workflows, embedded GMP compliance guidance via Letta RAG AI agents, and narrative audit timelines — making regulatory compliance an invisible outcome of good daily work rather than a separate documentation burden.

The system does not aim to replace paper immediately — it runs as a parallel digital system with full paper replacement as a future state. It serves 6 distinct personas (QC Analyst through Qualified Person) across 13 laboratory modules spanning sample management, specification control, COA generation, OOS investigation, stability studies, and AI-assisted quality management.

---

## Core Vision

### Problem Statement

QC laboratory teams at EU GMP cannabis facilities today operate with **paper-based Quality Management Systems**. The daily reality involves:

- **Triple transcription**: Logbook → Excel → COA form — every data point entered 3 times in 3 different places, each introducing transcription error risk
- **Compliance friction**: SOPs sit on shelves as 500-page binders. Analysts must stop work, flip to relevant section, interpret applicability — while managing sample throughput
- **Audit anxiety**: Regulatory inspections require reconstructing complete sample histories from scattered paper logs, multiple notebooks, and Excel files. A single missing entry can trigger an observation
- **Review bottlenecks**: The 'Submit for Review' pattern creates idle waiting — one person's work blocks the next person's progress
- **OOS investigation stress**: Out-of-specification results trigger a 24-hour documented investigation cycle. Without guided workflow support, Phase I investigations become stressful scrambles
- **Invisible compliance**: Teams do compliant work but struggle to *prove* compliance to inspectors because the evidence is fragmented across siloed records

### Problem Impact

- **Who feels this most acutely?** QC Analysts doing daily high-throughput testing (50+ results per batch), QC Managers responsible for batch release decisions, and Qualified Persons who must personally certify each COA for release. Auditors face the downstream challenge of reconstructing evidence trails.
- **What happens if unsolved?** Continued regulatory risk — Macedonian GMP inspection followed by EU GMP audit means observable deficiencies in data integrity, audit trail completeness, and electronic record controls. Paper systems cannot satisfy ALCOA++ contemporaneous and consistent requirements at scale.
- **Current cost**: 7 days average turnaround from first scan to batch release in paper system. Each transcription carries error risk. Each missing signature delays release.

### Why Existing Solutions Fall Short

| Alternative | Key Limitation |
|-------------|---------------|
| **Paper-based QMS** | Manual errors, lost forms, slow audits — the problem itself |
| **Generic LIMS (LabWare, LabVantage)** | GMP compliance bolted on as afterthought; no cannabis-specific SOPs; no AI guidance; complex configuration requiring vendor consultants |
| **Excel + Word** | No audit integrity, version chaos, no electronic signatures — cannot satisfy Annex 11 or 21 CFR Part 11 |
| **No system** | Everything manual, highest risk during inspection |

Existing LIMS solutions fail because they treat GMP compliance as a module to layer on top, rather than embedding it into the fundamental interaction design. They also offer no facility-specific SOP awareness — the system doesn't *read* the actual laboratory procedures to guide users.

### Proposed Solution

QC_LIMS delivers **frictionless compliance** through five architectural innovations:

1. **Barcode → Context**: A single barcode scan loads complete sample context — pending tests, spec limits, SOP references, status — eliminating triple transcription
2. **Embedded GMP Guidance**: Letta RAG AI agents read actual Purely Plant SOPs from Qdrant vector database and surface non-blocking, source-cited compliance tooltips during workflows
3. **Narrative Audit Trail**: Audit records presented as human-readable timeline stories — "Monday 09:15 — Collected by Ana → 10:14 — THC started by Stefan" — not filtered database tables
4. **Progressive Live Review**: No 'Submit' button. Results are visible to reviewers as they're entered. Workflow advances automatically when conditions are met
5. **Declaration-Level Signing**: QP sees full verification summary before signing — "Stefan verified 12 results, Blagoj approved conformity, 0 overrides, 0 deviations"

The system is built on FastAPI + React + PostgreSQL + Qdrant + Letta AI agents, with bilingual Macedonian/English support throughout UI, documents, and agent responses.

### Key Differentiators

| # | Differentiator | Why It's Unique |
|---|---------------|-----------------|
| 1 | **Embedded SOP-Aware AI** | Letta RAG reads actual Purely Plant SOPs via Qdrant. Provides non-blocking, source-cited compliance tooltips — not generic AI or static help pages |
| 2 | **Narrative Audit Timeline** | Audit records are stories with named actors and timestamped events — faster for inspectors, better comprehension than filtered database tables |
| 3 | **Barcode-to-Context Activation** | Scan triggers full workflow context (tests, specs, SOPs, status) — not just 'sample received' logging |
| 4 | **QP Declaration-Level Signing** | Unified COA with verification summary, override flags, and deviation status — professional shield for the QP, not a checkbox |
| 5 | **3-Tier Resilience** | Letta available → full AI guidance. Letta unavailable → cached SOP snippets. Complete offline → static validation rules still function. AI is additive, not critical path |
| 6 | **No Time Pressure UX** | Only the 15-minute session inactivity timer exists. OOS investigation tracked as status ('Day 1'), never a countdown. Respects professional pace of careful science |
| 7 | **Correction as First-Class** | Amending data is as easy as editing in consumer apps, but captures reason, preserves original, and shows version history — honesty is rewarded |

**Why now?** Upcoming Macedonian GMP inspection followed by EU GMP certification means the facility needs demonstrable electronic record controls. The existing backend scaffold (models, core modules) and Letta stack (ingested 21+ SOPs in Qdrant) mean the technical foundation is already in place.

---

## Target Users

### Primary Users

#### 1. Ana — QC Analyst

**Role & Context:** Ana spends her day testing dried cannabis flower — moisture content, cannabinoid profiles by HPLC, microbiological limits. She handles 50+ test results per batch, multiple batches daily. She's skilled, precise, and currently fights a paper system that makes her enter every number three times (logbook → Excel → COA form).

**Problem Experience:** Triple transcription creates constant anxiety about transcription errors. When a result approaches a spec limit, she's on her own — the SOP binder sits on a shelf across the lab. If she discovers an OOS result, the 24-hour investigation clock starts ticking and she must scramble to document her checks before the shift ends.

**Success Vision:** Ana scans a barcode. The screen loads her sample's complete context — 12 pending tests, spec limits pre-filled, SOP references linked. She tabs through the grid entering results. Validation happens as she types. When CBN approaches the upper limit, a subtle badge appears: *"Per QCSOP 019 §5.2, recommend remark."* She adds a note. When all 12 results are in, the footer updates: "Ready for reviewer verification." No 'Submit' button — the system knows she's done. Her hidden need: a pre-OOS verification screen that calms her fear before she escalates.

#### 2. Stefan — QC Supervisor (Reviewer)

**Role & Context:** Stefan verifies Ana's analytical results — the mandatory 2nd person check required by EU GMP. He manages the review queue across multiple analysts and handles Phase IB of OOS investigations.

**Problem Experience:** Paper results arrive in batches at shift end. He can't review incrementally — everything piles up at once. Urgent results aren't distinguishable from routine ones. He recreates the same checklist mentally for every OOS investigation.

**Success Vision:** Stefan sees Ana's results appear in his live queue as she enters them. He reviews in parallel — no waiting for "Submit." The queue is risk-prioritized: results near spec limits surface to the top. OOS investigations come with pre-populated checklists from his reusable templates. His hidden need: auto-notification the moment Ana completes a batch so he can begin review immediately.

#### 3. Blagoj — QC Manager

**Role & Context:** Blagoj approves specifications, sampling plans, and COAs. He makes decisions that affect product release, manages the QC team, and owns the laboratory's compliance posture.

**Problem Experience:** When a spec changes, he manually traces which active batches, which pending COAs, and which stability studies are affected. He discovers impacts by memory and email chains, not by system visualization. Quarterly trending requires compiling data from scattered Excel files.

**Success Vision:** Blagoj opens a specification and sees a dependency map: "Changing the THC upper limit affects 3 active batches, 12 pending COAs, and the ongoing long-term stability study for Batch PP-BTH-2026-0042." He approves the change with full awareness. Dashboards show real-time lab throughput, OOS rates trended monthly, and instrument utilization — all from a single source of truth.

#### 4. Elena — QA Manager

**Role & Context:** Elena owns the document control system — all QCSOP documents, specifications, and quality registers. She ensures the QMS remains inspection-ready at all times.

**Problem Experience:** Quarterly register reviews mean pulling paper files, checking for completeness, and manually compiling trends. When an inspector asks for a specific record, the search crosses multiple binders and filing cabinets. She trusts the work was done correctly — proving it is the struggle.

**Success Vision:** Elena opens the system and sees automated quarterly register summaries — OOS events by type and outcome, spec changes by material, audit trail completeness metrics. When an inspector asks "Show me all changes to Specification PP-SPEC-2025-0042," she runs a 3-second search and gets the complete version history with every approval, every reason for change, every effective date — in one scrollable timeline. Her hidden need: trust that amendments are visible immediately when she opens a record.

#### 5. Martin — Qualified Person (QP)

**Role & Context:** Martin is legally responsible for certifying each batch before release to the EU market. His signature on a COA carries personal liability. He must personally satisfy himself that every test was performed correctly, every result complies with the specification, and every deviation was properly investigated.

**Problem Experience:** Paper COAs arrive at his desk as a stack. He checks each parameter against the specification manually. If a result was corrected, he must trace back through analyst notes to understand why. There's no summary view — just raw data. His signature decision must be made with incomplete context.

**Success Vision:** Martin opens the COA for Batch PP-BTH-2026-0042. At the top, a verification summary: "Stefan verified 12 results. Blagoj approved conformity. 0 overrides. 0 deviations. All specifications current as of 2026-05-25." He scrolls through all results with spec comparisons inline. Any corrections show the original value, the amended value, and the reason — all visible without clicking. He checks the attestation checkbox: "I have reviewed all results and confirm compliance." He enters his MFA code. The COA is digitally signed. His hidden need: adversarial intelligence — what if a result was overridden and he wasn't told? The summary answers before he asks.

#### 6. Maria — External Laboratory Contact

**Role & Context:** Maria works at a contract laboratory that performs specialized testing (pesticide residues, mycotoxins) for Purely Plant. She receives physical samples by courier, runs the analyses, and reports results back.

**Problem Experience:** Samples arrive without advance notice. She opens the package and discovers 15 samples with a paper manifest. She must manually log each receipt and email confirmation. Purely Plant doesn't know the samples arrived until she sends that email — sometimes days later.

**Success Vision:** Maria receives a pre-arrival notification: "15 samples dispatched via courier DHL #3928471, expected delivery 2026-05-26." When the package arrives, she scans the manifest barcode and confirms receipt for all 15 samples in a single action. Purely Plant sees the status update immediately. Before the physical package arrives, she already sees what tests are required and can queue instrument time.

### Secondary Users

#### 7. Regulatory Inspector / QA Auditor

**Role & Context:** Inspectors from the Macedonian DZHU and EU regulatory authorities conduct on-site audits. They request specific records — samples, COAs, specifications, audit trails — and expect to see them within minutes, not hours.

**Problem Experience:** Paper systems mean pulling binders, finding specific forms, verifying signatures are present, and checking that correction procedures were followed. A single missing signature or unlogged correction can trigger a formal observation.

**Success Vision:** The inspector asks: "Show me all records for Batch PP-BTH-2026-0042." The auditor role opens the system with read-only access. A 3-second global search returns the complete batch history — samples, test results, reviewer verifications, COA with QP signature, all audit trail entries — in one timeline. The inspector is impressed by the completeness. The audit passes without observations.

#### 8. System Administrator

**Role & Context:** Manages user accounts, role assignments, system configuration, backup verification, and the technical validation of the computerised system per EU GMP Annex 11.

**Success Vision:** User management with clear role-based access control. Audit logs of all admin actions. Automated backup verification reports. System health dashboards showing database status, Letta agent connectivity, and Qdrant index freshness.

### User Journey — The Relay Model

> **A batch flows through QC_LIMS as a relay, not a queue.**

**Stage 1 — Collection:** Sampler logs into tablet in the processing area. Scans batch barcode. System loads sampling plan per QCSOP 011. Label printer generates unique sample ID (PP-SMP-2026-0518-001) with QR code. Sample logged. Chain of custody initiated.

**Stage 2 — Receipt:** Sample arrives at QC lab. Receiver scans QR code. System confirms: "Sample received 09:15 by Ana K. Condition verified. Storage: Cabinet B, Shelf 3." Chain of custody handoff recorded with digital signatures.

**Stage 3 — Testing:** Ana scans sample barcode at her workstation. System loads full context: 12 pending tests, spec limits, SOP references, instrument status. Ana tabs through the grid entering results. Validation runs as she types. Auto-save logs every keystroke to the audit trail. When she completes all 12 results, the footer updates: "Ready for reviewer verification." *(No 'Submit' button — the system knows.)*

**Stage 4 — Review (parallel):** Stefan sees Ana's results appear in his live queue in real-time — he starts reviewing while she's still entering. His queue is risk-prioritized. He verifies each result against the specification snapshot. Second person check logged. Handoff latency tracked: if >4 hours between Ana's completion and Stefan's review start, flagged for extra scrutiny.

**Stage 5 — Approval:** Blagoj reviews the completed verification. Confirms specification conformity. Approves the batch results. System checks: all parameters within spec, all verifications complete, all deviations documented.

**Stage 6 — QP Release:** Martin opens the full-screen COA review. Sees verification summary: "12 results, 0 overrides, 0 deviations, all specs current." He scrolls through all results. Checks the attestation checkbox. Enters MFA code. COA digitally signed with hash chain linking to all preceding entries. Batch released.

**Time from first scan to release:** Target 3 days (paper system average: 7 days).

**The Aha! Moments:**
- **Ana's moment:** First time she scans a barcode and the system loads everything — her data entry time drops 60%
- **Stefan's moment:** First time he reviews results while Ana is still entering them — no more end-of-shift pile-up
- **Martin's moment:** First COA where the verification summary tells him everything he needs before he even scrolls — he signs with full confidence
- **Inspector's moment:** First audit where a 3-second search produces the complete life of a batch — he closes his notebook early

---

## Success Metrics

### User Success Metrics

**For each persona, success is defined by observable outcomes and behaviors:**

| Persona | Success Outcome | Observable Indicator | Target |
|---------|----------------|----------------------|--------|
| **Ana — QC Analyst** | Completes result entry faster and more accurately than paper | Average time per test result entry | < 3 seconds per result |
| | Reduces transcription errors | Error rate (corrections logged) | < 2% of results amended |
| | Feels supported during OOS discovery | Pre-OOS verification screen acknowledged before escalation | 100% of OOS triggers see guidance screen first |
| **Stefan — QC Reviewer** | Reviews results in parallel, not batched | Average time between last result entry and first review action | < 30 minutes (paper: end-of-shift pile-up) |
| | Can distinguish urgent from routine at a glance | Risk-prioritized queue surfaces near-limit results to top | Top 20% of queue shows results within 10% of spec limits |
| **Blagoj — QC Manager** | Understands change impact before approving | Dependency map shows all affected batches, COAs, studies before approval action | 100% of spec changes show impact visualization |
| **Elena — QA Manager** | Audit-ready at any moment | Time to produce complete record for inspector request | < 3 seconds (global search returns full timeline) |
| | Trusts that amendments are visible | Amendment badge visible inline without navigation | 100% of records show provenance badges on open |
| **Martin — QP** | Signs COAs with full confidence | Verification summary presented before signature action | 100% of COA releases show summary with override count, deviation count |
| | Completes COA review efficiently | Time from opening COA to digital signature | < 2 minutes (including MFA) |
| **Maria — External Lab** | Knows samples are coming before they arrive | Pre-arrival notification sent before physical delivery | 100% of external dispatches trigger advance notice |
| **Inspector / Auditor** | Finds complete records without assistance | Audit search self-service — inspector navigates read-only role independently | 100% of requested records retrieved in single search |

### Business Objectives

#### 1. Regulatory Readiness (Primary)

**Why this matters:** The upcoming Macedonian GMP inspection followed by EU GMP certification is the existential business driver. The system must demonstrate electronic record controls that satisfy Annex 11 and ALCOA++.

| Objective | Measurement | 3-Month | 12-Month |
|-----------|------------|---------|----------|
| Annex 11 compliance readiness | Completed validation documents (URS, FS, DS, RA, IQ/OQ protocols) | IQ/OQ for P0 modules complete | Full validation package for all modules |
| ALCOA++ audit trail completeness | % of GxP-relevant actions with immutable audit entries | 100% of CREATE/UPDATE/DELETE/APPROVE/SIGN actions logged | 100% including VIEW/EXPORT/PRINT |
| Electronic signature compliance | Two-component signatures for release actions | MFA gating on all COA and batch release actions | MFA on all approval/reject/sign actions |
| Inspection readiness | Mock audit success rate | System passes mock internal audit on P0 workflows | System passes mock external audit on all modules |

#### 2. Operational Efficiency

| Objective | Measurement | Target |
|-----------|------------|--------|
| Reduce batch release cycle time | Time from first sample scan to QP release | 3 days (paper baseline: 7 days) |
| Reduce transcription burden | Data entry fields per batch | Eliminate triple entry — one capture per data point |
| Accelerate audit response | Time to locate and present records during inspection | 3 seconds per search query |

#### 3. Compliance Quality

| Objective | Measurement | Target |
|-----------|------------|--------|
| Eliminate undocumented corrections | % of corrections with required reason and reviewer signature | 100% (ALCOA++ Complete) |
| Reduce OOS investigation duration | Time from detection to Phase I closure | Complete Phase I within 1 working day (per QCSOP 019) |
| Prevent backdating | % of timestamps that are server-generated (not user-entered) | 100% (ALCOA++ Contemporaneous) |

### Key Performance Indicators

#### Leading Indicators (Predict success)

| KPI | Measurement Method | Target | Frequency |
|-----|-------------------|--------|-----------|
| **Daily active users** | Unique logins with at least one audited action | 100% of lab staff (6-8 users) | Daily |
| **Review parallelism** | % of results reviewed within 1 hour of entry (vs. end-of-shift batch) | > 80% | Weekly |
| **System availability** | Uptime % of backend API + Letta agents | 99.5% (allows scheduled maintenance) | Monthly |
| **Letta RAG tier** | % of time Letta Tier 1 (full guidance) is available vs. Tier 2/3 | > 95% Tier 1 | Weekly |
| **OOS detection-to-notification** | Time between result entry exceeding spec and manager notification | < 5 minutes (automated) | Per event |

#### Lagging Indicators (Confirm success)

| KPI | Measurement Method | Target | Frequency |
|-----|-------------------|--------|-----------|
| **Batch release throughput** | Batches released per month | Consistent with production schedule | Monthly |
| **Audit trail completeness** | % of required audit fields populated (user, timestamp, action, reason) | 100% | Monthly audit |
| **Correction rate** | % of test results amended after initial entry | < 2% | Monthly |
| **OOS rate** | OOS events as % of total test results | Trending downward or stable (monitor, not target) | Monthly |
| **Inspection outcome** | Number and severity of observations related to data integrity / computerised systems | Zero critical, zero major | Per inspection |

### Strategic Alignment

Every metric connects back to the core product vision. Here's the traceability:

| Vision Element | Primary Metric | KPI |
|---------------|-----------|------|
| **Barcode → Context** | Time per test result entry | < 3 seconds per result |
| **Embedded GMP Guidance** | Letta RAG availability tier | > 95% Tier 1 |
| **Narrative Audit Trail** | Inspector search time | < 3 seconds |
| **Progressive Live Review** | Review parallelism rate | > 80% within 1 hour |
| **Declaration-Level Signing** | QP COA review time | < 2 minutes |
| **No Time Pressure UX** | (Absence of anxiety metric — tracked via user feedback) | Qualitative |
| **Correction as First-Class** | % corrections with complete documentation | 100% reason + signature |

---

## MVP Scope

### Core Features (P0 — Foundation Release)

The MVP delivers the **minimum set of capabilities that solves the core problem** — eliminating triple transcription, providing a single source of truth for sample data, and generating auditable COAs with electronic signatures.

| # | Module | What It Does | Why It's Essential |
|---|--------|-------------|-------------------|
| 1 | **Sample Lifecycle** | Barcode-scanned sample registration, chain-of-custody tracking, test assignment, status tracking (COLLECTED → RELEASED) | Core user action — eliminates triple transcription. First touchpoint for every workflow. Enables the 'Scan → Context' differentiator. |
| 2 | **COA Generation** | Result grid entry with validation, progressive live review, QP declaration-level digital signing, PDF/A output via Gotenberg | Delivers 4 of 5 'Aha!' moments (Ana's scan, Stefan's parallel review, Martin's confident signature, Inspector's 3-second search). Reduces batch release from 7 to 3 days. |
| 3 | **Specification Management** | Spec lifecycle (Draft → Active → Superseded), versioned limits with change control, spec-to-result auto-comparison | Foundation for all compliance decisions. Without specs, COA has no basis for pass/fail. Must support Ph. Eur. cannabis monograph parameters (THC, CBD, cannabinoid profile, microbial limits). |

**These three modules together deliver the complete sample → test → COA pipeline.**

#### MVP Must Also Include (Infrastructure)

| Component | Purpose |
|-----------|---------|
| **User Management** | Role-based access (Analyst, Reviewer, Manager, QP, Auditor, Admin). Password complexity + MFA for release actions. |
| **Audit Trail (Core)** | Immutable WORM audit logging for all CREATE, UPDATE, SIGN, APPROVE actions on GxP records. Hash chain for tamper evidence. |
| **Bilingual Infrastructure** | Macedonian/English toggle in toolbar. Translation keys for all UI labels, errors, and generated document headers. |
| **Basic Dashboard** | Sample status overview: pending tests, in-progress, overdue. Role-filtered views. |

### Out of Scope for MVP

These are explicitly deferred to post-MVP releases. Each is important — but none are *essential* to solving the triple-transcription problem and getting compliant COAs out the door.

| # | Feature | Priority Level | Why Deferred |
|---|---------|---------------|-------------|
| 1 | **OOS Investigation Wizard** | P1 | Requires working COA and sample lifecycle as foundation. Paper OOS process is functional as interim. |
| 2 | **Narrative Audit Timeline Views** | P1 | Basic audit trail is in MVP — narrative views (stories, timelines) are UX enhancement on existing data. |
| 3 | **Letta RAG Agent Integration** | P1-P4 | Embedded GMP guidance (Tier 1) is a differentiator, not a critical path blocker. Static spec validation (Tier 3) handles core compliance. |
| 4 | **Water System QC** | P2 | SOP QCSOP 014 not yet uploaded. Separate testing schedule from batch testing. |
| 5 | **Microbiological Monitoring** | P2 | Environmental monitoring is a distinct workflow with different sampling patterns and data types. |
| 6 | **Cannabinoid Testing Module** | P2 | Core results entry in COA handles the data capture. Advanced HPLC integration (Chromeleon/Empower parsing) requires instrument interfaces. |
| 7 | **Stability Studies** | P3 | Long-term activity. Zero-time data captured via standard sample/COA pipeline. Pull scheduling and trending are post-MVP. |
| 8 | **Equipment Calibration** | P3 | Standalone module. Manual calendar tracking is adequate interim. |
| 9 | **Inventory & Labeling** | P3 | Chemical tracking separate from product batch testing. |
| 10 | **CAPA Manager Agent** | P4 | AI-guided OOS investigation is transformative but depends on OOS module (P1) being built first. |
| 11 | **SOP Writer Agent** | P4 | Bilingual SOP drafting is productivity enhancement, not core value. |
| 12 | **Mobile/Tablet App** | Future | Desktop-first for MVP. Tablet collection interface can be a responsive view, not native app. |

### MVP Success Criteria

The MVP is successful when the following criteria are met — these are the go/no-go gates before expanding beyond P0:

| # | Criterion | Measurement | Gate |
|---|-----------|------------|------|
| 1 | **Complete sample-to-COA pipeline functional** | A test batch can be registered, tested, reviewed, approved, and released entirely within the system | All P0 workflow steps execute without paper fallback |
| 2 | **Audit trail completeness** | All CREATE, UPDATE, SIGN, and APPROVE actions produce immutable audit entries with required fields | 100% coverage verified by audit query |
| 3 | **Electronic signatures compliant** | COA and batch release require two-component authentication (password + MFA) | 21 CFR Part 11 §11.200 satisfied |
| 4 | **Bilingual coverage** | All UI labels, error messages, and generated COA headers available in MK and EN | 100% of user-facing strings |
| 5 | **User acceptance** | QC Analysts and QP can complete their core workflows without paper assistance | Qualitative: team signs off on parallel-system readiness |
| 6 | **Mock audit pass** | Internal QA audit finds no critical or major observations related to data integrity | Zero critical, zero major observations |

**Decision gate:** When criteria 1-6 are met, proceed to P1 (OOS Investigation + Audit Trail enhancement). If any criterion fails, fix before expanding scope.

### Future Vision

**Post-MVP Evolution (P1 → P4):**

| Phase | Modules Added | Cumulative Capability |
|-------|--------------|----------------------|
| **P0 (MVP)** | Sample Lifecycle, COA, Spec Mgmt, Core Audit, User Mgmt | End-to-end digital sample → COA pipeline |
| **P1** | OOS Investigation, Narrative Audit Trail, Enhanced User Mgmt | Full compliance workflow — OOS detection through CAPA closure |
| **P2** | Water System QC, Micro Monitoring, Cannabinoid Testing | Complete laboratory operations — all test types covered |
| **P3** | Stability Studies, Equipment Calibration, Inventory | Full QC laboratory digitization — all SOP workflows |
| **P4** | Letta RAG Agents (all 5), AI QMS Dashboard | Embedded AI compliance guidance — the full vision |

**Long-term (2-3 year horizon):**
- **Full paper replacement** — system becomes primary record (not parallel). Requires GMP validation of electronic records as original.
- **Multi-site deployment** — Other EU GMP cannabis facilities adopting the same module with facility-specific SOP ingestion.
- **Regulatory submission integration** — Direct submission of batch records and COAs to regulatory authorities via structured data formats.
- **Predictive quality analytics** — AI trend analysis across years of stability data, OOS patterns, and environmental monitoring to predict quality risks before they occur.
