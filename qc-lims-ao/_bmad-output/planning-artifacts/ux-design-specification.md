---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - /a0/usr/projects/qc_lims/.a0proj/instructions/00-sop-index.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/01-gmp-compliance.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/02-letta-rag-pipeline.md
  - /a0/usr/projects/qc_lims/.a0proj/instructions/03-lims-modules.md
---

# UX Design Specification — QC_LIMS

**Author:** root
**Date:** 2026-05-18

---

## Executive Summary

### Project Vision

Build a modern QMS LIMS for an EU GMP-compliant QC laboratory specializing in dried cannabis flower for medical use. The system serves Purely Plant GmbH (North Macedonia) with bilingual (MK/EN) support, ALCOA++ data integrity, and AI-powered compliance guidance via Letta RAG agents.

### Target Users

- **QC Analyst** — Enters test results, handles samples, runs instruments. Needs fast data entry with validation guards.
- **QC Reviewer** — Verifies analytical results (mandatory 2nd person check). Needs clear comparison views.
- **QC Manager** — Approves results, manages OOS investigations. Needs dashboards and escalation visibility.
- **Qualified Person (QP)** — Digitally signs COAs for batch release. Needs summary views with MFA-gated actions.
- **QA Auditor** — Read-only access for regulatory inspections. Needs complete traceability and export.
- **System Admin** — User management, configuration. Needs secure role management.

### Key Design Challenges

1. **Regulatory Workflow Enforcement** — OOS investigation requires mandatory Phase I → Phase II flow with specific forms, signatures, and timelines. The UI must guide users without allowing skips.
2. **ALCOA++ Data Integrity** — No backdating, overwriting, or deletion. Every correction needs reason + 2nd signature. Compliance must feel natural, not punitive.
3. **Bilingual Everything** — Macedonian primary, English secondary. All labels, errors, dropdowns, and generated PDFs must support both languages.
4. **Role-Based Interface** — Same screens show completely different actions based on role. Analyst sees "enter"; Reviewer sees "verify"; QP sees "release" with MFA.

### Design Opportunities

1. **AI Copilot Panels** — "Ask GMP Expert" embedded alongside forms for real-time SOP citation during OOS investigation.
2. **Sample Lifecycle Visualizer** — Timeline showing where each sample is, who touched it, what's pending.
3. **Smart Dashboards** — Role-aware cards: "3 OOS awaiting Phase II", "5 stability pulls due", "2 instruments overdue".
4. **Progressive Disclosure** — Complex COA review shows summary first, expandable detail for auditors.

### Advanced Elicitation Insights

#### Party Mode Consensus

| Principle | UX Decision | Stakeholders |
|-----------|-------------|--------------|
| Speed + Compliance | High-density grid entry with background audit logging | Dev + Analyst |
| Draft Safety | Auto-save with timestamps, 24h escalation timer | Dev + Auditor |
| Path of Least Resistance | Compliance is default; cheating requires more effort | PM + Auditor |
| Visible Integrity | Inline override badges, expandable lineage | All |
| Immutable Records | Version stack, never replace | Auditor + Dev |

#### Critical UX Decisions

1. **Visible Data Lineage:** Every value shows if it's original, corrected, or verified — inline, without clicks
2. **Context-Aware Language:** MK/EN toggle is ambient (toolbar), persistent per user, and translation keys include workflow context
3. **Guided Compliance:** OOS investigation is a wizard, not a form — with auto-save, escalation timers, and pre-populated checks
4. **Role-Based Interface Density:** Analyst sees minimal chrome, maximum data entry speed. QP sees full context, minimal actions. Auditor sees everything, edits nothing.
5. **Friction by Design:** Digital signature is a deliberate, multi-step ritual — but only for release actions. Data entry is fast and fluid.
6. **Correction as First-Class:** "Amend with reason" is as easy as "Edit" in normal apps — but the reason is captured, versioned, and visible.
7. **Search as Infrastructure:** Global, fast, filterable search is not a feature — it's the backbone of audit readiness.

<!-- UX design content will be appended sequentially through collaborative workflow steps -->

## Core User Experience

### Defining Experience

The QC_LIMS experience centers on **frictionless compliance** — every interaction satisfies ALCOA++ requirements while feeling faster than paper-based alternatives. The system transforms regulatory burden into invisible guardrails.

**Core User Action:** Entering test results at high throughput (50+ results per batch). Grid entry with keyboard navigation, validation as-you-type, and inline attribution on hover.

**Secondary Critical Actions:**
- Sample registration with chain-of-custody tracking
- OOS investigation with guided Phase I → Phase II workflow
- COA review and digital signature for QP release
- Real-time dashboard monitoring for QC Managers

### Platform Strategy

**Primary:** Desktop-first responsive web application (React + TypeScript)
- Full keyboard navigation for data entry speed
- Large screens for dense information display
- Precise input controls (mouse, tab, enter)

**Secondary:** Tablet support for cleanroom/gowning areas
- Touch-friendly sample collection interface
- Simplified views for mobile contexts
- Offline capability with sync for sample logging

**Backend:** FastAPI with PostgreSQL, Qdrant vector DB, Letta agents

### Effortless Interactions

| Interaction | Streamlined UX |
|-------------|----------------|
| Language switching | Ambient toolbar toggle, persistent MK/EN preference |
| Test result entry | Grid entry, tab navigation, validation as you type |
| Audit trail lookup | Inline badges, hover to expand full lineage |
| OOS investigation | Guided wizard, auto-save, manager sees pending queue (no countdowns) |
| Sample search | Global search, 3 seconds, complete timeline |
| COA signature | Full-screen review, checkbox attestation, MFA, sign |
| Correction entry | "Amend" button, reason dropdown, version visible |
| Session security | 15min inactivity timeout, 2min warning countdown only |

