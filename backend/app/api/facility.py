"""Facility board — live cultivation occupancy (rooms + plant batches).

The owner's ask: how many plants are in each grow room, what strain, what
cultivation phase; how many in clones/nursery, vegetation, flowering.

Access model (role gating here, org isolation via RLS as everywhere):
  read   — every role above base USER (executives, QP, ALL department
           managers), per the owner's request;
  rooms  — opened and edited by whoever RUNS them (owner's model,
           2026-09-05): ADMIN and the executives for any room, assigned to a
           department or not; a department manager for rooms of the kinds
           their department operates, within their own department or one of
           its sub-departments — cultivation opens clone / nursery / veg /
           flower / mother rooms, production opens dry rooms (_KINDS_BY_ROLE).
           Rooms used to be ADMIN-only. A batch REQUIRES a room, so the
           cultivation manager could create a batch and had nowhere to put
           it: the gate was one table upstream of where it was felt.

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
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import dept_family, require_role, uuid_or_404
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/facility", tags=["facility"])

# Must stay in step with rooms_kind_check (migration 0064). 'clone' is a
# distinct kind because plant_batches.phase has had a distinct 'clone' phase
# since 0045 — a clone batch needs a clone room to sit in.
_KINDS = ("clone", "nursery", "veg", "flower", "mother", "dry", "other")

# Who may open or edit a room follows who RUNS it. ADMIN and the executives:
# any room. A department manager: only the kinds their department operates,
# and only within their department or one of its sub-departments. Everyone
# else is refused at the route.
_ROOM_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "PR_MGR")
_KINDS_BY_ROLE = {
    "CU_MGR": ("clone", "nursery", "veg", "flower", "mother"),
    "PR_MGR": ("dry",),
}


class RoomIn(BaseModel):
    code: str = Field(max_length=64, pattern=r"^[a-z0-9_]{1,64}$")
    name: str = Field(max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    kind: str = "flower"
    sort: int = Field(default=0, ge=0, le=1000)
    # The department that runs the room. A manager who omits it gets their
    # own — a room they open is theirs; ADMIN / executives may leave it unset.
    department_id: str | None = Field(default=None, max_length=64)


class RoomPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    kind: str | None = None
    sort: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None
    department_id: str | None = Field(default=None, max_length=64)


def _check_kind(kind: str | None) -> None:
    if kind is not None and kind not in _KINDS:
        raise HTTPException(422, f"kind must be one of: {', '.join(_KINDS)}")


def _kinds_for(user: dict) -> tuple | None:
    """The room kinds this actor may touch; None = any (ADMIN / executives)."""
    if user["role"] == ADMIN or user["role"] in EXECUTIVE_ROLES:
        return None
    return _KINDS_BY_ROLE.get(user["role"], ())


async def _actor_family(c, user: dict) -> list[str] | None:
    """The departments this actor may place a room in: None for ADMIN and the
    executives (any, or none), otherwise the manager's own department and its
    sub-departments. A manager with no department assigned may open nothing —
    there is no department for the room to belong to."""
    if _kinds_for(user) is None:
        return None
    if not user.get("department_id"):
        raise HTTPException(403, "No department assigned — ask an admin to set your department")
    return await dept_family(c, str(user["department_id"]))


async def _check_department(c, department_id: str | None) -> None:
    """Org-scoped existence check under RLS — a bare FK would accept any org's
    real department id, the same hole tasks.py closes on every id it takes."""
    if department_id is None:
        return
    try:
        uuid.UUID(str(department_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(422, "department_id must be a uuid")
    if not await c.fetchval("SELECT 1 FROM departments WHERE id=$1 AND is_active", department_id):
        raise HTTPException(422, "Unknown department")


def _assert_room_authority(user: dict, fam: list[str] | None, kind: str | None,
                           department_id) -> None:
    """A manager may touch a room only if it is a kind their department runs
    AND it belongs to their department (or a sub-department) — or to no
    department yet, which every room created before 0064 does: those legacy
    rooms stay editable by the manager whose kind they are, and are not
    silently claimed by editing them."""
    kinds = _kinds_for(user)
    if kinds is None:
        return
    if kind not in kinds:
        raise HTTPException(
            403, f"{user['role']} may open {', '.join(kinds)} rooms only — "
                 f"a {kind} room belongs to another department")
    if department_id is not None and str(department_id) not in (fam or []):
        raise HTTPException(403, "Managers may open rooms only in their own department")


def _room_out(row) -> dict:
    return {k: (str(v) if k in ("id", "department_id") and v is not None else v)
            for k, v in dict(row).items()
            if k not in ("org_id", "created_at", "updated_at")}


@router.get("")
async def facility(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Rooms with their live batches + org-wide phase totals — one call
    renders the whole board."""
    async with rls(user) as c:
        rooms = await c.fetch(
            "SELECT id, code, name, name_mk, kind, sort, is_active, department_id FROM rooms"
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
            "department_id": str(r["department_id"]) if r["department_id"] else None,
            "plant_total": sum(b["plant_count"] for b in blist),
        })
    totals["total"] = sum(totals.values())
    return {"rooms": out_rooms, "totals": totals}


