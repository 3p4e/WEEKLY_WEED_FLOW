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
line, and cannot be rebuilt if a segment is mistyped. The head (GP) is the
product code's acronym — the owner's "strain abbreviation" — and the form's
preview reads it from the same server answer, so the two cannot differ.

THE MOTHER NUMBER IS THE CAMPAIGN'S. "M03 = motherplant number 03 of the
corresponding Selection campaign" — one number, one line, whatever the
strain: once GP26_S1M03 exists, M03 of S1 is a Grape Pie 26 line and an OPM22
mother cannot take it (422). Migration 0070 makes the line key
(campaign, mother_no, generation, stock_no), and the next-number reads run
under an advisory lock per campaign, so two registrations at once get M05
and M06 rather than both M05.

A LINE IS ONE PRODUCT CODE, NOT ONE PRODUCT ROW. Approving a new document
version of the catalogue retires the old version's rows (qc/products.py
supersedes them), so after the fitted GP_THC26:CBD1 is approved the row a
mother was registered against is SUPERSEDED and the live page is another
row. The line-owner check and the parent check therefore compare the
product CODE; a later generation or a new stock plant registers against the
live page of that code (product_id may be left out with a parent and is
resolved to it), and the line's mothers still pointing at the retired row
are moved onto the live one at that moment, so the bank never reads
SUPERSEDED for a plant whose product did not change (review CS2-01).

A LATER GENERATION KEEPS ITS LINE. Registering from a parent takes the
campaign and the mother number FROM the parent — "GP26_S1M03-2_020 … all
clones made from this -2 (second) cloning generation of motherplant
selection S1M03" — and refuses a body that says otherwise (422). Only the
generation advances, and the stock number counts on within the new
generation.

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
that blocks the cutting. The date of cloning initiation has no default: the
owner said the initiator "has to set" it, so the run refuses to start
without one.

A RUN'S BATCH IS FROZEN ONCE THE BATCH HAS PLANTS. cultivation.generate_plants
numbers clones from the batch's runs laid end to end, so a run linked, moved
or unlinked after any plant exists would rename plants already printed. Both
directions are refused with 409; link the runs first, then fill.

"TESTED SO FAR" IS THE STRAIN'S HISTORY. The owner asked for "the potency
scores tested so far … from that Specification Strain". Three sources, each
labelled, the same three the product catalogue defines: APPROVED CoQs that
name a product of the cultivar, APPROVED CoQs that name only the cultivar,
and certificate Total THC results attributed to the strain by the batch
code's head. The strain-level figure counts each lot once (a CoQ and the
certificate it aggregates are one measurement); the product-level subset
(CoQs naming THIS product code, any version) is reported beside it. The SQL
is a self-contained copy of qc/products.py's — the two modules are owned
separately, and a shared import would couple their release cadences.
"""
import json
from datetime import date

from asyncpg.exceptions import UniqueViolationError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.plantids import (MAX_CUTTING_NO, MAX_GENERATION, MAX_MOTHER_NO, MAX_STOCK_NO,
                          acronym_of, mother_code)
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
    # campaign, save. With a parent, the campaign and the mother number come
    # FROM the parent (the line is inherited); given here they must agree.
    # product_id may be left out when a parent is named: the line's product
    # CODE is the parent's, and the row is the live (APPROVED) page of that
    # code — which is a later document version than the parent's own row
    # once the catalogue has been re-issued (review CS2-01).
    product_id: str | None = None
    campaign_id: str | None = None
    mother_no: int | None = Field(default=None, ge=1, le=MAX_MOTHER_NO)
    generation: int = Field(default=1, ge=1, le=MAX_GENERATION)
    stock_no: int | None = Field(default=None, ge=1, le=MAX_STOCK_NO)
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
    # The date of cloning initiation — REQUIRED, no default: "they have to set
    # the date of cloning initiation" (owner, 2026-09-05).
    started_on: date
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


async def _batch_unfrozen_or_409(c, batch_id, what: str):
    """A batch with plant rows has its run membership frozen: the clone ids
    were numbered from the runs laid end to end, and changing the set now
    would rename plants that exist (cultivation.generate_plants).

    Under the batch's FILL lock — the same key, byte for byte, that
    generate_plants takes while it reads its allocation plan and writes the
    first chunk. Without it a run could pass this count (0 plants committed)
    while a fill that already read the plan without it was writing chunk 1,
    and the ids on file would disagree with the runs on file (review
    CS2-04). The lock is transaction-scoped, so it is held until the run's
    own insert or relink commits and the fill's plan read sees it."""
    await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"fill:{batch_id}")
    row = await c.fetchrow(
        "SELECT b.code, (SELECT count(*) FROM plants p WHERE p.batch_id=b.id) AS n"
        " FROM plant_batches b WHERE b.id=$1", batch_id)
    if row is not None and row["n"]:
        raise HTTPException(
            409, f"batch {row['code']} already has {row['n']} plant ids numbered from its clone"
                 f" runs — {what} would renumber them; the runs of a batch are fixed once its"
                 " plants exist")


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

