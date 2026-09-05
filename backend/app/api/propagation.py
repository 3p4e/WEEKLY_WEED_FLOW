"""Propagation — the mother-plant bank and clone runs (migration 0065).

Where a batch begins. Cultivation runs the plant from seed, import or clone up
to the harvest cut (roles.py); this module is the clone end of that span: the
MOTHER-PLANT BANK the facility cuts from, and the CLONE RUN that records one
cutting event — which cultivar, from which mothers, how many cuttings, into
which room, on which date — and, once the cuttings root, which coded batch
they became. It sits on the /cultivation prefix beside cultivation.py
(identity), harvest.py (yield + IPM) and irrigation.py (feeding) because a
clone run IS a cultivation record; it simply lives in its own module.

Owner's description (2026-09-05): "a motherplant bank where we can list the
strains and phenotypes of mother plants, number of mother plants per strain
and all of them with unique ID number, and information regarding each
individual mother plant, when was last time when was cut for clones i.e. how
many generations of clones are produced so far, what mother room it is
located in or the number of pot or location in the room, how old it is; they
have to set the date of cloning initiation."

Access model:
  read        — every role above base USER (ELEVATED_ROLES);
  the bank    — registering and editing mother plants is floor master data:
                cultivation manager (CU_MGR) + executives + ADMIN (_WRITERS);
  a clone run — INITIATED by cultivation or QA ("the Cultivation manager and
                QA can initiate a clone production process") + executives +
                ADMIN (_INITIATORS): the same set that registers a batch in
                cultivation.py, because a clone run is how a batch begins.

DERIVED, NEVER STORED: a mother's age (from started_on), the date it was last
cut and how many runs it has been cut for (from clone_run_mothers). A stored
"generations" counter would drift from the runs that are its evidence.

THE PROPAGATION-MATERIAL SPECIFICATION. A clone run snapshots the cultivar's
APPROVED potency ladder (qc_potency_specs — the ImB Product Specification, the
document that carries the strain's name and its potency grades) at
initiation, so the record still names the specification the material was
propagated against after a newer ladder supersedes it. No approved ladder is
a fact the run states with NULL, not an error that blocks the cutting.
"""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES
from app.worktime import SITE_TODAY_SQL, facility_today

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")
# Mirrors _REGISTRARS in cultivation.py: whoever may register a batch may
# initiate the clone run that becomes one.
_INITIATORS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "QA_MGR")

# Must stay in step with the CHECK constraints in migration 0065.
_MOTHER_STATUS = ("active", "retired", "destroyed")
_RUN_STATUS = ("started", "transplanted", "failed")
_RUN_TERMINAL = ("transplanted", "failed")
_MAX_CUTTINGS = 100000
_CODE_RE = r"^[A-Za-z0-9_-]{1,64}$"


class MotherIn(BaseModel):
    cultivar_id: str
    code: str = Field(max_length=64, pattern=_CODE_RE)
    phenotype: str | None = Field(default=None, max_length=120)
    room_id: str | None = None
    position: str | None = Field(default=None, max_length=120)
    started_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class MotherPatch(BaseModel):
    phenotype: str | None = Field(default=None, max_length=120)
    room_id: str | None = None
    position: str | None = Field(default=None, max_length=120)
    started_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    status: str | None = None
    status_since: date | None = None
    note: str | None = Field(default=None, max_length=500)


class RunMotherIn(BaseModel):
    mother_plant_id: str
    cuttings: int | None = Field(default=None, ge=0, le=_MAX_CUTTINGS)


class CloneRunIn(BaseModel):
    cultivar_id: str
    started_on: date | None = None          # the date of cloning initiation
    planned_count: int = Field(default=0, ge=0, le=_MAX_CUTTINGS)
    room_id: str | None = None
    batch_id: str | None = None             # the coded batch the run feeds, if known
    code: str | None = Field(default=None, max_length=64, pattern=_CODE_RE)
    note: str | None = Field(default=None, max_length=500)
    mothers: list[RunMotherIn] = Field(default_factory=list, max_length=200)


