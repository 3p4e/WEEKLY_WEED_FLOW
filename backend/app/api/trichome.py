"""Trichome maturation checks — the documented record behind a harvest date.

The owner's rule (2026-09-05): flowering runs 6-9 weeks, and the day a batch is
actually cut is decided by "progressive tracking of maturation of trichomes for
determining the optimal harvest window using stereo or digital microscope, with
documented records". The plan's 42-63 days is the window; this record is what
closes it.

A fourth router on the /cultivation prefix beside cultivation.py (identity and
lifecycle), harvest.py (yield and IPM) and irrigation.py (feeding), for the
same reason those are separate: a trichome check IS a cultivation record, it
simply lives in its own module.

Access model:
  read   — every role above base USER (ELEVATED_ROLES);
  record — the cultivation writers (cultivation._WRITERS: CU_MGR, QA_MGR,
           executives, ADMIN).

THERE IS NO GATE HERE. Unlike a spray, a trichome check blocks nothing: the
harvest form shows the latest verdict and says so when none was taken, but a
cut is never refused for want of one. A check that refused a harvest would turn
an observation into a control the owner did not ask for — and the crew that
looks down a microscope must be free to record what they see, including
"overripe", without the record fighting them.

The percentages are the three trichome states (clear, cloudy, amber) as read
under the scope. Each is optional — a check may be qualitative — but if all
three are given they must add up to about 100, because three numbers that do
not are not a reading of one field of view. A missing percentage is missing,
never zero: 0 % amber is a real and different observation.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.cultivation import _WRITERS
from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from app.worktime import SITE_TODAY_SQL

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

# Must stay in step with the CHECK constraints in migration 0066.
_INSTRUMENTS = ("stereo", "digital")
_VERDICTS = ("immature", "approaching", "ready", "overripe")
_TERMINAL_PHASES = ("harvested", "destroyed")
_SUM_LO, _SUM_HI = 98, 102


class TrichomeIn(BaseModel):
    batch_id: str
    checked_on: date | None = None
    instrument: str
    magnification: str | None = Field(default=None, max_length=40)
    sample_sites: int | None = Field(default=None, ge=1, le=1000)
    pct_clear: float | None = Field(default=None, ge=0, le=100)
    pct_cloudy: float | None = Field(default=None, ge=0, le=100)
    pct_amber: float | None = Field(default=None, ge=0, le=100)
    verdict: str
    image_ref: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=1000)


def _out(r) -> dict:
    def _f(v):
        return float(v) if v is not None else None
    return {
        "id": str(r["id"]), "batch_id": str(r["batch_id"]), "batch_code": r["batch_code"],
        "room_id": str(r["room_id"]) if r["room_id"] else None, "room_name": r["room_name"],
        "checked_on": r["checked_on"].isoformat(), "instrument": r["instrument"],
        "magnification": r["magnification"], "sample_sites": r["sample_sites"],
        "pct_clear": _f(r["pct_clear"]), "pct_cloudy": _f(r["pct_cloudy"]),
        "pct_amber": _f(r["pct_amber"]), "verdict": r["verdict"],
        "image_ref": r["image_ref"], "note": r["note"],
        "checked_by": str(r["checked_by"]), "created_at": r["created_at"].isoformat(),
    }


_SQL = ("SELECT t.*, b.code AS batch_code, r.name AS room_name"
        " FROM trichome_checks t"
        " JOIN plant_batches b ON b.id = t.batch_id"
        " LEFT JOIN rooms r ON r.id = t.room_id")


@router.get("/trichome-checks")
async def list_checks(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                      batch_id: str | None = Query(None),
                      limit: int = Query(200, ge=1, le=1000)):
    """The maturation history, newest first — the trend is the point, so a
    single check is never the whole record."""
    if batch_id is not None:
        uuid_or_422(batch_id, "Unknown batch")
    async with rls(user) as c:
        rows = await c.fetch(
            _SQL + " WHERE ($1::uuid IS NULL OR t.batch_id=$1)"
            " ORDER BY t.checked_on DESC, t.created_at DESC LIMIT $2", batch_id, limit)
    return {"checks": [_out(r) for r in rows]}


@router.post("/trichome-checks", status_code=201)
async def record_check(body: TrichomeIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.instrument not in _INSTRUMENTS:
        raise HTTPException(422, f"instrument must be one of: {', '.join(_INSTRUMENTS)}")
    if body.verdict not in _VERDICTS:
        raise HTTPException(422, f"verdict must be one of: {', '.join(_VERDICTS)}")
    pcts = (body.pct_clear, body.pct_cloudy, body.pct_amber)
    if all(v is not None for v in pcts):
        total = sum(pcts)
        if not (_SUM_LO <= total <= _SUM_HI):
            raise HTTPException(
                422, f"clear + cloudy + amber = {total:g} % — the three states of one field of"
                     f" view must add up to about 100 %")
    uuid_or_404(body.batch_id, "Batch not found")
    async with rls(user) as c:
        b = await c.fetchrow(
            "SELECT id, code, phase, room_id FROM plant_batches WHERE id=$1", body.batch_id)
        if b is None:
            raise HTTPException(404, "Batch not found")
        if b["phase"] in _TERMINAL_PHASES:
            raise HTTPException(409, f"batch {b['code']} is {b['phase']} —"
                                     " there is nothing left to look at")
        row = await c.fetchrow(
            # SITE_TODAY_SQL is a module constant rendered at import; every
            # value travels in the bound parameters.
            "INSERT INTO trichome_checks(org_id, batch_id, room_id, checked_on,"  # nosec B608
            " instrument, magnification, sample_sites, pct_clear, pct_cloudy, pct_amber,"
            " verdict, image_ref, note, checked_by, created_by, updated_by)"
            f" VALUES ($1,$2,$3,COALESCE($4::date,{SITE_TODAY_SQL}),$5,$6,$7,$8,$9,$10,"
            "$11,$12,$13,$14,$14,$14) RETURNING id",
            user["org_id"], b["id"], b["room_id"], body.checked_on, body.instrument,
            body.magnification, body.sample_sites, body.pct_clear, body.pct_cloudy,
            body.pct_amber, body.verdict, body.image_ref, body.note, user["id"])
        await safe_emit(c, user, verb="trichome_checked", object_type="trichome_check",
                        object_id=row["id"], recipients=[],
                        params={"batch": b["code"], "verdict": body.verdict,
                                "pct_amber": body.pct_amber})
        full = await c.fetchrow(_SQL + " WHERE t.id=$1", row["id"])
    return _out(full)
