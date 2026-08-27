"""Facility board — live cultivation occupancy (rooms + plant batches).

The owner's ask: how many plants are in each grow room, what strain, what
cultivation phase; how many in clones/nursery, vegetation, flowering.

Access model (role gating here, org isolation via RLS as everywhere):
  read   — every role above base USER (executives, QP, ALL department
           managers), per the owner's request;
  rooms  — registry changes are ADMIN-only, same reasoning as POST
           /departments: physical org structure is a system-administration
           concern, seeded via API so the audit trail attributes it.

READ-ONLY over plant_batches. Batch create/move/close lives exclusively in
cultivation.py — this board used to also expose POST/PATCH /facility/batches,
a second, independent write path over the same `plant_batches` row
cultivation.py owns. That duplication was a real defect, not a style choice:
the facility-side batch model had no `cultivar_id`/`code` (so a batch created
there could never get plant ids or a genealogy edge), no validation of
`plant_count` against the headcount invariant harvest.py/waste.py trust, no
`plant_phase_events` audit trail on a move, and its own phase vocabulary was a
strict subset of cultivation.py's — so an ordinary cultivation batch sitting
in `nursery`, `harvested`, or `destroyed` (all normal, expected phases) could
crash this endpoint's phase-totals computation outright. Batch management now
lives only at /cultivation/batches; this file only ever reads what's there.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404
from app.roles import ADMIN, ELEVATED_ROLES

router = APIRouter(prefix="/facility", tags=["facility"])

_KINDS = ("nursery", "veg", "flower", "mother", "dry", "other")


class RoomIn(BaseModel):
    code: str = Field(max_length=64, pattern=r"^[a-z0-9_]{1,64}$")
    name: str = Field(max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    kind: str = "flower"
    sort: int = Field(default=0, ge=0, le=1000)


class RoomPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    kind: str | None = None
    sort: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None


def _check_kind(kind: str | None) -> None:
    if kind is not None and kind not in _KINDS:
        raise HTTPException(422, f"kind must be one of: {', '.join(_KINDS)}")


@router.get("")
async def facility(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Rooms with their live batches + org-wide phase totals — one call
    renders the whole board."""
    async with rls(user) as c:
        rooms = await c.fetch(
            "SELECT id, code, name, name_mk, kind, sort, is_active FROM rooms"
            " WHERE is_active ORDER BY sort, name")
        batches = await c.fetch(
            "SELECT id, room_id, strain, plant_count, phase, phase_since, note,"
            " updated_at FROM plant_batches WHERE is_active"
            " ORDER BY phase_since, strain")
    by_room: dict = {}
    # A plain dict keyed by whatever phase strings actually show up, not a
    # fixed whitelist — cultivation.py's phase vocabulary is a superset of
    # this board's own display phases (nursery, plus the terminal states,
    # though terminal batches never appear here since they're is_active=false
    # by the time they get there). Any phase the DB actually contains must be
    # summable without a KeyError; a fixed dict comprehension over a narrower
    # tuple is exactly what crashed this endpoint before.
    totals: dict = {}
    for b in batches:
        row = {
            "id": str(b["id"]), "room_id": str(b["room_id"]), "strain": b["strain"],
            "plant_count": b["plant_count"], "phase": b["phase"],
            "phase_since": b["phase_since"].isoformat() if b["phase_since"] else None,
            "note": b["note"], "updated_at": b["updated_at"].isoformat(),
        }
        by_room.setdefault(row["room_id"], []).append(row)
        totals[b["phase"]] = totals.get(b["phase"], 0) + b["plant_count"]
    out_rooms = []
    for r in rooms:
        rid = str(r["id"])
        blist = by_room.get(rid, [])
        out_rooms.append({
            "id": rid, "code": r["code"], "name": r["name"], "name_mk": r["name_mk"],
            "kind": r["kind"], "sort": r["sort"], "batches": blist,
            "plant_total": sum(b["plant_count"] for b in blist),
        })
    totals["total"] = sum(totals.values())
    return {"rooms": out_rooms, "totals": totals}


@router.post("/rooms", status_code=201)
async def create_room(body: RoomIn, user: dict = Depends(require_role(ADMIN))):
    """ADMIN-only, idempotent (same contract as POST /departments)."""
    _check_kind(body.kind)
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO rooms(org_id, code, name, name_mk, kind, sort)"
            " VALUES ($1,$2,$3,$4,$5,$6)"
            " ON CONFLICT (org_id, code) DO NOTHING RETURNING *",
            user["org_id"], body.code, body.name, body.name_mk, body.kind, body.sort)
        if row is None:
            row = await c.fetchrow(
                "SELECT * FROM rooms WHERE org_id=$1 AND code=$2",
                user["org_id"], body.code)
    return {k: (str(v) if k == "id" else v) for k, v in dict(row).items()
            if k not in ("org_id", "created_at", "updated_at")}


@router.patch("/rooms/{room_id}")
async def update_room(room_id: str, body: RoomPatch,
                      user: dict = Depends(require_role(ADMIN))):
    uuid_or_404(room_id, "Room not found")
    patch = body.model_dump(exclude_unset=True)
    _check_kind(patch.get("kind"))
    fields, args = [], []
    for col, val in patch.items():
        if val is None and col != "name_mk":
            continue
        args.append(val); fields.append(f"{col}=${len(args)}")
    if not fields:
        return {"ok": True, "noop": True}
    args.append(room_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE rooms SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING id", *args)
    if row is None:
        raise HTTPException(404, "Room not found")
    return {"ok": True}


# Batch create/move/close: see the module docstring — this used to be a
# second write path over plant_batches, independent of and inconsistent with
# cultivation.py's. Removed; use POST /cultivation/batches and
# POST /cultivation/batches/{id}/move instead.
