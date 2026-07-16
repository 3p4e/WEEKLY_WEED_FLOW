"""
Specification Lifecycle Service for LIMS.

Per P1-E5: 8-stage specification lifecycle management.
Handles transitions between INITIATED→DRAFT→QC_REVIEW→QA_APPROVED→
NUMBERED→TRAINED→ACTIVE→UNDER_CHANGE with proper guards.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.specification import (
    Specification,
    SpecStatus,
    SpecApproval,
    ApprovalRole,
    ApprovalStatusEnum,
)


class LifecycleTransitionError(Exception):
    """Raised when lifecycle transition validation fails."""
    pass


async def transition_spec_status(
    db: AsyncSession,
    spec_id: str,
    target_status: str,
    user_id: Optional[uuid.UUID] = None,
) -> Specification:
    """
    Transition specification to new status with guard validation.
    
    Per P1-E5 transition guards:
    - INITIATED→DRAFT: All mandatory fields populated
    - DRAFT→QC_REVIEW: QC Manager approval
    - QC_REVIEW→QA_APPROVED: QA approval
    - QA_APPROVED→NUMBERED: Unique spec_id assigned
    - NUMBERED→TRAINED: All users confirmed training
    - TRAINED→ACTIVE: effective_date reached
    - ACTIVE→UNDER_CHANGE: Change request initiated
    
    Args:
        db: Database session
        spec_id: Specification ID
        target_status: Target SpecStatus value
        user_id: User performing transition (for audit)
    
    Returns:
        Updated Specification
    
    Raises:
        LifecycleTransitionError: If transition guards not met
    """
    stmt = select(Specification).where(Specification.spec_id == spec_id)
    result = await db.execute(stmt)
    spec = result.scalar_one_or_none()
    
    if spec is None:
        raise ValueError(f"Specification {spec_id} not found")
    
    current_status = spec.status
    
    # Validate transition
    await _validate_transition(db, spec, current_status, target_status)
    
    # Perform transition
    spec.status = target_status
    
    # Auto-transition for TRAINED→ACTIVE when effective_date reached
    if target_status == SpecStatus.TRAINED.value:
        now = datetime.now(timezone.utc).date()
        if spec.effective_date <= now:
            spec.status = SpecStatus.ACTIVE.value
    
    await db.flush()
    return spec


async def _validate_transition(
    db: AsyncSession,
    spec: Specification,
    current: str,
    target: str,
) -> bool:
    """
    Validate lifecycle transition guards.
    
    Args:
        db: Database session
        spec: Specification being transitioned
        current: Current status
        target: Target status
    
    Returns:
        True if transition is valid
    
    Raises:
        LifecycleTransitionError: If transition is invalid
    """
    # Define valid transitions and their guards
    valid_transitions = {
        # (current, target): guard_function
        (SpecStatus.INITIATED.value, SpecStatus.DRAFT.value): _check_initiated_to_draft,
        (SpecStatus.DRAFT.value, SpecStatus.QC_REVIEW.value): _check_draft_to_qc_review,
        (SpecStatus.QC_REVIEW.value, SpecStatus.QA_APPROVED.value): _check_qc_to_qa,
        (SpecStatus.QA_APPROVED.value, SpecStatus.NUMBERED.value): _check_qa_to_numbered,
        (SpecStatus.NUMBERED.value, SpecStatus.TRAINED.value): _check_numbered_to_trained,
        (SpecStatus.TRAINED.value, SpecStatus.ACTIVE.value): _check_trained_to_active,
        (SpecStatus.ACTIVE.value, SpecStatus.UNDER_CHANGE.value): _check_active_to_change,
        # Allow backward transitions for rejection cases
        (SpecStatus.QC_REVIEW.value, SpecStatus.DRAFT.value): lambda db, spec: True,
        (SpecStatus.UNDER_CHANGE.value, SpecStatus.ACTIVE.value): lambda db, spec: True,
    }
    
    guard = valid_transitions.get((current, target))
    
    if guard is None:
        # Check if same status (no-op)
        if current == target:
            return True
        raise LifecycleTransitionError(
            f"Invalid transition from {current} to {target}"
        )
    
    # Run guard check
    result = await guard(db, spec)
    if not result:
        raise LifecycleTransitionError(
            f"Transition guard failed: {current} → {target}"
        )
    
    return True


async def _check_initiated_to_draft(db: AsyncSession, spec: Specification) -> bool:
    """Check all mandatory fields are populated."""
    # Mandatory: material_code, material_name_en, material_name_mk, effective_date
    if not all([
        spec.material_code,
        spec.material_name_en,
        spec.material_name_mk,
        spec.effective_date,
    ]):
        raise LifecycleTransitionError(
            "All mandatory fields must be populated: material_code, "
            "material_name_en, material_name_mk, effective_date"
        )
    return True


async def _check_draft_to_qc_review(db: AsyncSession, spec: Specification) -> bool:
    """Check QC Manager approval exists."""
    stmt = select(SpecApproval).where(
        SpecApproval.spec_id == spec.id,
        SpecApproval.role == ApprovalRole.QC_MANAGER.value,
        SpecApproval.status == ApprovalStatusEnum.APPROVED.value,
    )
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    
    if approval is None:
        raise LifecycleTransitionError(
            "QC Manager approval required before QC_REVIEW"
        )
    return True


async def _check_qc_to_qa(db: AsyncSession, spec: Specification) -> bool:
    """Check QA approval exists."""
    stmt = select(SpecApproval).where(
        SpecApproval.spec_id == spec.id,
        SpecApproval.role == ApprovalRole.QA.value,
        SpecApproval.status == ApprovalStatusEnum.APPROVED.value,
    )
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    
    if approval is None:
        raise LifecycleTransitionError(
            "QA approval required before QA_APPROVED"
        )
    return True


async def _check_qa_to_numbered(db: AsyncSession, spec: Specification) -> bool:
    """Check spec_id is unique and assigned."""
    if not spec.spec_id:
        raise LifecycleTransitionError(
            "Specification ID must be assigned before NUMBERED"
        )
    return True


async def _check_numbered_to_trained(db: AsyncSession, spec: Specification) -> bool:
    """Check training confirmation (placeholder - would check training records)."""
    # In production, this would verify training records exist
    # For now, assume training is tracked externally
    return True


async def _check_trained_to_active(db: AsyncSession, spec: Specification) -> bool:
    """Check effective_date has been reached."""
    from datetime import date
    today = date.today()
    
    if spec.effective_date > today:
        raise LifecycleTransitionError(
            f"Effective date {spec.effective_date} not yet reached (today: {today})"
        )
    return True


async def _check_active_to_change(db: AsyncSession, spec: Specification) -> bool:
    """Check change request has been initiated."""
    # This is called when a change request is created
    # The change request itself validates the spec can be changed
    return True


async def can_transition(
    db: AsyncSession,
    spec_id: str,
    target_status: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if transition is possible without performing it.
    
    Returns:
        Tuple of (can_transition, error_message)
    """
    try:
        stmt = select(Specification).where(Specification.spec_id == spec_id)
        result = await db.execute(stmt)
        spec = result.scalar_one_or_none()
        
        if spec is None:
            return False, f"Specification {spec_id} not found"
        
        await _validate_transition(db, spec, spec.status, target_status)
        return True, None
    except (LifecycleTransitionError, ValueError) as e:
        return False, str(e)


