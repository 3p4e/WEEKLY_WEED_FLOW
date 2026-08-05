"""Biosecurity events (migration 0053) — the four §5c record types on one board.

AHU filter pull/refit (§18), disinfection-mat refill + strip verification (§20),
contact plates + sentinel bioassay (§27), and gowning / zone-crossing (§23, §28
control 5). One table, one board, discriminated by `kind` — see the migration
header for why these four are one record shape and not four.

A second router on the `/decon` prefix, the same way harvest is a second router
on `/cultivation`: biosecurity monitoring belongs to the decontamination board
(that is where the swabs, bleach log and tool log already live), it simply lives
in its own module.

Access model:
  read    — every role above base USER (ELEVATED_ROLES);
  record  — cultivation crew (CU_MGR) AND QA (QA_MGR) + executives + ADMIN. Both,
            because these records straddle the two: the crew refill mats and pull
            filters, QA reads plates and runs the bioassay, and either may verify
            gowning.

THE ONE GATE, MIRRORED FROM THE DATABASE. A result of `fail` or `below_spec`
must carry an `action_taken`. It is pre-checked here for a clean 422 with a
reason, and backstopped by `biosecurity_events_action_on_fail_check` so no route
into the table — the API, a script, a direct SQL fix — can record a failed
biosecurity check that nobody responded to. That is the §27 gap this record
exists to close.

"Today" is resolved at the site zone by Postgres, the same discipline as
harvest.py and irrigation.py — never `date.today()` (the container's UTC).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.db import rls
from app.deps import require_role, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/decon", tags=["decon"])

_RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "QA_MGR")

# Stay in step with biosecurity_events_kind_check / _result_check in 0053.
_KINDS = ("ahu_filter", "disinfection_mat", "contact_plate", "sentinel_bioassay", "gowning")
_RESULTS = ("pass", "fail", "below_spec", "pending")
_FAIL_RESULTS = ("fail", "below_spec")


def _site_tz() -> str:
    return settings.snapshot_tz or "UTC"


async def _site_today(c) -> date:
    """Today AT THE SITE, resolved by Postgres — never `date.today()`."""
    return await c.fetchval("SELECT (now() AT TIME ZONE $1)::date", _site_tz())


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


def _num(v):
    return float(v) if v is not None else None


class BioIn(BaseModel):
    kind: str
    room_id: str | None = None
    location: str | None = Field(default=None, max_length=200)
    occurred_on: date | None = None
    subject: str | None = Field(default=None, max_length=200)
    action: str | None = Field(default=None, max_length=200)
    measure_value: float | None = Field(default=None, ge=0, le=1000000000)
    measure_unit: str | None = Field(default=None, max_length=40)
    result: str | None = None
    action_taken: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


def _bio_out(r) -> dict:
    return {
        "id": str(r["id"]),
        "kind": r["kind"],
        "room_id": str(r["room_id"]) if r["room_id"] else None,
        "room_name": r["room_name"],
        "location": r["location"],
        "occurred_on": r["occurred_on"].isoformat() if r["occurred_on"] else None,
        "subject": r["subject"], "action": r["action"],
        "measure_value": _num(r["measure_value"]), "measure_unit": r["measure_unit"],
        "result": r["result"], "action_taken": r["action_taken"], "note": r["note"],
    }


@router.get("/biosecurity")
async def list_biosecurity(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                           kind: str | None = Query(None),
                           room_id: str | None = Query(None),
                           open_only: bool = Query(False),
                           limit: int = Query(200, ge=1, le=500)):
    if kind is not None and kind not in _KINDS:
        raise HTTPException(422, f"kind must be one of: {', '.join(_KINDS)}")
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT e.*, r.name AS room_name"
            " FROM biosecurity_events e"
            " LEFT JOIN rooms r ON r.id=e.room_id"
            " WHERE ($1::text IS NULL OR e.kind=$1)"
            "   AND ($2::uuid IS NULL OR e.room_id=$2)"
            "   AND ($3 = false OR e.result IN ('fail','below_spec'))"
            " ORDER BY e.occurred_on DESC, e.created_at DESC LIMIT $4",
            kind, room_id, open_only, limit)
    return {"events": [_bio_out(r) for r in rows]}


@router.post("/biosecurity", status_code=201)
async def create_biosecurity(body: BioIn, user: dict = Depends(require_role(*_RECORDERS))):
    if body.kind not in _KINDS:
        raise HTTPException(422, f"kind must be one of: {', '.join(_KINDS)}")
    if body.result is not None and body.result not in _RESULTS:
        raise HTTPException(422, f"result must be one of: {', '.join(_RESULTS)}")
    # Mirror the DB invariant so a failing check with no response is a clean 422
    # rather than an asyncpg 500: a below-spec mat or a positive plate nobody
    # acted on is exactly the gap §27 exists to close.
    if body.result in _FAIL_RESULTS and not (body.action_taken and body.action_taken.strip()):
        raise HTTPException(
            422, "a failing result must state the action taken — a below-spec or"
                 " positive biosecurity check with no response is the gap this"
                 " record exists to close")
    async with rls(user) as c:
        if body.room_id is not None:
            await _room_or_422(c, body.room_id)
        occurred_on = body.occurred_on or await _site_today(c)
        row = await c.fetchrow(
            "INSERT INTO biosecurity_events(org_id, kind, room_id, location,"
            " occurred_on, subject, action, measure_value, measure_unit, result,"
            " action_taken, performed_by, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$12,$12)"
            " RETURNING *, (SELECT name FROM rooms WHERE id=$3) AS room_name",
            user["org_id"], body.kind, body.room_id, body.location, occurred_on,
            body.subject, body.action, body.measure_value, body.measure_unit,
            body.result, body.action_taken, user["id"], body.note)
        await safe_emit(c, user, verb="biosecurity_logged", object_type="biosecurity_event",
                        object_id=row["id"], recipients=[],
                        params={"kind": row["kind"], "result": row["result"],
                                "room_name": row["room_name"]})
    return _bio_out(row)
