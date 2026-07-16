"""
Barcode and sample ID generation service.

Per QCSOP 011-A01: Sample IDs follow PP-SMP-YYYY-NNNN format.
Supports QR code generation for label printing.
"""

import uuid
from datetime import datetime

try:
    import qrcode
except ImportError:  # qrcode is optional; QR rendering is a non-critical feature
    qrcode = None

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sample import Sample


async def generate_sample_id(db: AsyncSession) -> str:
    """
    Generate unique sample ID in PP-SMP-YYYY-NNNN format using DB sequence.
    
    Uses PostgreSQL sequence for atomic counter to eliminate TOCTOU race condition.
    Format: PP-SMP-YYYY-NNNN
    """
    year = datetime.utcnow().year
    
    # Use DB sequence for atomic counter (no TOCTOU race)
    seq_result = await db.execute(
        text("SELECT nextval('sample_id_seq')")
    )
    seq_num = seq_result.scalar()
    
    return f"PP-SMP-{year}-{seq_num:04d}"


def generate_qr_code(sample_id: str, box_size: int = 10, border: int = 4):
    """
    Generate QR code for sample label.

    Args:
        sample_id: The sample identifier to encode
        box_size: Size of each QR code box in pixels
        border: Border width in boxes

    Returns:
        Configured QRCode object (call .make_image() to render), or None if
        the optional ``qrcode`` dependency is not installed.
    """
    if qrcode is None:
        return None

    qr = qrcode.QRCode(
        version=None,  # Auto-fit
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=box_size,
        border=border,
    )
    qr.add_data(sample_id)
    qr.make(fit=True)
    return qr


def generate_sub_batch_code(index: int) -> str:
    """
    Generate sub-batch code for divided batches.
    
    Format: D1, D2, ... D26, DD1, DD2, ... DD26, DDD1, etc.
    
    Args:
        index: 0-based index of the sub-batch
    
    Returns:
        Sub-batch code string
    """
    if index < 0:
        raise ValueError("Index must be non-negative")
    
    # First 26: D1-D26
    if index < 26:
        return f"D{chr(ord('A') + index)}"
    
    # Next 26: DD1-DD26
    index -= 26
    if index < 26:
        return f"DD{chr(ord('A') + index)}"
    
    # Next 26: DDD1-DDD26
    index -= 26
    if index < 26:
        return f"DDD{chr(ord('A') + index)}"
    
    # Beyond 78 divisions: use numeric suffix
    return f"D{index - 52:03d}"


async def validate_sample_id(db: AsyncSession, sample_id: str) -> bool:
    """
    Validate that a sample ID exists in the database.
    
    Args:
        db: Database session
        sample_id: Sample ID to validate
    
    Returns:
        True if sample exists, False otherwise
    """
    stmt = select(Sample).where(Sample.sample_id == sample_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
