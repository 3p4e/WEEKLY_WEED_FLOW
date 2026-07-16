"""
OOS Numbering Service
Generates PP-OOS-YYYY-NNNN identifiers per QCSOP 019-A03.
Uses atomic DB sequence for race-free ID generation.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def next_oos_number(db: AsyncSession) -> str:
    """
    Generate next OOS identifier: PP-OOS-YYYY-NNNN
    
    Sequence: oos_id_seq (created via Alembic)
    Format: PP-OOS-{YYYY}-{NNNN}
    
    Args:
        db: Async database session
    
    Returns:
        Formatted OOS ID string
    """
    result = await db.execute(text("SELECT nextval('oos_id_seq')"))
    seq = result.scalar_one()
    year = __import__('datetime').datetime.utcnow().year
    return f"PP-OOS-{year}-{seq:04d}"
