"""The ImB Product Specifications — the facility's official potency catalogue.

Owner, 2026-09-05: the two ImB Specification documents are official "regarding
the strains and potency ranges and grades and codes", and "the nominal values
for every potency grade range per strain needs to be the same as in the 2 pdf
documents". Those documents are per PRODUCT: one page is one strain at one
nominal Total Δ9-THC, coded <ABBR>_THC<nominal>:CBD1, with an acceptance window
of nominal ± 10 % relative — GP_THC26:CBD1 nominal 26.00 %, window
23.40 – 28.59 %, document QCSP 001 v.03.

WHY THIS IS A NEW TABLE AND NOT A LADDER. potency.py models a per-cultivar
LADDER: tiers I…IV tiling [floor, 30 %], one APPROVED ladder per cultivar,
never overlapping. The official scheme breaks all three — a strain sells as
several products at once, their windows overlap (GP26 23.40–28.59 and GP24
21.60–26.39), and CJ_THC28's window reaches 30.79. So the catalogue is its own
table, and the ladders stay exactly as they are, read-only, so that CoQs issued
before the catalogue keep printing the grade they were issued with. Approving a
cultivar's first product supersedes that cultivar's APPROVED ladder — from then
on the strain is graded from the official page.

Access model, the same shape the ladders use:
  read      — every role above base USER (ELEVATED_ROLES);
  author    — QC writers (_WRITERS: ADMIN, executives, QC_MGR, QP);
  approve / supersede / import — head of QC (_HOQC), and the approver must not
              be the author (segregation of duties, as PP-QC-SPEC-001 requires).

WHAT "TESTED SO FAR" MEANS. The owner asked to see the potency actually
measured for a specification strain. Three sources, each labelled rather than
blended, because they are different strengths of evidence:
  product-level   — APPROVED CoQs that name this product;
  cultivar-level  — APPROVED CoQs that name only the cultivar (issued before
                    the catalogue, or compiled without choosing a product);
  certificate-level — Total Δ9-THC results on issued certificates of this
                    cultivar's batches, reached by the batch-code head. This is
                    the weakest link (a text join) and says so.
Nothing is invented: a lot with no measured total contributes nothing.
"""
import json
from pathlib import Path

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.plantids import PRODUCT_CODE_RE, acronym_of, window_for
from app.roles import ELEVATED_ROLES
from app.worktime import SITE_TODAY_SQL

from .common import _HOQC, _WRITERS, _uuid_or_404, _uuid_or_422, router
from .potency import _EPS
from .potency_import import resolve_or_create_cultivar

_CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "imb_products.json"
_STATUSES = ("DRAFT", "APPROVED", "SUPERSEDED")


class ProductIn(BaseModel):
    cultivar_id: str
    product_code: str = Field(max_length=64)
    grade: float = Field(gt=0, le=100)
    nominal_pct: float | None = Field(default=None, gt=0, le=100)
    window_min: float | None = Field(default=None, ge=0, le=100)
    window_max: float | None = Field(default=None, gt=0, le=100)
    doc_code: str = Field(default="QCSP 001", max_length=60)
    doc_version: str = Field(default="v.03", max_length=60)
    source: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class ProductPatch(BaseModel):
    grade: float | None = Field(default=None, gt=0, le=100)
    nominal_pct: float | None = Field(default=None, gt=0, le=100)
    window_min: float | None = Field(default=None, ge=0, le=100)
    window_max: float | None = Field(default=None, gt=0, le=100)
    source: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class ProductImportIn(BaseModel):
    dry_run: bool = False


def _f(v):
    return float(v) if v is not None else None


def _product_out(r) -> dict:
    out = {
        "id": str(r["id"]), "cultivar_id": str(r["cultivar_id"]),
        "cultivar_code": r["cultivar_code"], "cultivar_name": r["cultivar_name"],
        "product_code": r["product_code"], "grade": _f(r["grade"]),
        "nominal_pct": _f(r["nominal_pct"]),
        "window_min": _f(r["window_min"]), "window_max": _f(r["window_max"]),
        "doc_code": r["doc_code"], "doc_version": r["doc_version"],
        "source": r["source"], "status": r["status"],
        "effective_date": r["effective_date"].isoformat() if r["effective_date"] else None,
        "approved_by": str(r["approved_by"]) if r["approved_by"] else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }
    if "tested_n" in dict(r):
        out["tested"] = {"n": int(r["tested_n"] or 0), "avg": _f(r["tested_avg"]),
                         "min": _f(r["tested_min"]), "max": _f(r["tested_max"])}
    return out


