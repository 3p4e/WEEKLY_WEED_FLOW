"""
Sample Management API for LIMS.

Per QCSOP 011-A01 and ALCOA++ requirements.
Provides endpoints for sample lifecycle, custody transfer, genealogy, and potency grading.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.certificate import CertificateOfAnalysis
from app.models.sample import Sample
from app.models.user import User
from app.services.sample_lifecycle_service import create_sp06_and_children
from app.services.custody_service import transfer_custody
from app.services.genealogy_service import get_genealogy_tree
from app.services.potency_service import update_sample_potency

router = APIRouter(tags=["samples"])


def _serialize_sample(sample: Sample, coa_number: str | None = None) -> dict:
    """Shape a Sample ORM row into the dict the React frontend expects."""
    return {
        "sample_id": sample.sample_id,
        "batch_id": sample.batch_id,
        "material_name_en": sample.material_name_en,
        "material_name_mk": sample.material_name_mk,
        "sample_type": sample.sample_type,
        "sampling_point": sample.sp_type,
        "test_location": "IN_HOUSE",
        "status": sample.status,
        "sampling_date": sample.sampling_date,
        "analyst_id": str(sample.sampled_by_id) if sample.sampled_by_id else None,
        "potency_grade": sample.potency_grade,
        "coa_number": coa_number,
    }


# ============================================================================
# Request/Response Schemas
# ============================================================================

class SP06ReceiveRequest(BaseModel):
    """Request body for SP-06 batch reception."""
    batch_id: str = Field(..., description="Production batch identifier")
    batch_size: int = Field(..., ge=1, description="Number of units in batch (N)")
    material_code: str = Field(..., description="Material code")
    material_name_en: str = Field(..., description="Material name (English)")
    material_name_mk: str = Field(..., description="Material name (Macedonian)")
    sampling_plan_id: Optional[uuid.UUID] = Field(None, description="Optional sampling plan ID")


class SP06ReceiveResponse(BaseModel):
    """Response for SP-06 batch reception."""
    sp06_sample_id: str
    sp07_sample_id: Optional[str]
    sp08_sample_id: Optional[str]
    sp09_sample_id: Optional[str]
    sample_size: int
    message: str


class CustodyTransferRequest(BaseModel):
    """Request body for custody transfer."""
    to_user_id: uuid.UUID = Field(..., description="User ID receiving custody")
    from_location: Optional[str] = Field(None, description="Current location")
    to_location: Optional[str] = Field(None, description="New location")
    reason: Optional[str] = Field(None, description="Reason for transfer")


class CustodyTransferResponse(BaseModel):
    """Response for custody transfer."""
    custody_id: str
    transferred_at: datetime
    from_user_id: str
    to_user_id: str
    message: str


class GenealogyResponse(BaseModel):
    """Response for genealogy tree query."""
    ancestry: list[dict]
    target: dict
    progeny: dict


class PotencyGradeRequest(BaseModel):
    """Request body for potency grading."""
    thc: float = Field(..., ge=0, description="Measured THC content (% w/w)")
    thca: float = Field(..., ge=0, description="Measured THCA content (% w/w)")
    target_thc: float = Field(..., ge=0, description="Target THC potency (% w/w)")
    tolerance: float = Field(0.10, ge=0, le=1, description="Tolerance band (default 10%)")


class PotencyGradeResponse(BaseModel):
    """Response for potency grading."""
    sample_id: str
    total_thc: float
    grade: str
    oos: bool
    blocked: bool
    message: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    summary="List samples",
    description="Return all non-deleted samples for the frontend sample list.",
)
async def list_samples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List all (non-deleted) samples, newest first, with linked CoA number."""
    result = await db.execute(
        select(Sample)
        .where(Sample.is_deleted == False)  # noqa: E712
        .order_by(Sample.sampling_date.desc())
    )
    # .unique() is required because Sample eager-loads collection relationships.
    samples = result.unique().scalars().all()

    # Build a batch_id -> coa_number map in one query (best effort).
    batch_ids = [s.batch_id for s in samples if s.batch_id]
    coa_by_batch: dict[str, str] = {}
    if batch_ids:
        coa_result = await db.execute(
            select(CertificateOfAnalysis).where(
                CertificateOfAnalysis.batch_id.in_(batch_ids),
                CertificateOfAnalysis.is_deleted == False,  # noqa: E712
            )
        )
        for coa in coa_result.scalars().all():
            coa_by_batch.setdefault(coa.batch_id, coa.coa_number)

    return [
        _serialize_sample(s, coa_by_batch.get(s.batch_id) if s.batch_id else None)
        for s in samples
    ]


