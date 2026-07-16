"""
Specification numbering service per QCSOP 010 v02 §6.6.

Numbering format: QCSP-[type]-[NNN]-v[VV]
- QCSP: Quality Control Specification prefix
- [type]: SpecType code (FP, IMB, IMG, IPM)
- [NNN]: Three-digit sequential number starting at 001
- v[VV]: Two-digit version number starting at 01

Sequential numbers are assigned per spec_type to avoid collisions.
When a number is taken, auto-increment to the next available.
"""

import logging
from enum import StrEnum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.specification import Specification

logger = logging.getLogger(__name__)


class SpecType(StrEnum):
    """Per QCSOP 010 v02 §6.6 numbering convention."""
    IMG = "IMG"  # Raw Material / Incoming Material
    IPM = "IPM"  # In-Process Material
    FP = "FP"    # Finished Product
    IMB = "IMB"  # Intermediate Bulk


def generate_spec_number(spec_type: str, version: int = 1) -> str:
    """
    Generate a spec number per QCSOP 010 §6.6 format.

    Does NOT check for collisions — use get_next_spec_number_async()
    when creating specs in the database.

    Format: QCSP-[type]-[NNN]-v[VV]
    Examples:
        QCSP-FP-001-v01  (Finished Product spec #1, version 1)
        QCSP-IMB-003-v02 (Intermediate Bulk spec #3, version 2)

    Args:
        spec_type: SpecType code (FP, IMB, IMG, IPM) or raw string.
        version: Version number (positive integer, typically ≥ 1).

    Returns:
        Formatted spec number string.

    Raises:
        ValueError: If spec_type is not a valid SpecType or version < 1.
    """
    if version < 1:
        raise ValueError(f"Version must be >= 1, got {version}")

    # Validate spec_type — coerce raw strings through enum
    try:
        st = SpecType(spec_type.upper())
    except ValueError:
        raise ValueError(
            f"Invalid spec_type '{spec_type}'. Must be one of: "
            f"{[e.value for e in SpecType]}"
        )

    return f"QCSP-{st.value}-{version:03d}-v{version:02d}"


async def get_next_spec_number_async(
    session: AsyncSession,
    spec_type: str,
    version: int = 1,
) -> str:
    """
    Get the next available spec number for the given type and version.

    Scans existing Specification records for the highest sequential number
    for this spec_type, then increments. If no existing records, starts at 001.

    Collision-safe: increments until an unused number is found.

    Args:
        session: Async database session.
        spec_type: SpecType code (FP, IMB, IMG, IPM).
        version: Version number (typically 1 for new, incremented for revisions).

    Returns:
        Next available QCSP-[type]-[NNN]-v[VV] number.
    """
    st = SpecType(spec_type.upper())

    # Find the highest sequential number for this spec_type
    # by querying spec_id prefix matching QCSP-[type]-
    prefix = f"QCSP-{st.value}-"

    result = await session.execute(
        select(Specification.spec_id)
        .where(Specification.spec_id.like(f"{prefix}%"))
        .where(Specification.is_deleted.is_(False))
    )
    existing_ids = {row[0] for row in result.fetchall()}

    sequential = 1
    max_attempts = 10000
    while sequential <= max_attempts:
        candidate = f"QCSP-{st.value}-{sequential:03d}-v{version:02d}"
        if candidate not in existing_ids:
            return candidate
        sequential += 1

    raise RuntimeError(
        f"Exhausted {max_attempts} sequential numbers for spec_type={st.value}"
    )


async def get_next_version_async(
    session: AsyncSession,
    spec_type: str,
    sequential: int,
) -> int:
    """
    Get the next version number for a specific spec type + sequential combination.

    Scans existing Specification records for the highest version number
    with the same prefix, then returns version + 1.

    Args:
        session: Async database session.
        spec_type: SpecType code.
        sequential: The sequential number portion (NNN).

    Returns:
        Next version number (1 if no prior versions exist).
    """
    st = SpecType(spec_type.upper())
    prefix = f"QCSP-{st.value}-{sequential:03d}-v"

    result = await session.execute(
        select(Specification.spec_id)
        .where(Specification.spec_id.like(f"{prefix}%"))
        .where(Specification.is_deleted.is_(False))
    )
    existing_ids = [row[0] for row in result.fetchall()]

    if not existing_ids:
        return 1

    # Extract version numbers and find max
    versions = []
    for spec_id in existing_ids:
        try:
            v_part = spec_id.rsplit("-v", 1)[-1]
            versions.append(int(v_part))
        except (ValueError, IndexError):
            continue

    return max(versions) + 1 if versions else 1
