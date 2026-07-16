---
title: 'P2 Sample Lifecycle — SP-06 Triggers, Barcodes, Genealogy, Custody'
type: 'feature'
created: '2026-05-30'
status: 'in-review'
baseline_commit: '7afacdd'
implementation_commit: '2df761d'
context:
  - '{project-root}/instructions/00-sop-index.md'
  - '{project-root}/instructions/03-lims-modules.md'
---

<frozen-after-approval reason="SOP-grounded sample lifecycle implementation per QCSOP 011-A01">

## Intent

**Problem:** QC_LIMS has no sample lifecycle management. Manual sampling plans, no barcode tracking, no chain of custody logging, and no integration between sampling (SP-06) and specification testing (SP-07/08/09). This violates ALCOA++ traceability requirements.

**Approach:** Implement automated SP-06 trigger cascade that generates child samples (SP-07/08/09) with barcodes, maintains product genealogy (IPM-HT→IPM-IN→IPM-DS→IPM-PK), logs custody transfers, and routes potency-graded batches to appropriate processing streams.

## Boundaries & Constraints

**Always:**
- Sample IDs follow PP-SMP-YYYY-NNNN format (QCSOP 011-A01)
- Chain of custody logs every transfer with timestamp + user + signature
- SP-06 arrival triggers automatic SP-07/08/09 creation per sampling plan
- Sampling formula: ROUNDUP(√N×1.5) for sub-batch determination
- Potency grades (A/B/C) calculated via THCA×0.877+THC, ±10% tolerance
- All state changes logged to AuditEntry (ALCOA++)

**Ask First:**
- Should we support multiple sampling plans per material (e.g., different plans for different suppliers)?
- Do we need real-time barcode scanning integration, or manual entry with barcode display?
- Should potency grading trigger automatic workflow routing (A→premium, B→standard, C→extracts)?

**Never:**
- No physical barcode hardware integration (scanners, printers) — generate codes only
- No LIMS-to-lab-instrument integration (HPLC, GC) — manual result entry
- No integration with production scheduling systems

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| SP-06 received | Batch N=100, SP-06 triggers | Create SP-06 sample, auto-generate SP-07/08/09 with n=ROUNDUP(√100×1.5)=15 each | If sampling plan missing → HALT, require plan creation |
| Custody transfer | User A → User B, location change | Log transfer with timestamps, both signatures, reason | If user lacks custody permission → 403, log attempt |
| Potency test complete | THC=18%, THCA=2%, Grade B | Calculate total THC=18+(2×0.877)=19.75%, grade B (±10%), route to standard processing | If potency out of spec → flag for OOS, block routing |
| Sub-batch division | Grade A batch, D1/D2 codes | Create child samples D1, D2 with linked parent, independent custody chains | If division count exceeds 26 → use D1-D26, then DD1-DD26 |
| Missing SP-06 | Try to create SP-07 without SP-06 | Block creation, require SP-06 parent, log violation attempt | Clear error: "SP-06 required as parent for all QC samples" |

</frozen-after-approval>

## Code Map

- `models/sample.py` -- Sample model with SP type, parent/child relationships, custody chain
- `models/custody.py` -- ChainOfCustody model for transfer logging
- `services/sample_lifecycle_service.py` -- SP-06 trigger cascade, child sample generation
- `services/barcode_service.py` -- PP-SMP-YYYY-NNNN generation, QR code rendering
- `services/sampling_plan_service.py` -- Sampling formula implementation, plan enforcement
- `services/genealogy_service.py` -- Product genealogy tracking (IPM-HT→IPM-IN→IPM-DS→IPM-PK)
- `services/potency_service.py` -- THCA×0.877+THC calculation, grade assignment
- `api/samples.py` -- CRUD, custody transfer, potency calculation endpoints

## Tasks & Acceptance