@router.post("/rooms", status_code=201)
async def create_room(body: RoomIn, user: dict = Depends(require_role(*_ROOM_WRITERS))):
    """Idempotent on (org, code), same contract as POST /departments. Who may
    open a room follows who runs it — see _assert_room_authority."""
    _check_kind(body.kind)
    async with rls(user) as c:
        fam = await _actor_family(c, user)
        # A manager's room is theirs unless they say which sub-department;
        # ADMIN / executives leave a room unassigned unless they say otherwise.
        dept = body.department_id or (str(user["department_id"]) if fam is not None else None)
        await _check_department(c, dept)
        _assert_room_authority(user, fam, body.kind, dept)
        row = await c.fetchrow(
            "INSERT INTO rooms(org_id, code, name, name_mk, kind, sort, department_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7)"
            " ON CONFLICT (org_id, code) DO NOTHING RETURNING *",
            user["org_id"], body.code, body.name, body.name_mk, body.kind, body.sort, dept)
        if row is None:
            row = await c.fetchrow(
                "SELECT * FROM rooms WHERE org_id=$1 AND code=$2",
                user["org_id"], body.code)
    return _room_out(row)


@router.patch("/rooms/{room_id}")
async def update_room(room_id: str, body: RoomPatch,
                      user: dict = Depends(require_role(*_ROOM_WRITERS))):
    uuid_or_404(room_id, "Room not found")
    patch = body.model_dump(exclude_unset=True)
    _check_kind(patch.get("kind"))
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT kind, department_id FROM rooms WHERE id=$1", room_id)
        if cur is None:
            raise HTTPException(404, "Room not found")
        fam = await _actor_family(c, user)
        # The room as it IS must be theirs to touch…
        _assert_room_authority(user, fam, cur["kind"], cur["department_id"])
        # …and the room as it WILL BE must still be theirs: no retyping a
        # veg room into a dry room, no moving it to another department, and
        # no unassigning it so that anyone of that kind could edit it next.
        new_kind = patch.get("kind", cur["kind"])
        new_dept = patch["department_id"] if "department_id" in patch else cur["department_id"]
        if fam is not None and "department_id" in patch and patch["department_id"] is None:
            raise HTTPException(403, "Only an administrator may unassign a room from its department")
        await _check_department(c, new_dept)
        _assert_room_authority(user, fam, new_kind, new_dept)
        fields, args = [], []
        for col, val in patch.items():
            # name_mk and department_id are the two fields an explicit null
            # CLEARS rather than "not supplied" (the latter for ADMIN only, above).
            if val is None and col not in ("name_mk", "department_id"):
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(room_id)
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
