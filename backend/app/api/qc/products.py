"""The product catalogue — the facility's official potency specification.

Owner, 2026-09-05: the two ImB Specification documents are official "regarding
the strains and potency ranges and grades and codes", and "the nominal values
for every potency grade range per strain needs to be the same as in the 2 pdf
documents". Those documents are per PRODUCT: one page is one strain at one
nominal Total Δ9-THC, coded <ABBR>_THC<nominal>:CBD1, with an acceptance window
printed on the page — GP_THC26:CBD1 nominal 26.00 %, window 23.40 – 28.59 %,
document QCSP 001 v.03.

Owner, 2026-09-06: a tolerance is "a maximum of ±10 % of the nominal", a strain
carries 1–6 grades whose ranges do not overlap, and a Total THC outside the
chosen grade "falls to the next spec grade above or below", visibly, with a
formal OOS on the batch disposition and a deviation to Cultivation and
Production (the CoQ side of that rule lives in coq_aggregation.py).

Owner, 2026-09-18: "±10 % flat is not gonna work so the fitted approach is
applicable everywhere". Consequences implemented here:
  - a window is always EXPLICIT — POST /qc/products, /qc/products/ladder and
    the two importers all store the window they were given; nothing derives a
    window from the nominal any more (plantids.window_for is reference-only,
    kept to describe what the ImB pages print);
  - the fitted specifications are loaded through POST /qc/products/import-fitted
    from the Potency Spec Service's own export (GET /api/specs?status=finished),
    with the service's provenance written into `source` / `notes`;
  - ±10 % of the nominal remains the CEILING on any window (_TOLERANCE_CEILING),
    fitted or not.

WHY THIS IS A NEW TABLE AND NOT A LADDER. potency.py models a per-cultivar
LADDER: tiers I…IV tiling [floor, 30 %], one APPROVED ladder per cultivar,
never overlapping. The official scheme breaks all three — a strain sells as
several products at once, the ImB windows overlap (GP26 23.40–28.59 and GP24
21.60–26.39), and CJ_THC28's window reaches 30.79. So the catalogue is its own
table, and the ladders stay exactly as they are, read-only, so that CoQs issued
before the catalogue keep printing the grade they were issued with. Approving a
cultivar's first product supersedes that cultivar's APPROVED ladder — from then
on the strain is graded from the official page — and approving a product of a
NEWER document version supersedes the cultivar's products of the old version,
so one specification version is live per strain at a time (two live schemes
would be two answers to one question) — and only in that direction: a product
of an OLDER version than the strain's live one is refused approval, and the
packaged v.03 pages are not imported for a strain that holds a later version
(review 2026-09-27 QR-02). A single product may not overlap its siblings of the
same version (QR-09), the v.03 pages excepted (they overlap as issued).

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
import re
from pathlib import Path

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.plantids import PRODUCT_CODE_RE, grade_str
from app.plantids import product_code as compose_product_code
from app.roles import ELEVATED_ROLES
from app.worktime import SITE_TODAY_SQL

from .common import (_HOQC, _WRITERS, _uuid_or_404, _uuid_or_422, check_derived_total_units,
                     derived_total, router)
from .potency import _EPS
from .potency_import import resolve_or_create_cultivar

_CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "imb_products.json"
_STATUSES = ("DRAFT", "APPROVED", "SUPERSEDED")

# Owner, 2026-09-06: a product's tolerance "can be a maximum of ±10 % of the
# nominal value". Every window this module stores is checked against it.
_TOLERANCE_CEILING = 0.10

# The words an OOS record must carry in its test name to count as the formal
# investigation of an out-of-window Total Δ9-THC (coq_aggregation's approve
# gate). Case- and whitespace-folded; the Macedonian form is accepted too.
_TOTAL_THC_WORDS = (("total", "thc"), ("вкупен", "thc"), ("вкупен", "тхц"))


class ProductIn(BaseModel):
    cultivar_id: str
    product_code: str = Field(max_length=64)
    grade: float = Field(gt=0, le=100)
    nominal_pct: float | None = Field(default=None, gt=0, le=100)
    # Explicit since 2026-09-18: the window is what the issued page prints,
    # never a rule applied to the nominal.
    window_min: float = Field(ge=0, le=100)
    window_max: float = Field(gt=0, le=100)
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


class LadderGradeIn(BaseModel):
    """One grade of a strain's ladder, with the window it was fitted to."""
    grade: float = Field(gt=0, le=100)
    nominal_pct: float | None = Field(default=None, gt=0, le=100)
    window_min: float = Field(ge=0, le=100)
    window_max: float = Field(gt=0, le=100)
    cbd: float = Field(default=1, gt=0, le=100)
    source: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class LadderIn(BaseModel):
    """A whole strain's set of grades in one transaction (INS-03): a ladder
    written one product at a time can half-fail and leave a strain with a
    partial specification and no record of intent."""
    cultivar_id: str
    doc_code: str = Field(default="QCSP 001", max_length=60)
    doc_version: str = Field(max_length=60)
    source: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    grades: list[LadderGradeIn] = Field(min_length=1, max_length=8)