# The three sources of "tested so far" for a strain (see the module header).
# Self-contained copies of qc/products.py::_potency_history's reads.
_COQ_PRODUCT_SQL = (
    "SELECT q.id, q.coq_number, q.batch_id AS lot_code, q.compiled_at AS on_at,"
    " pr.product_code, (" + _TOTAL_LINE + ") AS total_thc"
    " FROM qc_coq q JOIN qc_products pr ON pr.id = q.product_id"
    " WHERE pr.cultivar_id=$1 AND q.status='APPROVED' ORDER BY q.compiled_at")
_COQ_CULTIVAR_SQL = (
    "SELECT q.id, q.coq_number, q.batch_id AS lot_code, q.compiled_at AS on_at,"
    " (" + _TOTAL_LINE + ") AS total_thc"
    " FROM qc_coq q"
    " WHERE q.product_id IS NULL AND q.cultivar_id=$1 AND q.status='APPROVED'"
    " ORDER BY q.compiled_at")
# Certificates of this cultivar's own batches: plant_batches.code is the CU
# batch (GP072501); a certificate names its batch as free text, so match the
# certificate's cultivation_batch or its batch_id against those codes.
_CERT_SQL = (
    "SELECT ct.id, ct.coa_number, ct.batch_id AS lot_code, ct.report_date AS on_at,"
    " r.result_numeric AS total_thc"
    " FROM qc_certificates ct"
    " JOIN qc_results r ON r.coa_id = ct.id"
    " JOIN qc_spec_parameters sp ON sp.id = r.parameter_id"
    " WHERE sp.computed_kind='total_thc' AND r.result_numeric IS NOT NULL"
    "   AND ct.status = ANY(ARRAY['APPROVED','RELEASED'])"
    "   AND (ct.batch_id IN (SELECT code FROM plant_batches WHERE cultivar_id=$1 AND code IS NOT NULL)"
    "     OR ct.cultivation_batch IN (SELECT code FROM plant_batches WHERE cultivar_id=$1"
    "                                 AND code IS NOT NULL))"
    " ORDER BY ct.report_date NULLS LAST")


def _stats(rows) -> dict:
    vals = [x["total_thc"] for x in rows]
    return {"n": len(vals), "avg": round(sum(vals) / len(vals), 2) if vals else None,
            "min": min(vals) if vals else None, "max": max(vals) if vals else None,
            "values": rows}


def _hist_rows(rs, number_key, source) -> list:
    return [{"number": r[number_key], "lot_code": r["lot_code"],
             "total_thc": float(r["total_thc"]), "source": source,
             "product_code": r["product_code"] if "product_code" in r.keys() else None,
             "on": r["on_at"].isoformat() if r["on_at"] else None}
            for r in rs if r["total_thc"] is not None]


async def _strain_history(c, cultivar_id, product_code=None) -> dict:
    """What a specification strain has tested so far, from the three sources,
    plus the strain-level roll-up that counts each lot once, and the subset
    that named the given product code (any version of its page)."""
    stated = _hist_rows(await c.fetch(_COQ_PRODUCT_SQL, cultivar_id), "coq_number", "coq_product")
    cultivar_level = _hist_rows(await c.fetch(_COQ_CULTIVAR_SQL, cultivar_id),
                                "coq_number", "coq_cultivar")
    certs = _hist_rows(await c.fetch(_CERT_SQL, cultivar_id), "coa_number", "certificate")
    # One measurement per lot: a CoQ aggregates the certificate it was compiled
    # from, so the same Total THC must not be averaged twice. Strongest source
    # first, and a source with no lot code cannot be matched, so it counts.
    seen, strain = set(), []
    for row in stated + cultivar_level + certs:
        key = row["lot_code"]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        strain.append(row)
    product = [r for r in stated if product_code and r["product_code"] == product_code]
    return {"strain": _stats(strain), "product": _stats(product),
            "sources": {"coq_product": _stats(stated), "coq_cultivar": _stats(cultivar_level),
                        "certificate": _stats(certs)}}


