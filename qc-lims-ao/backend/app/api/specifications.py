"""
Specification Management API Router (P1).

Endpoints:
  POST   /specifications/               — Create new specification draft
  GET    /specifications/               — List specifications (with filters)
  GET    /specifications/{id}           — Get specification detail with parameters
  PUT    /specifications/{id}           — Update specification (DRAFT only)
  POST   /specifications/{id}/submit    — Submit for review (creates approval chain)
  POST   /specifications/{id}/approve   — Approve a review step (→ ACTIVE when all done)
  POST   /specifications/{id}/withdraw  — Withdraw an ACTIVE or SUPERSEDED spec
  POST   /specifications/{id}/validate  — Validate test results against spec parameters
  GET    /specifications/{id}/a03-checklist  — Annex A03 checklist for COA review

Per QCSOP 010 §6.5: Self-review → QC Manager technical review → QA approval.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_role, Role
from app.models.user import User
from app.models.specification import (
    Specification,
    SpecParameter,
    SpecStatus,
    SpecApproval,
    ApprovalRole,
    ApprovalStatusEnum as ApprovalStatus,
)
from app.services.spec_numbering_service import (
    SpecType,
    get_next_spec_number_async,
    get_next_version_async,
)
from app.services.spec_lifecycle_service import (
    transition_spec,
    submit_for_review,
    approve_step,
    validate_transition,
)
from app.services.spec_validation_service import validate_result as validate_single_result
from app.schemas.specification import (
    SpecCreate,
    SpecUpdate,
    SpecResponse,
    SpecListResponse,
    SpecStateTransition,
    SpecParameterCreate,
    SpecParameterResponse,
    SpecApprovalAction,
    SpecApprovalResponse,
    ValidationRequest,
    ValidationResponse,
    BatchValidationRequest,
    BatchValidationResponse,
    AnnexA03ChecklistItem,
    AnnexA03ChecklistResponse,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_spec_or_404(
    db: AsyncSession,
    spec_id: uuid.UUID,
) -> Specification:
    """Fetch specification by UUID or raise 404."""
    result = await db.execute(
        select(Specification)
        .where(Specification.id == spec_id)
        .where(Specification.is_deleted.is_(False))
    )
    spec = result.scalar_one_or_none()
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specification {spec_id} not found",
        )
    return spec


async def _get_active_spec_for_material(
    db: AsyncSession,
    material_code: str,
) -> Specification | None:
    """Get the currently ACTIVE specification for a material code."""
    result = await db.execute(
        select(Specification)
        .where(Specification.material_code == material_code)
        .where(Specification.status == SpecStatus.ACTIVE.value)
        .where(Specification.is_deleted.is_(False))
    )
    return result.scalar_one_or_none()


# ── CRUD Endpoints ───────────────────────────────────────────────────────────

@router.post("/", response_model=SpecResponse, status_code=status.HTTP_201_CREATED)
async def create_spec(
    data: SpecCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([Role.QC_ANALYST, Role.QC_MANAGER])),
):
    """
    Create a new specification in DRAFT status.
    Numbering is assigned at the approval stage, not on creation.
    """
    # Determine spec_type from material_code prefix (default to IMG for now)
    spec_type_code = "IMG"  # Default — refine based on material code conventions

    # Create draft spec without a spec_number yet (assigned on approval)
    spec = Specification(
        material_code=data.material_code,
        material_name_en=data.material_name_en,
        material_name_mk=data.material_name_mk,
        version=1,
        effective_date=data.effective_date,
        status=SpecStatus.DRAFT.value,
        spec_id=f"TEMP-{data.material_code}-{current_user.id.hex[:8]}",
    )
    db.add(spec)
    await db.flush()
    await db.refresh(spec)

    return spec


@router.get("/", response_model=List[SpecListResponse])
async def list_specs(
    material_code: Optional[str] = Query(None, description="Filter by material code"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List specifications with optional filters."""
    stmt = select(Specification).where(Specification.is_deleted.is_(False))

    if material_code:
        stmt = stmt.where(Specification.material_code.ilike(f"%{material_code}%"))
    if status_filter:
        stmt = stmt.where(Specification.status == status_filter.upper())

    stmt = stmt.order_by(Specification.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    specs = result.scalars().all()

    # Build lightweight list with parameter counts
    list_items = []
    for spec in specs:
        param_count = len(spec.parameters) if spec.parameters else 0
        list_items.append(
            {
                "id": spec.id,
                "spec_id": spec.spec_id,
                "material_code": spec.material_code,
                "material_name_en": spec.material_name_en,
                "material_name_mk": spec.material_name_mk,
                "version": spec.version,
                "effective_date": spec.effective_date,
                "status": spec.status,
                "parameter_count": param_count,
                "created_at": spec.created_at,
            }
        )

    return list_items


@router.get("/{spec_id}", response_model=SpecResponse)
async def get_spec(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get specification detail including all parameters."""
    spec = await _get_spec_or_404(db, spec_id)
    return spec


@router.put("/{spec_id}", response_model=SpecResponse)
async def update_spec(
    spec_id: uuid.UUID,
    data: SpecUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([Role.QC_ANALYST, Role.QC_MANAGER])),
):
    """
    Update a DRAFT specification. Active/Superceded/Withdrawn specs cannot be edited.
    Use change control for modifications to approved specs.
    """
    spec = await _get_spec_or_404(db, spec_id)

    if SpecStatus(spec.status) != SpecStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit specification in '{spec.status}' status. "
                   "Only DRAFT specifications can be modified.",
        )

    if data.material_name_en is not None:
        spec.material_name_en = data.material_name_en
    if data.material_name_mk is not None:
        spec.material_name_mk = data.material_name_mk
    if data.effective_date is not None:
        spec.effective_date = data.effective_date

    spec.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return spec


# ── Lifecycle Endpoints ──────────────────────────────────────────────────────

@router.post("/{spec_id}/submit", response_model=SpecResponse)
async def submit_spec(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([Role.QC_MANAGER, Role.QC_ANALYST])),
):
    """
    Submit a DRAFT specification for review.
    Creates the approval chain (AUTHOR → QC_MANAGER → QA).
    The spec remains DRAFT until all approval steps are completed.
    """
    spec = await _get_spec_or_404(db, spec_id)

    if SpecStatus(spec.status) != SpecStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only DRAFT specifications can be submitted. Current: {spec.status}",
        )

    # Idempotency: skip if approvals already exist
    if spec.approvals and len(spec.approvals) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Specification already submitted for review",
        )

    await submit_for_review(db, spec, current_user.id)
    await db.commit()
    await db.refresh(spec)
    return spec


@router.post("/{spec_id}/approve", response_model=SpecResponse)
async def approve_spec(
    spec_id: uuid.UUID,
    action: SpecApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([Role.QC_MANAGER, Role.QP])),
):
    """
    Approve a review step. When all approval steps (AUTHOR, QC_MANAGER, QA)
    are complete, the specification transitions to ACTIVE and receives its
    official QCSP number.
    """
    spec = await _get_spec_or_404(db, spec_id)

    if SpecStatus(spec.status) not in (SpecStatus.DRAFT,):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve specification in '{spec.status}' status.",
        )

    # Perform the approval step
    await approve_step(db, spec, ApprovalRole(action.approval_role.value), current_user.id, action.comments)

    # If now ACTIVE, assign official QCSP number
    if SpecStatus(spec.status) == SpecStatus.ACTIVE and spec.spec_id.startswith("TEMP-"):
        spec_type_code = "IMG"  # Default — infer from material_code if needed
        new_number = await get_next_spec_number_async(db, spec_type_code)
        spec.spec_id = new_number

    await db.commit()
    await db.refresh(spec)
    return spec


@router.post("/{spec_id}/withdraw", response_model=SpecResponse)
async def withdraw_spec(
    spec_id: uuid.UUID,
    body: SpecStateTransition,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([Role.QC_MANAGER, Role.QP])),
):
    """
    Withdraw an ACTIVE or SUPERSEDED specification.
    Requires reason per GMP change control.
    """
    spec = await _get_spec_or_404(db, spec_id)

    await transition_spec(
        db, spec, SpecStatus.WITHDRAWN,
        current_user.id, current_user.role, body.reason,
    )
    await db.commit()
    await db.refresh(spec)
    return spec


# ── Validation Endpoints ─────────────────────────────────────────────────────

@router.post("/{spec_id}/validate", response_model=ValidationResponse)
async def validate_test_result(
    spec_id: uuid.UUID,
    request: ValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate a single test result against this specification's parameters.
    Returns pass / alert / fail based on dual operational/release limits.
    """
    spec = await _get_spec_or_404(db, spec_id)

    # E9: effective_date check — spec must be effective before validation
    if spec.effective_date and spec.effective_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Specification {spec.spec_id} is not yet effective (effective_date: {spec.effective_date})",
        )

    # Find the matching parameter by name
    param = None
    for p in spec.parameters:
        if p.test_name_en == request.test_name:
            param = p
            break

    if param is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Test '{request.test_name}' not found in specification {spec.spec_id}",
        )

    # Build spec parameter dict for validation service
    spec_param = {
        "id": param.id,
        "test_name_en": param.test_name_en,
        "spec_type": param.spec_type,
        "operational_limit_min": param.operational_limit_min,
        "operational_limit_max": param.operational_limit_max,
        "release_limit_min": param.release_limit_min,
        "release_limit_max": param.release_limit_max,
        "unit": param.unit,
    }

    vr = validate_single_result(
        result_value=request.result_value,
        result_numeric=request.result_numeric,
        spec_parameter=spec_param,
    )

    return ValidationResponse(
        complies=vr.complies,
        status=vr.status,
        limit_type=vr.limit_type,
        spec_parameter_id=vr.spec_parameter_id,
        spec_parameter_name=vr.spec_parameter_name,
        alert_message=vr.alert_message,
        result_value=vr.result_value,
        spec_limit_display=vr.spec_limit_display,
    )


