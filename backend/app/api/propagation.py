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

THE OWNER'S MOTHER-PLANT ID (2026-09-05):

    GP26_S1M03-2_020

  GP26  strain abbreviation + potency grade — the ImB PRODUCT (qc_products);
  _S1   the selection campaign, numbered FACILITY-WIDE (a selection event from
        seeds, new clones or phenotypes);
  M03   mother plant number 03 of that campaign;
  -2    the mother's own generation (a second-generation clone of the initial
        mother);
  _020  its clone number in stock, 001-999.

The segments are columns (migration 0067) and the code is composed from them
by app.plantids.mother_code, then stored: a string cannot answer "what is the
next mother number in this campaign", cannot stop two mothers claiming one
line, and cannot be rebuilt if a segment is mistyped.

AND THE CLONE'S ID:

    GP26_S1M03-2_020-03.147

  -03   the third CUTTING taken from that mother (clone_run_mothers.cutting_no,
        stamped when the run is created so it can never shift afterwards);
  .147  the 147th clone of that cutting. A mother is cut 6-9+ times at 200-300
        clones each, which is why the clone number runs per cutting.

A NAME THAT WAS WRONG. Until 0067 this module derived `generations` meaning
"how many clone runs this mother was cut in" — which is not the owner's -2 at
all. That reading is now `times_cut`; `generation` means only the mother's own
generation.

