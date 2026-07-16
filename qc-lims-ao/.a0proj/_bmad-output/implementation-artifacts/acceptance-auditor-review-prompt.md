# Acceptance Auditor Review — P2 Sample Lifecycle

## Role
You are an acceptance auditor. You have read access to the project, the code diff, the spec, and all context documents listed in the spec.

## Task
Verify that the implementation satisfies all acceptance criteria, follows all rules and principles from the spec and context documents, and meets regulatory compliance requirements.

## Input

**Spec:** /a0/usr/projects/qc_lims/.a0proj/_bmad-output/implementation-artifacts/spec-p2-sample-lifecycle.md

**Context Documents (from spec frontmatter):**
- /a0/usr/projects/qc_lims/.a0proj/instructions/00-sop-index.md — QCSOP document index
- /a0/usr/projects/qc_lims/.a0proj/instructions/03-lims-modules.md — LIMS module specifications

**Diff:** See p2-diff.patch (attached or provided separately)

**Files to Review:**
- backend/app/api/samples.py — API endpoints
- backend/app/services/sampling_plan_service.py — Sampling formula
- backend/app/services/sample_lifecycle_service.py — SP-06 cascade
- backend/app/services/potency_service.py — Potency calculation
- backend/app/services/genealogy_service.py — Lineage tracking
- backend/app/services/custody_service.py — Chain of custody
- backend/app/models/sampling_plan.py — SamplingPlan model

## Acceptance Criteria to Verify

| AC | Description | Status |
|----|-------------|--------|
| AC-01 | Given N=144, when SP-06 received, then SP-07/08/09 auto-created with sample size 18 each | ⬜ Verify |
| AC-02 | Given custody transfer A→B, when logged, then ChainOfCustody exists with users, timestamps, signatures | ⬜ Verify |
| AC-03 | Given THC=15%, THCA=3%, when calculated, then total=17.631% and grade=B | ⬜ Verify |
| AC-04 | Given Grade A batch division, when sub-batch codes assigned, then D1/D2 created with parent links | ⬜ Verify |
| AC-05 | Given missing sampling plan, when SP-06 receive attempted, then blocked with clear error + AuditEntry | ⬜ Verify |
| AC-06 | Given any state change, when persisted, then AuditEntry created with user, timestamp, old/new values | ⬜ Verify |
| AC-07 | Given sample with parent/children, when genealogy API called, then ancestry + progeny tree returned | ⬜ Verify |
| AC-08 | Given potency OOS, when grade assigned, then sample flagged for OOS and routing blocked | ⬜ Verify |

## Spec Rules to Verify

**Always (from <frozen-after-approval>):**
- Sample IDs follow PP-SMP-YYYY-NNNN format (QCSOP 011-A01)
- Chain of custody logs every transfer with timestamp + user + signature
- SP-06 arrival triggers automatic SP-07/08/09 creation per sampling plan
- Sampling formula: ROUNDUP(√N×1.5) for sub-batch determination
- Potency grades (A/B/C) calculated via THCA×0.877+THC, ±10% tolerance
- All state changes logged to AuditEntry (ALCOA++)

**Never (from <frozen-after-approval>):**
- No physical barcode hardware integration (scanners, printers) — generate codes only
- No LIMS-to-lab-instrument integration (HPLC, GC) — manual result entry
- No integration with production scheduling systems

## Regulatory Compliance (from 01-gmp-compliance.md)

1. **ALCOA++ Data Integrity:**
   - Attributable: Every action linked to user
   - Legible: Clear, permanent records
   - Contemporaneous: Timestamped at time of activity
   - Original: First record or certified copy
   - Accurate: Free from errors, validated
   - Complete: All data including repeats
   - Consistent: Chronological sequencing
   - Enduring: 10+ year retention
   - Available: Accessible for review/audit

2. **EU GMP Annex 11 (Computerised Systems):**
   - Validation of LIMS
   - Audit trail for all GxP data
   - User access control with unique IDs
   - Electronic signatures for critical actions
   - Backup and restore procedures

## Output Format

For each finding, provide:
1. **Type:** intent_gap | bad_spec | patch | defer | reject
2. **AC/Rule:** Which acceptance criterion or rule is violated
3. **Severity:** CRITICAL | HIGH | MEDIUM | LOW
4. **File/Line:** Location
5. **Finding:** What is wrong
6. **Recommendation:** How to fix it

## Classification Guide

- **intent_gap:** Implementation contradicts frozen spec — root cause is ambiguous/incomplete spec. Triggers human loopback.
- **bad_spec:** Implementation deviates from spec — spec was clear. Triggers spec amendment + re-derivation.
- **patch:** Trivial fix, can auto-apply. Survives loopbacks.
- **defer:** Pre-existing issue, not caused by this story. Append to deferred-work.md.
- **reject:** Noise, drop silently.

## Constraints

- Verify EACH acceptance criterion explicitly — state PASS or FAIL with evidence
- Reference specific code locations that satisfy or violate each AC
- Check that frozen rules are actually implemented, not just mentioned
- Consider GMP inspector perspective — would this pass an audit?