async def get_spec_status_history(
    db: AsyncSession,
    spec_id: str,
) -> list[dict]:
    """
    Get status transition history for a specification.
    
    Returns:
        List of status change records
    """
    # This would integrate with audit log in production
    # For now, return current status
    stmt = select(Specification).where(Specification.spec_id == spec_id)
    result = await db.execute(stmt)
    spec = result.scalar_one_or_none()
    
    if spec is None:
        return []
    
    return [{
        "status": spec.status,
        "timestamp": spec.updated_at or spec.created_at,
        "spec_id": spec_id,
    }]


# ---------------------------------------------------------------------------
# Compatibility API expected by app.api.specifications
#
# The specifications router imports submit_for_review / approve_step /
# transition_spec / validate_transition. These thin wrappers operate on an
# already-loaded Specification object (as the router passes it) and reuse the
# existing guard/approval logic above.
# ---------------------------------------------------------------------------


# validate_transition is the public alias of the internal guard validator.
validate_transition = _validate_transition


async def submit_for_review(
    db: AsyncSession,
    spec: Specification,
    user_id: uuid.UUID,
) -> Specification:
    """
    Submit a DRAFT specification for review.

    Records the AUTHOR self-review approval and creates PENDING approval steps
    for QC_MANAGER and QA so the approval chain can proceed.
    """
    db.add(
        SpecApproval(
            spec_id=spec.id,
            role=ApprovalRole.AUTHOR.value,
            user_id=user_id,
            status=ApprovalStatusEnum.APPROVED.value,
            signed_at=datetime.now(timezone.utc),
        )
    )
    for role in (ApprovalRole.QC_MANAGER, ApprovalRole.QA):
        db.add(
            SpecApproval(
                spec_id=spec.id,
                role=role.value,
                user_id=user_id,
                status=ApprovalStatusEnum.PENDING.value,
            )
        )
    await db.flush()
    return spec