def conforms(window_min, window_max, value) -> bool | None:
    """Does a measured Total Δ9-THC fall inside the product's printed window?

    Inclusive at both ends, with the same float slack the ladders use: the
    window is authored to two decimals, so a value that should sit exactly on
    a bound must not be excluded by binary round-tripping. None when there is
    no value — an unmeasured lot is never judged."""
    if value is None:
        return None
    return (float(value) >= float(window_min) - _EPS
            and float(value) <= float(window_max) + _EPS)


_PRODUCT_SQL = (
    "SELECT p.*, cv.code AS cultivar_code, cv.name AS cultivar_name"
    " FROM qc_products p JOIN cultivars cv ON cv.id = p.cultivar_id")

# The measured Total Δ9-THC of a CoQ: the computed total_thc line (Ph. Eur.
# 3028), the same read _coq_disposition uses so the two can never disagree.
_TOTAL_LINE = (
    "SELECT l.result_numeric FROM qc_coq_lines l"
    " JOIN qc_spec_parameters sp ON sp.id = l.parameter_id"
    " WHERE l.coq_id = q.id AND sp.computed_kind='total_thc'"
    " AND l.result_numeric IS NOT NULL LIMIT 1")

# Selected alongside _PRODUCT_SQL when a list wants the aggregate — the lateral
# below computes it, but a join alone does not put it in the row.
_TESTED_COLS = ", tv.tested_n, tv.tested_avg, tv.tested_min, tv.tested_max"

_TESTED_AGG = (
    " LEFT JOIN LATERAL (SELECT count(*) AS tested_n, avg(t.v) AS tested_avg,"
    "   min(t.v) AS tested_min, max(t.v) AS tested_max"
    "   FROM (SELECT (" + _TOTAL_LINE + ") AS v FROM qc_coq q"
    "         WHERE q.product_id = p.id AND q.status='APPROVED') t"
    "   WHERE t.v IS NOT NULL) tv ON true")


@router.get("/products")
async def list_products(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                        cultivar_id: str | None = Query(None),
                        status: str | None = Query(None)):
    """The catalogue, with what each product has actually tested so far."""
    _uuid_or_422(cultivar_id, "cultivar_id")
    async with rls(user) as c:
        rows = await c.fetch(
            _PRODUCT_SQL.replace(" FROM qc_products p", _TESTED_COLS + " FROM qc_products p", 1)
            + _TESTED_AGG +
            " WHERE ($1::uuid IS NULL OR p.cultivar_id=$1)"
            "   AND ($2::text IS NULL OR p.status=$2)"
            " ORDER BY cv.code, p.grade DESC", cultivar_id, status)
    return [_product_out(r) for r in rows]


async def _potency_history(c, product) -> dict:
    """Everything measured that bears on this product's strain, by strength of
    evidence. Never merged into one number: a cultivar-level CoQ did not name
    this product, and a certificate reached through the batch code is a text
    join, so both are reported beside the product's own figures, not inside
    them."""
    stated = await c.fetch(
        "SELECT q.id, q.coq_number, q.batch_id, q.reviewed_at, q.compiled_at,"
        f" ({_TOTAL_LINE}) AS total_thc FROM qc_coq q"
        " WHERE q.product_id=$1 AND q.status='APPROVED' ORDER BY q.compiled_at", product["id"])
    cultivar_level = await c.fetch(
        "SELECT q.id, q.coq_number, q.batch_id, q.compiled_at,"
        f" ({_TOTAL_LINE}) AS total_thc FROM qc_coq q"
        " WHERE q.product_id IS NULL AND q.cultivar_id=$1 AND q.status='APPROVED'"
        " ORDER BY q.compiled_at", product["cultivar_id"])
    # Certificates of this cultivar's own batches. plant_batches.code is the CU
    # batch (GP072501); a certificate names its batch as free text, so match the
    # certificate's cultivation_batch or its batch_id against those codes.
    certs = await c.fetch(
        "SELECT ct.id, ct.coa_number, ct.batch_id, ct.cultivation_batch, ct.report_date,"
        " r.result_numeric AS total_thc"
        " FROM qc_certificates ct"
        " JOIN qc_results r ON r.coa_id = ct.id"
        " JOIN qc_spec_parameters sp ON sp.id = r.parameter_id"
        " WHERE sp.computed_kind='total_thc' AND r.result_numeric IS NOT NULL"
        "   AND ct.status = ANY(ARRAY['APPROVED','RELEASED'])"
        "   AND (ct.batch_id IN (SELECT code FROM plant_batches WHERE cultivar_id=$1 AND code IS NOT NULL)"
        "     OR ct.cultivation_batch IN (SELECT code FROM plant_batches WHERE cultivar_id=$1 AND code IS NOT NULL))"
        " ORDER BY ct.report_date NULLS LAST", product["cultivar_id"])

    def _stats(values):
        vals = [float(v) for v in values if v is not None]
        return {"n": len(vals), "avg": round(sum(vals) / len(vals), 2) if vals else None,
                "min": min(vals) if vals else None, "max": max(vals) if vals else None}

    def _rows(rs, number_key, date_key):
        return [{"id": str(r["id"]), "number": r[number_key], "lot_code": r["batch_id"],
                 "total_thc": _f(r["total_thc"]),
                 "on": r[date_key].isoformat() if r[date_key] else None,
                 "conforms": conforms(product["window_min"], product["window_max"], r["total_thc"])}
                for r in rs if r["total_thc"] is not None]

    return {
        "tested": {**_stats([r["total_thc"] for r in stated]),
                   "values": _rows(stated, "coq_number", "compiled_at")},
        "cultivar_level": {**_stats([r["total_thc"] for r in cultivar_level]),
                           "values": _rows(cultivar_level, "coq_number", "compiled_at")},
        "certificate_level": {**_stats([r["total_thc"] for r in certs]),
                              "values": _rows(certs, "coa_number", "report_date")},
    }


