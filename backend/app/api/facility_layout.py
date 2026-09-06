"""The as-built facility layout — the building as the architect drew it.

The owner supplied the Archicad A0 ground-floor sheet on 2026-09-05 and asked
that the app know the actual layout, carry a visual reference for every room,
and hold each room's information. `docs/FACILITY-LAYOUT-2026-09.md` records how
the 191 rooms were read off the drawing; `app/data/facility_layout.json` is the
result, and `POST /facility/layout/import` loads it.

This register is NOT `rooms` (see migration 0068 for why): `rooms` is the short
list of places the app schedules, `facility_rooms` is the whole building —
corridors, air locks, plant rooms, toilets and fire escapes included. The two
are linked by `rooms.facility_room_id`, and either can exist without the other.

Access model, the shape the rest of the facility board uses:
  read     — every role above base USER (ELEVATED_ROLES);
  classify — ADMIN, the executives, and QA (`_CLASSIFIERS`): the cleanliness
             grade, the regime, the department that runs a room, and the link to
             an operational room are all QA/management judgements;
  import   — ADMIN and the executives only, because it seeds the whole register.

`grade` starts null everywhere and stays null until someone sets it. No
cleanliness grade appears anywhere on the drawing, so the app has nothing to
read it from and must not invent one — the doc asks QA for the site's scheme.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/facility/layout", tags=["facility"])

_LAYOUT_PATH = Path(__file__).resolve().parents[1] / "data" / "facility_layout.json"

_CLASSIFIERS = (ADMIN, *EXECUTIVE_ROLES, "QA_MGR")
_IMPORTERS = (ADMIN, *EXECUTIVE_ROLES)

_WINGS = ("cultivation", "processing", "extraction", "main", "technical", "washing", "other")
_ZONES = ("cultivation", "post_harvest", "production", "quality", "warehouse", "airlock",
          "circulation", "personnel", "technical", "utility", "waste", "egress")
_REGIMES = ("GACP", "GMP", "SUPPORT")


class LayoutPatch(BaseModel):
    """Only the judgement columns are editable. Code, name, area, perimeter and
    the plan anchor come off the drawing and stay as drawn — a room that is
    genuinely wrong should be corrected in the register and re-imported, so the
    app never disagrees with the sheet by accident."""
    zone: str | None = None
    regime: str | None = None
    grade: str | None = Field(default=None, max_length=40)
    department_id: str | None = Field(default=None, max_length=64)
    room_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class LayoutImportIn(BaseModel):
    dry_run: bool = False


_SELECT = """
    SELECT f.id, f.code, f.name_en, f.name_mk, f.wing, f.zone, f.regime, f.grade,
           f.floor, f.area_m2, f.net_area_m2, f.perimeter_m, f.plan_x, f.plan_y,
           f.department_id, f.source, f.notes, f.is_active,
           d.name AS department_name,
           r.id AS room_id, r.code AS room_code, r.name AS room_name, r.kind AS room_kind
      FROM facility_rooms f
      LEFT JOIN departments d ON d.id = f.department_id
      LEFT JOIN rooms r ON r.facility_room_id = f.id
"""


def _out(row) -> dict:
    d = dict(row)
    for k in ("id", "department_id", "room_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("area_m2", "net_area_m2", "perimeter_m", "plan_x", "plan_y"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    return d


def _load_register() -> list[dict]:
    with _LAYOUT_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@router.get("")
async def list_layout(zone: str | None = Query(default=None),
                      wing: str | None = Query(default=None),
                      regime: str | None = Query(default=None),
                      q: str | None = Query(default=None, max_length=120),
                      user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The register, newest classification included. Filters are additive; `q`
    matches the code or either printed name, case-insensitively."""
    where, args = ["f.is_active"], []
    for col, val in (("zone", zone), ("wing", wing), ("regime", regime)):
        if val:
            args.append(val)
            where.append(f"f.{col} = ${len(args)}")
    if q:
        args.append(f"%{q}%")
        where.append(f"(f.code ILIKE ${len(args)} OR f.name_en ILIKE ${len(args)}"
                     f" OR f.name_mk ILIKE ${len(args)})")
    sql = f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY f.wing, f.code"
    async with rls(user) as c:
        rows = await c.fetch(sql, *args)
    out = [_out(r) for r in rows]
    totals: dict[str, dict] = {}
    for r in out:
        t = totals.setdefault(r["zone"] or "unclassified", {"rooms": 0, "area_m2": 0.0})
        t["rooms"] += 1
        t["area_m2"] = round(t["area_m2"] + (r["area_m2"] or 0), 2)
    return {"rooms": out, "totals": totals,
            "vocab": {"wings": list(_WINGS), "zones": list(_ZONES), "regimes": list(_REGIMES)}}