class FittedRangeIn(BaseModel):
    """One range of a Potency Spec Service spec: `N ± t` covers `lo … hi`,
    where the service prints hi = N + t − 0.01 (the specification's own
    convention)."""
    nominal: float = Field(gt=0, le=100)
    tol: float = Field(gt=0, le=100)
    lo: float = Field(ge=0, le=100)
    hi: float = Field(gt=0, le=100)


class FittedSpecIn(BaseModel):
    """One spec exactly as GET /api/specs returns it. Server-managed fields
    (`created_at`, `updated_at`, `finished_at`) and any extra keys the SPA
    stashes in the object are accepted and ignored except where named."""
    id: str = Field(max_length=12)
    name: str = Field(max_length=200)
    status: str = "finished"
    custom: bool = False
    ranges: list[FittedRangeIn] = Field(default_factory=list)
    results_entered: list = Field(default_factory=list)
    results_excluded: list = Field(default_factory=list)
    finished_at: str | None = None
    updated_at: str | None = None


class FittedImportIn(BaseModel):
    """The body is the service's export: `{"specs": [...]}` from
    GET /api/specs?status=finished, plus the document identity the fitted
    specification was issued under — stated by the person importing, never
    invented here."""
    specs: list[FittedSpecIn] = Field(min_length=1)
    doc_code: str = Field(default="QCSP 001", max_length=60)
    doc_version: str = Field(max_length=60)
    dry_run: bool = False
    include_drafts: bool = False


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


def names_total_thc(test_name: str | None) -> bool:
    """Does an OOS record's test name name Total Δ9-THC? Folded the way
    coq_aggregation._norm_test folds ("Total  THC", "Total Δ9-THC",
    "вкупен THC" all count); "Total CBD" and "THCA" do not."""
    t = " ".join((test_name or "").split()).lower()
    return any(all(w in t for w in words) for words in _TOTAL_THC_WORDS)


def nearest_of(products: list[dict], value) -> dict | None:
    """AD-12 — the product a measured Total Δ9-THC belongs to.

    The owner's rule (2026-09-06): an out-of-window value "falls to the next
    spec grade above or below, suitably". So: the product whose window CONTAINS
    the value; when several do (the ImB ±10 % windows overlap), the one whose
    nominal is closest to the value, and on a tie the LOWER nominal — a
    certificate must never over-label potency. When no window contains it, the
    product whose window edge is nearest, above or below, again preferring the
    lower nominal on a tie. None when nothing was measured or nothing exists."""
    if value is None or not products:
        return None
    v = float(value)
    inside = [p for p in products if conforms(p["window_min"], p["window_max"], v)]
    if inside:
        return min(inside, key=lambda p: (abs(v - float(p["nominal_pct"])), float(p["nominal_pct"])))

    def gap(p):
        lo, hi = float(p["window_min"]), float(p["window_max"])
        return (lo - v) if v < lo else (v - hi)

    return min(products, key=lambda p: (gap(p), float(p["nominal_pct"])))


def conformance_of(products: list[dict], value, chosen: dict | None = None) -> dict:
    """The catalogue's answer for one measured value: every product it
    satisfies, the single nearest one (nearest_of), and — when a product was
    chosen — whether the value conforms to it and which product it falls to
    when it does not (`regrade_to`, None when the value fits no product at
    all or already fits the chosen one)."""
    matching = [p for p in products if conforms(p["window_min"], p["window_max"], value)]
    near = nearest_of(products, value)
    out = {"matching": [p["product_code"] for p in matching],
           "nearest": near["product_code"] if near else None}
    if chosen is not None:
        conf = conforms(chosen["window_min"], chosen["window_max"], value)
        out["conforms"] = conf
        fits_elsewhere = (conf is False and near is not None
                          and near["product_code"] != chosen["product_code"]
                          and conforms(near["window_min"], near["window_max"], value))
        out["regrade_to"] = near["product_code"] if fits_elsewhere else None
    return out


def _check_window(nominal: float, wmin: float, wmax: float, label: str = "") -> None:
    """Every stored window passes here: ordered, nominal inside, and neither
    side wider than the owner's ±10 % ceiling. Raises 422."""
    tag = f"{label}: " if label else ""
    if wmax <= wmin:
        raise HTTPException(422, f"{tag}window_max must be greater than window_min")
    if not (wmin - _EPS <= nominal <= wmax + _EPS):
        raise HTTPException(422, f"{tag}nominal must lie inside the window")
    ceiling = round(nominal * _TOLERANCE_CEILING, 4)
    if (nominal - wmin) > ceiling + _EPS or (wmax - nominal) > ceiling + _EPS:
        raise HTTPException(
            422, f"{tag}the window exceeds the owner's ceiling of ±10 % of the nominal"
                 f" (±{ceiling:.2f} around {nominal:g}) — 2026-09-06")