@router.get("/products/conformance")
async def product_conformance(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                              cultivar_id: str = Query(...),
                              total_d9_thc: float = Query(..., ge=0, le=100),
                              product_id: str | None = Query(None)):
    """Which of a strain's products a measured Total Δ9-THC satisfies.

    The ladder answered "which tier is this?" — exactly one, by construction.
    The official catalogue's windows OVERLAP, so the honest answer is a list;
    which product a lot is actually sold as is a packaging decision, not
    something a measurement can settle. `nearest` names the highest-nominal
    product the value satisfies, for a reader who wants one name."""
    _uuid_or_422(cultivar_id, "cultivar_id")
    _uuid_or_422(product_id, "product_id")
    async with rls(user) as c:
        rows = await c.fetch(
            _PRODUCT_SQL + " WHERE p.cultivar_id=$1 AND p.status='APPROVED'"
            " ORDER BY p.grade DESC", cultivar_id)
        chosen = None
        if product_id:
            chosen = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
            if chosen is None:
                raise HTTPException(422, "Unknown product")
    out = []
    for r in rows:
        out.append({"id": str(r["id"]), "product_code": r["product_code"],
                    "grade": _f(r["grade"]), "nominal_pct": _f(r["nominal_pct"]),
                    "window_min": _f(r["window_min"]), "window_max": _f(r["window_max"]),
                    "conforms": conforms(r["window_min"], r["window_max"], total_d9_thc)})
    matching = [p["product_code"] for p in out if p["conforms"]]
    return {
        "cultivar_id": cultivar_id, "total_d9_thc": total_d9_thc,
        "products": out, "matching": matching, "nearest": matching[0] if matching else None,
        "product": None if chosen is None else {
            "product_id": str(chosen["id"]), "product_code": chosen["product_code"],
            "window_min": _f(chosen["window_min"]), "window_max": _f(chosen["window_max"]),
            "conforms": conforms(chosen["window_min"], chosen["window_max"], total_d9_thc)},
    }


