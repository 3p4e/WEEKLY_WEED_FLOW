"""
Sampling Plan Service for LIMS sample size calculations.

Per QCSOP 011-A01: Sampling formula ROUNDUP(√N×1.5) for sub-batch determination.

Provides validation, calculation, and enforcement of sampling plans.
"""

import math
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.sampling_plan import SamplingPlan


async def get_sampling_plan(db: AsyncSession, material_code: str) -> "SamplingPlan | None":
    """
    Retrieve the active sampling plan for a material.
    
    Args:
        db: Database session
        material_code: Material code to look up
    
    Returns:
        SamplingPlan if found and active, None otherwise
    """
    from app.models.sampling_plan import SamplingPlan
    
    stmt = (
        select(SamplingPlan)
        .where(SamplingPlan.material_code == material_code)
        .where(SamplingPlan.active == True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def calculate_sample_size(N: int) -> int:
    """
    Calculate sample size using QCSOP 011-A01 formula: ROUNDUP(√N×1.5).
    
    Validates against min/max limits (min=1, max=50).
    
    Args:
        N: Batch size (number of units in batch)
    
    Returns:
        Calculated sample size (clamped between 1 and 50)
    
    Examples:
        >>> calculate_sample_size(100)
        15  # ROUNDUP(√100×1.5) = ROUNDUP(15.0) = 15
        >>> calculate_sample_size(144)
        18  # ROUNDUP(√144×1.5) = ROUNDUP(18.0) = 18
    """
    if N <= 0:
        raise ValueError("Batch size N must be positive, got {N}")
    
    # Calculate ROUNDUP(√N×1.5)
    sample_size = math.ceil(math.sqrt(N) * 1.5)
    
    # Apply min/max limits
    MIN_SAMPLE_SIZE = 1
    MAX_SAMPLE_SIZE = 50
    
    sample_size = max(MIN_SAMPLE_SIZE, min(sample_size, MAX_SAMPLE_SIZE))
    
    return sample_size


async def validate_and_calculate_sample_size(
    db: AsyncSession,
    material_code: str,
    batch_size: int
) -> int:
    """
    Validate sampling plan exists and calculate sample size.
    
    Args:
        db: Database session
        material_code: Material code to validate
        batch_size: Batch size N
    
    Returns:
        Calculated sample size
    
    Raises:
        ValueError: If no active sampling plan exists for the material
    """
    plan = await get_sampling_plan(db, material_code)
    
    if plan is None:
        raise ValueError(
            f"No active sampling plan found for material '{material_code}'. "
            f"Sampling plan must be created before receiving batch."
        )
    
    return calculate_sample_size(batch_size)


async def get_sample_size_limits(plan: "SamplingPlan") -> tuple[int, int]:
    """
    Get the min/max sample size limits from a sampling plan.
    
    Args:
        plan: SamplingPlan instance
    
    Returns:
        Tuple of (min_sample_size, max_sample_size)
    """
    return (plan.min_sample_size, plan.max_sample_size)