Access model:
  read        — every role above base USER (ELEVATED_ROLES);
  the bank    — mother plants and selection campaigns are floor master data:
                cultivation manager (CU_MGR), QA manager (QA_MGR), executives
                and ADMIN (_WRITERS). QA joined on 2026-09-05, with the rest
                of the cultivation master data;
  a clone run — INITIATED by the same set ("the Cultivation manager and QA can
                initiate a clone production process"), which is also the set
                that registers a batch in cultivation.py, because a clone run
                is how a batch begins.

DERIVED, NEVER STORED: a mother's age (from started_on), the date it was last
cut and how many runs it has been cut for (from clone_run_mothers). A stored
"generations" counter would drift from the runs that are its evidence.

THE PROPAGATION-MATERIAL SPECIFICATION. A clone run names the official ImB
PRODUCT the material is propagated against (qc_products — the page that
carries the strain, its potency grade and the window). Recorded on the run
itself, so the record still names it after a newer version of the page
supersedes it. No product is a fact the run states with NULL, not an error
that blocks the cutting.
"""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.plantids import mother_code
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES
from app.worktime import SITE_TODAY_SQL, facility_today

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "QA_MGR")
# Mirrors _REGISTRARS in cultivation.py: whoever may register a batch may
# initiate the clone run that becomes one. The same set since QA joined the
# floor writers (owner, 2026-09-05).
_INITIATORS = _WRITERS

# Must stay in step with the CHECK constraints in migration 0065.
_MOTHER_STATUS = ("active", "retired", "destroyed")
# A selection campaign selects from seeds, from new clones, or between
# phenotypes of one strain (owner, 2026-09-05).
_MATERIALS = ("seeds", "clones", "phenotypes")
_RUN_STATUS = ("started", "transplanted", "failed")
_RUN_TERMINAL = ("transplanted", "failed")
_MAX_CUTTINGS = 100000
_CODE_RE = r"^[A-Za-z0-9_-]{1,64}$"


class CampaignIn(BaseModel):
    started_on: date | None = None
    material: str
    cultivar_id: str | None = None
    description: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=500)


class CampaignPatch(BaseModel):
    description: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=500)


class MotherIn(BaseModel):
    # The five segments of the owner's ID. mother_no and stock_no default to
    # the next free number, so the common case is: pick the product and the
    # campaign, save.
    product_id: str
    campaign_id: str
    mother_no: int | None = Field(default=None, ge=1, le=99)
    generation: int = Field(default=1, ge=1, le=9)
    stock_no: int | None = Field(default=None, ge=1, le=999)
    parent_id: str | None = None
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
    # The official product the material is propagated against (qc_products);
    # replaces the ladder snapshot 0065 took.
    product_id: str | None = None
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


# ── selection campaigns (the S<n> in a mother-plant ID) ─────────────────────

@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT sc.*, cv.code AS cultivar_code, cv.name AS cultivar_name,"
            " (SELECT count(*) FROM mother_plants m WHERE m.campaign_id=sc.id) AS mothers_count"
            " FROM selection_campaigns sc"
            " LEFT JOIN cultivars cv ON cv.id=sc.cultivar_id ORDER BY sc.seq")
    return {"campaigns": [{
        "id": str(r["id"]), "seq": r["seq"], "label": f"S{r['seq']}",
        "started_on": _iso(r["started_on"]), "material": r["material"],
        "cultivar_id": _sid(r["cultivar_id"]), "cultivar_code": r["cultivar_code"],
        "cultivar_name": r["cultivar_name"], "description": r["description"],
        "note": r["note"], "mothers_count": int(r["mothers_count"] or 0),
    } for r in rows]}


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignIn, user: dict = Depends(require_role(*_WRITERS))):
    """Open a selection campaign — S1, S2, S3 … numbered FACILITY-WIDE, whatever
    the strain, because that is what the owner's ID means by S3: "the third such
    event". The number is minted under an advisory lock so two campaigns opened
    at once cannot claim one number."""
    if body.material not in _MATERIALS:
        raise HTTPException(422, f"material must be one of: {', '.join(_MATERIALS)}")
    async with rls(user) as c:
        if body.cultivar_id:
            await _cultivar_or_422(c, body.cultivar_id)
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))",
                        f"campaign:{user['org_id']}")
        seq = int(await c.fetchval(
            "SELECT coalesce(max(seq), 0) + 1 FROM selection_campaigns") or 1)
        row = await c.fetchrow(
            # SITE_TODAY_SQL is a module constant rendered at import; data is bound.
            "INSERT INTO selection_campaigns(org_id, seq, started_on, material,"  # nosec B608
            " cultivar_id, description, note, created_by, updated_by)"
            f" VALUES ($1,$2,COALESCE($3::date,{SITE_TODAY_SQL}),$4,$5,$6,$7,$8,$8)"
            " RETURNING id, seq, started_on",
            user["org_id"], seq, body.started_on, body.material, body.cultivar_id or None,
            body.description, body.note, user["id"])
        await safe_emit(c, user, verb="campaign_started", object_type="selection_campaign",
                        object_id=row["id"], recipients=[],
                        params={"seq": row["seq"], "material": body.material,
                                "started_on": row["started_on"].isoformat()})
    return {"id": str(row["id"]), "seq": row["seq"], "label": f"S{row['seq']}",
            "started_on": row["started_on"].isoformat(), "material": body.material,
            "cultivar_id": body.cultivar_id, "description": body.description,
            "note": body.note, "mothers_count": 0}


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignPatch,
                          user: dict = Depends(require_role(*_WRITERS))):
    """Only the prose. The number, the date and the material are what the
    campaign IS — every mother cut in it carries the number in its id."""
    uuid_or_404(campaign_id, "Campaign not found")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchval("SELECT 1 FROM selection_campaigns WHERE id=$1", campaign_id)
        if cur is None:
            raise HTTPException(404, "Campaign not found")
        fields, args = [], []
        for col, val in patch.items():
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(campaign_id)
        await c.execute(
            # Column names from CampaignPatch's own fields; values are bound.
            f"UPDATE selection_campaigns SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
    return {"ok": True}


# ── the mother-plant bank ────────────────────────────────────────────────────

# The measured Total Δ9-THC of an APPROVED CoQ — the same read the products
# module and the CoQ disposition use, so the three can never disagree.
_TOTAL_LINE = (
    "SELECT l.result_numeric FROM qc_coq_lines l"
    " JOIN qc_spec_parameters sp ON sp.id = l.parameter_id"
    " WHERE l.coq_id = q.id AND sp.computed_kind='total_thc'"
    " AND l.result_numeric IS NOT NULL LIMIT 1")

_MOTHER_SQL = (
    "SELECT m.*, cv.code AS cultivar_code, cv.name AS cultivar_name, r.name AS room_name,"
    " pr.product_code, pr.grade AS product_grade, pr.nominal_pct AS product_nominal,"
    " pr.window_min AS product_window_min, pr.window_max AS product_window_max,"
    " pr.status AS product_status,"
    " sc.seq AS campaign_seq, sc.material AS campaign_material,"
    " pm.code AS parent_code,"
    " (SELECT max(cr.started_on) FROM clone_run_mothers cm JOIN clone_runs cr ON cr.id=cm.run_id"
    "   WHERE cm.mother_plant_id=m.id) AS last_cut_on,"
    # How many CUTTINGS this mother has given — renamed from `generations`,
    # which collided with the mother's own generation (the -2 in its id).
    " (SELECT count(*) FROM clone_run_mothers cm WHERE cm.mother_plant_id=m.id) AS times_cut,"
    " (SELECT coalesce(sum(cm.cuttings), 0) FROM clone_run_mothers cm"
    "   WHERE cm.mother_plant_id=m.id) AS cuttings_total,"
    # What this mother's specification strain has tested so far — the owner
    # asked to see it on the plant itself.
    " tv.tested_n, tv.tested_avg, tv.tested_min, tv.tested_max"
    " FROM mother_plants m"
    " JOIN cultivars cv ON cv.id=m.cultivar_id"
    " JOIN qc_products pr ON pr.id=m.product_id"
    " JOIN selection_campaigns sc ON sc.id=m.campaign_id"
    " LEFT JOIN rooms r ON r.id=m.room_id"
    " LEFT JOIN mother_plants pm ON pm.id=m.parent_id"
    " LEFT JOIN LATERAL (SELECT count(*) AS tested_n, avg(x.v) AS tested_avg,"
    "     min(x.v) AS tested_min, max(x.v) AS tested_max"
    "   FROM (SELECT (" + _TOTAL_LINE + ") AS v FROM qc_coq q"
    "         WHERE q.product_id = m.product_id AND q.status='APPROVED') x"
    "   WHERE x.v IS NOT NULL) tv ON true")


def _fl(v):
    return float(v) if v is not None else None


def _mother_out(r, today: date) -> dict:
    started = r["started_on"]
    return {
        "id": str(r["id"]), "code": r["code"],
        # The five segments the code is composed from (0067) — exposed so the
        # form can offer the next number rather than parsing the string back.
        "product_id": str(r["product_id"]),
        "product_code": r["product_code"], "product_grade": _fl(r["product_grade"]),
        "product_status": r["product_status"],
        "product_window": ([_fl(r["product_window_min"]), _fl(r["product_window_max"])]
                           if r["product_window_min"] is not None else None),
        "campaign_id": str(r["campaign_id"]), "campaign_seq": r["campaign_seq"],
        "campaign_label": f"S{r['campaign_seq']}", "campaign_material": r["campaign_material"],
        "mother_no": r["mother_no"], "generation": r["generation"], "stock_no": r["stock_no"],
        "parent_id": _sid(r["parent_id"]), "parent_code": r["parent_code"],
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
        # How many cuttings this mother has given. NOT its generation — that is
        # `generation` above, the -2 in its id.
        "times_cut": int(r["times_cut"] or 0),
        "cuttings_total": int(r["cuttings_total"] or 0),
        # The potency measured for this mother's specification strain so far.
        "tested": {"n": int(r["tested_n"] or 0), "avg": _fl(r["tested_avg"]),
                   "min": _fl(r["tested_min"]), "max": _fl(r["tested_max"])},
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
            " ORDER BY pr.product_code, m.code", active)
    mothers = [_mother_out(r, today) for r in rows]
    by_cv: dict = {}
    for m in mothers:
        s = by_cv.setdefault(m["cultivar_id"], {
            "cultivar_id": m["cultivar_id"], "cultivar_code": m["cultivar_code"],
            "cultivar_name": m["cultivar_name"], "active": 0, "total": 0,
            "phenotypes": [], "products": []})
        s["total"] += 1
        if m["product_code"] not in s["products"]:
            s["products"].append(m["product_code"])
        if m["status"] == "active":
            s["active"] += 1
        if m["phenotype"] and m["phenotype"] not in s["phenotypes"]:
            s["phenotypes"].append(m["phenotype"])
    return {"mothers": mothers, "by_cultivar": list(by_cv.values())}


async def _product_or_422(c, product_id):
    """The specification strain a mother belongs to. It must be APPROVED: the
    grade in the plant's id (GP26) comes from the product's nominal, and a
    draft page can still change its nominal."""
    uuid_or_422(product_id, "Unknown product")
    row = await c.fetchrow(
        "SELECT p.id, p.product_code, p.grade, p.status, p.cultivar_id, cv.code AS cultivar_code"
        " FROM qc_products p JOIN cultivars cv ON cv.id=p.cultivar_id WHERE p.id=$1", product_id)
    if row is None:
        raise HTTPException(422, "Unknown product")
    if row["status"] != "APPROVED":
        raise HTTPException(422, f"{row['product_code']} is {row['status']} — a mother plant"
                                 " belongs to an APPROVED product specification")
    return row


async def _campaign_or_422(c, campaign_id):
    uuid_or_422(campaign_id, "Unknown selection campaign")
    row = await c.fetchrow("SELECT id, seq FROM selection_campaigns WHERE id=$1", campaign_id)
    if row is None:
        raise HTTPException(422, "Unknown selection campaign")
    return row


async def _next_numbers(c, campaign_id, product_id, mother_no=None, generation=1):
    """The next free mother number in the campaign, and the next stock number
    on that line.

    mother_no counts PER CAMPAIGN — the owner's words are "motherplant number
    03 of the corresponding Selection campaign", so M03 is the third mother of
    S1 whatever its strain. stock_no counts within one line: the same campaign,
    product, mother number and generation. Both are max+1, never count(*): a
    retired plant keeps its number, and reusing it would point two plants at
    one id."""
    next_mother = int(await c.fetchval(
        "SELECT coalesce(max(mother_no), 0) + 1 FROM mother_plants WHERE campaign_id=$1",
        campaign_id) or 1)
    if mother_no is None:
        mother_no = next_mother
    next_stock = int(await c.fetchval(
        "SELECT coalesce(max(stock_no), 0) + 1 FROM mother_plants"
        " WHERE campaign_id=$1 AND product_id=$2 AND mother_no=$3 AND generation=$4",
        campaign_id, product_id, mother_no, generation) or 1)
    return mother_no, next_mother, next_stock


@router.get("/mothers/next-code")
async def next_mother_code(product_id: str = Query(...), campaign_id: str = Query(...),
                           mother_no: int | None = Query(None, ge=1, le=99),
                           generation: int = Query(1, ge=1, le=9),
                           user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The next mother ID for a product in a campaign — GP26_S1M04-1_001.

    A suggestion, not a reservation: the form fills its segments from this and
    every one stays editable, because the facility numbers plants, not the app."""
    async with rls(user) as c:
        pr = await _product_or_422(c, product_id)
        camp = await _campaign_or_422(c, campaign_id)
        chosen, next_mother, next_stock = await _next_numbers(
            c, camp["id"], pr["id"], mother_no, generation)
    return {
        "acronym": pr["cultivar_code"], "grade": float(pr["grade"]),
        "product_code": pr["product_code"], "campaign_seq": camp["seq"],
        "head": mother_code(pr["cultivar_code"], pr["grade"], camp["seq"], chosen,
                            generation, 1)[:-3],
        "mother_no": chosen, "next_mother_no": next_mother,
        "generation": generation, "next_stock_no": next_stock,
        "suggested": mother_code(pr["cultivar_code"], pr["grade"], camp["seq"], chosen,
                                 generation, next_stock),
    }


@router.post("/mothers", status_code=201)
async def create_mother(body: MotherIn, user: dict = Depends(require_role(*_WRITERS))):
    """Register a mother plant against a product and a selection campaign.

    The code is COMPOSED from the segments rather than typed, so the bank
    cannot hold a plant whose id disagrees with its own record. Two mothers may
    not claim one line (409): an id must identify exactly one plant."""
    async with rls(user) as c:
        pr = await _product_or_422(c, body.product_id)
        camp = await _campaign_or_422(c, body.campaign_id)
        if body.room_id:
            await _room_or_422(c, body.room_id)
        generation = body.generation
        parent = None
        if body.parent_id:
            uuid_or_422(body.parent_id, "Unknown parent mother plant")
            parent = await c.fetchrow(
                "SELECT id, code, generation, product_id FROM mother_plants WHERE id=$1",
                body.parent_id)
            if parent is None:
                raise HTTPException(422, "Unknown parent mother plant")
            if _sid(parent["product_id"]) != _sid(pr["id"]):
                raise HTTPException(
                    422, f"{parent['code']} is not a {pr['product_code']} mother —"
                         " a clone cannot change its specification strain")
            # The generation FOLLOWS from the parent: a clone of a
            # second-generation mother is third-generation, and a number that
            # said otherwise would be a lie the id then carries.
            generation = parent["generation"] + 1
        elif generation > 1:
            # Allowed: the plant a later generation came from may not be in the
            # bank (an outside clone of a known line). Its own generation is
            # still recorded.
            parent = None
        mother_no, _next_m, next_stock = await _next_numbers(
            c, camp["id"], pr["id"], body.mother_no, generation)
        stock_no = body.stock_no if body.stock_no is not None else next_stock
        code = mother_code(pr["cultivar_code"], pr["grade"], camp["seq"],
                           mother_no, generation, stock_no)
        dup = await c.fetchval(
            "SELECT 1 FROM mother_plants WHERE org_id=$1 AND code=$2", user["org_id"], code)
        if dup:
            raise HTTPException(409, f"mother plant {code} already exists")
        row = await c.fetchrow(
            "INSERT INTO mother_plants(org_id, cultivar_id, product_id, campaign_id,"
            " mother_no, generation, stock_no, parent_id, code, phenotype, room_id, \"position\","
            " started_on, source, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16) RETURNING id",
            user["org_id"], pr["cultivar_id"], pr["id"], camp["id"], mother_no, generation,
            stock_no, parent["id"] if parent else None, code, body.phenotype,
            body.room_id or None, body.position, body.started_on, body.source, body.note,
            user["id"])
        await safe_emit(c, user, verb="mother_registered", object_type="mother_plant",
                        object_id=row["id"], recipients=[],
                        params={"code": code, "product_code": pr["product_code"],
                                "campaign": f"S{camp['seq']}"})
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
    " pr.product_code, pr.grade AS product_grade, pr.status AS product_status,"
    " (SELECT json_agg(json_build_object('id', cm.id, 'mother_plant_id', cm.mother_plant_id,"
    "     'code', mp.code, 'phenotype', mp.phenotype, 'cuttings', cm.cuttings,"
    "     'cutting_no', cm.cutting_no) ORDER BY mp.code)"
    "   FROM clone_run_mothers cm JOIN mother_plants mp ON mp.id=cm.mother_plant_id"
    "   WHERE cm.run_id=cr.id) AS mothers"
    " FROM clone_runs cr"
    " JOIN cultivars cv ON cv.id=cr.cultivar_id"
    " LEFT JOIN rooms r ON r.id=cr.room_id"
    " LEFT JOIN plant_batches b ON b.id=cr.batch_id"
    " LEFT JOIN qc_products pr ON pr.id=cr.product_id")