def _tie_code_to_grade(code: str, cultivar_code: str | None, grade: float, nominal: float) -> str:
    """QC-30: the product code, the grade and the nominal are one number seen
    three ways (GP_THC26 → grade 26 → nominal 26.00 → mother id GP26…). Refuse
    a disagreement rather than store it, and return the code in its canonical
    spelling (GP_THC26.0:CBD1 → GP_THC26:CBD1). With `cultivar_code` None the
    strain check is skipped (a pre-database pass); with it, the code must name
    that cultivar."""
    m = PRODUCT_CODE_RE.match(code or "")
    if not m:
        raise HTTPException(422, "product_code must read like GP_THC26:CBD1")
    acr, thc, cbd = m.group(1), float(m.group(2)), float(m.group(3))
    if cultivar_code is not None and acr != cultivar_code:
        raise HTTPException(422, f"{code} is a {acr} product — it does not belong to {cultivar_code}")
    if abs(thc - float(grade)) > _EPS:
        raise HTTPException(
            422, f"grade {grade:g} disagrees with the product code's THC number"
                 f" ({acr}_THC{grade_str(thc)}) — the two are the same number")
    if abs(float(nominal) - float(grade)) > _EPS:
        raise HTTPException(
            422, f"nominal {nominal:g} disagrees with grade {grade:g} — a product's grade IS"
                 " its nominal Total Δ9-THC")
    return compose_product_code(acr, grade, cbd)


def _overlap(a: dict, b: dict) -> bool:
    """Inclusive-bound overlap of two windows (a value on a shared bound would
    belong to both)."""
    return (float(a["window_min"]) <= float(b["window_max"]) + _EPS
            and float(b["window_min"]) <= float(a["window_max"]) + _EPS)


def _validate_grade_set(items: list[dict], label: str) -> None:
    """A strain's grades must be distinct and their windows must not overlap
    (owner 2026-09-06: "ranges not overlapping"). `items` carry grade,
    nominal_pct, window_min, window_max."""
    grades = [float(i["grade"]) for i in items]
    if len(set(grades)) != len(grades):
        raise HTTPException(422, f"{label}: the same grade appears twice")
    ordered = sorted(items, key=lambda i: float(i["nominal_pct"]))
    for lo, hi in zip(ordered, ordered[1:]):
        if _overlap(lo, hi):
            raise HTTPException(
                422, f"{label}: grades {lo['grade']:g} and {hi['grade']:g} overlap"
                     f" ({lo['window_min']:.2f}–{lo['window_max']:.2f} vs"
                     f" {hi['window_min']:.2f}–{hi['window_max']:.2f}) — a strain's grades"
                     " must not overlap (owner, 2026-09-06)")


def _version_key(doc_version: str | None) -> tuple:
    """Order document versions by the numbers they carry: "v.03" < "v.04" <
    "fitted 2026-09-15" ((3,) < (4,) < (2026, 9, 15)). A version with no
    digits sorts first. Two spellings of one number ("v.3", "v.03") are the
    same version for ordering, though the table keeps them distinct."""
    nums = tuple(int(x) for x in re.findall(r"\d+", doc_version or ""))
    return nums


async def _newest_version(c, cultivar_id) -> str | None:
    """The newest document version this cultivar has ever had APPROVED (or
    that has since been SUPERSEDED) — the version rule's reference point
    (review 2026-09-27 QR-02). DRAFTs do not count: nothing was ever live
    under them."""
    rows = await c.fetch(
        "SELECT DISTINCT doc_version FROM qc_products WHERE cultivar_id=$1"
        " AND status IN ('APPROVED','SUPERSEDED')", cultivar_id)
    if not rows:
        return None
    return max((r["doc_version"] for r in rows), key=_version_key)


def _reference_version() -> str:
    """The packaged ImB pages' document version (QCSP 001 v.03) — the issued
    v.03 pages overlap by issue (documented in PRODUCT-CATALOGUE), so a
    single page authored under that version is exempt from the sibling
    non-overlap rule that every later version obeys."""
    try:
        return _load_catalogue().get("doc_version", "v.03")
    except HTTPException:
        return "v.03"