class CloneRunPatch(BaseModel):
    status: str | None = None
    finished_on: date | None = None
    batch_id: str | None = None
    room_id: str | None = None
    planned_count: int | None = Field(default=None, ge=0, le=_MAX_CUTTINGS)
    note: str | None = Field(default=None, max_length=500)


def _iso(d):
    return d.isoformat() if d else None


def _sid(v):
    return str(v) if v is not None else None


def _json(v):
    """asyncpg hands json_agg back as text; an empty aggregate is SQL NULL."""
    if v is None:
        return []
    return json.loads(v) if isinstance(v, str) else v


async def _cultivar_or_422(c, cultivar_id):
    uuid_or_422(cultivar_id, "Unknown or inactive cultivar")
    cv = await c.fetchrow(
        "SELECT id, code, name FROM cultivars WHERE id=$1 AND is_active", cultivar_id)
    if cv is None:
        raise HTTPException(422, "Unknown or inactive cultivar")
    return cv


async def _room_or_422(c, room_id):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name, kind FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _batch_of_cultivar_or_422(c, batch_id, cultivar_id):
    """The batch a run feeds must exist, be open, and be the SAME cultivar —
    cuttings of one strain cannot become a batch of another."""
    uuid_or_422(batch_id, "Unknown or closed batch")
    b = await c.fetchrow(
        "SELECT id, code, cultivar_id FROM plant_batches WHERE id=$1 AND is_active", batch_id)
    if b is None:
        raise HTTPException(422, "Unknown or closed batch")
    if _sid(b["cultivar_id"]) != _sid(cultivar_id):
        raise HTTPException(422, f"batch {b['code']} is not this cultivar")
    return b


# ── the mother-plant bank ────────────────────────────────────────────────────

_MOTHER_SQL = (
    "SELECT m.*, cv.code AS cultivar_code, cv.name AS cultivar_name, r.name AS room_name,"
    " (SELECT max(cr.started_on) FROM clone_run_mothers cm JOIN clone_runs cr ON cr.id=cm.run_id"
    "   WHERE cm.mother_plant_id=m.id) AS last_cut_on,"
    " (SELECT count(*) FROM clone_run_mothers cm WHERE cm.mother_plant_id=m.id) AS generations,"
    " (SELECT coalesce(sum(cm.cuttings), 0) FROM clone_run_mothers cm"
    "   WHERE cm.mother_plant_id=m.id) AS cuttings_total"
    " FROM mother_plants m"
    " JOIN cultivars cv ON cv.id=m.cultivar_id"
    " LEFT JOIN rooms r ON r.id=m.room_id")


def _mother_out(r, today: date) -> dict:
    started = r["started_on"]
    return {
        "id": str(r["id"]), "code": r["code"],
        "cultivar_id": str(r["cultivar_id"]),
        "cultivar_code": r["cultivar_code"], "cultivar_name": r["cultivar_name"],
        "phenotype": r["phenotype"],
        "room_id": _sid(r["room_id"]), "room_name": r["room_name"],
        "position": r["position"],
        "started_on": _iso(started),
        # Age is derived on read from the establishment date; a mother with no
        # recorded date has no age rather than an age of zero.
        "age_days": (today - started).days if started else None,
        "source": r["source"], "status": r["status"],
        "status_since": _iso(r["status_since"]), "note": r["note"],
        "last_cut_on": _iso(r["last_cut_on"]),
        "generations": int(r["generations"] or 0),
        "cuttings_total": int(r["cuttings_total"] or 0),
    }