@router.post("/{spec_id}/validate-batch", response_model=BatchValidationResponse)
async def validate_batch(
    spec_id: uuid.UUID,
    request: BatchValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate multiple test results against this specification in one call.
    Returns individual results plus summary counts.
    """
    spec = await _get_spec_or_404(db, spec_id)

    # Build parameter map
    spec_params = []
    for p in spec.parameters:
        spec_params.append({
            "id": p.id,
            "test_name_en": p.test_name_en,
            "spec_type": p.spec_type,
            "operational_limit_min": p.operational_limit_min,
            "operational_limit_max": p.operational_limit_max,
            "release_limit_min": p.release_limit_min,
            "release_limit_max": p.release_limit_max,
            "unit": p.unit,
        })

    # Convert request results to dicts
    result_dicts = [
        {
            "test_name": r.test_name,
            "result_value": r.result_value,
            "result_numeric": r.result_numeric,
        }
        for r in request.results
    ]

    from app.services.spec_validation_service import validate_batch_results
    validation_results = validate_batch_results(result_dicts, spec_params)

    # Count statuses
    summary = {"pass": 0, "alert": 0, "fail": 0, "error": 0}
    response_results = []
    for vr in validation_results:
        summary[vr.status] = summary.get(vr.status, 0) + 1
        response_results.append(ValidationResponse(
            complies=vr.complies,
            status=vr.status,
            limit_type=vr.limit_type,
            spec_parameter_id=vr.spec_parameter_id,
            spec_parameter_name=vr.spec_parameter_name,
            alert_message=vr.alert_message,
            result_value=vr.result_value,
            spec_limit_display=vr.spec_limit_display,
        ))

    return BatchValidationResponse(
        spec_id=spec_id,
        results=response_results,
        summary=summary,
    )


# ── Annex A03 Checklist Endpoint ─────────────────────────────────────────────

@router.get("/{spec_id}/a03-checklist", response_model=AnnexA03ChecklistResponse)
async def get_a03_checklist(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate Annex A03 checklist for COA review per QCSOP 012 §A01.2.
    Returns all specification parameters formatted as checklist items.
    """
    spec = await _get_spec_or_404(db, spec_id)

    checklist_items = []
    for param in spec.parameters:
        # Build spec_limit display string
        limit_parts = []
        if param.release_limit_min is not None and param.release_limit_max is not None:
            limit_parts.append(f"{param.release_limit_min}–{param.release_limit_max}")
        elif param.release_limit_max is not None:
            limit_parts.append(f"≤ {param.release_limit_max}")
        elif param.release_limit_min is not None:
            limit_parts.append(f"≥ {param.release_limit_min}")
        elif param.operational_limit_min is not None or param.operational_limit_max is not None:
            if param.operational_limit_min is not None and param.operational_limit_max is not None:
                limit_parts.append(f"{param.operational_limit_min}–{param.operational_limit_max} (op)")
            elif param.operational_limit_max is not None:
                limit_parts.append(f"≤ {param.operational_limit_max} (op)")
            elif param.operational_limit_min is not None:
                limit_parts.append(f"≥ {param.operational_limit_min} (op)")

        spec_limit = f"{' — '.join(limit_parts)} {param.unit}" if limit_parts else f"See method {param.test_method}"

        checklist_items.append(AnnexA03ChecklistItem(
            parameter_name=param.test_name_en,
            parameter_name_mk=param.test_name_mk,
            method_reference=param.test_method,
            spec_limit=spec_limit,
            unit=param.unit,
        ))

    return AnnexA03ChecklistResponse(
        spec_id=spec_id,
        spec_number=spec.spec_id,
        effective_date=spec.effective_date,
        checklist_items=checklist_items,
        generated_at=datetime.now(timezone.utc),
    )
