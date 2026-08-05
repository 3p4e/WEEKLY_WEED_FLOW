"""Irrigation / feeding record (migration 0052).

Phase 2's last cultivation record (docs/CULTIVATION-DESIGN-2026-07.md §5). A
dated, room-level log of what solution went onto a room — volume, feed and
runoff EC/pH, the recipe — with an optional batch scope for a room holding more
than one cultivar.

Routes hang off the `/cultivation` prefix, a third router on that prefix
alongside cultivation.py (identity/lifecycle) and harvest.py (yield + IPM),
because a feed IS a cultivation record; it simply lives in its own module the
way harvest does.

Access model, same shape as harvest.py:
  read    — every role above base USER (ELEVATED_ROLES);
  record  — cultivation crew (CU_MGR) + executives + ADMIN (_RECORDERS).

There is no gate here and no override: unlike a spray, a feed carries no
re-entry or pre-harvest interval, so nothing downstream blocks on it and there
is nothing to release. That is the whole reason this record could land on its
own rather than interlocked with harvest the way IPM had to be.

The one discipline it shares with harvest is the SITE clock: "today" is resolved
by Postgres at the facility zone, never `date.today()` (the container's UTC),
because a feed logged at 01:00 local on the 6th must not be filed under the 5th.
The column is a plain date because the day, not the hour, is the grain the floor
logs — but the day is the SITE's day.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.db import rls
from app.deps import require_role, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

_RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")

# Must stay in step with irrigation_events_method_check in migration 0052.
_METHODS = ("drip", "hand", "flood", "boom", "other")


def _site_tz() -> str:
    return settings.snapshot_tz or "UTC"


async def _site_today(c) -> date:
    """Today AT THE SITE, resolved by Postgres — the same discipline as
    harvest.py's `_site_today`. Not `date.today()`, which renders under the
    container's UTC zone and would misfile an evening feed by a day."""
    return await c.fetchval("SELECT (now() AT TIME ZONE $1)::date", _site_tz())


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _batch_or_422(c, batch_id: str):
    uuid_or_422(batch_id, "Unknown batch")
    b = await c.fetchrow("SELECT id, room_id FROM plant_batches WHERE id=$1", batch_id)
    if b is None:
        raise HTTPException(422, "Unknown batch")
    return b


def _num(v):
    return float(v) if v is not None else None


def _iso(v):
    return v.isoformat() if v is not None else None


class FeedIn(BaseModel):
    room_id: str
    batch_id: str | None = None
    applied_on: date | None = None
    method: str | None = None
    # Readings are optional (a feed may be metered or not); ranges mirror the
    # CHECK constraints so a slip surfaces as a clean 422, not an asyncpg 500.
    water_volume_l: float | None = Field(default=None, ge=0, le=1000000)
    feed_ec: float | None = Field(default=None, ge=0, le=100)
    feed_ph: float | None = Field(default=None, ge=0, le=14)
    runoff_ec: float | None = Field(default=None, ge=0, le=100)
    runoff_ph: float | None = Field(default=None, ge=0, le=14)
    nutrients: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


def _feed_out(r) -> dict:
    return {
        "id": str(r["id"]),
        "room_id": str(r["room_id"]),
        "room_name": r["room_name"],
        "batch_id": str(r["batch_id"]) if r["batch_id"] else None,
        "batch_code": r["batch_code"],
        "applied_on": _iso(r["applied_on"]),
        "method": r["method"],
        "water_volume_l": _num(r["water_volume_l"]),
        "feed_ec": _num(r["feed_ec"]), "feed_ph": _num(r["feed_ph"]),
        "runoff_ec": _num(r["runoff_ec"]), "runoff_ph": _num(r["runoff_ph"]),
        "nutrients": r["nutrients"], "note": r["note"],
    }


@router.get("/irrigation")
async def list_irrigation(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                          room_id: str | None = Query(None),
                          batch_id: str | None = Query(None),
                          limit: int = Query(100, ge=1, le=500)):
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    if batch_id is not None:
        uuid_or_422(batch_id, "batch_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT e.*, r.name AS room_name, b.code AS batch_code"
            " FROM irrigation_events e"
            " LEFT JOIN rooms r ON r.id=e.room_id"
            " LEFT JOIN plant_batches b ON b.id=e.batch_id"
            " WHERE ($1::uuid IS NULL OR e.room_id=$1)"
            "   AND ($2::uuid IS NULL OR e.batch_id=$2)"
            " ORDER BY e.applied_on DESC, e.created_at DESC LIMIT $3",
            room_id, batch_id, limit)
    return {"feeds": [_feed_out(r) for r in rows]}


@router.post("/irrigation", status_code=201)
async def create_irrigation(body: FeedIn, user: dict = Depends(require_role(*_RECORDERS))):
    if body.method is not None and body.method not in _METHODS:
        raise HTTPException(422, f"method must be one of: {', '.join(_METHODS)}")
    async with rls(user) as c:
        await _room_or_422(c, body.room_id)
        if body.batch_id is not None:
            await _batch_or_422(c, body.batch_id)
        # "today" at the site, resolved by Postgres — never the container's UTC.
        applied_on = body.applied_on or await _site_today(c)
        row = await c.fetchrow(
            "INSERT INTO irrigation_events(org_id, room_id, batch_id, applied_on,"
            " method, water_volume_l, feed_ec, feed_ph, runoff_ec, runoff_ph,"
            " nutrients, applied_by, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$12,$12)"
            " RETURNING *, (SELECT name FROM rooms WHERE id=$2) AS room_name,"
            "   (SELECT code FROM plant_batches WHERE id=$3) AS batch_code",
            user["org_id"], body.room_id, body.batch_id, applied_on,
            body.method, body.water_volume_l, body.feed_ec, body.feed_ph,
            body.runoff_ec, body.runoff_ph, body.nutrients, user["id"], body.note)
        await safe_emit(c, user, verb="irrigation_logged", object_type="irrigation_event",
                        object_id=row["id"], recipients=[],
                        params={"room_name": row["room_name"], "method": row["method"],
                                "applied_on": _iso(row["applied_on"])})
    return _feed_out(row)