async def _assert_no_sibling_overlap(c, cultivar_id, doc_version: str, item: dict,
                                     label: str, exclude_id=None) -> None:
    """Owner 2026-09-06 "ranges not overlapping" for ONE product at a time
    (review 2026-09-27 QR-09 / INS2-06): the new or edited product is checked
    as a set with the cultivar's DRAFT/APPROVED siblings of the same
    doc_version, exactly as /ladder and import-fitted check a whole set.
    The packaged reference version (v.03) is exempt: those pages overlap as
    issued."""
    if doc_version == _reference_version():
        return
    siblings = await c.fetch(
        "SELECT id, product_code, grade, nominal_pct, window_min, window_max FROM qc_products"
        " WHERE cultivar_id=$1 AND doc_version=$2 AND status<>'SUPERSEDED'"
        " AND ($3::uuid IS NULL OR id<>$3)", cultivar_id, doc_version, exclude_id)
    if not siblings:
        return
    items = [{"grade": float(r["grade"]), "nominal_pct": float(r["nominal_pct"]),
              "window_min": float(r["window_min"]), "window_max": float(r["window_max"])}
             for r in siblings]
    items.append(item)
    _validate_grade_set(items, label)


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
    # Certificates of this cultivar's own batches (review 2026-09-27 QR-11).
    # The Total Δ9-THC of a certificate is DERIVED here from its two
    # component results (Ph. Eur. 3028, the one derived_total every CoQ path
    # uses) — a transcribed total is refused everywhere since QC-10, so a
    # join on stored total rows was structurally empty for every certificate
    # issued from then on. The batch is attributed to the strain by the
    # batch-code HEAD (`^<CV>[0-9]`, the facility convention GP072501) on the
    # certificate's batch_id or cultivation_batch, case-insensitively, or by
    # an exact match against the cultivar's registered batch codes. A text
    # join, and it says so.
    head_re = f"^{product['cultivar_code'].upper()}[0-9]" if str(product["cultivar_code"]).isalnum() else None
    certs = await c.fetch(
        "SELECT ct.id, ct.coa_number, ct.batch_id, ct.cultivation_batch, ct.report_date,"
        " sp.test_name_en, sp.test_name_mk, sp.unit AS p_unit,"
        " ra.result_numeric AS a_val, ra.unit AS a_unit, rb.result_numeric AS b_val, rb.unit AS b_unit"
        " FROM qc_certificates ct"
        " JOIN qc_spec_parameters sp ON sp.spec_id = ct.specification_id"
        "   AND sp.computed_kind='total_thc'"
        " JOIN LATERAL (SELECT result_numeric, unit FROM qc_results WHERE coa_id=ct.id"
        "   AND parameter_id=sp.component_a_id AND result_numeric IS NOT NULL"
        "   ORDER BY result_date DESC NULLS LAST, created_at DESC LIMIT 1) ra ON true"
        " JOIN LATERAL (SELECT result_numeric, unit FROM qc_results WHERE coa_id=ct.id"
        "   AND parameter_id=sp.component_b_id AND result_numeric IS NOT NULL"
        "   ORDER BY result_date DESC NULLS LAST, created_at DESC LIMIT 1) rb ON true"
        " WHERE ct.status = ANY(ARRAY['APPROVED','RELEASED'])"
        "   AND (($2::text IS NOT NULL AND (upper(ct.batch_id) ~ $2::text"
        "                                   OR upper(ct.cultivation_batch) ~ $2::text))"
        "     OR upper(ct.batch_id) IN (SELECT upper(code) FROM plant_batches"
        "                                WHERE cultivar_id=$1 AND code IS NOT NULL)"
        "     OR upper(ct.cultivation_batch) IN (SELECT upper(code) FROM plant_batches"
        "                                         WHERE cultivar_id=$1 AND code IS NOT NULL))"
        " ORDER BY ct.report_date NULLS LAST", product["cultivar_id"], head_re)
    cert_rows = []
    for ct in certs:
        try:
            check_derived_total_units(
                {"unit": ct["p_unit"], "test_name_en": ct["test_name_en"],
                 "test_name_mk": ct["test_name_mk"]},
                {"unit": ct["a_unit"]}, {"unit": ct["b_unit"]})
        except HTTPException:
            continue        # mixed units: no meaningful total to report
        cert_rows.append({**dict(ct), "total_thc": derived_total(ct["a_val"], ct["b_val"])})

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
        "certificate_level": {**_stats([r["total_thc"] for r in cert_rows]),
                              "values": _rows(cert_rows, "coa_number", "report_date")},
    }