@router.get("/{layout_id}")
async def get_layout_room(layout_id: str,
                          user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """One room, plus whatever is happening in it — the batches sitting in the
    operational room this architectural room is linked to."""
    uuid_or_404(layout_id)
    rid = layout_id
    async with rls(user) as c:
        row = await c.fetchrow(f"{_SELECT} WHERE f.id = $1", rid)
        if not row:
            raise HTTPException(404, "Unknown room")
        out = _out(row)
        out["batches"] = []
        if out.get("room_id"):
            bs = await c.fetch(
                "SELECT b.id, b.code, b.phase, b.plant_count, b.phase_since,"
                "       cv.code AS cultivar_code, cv.name AS cultivar_name"
                "  FROM plant_batches b"
                "  LEFT JOIN cultivars cv ON cv.id = b.cultivar_id"
                " WHERE b.room_id = $1 AND b.is_active"
                " ORDER BY b.phase_since DESC", out["room_id"])
            out["batches"] = [{**{k: v for k, v in dict(b).items() if k != "id"},
                               "id": str(b["id"])} for b in bs]
    return out


@router.patch("/{layout_id}")
async def patch_layout_room(layout_id: str, body: LayoutPatch,
                            user: dict = Depends(require_role(*_CLASSIFIERS))):
    """Set the judgement columns: the cleanliness grade, the regime, the zone,
    the department that runs the room, and the operational room it is."""
    uuid_or_404(layout_id)
    rid = layout_id
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(422, "Nothing to change")
    if data.get("zone") is not None and data["zone"] not in _ZONES:
        raise HTTPException(422, f"zone must be one of: {', '.join(_ZONES)}")
    if data.get("regime") is not None and data["regime"] not in _REGIMES:
        raise HTTPException(422, f"regime must be one of: {', '.join(_REGIMES)}")
    room_id = data.pop("room_id", ...)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT id, code FROM facility_rooms WHERE id=$1", rid)
        if not cur:
            raise HTTPException(404, "Unknown room")
        if data.get("department_id"):
            uuid_or_422(data["department_id"], "department_id must be a uuid")
            dept = data["department_id"]
            if not await c.fetchval("SELECT 1 FROM departments WHERE id=$1 AND is_active", dept):
                raise HTTPException(422, "Unknown department")
            data["department_id"] = dept
        sets, args = [], []
        for k, v in data.items():
            args.append(v)
            sets.append(f"{k} = ${len(args)}")
        if sets:
            args += [user["id"], rid]
            await c.execute(
                f"UPDATE facility_rooms SET {', '.join(sets)},"  # nosec B608
                f" updated_by = ${len(args)-1}, updated_at = now() WHERE id = ${len(args)}",
                *args)
        if room_id is not ...:
            # One operational room per architectural room (partial unique index
            # in 0068). Clear any previous link before making the new one, so a
            # re-link reads as a move rather than a constraint violation.
            await c.execute("UPDATE rooms SET facility_room_id = NULL"
                            " WHERE facility_room_id = $1", rid)
            if room_id:
                uuid_or_422(room_id, "room_id must be a uuid")
                op_id = room_id
                if not await c.fetchval("SELECT 1 FROM rooms WHERE id=$1", op_id):
                    raise HTTPException(422, "Unknown room")
                await c.execute("UPDATE rooms SET facility_room_id = $1,"
                                " updated_at = now() WHERE id = $2", rid, op_id)
        row = await c.fetchrow(f"{_SELECT} WHERE f.id = $1", rid)
        await safe_emit(c, user, verb="facility_room_classified",
                        object_type="facility_room", object_id=str(rid), recipients=[],
                        params={"code": cur["code"],
                                **{k: str(v) for k, v in data.items() if v is not None}})
    return _out(row)


@router.post("/import")
async def import_layout(body: LayoutImportIn,
                        user: dict = Depends(require_role(*_IMPORTERS))):
    """Load the packaged register (app/data/facility_layout.json — the 191 rooms
    read off the ground-floor sheet).

    Idempotent on (floor, code): a room already present is UPDATED with the
    drawing's own columns — name, wing, area, perimeter, anchor — and its
    judgement columns (grade, department, notes, the operational-room link) are
    left exactly as they are. Re-importing a corrected register therefore never
    discards a classification somebody made."""
    rows = _load_register()
    created, updated = [], []
    async with rls(user) as c:
        for r in rows:
            if r["wing"] not in _WINGS:
                raise HTTPException(422, f"{r['code']}: unknown wing {r['wing']}")
            if r["zone"] is not None and r["zone"] not in _ZONES:
                raise HTTPException(422, f"{r['code']}: unknown zone {r['zone']}")
            exists = await c.fetchval(
                "SELECT id FROM facility_rooms WHERE org_id=$1 AND floor='ground' AND code=$2",
                user["org_id"], r["code"])
            if body.dry_run:
                (updated if exists else created).append(r["code"])
                continue
            if exists:
                await c.execute(
                    "UPDATE facility_rooms SET name_en=$1, name_mk=$2, wing=$3, zone=$4,"
                    " area_m2=$5, net_area_m2=$6, perimeter_m=$7, plan_x=$8, plan_y=$9,"
                    " source=$10, updated_by=$11, updated_at=now() WHERE id=$12",
                    r["name_en"], r["name_mk"], r["wing"], r["zone"], r["area_m2"],
                    r["net_area_m2"], r["perimeter_m"], r["plan_x"], r["plan_y"],
                    "Layout Full.pdf (ground floor, 1:100, 03/2021)", user["id"], exists)
                updated.append(r["code"])
                continue
            await c.execute(
                "INSERT INTO facility_rooms(org_id, code, name_en, name_mk, wing, zone, regime,"
                " area_m2, net_area_m2, perimeter_m, plan_x, plan_y, source, created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$14)",
                user["org_id"], r["code"], r["name_en"], r["name_mk"], r["wing"], r["zone"],
                r["regime"], r["area_m2"], r["net_area_m2"], r["perimeter_m"],
                r["plan_x"], r["plan_y"],
                "Layout Full.pdf (ground floor, 1:100, 03/2021)", user["id"])
            created.append(r["code"])
        if not body.dry_run and (created or updated):
            await safe_emit(c, user, verb="facility_layout_imported",
                            object_type="facility_room", object_id=rows[0]["code"],
                            recipients=[],
                            params={"created": len(created), "updated": len(updated),
                                    "source": "Layout Full.pdf"})
    return {"dry_run": body.dry_run, "created": created, "updated": updated,
            "total": len(rows)}
