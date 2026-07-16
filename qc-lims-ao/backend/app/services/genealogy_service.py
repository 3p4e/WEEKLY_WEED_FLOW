"""
Genealogy Service for LIMS sample lineage tracking.

Per QCSOP 011-A01: Product genealogy tracking (IPM-HT→IPM-IN→IPM-DS→IPM-PK).

Manages parent-child relationships, ancestry traversal, and progeny trees.
"""

import uuid
from enum import StrEnum
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.sample import Sample


# ── P2-E6: Corrected Genealogy Chain (QCSP 003) ──

class GenealogyStage(StrEnum):
    """Corrected genealogy stage codes per QCSP 003.
    
    OLD (WRONG): IPM-HT → IPM-IN → IPM-DS → IPM-PK
    NEW (CORRECT): IPM-HT → IPM-MT → IPM-DR → IPM-CR → IPM-PK
    
    IPM-HT: Wet inflorescences (hand-trim stage input)
    IPM-MT: Hand-trim completed (machine-trim input)
    IPM-DR: Machine-trim completed (drying input)
    IPM-CR: Dried/cured (packaging input)
    IPM-PK: Cured, ready for packaging (final QC stage)
    """
    IPM_HT_001 = "IPM‑HT‑001"  # stage_order=0
    IPM_MT_001 = "IPM‑MT‑001"  # stage_order=1
    IPM_DR_001 = "IPM‑DR‑001"  # stage_order=2
    IPM_CR_001 = "IPM‑CR‑001"  # stage_order=3
    IPM_PK_001 = "IPM‑PK‑001"  # stage_order=4
    
    @property
    def stage_order(self) -> int:
        """Return the numeric stage order for sequential validation."""
        order_map = {
            GenealogyStage.IPM_HT_001: 0,
            GenealogyStage.IPM_MT_001: 1,
            GenealogyStage.IPM_DR_001: 2,
            GenealogyStage.IPM_CR_001: 3,
            GenealogyStage.IPM_PK_001: 4,
        }
        return order_map[self]
    
    @classmethod
    def from_code(cls, code: str) -> "GenealogyStage":
        """Get GenealogyStage from string code."""
        # Normalize hyphen variations
        normalized = code.replace("-", "‑")
        for stage in cls:
            if stage.value == normalized:
                return stage
        raise ValueError(f"Invalid genealogy stage code: {code}")


def validate_stage_progression(current_stage: str, target_stage: str) -> bool:
    """
    Validate that stage progression is sequential with no gaps.
    
    Args:
        current_stage: Current genealogy stage code
        target_stage: Target genealogy stage code
    
    Returns:
        True if progression is valid (sequential, no skips)
    
    Raises:
        ValueError: If stage progression is invalid
    """
    try:
        current = GenealogyStage.from_code(current_stage)
        target = GenealogyStage.from_code(target_stage)
    except ValueError as e:
        raise ValueError(f"Invalid stage code: {e}")
    
    current_order = current.stage_order
    target_order = target.stage_order
    
    if target_order <= current_order:
        raise ValueError(
            f"Stage progression must be forward. "
            f"Current: {current.value} (order={current_order}), "
            f"Target: {target.value} (order={target_order})"
        )
    
    if target_order != current_order + 1:
        raise ValueError(
            f"Stage progression cannot skip stages. "
            f"Current: {current.value} (order={current_order}), "
            f"Target: {target.value} (order={target_order}). "
            f"Expected next: order {current_order + 1}"
        )
    
    return True


