"""Facility board — live cultivation occupancy (rooms + plant batches).

The owner's ask: how many plants are in each grow room, what strain, what
cultivation phase; how many in clones/nursery, vegetation, flowering.

Access model (role gating here, org isolation via RLS as everywhere):
  read   — every role above base USER (executives, QP, ALL department
           managers), per the owner's request;
  write  — the cultivation manager (CU_MGR), executives, ADMIN;
  rooms  — registry changes are ADMIN-only, same reasoning as POST
           /departments: physical org structure is a system-administration
           concern, seeded via API so the audit trail attributes it.

Batch changes emit feed-only events (recipients=[]) so the activity stream
shows plants moving through the facility without pinging anyone's inbox.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/facility", tags=["facility"])

_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")
_PHASES = ("clone", "veg", "flower", "mother", "drying")
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


class BatchIn(BaseModel):
    room_id: str
    strain: str = Field(max_length=120)
    plant_count: int = Field(ge=0, le=100000)
    phase: str
    phase_since: str | None = None   # ISO date; defaults to today in the DB
    note: str | None = Field(default=None, max_length=500)


class BatchPatch(BaseModel):
    room_id: str | None = None
    strain: str | None = Field(default=None, max_length=120)
    plant_count: int | None = Field(default=None, ge=0, le=100000)
    phase: str | None = None
    phase_since: str | None = None
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


def _check_phase(phase: str | None) -> None:
    if phase is not None and phase not in _PHASES:
        raise HTTPException(422, f"phase must be one of: {', '.join(_PHASES)}")


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
    totals = {p: 0 for p in _PHASES}
    for b in batches:
        row = {
            "id": str(b["id"]), "room_id": str(b["room_id"]), "strain": b["strain"],
            "plant_count": b["plant_count"], "phase": b["phase"],
            "phase_since": b["phase_since"].isoformat() if b["phase_since"] else None,
            "note": b["note"], "updated_at": b["updated_at"].isoformat(),
        }
        by_room.setdefault(row["room_id"], []).append(row)
        totals[b["phase"]] += b["plant_count"]
    out_rooms = []
    for r in rooms:
        rid = str(r["id"])
        blist = by_room.get(rid, [])
        out_rooms.append({
            "id": rid, "code": r["code"], "name": r["name"], "name_mk": r["name_mk"],
            "kind": r["kind"], "sort": r["sort"], "batches": blist,
            "plant_total": sum(b["plant_count"] for b in blist),
        })
    totals["total"] = sum(totals[p] for p in _PHASES)
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


async def _room_or_422(c, room_id: str):
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


@router.post("/batches", status_code=201)
async def create_batch(body: BatchIn, user: dict = Depends(require_role(*_WRITERS))):
    _check_phase(body.phase)
    async with rls(user) as c:
        room = await _room_or_422(c, body.room_id)
        row = await c.fetchrow(
            "INSERT INTO plant_batches(org_id, room_id, strain, plant_count, phase,"
            " phase_since, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,COALESCE($6::date, CURRENT_DATE),$7,$8,$8) RETURNING *",
            user["org_id"], body.room_id, body.strain, body.plant_count,
            body.phase, body.phase_since, body.note, user["id"])
        try:
            await emit(c, user, verb="batch_added", object_type="plant_batch",
                       object_id=row["id"], recipients=[],
                       params={"strain": row["strain"], "plant_count": row["plant_count"],
                               "phase": row["phase"], "room": room["name"]})
        except Exception:
            pass
    out = dict(row)
    return {"id": str(out["id"]), "room_id": str(out["room_id"]), "strain": out["strain"],
            "plant_count": out["plant_count"], "phase": out["phase"],
            "phase_since": out["phase_since"].isoformat(), "note": out["note"]}


@router.patch("/batches/{batch_id}")
async def update_batch(batch_id: str, body: BatchPatch,
                       user: dict = Depends(require_role(*_WRITERS))):
    patch = body.model_dump(exclude_unset=True)
    _check_phase(patch.get("phase"))
    async with rls(user) as c:
        prev = await c.fetchrow(
            "SELECT b.*, r.name AS room_name FROM plant_batches b"
            " JOIN rooms r ON r.id=b.room_id WHERE b.id=$1", batch_id)
        if prev is None:
            raise HTTPException(404, "Batch not found")
        if "room_id" in patch:
            await _room_or_422(c, patch["room_id"])
        # A phase move stamps phase_since unless the caller set it explicitly.
        if patch.get("phase") and patch["phase"] != prev["phase"] and "phase_since" not in patch:
            patch["phase_since"] = None   # placeholder; swapped to CURRENT_DATE below
        fields, args = [], []
        for col, val in patch.items():
            if col == "phase_since" and val is None:
                fields.append("phase_since=CURRENT_DATE")
                continue
            if val is None and col != "note":
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(batch_id)
        row = await c.fetchrow(
            f"UPDATE plant_batches SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
        try:
            closed = patch.get("is_active") is False
            moved = ("room_id" in patch and str(patch["room_id"]) != str(prev["room_id"])) \
                or (patch.get("phase") and patch["phase"] != prev["phase"])
            verb = "batch_closed" if closed else ("batch_moved" if moved else None)
            if verb:
                room = await c.fetchrow("SELECT name FROM rooms WHERE id=$1", row["room_id"])
                await emit(c, user, verb=verb, object_type="plant_batch",
                           object_id=row["id"], recipients=[],
                           params={"strain": row["strain"], "plant_count": row["plant_count"],
                                   "phase": row["phase"], "room": room["name"] if room else "",
                                   "old_phase": prev["phase"], "old_room": prev["room_name"]})
        except Exception:
            pass
    out = dict(row)
    return {"id": str(out["id"]), "room_id": str(out["room_id"]), "strain": out["strain"],
            "plant_count": out["plant_count"], "phase": out["phase"],
            "phase_since": out["phase_since"].isoformat(), "note": out["note"],
            "is_active": out["is_active"]}