### Critical Success Moments

1. **The "3-Second Search"** — User searches for any sample. System returns complete lifecycle — who, when, where, what instrument, all results, all versions, all signatures — in one scrollable timeline.

2. **The Effortless Correction** — User makes data entry error. Clicks "Amend," selects reason from dropdown, enters corrected value. Original preserved, version visible, no admin needed, no guilt.

3. **The Guided OOS** — User finds out-of-spec result. System presents guided wizard with pre-populated checks, auto-save. Manager sees "Pending OOS: 3 investigations, oldest 18 hours" — prioritized queue, not countdown panic. Phase I completes with proper diligence, not time pressure.

4. **The Confident Signature** — QP reviews full-screen COA with all test results visible, scrollable, printable. Checkbox: "I have reviewed all results and confirm compliance." MFA prompt. Signature recorded with hash chain.

### Experience Principles

1. **Compliance as Default** — The path of least resistance is always the compliant path. Non-compliant actions require deliberate effort and documentation.

2. **Visible Integrity** — Data lineage is never hidden. Every value shows its provenance: original, amended, verified, or overridden — inline and immediately accessible.

3. **Streamlined Density** — Information density matches user sophistication. Analysts see minimal chrome, maximum data. QPs see full context. Auditors see everything.

4. **Ambient Bilingualism** — Language is environment, not setting. Toggle is one click, persistent, and translation keys carry workflow context.

5. **Friction by Design** — Only release actions (COA signature, batch approval) carry deliberate friction. Data entry is fast and fluid. The ritual creates meaning.

6. **Search as Infrastructure** — Global, fast, filterable search is not a feature — it's the backbone of audit readiness and daily workflow efficiency.

7. **Correction as First-Class** — Amending data is as easy as editing in consumer apps, but with captured reasons, version stacks, and visible history.

8. **Transparent Automation** — All automated checks, validations, and notifications are surfaced visibly. The user is never unaware of what the system has done or why.

9. **No Time Pressure UX** — Only the session inactivity security timer is visible. Workflows proceed at proper pace for careful, accurate work.

## Desired Emotional Response

### Primary Emotional Goals

**1. Confident and In Control**
Users should feel they are the masters of their work, not subjects of the system. Every automated check, validation, and notification is visible — they know *what* happened, *why*, and that it was correct.

**2. Trusting (of the System)**
The LIMS should feel like a reliable colleague, not a surveillance tool. When they make a correction, the system preserves the original gracefully. When they sign a COA, the system shows them everything they need to feel confident.

**3. Efficient (but not Rushed)**
Streamlined workflows mean less friction, not less time to think. Users feel they can work at their natural pace — careful, accurate, deliberate — without the system slowing them down or rushing them.

**4. Calm and Focused**
No anxiety-inducing countdowns (except security logout). Clean, dense interfaces that match their sophistication. Everything they need is visible; nothing unnecessary distracts.

**5. Proud of Their Work**
When a batch is released, when an OOS is properly investigated, when an audit passes — users should feel professional satisfaction. The system makes their good work visible and defensible.

### Emotional Journey Mapping

| Stage | User | Desired Emotion |
|-------|------|-----------------|
| **First Login** | New analyst | Welcomed, oriented, "I can learn this" |
| **Daily Data Entry** | Experienced analyst | In flow, efficient, trusted |
| **Discovering Error** | Any user | Supported, not punished — "I can fix this properly" |
| **OOS Investigation** | Analyst/Manager | Guided, not pressured — "The system helps me do this right" |
| **COA Signature** | QP | Confident, informed — "I know what I'm signing" |
| **Audit Inspection** | Auditor | Impressed, satisfied — "Everything is here, traceable" |
| **Returning Next Day** | All users | Resuming smoothly — "My work is preserved, I know where I left off" |

### Micro-Emotions

| Positive (Design For) | Negative (Design Against) |
|----------------------|---------------------------|
| Confidence | Confusion — unclear status or next steps |
| Trust | Skepticism — hidden processes or silent failures |
| Control | Helplessness — forced workflows or lockouts |
| Satisfaction | Frustration — unnecessary clicks or slow responses |
| Pride | Anxiety — time pressure or fear of mistakes |
| Belonging | Isolation — unclear who to ask for help |

### Design Implications

| Emotion | UX Choice |
|---------|-----------|
| **Confident** | Inline validation with clear success indicators; visible system checks |
| **Trusting** | Graceful error recovery; "Amend" not "Override"; transparent audit trail |
| **Efficient** | Keyboard-driven grid entry; global search; minimal modal dialogs |
| **Calm** | No countdown timers (except security); status not urgency; clean density |
| **Proud** | Completion acknowledgments; clear audit trail export; professional COA output |

### Emotional Design Principles

1. **Visibility Builds Trust** — Every automated action is surfaced. Users trust what they can see.
2. **Graceful Recovery** — Errors and corrections are handled with dignity, not punishment.
3. **Respect for Expertise** — The interface adapts to user sophistication; novices get guidance, experts get speed.
4. **Professional Satisfaction** — The system makes good work look good. Completed tasks feel complete.
5. **No Anxiety by Design** — Timers only for security. Workflows support careful accuracy, not rushing.