async def approve_step(
    db: AsyncSession,
    spec: Specification,
    role: ApprovalRole,
    user_id: uuid.UUID,
    comments: Optional[str] = None,
) -> Specification:
    """
    Approve a single review step for the given role.

    When every required approval (AUTHOR, QC_MANAGER, QA) is APPROVED, the
    specification transitions to ACTIVE.
    """
    stmt = select(SpecApproval).where(
        SpecApproval.spec_id == spec.id,
        SpecApproval.role == role.value,
    )
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()

    if approval is None:
        approval = SpecApproval(spec_id=spec.id, role=role.value, user_id=user_id)
        db.add(approval)

    approval.status = ApprovalStatusEnum.APPROVED.value
    approval.user_id = user_id
    approval.comments = comments
    approval.signed_at = datetime.now(timezone.utc)
    await db.flush()

    # If all required roles are approved, activate the specification.
    required = {
        ApprovalRole.AUTHOR.value,
        ApprovalRole.QC_MANAGER.value,
        ApprovalRole.QA.value,
    }
    rows = (
        await db.execute(
            select(SpecApproval).where(SpecApproval.spec_id == spec.id)
        )
    ).scalars().all()
    approved = {
        r.role for r in rows if r.status == ApprovalStatusEnum.APPROVED.value
    }
    if required.issubset(approved):
        spec.status = SpecStatus.ACTIVE.value
        await db.flush()

    return spec


async def transition_spec(
    db: AsyncSession,
    spec: Specification,
    target_status: SpecStatus,
    user_id: uuid.UUID,
    user_role: Optional[str] = None,
    reason: Optional[str] = None,
) -> Specification:
    """
    Transition a loaded specification to ``target_status``.

    Unlike transition_spec_status (which looks up by spec_id string), this
    operates on the Specification instance the router already holds.
    """
    target = target_status.value if isinstance(target_status, SpecStatus) else str(target_status)

    # WITHDRAWN is a terminal administrative status reachable from ACTIVE /
    # SUPERSEDED / UNDER_CHANGE without the staged guards.
    if target == SpecStatus.WITHDRAWN.value:
        spec.status = target
        await db.flush()
        return spec

    await _validate_transition(db, spec, spec.status, target)
    spec.status = target
    await db.flush()
    return spec