class GenealogyNode:
    """Node in the genealogy tree."""
    
    def __init__(
        self,
        sample_id: str,
        sample_uuid: uuid.UUID,
        sample_type: str,
        sp_type: Optional[str],
        batch_id: Optional[str],
        sub_batch_code: Optional[str],
        potency_grade: Optional[str],
        status: str,
        depth: int = 0,
        children: Optional[List["GenealogyNode"]] = None,
    ):
        self.sample_id = sample_id
        self.sample_uuid = sample_uuid
        self.sample_type = sample_type
        self.sp_type = sp_type
        self.batch_id = batch_id
        self.sub_batch_code = sub_batch_code
        self.potency_grade = potency_grade
        self.status = status
        self.depth = depth
        self.children = children or []
    
    def to_dict(self) -> dict:
        """Convert node to dictionary representation."""
        return {
            "sample_id": self.sample_id,
            "sample_uuid": str(self.sample_uuid),
            "sample_type": self.sample_type,
            "sp_type": self.sp_type,
            "batch_id": self.batch_id,
            "sub_batch_code": self.sub_batch_code,
            "potency_grade": self.potency_grade,
            "status": self.status,
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


async def get_sample_by_id(
    db: AsyncSession,
    sample_id: uuid.UUID
) -> Optional["Sample"]:
    """
    Retrieve a sample by its UUID.
    
    Args:
        db: Database session
        sample_id: Sample UUID
    
    Returns:
        Sample instance or None if not found
    """
    from app.models.sample import Sample
    return await db.get(Sample, sample_id)


async def track_lineage(
    db: AsyncSession,
    parent_sample_id: uuid.UUID,
    child_sample_ids: List[uuid.UUID]
) -> List["Sample"]:
    """
    Establish parent-child lineage links between samples.
    
    Args:
        db: Database session
        parent_sample_id: Parent sample UUID
        child_sample_ids: List of child sample UUIDs to link
    
    Returns:
        List of updated child samples
    
    Raises:
        ValueError: If parent or any child sample not found
    """
    from app.models.sample import Sample
    
    # Get parent sample
    parent = await db.get(Sample, parent_sample_id)
    if parent is None:
        raise ValueError(f"Parent sample {parent_sample_id} not found")
    
    # Update each child with parent reference
    updated_children = []
    for child_id in child_sample_ids:
        child = await db.get(Sample, child_id)
        if child is None:
            raise ValueError(f"Child sample {child_id} not found")
        
        child.parent_id = parent_sample_id
        updated_children.append(child)
    
    await db.flush()
    return updated_children


async def get_ancestry(
    db: AsyncSession,
    sample_id: uuid.UUID,
    include_self: bool = True
) -> List["Sample"]:
    """
    Get ancestry chain for a sample (traverse up parent chain).
    
    Returns samples ordered from root ancestor to the target sample.
    
    Args:
        db: Database session
        sample_id: Sample UUID to start from
        include_self: Whether to include the target sample in results
    
    Returns:
        List of samples from root to target (or target's parent if include_self=False)
    """
    from app.models.sample import Sample
    
    ancestry = []
    current_id = sample_id
    visited = set()  # Prevent infinite loops
    
    while current_id and current_id not in visited:
        visited.add(current_id)
        sample = await db.get(Sample, current_id)
        
        if sample is None:
            break
        
        ancestry.append(sample)
        current_id = sample.parent_id
    
    # Reverse to get root -> target order
    ancestry.reverse()
    
    if not include_self and ancestry:
        # Remove the target sample (last in list)
        ancestry = ancestry[:-1]
    
    return ancestry


async def get_progeny(
    db: AsyncSession,
    sample_id: uuid.UUID,
    include_self: bool = False,
    max_depth: int = 10
) -> List["Sample"]:
    """
    Get all descendants (progeny) for a sample (traverse down to all children).
    
    Args:
        db: Database session
        sample_id: Sample UUID to start from
        include_self: Whether to include the starting sample in results
        max_depth: Maximum depth to traverse (safety limit)
    
    Returns:
        List of all descendant samples
    """
    from app.models.sample import Sample
    
    progeny = []
    to_process = [(sample_id, 0)]
    visited = set()
    
    while to_process:
        current_id, depth = to_process.pop(0)
        
        if current_id in visited or depth > max_depth:
            continue
        
        visited.add(current_id)
        sample = await db.get(Sample, current_id)
        
        if sample is None:
            continue
        
        if include_self or current_id != sample_id:
            progeny.append(sample)
        
        # Get direct children
        stmt = select(Sample).where(Sample.parent_id == current_id)
        result = await db.execute(stmt)
        children = result.scalars().all()
        
        for child in children:
            if child.id not in visited:
                to_process.append((child.id, depth + 1))
    
    return progeny


async def get_genealogy_tree(
    db: AsyncSession,
    sample_id: uuid.UUID
) -> dict:
    """
    Get complete genealogy tree with ancestry and progeny.
    
    Args:
        db: Database session
        sample_id: Sample UUID to build tree for
    
    Returns:
        Dictionary with:
        - ancestry: List of ancestor nodes (root to parent)
        - target: The target sample node
        - progeny: Tree of descendant nodes
    """
    from app.models.sample import Sample
    
    # Get target sample
    target = await db.get(Sample, sample_id)
    if target is None:
        raise ValueError(f"Sample {sample_id} not found")
    
    # Get ancestry (without self)
    ancestors = await get_ancestry(db, sample_id, include_self=False)
    
    # Build ancestry list
    ancestry_nodes = []
    for i, ancestor in enumerate(ancestors):
        ancestry_nodes.append({
            "sample_id": ancestor.sample_id,
            "sample_uuid": str(ancestor.id),
            "sp_type": ancestor.sp_type,
            "batch_id": ancestor.batch_id,
            "sub_batch_code": ancestor.sub_batch_code,
            "potency_grade": ancestor.potency_grade,
            "status": ancestor.status,
            "depth": i,
        })
    
    # Build progeny tree recursively
    MAX_GENEALOGY_DEPTH = 50
    
    async def build_tree(sample: Sample, depth: int = 0) -> GenealogyNode:
        """Recursively build progeny tree with depth limit to prevent unbounded recursion."""
        node = GenealogyNode(
            sample_id=sample.sample_id,
            sample_uuid=sample.id,
            sample_type=sample.sample_type,
            sp_type=sample.sp_type,
            batch_id=sample.batch_id,
            sub_batch_code=sample.sub_batch_code,
            potency_grade=sample.potency_grade,
            status=sample.status,
            depth=depth,
        )
        
        if depth >= MAX_GENEALOGY_DEPTH:
            return node
        
        # Get direct children
        stmt = select(Sample).where(Sample.parent_id == sample.id)
        result = await db.execute(stmt)
        children = result.scalars().all()
        
        for child in children:
            child_node = await build_tree(child, depth + 1)
            node.children.append(child_node)
        
        return node
    
    progeny_tree = await build_tree(target)
    
    return {
        "ancestry": ancestry_nodes,
        "target": {
            "sample_id": target.sample_id,
            "sample_uuid": str(target.id),
            "sp_type": target.sp_type,
            "batch_id": target.batch_id,
            "sub_batch_code": target.sub_batch_code,
            "potency_grade": target.potency_grade,
            "status": target.status,
            "depth": len(ancestors),
        },
        "progeny": progeny_tree.to_dict(),
    }


async def get_related_samples(
    db: AsyncSession,
    batch_id: str
) -> List["Sample"]:
    """
    Get all samples related to a specific batch.
    
    Args:
        db: Database session
        batch_id: Batch identifier
    
    Returns:
        List of all samples for the batch
    """
    from app.models.sample import Sample
    
    stmt = select(Sample).where(Sample.batch_id == batch_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def format_genealogy_report(tree: dict) -> str:
    """
    Format genealogy tree as human-readable report.
    
    Args:
        tree: Genealogy tree from get_genealogy_tree()
    
    Returns:
        Formatted string report
    """
    lines = []
    
    lines.append("=" * 60)
    lines.append("SAMPLE GENEALOGY REPORT")
    lines.append("=" * 60)
    
    # Ancestry
    if tree["ancestry"]:
        lines.append("\nANCESTRY (Root → Parent):")
        for ancestor in tree["ancestry"]:
            sp_label = f" [{ancestor['sp_type']}]" if ancestor['sp_type'] else ""
            grade_label = f" (Grade {ancestor['potency_grade']})" if ancestor['potency_grade'] else ""
            lines.append(f"  {'  ' * ancestor['depth']}└─ {ancestor['sample_id']}{sp_label}{grade_label}")
    else:
        lines.append("\nANCESTRY: Root sample (no parent)")
    
    # Target
    target = tree["target"]
    sp_label = f" [{target['sp_type']}]" if target['sp_type'] else ""
    grade_label = f" (Grade {target['potency_grade']})" if target['potency_grade'] else ""
    lines.append(f"\nTARGET:")
    lines.append(f"  {target['sample_id']}{sp_label}{grade_label}")
    lines.append(f"  Status: {target['status']}")
    if target['sub_batch_code']:
        lines.append(f"  Sub-batch: {target['sub_batch_code']}")
    
    # Progeny
    def format_children(node: dict, indent: int = 0):
        for child in node.get("children", []):
            sp_label = f" [{child['sp_type']}]" if child['sp_type'] else ""
            grade_label = f" (Grade {child['potency_grade']})" if child['potency_grade'] else ""
            sub_label = f" [{child['sub_batch_code']}]" if child['sub_batch_code'] else ""
            lines.append(f"  {'  ' * indent}└─ {child['sample_id']}{sp_label}{sub_label}{grade_label}")
            format_children(child, indent + 1)
    
    if tree["progeny"]["children"]:
        lines.append(f"\nPROGENY:")
        format_children(tree["progeny"])
    else:
        lines.append("\nPROGENY: No children")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)