def _run_out(r) -> dict:
    mothers = _json(r["mothers"])
    return {
        "id": str(r["id"]), "code": r["code"],
        "cultivar_id": str(r["cultivar_id"]),
        "cultivar_code": r["cultivar_code"], "cultivar_name": r["cultivar_name"],
        "started_on": _iso(r["started_on"]), "planned_count": r["planned_count"],
        "room_id": _sid(r["room_id"]), "room_name": r["room_name"],
        "batch_id": _sid(r["batch_id"]), "batch_code": r["batch_code"],
        "product_id": _sid(r["product_id"]), "product_code": r["product_code"],
        "product_grade": float(r["product_grade"]) if r["product_grade"] is not None else None,
        "product_status": r["product_status"],
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
        product = None
        if body.product_id:
            product = await _product_or_422(c, body.product_id)
            if _sid(product["cultivar_id"]) != _sid(cv["id"]):
                raise HTTPException(422, f"{product['product_code']} is not this cultivar's product")
        row = await c.fetchrow(
            # SITE_TODAY_SQL is a module constant rendered at import; every
            # value travels in the bound parameters.
            "INSERT INTO clone_runs(org_id, cultivar_id, code, started_on, planned_count,"  # nosec B608
            " room_id, batch_id, product_id, note, created_by, updated_by)"
            f" VALUES ($1,$2,$3,COALESCE($4::date,{SITE_TODAY_SQL}),$5,$6,$7,$8,$9,$10,$10)"
            " RETURNING id, started_on",
            user["org_id"], cv["id"], body.code, body.started_on, body.planned_count,
            body.room_id or None, body.batch_id or None,
            product["id"] if product else None, body.note, user["id"])
        for mid, cuttings in mothers:
            # The cutting number is stamped NOW and never recomputed: it is the
            # xx in every clone's own id (GP26_S1M03-2_020-03.147), so a number
            # that shifted later would rename plants that already exist. The
            # advisory lock makes two runs cutting one mother at the same moment
            # take 03 and 04 rather than both taking 03.
            await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"cutting:{mid}")
            cutting_no = int(await c.fetchval(
                "SELECT coalesce(max(cutting_no), 0) + 1 FROM clone_run_mothers"
                " WHERE mother_plant_id=$1", mid) or 1)
            if cutting_no > 99:
                raise HTTPException(
                    409, "this mother has been cut 99 times — the clone id has no room for another")
            await c.execute(
                "INSERT INTO clone_run_mothers(org_id, run_id, mother_plant_id, cuttings,"
                " cutting_no, created_by) VALUES ($1,$2,$3,$4,$5,$6)",
                user["org_id"], row["id"], mid, cuttings, cutting_no, user["id"])
        await safe_emit(c, user, verb="clone_run_started", object_type="clone_run",
                        object_id=row["id"], recipients=[],
                        params={"cultivar": cv["code"], "strain": cv["name"],
                                "planned_count": body.planned_count,
                                "mothers": len(mothers),
                                "product_code": product["product_code"] if product else None,
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


@router.get("/mothers/{mother_id}/potency")
async def mother_potency(mother_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """What this mother's specification strain has tested so far, and which of
    it can be traced to this plant.

    The owner asked for "the potency scores tested so far, as an average value,
    and info regarding individual Total THC% scores tested so far from that
    Specification Strain". `product` is that: every APPROVED Certificate of
    Quality issued against the mother's product. `traced` is the subset whose
    lot descends from a batch this mother was actually cut into — a smaller,
    stronger claim, and often empty, because it needs the clone run to name its
    batch and the harvest to have recorded the lot. Neither is inflated by the
    other."""
    uuid_or_404(mother_id, "Mother plant not found")
    async with rls(user) as c:
        m = await c.fetchrow(
            "SELECT m.id, m.code, m.product_id, pr.product_code, pr.window_min, pr.window_max"
            " FROM mother_plants m JOIN qc_products pr ON pr.id=m.product_id WHERE m.id=$1",
            mother_id)
        if m is None:
            raise HTTPException(404, "Mother plant not found")
        product_rows = await c.fetch(
            "SELECT q.id, q.coq_number, q.batch_id, q.compiled_at,"
            f" ({_TOTAL_LINE}) AS total_thc FROM qc_coq q"
            " WHERE q.product_id=$1 AND q.status='APPROVED' ORDER BY q.compiled_at",
            m["product_id"])
        # Cut into a batch → the batch's code → the CULTIVATION genealogy edge
        # → the lot a certificate names. A text join at the last hop, which is
        # why this is reported as its own, weaker figure.
        traced_rows = await c.fetch(
            "WITH batches AS ("
            "   SELECT DISTINCT b.code FROM clone_run_mothers cm"
            "     JOIN clone_runs cr ON cr.id = cm.run_id"
            "     JOIN plant_batches b ON b.id = cr.batch_id"
            "    WHERE cm.mother_plant_id = $1 AND b.code IS NOT NULL"
            "   UNION"
            "   SELECT DISTINCT b.code FROM plants p JOIN plant_batches b ON b.id = p.batch_id"
            "    WHERE p.mother_plant_id = $1 AND b.code IS NOT NULL),"
            " lots AS (SELECT g.child_batch_id AS code FROM qc_batch_genealogy g"
            "          JOIN batches ON batches.code = g.parent_batch_id"
            "          WHERE g.relation='CULTIVATION'"
            "          UNION SELECT code FROM batches)"
            " SELECT q.id, q.coq_number, q.batch_id, q.compiled_at,"
            f" ({_TOTAL_LINE}) AS total_thc FROM qc_coq q"
            " WHERE q.status='APPROVED' AND q.batch_id IN (SELECT code FROM lots)"
            " ORDER BY q.compiled_at", mother_id)

    def _rows(rs):
        return [{"coq_number": r["coq_number"], "lot_code": r["batch_id"],
                 "total_thc": _fl(r["total_thc"]),
                 "on": r["compiled_at"].isoformat() if r["compiled_at"] else None}
                for r in rs if r["total_thc"] is not None]

    def _stats(rows):
        vals = [x["total_thc"] for x in rows]
        return {"n": len(vals), "avg": round(sum(vals) / len(vals), 2) if vals else None,
                "min": min(vals) if vals else None, "max": max(vals) if vals else None,
                "values": rows}

    return {"mother_id": str(m["id"]), "code": m["code"],
            "product_code": m["product_code"],
            "window": [_fl(m["window_min"]), _fl(m["window_max"])],
            "product": _stats(_rows(product_rows)),
            "traced": _stats(_rows(traced_rows))}
