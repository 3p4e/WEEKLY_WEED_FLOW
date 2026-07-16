"""
Sample Lifecycle Service for LIMS sample management.

Per QCSOP 011-A01: SP-06 trigger cascade that auto-generates SP-07/08/09 child samples.

Manages sample creation, parent-child relationships, and batch initialization.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sample import Sample, SamplingPointType, SampleStatus
from app.models.audit import AuditEntry, AuditAction
from app.services.barcode_service import generate_sample_id, generate_sub_batch_code
from app.services.sampling_plan_service import (
    get_sampling_plan,
    calculate_sample_size,
    validate_and_calculate_sample_size
)

if TYPE_CHECKING:
    from app.models.sampling_plan import SamplingPlan


async def create_sample(
    db: AsyncSession,
    sample_id: str,
    batch_id: str | None,
    material_code: str,
    material_name_en: str,
    material_name_mk: str,
    sampled_by_id: uuid.UUID,
    sp_type: str | None = None,
    parent_id: uuid.UUID | None = None,
    planned_quantity: int | None = None,
    sampling_plan_id: uuid.UUID | None = None,
    location: str | None = None,
    quantity: float | None = None,
    quantity_unit: str | None = None,
    sub_batch_code: str | None = None,
) -> Sample:
    """
    Create a new sample record.
    
    Args:
        db: Database session
        sample_id: Unique sample identifier (PP-SMP-YYYY-NNNN)
        batch_id: Associated production batch identifier
        material_code: Material code
        material_name_en: Material name (English)
        material_name_mk: Material name (Macedonian)
        sampled_by_id: User ID who collected the sample
        sp_type: Sampling point type (SP_06, SP_07, SP_08, SP_09)
        parent_id: Parent sample ID for child samples
        planned_quantity: Planned sample size per formula
        sampling_plan_id: Reference to sampling plan used
        location: Storage location
        quantity: Sample quantity collected
        quantity_unit: Unit of quantity
        sub_batch_code: Sub-batch division code
    
    Returns:
        Created Sample instance
    """
    sample = Sample(
        sample_id=sample_id,
        batch_id=batch_id,
        sample_type="RAW_MATERIAL",  # Default, can be overridden
        material_code=material_code,
        material_name_en=material_name_en,
        material_name_mk=material_name_mk,
        sampling_date=datetime.now(timezone.utc),
        sampled_by_id=sampled_by_id,
        status=SampleStatus.COLLECTED.value,
        sp_type=sp_type,
        parent_id=parent_id,
        planned_quantity=planned_quantity,
        sampling_plan_id=sampling_plan_id,
        location=location,
        quantity=quantity,
        quantity_unit=quantity_unit,
        sub_batch_code=sub_batch_code,
    )
    
    db.add(sample)
    await db.flush()  # Get ID assigned
    
    return sample


async def log_sample_creation_audit(
    db: AsyncSession,
    sample: Sample,
    user_id: uuid.UUID,
    user_full_name: str,
    ip_address: str = "127.0.0.1",
    session_id: str = "system",
) -> AuditEntry:
    """
    Log sample creation to audit trail.
    
    Args:
        db: Database session
        sample: Created sample instance
        user_id: User who created the sample
        user_full_name: User's full name for audit
        ip_address: Client IP address
        session_id: Session identifier
    
    Returns:
        Created AuditEntry instance
    """
    audit_entry = AuditEntry(
        user_id=user_id,
        user_full_name=user_full_name,
        action=AuditAction.CREATE.value,
        record_type="sample",
        record_id=str(sample.id),
        record_identifier=sample.sample_id,
        field_name=None,
        old_value=None,
        new_value=f"Created {sample.sp_type or 'sample'} for batch {sample.batch_id}",
        reason="Sample creation per sampling plan",
        ip_address=ip_address,
        session_id=session_id,
    )
    
    db.add(audit_entry)
    await db.flush()
    
    return audit_entry


async def create_sp06_and_children(
    db: AsyncSession,
    batch_id: str,
    batch_size: int,
    material_code: str,
    material_name_en: str,
    material_name_mk: str,
    sampled_by_id: uuid.UUID,
    sampling_plan_id: uuid.UUID | None = None,
    user_full_name: str = "System",
    ip_address: str = "127.0.0.1",
    session_id: str = "system",
) -> dict:
    """
    Create SP-06 sample and auto-generate SP-07/08/09 child samples.
    
    Per QCSOP 011-A01: When SP-06 is received, automatically create child
    samples for in-process control (SP-07, SP-08) and finished product (SP-09).
    
    Args:
        db: Database session
        batch_id: Production batch identifier
        batch_size: Number of units in batch (N)
        material_code: Material code
        material_name_en: Material name (English)
        material_name_mk: Material name (Macedonian)
        sampled_by_id: User ID receiving the batch
        sampling_plan_id: Optional sampling plan ID (will be looked up if None)
        user_full_name: User's full name for audit logging
        ip_address: Client IP address for audit
        session_id: Session ID for audit
    
    Returns:
        Dictionary with created samples:
        {
            "sp06": Sample,
            "sp07": Sample | None,
            "sp08": Sample | None,
            "sp09": Sample | None,
            "sample_size": int
        }
    
    Raises:
        ValueError: If no active sampling plan exists for the material
    """
    # Get sampling plan if not provided
    if sampling_plan_id is None:
        plan = await get_sampling_plan(db, material_code)
        if plan is None:
            # Log blocked SP-06 attempt to audit trail (B-01 fix)
            audit_entry = AuditEntry(
                action=AuditAction.BLOCKED,
                record_type="sample",
                record_id=str(uuid.uuid4()),
                field_name="sp06_blocked",
                new_value=f"Missing sampling plan for material '{material_code}'",
                user_id=str(sampled_by_id),
                user_full_name=user_full_name,
                ip_address=ip_address,
                session_id=session_id,
            )
            db.add(audit_entry)
            await db.flush()
            raise ValueError(
                f"No active sampling plan found for material '{material_code}'. "
                f"SP-06 receive blocked per QCSOP 011-A01."
            )
        sampling_plan_id = plan.id
    else:
        from app.models.sampling_plan import SamplingPlan
        plan = await db.get(SamplingPlan, sampling_plan_id)
        if plan is None:
            raise ValueError(f"Sampling plan {sampling_plan_id} not found")
    
    # Calculate sample size using ROUNDUP(√N×1.5)
    sample_size = calculate_sample_size(batch_size)
    
    # Create SP-06 (parent reception sample)
    sp06_sample_id = await generate_sample_id(db)
    sp06 = await create_sample(
        db=db,
        sample_id=sp06_sample_id,
        batch_id=batch_id,
        material_code=material_code,
        material_name_en=material_name_en,
        material_name_mk=material_name_mk,
        sampled_by_id=sampled_by_id,
        sp_type=SamplingPointType.SP_06.value,
        sampling_plan_id=sampling_plan_id,
        planned_quantity=sample_size,
        location="QC Receiving",
    )
    
    # Log SP-06 creation
    await log_sample_creation_audit(
        db=db,
        sample=sp06,
        user_id=sampled_by_id,
        user_full_name=user_full_name,
        ip_address=ip_address,
        session_id=session_id,
    )
    
    # Create child samples per sampling plan
    children = {
        "sp06": sp06,
        "sp07": None,
        "sp08": None,
        "sp09": None,
        "sample_size": sample_size,
    }
    
    # SP-07: In-process control (during drying)
    if plan.sp_07_required:
        sp07_sample_id = await generate_sample_id(db)
        sp07 = await create_sample(
            db=db,
            sample_id=sp07_sample_id,
            batch_id=batch_id,
            material_code=material_code,
            material_name_en=material_name_en,
            material_name_mk=material_name_mk,
            sampled_by_id=sampled_by_id,
            sp_type=SamplingPointType.SP_07.value,
            parent_id=sp06.id,
            sampling_plan_id=sampling_plan_id,
            planned_quantity=sample_size,
            location="QC Lab - IPC Drying",
        )
        await log_sample_creation_audit(
            db=db,
            sample=sp07,
            user_id=sampled_by_id,
            user_full_name=user_full_name,
            ip_address=ip_address,
            session_id=session_id,
        )
        children["sp07"] = sp07
    
    # SP-08: In-process control (during curing)
    if plan.sp_08_required:
        sp08_sample_id = await generate_sample_id(db)
        sp08 = await create_sample(
            db=db,
            sample_id=sp08_sample_id,
            batch_id=batch_id,
            material_code=material_code,
            material_name_en=material_name_en,
            material_name_mk=material_name_mk,
            sampled_by_id=sampled_by_id,
            sp_type=SamplingPointType.SP_08.value,
            parent_id=sp06.id,
            sampling_plan_id=sampling_plan_id,
            planned_quantity=sample_size,
            location="QC Lab - IPC Curing",
        )
        await log_sample_creation_audit(
            db=db,
            sample=sp08,
            user_id=sampled_by_id,
            user_full_name=user_full_name,
            ip_address=ip_address,
            session_id=session_id,
        )
        children["sp08"] = sp08
    
    # SP-09: Finished product (packaging)
    if plan.sp_09_required:
        sp09_sample_id = await generate_sample_id(db)
        sp09 = await create_sample(
            db=db,
            sample_id=sp09_sample_id,
            batch_id=batch_id,
            material_code=material_code,
            material_name_en=material_name_en,
            material_name_mk=material_name_mk,
            sampled_by_id=sampled_by_id,
            sp_type=SamplingPointType.SP_09.value,
            parent_id=sp06.id,
            sampling_plan_id=sampling_plan_id,
            planned_quantity=sample_size,
            location="QC Lab - Finished Product",
        )
        await log_sample_creation_audit(
            db=db,
            sample=sp09,
            user_id=sampled_by_id,
            user_full_name=user_full_name,
            ip_address=ip_address,
            session_id=session_id,
        )
        children["sp09"] = sp09
    
    await db.commit()
    
    return children


# ── P2-E2: Foreign Matter Pre-test Gate ──

FM_LIMIT_PCT = 2.0  # Foreign matter limit per QCSOP


def validate_fm_pretest(fm_value: float) -> tuple[bool, str]:
    """
    Validate Foreign Matter pre-test result.
    
    Per P2-E2: FM test must pass (≤2.0%) before SP-06 sampling proceeds.
    
    Args:
        fm_value: Foreign Matter result (% w/w)
    
    Returns:
        Tuple of (passed, message)
    """
    if fm_value <= FM_LIMIT_PCT:
        return True, f"FM pre-test PASSED: {fm_value}% ≤ {FM_LIMIT_PCT}%"
    else:
        return False, f"FM pre-test FAILED: {fm_value}% > {FM_LIMIT_PCT}% limit"


async def record_fm_pretest(
    db: AsyncSession,
    sample_id: str,
    fm_value: float,
    tested_by_id: uuid.UUID,
) -> Sample:
    """
    Record FM pre-test result and validate against limit.
    
    Args:
        db: Database session
        sample_id: Sample ID (PP-SMP-YYYY-NNNN)
        fm_value: Foreign Matter result (% w/w)
        tested_by_id: User performing the test
    
    Returns:
        Updated Sample
    
    Raises:
        ValueError: If FM exceeds 2.0% limit (blocks SP-06)
    """
    from sqlalchemy import select
    
    stmt = select(Sample).where(Sample.sample_id == sample_id)
    result = await db.execute(stmt)
    sample = result.scalar_one_or_none()
    
    if sample is None:
        raise ValueError(f"Sample {sample_id} not found")
    
    # Validate FM result
    passed, message = validate_fm_pretest(fm_value)
    
    sample.fm_pretest_value = fm_value
    sample.fm_pretest_passed = passed
    sample.fm_pretest_date = datetime.now(timezone.utc)
    
    if not passed:
        await db.flush()
        raise ValueError(
            f"FM Pre-test failed: Foreign Matter {fm_value}% exceeds 2.0% limit. "
            f"SP-06 sampling blocked. Deviation must be raised and QP notified."
        )
    
    await db.flush()
    return sample


# ── P2-E3: Multi-day Packaging Cascade ──

HMA_LOD_LIMIT = 10.0  # High Moisture Alert LOD limit


def validate_hma_pretest(lod_readings: list[float]) -> tuple[bool, float, str]:
    """
    Validate HMA (High Moisture Alert) pre-gate.
    
    Per P2-E3: Requires ≥3 LOD readings, all ≤10.0%
    
    Args:
        lod_readings: List of LOD (Loss on Drying) readings (%)
    
    Returns:
        Tuple of (passed, max_reading, message)
    """
    if len(lod_readings) < 3:
        return False, max(lod_readings) if lod_readings else 0.0, \
               f"HMA pre-gate requires ≥3 readings, got {len(lod_readings)}"
    
    max_lod = max(lod_readings)
    
    if all(r <= HMA_LOD_LIMIT for r in lod_readings):
        return True, max_lod, f"HMA pre-gate PASSED: all readings ≤ {HMA_LOD_LIMIT}%"
    else:
        return False, max_lod, f"HMA pre-gate FAILED: max reading {max_lod}% > {HMA_LOD_LIMIT}%"


def get_analytical_panel_for_day(packaging_day: int, hma_passed: bool) -> list[str]:
    """
    Get analytical test panel based on packaging day and HMA result.
    
    Per P2-E3:
    - Day 1: Full panel
    - Day 2+ with HMA passed (LOD≤10.0%): Reduced panel (potency dupes, LOD dupes, retention)
    - Day 2+ with HMA failed (LOD>10.0%): MAJOR deviation
    
    Args:
        packaging_day: Day number (1, 2, 3, ...)
        hma_passed: Whether HMA pre-gate passed
    
    Returns:
        List of test names to perform
    """
    if packaging_day == 1:
        # Full panel for Day 1
        return [
            "Identity",
            "Loss on Drying",
            "Foreign Matter",
            "THC Content",
            "CBD Content",
            "Total Cannabinoids",
            "TAMC",
            "TYMC",
            "Specified Micro-organisms",
        ]
    
    # Day 2+ with HMA passed
    if hma_passed:
        return [
            "THC Content (duplicate)",
            "CBD Content (duplicate)",
            "Loss on Drying (duplicate)",
            "Retention Sample",
        ]
    
    # Day 2+ with HMA failed - should not reach here (raises error before)
    return []


async def create_multi_day_packaging_samples(
    db: AsyncSession,
    batch_id: str,
    packaging_day: int,
    lod_readings: list[float],
    material_code: str,
    material_name_en: str,
    material_name_mk: str,
    sampled_by_id: uuid.UUID,
    sampling_plan_id: uuid.UUID | None = None,
) -> dict:
    """
    Create samples for multi-day packaging with HMA pre-gate.
    
    Per P2-E3:
    1. Validate HMA pre-gate (≥3 readings, all LOD≤10.0%)
    2. If HMA passes, proceed with reduced panel for Day 2+
    3. If HMA fails (LOD>10.0%), raise MAJOR deviation
    
    Args:
        db: Database session
        batch_id: Production batch identifier
        packaging_day: Day number (1, 2, 3, ...)
        lod_readings: List of LOD readings for HMA validation
        material_code: Material code
        material_name_en: Material name (English)
        material_name_mk: Material name (Macedonian)
        sampled_by_id: User ID
        sampling_plan_id: Optional sampling plan
    
    Returns:
        Dictionary with created samples and panel info
    
    Raises:
        ValueError: If HMA fails (LOD>10.0% on Day 2+)
    """
    # Validate HMA pre-gate (required for all days)
    hma_passed, max_lod, message = validate_hma_pretest(lod_readings)
    
    if packaging_day >= 2 and not hma_passed:
        raise ValueError(
            f"MAJOR DEVIATION: Day {packaging_day} HMA pre-gate failed. "
            f"Maximum LOD {max_lod}% exceeds limit {HMA_LOD_LIMIT}%. "
            f"Production must halt pending QP investigation."
        )
    
    # Get analytical panel
    panel = get_analytical_panel_for_day(packaging_day, hma_passed)
    
    # Create SP-10 sample for Day 2+ packaging
    sample_id = await generate_sample_id(db)
    sample = await create_sample(
        db=db,
        sample_id=sample_id,
        batch_id=batch_id,
        material_code=material_code,
        material_name_en=material_name_en,
        material_name_mk=material_name_mk,
        sampled_by_id=sampled_by_id,
        sp_type=SamplingPointType.SP_10.value,  # Multi-day packaging
        sampling_plan_id=sampling_plan_id,
        packaging_day=packaging_day,
        hma_pretest_passed=hma_passed,
        reduced_panel_applied=(packaging_day >= 2),
        location=f"Packaging Day {packaging_day}",
    )
    
    await db.flush()
    
    return {
        "sample": sample,
        "packaging_day": packaging_day,
        "hma_passed": hma_passed,
        "max_lod": max_lod,
        "analytical_panel": panel,
    }


async def create_sub_batch_samples(
    db: AsyncSession,
    parent_sample_id: uuid.UUID,
    num_divisions: int,
    sampled_by_id: uuid.UUID,
    user_full_name: str = "System",
    ip_address: str = "127.0.0.1",
    session_id: str = "system",
) -> List[Sample]:
    """
    Create sub-batch samples for divided batches.
    
    Per QCSOP 011-A01: When a batch is divided (e.g., potency grades A/B/C),
    create child samples with sub-batch codes (D1, D2, ... D26, DD1, etc.).
    
    Args:
        db: Database session
        parent_sample_id: Parent sample ID (SP-06 or SP-09)
        num_divisions: Number of sub-batches to create
        sampled_by_id: User ID creating sub-batches
        user_full_name: User's full name for audit
        ip_address: Client IP address
        session_id: Session ID
    
    Returns:
        List of created sub-batch samples
    """
    from sqlalchemy import select
    
    # Get parent sample
    parent = await db.get(Sample, parent_sample_id)
    if parent is None:
        raise ValueError(f"Parent sample {parent_sample_id} not found")
    
    sub_batches = []
    
    for i in range(num_divisions):
        sub_batch_code = generate_sub_batch_code(i)
        sample_id = await generate_sample_id(db)
        
        sub_batch = await create_sample(
            db=db,
            sample_id=sample_id,
            batch_id=parent.batch_id,
            material_code=parent.material_code,
            material_name_en=parent.material_name_en,
            material_name_mk=parent.material_name_mk,
            sampled_by_id=sampled_by_id,
            sp_type=parent.sp_type,  # Same type as parent
            parent_id=parent.id,
            sub_batch_code=sub_batch_code,
            sampling_plan_id=parent.sampling_plan_id,
            planned_quantity=parent.planned_quantity,
            location=parent.location,
        )
        
        await log_sample_creation_audit(
            db=db,
            sample=sub_batch,
            user_id=sampled_by_id,
            user_full_name=user_full_name,
            ip_address=ip_address,
            session_id=session_id,
            reason=f"Sub-batch division {sub_batch_code}",
        )
        
        sub_batches.append(sub_batch)
    
    await db.commit()
    
    return sub_batches
