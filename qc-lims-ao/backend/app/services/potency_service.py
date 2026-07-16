"""
Potency Service for LIMS cannabinoid testing and grading.

Per QCSP 003: THCA×0.877+THC formula for total THC calculation.
Per QCSOP 011-A01: Potency grades (A/B/C) with ±10% tolerance bands.

Handles potency calculation, grade assignment, and OOS flagging.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sample import Sample, PotencyGrade, SampleStatus
from app.models.audit import AuditEntry, AuditAction

if TYPE_CHECKING:
    from app.models.user import User


def calculate_potency(thc: float, thca: float) -> float:
    """
    Calculate total potency using THCA×0.877+THC formula.
    
    Per QCSP 003: Accounts for decarboxylation factor (0.877) converting
    THCA to THC equivalent. This is the standard calculation for total
    psychoactive potency.
    
    Args:
        thc: Measured THC content (% w/w)
        thca: Measured THCA content (% w/w)
    
    Returns:
        Total THC potency (% w/w) including decarboxylated THCA
    
    Examples:
        >>> calculate_potency(15.0, 3.0)
        17.631  # 15 + (3 × 0.877) = 17.631
        >>> calculate_potency(18.0, 2.0)
        19.754  # 18 + (2 × 0.877) = 19.754
    """
    DECARBOXYLATION_FACTOR = 0.877
    total_thc = thc + (thca * DECARBOXYLATION_FACTOR)
    return round(total_thc, 3)


def assign_grade(
    total_thc: float,
    target: float,
    tolerance: float = 0.10
) -> str:
    """
    Assign potency grade (A/B/C) based on total THC vs target.
    
    Per QCSOP 011-A01 and QCSP 003:
    - Grade A (Premium): > target × 1.10 (exceeds tolerance)
    - Grade B (Standard): target × 0.90 to target × 1.10 (within tolerance)
    - Grade C (Extracts): < target × 0.90 (below tolerance)
    
    Args:
        total_thc: Calculated total THC potency (% w/w)
        target: Target potency (% w/w)
        tolerance: Tolerance band (default 10% = 0.10)
    
    Returns:
        Potency grade: "A", "B", or "C"
    
    Raises:
        ValueError: If target is zero or negative
    
    Examples:
        >>> assign_grade(19.75, 18.0, 0.10)  # > 19.8 (110%)
        "A"  # Premium grade
        >>> assign_grade(17.63, 18.0, 0.10)  # 16.2-19.8 (90-110%)
        "B"  # Standard grade
        >>> assign_grade(15.5, 18.0, 0.10)   # < 16.2 (<90%)
        "C"  # Extracts grade
    """
    if target <= 0:
        raise ValueError(f"Target potency must be positive, got {target}")
    
    lower_bound = target * (1 - tolerance)
    upper_bound = target * (1 + tolerance)
    
    # Use epsilon for float boundary comparisons (M-01 fix)
    EPSILON = 0.001
    if total_thc > upper_bound and not math.isclose(total_thc, upper_bound, abs_tol=EPSILON):
        return PotencyGrade.GRADE_A.value  # Premium
    elif total_thc >= lower_bound or math.isclose(total_thc, lower_bound, abs_tol=EPSILON):
        return PotencyGrade.GRADE_B.value  # Standard
    else:
        return PotencyGrade.GRADE_C.value  # Extracts


def is_potency_out_of_spec(
    total_thc: float,
    target: float,
    tolerance: float = 0.10
) -> bool:
    """
    Check if potency is outside acceptable specification limits.
    
    Args:
        total_thc: Calculated total THC potency (% w/w)
        target: Target potency (% w/w)
        tolerance: Tolerance band (default 10% = 0.10)
    
    Returns:
        True if potency is out of specification (Grade A or C),
        False if within specification (Grade B)
    """
    grade = assign_grade(total_thc, target, tolerance)
    return grade != PotencyGrade.GRADE_B.value


async def update_sample_potency(
    db: AsyncSession,
    sample_id: uuid.UUID,
    thc: float,
    thca: float,
    target_thc: float,
    tested_by_id: uuid.UUID,
    user_full_name: str,
    tolerance: float = 0.10,
    ip_address: str = "127.0.0.1",
    session_id: str = "system",
) -> dict:
    """
    Update sample with potency calculation and grade assignment.
    
    Args:
        db: Database session
        sample_id: Sample UUID to update
        thc: Measured THC content (% w/w)
        thca: Measured THCA content (% w/w)
        target_thc: Target THC potency (% w/w)
        tested_by_id: User ID performing the test
        user_full_name: User's full name for audit
        tolerance: Tolerance band (default 10%)
        ip_address: Client IP address
        session_id: Session ID
    
    Returns:
        Dictionary with:
        - sample: Updated Sample instance
        - total_thc: Calculated total potency
        - grade: Assigned grade (A/B/C)
        - oos: Boolean indicating if out of specification
        - blocked: Boolean indicating if routing is blocked
    """
    # Get sample
    sample = await db.get(Sample, sample_id)
    if sample is None:
        raise ValueError(f"Sample {sample_id} not found")
    
    # Calculate potency
    total_thc = calculate_potency(thc, thca)
    
    # Assign grade
    grade = assign_grade(total_thc, target_thc, tolerance)
    
    # Check OOS
    is_oos = is_potency_out_of_spec(total_thc, target_thc, tolerance)
    
    # Update sample
    old_grade = sample.potency_grade
    sample.potency_grade = grade
    sample.status = SampleStatus.TESTED.value
    
    # OOS handling: flag sample and block routing
    if is_oos:
        # Note: OOS investigation record would be created by OOS service
        # For now, we just flag the sample
        sample.status = SampleStatus.REJECTED.value  # Block routing
    
    await db.flush()
    
    # Log to audit trail
    audit_entry = AuditEntry(
        user_id=tested_by_id,
        user_full_name=user_full_name,
        action=AuditAction.UPDATE.value,
        record_type="sample",
        record_id=str(sample.id),
        record_identifier=sample.sample_id,
        field_name="potency_grade",
        old_value=old_grade or "None",
        new_value=grade,
        reason=f"Potency test: THC={thc}%, THCA={thca}%, Total={total_thc}%, Target={target_thc}%",
        ip_address=ip_address,
        session_id=session_id,
    )
    db.add(audit_entry)
    
    # Log OOS if applicable
    if is_oos:
        oos_audit = AuditEntry(
            user_id=tested_by_id,
            user_full_name=user_full_name,
            action=AuditAction.REJECT.value,
            record_type="sample",
            record_id=str(sample.id),
            record_identifier=sample.sample_id,
            field_name="status",
            old_value=SampleStatus.TESTED.value,
            new_value=SampleStatus.REJECTED.value,
            reason=f"OOS: Potency {total_thc}% outside tolerance band ({target_thc*(1-tolerance):.1f}-{target_thc*(1+tolerance):.1f}%)",
            ip_address=ip_address,
            session_id=session_id,
        )
        db.add(oos_audit)
    
    await db.commit()
    
    return {
        "sample": sample,
        "total_thc": total_thc,
        "grade": grade,
        "oos": is_oos,
        "blocked": is_oos,  # OOS blocks routing
    }


async def get_potency_grade_description(grade: str) -> dict:
    """
    Get human-readable description of potency grade.
    
    Args:
        grade: Potency grade (A, B, or C)
    
    Returns:
        Dictionary with grade description in English and Macedonian
    """
    descriptions = {
        "A": {
            "en": "Premium Grade - High potency, suitable for premium flower products",
            "mk": "Премиум квалитет - Висока јачина, погодно за премиум цветни производи",
            "routing": "Premium processing stream",
        },
        "B": {
            "en": "Standard Grade - Within specification, standard flower products",
            "mk": "Стандард квалитет - Во рамки на спецификацијата, стандардни цветни производи",
            "routing": "Standard processing stream",
        },
        "C": {
            "en": "Extracts Grade - Below specification, suitable for extraction",
            "mk": "Квалитет за екстракта - Под спецификацијата, погодно за екстракција",
            "routing": "Extracts processing stream",
        },
    }
    
    return descriptions.get(grade, {
        "en": "Unknown grade",
        "mk": "Непознат квалитет",
        "routing": "Unknown",
    })