@router.get("/products/{product_id}")
async def get_product(product_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(product_id, "Product")
    async with rls(user) as c:
        row = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
        if row is None:
            raise HTTPException(404, "Product not found")
        history = await _potency_history(c, row)
    return {"product": _product_out(row), **history}


@router.get("/products/{product_id}/potency-history")
async def product_potency_history(product_id: str,
                                  user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The same measured history the product detail carries — its own endpoint
    because the mother bank asks for it per specification strain."""
    _uuid_or_404(product_id, "Product")
    async with rls(user) as c:
        row = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
        if row is None:
            raise HTTPException(404, "Product not found")
        history = await _potency_history(c, row)
    return {"product": _product_out(row), **history}


def _resolve_window(body) -> tuple[float, float, float]:
    """nominal and window default to the printed rule (± 10 % relative); an
    explicitly supplied pair is kept as given, because the page is the
    specification and a page that prints something else must be recordable."""
    nominal = body.nominal_pct if body.nominal_pct is not None else float(body.grade)
    wmin, wmax = window_for(nominal)
    if body.window_min is not None:
        wmin = body.window_min
    if body.window_max is not None:
        wmax = body.window_max
    if wmax <= wmin:
        raise HTTPException(422, "window_max must be greater than window_min")
    if not (wmin - _EPS <= nominal <= wmax + _EPS):
        raise HTTPException(422, "nominal must lie inside the window")
    return nominal, wmin, wmax


@router.post("/products", status_code=201)
async def create_product(body: ProductIn, user: dict = Depends(require_role(*_WRITERS))):
    """Author one product page. DRAFT until a second person approves it."""
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    if not PRODUCT_CODE_RE.match(body.product_code):
        raise HTTPException(422, "product_code must read like GP_THC26:CBD1")
    nominal, wmin, wmax = _resolve_window(body)
    async with rls(user) as c:
        cv = await c.fetchrow(
            "SELECT id, code, name FROM cultivars WHERE id=$1 AND is_active", body.cultivar_id)
        if cv is None:
            raise HTTPException(422, "Unknown or inactive cultivar")
        # The mother-plant ID is built from the product code's head (GP26), so a
        # product filed under the wrong strain would print a wrong plant id
        # forever. Refuse rather than guess.
        acr = acronym_of(body.product_code)
        if acr != cv["code"]:
            raise HTTPException(
                422, f"{body.product_code} is a {acr} product — it does not belong to {cv['code']}")
        dup = await c.fetchval(
            "SELECT 1 FROM qc_products WHERE org_id=$1 AND product_code=$2 AND doc_version=$3",
            user["org_id"], body.product_code, body.doc_version)
        if dup:
            raise HTTPException(409, f"{body.product_code} {body.doc_version} already exists")
        row = await c.fetchrow(
            "INSERT INTO qc_products(org_id, cultivar_id, product_code, grade, nominal_pct,"
            " window_min, window_max, doc_code, doc_version, source, notes, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
            user["org_id"], cv["id"], body.product_code, body.grade, nominal, wmin, wmax,
            body.doc_code, body.doc_version, body.source, body.notes, user["id"])
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", row["id"])
        await safe_emit(c, user, verb="product_created", object_type="qc_product",
                        object_id=row["id"], recipients=[],
                        params={"product_code": body.product_code, "cultivar": cv["code"]})
    return _product_out(full)


@router.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductPatch,
                         user: dict = Depends(require_role(*_WRITERS))):
    """DRAFT only — an approved page is superseded by a new version, never
    edited in place (the ladders' rule, for the same reason)."""
    _uuid_or_404(product_id, "Product")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT * FROM qc_products WHERE id=$1", product_id)
        if cur is None:
            raise HTTPException(404, "Product not found")
        if cur["status"] != "DRAFT":
            raise HTTPException(409, f"a {cur['status']} product cannot be edited —"
                                     " author a new version instead")
        fields, args = [], []
        for col, val in patch.items():
            if val is None and col not in ("source", "notes"):
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(product_id)
        await c.execute(
            # Column names come from ProductPatch's own fields; values are bound.
            f"UPDATE qc_products SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
        row = await c.fetchrow("SELECT * FROM qc_products WHERE id=$1", product_id)
        if row["window_max"] <= row["window_min"] or not (
                row["window_min"] <= row["nominal_pct"] <= row["window_max"]):
            raise HTTPException(422, "nominal must lie inside the window")
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
    return _product_out(full)


@router.post("/products/{product_id}/approve")
async def approve_product(product_id: str, user: dict = Depends(require_role(*_HOQC))):
    """DRAFT → APPROVED. Supersedes the same code's current APPROVED row, and —
    the moment a cultivar's first product is approved — that cultivar's APPROVED
    potency ladder: the official page takes over grading for the strain, and two
    live schemes would be two answers to one question."""
    _uuid_or_404(product_id, "Product")
    async with rls(user) as c:
        cur = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
        if cur is None:
            raise HTTPException(404, "Product not found")
        if cur["status"] != "DRAFT":
            raise HTTPException(409, f"Only a DRAFT product can be approved (is {cur['status']})")
        if str(user["id"]) in (str(cur["created_by"]), str(cur["updated_by"])):
            raise HTTPException(
                403, "The person approving a product specification must be different from the"
                     " person who authored it (segregation of duties, PP-QC-SPEC-001)")
        # Supersede the sitting APPROVED row FIRST — qc_products_one_approved_idx
        # is checked at statement end, so the order matters.
        await c.execute(
            "UPDATE qc_products SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
            " WHERE product_code=$2 AND status='APPROVED' AND id<>$3",
            user["id"], cur["product_code"], product_id)
        ladders = await c.fetchval(
            "WITH s AS (UPDATE qc_potency_specs SET status='SUPERSEDED', updated_by=$1,"
            " updated_at=now() WHERE cultivar_id=$2 AND status='APPROVED' RETURNING 1)"
            " SELECT count(*) FROM s", user["id"], cur["cultivar_id"])
        await c.execute(
            f"UPDATE qc_products SET status='APPROVED', approved_by=$1,"  # nosec B608
            f" effective_date=COALESCE(effective_date, {SITE_TODAY_SQL}),"
            " updated_by=$1, updated_at=now() WHERE id=$2", user["id"], product_id)
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
        await safe_emit(c, user, verb="product_approved", object_type="qc_product",
                        object_id=product_id, recipients=[],
                        params={"product_code": cur["product_code"],
                                "cultivar": cur["cultivar_code"],
                                "ladders_superseded": int(ladders or 0)})
    return _product_out(full)


@router.post("/products/{product_id}/supersede")
async def supersede_product(product_id: str, user: dict = Depends(require_role(*_HOQC))):
    _uuid_or_404(product_id, "Product")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_products WHERE id=$1", product_id)
        if cur is None:
            raise HTTPException(404, "Product not found")
        if cur["status"] != "APPROVED":
            raise HTTPException(409, f"Only an APPROVED product can be superseded (is {cur['status']})")
        await c.execute(
            "UPDATE qc_products SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
            " WHERE id=$2", user["id"], product_id)
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
    return _product_out(full)


def _load_catalogue() -> dict:
    try:
        with open(_CATALOGUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(503, "The packaged product catalogue is missing from this build")


@router.post("/products/import")
async def import_products(body: ProductImportIn,
                          user: dict = Depends(require_role(*_HOQC))):
    """Load the packaged ImB catalogue (app/data/imb_products.json — every page
    of the owner's two documents) as DRAFT products, auto-creating cultivars
    from the product code's acronym. Idempotent on (code, doc_version);
    approval stays a second person's act."""
    cat = _load_catalogue()
    version = cat.get("doc_version", "v.03")
    doc_code = cat.get("doc_code", "QCSP 001")
    created, skipped, conflicts, cultivars_created = [], [], [], []
    seen_cultivars: set[str] = set()
    last_id = None
    async with rls(user) as c:
        for row in cat.get("products", []):
            strain, acr, code = row["strain"], row["acronym"], row["product_code"]
            cv, made, conflict = await resolve_or_create_cultivar(
                c, user, acr, strain, body.dry_run)
            if conflict:
                conflicts.append(conflict)
                continue
            if made and made["code"] not in seen_cultivars:
                # A strain has several products; a dry run resolves nothing, so
                # without this the same new cultivar is reported once per page.
                seen_cultivars.add(made["code"])
                cultivars_created.append(made)
            if cv is not None:
                exists = await c.fetchval(
                    "SELECT 1 FROM qc_products WHERE org_id=$1 AND product_code=$2"
                    " AND doc_version=$3", user["org_id"], code, version)
                if exists:
                    skipped.append({"product_code": code, "reason": "version exists"})
                    continue
            entry = {"product_code": code, "strain": strain,
                     "grade": row["grade"], "window": [row["window_min"], row["window_max"]],
                     "pages": row.get("pages", [])}
            if body.dry_run or cv is None:
                created.append(entry)
                continue
            src = f"{', '.join(row.get('pages', []))} ({doc_code} {version})"
            ins = await c.fetchrow(
                "INSERT INTO qc_products(org_id, cultivar_id, product_code, grade, nominal_pct,"
                " window_min, window_max, doc_code, doc_version, source, notes, created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
                user["org_id"], cv["id"], code, row["grade"], row["nominal_pct"],
                row["window_min"], row["window_max"], doc_code, version, src,
                ("Imported from the owner's ImB Product Specifications; the page prints the"
                 f" strain as {row['strain_printed']}." if row.get("strain_printed")
                 and row["strain_printed"] != strain else
                 "Imported from the owner's ImB Product Specifications."),
                user["id"])
            last_id = ins["id"]
            created.append(entry)
        if not body.dry_run and last_id is not None:
            await safe_emit(c, user, verb="product_catalogue_imported", object_type="qc_product",
                            object_id=last_id, recipients=[],
                            params={"doc_code": doc_code, "doc_version": version,
                                    "created": len(created), "skipped": len(skipped),
                                    "conflicts": len(conflicts)})
    return {"dry_run": body.dry_run, "doc_code": doc_code, "doc_version": version,
            "created": created, "skipped": skipped, "conflicts": conflicts,
            "cultivars_created": cultivars_created}