def _summary(st) -> dict:
    return {k: st[k] for k in ("n", "avg", "min", "max")}


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
    "   WHERE cm.mother_plant_id=m.id) AS cuttings_total"
    " FROM mother_plants m"
    " JOIN cultivars cv ON cv.id=m.cultivar_id"
    " JOIN qc_products pr ON pr.id=m.product_id"
    " JOIN selection_campaigns sc ON sc.id=m.campaign_id"
    " LEFT JOIN rooms r ON r.id=m.room_id"
    " LEFT JOIN mother_plants pm ON pm.id=m.parent_id")


def _fl(v):
    return float(v) if v is not None else None


def _mother_out(r, today: date, tested=None) -> dict:
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
        # The potency measured for this mother's specification STRAIN so far
        # (all three sources, one measurement per lot), and the subset that
        # named this product. See _strain_history.
        "tested": _summary(tested["strain"]) if tested else {"n": 0, "avg": None,
                                                            "min": None, "max": None},
        "tested_product": _summary(tested["product"]) if tested else {"n": 0, "avg": None,
                                                                     "min": None, "max": None},
    }


async def _tested_for(c, rows) -> dict:
    """One history read per (cultivar, product code) among the rows."""
    out = {}
    for r in rows:
        key = (str(r["cultivar_id"]), r["product_code"])
        if key not in out:
            out[key] = await _strain_history(c, r["cultivar_id"], r["product_code"])
    return out


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
        tested = await _tested_for(c, rows)
    mothers = [_mother_out(r, today, tested[(str(r["cultivar_id"]), r["product_code"])])
               for r in rows]
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


def _head(pr) -> str:
    """The strain abbreviation the id starts with: the product code's acronym
    (GP in GP_THC26:CBD1) — one source for the server and the form's preview.
    A product code that does not parse falls back to the cultivar code, which
    qc/products.py keeps equal to the acronym on every page it authors."""
    return acronym_of(pr["product_code"]) or pr["cultivar_code"]


async def _campaign_or_422(c, campaign_id):
    uuid_or_422(campaign_id, "Unknown selection campaign")
    row = await c.fetchrow(
        "SELECT id, seq, cultivar_id FROM selection_campaigns WHERE id=$1", campaign_id)
    if row is None:
        raise HTTPException(422, "Unknown selection campaign")
    return row


def _campaign_fits_product(camp, pr) -> None:
    """A campaign opened for one strain selects mothers of that strain."""
    if camp["cultivar_id"] is not None and _sid(camp["cultivar_id"]) != _sid(pr["cultivar_id"]):
        raise HTTPException(
            422, f"campaign S{camp['seq']} was opened for another strain —"
                 f" {pr['product_code']} is not a mother of that campaign's strain")


async def _next_numbers(c, campaign_id, product_id, mother_no=None, generation=1):
    """The next free mother number in the campaign, and the next stock number
    on that line.

    mother_no counts PER CAMPAIGN — the owner's words are "motherplant number
    03 of the corresponding Selection campaign", so M03 is the third mother of
    S1 whatever its strain. stock_no counts within one line: the same campaign,
    mother number and generation (the product follows from the number, see
    _line_owner_or_422). Both are max+1, never count(*): a retired plant keeps
    its number, and reusing it would point two plants at one id. Past the cap
    there is no next number, and saying so (422) beats a CHECK violation."""
    next_mother = int(await c.fetchval(
        "SELECT coalesce(max(mother_no), 0) + 1 FROM mother_plants WHERE campaign_id=$1",
        campaign_id) or 1)
    if mother_no is None:
        mother_no = next_mother
        if mother_no > MAX_MOTHER_NO:
            raise HTTPException(
                422, f"this campaign already has mother M{MAX_MOTHER_NO} — the mother id has no"
                     " room for another mother number in it")
    next_stock = int(await c.fetchval(
        "SELECT coalesce(max(stock_no), 0) + 1 FROM mother_plants"
        " WHERE campaign_id=$1 AND mother_no=$2 AND generation=$3",
        campaign_id, mother_no, generation) or 1)
    if next_stock > MAX_STOCK_NO:
        raise HTTPException(
            422, f"line M{mother_no:02d}-{generation} already holds stock number {MAX_STOCK_NO}"
                 " — the mother id has no room for another plant on this line")
    return mother_no, next_mother, next_stock