**Execution:**
- [x] `models/sample.py` -- Extend Sample model with SP type enum, parent_id FK, sub_batch_code, potency_grade, sample_status -- RATIONALE: Core sample tracking per QCSOP 011-A01
- [x] `models/custody.py` -- Create ChainOfCustody model with sample_id, from_user, to_user, timestamp, location, signature_hash -- RATIONALE: ALCOA++ custody logging
- [x] `services/barcode_service.py` -- Implement generate_sample_id() → PP-SMP-YYYY-NNNN with collision check, generate_qr_code() for label printing -- RATIONALE: Unique sample identification
- [x] `services/sampling_plan_service.py` -- Implement calculate_sample_size(N) → ROUNDUP(√N×1.5), validate against min/max limits -- RATIONALE: SOP-compliant sampling
- [x] `services/sample_lifecycle_service.py` -- Implement create_sp06_and_children() that creates SP-06 then auto-generates SP-07/08/09 with calculated sizes -- RATIONALE: SP-06 trigger cascade
- [x] `services/potency_service.py` -- Implement calculate_potency(thc, thca) → total_thc, assign_grade(total_thc, spec_limits) → A/B/C -- RATIONALE: Potency grading per QCSP 003
- [x] `services/genealogy_service.py` -- Implement track_lineage(parent_sample, child_samples), get_ancestry(sample_id), get_progeny(sample_id) -- RATIONALE: Product genealogy for recalls
- [x] `api/samples.py` -- Add POST /samples/sp06-receive, POST /samples/{id}/custody-transfer, GET /samples/{id}/genealogy, POST /samples/{id}/potency-grade -- RATIONALE: API surface for lifecycle operations

**Acceptance Criteria:**
- Given a batch with N=144 units, when SP-06 is received, then SP-07/08/09 are auto-created with sample size ROUNDUP(√144×1.5)=18 each
- Given a custody transfer from Analyst A to Analyst B, when transfer is logged, then ChainOfCustody entry exists with both user IDs, timestamps, and digital signatures
- Given THC=15% and THCA=3%, when potency is calculated, then total=15+(3×0.877)=17.63% and grade is assigned per ±10% tolerance bands
- Given a Grade A batch requiring division, when sub-batch codes are assigned, then D1, D2... are created with independent sample IDs linked to parent
- Given a missing sampling plan, when SP-06 receive is attempted, then operation is blocked with clear error and logged to AuditEntry
- Given any sample state change, when change is persisted, then corresponding AuditEntry is created with user, timestamp, old/new values
- Given a sample with parent and children, when genealogy API is called, then full ancestry and progeny are returned in tree structure
- Given a potency out of specification, when grade is assigned, then sample is flagged for OOS investigation and routing is blocked

## Design Notes

**SP-06 Trigger Cascade:**
```python
# When SP-06 received for batch
def create_sp06_and_children(batch_id: UUID, sampling_plan_id: UUID):
    sp06 = create_sample(type=SP_06, batch_id=batch_id)
    N = get_batch_size(batch_id)
    n = calculate_sample_size(N)  # ROUNDUP(√N×1.5)
    
    for sp_type in [SP_07, SP_08, SP_09]:
        create_sample(
            type=sp_type,
            parent_id=sp06.id,
            planned_quantity=n,
            barcode=generate_sample_id()
        )
```

**Potency Grade Calculation:**
```python
def calculate_potency(thc: float, thca: float) -> float:
    return thc + (thca * 0.877)  # Decarboxylation factor

def assign_grade(total_thc: float, target: float, tolerance: float = 0.10) -> str:
    if total_thc >= target * (1 - tolerance) and total_thc <= target * (1 + tolerance):
        return "B"  # Standard
    elif total_thc > target * (1 + tolerance):
        return "A"  # Premium
    else:
        return "C"  # Extracts
```

## Verification

**Commands:**
- `cd /a0/usr/projects/qc_lims && python -c "from backend.app.services.barcode_service import generate_sample_id; print(generate_sample_id())"` -- expected: ID matching PP-SMP-YYYY-NNNN pattern
- `python -c "from backend.app.services.sampling_plan_service import calculate_sample_size; print(calculate_sample_size(100))"` -- expected: 15 (ROUNDUP(√100×1.5))
- `pytest backend/tests/test_sample_lifecycle.py -v` -- expected: All 8 AC tests passing

**Manual checks (if no CLI):**
- Inspect `models/sample.py` -- Sample model has sp_type, parent_id, potency_grade fields
- Inspect `services/sample_lifecycle_service.py` -- create_sp06_and_children() function exists with cascade logic
- Test custody transfer via API -- POST /samples/{id}/custody-transfer creates ChainOfCustody record
