from app.db import rls
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .certificates import _ISSUED_FROZEN, _result_out
from .common import _WRITERS, _uuid_or_404, router


_GENEALOGY_RELATIONS = ("CULTIVATION", "PROCESSING", "PACKAGING", "BLEND", "GENERIC")


class GenealogyIn(BaseModel):
    parent_batch_id: str = Field(min_length=1, max_length=120)
    child_batch_id: str = Field(min_length=1, max_length=120)
    relation: str = "GENERIC"
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)


def _edge_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "parent_batch_id": r["parent_batch_id"],
        "child_batch_id": r["child_batch_id"], "relation": r["relation"],
        "quantity": float(r["quantity"]) if r["quantity"] is not None else None,
        "unit": r["unit"], "notes": r["notes"],
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }


@router.post("/genealogy", status_code=201)
async def add_genealogy_edge(body: GenealogyIn, user: dict = Depends(require_role(*_WRITERS))):
    """Link a parent batch to a child batch (variety→cultivation→processing→
    packaging; BLEND for a multi-parent merge). Refuses an edge that would close
    a cycle (a batch cannot be its own ancestor)."""
    parent, child = body.parent_batch_id.strip(), body.child_batch_id.strip()
    if not parent or not child:
        raise HTTPException(422, "parent_batch_id and child_batch_id are required")
    if parent == child:
        raise HTTPException(422, "A batch cannot be its own parent")
    if body.relation not in _GENEALOGY_RELATIONS:
        raise HTTPException(422, f"relation must be one of: {', '.join(_GENEALOGY_RELATIONS)}")
    async with rls(user) as c:
        # Serialize genealogy writes per-org: the cycle check below reads the
        # graph, then the INSERT commits a new edge — two concurrent edges that
        # only close a cycle TOGETHER would each see a pre-insert graph and both
        # pass, so lock out other genealogy writers in this org for the
        # duration of this transaction (same pattern as cert numbering/RQS
        # ordering elsewhere in this file).
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"genealogy:{user['org_id']}")
        # cycle guard: parent must NOT already be a descendant of child
        cyc = await c.fetchval(
            "WITH RECURSIVE d AS ("
            "  SELECT child_batch_id AS b FROM qc_batch_genealogy WHERE parent_batch_id=$1"
            "  UNION"
            "  SELECT g.child_batch_id FROM qc_batch_genealogy g JOIN d ON g.parent_batch_id=d.b)"
            " SELECT 1 FROM d WHERE b=$2 LIMIT 1", child, parent)
        if cyc:
            raise HTTPException(409, "That edge would create a cycle in the genealogy")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_batch_genealogy(org_id, parent_batch_id, child_batch_id, relation,"
                " quantity, unit, notes, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
                user["org_id"], parent, child, body.relation, body.quantity, body.unit,
                body.notes, user["id"])
        except Exception as e:
            if "qc_batch_genealogy_edge_key" in str(e):
                raise HTTPException(409, "That parent→child edge already exists")
            raise
    return _edge_out(dict(row))


@router.delete("/genealogy/{edge_id}", status_code=204)
async def delete_genealogy_edge(edge_id: str, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(edge_id, "Genealogy edge")
    async with rls(user) as c:
        edge = await c.fetchrow(
            "SELECT parent_batch_id, child_batch_id FROM qc_batch_genealogy WHERE id=$1", edge_id)
        if edge is None:
            raise HTTPException(404, "Genealogy edge not found")
        # An issued (APPROVED/RELEASED) certificate's batch lineage is part of
        # its traceable record — removing an edge that feeds it would silently
        # rewrite history for a document already handed out.
        issued = await c.fetchval(
            "SELECT 1 FROM qc_certificates WHERE batch_id = ANY($1) AND status = ANY($2) LIMIT 1",
            [edge["parent_batch_id"], edge["child_batch_id"]], list(_ISSUED_FROZEN))
        if issued:
            raise HTTPException(409, "That edge feeds an issued (APPROVED/RELEASED) certificate's"
                                     " batch lineage and cannot be removed")
        await c.execute("DELETE FROM qc_batch_genealogy WHERE id=$1", edge_id)
    return Response(status_code=204)


@router.get("/genealogy/{batch_id}")
async def get_genealogy(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The lineage around a batch: its ancestors (recursively up), descendants
    (recursively down), and the direct parent/child edges."""
    async with rls(user) as c:
        parents = await c.fetch(
            "SELECT * FROM qc_batch_genealogy WHERE child_batch_id=$1 ORDER BY created_at", batch_id)
        children = await c.fetch(
            "SELECT * FROM qc_batch_genealogy WHERE parent_batch_id=$1 ORDER BY created_at", batch_id)
        ancestors = await c.fetch(
            "WITH RECURSIVE a AS ("
            "  SELECT parent_batch_id AS b, 1 AS depth FROM qc_batch_genealogy WHERE child_batch_id=$1"
            "  UNION"
            "  SELECT g.parent_batch_id, a.depth+1 FROM qc_batch_genealogy g JOIN a ON g.child_batch_id=a.b)"
            " SELECT b, min(depth) AS depth FROM a GROUP BY b ORDER BY depth, b", batch_id)
        descendants = await c.fetch(
            "WITH RECURSIVE d AS ("
            "  SELECT child_batch_id AS b, 1 AS depth FROM qc_batch_genealogy WHERE parent_batch_id=$1"
            "  UNION"
            "  SELECT g.child_batch_id, d.depth+1 FROM qc_batch_genealogy g JOIN d ON g.parent_batch_id=d.b)"
            " SELECT b, min(depth) AS depth FROM d GROUP BY b ORDER BY depth, b", batch_id)
    return {
        "batch_id": batch_id,
        "parents": [_edge_out(dict(r)) for r in parents],
        "children": [_edge_out(dict(r)) for r in children],
        "ancestors": [{"batch_id": r["b"], "depth": r["depth"]} for r in ancestors],
        "descendants": [{"batch_id": r["b"], "depth": r["depth"]} for r in descendants],
    }


@router.get("/genealogy/{batch_id}/inherited-results")
async def get_inherited_results(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """CoQ-level inheritance (QCSOP 012 D3): the RELEASED-certificate results of
    this batch's ANCESTOR batches, available for a finished-product CoQ to inherit
    from its intermediate/bulk lots. Advisory — surfaced for the compiler, never
    auto-copied into a certificate (a human decides what a blend carries forward)."""
    async with rls(user) as c:
        anc = await c.fetch(
            "WITH RECURSIVE a AS ("
            "  SELECT parent_batch_id AS b FROM qc_batch_genealogy WHERE child_batch_id=$1"
            "  UNION"
            "  SELECT g.parent_batch_id FROM qc_batch_genealogy g JOIN a ON g.child_batch_id=a.b)"
            " SELECT DISTINCT b FROM a", batch_id)
        ancestor_ids = [r["b"] for r in anc]
        inherited = []
        if ancestor_ids:
            certs = await c.fetch(
                "SELECT * FROM qc_certificates WHERE batch_id = ANY($1::text[])"
                " AND status='RELEASED' ORDER BY batch_id, created_at", ancestor_ids)
            for cert in certs:
                results = await c.fetch(
                    "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", cert["id"])
                inherited.append({
                    "from_batch_id": cert["batch_id"],
                    "coa_number": cert["coa_number"],
                    "decision": cert["decision"],
                    "results": [_result_out(dict(r)) for r in results],
                })
    return {"batch_id": batch_id, "ancestors": ancestor_ids, "inherited": inherited}