async def _line_owner_or_422(c, campaign_id, mother_no, pr) -> None:
    """A mother number names one line of one product: M03 of S1 that already
    exists as a Grape Pie 26 line cannot also be an OPM22 line.

    The product is compared by CODE, never by row id. Approving a new
    document version of the catalogue retires the old version's rows
    (qc/products.py), so the live GP_THC26:CBD1 is a different row from the
    one the line was opened against; it is still the same product, and the
    line must go on taking it (review CS2-01)."""
    other = await c.fetchrow(
        "SELECT DISTINCT pr.product_code FROM mother_plants m"
        " JOIN qc_products pr ON pr.id = m.product_id"
        " WHERE m.campaign_id=$1 AND m.mother_no=$2 AND pr.product_code <> $3 LIMIT 1",
        campaign_id, mother_no, pr["product_code"])
    if other is not None:
        raise HTTPException(
            422, f"M{mother_no:02d} of this campaign is a {other['product_code']} line —"
                 f" a mother number names one line, and {pr['product_code']} cannot take it")


async def _live_product_of_code_or_422(c, product_code: str):
    """The APPROVED row of a product code — the page the catalogue currently
    holds live for it. A code with no live page cannot take a new mother:
    the id's grade would be read off a retired or draft nominal."""
    row = await c.fetchrow(
        "SELECT p.id, p.product_code, p.grade, p.status, p.cultivar_id, cv.code AS cultivar_code"
        " FROM qc_products p JOIN cultivars cv ON cv.id=p.cultivar_id"
        " WHERE p.product_code=$1 AND p.status='APPROVED'", product_code)
    if row is None:
        raise HTTPException(
            422, f"{product_code} has no APPROVED page in the catalogue — approve the current"
                 " version of the specification before registering another mother on this line")
    return row


async def _repoint_line_to_live_product(c, user, campaign_id, mother_no, pr) -> int:
    """Move the line's mothers from a retired row of the product code onto
    the live one. Called under the campaign's advisory lock, after the code
    check above, so every mother of the line names the same live page and
    the bank reads APPROVED, not SUPERSEDED, for a plant whose product did
    not change — only the document version of its page did. Returns the
    number of rows re-pointed."""
    n = await c.fetchval(
        "WITH r AS (UPDATE mother_plants m SET product_id=$3, updated_by=$4, updated_at=now()"
        " FROM qc_products pr WHERE pr.id = m.product_id AND m.campaign_id=$1 AND m.mother_no=$2"
        "   AND pr.product_code=$5 AND m.product_id <> $3 RETURNING 1) SELECT count(*) FROM r",
        campaign_id, mother_no, pr["id"], user["id"], pr["product_code"])
    return int(n or 0)


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
        _campaign_fits_product(camp, pr)
        if mother_no is not None:
            await _line_owner_or_422(c, camp["id"], mother_no, pr)
        chosen, next_mother, next_stock = await _next_numbers(
            c, camp["id"], pr["id"], mother_no, generation)
    acr = _head(pr)
    return {
        "acronym": acr, "grade": float(pr["grade"]),
        "product_code": pr["product_code"], "campaign_seq": camp["seq"],
        "head": mother_code(acr, pr["grade"], camp["seq"], chosen, generation, 1)[:-3],
        "mother_no": chosen, "next_mother_no": next_mother,
        "generation": generation, "next_stock_no": next_stock,
        "suggested": mother_code(acr, pr["grade"], camp["seq"], chosen, generation, next_stock),
    }