@router.get("/mothers")
async def list_mothers(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                       active: bool = Query(True)):
    """The bank: every mother, plus the per-strain count the owner asked for
    ("number of mother plants per strain") computed here, not by the client."""
    today = facility_today()
    async with rls(user) as c:
        rows = await c.fetch(
            _MOTHER_SQL + " WHERE ($1::bool IS FALSE OR m.status='active')"
            " ORDER BY cv.code, m.code", active)
    mothers = [_mother_out(r, today) for r in rows]
    by_cv: dict = {}
    for m in mothers:
        s = by_cv.setdefault(m["cultivar_id"], {
            "cultivar_id": m["cultivar_id"], "cultivar_code": m["cultivar_code"],
            "cultivar_name": m["cultivar_name"], "active": 0, "total": 0, "phenotypes": []})
        s["total"] += 1
        if m["status"] == "active":
            s["active"] += 1
        if m["phenotype"] and m["phenotype"] not in s["phenotypes"]:
            s["phenotypes"].append(m["phenotype"])
    return {"mothers": mothers, "by_cultivar": list(by_cv.values())}


@router.get("/mothers/next-code")
async def next_mother_code(cultivar_id: str = Query(...),
                           user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Suggest the next mother ID for a cultivar: <cultivar code>_M<NN>.

    The constant head is the cultivar code (the same head plant ids and batch
    codes carry) and the tail is the next free number in the bank. Only a
    suggestion — the field stays editable — and a facility convention, once
    the owner states one, replaces this rule in one place."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, cultivar_id)
        prefix = f"{cv['code']}_M"
        n = await c.fetchval(
            "SELECT count(*) FROM mother_plants WHERE cultivar_id=$1 AND code LIKE $2",
            cv["id"], prefix + "%")
    seq = int(n or 0) + 1
    return {"prefix": prefix, "seq": seq, "suggested": f"{prefix}{seq:02d}"}


@router.post("/mothers", status_code=201)
async def create_mother(body: MotherIn, user: dict = Depends(require_role(*_WRITERS))):
    """Register a mother plant. The ID must be new — a duplicate is a 409, not a
    silent return of the other plant (two mothers are two plants)."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, body.cultivar_id)
        if body.room_id:
            await _room_or_422(c, body.room_id)
        dup = await c.fetchval(
            "SELECT 1 FROM mother_plants WHERE org_id=$1 AND code=$2", user["org_id"], body.code)
        if dup:
            raise HTTPException(409, f"mother plant {body.code} already exists")
        row = await c.fetchrow(
            "INSERT INTO mother_plants(org_id, cultivar_id, code, phenotype, room_id, \"position\","
            " started_on, source, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10) RETURNING id",
            user["org_id"], cv["id"], body.code, body.phenotype, body.room_id or None,
            body.position, body.started_on, body.source, body.note, user["id"])
        full = await c.fetchrow(_MOTHER_SQL + " WHERE m.id=$1", row["id"])
    return _mother_out(full, facility_today())


@router.patch("/mothers/{mother_id}")
async def update_mother(mother_id: str, body: MotherPatch,
                        user: dict = Depends(require_role(*_WRITERS))):
    uuid_or_404(mother_id, "Mother plant not found")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM mother_plants WHERE id=$1", mother_id)
        if cur is None:
            raise HTTPException(404, "Mother plant not found")
        if "status" in patch:
            if patch["status"] not in _MOTHER_STATUS:
                raise HTTPException(422, f"status must be one of: {', '.join(_MOTHER_STATUS)}")
            # A destroyed plant does not come back; a retired one may.
            if cur["status"] == "destroyed" and patch["status"] != "destroyed":
                raise HTTPException(409, "a destroyed mother plant cannot be reinstated")
        if patch.get("room_id"):
            await _room_or_422(c, patch["room_id"])
        fields, args = [], []
        for col, val in patch.items():
            # Explicit null CLEARS these; an absent key leaves them alone.
            if val is None and col not in ("phenotype", "room_id", "position", "started_on",
                                           "source", "note"):
                continue
            args.append(val)
            fields.append(f"\"{col}\"=${len(args)}" if col == "position" else f"{col}=${len(args)}")
        if "status" in patch and patch["status"] != cur["status"] and "status_since" not in patch:
            fields.append(f"status_since={SITE_TODAY_SQL}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(mother_id)
        await c.execute(
            # The only interpolation is SITE_TODAY_SQL and the column list
            # built from MotherPatch's own field names; data is bound.
            f"UPDATE mother_plants SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
        full = await c.fetchrow(_MOTHER_SQL + " WHERE m.id=$1", mother_id)
    return _mother_out(full, facility_today())


# ── clone runs ───────────────────────────────────────────────────────────────

_RUN_SQL = (
    "SELECT cr.*, cv.code AS cultivar_code, cv.name AS cultivar_name,"
    " r.name AS room_name, b.code AS batch_code,"
    " ps.version AS spec_version, ps.status AS spec_status, ps.spec_code,"
    " (SELECT json_agg(json_build_object('id', cm.id, 'mother_plant_id', cm.mother_plant_id,"
    "     'code', mp.code, 'phenotype', mp.phenotype, 'cuttings', cm.cuttings) ORDER BY mp.code)"
    "   FROM clone_run_mothers cm JOIN mother_plants mp ON mp.id=cm.mother_plant_id"
    "   WHERE cm.run_id=cr.id) AS mothers"
    " FROM clone_runs cr"
    " JOIN cultivars cv ON cv.id=cr.cultivar_id"
    " LEFT JOIN rooms r ON r.id=cr.room_id"
    " LEFT JOIN plant_batches b ON b.id=cr.batch_id"
    " LEFT JOIN qc_potency_specs ps ON ps.id=cr.potency_spec_id")


def _run_out(r) -> dict:
    mothers = _json(r["mothers"])
    return {
        "id": str(r["id"]), "code": r["code"],
        "cultivar_id": str(r["cultivar_id"]),
        "cultivar_code": r["cultivar_code"], "cultivar_name": r["cultivar_name"],
        "started_on": _iso(r["started_on"]), "planned_count": r["planned_count"],
        "room_id": _sid(r["room_id"]), "room_name": r["room_name"],
        "batch_id": _sid(r["batch_id"]), "batch_code": r["batch_code"],
        "potency_spec_id": _sid(r["potency_spec_id"]),
        "spec_code": r["spec_code"], "spec_version": r["spec_version"],
        "spec_status": r["spec_status"],
        "status": r["status"], "finished_on": _iso(r["finished_on"]), "note": r["note"],
        "mothers": mothers,
        "cuttings_total": sum(int(m.get("cuttings") or 0) for m in mothers),
        "created_at": r["created_at"].isoformat(),
    }


@router.get("/clone-runs")
async def list_clone_runs(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                          active: bool = Query(True)):
    async with rls(user) as c:
        rows = await c.fetch(
            _RUN_SQL + " WHERE ($1::bool IS FALSE OR cr.status='started')"
            " ORDER BY cr.started_on DESC, cr.created_at DESC", active)
    return {"runs": [_run_out(r) for r in rows]}


@router.post("/clone-runs", status_code=201)
async def create_clone_run(body: CloneRunIn,
                           user: dict = Depends(require_role(*_INITIATORS))):
    """Initiate cloning: the cultivar, the date, the mothers cut, the cuttings
    planned, the room they go into — and the batch they feed, if it is already
    registered. Snapshots the cultivar's APPROVED product specification."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, body.cultivar_id)
        if body.room_id:
            await _room_or_422(c, body.room_id)
        if body.batch_id:
            await _batch_of_cultivar_or_422(c, body.batch_id, cv["id"])
        if body.code:
            dup = await c.fetchval(
                "SELECT 1 FROM clone_runs WHERE org_id=$1 AND code=$2", user["org_id"], body.code)
            if dup:
                raise HTTPException(409, f"clone run {body.code} already exists")
        mothers, seen = [], set()
        for m in body.mothers:
            uuid_or_422(m.mother_plant_id, "Unknown mother plant")
            if m.mother_plant_id in seen:
                raise HTTPException(422, "a mother plant is listed twice")
            seen.add(m.mother_plant_id)
            row = await c.fetchrow(
                "SELECT id, code, cultivar_id, status FROM mother_plants WHERE id=$1",
                m.mother_plant_id)
            if row is None:
                raise HTTPException(422, "Unknown mother plant")
            if _sid(row["cultivar_id"]) != _sid(cv["id"]):
                raise HTTPException(422, f"mother plant {row['code']} is not {cv['code']}")
            if row["status"] != "active":
                raise HTTPException(422, f"mother plant {row['code']} is {row['status']}")
            mothers.append((row["id"], m.cuttings))
        spec_id = await c.fetchval(
            "SELECT id FROM qc_potency_specs WHERE cultivar_id=$1 AND status='APPROVED'", cv["id"])
        row = await c.fetchrow(
            # SITE_TODAY_SQL is a module constant rendered at import; every
            # value travels in the bound parameters.
            "INSERT INTO clone_runs(org_id, cultivar_id, code, started_on, planned_count,"  # nosec B608
            " room_id, batch_id, potency_spec_id, note, created_by, updated_by)"
            f" VALUES ($1,$2,$3,COALESCE($4::date,{SITE_TODAY_SQL}),$5,$6,$7,$8,$9,$10,$10)"
            " RETURNING id, started_on",
            user["org_id"], cv["id"], body.code, body.started_on, body.planned_count,
            body.room_id or None, body.batch_id or None, spec_id, body.note, user["id"])
        for mid, cuttings in mothers:
            await c.execute(
                "INSERT INTO clone_run_mothers(org_id, run_id, mother_plant_id, cuttings, created_by)"
                " VALUES ($1,$2,$3,$4,$5)", user["org_id"], row["id"], mid, cuttings, user["id"])
        await safe_emit(c, user, verb="clone_run_started", object_type="clone_run",
                        object_id=row["id"], recipients=[],
                        params={"cultivar": cv["code"], "strain": cv["name"],
                                "planned_count": body.planned_count,
                                "mothers": len(mothers),
                                "started_on": row["started_on"].isoformat()})
        full = await c.fetchrow(_RUN_SQL + " WHERE cr.id=$1", row["id"])
    return _run_out(full)


@router.patch("/clone-runs/{run_id}")
async def update_clone_run(run_id: str, body: CloneRunPatch,
                           user: dict = Depends(require_role(*_INITIATORS))):
    """Close a run (transplanted / failed), link the batch it became, or
    correct its count, room or note. A finished run does not change again."""
    uuid_or_404(run_id, "Clone run not found")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, cultivar_id, finished_on FROM clone_runs WHERE id=$1", run_id)
        if cur is None:
            raise HTTPException(404, "Clone run not found")
        if cur["status"] in _RUN_TERMINAL and patch:
            raise HTTPException(409, f"clone run is {cur['status']}; it cannot change again")
        if "status" in patch:
            if patch["status"] not in _RUN_STATUS:
                raise HTTPException(422, f"status must be one of: {', '.join(_RUN_STATUS)}")
        if patch.get("batch_id"):
            await _batch_of_cultivar_or_422(c, patch["batch_id"], cur["cultivar_id"])
        if patch.get("room_id"):
            await _room_or_422(c, patch["room_id"])
        fields, args = [], []
        for col, val in patch.items():
            if val is None and col not in ("batch_id", "room_id", "note"):
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if patch.get("status") in _RUN_TERMINAL and "finished_on" not in patch:
            fields.append(f"finished_on={SITE_TODAY_SQL}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(run_id)
        await c.execute(
            # Column list from CloneRunPatch's own field names + SITE_TODAY_SQL;
            # data is bound.
            f"UPDATE clone_runs SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
        full = await c.fetchrow(_RUN_SQL + " WHERE cr.id=$1", run_id)
    return _run_out(full)