@router.get("/products/conformance")
async def product_conformance(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                              cultivar_id: str = Query(...),
                              total_d9_thc: float = Query(..., ge=0, le=100),
                              product_id: str | None = Query(None)):
    """Which of a strain's APPROVED products a measured Total Δ9-THC satisfies.

    The ladder answered "which tier is this?" — exactly one, by construction.
    The ImB catalogue's windows OVERLAP, so `matching` is a list; `nearest` is
    the one product the value belongs to under the owner's next-grade rule
    (nearest_of / AD-12), and with `product_id` given, `product.conforms`
    judges that product and `product.regrade_to` names where the value falls
    when it does not conform."""
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
    products = [dict(r) for r in rows]
    out = []
    for r in products:
        out.append({"id": str(r["id"]), "product_code": r["product_code"],
                    "grade": _f(r["grade"]), "nominal_pct": _f(r["nominal_pct"]),
                    "window_min": _f(r["window_min"]), "window_max": _f(r["window_max"]),
                    "conforms": conforms(r["window_min"], r["window_max"], total_d9_thc)})
    verdict = conformance_of(products, total_d9_thc, dict(chosen) if chosen is not None else None)
    return {
        "cultivar_id": cultivar_id, "total_d9_thc": total_d9_thc,
        "products": out, "matching": verdict["matching"], "nearest": verdict["nearest"],
        "product": None if chosen is None else {
            "product_id": str(chosen["id"]), "product_code": chosen["product_code"],
            "window_min": _f(chosen["window_min"]), "window_max": _f(chosen["window_max"]),
            "conforms": verdict["conforms"], "regrade_to": verdict["regrade_to"]},
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


async def _active_cultivar(c, cultivar_id: str):
    cv = await c.fetchrow(
        "SELECT id, code, name FROM cultivars WHERE id=$1 AND is_active", cultivar_id)
    if cv is None:
        raise HTTPException(422, "Unknown or inactive cultivar")
    return cv


async def _insert_product(c, user, cv_id, code, grade, nominal, wmin, wmax, doc_code,
                          doc_version, source, notes):
    return await c.fetchval(
        "INSERT INTO qc_products(org_id, cultivar_id, product_code, grade, nominal_pct,"
        " window_min, window_max, doc_code, doc_version, source, notes, created_by, updated_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
        user["org_id"], cv_id, code, grade, nominal, wmin, wmax, doc_code, doc_version,
        source, notes, user["id"])


@router.post("/products", status_code=201)
async def create_product(body: ProductIn, user: dict = Depends(require_role(*_WRITERS))):
    """Author one product page, with the window the page prints. DRAFT until a
    second person approves it."""
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    nominal = body.nominal_pct if body.nominal_pct is not None else float(body.grade)
    # Code ↔ grade ↔ nominal first (one number, three ways), then the window
    # around that number, then — with the cultivar in hand — the strain.
    _tie_code_to_grade(body.product_code, None, body.grade, nominal)
    _check_window(nominal, body.window_min, body.window_max)
    async with rls(user) as c:
        cv = await _active_cultivar(c, body.cultivar_id)
        # The mother-plant ID is built from the product code's head (GP26), so a
        # product filed under the wrong strain, or a code that disagrees with
        # its grade, would print a wrong plant id forever. Refuse rather than guess.
        code = _tie_code_to_grade(body.product_code, cv["code"], body.grade, nominal)
        dup = await c.fetchval(
            "SELECT 1 FROM qc_products WHERE org_id=$1 AND product_code=$2 AND doc_version=$3",
            user["org_id"], code, body.doc_version)
        if dup:
            raise HTTPException(409, f"{code} {body.doc_version} already exists")
        await _assert_no_sibling_overlap(
            c, cv["id"], body.doc_version,
            {"grade": float(body.grade), "nominal_pct": nominal,
             "window_min": body.window_min, "window_max": body.window_max},
            f"{cv['code']} {body.doc_version}")
        pid = await _insert_product(c, user, cv["id"], code, body.grade, nominal,
                                    body.window_min, body.window_max, body.doc_code,
                                    body.doc_version, body.source, body.notes)
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", pid)
        await safe_emit(c, user, verb="product_created", object_type="qc_product",
                        object_id=pid, recipients=[],
                        params={"product_code": code, "cultivar": cv["code"]})
    return _product_out(full)


@router.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductPatch,
                         user: dict = Depends(require_role(*_WRITERS))):
    """DRAFT only — an approved page is superseded by a new version, never
    edited in place (the ladders' rule, for the same reason). The merged row
    is validated BEFORE the UPDATE (QC-30): an inverted window used to reach
    the table's CHECK constraint first and surface as a 500."""
    _uuid_or_404(product_id, "Product")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
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
        merged = {k: float(cur[k]) for k in ("grade", "nominal_pct", "window_min", "window_max")}
        for k in merged:
            if patch.get(k) is not None:
                merged[k] = float(patch[k])
        # Code, grade and nominal stay one number; the code itself is not
        # patchable, so a grade that no longer matches it is refused here.
        _tie_code_to_grade(cur["product_code"], cur["cultivar_code"],
                           merged["grade"], merged["nominal_pct"])
        _check_window(merged["nominal_pct"], merged["window_min"], merged["window_max"])
        await _assert_no_sibling_overlap(c, cur["cultivar_id"], cur["doc_version"], merged,
                                         f"{cur['cultivar_code']} {cur['doc_version']}",
                                         exclude_id=cur["id"])
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(product_id)
        await c.execute(
            # Column names come from ProductPatch's own fields; values are bound.
            f"UPDATE qc_products SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
        full = await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", product_id)
    return _product_out(full)


@router.post("/products/{product_id}/approve")
async def approve_product(product_id: str, user: dict = Depends(require_role(*_HOQC))):
    """DRAFT → APPROVED. One specification is live per strain: approving a
    product supersedes the same code's current APPROVED row, the cultivar's
    APPROVED products of an OLDER document version (a new fitted set retires
    the ImB pages it replaces), and — the moment a cultivar's first product is
    approved — that cultivar's APPROVED potency ladder. Two live schemes would
    be two answers to one question.

    The supersession runs one way only (review 2026-09-27 QR-02, owner
    2026-09-18 "±10 % flat is not gonna work"): a product whose doc_version
    is OLDER than the newest version the strain has had APPROVED (or
    SUPERSEDED since) is refused with 409 naming the live version — approving
    a retired v.03 ImB page must never retire a strain's fitted set. The same
    version joins it; a newer version supersedes it."""
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
        newest = await _newest_version(c, cur["cultivar_id"])
        if newest is not None and _version_key(cur["doc_version"]) < _version_key(newest):
            raise HTTPException(
                409, f"{cur['product_code']} {cur['doc_version']} is an older document version"
                     f" than {cur['cultivar_code']}'s live specification ({newest}) — approving"
                     " it would retire the newer set; author the grade under the live version"
                     " instead (owner 2026-09-18: the fitted specification applies everywhere)")
        # Supersede the sitting APPROVED rows FIRST — qc_products_one_approved_idx
        # is checked at statement end, so the order matters.
        await c.execute(
            "UPDATE qc_products SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
            " WHERE product_code=$2 AND status='APPROVED' AND id<>$3",
            user["id"], cur["product_code"], product_id)
        versions = await c.fetchval(
            "WITH s AS (UPDATE qc_products SET status='SUPERSEDED', updated_by=$1,"
            " updated_at=now() WHERE cultivar_id=$2 AND status='APPROVED'"
            " AND doc_version<>$3 AND id<>$4 RETURNING 1) SELECT count(*) FROM s",
            user["id"], cur["cultivar_id"], cur["doc_version"], product_id)
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
                                "doc_version": cur["doc_version"],
                                "products_superseded": int(versions or 0),
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


@router.post("/products/ladder", status_code=201)
async def create_ladder(body: LadderIn, user: dict = Depends(require_role(*_WRITERS))):
    """A strain's whole set of grades in ONE transaction, each with the window
    it was fitted to (INS-03). Validated as a set before anything is written —
    distinct grades, no overlap, every window inside the ±10 % ceiling, no
    (code, version) already on file — so a refused ladder leaves nothing
    behind. Everything lands as DRAFT; approval stays a second person's act.
    Provenance goes into `source` / `notes` (the ladder's, then each grade's).
    Overlaps with the cultivar's products of OTHER versions are reported, not
    refused: they are what approval of the new version supersedes."""
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    items = []
    for g in body.grades:
        nominal = g.nominal_pct if g.nominal_pct is not None else float(g.grade)
        _check_window(nominal, g.window_min, g.window_max, f"grade {g.grade:g}")
        items.append({"grade": float(g.grade), "nominal_pct": nominal,
                      "window_min": g.window_min, "window_max": g.window_max, "cbd": g.cbd,
                      "source": g.source or body.source, "notes": g.notes or body.notes})
    async with rls(user) as c:
        cv = await _active_cultivar(c, body.cultivar_id)
        for it in items:
            it["product_code"] = _tie_code_to_grade(
                compose_product_code(cv["code"], it["grade"], it["cbd"]), cv["code"],
                it["grade"], it["nominal_pct"])
        _validate_grade_set(items, cv["code"])
        codes = [it["product_code"] for it in items]
        taken = await c.fetch(
            "SELECT product_code FROM qc_products WHERE org_id=$1 AND doc_version=$2"
            " AND product_code = ANY($3::text[])", user["org_id"], body.doc_version, codes)
        if taken:
            raise HTTPException(
                409, f"{', '.join(r['product_code'] for r in taken)} {body.doc_version}"
                     " already exist — nothing was written")
        # Singles already authored under this version are part of the set
        # (QR-09): the whole version must not overlap, not just this body.
        same_version = await c.fetch(
            "SELECT product_code, grade, nominal_pct, window_min, window_max FROM qc_products"
            " WHERE cultivar_id=$1 AND doc_version=$2 AND status<>'SUPERSEDED'",
            cv["id"], body.doc_version)
        if same_version and body.doc_version != _reference_version():
            _validate_grade_set(
                items + [{"grade": float(r["grade"]), "nominal_pct": float(r["nominal_pct"]),
                          "window_min": float(r["window_min"]), "window_max": float(r["window_max"])}
                         for r in same_version], f"{cv['code']} {body.doc_version}")
        siblings = await c.fetch(
            "SELECT product_code, doc_version, status, window_min, window_max FROM qc_products"
            " WHERE cultivar_id=$1 AND status<>'SUPERSEDED' AND doc_version<>$2",
            cv["id"], body.doc_version)
        overlaps = [{"product_code": s["product_code"], "doc_version": s["doc_version"],
                     "status": s["status"], "with": it["product_code"]}
                    for s in siblings for it in items if _overlap(dict(s), it)]
        created = []
        for it in items:
            pid = await _insert_product(c, user, cv["id"], it["product_code"], it["grade"],
                                        it["nominal_pct"], it["window_min"], it["window_max"],
                                        body.doc_code, body.doc_version, it["source"], it["notes"])
            created.append(await c.fetchrow(_PRODUCT_SQL + " WHERE p.id=$1", pid))
        await safe_emit(c, user, verb="product_ladder_created", object_type="qc_product",
                        object_id=created[-1]["id"], recipients=[],
                        params={"cultivar": cv["code"], "doc_version": body.doc_version,
                                "grades": [it["grade"] for it in items]})
    return {"cultivar_id": str(cv["id"]), "cultivar_code": cv["code"],
            "doc_code": body.doc_code, "doc_version": body.doc_version,
            "products": [_product_out(r) for r in created], "overlaps_existing": overlaps}


def _load_catalogue() -> dict:
    try:
        with open(_CATALOGUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(503, "The packaged product catalogue is missing from this build")


def _spellings(row: dict) -> tuple[str, ...]:
    """Every spelling the packaged catalogue knows for a row's strain: the
    canonical name, the one the page prints, the retired ones (renamed on
    import) and the disputed ones (INS2-03: the per-strain folder's "Sleepy
    Joy" against the merged master's "Sleepy Joe" — an alias, so a fitted
    import naming either resolves to the one cultivar; never a rename, the
    owner has not picked)."""
    names = [row.get("strain"), row.get("strain_printed"), *row.get("retired_spellings", []),
             *row.get("disputed_spellings", [])]
    return tuple(dict.fromkeys(n.strip() for n in names if n))


def catalogue_aliases() -> dict[str, tuple[str, ...]]:
    """acronym → every known spelling, for importers that meet a strain under
    a name the cultivar master spells differently (the four disputed names
    stay one strain each, never two)."""
    out: dict[str, tuple[str, ...]] = {}
    for row in _load_catalogue().get("products", []):
        out.setdefault(row["acronym"], ())
        out[row["acronym"]] = tuple(dict.fromkeys(out[row["acronym"]] + _spellings(row)))
    return out


async def _rename_retired_spelling(c, user, row: dict, dry_run: bool):
    """INS-05 (owner 2026-09-06: strain names "as in the specifications"). Where
    both controlled sources agree on a spelling the August catalogue got wrong
    (PURE MICHIGEN, CLEMOSA A BUD), the packaged row lists the wrong one under
    `retired_spellings`; a cultivar still carrying it is renamed to the
    canonical name and the old spelling is kept in its note. Returns the
    rename record, or None."""
    retired = {s.strip().lower() for s in row.get("retired_spellings", [])}
    if not retired:
        return None
    cv = await c.fetchrow("SELECT id, name, note FROM cultivars WHERE code=$1", row["acronym"])
    if cv is None or cv["name"].strip().lower() not in retired:
        return None
    if cv["name"].strip().lower() == row["strain"].strip().lower():
        return None
    rec = {"code": row["acronym"], "from": cv["name"], "to": row["strain"]}
    if not dry_run:
        note = (f"Renamed from \"{cv['name']}\" on import of the ImB specifications —"
                " the specification prints the name this way (owner, 2026-09-06).")
        await c.execute(
            "UPDATE cultivars SET name=$1, note=COALESCE(note || E'\\n', '') || $2,"
            " updated_by=$3, updated_at=now() WHERE id=$4",
            row["strain"], note, user["id"], cv["id"])
    return rec


@router.post("/products/import")
async def import_products(body: ProductImportIn,
                          user: dict = Depends(require_role(*_HOQC))):
    """Load the packaged ImB catalogue (app/data/imb_products.json — every page
    of the owner's two documents) as DRAFT products, auto-creating cultivars
    from the product code's acronym. Idempotent on (code, doc_version);
    approval stays a second person's act. Reference data: since 2026-09-18 the
    fitted specifications (import-fitted) are what the facility grades on;
    these pages remain importable because they are the issued v.03 document."""
    cat = _load_catalogue()
    version = cat.get("doc_version", "v.03")
    doc_code = cat.get("doc_code", "QCSP 001")
    created, skipped, conflicts, cultivars_created, renamed = [], [], [], [], []
    seen_cultivars: set[str] = set()
    last_id = None
    async with rls(user) as c:
        # Review 2026-09-27 QR-02 (owner 2026-09-18): once a strain holds a
        # product of a LATER document version — its fitted set — the retired
        # v.03 pages are not loaded for it again. The import is refused as a
        # whole (409) naming those strains; a dry run reports them instead.
        acronyms = sorted({row["acronym"] for row in cat.get("products", [])})
        later = await c.fetch(
            "SELECT DISTINCT cv.code, p.doc_version FROM qc_products p"
            " JOIN cultivars cv ON cv.id = p.cultivar_id"
            " WHERE p.org_id=$1 AND cv.code = ANY($2::text[]) AND p.doc_version<>$3",
            user["org_id"], acronyms, version)
        refused = sorted({f"{r['code']} ({r['doc_version']})" for r in later
                          if _version_key(r["doc_version"]) > _version_key(version)})
        if refused and not body.dry_run:
            raise HTTPException(
                409, f"the {version} pages are retired for {', '.join(refused)} — a later"
                     " specification version exists for the strain(s); the fitted"
                     " specification is what the facility grades on (owner 2026-09-18)")
        for row in cat.get("products", []):
            strain, acr, code = row["strain"], row["acronym"], row["product_code"]
            _check_window(float(row["nominal_pct"]), float(row["window_min"]),
                          float(row["window_max"]), code)
            if acr not in seen_cultivars:
                rec = await _rename_retired_spelling(c, user, row, body.dry_run)
                if rec:
                    renamed.append(rec)
            cv, made, conflict = await resolve_or_create_cultivar(
                c, user, acr, strain, body.dry_run, aliases=_spellings(row))
            if conflict:
                conflicts.append(conflict)
                continue
            if made and made["code"] not in seen_cultivars:
                # A strain has several products; a dry run resolves nothing, so
                # without this the same new cultivar is reported once per page.
                cultivars_created.append(made)
            seen_cultivars.add(acr)
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
            notes = "Imported from the owner's ImB Product Specifications (window as printed: ±10 % of nominal)."
            if row.get("strain_printed") and row["strain_printed"] != strain:
                notes += f" The page prints the strain as {row['strain_printed']}."
            if row.get("spelling_disputed"):
                notes += " The two controlled sources disagree on this strain's spelling — open with the owner."
            last_id = await _insert_product(c, user, cv["id"], code, row["grade"], row["nominal_pct"],
                                            row["window_min"], row["window_max"], doc_code, version,
                                            src, notes)
            created.append(entry)
        if not body.dry_run and last_id is not None:
            await safe_emit(c, user, verb="product_catalogue_imported", object_type="qc_product",
                            object_id=last_id, recipients=[],
                            params={"doc_code": doc_code, "doc_version": version,
                                    "created": len(created), "skipped": len(skipped),
                                    "conflicts": len(conflicts)})
    return {"dry_run": body.dry_run, "doc_code": doc_code, "doc_version": version,
            "created": created, "skipped": skipped, "conflicts": conflicts,
            "cultivars_created": cultivars_created, "cultivars_renamed": renamed,
            "refused": refused}


@router.post("/products/import-fitted")
async def import_fitted(body: FittedImportIn, user: dict = Depends(require_role(*_HOQC))):
    """Load the owner's FINISHED fitted specifications (owner 2026-09-18) from
    the Potency Spec Service's export — the body is `GET /api/specs?status=finished`
    verbatim, plus the document version they were issued under.

    Per spec: every range becomes one DRAFT product `<ID>_THC<nominal>:CBD1`
    with the window the service prints (lo … hi), checked the way any other
    window is (nominal inside, ±10 % ceiling, no overlap within the strain)
    and checked against the spec's own arithmetic (`N ± t` → `N − t … N + t −
    0.01`) so a hand-edited export cannot slip through. Provenance — the
    service id, the finish date, the fitted tolerance and the result counts
    behind it — is written into `source` / `notes`. Draft specs are skipped
    unless `include_drafts`; a strain with no grades is skipped; a strain the
    cultivar master spells differently resolves through the packaged
    catalogue's aliases rather than becoming a second cultivar. Idempotent on
    (code, doc_version)."""
    created, skipped, conflicts, cultivars_created = [], [], [], []
    aliases = catalogue_aliases()
    last_id = None
    async with rls(user) as c:
        for spec in body.specs:
            sid = spec.id.strip().upper()
            if spec.status != "finished" and not body.include_drafts:
                skipped.append({"id": sid, "reason": "draft — not finished in the service"})
                continue
            if not spec.ranges:
                skipped.append({"id": sid, "reason": "no grades"})
                continue
            # The id becomes the cultivar code and the head of every product,
            # batch and mother id — it has to be a plain acronym. The service
            # also holds a partner's catalogue under ids like V_BG; those are
            # not this facility's strains and are reported, not loaded.
            if not PRODUCT_CODE_RE.match(compose_product_code(sid, spec.ranges[0].nominal, 1)):
                skipped.append({"id": sid, "reason": "id is not a strain acronym (letters and digits only)"})
                continue
            items = []
            for r in spec.ranges:
                lo_expected, hi_expected = round(r.nominal - r.tol, 2), round(r.nominal + r.tol - 0.01, 2)
                if abs(lo_expected - r.lo) > 0.006 or abs(hi_expected - r.hi) > 0.006:
                    raise HTTPException(
                        422, f"{sid} {r.nominal:g} ± {r.tol:g}: the export's window {r.lo}–{r.hi}"
                             f" is not the specification's own arithmetic ({lo_expected}–{hi_expected})"
                             " — re-export from the service rather than editing the file")
                _check_window(r.nominal, r.lo, r.hi, f"{sid} {r.nominal:g}")
                items.append({"grade": float(r.nominal), "nominal_pct": float(r.nominal),
                              "window_min": r.lo, "window_max": r.hi, "tol": r.tol,
                              "product_code": compose_product_code(sid, r.nominal, 1)})
            _validate_grade_set(items, sid)
            cv, made, conflict = await resolve_or_create_cultivar(
                c, user, sid, spec.name.strip(), body.dry_run, aliases=aliases.get(sid, ()))
            if conflict:
                conflicts.append(conflict)
                continue
            if made:
                cultivars_created.append(made)
            finished = (spec.finished_at or spec.updated_at or "")[:10]
            for it in items:
                if cv is not None:
                    exists = await c.fetchval(
                        "SELECT 1 FROM qc_products WHERE org_id=$1 AND product_code=$2"
                        " AND doc_version=$3", user["org_id"], it["product_code"], body.doc_version)
                    if exists:
                        skipped.append({"product_code": it["product_code"], "reason": "version exists"})
                        continue
                entry = {"product_code": it["product_code"], "strain": spec.name, "grade": it["grade"],
                         "tol": it["tol"], "window": [it["window_min"], it["window_max"]]}
                if body.dry_run or cv is None:
                    created.append(entry)
                    continue
                src = (f"Potency Spec Service export · spec {sid}"
                       f"{' finished ' + finished if finished else ''}"
                       f" · {len(spec.results_entered)} result(s) entered ({body.doc_code} {body.doc_version})")
                notes = (f"Fitted tolerance ±{it['tol']:g} (owner decision 2026-09-18: the fitted"
                         " approach applies everywhere; the flat ±10 % rule is retired as a grading"
                         f" method). {len(spec.results_excluded)} source result(s) excluded in the fit."
                         + (" User-created strain in the service." if spec.custom else ""))
                last_id = await _insert_product(c, user, cv["id"], it["product_code"], it["grade"],
                                                it["nominal_pct"], it["window_min"], it["window_max"],
                                                body.doc_code, body.doc_version, src, notes)
                created.append(entry)
        if not body.dry_run and last_id is not None:
            await safe_emit(c, user, verb="fitted_catalogue_imported", object_type="qc_product",
                            object_id=last_id, recipients=[],
                            params={"doc_code": body.doc_code, "doc_version": body.doc_version,
                                    "created": len(created), "skipped": len(skipped),
                                    "conflicts": len(conflicts)})
    return {"dry_run": body.dry_run, "doc_code": body.doc_code, "doc_version": body.doc_version,
            "created": created, "skipped": skipped, "conflicts": conflicts,
            "cultivars_created": cultivars_created}