@router.post("/mothers", status_code=201)
async def create_mother(body: MotherIn, user: dict = Depends(require_role(*_WRITERS))):
    """Register a mother plant against a product and a selection campaign.

    The code is COMPOSED from the segments rather than typed, so the bank
    cannot hold a plant whose id disagrees with its own record. Two mothers may
    not claim one line (409): an id must identify exactly one plant. The
    next-number reads and the insert run under one advisory lock per campaign,
    so two registrations at once cannot both read M04 and both become M05."""
    async with rls(user) as c:
        if body.room_id is not None:
            await _room_or_422(c, body.room_id)
        generation = body.generation
        parent = None
        if body.parent_id:
            uuid_or_422(body.parent_id, "Unknown parent mother plant")
            parent = await c.fetchrow(
                "SELECT m.id, m.code, m.generation, m.product_id, m.campaign_id, m.mother_no,"
                " pr.product_code"
                " FROM mother_plants m JOIN qc_products pr ON pr.id = m.product_id"
                " WHERE m.id=$1", body.parent_id)
            if parent is None:
                raise HTTPException(422, "Unknown parent mother plant")
            # The product is the parent's by CODE. Its row may be a retired
            # document version by now (a fitted page superseded the ImB one),
            # so a body that names no product takes the live page of that
            # code, and a body that names one must name the same code.
            pr = (await _product_or_422(c, body.product_id) if body.product_id
                  else await _live_product_of_code_or_422(c, parent["product_code"]))
            if parent["product_code"] != pr["product_code"]:
                raise HTTPException(
                    422, f"{parent['code']} is not a {pr['product_code']} mother —"
                         " a clone cannot change its specification strain")
            # The LINE follows from the parent: the campaign and the mother
            # number are inherited (GP26_S1M03-1 -> GP26_S1M03-2), and a body
            # that names another is contradicting the parent it names.
            if body.campaign_id is not None and body.campaign_id != _sid(parent["campaign_id"]):
                raise HTTPException(
                    422, f"{parent['code']} belongs to another selection campaign — a later"
                         " generation keeps its parent's campaign")
            if body.mother_no is not None and body.mother_no != parent["mother_no"]:
                raise HTTPException(
                    422, f"{parent['code']} is mother M{parent['mother_no']:02d} — a later"
                         " generation keeps its parent's mother number")
            # The generation FOLLOWS from the parent: a clone of a
            # second-generation mother is third-generation, and a number that
            # said otherwise would be a lie the id then carries.
            generation = parent["generation"] + 1
            if generation > MAX_GENERATION:
                raise HTTPException(
                    422, f"{parent['code']} is generation {parent['generation']} — the mother"
                         f" id numbers generations up to {MAX_GENERATION}")
            camp = await _campaign_or_422(c, str(parent["campaign_id"]))
            mother_no_wanted = parent["mother_no"]
        else:
            if body.product_id is None:
                raise HTTPException(422, "product_id is required unless a parent mother is named")
            pr = await _product_or_422(c, body.product_id)
            if body.campaign_id is None:
                raise HTTPException(422, "campaign_id is required unless a parent mother is named")
            camp = await _campaign_or_422(c, body.campaign_id)
            mother_no_wanted = body.mother_no
        _campaign_fits_product(camp, pr)
        # Everything from here reads the campaign's numbers, so serialise on it.
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"mother:{camp['id']}")
        if mother_no_wanted is not None:
            await _line_owner_or_422(c, camp["id"], mother_no_wanted, pr)
            # The line goes on under the live page of its code: mothers still
            # pointing at a retired version of the same code are moved onto
            # the row this registration names (review CS2-01).
            await _repoint_line_to_live_product(c, user, camp["id"], mother_no_wanted, pr)
        mother_no, _next_m, next_stock = await _next_numbers(
            c, camp["id"], pr["id"], mother_no_wanted, generation)
        stock_no = body.stock_no if body.stock_no is not None else next_stock
        code = mother_code(_head(pr), pr["grade"], camp["seq"], mother_no, generation, stock_no)
        dup = await c.fetchval(
            "SELECT 1 FROM mother_plants WHERE org_id=$1 AND code=$2", user["org_id"], code)
        if dup:
            raise HTTPException(409, f"mother plant {code} already exists")
        try:
            row = await c.fetchrow(
                # SITE_TODAY_SQL is a module constant rendered at import; data is bound.
                "INSERT INTO mother_plants(org_id, cultivar_id, product_id, campaign_id,"  # nosec B608
                " mother_no, generation, stock_no, parent_id, code, phenotype, room_id, \"position\","
                " started_on, source, note, status_since, created_by, updated_by)"
                f" VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,{SITE_TODAY_SQL},$16,$16)"
                " RETURNING id",
                user["org_id"], pr["cultivar_id"], pr["id"], camp["id"], mother_no, generation,
                stock_no, parent["id"] if parent else None, code, body.phenotype,
                body.room_id or None, body.position, body.started_on, body.source, body.note,
                user["id"])
        except UniqueViolationError:
            # The line key or the code: another registration took this line
            # between the read and the write (only possible from outside the
            # advisory lock, e.g. a direct SQL insert). Same answer as `dup`.
            raise HTTPException(409, f"mother plant {code} already exists")
        await safe_emit(c, user, verb="mother_registered", object_type="mother_plant",
                        object_id=row["id"], recipients=[],
                        params={"code": code, "product_code": pr["product_code"],
                                "campaign": f"S{camp['seq']}"})
        full = await c.fetchrow(_MOTHER_SQL + " WHERE m.id=$1", row["id"])
        tested = await _strain_history(c, full["cultivar_id"], full["product_code"])
    return _mother_out(full, facility_today(), tested)


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
        # `is not None`, not truthiness: null clears the room, but "" is a
        # malformed id and is refused (422) rather than reaching asyncpg.
        if patch.get("room_id") is not None:
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
        tested = await _strain_history(c, full["cultivar_id"], full["product_code"])
    return _mother_out(full, facility_today(), tested)


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
    """Initiate cloning: the cultivar, the date the initiator sets, the mothers
    cut, the cuttings planned, the room they go into — and the batch they feed,
    if it is already registered and not yet filled with plant ids. Names the
    official product the material is propagated against, if one is stated."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, body.cultivar_id)
        if body.room_id is not None:
            await _room_or_422(c, body.room_id)
        if body.batch_id is not None:
            await _batch_of_cultivar_or_422(c, body.batch_id, cv["id"])
            await _batch_unfrozen_or_409(c, body.batch_id, "linking another run to it")
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
            # Every value travels in the bound parameters; the date has no
            # default (the initiator sets it, owner 2026-09-05).
            "INSERT INTO clone_runs(org_id, cultivar_id, code, started_on, planned_count,"
            " room_id, batch_id, product_id, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10)"
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
            if cutting_no > MAX_CUTTING_NO:
                raise HTTPException(
                    409, f"this mother has been cut {MAX_CUTTING_NO} times — the clone id has no"
                         " room for another cutting")
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
            "SELECT status, cultivar_id, finished_on, batch_id FROM clone_runs WHERE id=$1", run_id)
        if cur is None:
            raise HTTPException(404, "Clone run not found")
        if cur["status"] in _RUN_TERMINAL and patch:
            raise HTTPException(409, f"clone run is {cur['status']}; it cannot change again")
        if "status" in patch:
            if patch["status"] not in _RUN_STATUS:
                raise HTTPException(422, f"status must be one of: {', '.join(_RUN_STATUS)}")
        # `is not None`, not truthiness: null unlinks, "" is a malformed id (422).
        if "batch_id" in patch and patch["batch_id"] != _sid(cur["batch_id"]):
            if patch["batch_id"] is not None:
                await _batch_of_cultivar_or_422(c, patch["batch_id"], cur["cultivar_id"])
            # Leaving a batch whose plants were numbered from this run, or
            # joining one that is already numbered, renames plants that exist.
            # Both fill locks are taken in id order, so two relinks crossing
            # between the same two batches cannot wait on each other.
            sides = {str(cur["batch_id"]): "moving this run away from it"} if cur["batch_id"] else {}
            if patch["batch_id"] is not None:
                sides[str(patch["batch_id"])] = "linking this run to it"
            for bid in sorted(sides):
                await _batch_unfrozen_or_409(c, bid, sides[bid])
        if patch.get("room_id") is not None:
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
    Specification Strain". `strain` is that: the three labelled sources
    (see the module header), rolled up one measurement per lot. `product` is
    the subset of CoQs that named this mother's product code. `traced` is the
    subset whose lot descends from a batch this mother was actually cut into —
    a smaller, stronger claim, and often empty, because it needs the clone run
    to name its batch and the harvest to have recorded the lot. None is
    inflated by another."""
    uuid_or_404(mother_id, "Mother plant not found")
    async with rls(user) as c:
        m = await c.fetchrow(
            "SELECT m.id, m.code, m.product_id, m.cultivar_id, pr.product_code,"
            " pr.window_min, pr.window_max"
            " FROM mother_plants m JOIN qc_products pr ON pr.id=m.product_id WHERE m.id=$1",
            mother_id)
        if m is None:
            raise HTTPException(404, "Mother plant not found")
        history = await _strain_history(c, m["cultivar_id"], m["product_code"])
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
            " SELECT q.id, q.coq_number, q.batch_id AS lot_code, q.compiled_at AS on_at,"
            f" ({_TOTAL_LINE}) AS total_thc FROM qc_coq q"
            " WHERE q.status='APPROVED' AND q.batch_id IN (SELECT code FROM lots)"
            " ORDER BY q.compiled_at", mother_id)

    return {"mother_id": str(m["id"]), "code": m["code"],
            "product_code": m["product_code"],
            "window": [_fl(m["window_min"]), _fl(m["window_max"])],
            "strain": history["strain"], "sources": history["sources"],
            "product": history["product"],
            "traced": _stats(_hist_rows(traced_rows, "coq_number", "coq_traced"))}
