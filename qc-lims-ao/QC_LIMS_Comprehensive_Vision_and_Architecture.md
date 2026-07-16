# QC_LIMS — Comprehensive Vision, Architecture, and Decisions

**Document Type:** Project Synthesis & Architectural Decision Record  
**Module Code:** `qc-lims`  
**Module Type:** Standalone BMAD Module  
**Domain:** EU GMP Quality Control LIMS for Medical Cannabis  
**Facility:** Purely Plant GmbH, North Macedonia  
**Date:** 2026-05-24  
**Status:** Active — In Module Brief Creation (Step 8 completed)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Experience Design](#2-core-experience-design)
3. [Emotional Response & Design Principles](#3-emotional-response--design-principles)
4. [Workflow Architecture](#4-workflow-architecture)
5. [Module Definition & Identity](#5-module-definition--identity)
6. [User Personas & Role Interactions](#6-user-personas--role-interactions)
7. [Unique Value Proposition](#7-unique-value-proposition)
8. [Agent Architecture](#8-agent-architecture)
9. [Technical Architecture](#9-technical-architecture)
10. [Regulatory Compliance Framework](#10-regulatory-compliance-framework)
11. [Implementation Priority & Roadmap](#11-implementation-priority--roadmap)
12. [Key Architectural Decisions](#12-key-architectural-decisions)

---

## 1. Executive Summary

**QC_LIMS** is a standalone BMAD module providing a GMP-compliant Laboratory Information Management System for the EU licensed medical cannabis QC laboratory at Purely Plant GmbH. The system is built from scratch to improve the quality of life for laboratory colleagues — reducing redundant data entry, embedding compliance guidance into workflows, and producing perfect audit records as a natural outcome of doing good work.

### Core Vision

> **Make laboratory life better.** Reduce the daily friction of paper-based QC operations through barcode-activated workflows, embedded GMP guidance via Letta RAG agents, narrative audit timelines, and progressive review — so compliance becomes invisible, colleagues feel supported and proud, and regulatory inspections are met with confidence.

### Strategic Context

- **Not replacing paper immediately.** The system supplements existing paper QMS as a parallel digital system. Full paper replacement is a potential future state.
- **Inspections approaching:** Macedonian GMP inspection, followed by EU GMP. The system aims for partial implementation readiness.
- **From scratch:** No legacy LIMS migration. Clean architecture, full control.
- **Bilingual:** Macedonian (primary) and English throughout UI, documents, and agent responses.

### Key Innovations

| Innovation | Description |
|-----------|-------------|
| **Barcode → Context** | Single barcode scan loads complete sample context: pending tests, spec limits, SOP references, status |
| **Embedded GMP Guidance** | Letta RAG agents provide non-blocking, source-cited, advisory compliance nudges during workflows |
| **Narrative Audit Trail** | Human-readable timeline stories, not filtered database tables — "Monday 09:15 — Collected by Ana → 10:14 — THC started by Stefan" |
| **Progressive Review** | No 'Submit' button — results are live, reviewers see them as they appear, QP reviews COA in parallel |
| **Preventive Prompts** | Historical OOS data feeds proactive guidance before risky tests — "Common pitfalls for this method: dilution factor, extraction time" |
| **Declaration-Level Signing** | QP sees full verification summary before signing — "Stefan verified 12 results, Blagoj approved conformity, 0 overrides, 0 deviations" |

---

## 2. Core Experience Design

### Defining Experience

The QC_LIMS experience centers on **frictionless compliance** — every interaction must satisfy ALCOA++ requirements while feeling faster and more intuitive than paper-based alternatives. The system transforms regulatory burden into invisible guardrails, guiding users toward correct actions without imposing cognitive load.

**Core User Action:** Entering test results at high throughput (50+ results per batch, multiple batches daily). This must feel like a spreadsheet but capture complete audit lineage.

**Secondary Critical Actions:**
- Sample registration with chain-of-custody tracking
- OOS investigation with guided Phase I → Phase II workflow
- COA review and digital signature for QP release
- Real-time dashboard monitoring for QC Managers

### Platform Strategy

| Platform | Priority | Technology | Use Case |
|----------|----------|-----------|----------|
| **Desktop Web** | Primary | React + TypeScript | Data entry, review, dashboard — full keyboard navigation |
| **Tablet** | Secondary | React (responsive) | Cleanroom sample collection, gowning areas |
| **Backend** | Core | FastAPI + PostgreSQL | API, data integrity, audit trail |

### Effortless Interactions

| Interaction | Streamlined UX |
|-------------|----------------|
| Language switching | Ambient toolbar toggle, persistent preference, one click |
| Test result entry | Grid entry with tab navigation, validation as you type, 3s per result |
| Audit trail lookup | Inline badges, hover to expand full lineage, never hidden |
| OOS investigation | Guided wizard, auto-save, status shows "Phase I — Day 1" — NO countdown timers |
| Sample search | Global search, 3 seconds, complete timeline returned |
| COA signature | Full-screen review, checkbox attestation, MFA, sign — declaration, not checkbox |
| Correction entry | "Amend" button, reason dropdown, original preserved, version visible |
| **Session security** | 15-minute inactivity timeout, 2-minute warning countdown, extend or save |

### Critical Design Principle: No Time Pressure

**ONLY timer:** Session inactivity auto-logout (15 minutes, with 2-minute warning).

**NO countdown timers** for OOS investigations, testing, or workflow deadlines. Workflows proceed at the professional pace of careful science. The 24-hour Phase I requirement is tracked in the system backend, visible as status ("Day 1"), not as an anxiety-inducing countdown. The QC Manager sees pending queue sorted by age for prioritization.

### Critical Success Moments

1. **"The 3-Second Search"** — First time searching for a sample and getting complete lifecycle in one scrollable timeline.
2. **"The Effortless Correction"** — First time amending a result with reason dropdown, seeing original preserved, no admin needed.
3. **"The Guided OOS"** — First OOS investigation where the system presents pre-populated checks and auto-saves, with the supervisor auto-notified.
4. **"The Confident Signature"** — First COA release where the QP sees verification summaries and signs with full confidence.

---

## 3. Emotional Response & Design Principles

### Primary Emotional Goals

| Emotion | What Users Should Feel | UX Strategy |
|---------|----------------------|-------------|
| **Confident** | In control of their work, not subjects of the system | Visible system checks, clear success indicators |
| **Trusting** | The system is a reliable colleague, not surveillance | Graceful error recovery, transparent audit trail |
| **Efficient** | Productive at their natural pace, not rushed | Keyboard-driven grid entry, no countdowns |
| **Calm** | No anxiety — focused and deliberate | Clean density, status not urgency, security-only timer |
| **Proud** | Professional satisfaction when work is complete | Completion acknowledgments, professional COA output |

### Emotional Journey Map

| Stage | Desired Emotion | UX Support |
|-------|----------------|------------|
| First login | Welcomed, oriented | Clean onboarding, SOP-aware guidance |
| Daily data entry | In flow, efficient | Grid with keyboard nav, validation as you type |
| Discovering error | Supported, not punished | "Amend" with reason, version preserved |
| OOS investigation | Guided, not pressured | Wizard with auto-save, visible status |
| COA signature | Confident, informed | Full verification summary, declaration view |
| Audit inspection | Impressed, satisfied | 3-second search, narrative timeline |
| Returning next day | Smooth resume | Auto-saved state, clear status of pending work |

### Design Principles (7 Principles)

1. **Compliance as Default** — The path of least resistance is always the compliant path. Non-compliant actions require deliberate effort.
2. **Visible Integrity** — Data lineage is never hidden. Every value shows provenance: original, amended, verified, or overridden — inline.
3. **Streamlined Density** — Information density matches user sophistication. Analysts: minimal chrome, maximum data. QPs: full context. Auditors: everything.
4. **Ambient Bilingualism** — Language is environment, not setting. Toggle is one click, persistent, and translation keys carry workflow context.
5. **Friction by Design** — Only release actions (COA signature, batch approval) carry deliberate friction. Data entry is fast and fluid.
6. **Search as Infrastructure** — Global, fast, filterable search is the backbone of audit readiness and daily workflow efficiency.
7. **Correction as First-Class** — Amending data is as easy as consumer app editing, but with captured reasons, version stacks, and visible history. Honesty is rewarded.

---

## 4. Workflow Architecture

### System-Wide Workflow Requirements

Every workflow in QC_LIMS must satisfy:

| Requirement | Implementation |
|-------------|----------------|
| **ALCOA++ Compliance** | Every state change logged: user ID, timestamp, session, reason. Immutable audit entries. |
| **Role-Based Transitions** | State machine guards check user.role before allowing transitions |
| **Bilingual Content** | Workflow steps carry both MK and EN labels; user preference determines display |
| **Letta Integration** | Key decision points can query GMP Expert Agent for SOP compliance |
| **Human Checkpoints** | Critical transitions have explicit STOP instructions for human approval |
| **Error Recovery** | Every workflow has defined rollback paths; business errors trigger CAPA |
| **Event-Driven Coordination** | Role handoffs trigger events → audit trail + notifications → next role |

### Workflow State Machine Pattern

```yaml
workflow_state_machine:
  states: [DRAFT, PENDING, IN_PROGRESS, REVIEW, APPROVED, RELEASED, REJECTED, SUPERSEDED]
  transitions:
    - name: submit_for_review
      from: DRAFT
      to: PENDING
      guard: user.has_role(ANALYST) AND data.complete
      audit: true
      
    - name: review_complete
      from: PENDING
      to: REVIEW
      guard: user.has_role(REVIEWER) AND second_person_verified
      audit: true
      
    - name: approve_release
      from: REVIEW
      to: APPROVED
      guard: user.has_role(QP) AND mfa_verified AND full_review_acknowledged
      audit: true
      stop_for_human: true
```

### P0 Workflow: Sample Lifecycle

**Trigger:** Sample physically collected in lab  
**Success State:** Sample RELEASED or REJECTED/DISPOSED  
**Failure States:** Contamination, chain of custody broken, OOS result

```yaml
states:
  - COLLECTED          # Sample logged, label printed
  - IN_TRANSIT         # Chain of custody transfer
  - RECEIVED           # At testing location
  - IN_TEST            # Assigned to analyst
  - TESTED             # Results entered
  - REVIEWED           # Second person verified
  - APPROVED           # Manager approved
  - RELEASED           # Available for use
  - REJECTED           # Failed spec, disposed
  - QUARANTINE         # Pending investigation

transitions:
  collect:       from [null] → COLLECTED    | actor: SAMPLER
  transfer:      from COLLECTED → IN_TRANSIT | actor: COURIER | requires: chain_of_custody_signature
  receive:       from IN_TRANSIT → RECEIVED  | actor: RECEIVER | requires: condition_verification
  assign_test:   from RECEIVED → IN_TEST     | actor: MANAGER | auto: assign_to_available_analyst
  enter_results: from IN_TEST → TESTED       | actor: ANALYST | requires: all_spec_parameters_complete
  verify:        from TESTED → REVIEWED      | actor: REVIEWER (≠ analyst) | requires: second_person_check_passed
  approve:       from REVIEWED → APPROVED    | actor: MANAGER
  release:       from APPROVED → RELEASED    | actor: SYSTEM (if all specs pass)
  reject:        from [TESTED,REVIEWED,APPROVED] → REJECTED | actor: QP | requires: rejection_reason, disposal_confirmation
  escalate_oos:  from [IN_TEST, TESTED] → QUARANTINE | trigger: out_of_spec_result_detected | auto: notify_manager, create_oos_record
  next_workflow: oos-investigation-v1 (from QUARANTINE)
```

**Entry Conditions:** Sample collected per QCSOP 011, sampling plan exists, sampler authenticated, label printer available.

**Exit Criteria:** RELEASED (all tests passed, manager approved, system auto-releases) OR REJECTED (QP decision, documented reason, disposal recorded) OR QUARANTINE (OOS detected, escalated to investigation).

**Error Handling:**

| Error | Handling | Retry |
|-------|----------|-------|
| Label printer offline | Queue label job, notify admin, manual temp ID | Auto-retry 60s |
| Chain of custody break | Require supervisor override, document reason, flag for audit | Manual resolution |
| Missing sampling plan | Block collection, notify QC Manager | Allow emergency plan creation |
| Out-of-spec result | Auto-trigger OOS workflow, quarantine sample, notify manager | Immediate |

### P0 Workflow: COA Generation

**Trigger:** All test results entered for a batch  
**Success State:** QP digitally signs COA  
**Key Innovation:** Progressive review — results visible live, reviewer works in parallel

### P1 Workflow: OOS Investigation

**Trigger:** OOS result detected during testing  
**Stages:** Phase IA (Analyst, 1-hour window) → Phase IB (Supervisor, 7-step assessment) → Investigation → CAPA → Closure  
**Forms:** A01 (Internal Record), A02 (External Record), A03 (Register), A04 (Notification)

### Critical Workflow Priority

| Priority | Workflow | Dependencies | SOP Basis |
|----------|----------|--------------|-----------|
| **P0** | Sample Lifecycle | None | QCSOP 011, QCSOP 017, PP-QC-SOP-012 |
| **P0** | COA Generation | Sample Mgmt, Spec Mgmt | QCSOP 012, QCCoA 001 |
| **P0** | Specification Management | None | QCSOP 010 |
| **P1** | OOS Investigation | Sample, Spec, COA | QCSOP 019 + A01–A04 |
| **P1** | User Management & Roles | None | QCSOP 001 |
| **P2** | Water System QC | Sample Mgmt | QCSOP 014 (pending) |
| **P2** | Microbiological Monitoring | Sample Mgmt | QCSOP 023, QCSOP 024 |
| **P3** | Stability Studies | Sample, COA | QCSOP 018 |
| **P3** | Equipment Calibration | None | QCSOP 008 |

---

## 5. Module Definition & Identity

### Module Type: STANDALONE

**Decision:** QC_LIMS is a standalone BMAD module — not an extension of any existing module.

**Rationale:**
1. No existing BMAD module covers QC laboratory operations, GMP compliance, sample management, or electronic signatures
2. The domain is entirely novel within the BMAD ecosystem
3. Extension to existing modules would couple unrelated concerns
4. Global would impose GMP features on all BMAD users

**Implications:** Own module code (`qc-lims`), independent installation, full control over agents, workflows, data, config. Can become the base module for future LIMS extensions.

### Identity

| Attribute | Value |
|-----------|-------|
| **Module Code** | `qc-lims` |
| **Display Name** | `QC LIMS — EU GMP Quality Control` |
| **Personality Theme** | Professional / Laboratory |
| **Visual Identity** | Clean, medical, precision-focused |
| **Language** | Bilingual: Macedonian (primary) + English |

---

## 6. User Personas & Role Interactions

### Persona Map

| Persona | Role | Primary Need | Hidden Need |
|---------|------|-------------|-------------|
| **Ana** — QC Analyst | Daily testing, data entry, Phase IA OOS | Fast accurate entry with context auto-loading | Pre-OOS verification screen to calm fear before escalation |
| **Stefan** — QC Supervisor | Phase IB OOS, result review, risk classification | Risk-prioritized queue, reusable checklists | Live queue with auto-notification when Ana completes |
| **Blagoj** — QC Manager | Spec/method approval, COA approval, sampling plans | Spec change impact visualization | Dependency map: change X affects Y COAs, Z studies |
| **Elena** — QA Manager | Document control, spec final approval, register reviews | Automated quarterly register reports | Trust in system: amendments visible immediately on open |
| **Martin** — QP | Final COA review, batch release | Declaration-level signing with verification summary | Adversarial intelligence: what if a result was overridden and he wasn't told? |
| **Maria** — External Lab | Receives samples, performs contracted analysis | Clear chain of custody, instant receipt confirmation | Pending request visibility before physical sample arrival |

### Role Interaction Map (Relay Model)

```
Ana (Analyst)  ──complete batch──→  Stefan (Supervisor)
                                        │ verify
                                        ▼
                                    Blagoj (Manager)
                                        │ approve spec conformity
                                        ▼
                                    Martin (QP)
                                        │ sign & release
                                        ▼
                                    (Batch Released)

Maria (External Lab)  ──receipt confirmed──→  Transport Manifest updated
                         results reported →  Ana's sample history updated
```

**Each arrow triggers:** event log → audit trail entry → notification to next role.  
**Handoff latency tracked:** Gap between Ana's completion and Stefan's review start — flagged if >4 hours for extra scrutiny.  
**Core principle:** Workflow is not linear, it's a relay. Each handoff has a sender, receiver, and quality checkpoint.

### User Journey Story

> Ana scans a sample barcode. The screen loads: sample PP-SMP-2026-0518-001, 12 pending tests, spec limits pre-filled. She tabs through the grid entering results. Each validates as she types. Auto-save silently logs every keystroke. When CBN approaches the upper limit, a subtle badge appears: "Per QCSOP 019 §5.2, recommend remark." She adds a brief note. When all 12 results are in, the footer updates: "Ready for reviewer verification." No 'Submit' button — the system knows she's done. Across the lab, Stefan sees the batch appear in his live queue. He begins reviewing while Ana starts the next sample. Three days later, Martin reviews the full COA, sees Stefan's verifications and Blagoj's approval summarized, enters his MFA code, and releases the batch. Time from first scan to release: 3 days. The paper system took 7.

---

## 7. Unique Value Proposition

### UVP Statement

> **For QC laboratory teams at EU GMP cannabis facilities, QC_LIMS provides embedded compliance guidance through Letta RAG agents, narrative audit timelines, and barcode-to-context workflow activation — unlike paper systems, generic LIMS, or manual Excel/Word processes — because the system reads and applies actual laboratory SOPs in real-time, surfaces compliance in the workflow, and presents audit records as human-readable stories, not database dumps.**

### Four Differentiators

| # | Differentiator | Why It's Unique |
|---|---------------|-----------------|
| 1 | **Embedded GMP Guidance** | Letta RAG reads actual Purely Plant SOPs via Qdrant. Non-blocking, source-cited tooltips — not generic AI or static help pages |
| 2 | **Narrative Audit Timeline** | Audit records are stories: "Monday 09:15 — Collected by Ana → 10:14 — THC started by Stefan" — faster for inspectors, better compliance |
| 3 | **Barcode-to-Context Activation** | Scan triggers full workflow context (tests, specs, SOPs, status) — not just "sample received" logging |
| 4 | **QP Declaration-Level Signing** | Unified COA with verification summary, override flags, and deviation status — professional shield, not a checkbox |

### Competitive Context

| Alternative | Limitation | QC_LIMS Advantage |
|-------------|-----------|-------------------|
| **Paper-based QMS** | Manual errors, lost forms, slow audits | Digital capture with invisible compliance |
| **Generic LIMS (LabWare, LabVantage)** | GMP bolted on, no cannabis SOPs, no AI guidance | Purpose-built with actual SOPs ingested as RAG |
| **Excel + Word** | No audit integrity, version chaos, no e-signatures | Immutable audit trail, MFA signatures |
| **No system** | Everything manual, highest risk | The only GMP-compliant digital alternative |

### Resilience: 3-Tier System

| Tier | State | Capability |
|------|-------|------------|
| **Tier 1** | Letta available | Full contextual GMP guidance with dynamic LLM reasoning |
| **Tier 2** | Letta unavailable | Cached SOP snippets (re-indexed weekly). Analyst sees relevant SOP sections without dynamic reasoning |
| **Tier 3** | Complete offline | Static validation rules (spec limits, required fields) still function; audit trail still logs |

---

## 8. Agent Architecture

### Multi-Agent Design

QC_LIMS uses **5 specialized agents** forming a cohesive laboratory team. No single persona can be simultaneously a GMP regulatory expert, CAPA investigator, SOP drafting assistant, and risk assessor.

### Agent Team

| Agent | Name | Role | Workflows | Communication Style | Memory |
|-------|------|------|-----------|---------------------|--------|
| **GMP Expert** | Viktor | EU GMP compliance advisor | Spec validation, COA review, method verification | Authoritative, citation-driven, bilingual | ✅ Yes (learns facility SOPs) |
| **CAPA Manager** | Elena | OOS investigation & CAPA | OOS Phase I/II, CAPA tracking, root cause | Systematic, investigative, calm, methodical | ✅ Yes (learns from past investigations) |
| **SOP Writer** | — | Bilingual SOP drafting | Spec creation, method SOP drafting | Methodical, template-driven, bilingual MK/EN | ❌ No (stateless, uses templates) |
| **Risk Assessor** | — | Quality risk management | Deviation risk, FMEA, change impact | Analytical, risk-aware, balanced | ❌ No (stateless evaluation) |
| **QMS Orchestrator** | — | Workflow coordination | Routes queries to specialists, dashboard overview | Polished, orchestral, multi-lingual | ✅ Yes (coordinates across agents) |

### Agent Interaction Scenario

1. Analyst detects OOS → QMS Orchestrator routes to CAPA Manager (Elena)
2. Elena starts Phase IA → pulls relevant SOP from GMP Expert (Viktor): *"QCSOP 019 §5.2 requires..."*
3. Elena completes investigation → triggers Risk Assessor for residual risk evaluation
4. Risk Assessor returns score → Elena generates CAPA plan
5. If new SOP needed → SOP Writer drafts based on CAPA outcome

### Menu Command Architecture

**Shared:** `[WS]` Workflow Status (all agents)

**Specialty:**
| Agent | Commands |
|-------|----------|
| GMP Expert (Viktor) | `[GC]` GMP Compliance Check, `[VS]` Validate Spec |
| CAPA Manager (Elena) | `[OI]` OOS Investigation, `[CA]` CAPA Action |
| SOP Writer | `[SD]` Draft SOP, `[ED]` Edit Document |
| Risk Assessor | `[RA]` Risk Assessment, `[CM]` Change Impact |
| QMS Orchestrator | `[DQ]` Dashboard Query, `[TR]` Task Route |

### Letta RAG Integration

- **Model:** `anthropic/claude-sonnet-4-5`
- **Embedding:** `voyageai/voyage-3` (1024 dimensions)
- **Vector Store:** Qdrant collection `pp_qms_sops` at KVM4 server
- **Chunking:** 500 tokens with 50-token overlap
- **Documents:** 21 QCSOP SOPs + 5 transport/appendix forms
- **Guidance Style:** Advisory, non-blocking tooltips. Always cite source: *"Per QCSOP 019 §5.2..."*

---

## 9. Technical Architecture

### Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | Desktop-first web UI with tablet support |
| **Backend API** | FastAPI (Python) | REST API, business logic, validation |
| **Database** | PostgreSQL | Transactional data, audit trail |
| **Vector DB** | Qdrant | SOP semantic search, RAG retrieval |
| **AI Agents** | Letta (v0.16.7) | Stateful GMP agents with RAG |
| **PDF Generation** | python-docx → Gotenberg | COA PDF generation and PDF/A conversion |
| **Auth** | JWT + MFA | Two-component electronic signatures |

### Backend Scaffold (Existing)

```
backend/app/
├── models/
│   ├── user.py            # User model (roles: Analyst, Reviewer, Manager, QP, Auditor, Admin)
│   ├── sample.py          # Sample lifecycle with states and chain of custody
│   ├── specification.py   # Spec parameters with versioned limits
│   ├── certificate.py     # COA with test results and signature blocks
│   ├── oos.py             # OOS investigation with Phase I/II tracking
│   └── base.py            # SQLAlchemy declarative base
├── core/
│   ├── audit.py           # Immutable WORM audit trail (21 CFR Part 11 compliant)
│   ├── security.py        # JWT, MFA, role-based access, password policies
│   ├── database.py        # Async SQLAlchemy, connection pooling
│   └── config.py          # Environment configuration
└── main.py                # FastAPI application entry point
```

### Architecture Patterns

- **Three-Layer API:** Controller → Service → Repository
- **Pydantic v2 Schemas:** Request/Response validation
- **Event-Driven Coordination:** Handoff events → audit trail + notifications
- **Materialized Views:** Performance for narrative timeline queries
- **Computed Scoring:** Risk-prioritized queues via SQL views
- **Offline Resilience:** 3-tier degradation (Letta → cached → static)

### Infrastructure

- **Letta Stack:** Running on KVM4 Hostinger VPS via SSH tunnel
- **Qdrant:** Same server, port 6333
- **Deployment:** Docker Compose on remote VPS
- **SSH Tunnel:** Persistent with auto-reconnection

---

## 10. Regulatory Compliance Framework

### Applicable Regulations

| Regulation | Impact on LIMS |
|-----------|----------------|
| **EU GMP EudraLex Vol 4 Annex 11** | Computerised systems validation, audit trails, electronic signatures, backup/restore |
| **EU GMP Annex 1** | Environmental monitoring schedules, alert/action limits, room classification |
| **EU GMP Annex 15** | Process/method validation records |
| **EU GMP Annex 16** | QP review workflow, batch release, COA signing |
| **21 CFR Part 11** | Electronic records/signatures — password + MFA, immutable audit trail, hash chain |
| **ICH Q10** | CAPA system, change management, quality risk management, trending |
| **Ph. Eur. Monograph 3028** | Cannabis flower mandatory tests and acceptance criteria |
| **WHO TRS 902 Annex 9** | GMP for herbal medicinal products — botanical identity, purity |

### ALCOA++ Implementation

| Principle | LIMS Implementation |
|-----------|---------------------|
| **Attributable** | Digital signature, user login, timestamped audit trail |
| **Legible** | Print-friendly COAs, clear UI, no overwriting |
| **Contemporaneous** | Real-time data entry, no backdating, locked timestamps |
| **Original** | Immutable raw data store, PDF/A final reports |
| **Accurate** | 2nd person verification, range checks, limits validation |
| **Complete** | Full metadata logging, re-injection tracking, recalculation history |
| **Consistent** | Session UUIDs, logical clock ordering, no gaps |
| **Enduring** | Daily incremental + weekly full backups, 10+ year retention |
| **Available** | Fast search, structured queries, read-only audit user role |

### Audit Trail Schema (Per Entry)

```yaml
audit_entry:
  timestamp: ISO 8601 (UTC + local time offset)
  user_id: UUID
  user_full_name: string
  action: CREATE | UPDATE | DELETE | VIEW | APPROVE | REJECT | SIGN | EXPORT | PRINT
  record_type: string
  record_id: UUID
  record_identifier: string (human-readable)
  field_name: string | null
  old_value: string | null (encrypted at rest)
  new_value: string | null
  reason: string | null (required for critical changes)
  ip_address: string
  session_id: UUID
  digital_signature_hash: string (hash chain linking to previous entry)
```

### Validation Requirements (per EU GMP Annex 11)

- **Category 3 (Configured):** LIMS forms, user roles, workflows, templates → IQ + OQ
- **Category 4 (Complex/Custom):** Letta RAG agents, auto-COA generation → IQ + OQ + PQ + periodic review
- **Key Documents:** URS, FS, DS, RA, IQ/OQ/PQ Protocols, Validation Report

---

## 11. Implementation Priority & Roadmap

### P0 — Foundation (Immediate)

| Module | Deliverables | SOP Basis |
|--------|-------------|-----------|
| **Sample Lifecycle** | Barcode scanning, chain of custody, test assignment, status tracking | QCSOP 011, QCSOP 017, PP-QC-SOP-012 |
| **COA Generation** | Result grid entry, progressive review, QP declaration signing, PDF/A output | QCSOP 012, QCCoA 001 |
| **Specification Management** | Spec lifecycle, version control, change impact visualization, parameter compliance | QCSOP 010 |

### P1 — Core Compliance (Second Wave)

| Module | Deliverables | SOP Basis |
|--------|-------------|-----------|
| **OOS Investigation** | Guided Phase I/II wizard, auto-notification, CAPA tracking, investigation forms A01–A04 | QCSOP 019 + Appendices |
| **User Management** | Role-based access, MFA, training records, qualification status | QCSOP 001, QCSOP 005 |
| **Audit Trail (enhanced)** | Narrative timeline views, inspector-ready exports, hash chain verification | Annex 11, 21 CFR Part 11 |

### P2 — Laboratory Operations (Third Wave)

| Module | Deliverables | SOP Basis |
|--------|-------------|-----------|
| **Water System QC** | Sampling points, TOC/conductivity/microbial trending, alert/action limits | QCSOP 014 (pending) |
| **Microbiological Monitoring** | Environmental sampling, plate reading, grade classification, trend analysis | QCSOP 023, QCSOP 024 |
| **Cannabinoid Testing** | HPLC/GC result entry, moisture-adjusted calculations, system suitability | QCSOP 016 (pending), Ph. Eur. |

### P3 — Advanced Features (Fourth Wave)

| Module | Deliverables | SOP Basis |
|--------|-------------|-----------|
| **Stability Studies** | Pull scheduling, chamber management, trending charts, excursion handling | QCSOP 018 |
| **Equipment Calibration** | Calibration schedules, daily checks, out-of-service tracking | QCSOP 008 |
| **Inventory & Labeling** | Chemical/reagent tracking, reference standards, GMP labeling | QCSOP 025 |

### P4 — AI QMS Integration

| Capability | Agent |
|-----------|-------|
| GMP Compliance Checking | Viktor (GMP Expert) |
| OOS/CAPA Guidance | Elena (CAPA Manager) |
| SOP Drafting | SOP Writer |
| Risk Assessment | Risk Assessor |
| Workflow Orchestration | QMS Orchestrator |

---

## 12. Key Architectural Decisions

### ADR-001: Module Type — STANDALONE

**Context:** QC_LIMS is a GxP laboratory information management system for EU GMP cannabis QC operations.

**Decision:** Module type STANDALONE with code `qc-lims`.

**Rationale:**
1. No existing BMAD module covers laboratory operations or GMP compliance
2. The domain is entirely novel within BMAD ecosystem
3. Extension to Core would couple unrelated concerns
4. Global would impose GMP features on all BMAD users

**Consequences:** Independent installation, full control, can become base for future LIMS extensions.

**Validated by:** First Principles Analysis + Party Mode (GMP Auditor, Product Manager, Frontend Dev, UX Designer).

---

### ADR-002: Scan → Context Architecture

**Context:** Sample identification is the most frequent user action and the primary source of data entry errors.

**Decision:** Barcode scan triggers full context loading (pending tests, spec limits, SOP references, instrument status) via single API call — not just sample receipt logging.

**Rationale:**
- Reduces 3 transcriptions to 1 scan (eliminates logbook → Excel → COA form copying)
- ALCOA++ Attributable: scan event logged with session, timestamp, user
- Implementation: single SQLAlchemy joinedload query, no extra architecture

---

### ADR-003: No Time Pressure by Design

**Context:** QC laboratory work requires accuracy, not speed. Countdown timers create anxiety that leads to errors.

**Decision:** ONLY timer in the system is the 15-minute session inactivity auto-logout. OOS investigations, testing workflows, and approval gates have NO visible countdown timers.

**Rationale:**
- QC work requires care and accuracy; timers create pressure
- Regulatory deadlines (24h Phase I) tracked in backend, visible as status ("Day 1"), not countdown
- Aligns with Emotional Response: Calm, Focused, Professional

---

### ADR-004: Progressive Review — No 'Submit' Buttons

**Context:** Traditional LIMS require explicit "Submit for Review" actions, creating bottlenecks where reviewers wait idly.

**Decision:** Results are live. Reviewer sees them as they're entered. Workflow advances automatically when all conditions are met. No 'Submit' button needed.

**Rationale:**
- Cuts COA turnaround time 40-60%
- Compliance maintained: full audit trail of every keystroke and auto-save
- The system knows when review conditions are met — doesn't need to be told

---

### ADR-005: Multi-Agent Architecture (5 Agents)

**Context:** Domain requires distinct expertise: GMP regulation, CAPA investigation, SOP drafting, risk assessment, workflow orchestration.

**Decision:** 5 specialized agents with defined roles, communication styles, and memory profiles.

**Rationale:**
- Single agent cannot span regulatory, investigative, drafting, and risk domains credibly
- Each agent has focused workflows and clear ownership
- QMS Orchestrator routes queries to the right specialist

---

### ADR-006: Letta RAG — Advisory, Not Directive

**Context:** AI guidance in regulated environments must never replace professional judgment.

**Decision:** Letta RAG guidance is framed as advisory tooltips, not directives. Always cites source SOP. Non-blocking async delivery. User remains decision-maker.

**Rationale:**
- QP authority: "The system advises, I decide"
- Auditability: guidance citations provide traceability
- Regulatory comfort: AI as assistant, not replacement

---

### ADR-007: 3-Tier Resilience for Letta RAG

**Context:** Letta server may be unreachable (network, server issues). The system must not lose critical functionality.

**Decision:** Three-tier degradation:
1. Tier 1: Letta available → full contextual GMP guidance
2. Tier 2: Letta unavailable → cached SOP snippets (re-indexed weekly)
3. Tier 3: Complete offline → static validation rules (spec limits, required fields) still function

**Rationale:**
- Audit trail and data entry must work regardless of AI availability
- GMP guidance is additive value, not critical path blocker
- Cached snippets provide SOP reference without dynamic LLM

---

### ADR-008: Handoff Relay Model

**Context:** Laboratory workflow involves sequential role handoffs (Analyst → Supervisor → Manager → QP). Latency between handoffs is a quality indicator.

**Decision:** Each handoff triggers event → audit trail entry → notification to next role. Handoff gaps >4 hours flagged for scrutiny.

**Rationale:**
- Supervisor responsiveness is a process control metric
- Regulatory: Annex 11 requires 'timely' review — gap tracking provides evidence
- Event-driven architecture is lightweight, scalable, auditable

---

*End of Document.*

**Next Steps (Module Brief Workflow):**
- Step 9: Workflows (formalize BMAD workflow specs for Sample Lifecycle, COA, OOS)
- Step 10: Tools (define tool architecture)
- Step 11: Scenarios (user interaction scenarios)
- Step 12: Creative (creative additions)
- Step 13: Review (module brief review)
- Step 14: Finalize (complete module brief)

**Then:** Create Module steps (scaffold, agents, workflows, docs, config, validation).