@router.get(
    "/{sample_id}",
    summary="Get a single sample by business sample_id",
)
async def get_sample(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return one sample by its human-readable sample_id (PP-SMP-...)."""
    result = await db.execute(
        select(Sample).where(
            Sample.sample_id == sample_id,
            Sample.is_deleted == False,  # noqa: E712
        )
    )
    sample = result.unique().scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    coa_number = None
    if sample.batch_id:
        coa_result = await db.execute(
            select(CertificateOfAnalysis).where(
                CertificateOfAnalysis.batch_id == sample.batch_id,
                CertificateOfAnalysis.is_deleted == False,  # noqa: E712
            )
        )
        coa = coa_result.scalars().first()
        coa_number = coa.coa_number if coa else None

    return _serialize_sample(sample, coa_number)


@router.post(
    "/sp06-receive",
    response_model=SP06ReceiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive batch and create SP-06 with child samples",
    description="""
    Receives a production batch and creates:
    - SP-06: Reception/arrival sample (parent)
    - SP-07: In-process control (during drying) - if sampling plan requires
    - SP-08: In-process control (during curing) - if sampling plan requires  
    - SP-09: Finished product (packaging) - if sampling plan requires
    
    Sample size is calculated using ROUNDUP(√N×1.5) per QCSOP 011-A01.
    """
)
async def sp06_receive(
    request: SP06ReceiveRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SP06ReceiveResponse:
    """
    Receive batch and create SP-06 with auto-generated SP-07/08/09 children.
    
    Raises:
        HTTPException 400: If sampling plan not found for material
        HTTPException 500: If sample creation fails
    """
    try:
        result = await create_sp06_and_children(
            db=db,
            batch_id=request.batch_id,
            batch_size=request.batch_size,
            material_code=request.material_code,
            material_name_en=request.material_name_en,
            material_name_mk=request.material_name_mk,
            sampled_by_id=current_user.id,
            sampling_plan_id=request.sampling_plan_id,
            user_full_name=current_user.full_name or current_user.email,
            ip_address=req.client.host if req.client else "127.0.0.1",
            session_id=str(req.session.get("id", "api")) if hasattr(req, "session") else "api",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create samples: {str(e)}"
        )
    
    return SP06ReceiveResponse(
        sp06_sample_id=result["sp06"].sample_id,
        sp07_sample_id=result["sp07"].sample_id if result["sp07"] else None,
        sp08_sample_id=result["sp08"].sample_id if result["sp08"] else None,
        sp09_sample_id=result["sp09"].sample_id if result["sp09"] else None,
        sample_size=result["sample_size"],
        message="SP-06 and child samples created successfully"
    )


@router.post(
    "/{sample_id}/custody-transfer",
    response_model=CustodyTransferResponse,
    summary="Transfer custody of a sample",
    description="""
    Transfers custody of a sample from the current user to another user.
    Logs the transfer in the chain of custody with timestamps and signatures.
    """
)
async def custody_transfer(
    sample_id: uuid.UUID,
    request: CustodyTransferRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustodyTransferResponse:
    """
    Transfer custody of a sample.
    
    Raises:
        HTTPException 404: If sample not found
        HTTPException 400: If custody transfer fails
    """
    try:
        custody_record = await transfer_custody(
            db=db,
            sample_id=sample_id,
            from_user_id=current_user.id,
            to_user_id=request.to_user_id,
            from_location=request.from_location,
            to_location=request.to_location,
            transfer_reason=request.reason,
            user_full_name=current_user.full_name or current_user.email,
            ip_address=req.client.host if req.client else "127.0.0.1",
            session_id=str(req.session.get("id", "api")) if hasattr(req, "session") else "api",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Custody transfer failed: {str(e)}"
        )
    
    return CustodyTransferResponse(
        custody_id=str(custody_record.id),
        transferred_at=custody_record.transferred_at,
        from_user_id=str(custody_record.from_user_id),
        to_user_id=str(custody_record.to_user_id),
        message="Custody transferred successfully"
    )


@router.get(
    "/{sample_id}/genealogy",
    response_model=GenealogyResponse,
    summary="Get sample genealogy tree",
    description="""
    Returns the complete genealogy tree for a sample including:
    - Ancestry: All parent samples up to the root
    - Target: The sample itself
    - Progeny: All descendant samples in tree structure
    """
)
async def get_sample_genealogy(
    sample_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenealogyResponse:
    """
    Get genealogy tree for a sample.
    
    Raises:
        HTTPException 404: If sample not found
    """
    try:
        tree = await get_genealogy_tree(db, sample_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    return GenealogyResponse(
        ancestry=tree["ancestry"],
        target=tree["target"],
        progeny=tree["progeny"]
    )


@router.post(
    "/{sample_id}/potency-grade",
    response_model=PotencyGradeResponse,
    summary="Calculate potency and assign grade",
    description="""
    Calculates total potency using THCA×0.877+THC formula and assigns grade:
    - Grade A (Premium): >110% of target
    - Grade B (Standard): 90-110% of target
    - Grade C (Extracts): <90% of target
    
    If potency is out of specification (Grade A or C), the sample is flagged
    for OOS investigation and routing is blocked.
    """
)
async def assign_potency_grade(
    sample_id: uuid.UUID,
    request: PotencyGradeRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PotencyGradeResponse:
    """
    Calculate potency and assign grade to sample.
    
    Raises:
        HTTPException 404: If sample not found
        HTTPException 400: If potency update fails
    """
    try:
        result = await update_sample_potency(
            db=db,
            sample_id=sample_id,
            thc=request.thc,
            thca=request.thca,
            target_thc=request.target_thc,
            tested_by_id=current_user.id,
            user_full_name=current_user.full_name or current_user.email,
            tolerance=request.tolerance,
            ip_address=req.client.host if req.client else "127.0.0.1",
            session_id=str(req.session.get("id", "api")) if hasattr(req, "session") else "api",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Potency grading failed: {str(e)}"
        )
    
    sample = result["sample"]
    
    message = f"Potency graded: {result['grade']}"
    if result["oos"]:
        message = f"OOS ALERT: Potency {result['total_thc']}% outside tolerance - sample blocked for investigation"
    
    return PotencyGradeResponse(
        sample_id=sample.sample_id,
        total_thc=result["total_thc"],
        grade=result["grade"],
        oos=result["oos"],
        blocked=result["blocked"],
        message=message
    )
