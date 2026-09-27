from app import docengine
from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from app.worktime import TZ
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .certificates import VoidIn, _mint_cert_number
from .common import (_COQ_ROLES, _HOQC, _WRITERS, _evaluate, _uuid_or_404, _uuid_or_422,
                     check_derived_total_units, derived_total, norm_batch, router)
from .coq_docx import _coq_client, _coq_manifest, _coq_markdown
from .laboratories import _lab_scope_set, _result_in_scope
from .potency import disposition_for
from .products import conformance_of, names_total_thc
from .specs import _ACID_FACTOR
from .signatures import _sig_out


_COQ_STATUSES = ("DRAFT", "APPROVED", "VOIDED")


_COQ_VOIDABLE = {"DRAFT", "APPROVED"}


_COQ_SOURCE_STATUSES = ("APPROVED", "RELEASED")


_COQ_SOURCE_TYPES = ("ICOA", "ECOA")


def _norm_test(name: str | None) -> str:
    """Fold a test name for comparison — same idiom as ecoa._norm_label /
    laboratories._norm. Both sides of the masked-failure match below are free
    text typed by different people at different times (qc_results.test_name on
    the analytical result, qc_oos_records.test_name on the investigation), so an
    investigation filed as "total  thc" still has to cover a "Total THC"
    failure. Only case and internal whitespace are folded — nothing else, so
    "Total THC" and "Total CBD" stay distinct."""
    return " ".join((name or "").split()).lower()


# SQL fragments shared by the three OOS gates (compile / review / render).
# Batch ids are compared case-insensitively (QC-27) for rows written before
# batch_id was normalised on write.
_OPEN_OOS_SQL = ("SELECT count(*) FROM qc_oos_records"
                 " WHERE upper(batch_id)=upper($1) AND status <> 'CLOSED'")
# A CLOSED investigation whose Qualified-Person disposition REJECTED the batch
# (review 2026-09-27 QC-01): no Certificate of Quality is compiled, approved
# or issued for a rejected batch, whatever a later re-test shows.
_REJECTED_OOS_SQL = ("SELECT oos_number FROM qc_oos_records"
                     " WHERE upper(batch_id)=upper($1) AND status='CLOSED'"
                     " AND disposition='REJECT' ORDER BY closed_at LIMIT 1")


async def _assert_batch_not_rejected(c, batch_id: str) -> None:
    rejected = await c.fetchval(_REJECTED_OOS_SQL, batch_id)
    if rejected:
        raise HTTPException(
            409, f"OOS {rejected} closed with the batch disposition REJECT — a Certificate of"
                 f" Quality is not compiled for a rejected batch ({batch_id}); a re-test does"
                 " not overturn a confirmed investigation (QCSOP 012 §6.4.1)")


async def _assert_sources_live(c, coq_id) -> None:
    """Every source certificate a CoQ snapshotted its lines from must still be
    APPROVED/RELEASED (review 2026-09-27 QC-02). void_certificate and the
    revision-release path refuse while a live CoQ cites the certificate, but a
    CoQ whose sources were voided or superseded before this rule existed —
    or through any path that bypasses it — must not be approved or printed."""
    dead = await c.fetch(
        "SELECT s.coa_number, c.status FROM qc_coq_sources s"
        " JOIN qc_certificates c ON c.id = s.coa_id"
        " WHERE s.coq_id=$1 AND c.status <> ALL($2::text[]) ORDER BY s.coa_number",
        coq_id, list(_COQ_SOURCE_STATUSES))
    if dead:
        names = ", ".join(f"{d['coa_number']} ({d['status']})" for d in dead[:5])
        raise HTTPException(
            409, f"source certificate(s) no longer valid: {names} — the CoQ was compiled from"
                 " lines of a record that has since been voided or superseded; void this CoQ"
                 " and recompile from the current certificates (QCSOP 012 §6.6/§6.7)")


class CoqIn(BaseModel):
    batch_id: str = Field(max_length=120)

    @field_validator("batch_id")
    @classmethod
    def _norm_batch_id(cls, v: str) -> str:
        # QC-27: every OOS/CoQ gate keys on this text — one canonical form.
        v = norm_batch(v)
        if not v:
            raise ValueError("batch_id must not be blank")
        return v

    specification_id: str
    # §6.4.2 batch identification — nullable; an unknown value stays blank for
    # a human, never invented (GxP).
    product_name: str | None = Field(default=None, max_length=300)
    manufacture_date: date | None = None
    batch_size: str | None = Field(default=None, max_length=120)
    comments: str | None = Field(default=None, max_length=4000)
    oos_reference: str | None = Field(default=None, max_length=300)
    # The cultivar this batch is — lets the CoQ grade it on Total Δ9-THC against
    # the cultivar's APPROVED potency ladder (PP-QC-SPEC-001). Optional: without
    # it the CoQ simply carries no grade (never invented).
    cultivar_id: str | None = None
    # The official ImB product the lot is certified against (qc_products).
    # Optional: a CoQ compiled before the catalogue, or for a strain with no
    # approved product, still grades on the legacy ladder.
    product_id: str | None = None
    # Review 2026-09-27 QC-15 — which testing period this CoQ certifies. The
    # owner issues CoQs for the initial release AND for later re-test periods
    # of the same batch against the same specification; they coexist, one
    # live APPROVED CoQ per (batch, spec, purpose, timepoint). A RETEST CoQ
    # names its timepoint ('6M', '12M', …).
    purpose: str = "INITIAL"
    timepoint: str | None = Field(default=None, max_length=40)
    # The source certificates to aggregate, by id. Optional: when absent every
    # usable (APPROVED/RELEASED iCoA/eCoA) certificate of the batch+spec is
    # consolidated, latest result per parameter. A re-test period names its
    # own certificates so the initial-release CoQ stays recompilable from the
    # release-time set once re-test results exist.
    source_coa_ids: list[str] | None = Field(default=None, max_length=50)



def _coq_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coq_number": r["coq_number"], "batch_id": r["batch_id"],
        "product_name": r["product_name"],
        "manufacture_date": r["manufacture_date"].isoformat() if r["manufacture_date"] else None,
        "batch_size": r["batch_size"],
        "specification_id": str(r["specification_id"]),
        "spec_reference": r["spec_reference"],
        "status": r["status"], "overall_conform": r["overall_conform"],
        "comments": r["comments"], "oos_reference": r["oos_reference"],
        "compiled_by": str(r["compiled_by"]) if r["compiled_by"] else None,
        "compiled_at": r["compiled_at"].isoformat() if r["compiled_at"] else None,
        "reviewed_by": str(r["reviewed_by"]) if r["reviewed_by"] else None,
        "reviewed_at": r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
        "void_reason": r["void_reason"],
        "voided_by": str(r["voided_by"]) if r["voided_by"] else None,
        "voided_at": r["voided_at"].isoformat() if r["voided_at"] else None,
        "coq_document_id": r["coq_document_id"],
        "coq_generated_at": r["coq_generated_at"].isoformat() if r["coq_generated_at"] else None,
        "cultivar_id": str(r["cultivar_id"]) if r.get("cultivar_id") else None,
        "potency_spec_id": str(r["potency_spec_id"]) if r.get("potency_spec_id") else None,
        "product_id": str(r["product_id"]) if r.get("product_id") else None,
        # The product verdict (official catalogue): filled by _with_product_fields
        # on the detail and compile responses; absent (None) on a bare list row.
        "product_code": r.get("product_code"),
        "product_conforms": r.get("product_conforms"),
        "regrade_to": r.get("regrade_to"),
        "purpose": r.get("purpose") or "INITIAL",
        "timepoint": r.get("timepoint"),
        "updated_at": r["updated_at"].isoformat(),
    }


async def _coq_total_thc(c, coq_id) -> float | None:
    """The batch's Total Δ9-THC: the computed total_thc CoQ line (Ph. Eur. 3028)."""
    total = await c.fetchval(
        "SELECT l.result_numeric FROM qc_coq_lines l"
        " JOIN qc_spec_parameters p ON p.id = l.parameter_id"
        " WHERE l.coq_id=$1 AND p.computed_kind='total_thc'"
        " AND l.result_numeric IS NOT NULL LIMIT 1", coq_id)
    return float(total) if total is not None else None


async def _coq_product_disposition(c, coq_row: dict) -> dict | None:
    """The product branch: the CoQ was compiled against ONE product of the
    official catalogue (qc_coq.product_id, frozen at compile). Its Total
    Δ9-THC is judged against that product's printed window; `matching`,
    `nearest` and `regrade_to` come from the same specification VERSION the
    product belongs to (its cultivar's products of that doc_version, whether
    still APPROVED or since SUPERSEDED), so the verdict an issued certificate
    shows does not drift when the catalogue is re-cut later."""
    prod = await c.fetchrow(
        "SELECT p.*, cv.code AS cultivar_code, cv.name AS cultivar_name FROM qc_products p"
        " JOIN cultivars cv ON cv.id = p.cultivar_id WHERE p.id=$1", coq_row["product_id"])
    if prod is None:
        return None
    siblings = await c.fetch(
        "SELECT id, product_code, nominal_pct, window_min, window_max, status FROM qc_products"
        " WHERE cultivar_id=$1 AND doc_version=$2 AND status<>'DRAFT' ORDER BY nominal_pct DESC",
        prod["cultivar_id"], prod["doc_version"])
    total_f = await _coq_total_thc(c, coq_row["id"])
    verdict = conformance_of([dict(s) for s in siblings], total_f, dict(prod))
    return {
        "kind": "product",
        "product_id": str(prod["id"]), "product_code": prod["product_code"],
        "product_status": prod["status"],
        "doc_code": prod["doc_code"], "doc_version": prod["doc_version"],
        "cultivar_code": prod["cultivar_code"], "cultivar_name": prod["cultivar_name"],
        "nominal": float(prod["nominal_pct"]),
        "window_min": float(prod["window_min"]), "window_max": float(prod["window_max"]),
        "total_d9_thc": total_f,
        "conforms": verdict["conforms"], "matching": verdict["matching"],
        "nearest": verdict["nearest"], "regrade_to": verdict["regrade_to"],
    }


def _with_product_fields(row: dict, disposition: dict | None) -> dict:
    """Copy the product verdict onto a qc_coq row dict so _coq_out can print it."""
    if disposition and disposition.get("kind") == "product":
        row = dict(row)
        row["product_code"] = disposition["product_code"]
        row["product_conforms"] = disposition["conforms"]
        row["regrade_to"] = disposition["regrade_to"]
    return row


async def _grade_against_product(c, user: dict, row: dict) -> dict:
    """Right after compile: judge the fresh CoQ against its product and, when
    the Total Δ9-THC is outside the window, hand the deviation to the
    Cultivation and Production managers (owner 2026-09-06: the value is
    accepted, the lot falls to the grade whose window holds it, and the
    departments that grew and processed it are told). The formal OOS the same
    rule requires is a person's act, checked at approval (_regrade_needs_oos)."""
    if not row.get("product_id"):
        return row
    disp = await _coq_product_disposition(c, row)
    row = _with_product_fields(row, disp)
    if not disp or disp["conforms"] is not False:
        return row
    managers = await users_admin_pool().fetch(
        "SELECT id FROM profiles WHERE org_id=$1 AND is_deleted=false AND is_active"
        " AND role = ANY($2::text[])", user["org_id"], ["CU_MGR", "PR_MGR"])
    await safe_emit(c, user, verb="potency_deviation", object_type="qc_coq",
                    object_id=str(row["id"]),
                    recipients=[(str(m["id"]), "workflow") for m in managers],
                    params={"coq_number": row["coq_number"], "batch_id": row["batch_id"],
                            "cultivar": disp["cultivar_code"],
                            "product_code": disp["product_code"],
                            "total_d9_thc": disp["total_d9_thc"],
                            "window_min": disp["window_min"], "window_max": disp["window_max"],
                            "regrade_to": disp["regrade_to"]})
    return row


async def _regrade_needs_oos(c, user: dict, coq_row: dict) -> str | None:
    """The approval half of the out-of-grade rule (owner 2026-09-06): a CoQ
    whose Total Δ9-THC is outside its product's window is approved only once a
    formal OOS naming Total Δ9-THC is on record for that batch — the batch
    disposition is investigated, the value accepted, the regrade documented.
    Returns the refusal text, or None when nothing stands in the way. (The
    §6.4.1 gate in review_coq already refuses while any OOS is still open, so
    in practice the investigation has to be CLOSED.)"""
    if not coq_row.get("product_id"):
        return None
    disp = await _coq_product_disposition(c, coq_row)
    if not disp or disp["conforms"] is not False:
        return None
    rows = await c.fetch(
        "SELECT test_name FROM qc_oos_records WHERE org_id=$1 AND batch_id=$2",
        user["org_id"], coq_row["batch_id"])
    if any(names_total_thc(r["test_name"]) for r in rows):
        return None
    lo, hi, tot = disp["window_min"], disp["window_max"], disp["total_d9_thc"]
    falls = (f"the lot falls to {disp['regrade_to']}" if disp["regrade_to"]
             else "no grade of this strain holds the value")
    return (f"Total Δ9-THC {tot:.2f} % is outside {disp['product_code']}'s window"
            f" ({lo:.2f}–{hi:.2f} %) — {falls}; a formal OOS naming Total Δ9-THC must be"
            f" recorded on batch {coq_row['batch_id']} before this CoQ is approved"
            " (out-of-grade rule, owner 2026-09-06)")
_COQ_PURPOSES = ("INITIAL", "RETEST")


async def _coq_disposition(c, coq_row: dict) -> dict | None:
    """The batch's potency grade, from the grade source FROZEN on the CoQ at
    compile time: the official product (qc_coq.product_id → kind "product",
    _coq_product_disposition) or, for CoQs issued before the catalogue, the
    ladder version (qc_coq.potency_spec_id → kind "ladder", Spec I…N). Read
    against the CoQ's own Total Δ9-THC line. Returns None when the CoQ carries
    neither (no cultivar mapped, or none APPROVED at compile). Freezing the
    id keeps the printed grade stable and traceable after later supersession."""
    if coq_row.get("product_id"):
        return await _coq_product_disposition(c, coq_row)
    spec_id = coq_row.get("potency_spec_id")
    if not spec_id:
        return None
    spec = await c.fetchrow(
        "SELECT ps.id, ps.version, ps.floor_pct, ps.status, cv.code AS cultivar_code,"
        " cv.name AS cultivar_name FROM qc_potency_specs ps"
        " JOIN cultivars cv ON cv.id = ps.cultivar_id WHERE ps.id=$1", spec_id)
    if spec is None:
        return None
    ranges = await c.fetch(
        "SELECT tier, range_min, range_max, nominal FROM qc_potency_spec_ranges"
        " WHERE potency_spec_id=$1 ORDER BY tier", spec_id)
    total_f = await _coq_total_thc(c, coq_row["id"])
    disp = disposition_for(spec["floor_pct"], [dict(r) for r in ranges], total_f)
    return {
        "kind": "ladder",
        "potency_spec_id": str(spec["id"]), "version": spec["version"],
        "spec_status": spec["status"],
        "cultivar_code": spec["cultivar_code"], "cultivar_name": spec["cultivar_name"],
        "floor_pct": float(spec["floor_pct"]),
        "total_d9_thc": total_f,
        "below_spec": (total_f is not None and disp is None),
        "disposition": disp,
    }


def _coq_line_out(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "parameter_name": r["parameter_name"], "test_method": r["test_method"],
        "acceptance_criterion": r["acceptance_criterion"],
        "result_value": r["result_value"],
        "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
        "unit": r["unit"], "complies": r["complies"], "testing_lab": r["testing_lab"],
        "source_coa_id": str(r["source_coa_id"]) if r["source_coa_id"] else None,
        "source_coa_number": r["source_coa_number"],
        "sorting_order": r["sorting_order"],
    }


def _coq_source_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_id": str(r["coa_id"]),
        "coa_number": r["coa_number"], "cert_type": r["cert_type"],
        "issue_date": r["issue_date"].isoformat() if r["issue_date"] else None,
        # the source certificate's LIVE status (QC-02) — a snapshot line whose
        # source has been voided/superseded is shown as such, not as bare numbers
        "coa_status": r.get("coa_status"),
        "coa_decision": r.get("coa_decision"),
    }


_SOURCES_SQL = ("SELECT s.*, c.status AS coa_status, c.decision AS coa_decision"
                " FROM qc_coq_sources s LEFT JOIN qc_certificates c ON c.id = s.coa_id"
                " WHERE s.coq_id=$1 ORDER BY s.coa_number")


def _coq_criterion(lo, hi, unit) -> str | None:
    """Human acceptance-criterion snapshot from the spec limits — empty stays
    None (an absent limit is absent, never invented)."""
    if lo is None and hi is None:
        return None
    s = f"{'' if lo is None else lo} … {'' if hi is None else hi}".strip()
    return f"{s} {unit}".strip() if unit else s


@router.get("/coq")
async def list_coq(batch_id: str | None = None, status: str | None = None,
                   user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_coq{where} ORDER BY created_at DESC", *args)
    return [_coq_out(dict(r)) for r in rows]


@router.get("/coq/{coq_id}")
async def get_coq(coq_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM qc_coq WHERE id=$1", coq_id)
        if row is None:
            raise HTTPException(404, "CoQ not found")
        lines = await c.fetch(
            "SELECT * FROM qc_coq_lines WHERE coq_id=$1 ORDER BY sorting_order, created_at", coq_id)
        sources = await c.fetch(_SOURCES_SQL, coq_id)
        disposition = await _coq_disposition(c, dict(row))
        # Commercial identity (0059) — read-only companion data joined by the
        # batch-code string. Absent row → absent key content; never fabricated,
        # and never part of the certificate content itself.
        commercial = await c.fetchrow(
            "SELECT neu_name, brand, final_label, tranche, thc_bracket"
            " FROM batch_commercial_identities WHERE batch_code=$1", row["batch_id"])
    return {"coq": _coq_out(_with_product_fields(dict(row), disposition)),
            "lines": [_coq_line_out(dict(r)) for r in lines],
            "sources": [_coq_source_out(dict(r)) for r in sources],
            "potency": disposition,
            "commercial": dict(commercial) if commercial else None}


@router.post("/coq", status_code=201)
async def compile_coq(body: CoqIn, user: dict = Depends(require_role(*_WRITERS))):
    """§6.4.1 — compile the per-batch Certificate of Quality: consolidate every
    usable iCoA/eCoA result for the batch against the specification, one line
    per spec parameter (the LATEST result wins when a parameter was re-tested;
    Ph. Eur. 3028 derived totals are computed from components, never
    transcribed), each line citing its source certificate + testing lab.
    Aggregation only — no value is invented; a non-conforming line is recorded
    (overall_conform=false), never hidden."""
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    if body.purpose not in _COQ_PURPOSES:
        raise HTTPException(422, f"purpose must be one of: {', '.join(_COQ_PURPOSES)}")
    body.timepoint = (body.timepoint or "").strip() or None
    if body.purpose == "RETEST" and not body.timepoint:
        raise HTTPException(422, "a RETEST CoQ names its timepoint (e.g. '6M')")
    if body.purpose == "INITIAL" and body.timepoint:
        raise HTTPException(422, "an INITIAL-release CoQ carries no timepoint")
    for sid in body.source_coa_ids or []:
        _uuid_or_422(sid, "source_coa_ids")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                body.specification_id)
        if spec is None:
            raise HTTPException(422, "Unknown specification")
        # Optional cultivar grade: validate the cultivar, then FREEZE the ladder
        # version APPROVED right now — the printed grade must stay stable and
        # traceable even after the ladder is later superseded. No approved ladder
        # yet → the CoQ carries the cultivar but no grade (never invented).
        # The official product catalogue (2026-09-05) grades a lot against ONE
        # product's printed window. Naming a product settles the cultivar too,
        # and leaves the ladder out of it — two live grade schemes on one
        # document would be two answers to one question.
        product_id = None
        if body.product_id:
            _uuid_or_422(body.product_id, "product_id")
            prod = await c.fetchrow(
                "SELECT id, cultivar_id, product_code, status FROM qc_products WHERE id=$1",
                body.product_id)
            if prod is None:
                raise HTTPException(422, "Unknown product")
            if prod["status"] != "APPROVED":
                raise HTTPException(
                    422, f"{prod['product_code']} is {prod['status']} — a lot is certified"
                         " against an APPROVED product specification")
            if body.cultivar_id and str(body.cultivar_id) != str(prod["cultivar_id"]):
                raise HTTPException(422, f"{prod['product_code']} is not this cultivar's product")
            product_id = prod["id"]
            body.cultivar_id = str(prod["cultivar_id"])
        potency_spec_id = None
        if body.cultivar_id and product_id is None:
            cv = await c.fetchrow(
                "SELECT id FROM cultivars WHERE id=$1 AND is_active", body.cultivar_id)
            if cv is None:
                raise HTTPException(422, "Unknown or inactive cultivar")
            potency_spec_id = await c.fetchval(
                "SELECT id FROM qc_potency_specs WHERE cultivar_id=$1 AND status='APPROVED'",
                body.cultivar_id)
        certs = await c.fetch(
            "SELECT * FROM qc_certificates WHERE upper(batch_id)=upper($1) AND specification_id=$2"
            " AND cert_type = ANY($3::text[]) AND status = ANY($4::text[])"
            " ORDER BY created_at",
            body.batch_id, body.specification_id,
            list(_COQ_SOURCE_TYPES), list(_COQ_SOURCE_STATUSES))
        if not certs:
            raise HTTPException(
                409, "No usable source certificate (APPROVED/RELEASED iCoA or eCoA)"
                     " exists for this batch and specification (§6.4.2)")
        if body.source_coa_ids:
            # QC-15: an explicit source set — every id must be one of the
            # batch's usable certificates (never a certificate of another
            # batch, specification or status).
            usable = {str(c_["id"]): c_ for c_ in certs}
            unknown = [sid for sid in body.source_coa_ids if sid not in usable]
            if unknown:
                raise HTTPException(
                    422, f"{len(unknown)} source_coa_ids are not APPROVED/RELEASED iCoA/eCoA"
                         " certificates of this batch and specification")
            certs = [usable[sid] for sid in dict.fromkeys(body.source_coa_ids)]
        cert_ids = [c_["id"] for c_ in certs]
        # §6.3.2 — an eCoA source promoted from an ingested document feeds a CoQ
        # only after its QCT 018 review checklist is ACCEPTED. Matched through
        # the WHOLE supersession chain: a revised certificate carries the same
        # transcribed external data as the promoted original it corrects, so a
        # routine revise→release cycle must not slip past the checklist gate.
        bad_docs = await c.fetch(
            """
            WITH RECURSIVE chain AS (
                SELECT id, supersedes_id FROM qc_certificates WHERE id = ANY($1::uuid[])
                UNION ALL
                SELECT p.id, p.supersedes_id FROM qc_certificates p
                JOIN chain ch ON p.id = ch.supersedes_id
            )
            SELECT d.doc_number, cl.outcome FROM qc_coa_documents d
            LEFT JOIN qc_ecoa_checklist cl ON cl.document_id = d.id
            WHERE d.promoted_coa_id IN (SELECT id FROM chain)
              AND (cl.outcome IS NULL OR cl.outcome <> 'ACCEPTED')
            """,
            cert_ids)
        if bad_docs:
            names = ", ".join(f"{d['doc_number']} ({d['outcome'] or 'no checklist'})"
                              for d in bad_docs[:5])
            raise HTTPException(
                409, f"eCoA source(s) lack an ACCEPTED QCT 018 review checklist: {names}"
                     " (QCSOP 012 §6.3.2)")
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1 ORDER BY sorting_order, created_at",
            body.specification_id)
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id = ANY($1::uuid[]) ORDER BY created_at",
            cert_ids)
        open_oos = await c.fetchval(_OPEN_OOS_SQL, body.batch_id)
        row = None
        if not open_oos:
            await _assert_batch_not_rejected(c, body.batch_id)
            row = await _compile_coq_tx(c, user, body, spec, certs, params, results,
                                        potency_spec_id, product_id)
            row = await _grade_against_product(c, user, dict(row))
    if open_oos:
        # §6.16 (C8) — an attempted CoQ compile on an open-OOS batch is itself a
        # reportable deviation, recorded in its own transaction so the 409
        # cannot roll the event back.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_specification",
                       object_id=str(spec["id"]), recipients=[],
                       params={"reason": "coq_compile_on_open_oos", "batch_id": body.batch_id,
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {body.batch_id}"
                 " — the CoQ is compiled only on the investigation-confirmed result set"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    return _coq_out(dict(row))


async def _compile_coq_tx(c, user: dict, body: CoqIn, spec, certs, params, results,
                          potency_spec_id=None, product_id=None):
    """The aggregation itself — runs INSIDE the caller's transaction, so the
    validation reads, the advisory-locked number mint, and the inserts are one
    atomic unit (no window for a source to be voided or an OOS to open between
    validation and insert)."""
    certs = [dict(x) for x in certs]
    by_cert = {str(x["id"]): x for x in certs}
    # Latest result per spec parameter across ALL source certificates — a
    # re-test supersedes for reporting; the earlier result stays on its own
    # certificate (nothing is deleted). "Latest" is by MEASUREMENT date
    # (review 2026-09-27 QC-09): result_date, which every write path now
    # stamps (add_result defaults it to the facility day, promote carries the
    # eCoA's report date). A row from before that rule has no measurement
    # date; the best evidence is the facility day it was entered on, which is
    # what add_result would have stamped, so that is what it sorts by —
    # never date.min (an undated eCoA result lost to any dated result) and
    # never "NULL wins".
    def _measured(x):
        return x["result_date"] or x["created_at"].astimezone(TZ).date()
    latest: dict[str, dict] = {}
    for r in sorted(results, key=lambda x: (_measured(x), x["created_at"])):
        if r["parameter_id"]:
            latest[str(r["parameter_id"])] = dict(r)
    # An explicitly cited reference is ALWAYS authenticated, whatever else the
    # batch carries (QC-31: it used to be validated only when a masked failure
    # existed, and stored unchecked otherwise). This check once sat nested
    # under `if not closed_oos:`, which the caller's open-OOS gate made
    # unreachable, so a fabricated oos_reference sailed straight through.
    if body.oos_reference:
        cited = await c.fetchval(
            "SELECT 1 FROM qc_oos_records WHERE org_id=$1 AND upper(batch_id)=upper($2)"
            " AND oos_number=$3 AND status='CLOSED'",
            user["org_id"], body.batch_id, body.oos_reference)
        if not cited:
            raise HTTPException(
                409, f"oos_reference '{body.oos_reference}' does not match a CLOSED OOS"
                     " record on this batch — cite an existing closed investigation's"
                     " OOS number, or close the investigation (QCSOP 012 §6.4.1)")
    # §6.4.1 — the CoQ is compiled only on the INVESTIGATION-CONFIRMED result
    # set. A failing result superseded by a later passing re-test must not
    # silently vanish from the batch record: EACH masked failure needs its own
    # OOS trail — a CLOSED investigation on this batch raised against that same
    # result, or against that same test, whose Phase I INVALIDATED the result.
    #
    # Review 2026-09-27 QC-06: a source certificate the Head of QC dispositioned
    # FAIL is a failed record as a whole, whatever its per-line `complies` say
    # (a FAIL on a non-numeric observation leaves every line green). None of
    # its lines may certify conformance: while one of them is the batch's
    # current line the CoQ compiles as NON-conforming (recorded for the QP,
    # never printed — the sources carry the certificate's decision), and one
    # that a later result superseded is treated like a masked failure — it
    # needs the same invalidating OOS trail.
    failed_cert_ids = {str(x["id"]) for x in certs if x["decision"] == "FAIL"}
    failed_winner = any(str(ln["coa_id"]) in failed_cert_ids for ln in latest.values())
    masked_fails = [dict(r) for r in results
                    if r["parameter_id"]
                    and (r["complies"] is False or str(r["coa_id"]) in failed_cert_ids)
                    and latest.get(str(r["parameter_id"]), {}).get("id") != r["id"]]
    if masked_fails:
        # Cover is per-PARAMETER, not per-batch. Batch scope was too loose: a
        # closed microbial investigation would otherwise silently license
        # dropping a masked potency failure, because the old counter asked only
        # "does this batch have ANY closed OOS?". An OOS carries result_id
        # (exact result it was raised on) and/or test_name; either binds it.
        #
        # Review 2026-09-27 QC-01: cover comes ONLY from a CLOSED investigation
        # that INVALIDATED the original result (Phase I: assignable laboratory
        # error, `invalidated IS TRUE`). Any CLOSED OOS naming the test used to
        # count, whatever it concluded — a Phase II that attributed the failure
        # to the batch still licensed the passing re-test, which is testing
        # into compliance. A REJECT disposition is refused before this point.
        oos_rows = await c.fetch(
            "SELECT result_id, test_name, oos_number, invalidated FROM qc_oos_records"
            " WHERE org_id=$1 AND upper(batch_id)=upper($2) AND status='CLOSED'",
            user["org_id"], body.batch_id)
        covered_ids = {str(o["result_id"]) for o in oos_rows if o["result_id"] and o["invalidated"]}
        covered_tests = {_norm_test(o["test_name"]) for o in oos_rows
                         if o["test_name"] and o["invalidated"]}
        named_ids = {str(o["result_id"]) for o in oos_rows if o["result_id"]}
        named_tests = {_norm_test(o["test_name"]) for o in oos_rows if o["test_name"]}
        uncovered, confirmed = set(), set()
        for r in masked_fails:
            if str(r["id"]) in covered_ids or _norm_test(r["test_name"]) in covered_tests:
                continue
            if str(r["id"]) in named_ids or _norm_test(r["test_name"]) in named_tests:
                confirmed.add(r["test_name"])
            else:
                uncovered.add(r["test_name"])
        if confirmed:
            names = ", ".join(sorted(confirmed)[:5])
            raise HTTPException(
                409, f"{len(confirmed)} test(s) ({names}) had a failing result superseded by a"
                     " re-test, and the closed OOS investigation on that test CONFIRMED the"
                     " result (it was not invalidated by an assignable laboratory error) — the"
                     " re-test does not replace a confirmed failure (QCSOP 012 §6.4.1)")
        if uncovered:
            names = ", ".join(sorted(uncovered)[:5])
            raise HTTPException(
                409, f"{len(uncovered)} test(s) ({names}) had a failing result"
                     " superseded by a re-test with no closed OOS investigation naming that same"
                     " test — the CoQ compiles only the investigation-confirmed result set"
                     " (QCSOP 012 §6.4.1; close an OOS against that test, or cite one via"
                     " oos_reference)")
    lines, cited_cert_ids, missing = [], set(), []
    for i, p in enumerate(params):
        pid = str(p["id"])
        crit = _coq_criterion(
            float(p["lower_limit"]) if p["lower_limit"] is not None else None,
            float(p["upper_limit"]) if p["upper_limit"] is not None else None,
            p["unit"])
        if p["computed_kind"]:
            # Ph. Eur. 3028 derived total — computed here from the latest
            # component results (total = neutral + 0.877 × acid).
            ra = latest.get(str(p["component_a_id"])) if p["component_a_id"] else None
            rb = latest.get(str(p["component_b_id"])) if p["component_b_id"] else None
            if not (ra and rb and ra["result_numeric"] is not None
                    and rb["result_numeric"] is not None):
                missing.append(p["test_name_en"] or p["test_name_mk"] or "?")
                continue
            check_derived_total_units(dict(p), ra, rb)
            # ONE computation for every path (QC-10/QC-20): Decimal, half-up.
            val = derived_total(ra["result_numeric"], rb["result_numeric"])
            complies, _st = _evaluate(val, p["lower_limit"], p["upper_limit"])
            for comp in (ra, rb):
                cited_cert_ids.add(str(comp["coa_id"]))
            lines.append({
                "parameter_id": p["id"],
                "parameter_name": p["test_name_en"] or p["test_name_mk"] or "?",
                "test_method": p["test_method"] or p["pharmacopoeia_ref"],
                "acceptance_criterion": crit, "result_value": None,
                "result_numeric": val, "unit": p["unit"], "complies": complies,
                "testing_lab": None, "source_coa_id": None,
                "source_coa_number": "Computed — Ph. Eur. 3028", "sorting_order": i,
            })
            continue
        r = latest.get(pid)
        if r is None:
            missing.append(p["test_name_en"] or p["test_name_mk"] or "?")
            continue
        src = by_cert.get(str(r["coa_id"])) or {}
        cited_cert_ids.add(str(r["coa_id"]))
        lines.append({
            "parameter_id": p["id"],
            "parameter_name": p["test_name_en"] or p["test_name_mk"] or "?",
            "test_method": p["test_method"] or p["pharmacopoeia_ref"],
            "acceptance_criterion": crit, "result_value": r["result_value"],
            "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
            "unit": r["unit"] or p["unit"], "complies": r["complies"],
            "testing_lab": r["source_institution"] or src.get("source_lab"),
            "source_coa_id": r["coa_id"], "source_coa_number": src.get("coa_number"),
            "sorting_order": i,
        })
    if missing:
        names = ", ".join(missing[:5])
        raise HTTPException(
            409, f"{len(missing)} specification parameter(s) have no result ({names}"
                 f"{'…' if len(missing) > 5 else ''}) — the batch is not fully"
                 " tested, the CoQ cannot be compiled (§6.4.1)")
    if not lines:
        # GxP: an empty results table must never yield a vacuous conformance
        # assertion — there is literally nothing to certify.
        raise HTTPException(409, "the specification has no parameters — nothing to certify")
    # Overall conformance: asserted only when every line complies; a single
    # FAIL makes it false; an unknown (unmeasured verdict) stays null.
    verdicts = [ln["complies"] for ln in lines]
    if any(v is False for v in verdicts) or failed_winner:
        overall = False
    elif all(v is True for v in verdicts):
        overall = True
    else:
        overall = None
    spec_ref = spec["spec_id"] or ""
    if spec["version"]:
        spec_ref = f"{spec_ref} · v{spec['version']}".strip(" ·")
    coq_number = await _mint_cert_number(c, user["org_id"], "COQ")
    row = await c.fetchrow(
        "INSERT INTO qc_coq(org_id, coq_number, batch_id, product_name, manufacture_date,"
        " batch_size, specification_id, spec_reference, overall_conform, comments,"
        " oos_reference, compiled_by, compiled_at, created_by, updated_by,"
        " cultivar_id, potency_spec_id, product_id, purpose, timepoint)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,now(),$12,$12,$13,$14,$15,$16,$17)"
        " RETURNING *",
        user["org_id"], coq_number, body.batch_id, body.product_name,
        body.manufacture_date, body.batch_size, body.specification_id, spec_ref,
        overall, body.comments, body.oos_reference, user["id"],
        body.cultivar_id, potency_spec_id, product_id, body.purpose, body.timepoint)
    for src_id in sorted(cited_cert_ids):
        src = by_cert[src_id]
        await c.execute(
            "INSERT INTO qc_coq_sources(org_id, coq_id, coa_id, coa_number, cert_type,"
            " issue_date) VALUES ($1,$2,$3,$4,$5,$6)",
            user["org_id"], row["id"], src["id"], src["coa_number"], src["cert_type"],
            src["report_date"])
    for ln in lines:
        await c.execute(
            "INSERT INTO qc_coq_lines(org_id, coq_id, parameter_id, parameter_name,"
            " test_method, acceptance_criterion, result_value, result_numeric, unit,"
            " complies, testing_lab, source_coa_id, source_coa_number, sorting_order)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
            user["org_id"], row["id"], ln["parameter_id"], ln["parameter_name"],
            ln["test_method"], ln["acceptance_criterion"], ln["result_value"],
            ln["result_numeric"], ln["unit"], ln["complies"], ln["testing_lab"],
            ln["source_coa_id"], ln["source_coa_number"], ln["sorting_order"])
    await safe_emit(c, user, verb="coq_compiled", object_type="qc_coq",
               object_id=str(row["id"]), recipients=[],
               params={"coq_number": coq_number, "batch_id": body.batch_id,
                       "overall_conform": overall, "sources": len(cited_cert_ids)})
    return row


@router.post("/coq/{coq_id}/review")
async def review_coq(coq_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    # M2 (URS §3 / QCSOP-012 C5): the CoQ is approved by the Head of QC and carries
    # NO QP signature — the QP receives it. The issuing gate already excludes QP
    # (_COQ_ROLES on render_coq); the approval-of-record here must match, so it is
    # gated on _COQ_ROLES (ADMIN, QC_MGR), not _HOQC (which still admits QP).
    """§6.4.3 — the Head of QC reviews and approves the compiled CoQ. Second
    person: the reviewer must not be the compiler. No QP signature — the
    approved CoQ is an input TO the QP batch-release decision."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT * FROM qc_coq WHERE id=$1", coq_id)
        if cur is None:
            raise HTTPException(404, "CoQ not found")
        if cur["status"] != "DRAFT":
            raise HTTPException(409, f"a {cur['status']} CoQ cannot be approved")
        # Out-of-grade rule (owner 2026-09-06): a lot outside its product's
        # window is approved only with a formal OOS on the batch disposition.
        needs_oos = await _regrade_needs_oos(c, user, dict(cur))
        if needs_oos:
            raise HTTPException(409, needs_oos)
        if cur["compiled_by"] and str(cur["compiled_by"]) == str(user["id"]):
            raise HTTPException(403, "the CoQ is reviewed by a second person —"
                                     " the compiler cannot approve their own compilation (§6.4.3)")
        # one live APPROVED CoQ per (batch, spec, purpose, timepoint) — two
        # divergent approved aggregations for one period would hand the QP
        # conflicting release inputs (a partial unique index, 0041/0071, backs
        # this at the DB level). An initial-release CoQ and a re-test-period
        # CoQ are different periods and coexist (QC-15).
        dup = await c.fetchval(
            "SELECT coq_number FROM qc_coq WHERE upper(batch_id)=upper($1) AND specification_id=$2"
            " AND purpose=$4 AND COALESCE(timepoint,'')=COALESCE($5,'')"
            " AND status='APPROVED' AND id <> $3 LIMIT 1",
            cur["batch_id"], cur["specification_id"], coq_id, cur["purpose"], cur["timepoint"])
        if dup:
            raise HTTPException(409, f"an APPROVED CoQ ({dup}) already exists for this batch,"
                                     " specification and testing period — void it before"
                                     " approving another")
        # §6.4.1 — the OOS state can change between compile and approval; the
        # HoQC signature must not land on a batch under open investigation.
        open_oos = await c.fetchval(_OPEN_OOS_SQL, cur["batch_id"])
        row = None
        if not open_oos:
            await _assert_batch_not_rejected(c, cur["batch_id"])
            await _assert_sources_live(c, coq_id)
            row = await c.fetchrow(
                "UPDATE qc_coq SET status='APPROVED', reviewed_by=$1, reviewed_at=now(),"
                " updated_by=$1, updated_at=now() WHERE id=$2 RETURNING *", user["id"], coq_id)
            await safe_emit(c, user, verb="coq_reviewed", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"coq_number": row["coq_number"]})
    if open_oos:
        # §6.16 (C8) — recorded in its own transaction so the 409 cannot roll
        # the deviation event back.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"reason": "coq_approve_on_open_oos", "batch_id": cur["batch_id"],
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {cur['batch_id']}"
                 " — the CoQ cannot be approved until the investigation is closed"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    return _coq_out(dict(row))


@router.post("/coq/{coq_id}/void")
async def void_coq(coq_id: str, body: VoidIn, user: dict = Depends(require_role(*_HOQC))):
    """§6.6 — void a fundamentally-invalid CoQ (wrong batch / wrong sources).
    Head-of-QC act, written reason mandatory; the record is retained, never
    deleted (GxP)."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_coq WHERE id=$1", coq_id)
        if cur is None:
            raise HTTPException(404, "CoQ not found")
        if cur["status"] not in _COQ_VOIDABLE:
            raise HTTPException(409, f"a {cur['status']} CoQ cannot be voided")
        row = await c.fetchrow(
            "UPDATE qc_coq SET status='VOIDED', void_reason=$1, voided_by=$2, voided_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 RETURNING *",
            body.reason.strip(), user["id"], coq_id)
        await safe_emit(c, user, verb="coq_voided", object_type="qc_coq",
                   object_id=coq_id, recipients=[],
                   params={"coq_number": row["coq_number"], "reason": body.reason.strip()})
    return _coq_out(dict(row))


@router.post("/coq/{coq_id}/render", status_code=201)
async def render_coq(coq_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    """Render the APPROVED aggregation CoQ to the bilingual house-style .docx
    via the DocEngine (same PASS-gated pipeline as the single-certificate CoQ).
    A printable Certificate of Quality asserts conformance — it is issued only
    for a conforming batch (overall_conform=true); a non-conforming CoQ stays
    an in-app record for the QP (GxP: never render a conformant certificate
    over failing data)."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        coq = await c.fetchrow("SELECT * FROM qc_coq WHERE id=$1", coq_id)
        if coq is None:
            raise HTTPException(404, "CoQ not found")
        if coq["status"] != "APPROVED":
            raise HTTPException(409, "the CoQ document is rendered only from an APPROVED CoQ")
        if coq["overall_conform"] is not True:
            raise HTTPException(
                409, "the batch does not conform (or conformance is undetermined) —"
                     " a Certificate of Quality asserting conformance cannot be issued")
        # §6.4.1 — re-check at ISSUANCE time: an OOS opened after compile/
        # approval must block the printable conformance document.
        open_oos = await c.fetchval(_OPEN_OOS_SQL, coq["batch_id"])
        if not open_oos:
            await _assert_batch_not_rejected(c, coq["batch_id"])
            await _assert_sources_live(c, coq_id)
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                coq["specification_id"])
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", coq["specification_id"])
        lines = await c.fetch(
            "SELECT * FROM qc_coq_lines WHERE coq_id=$1 ORDER BY sorting_order, created_at",
            coq_id)
        # The batch's per-cultivar potency grade, resolved against the ladder
        # version frozen on the CoQ at compile time (Phase B) — rendered into the
        # document's meta grid.
        potency = await _coq_disposition(c, dict(coq))
        # The cultivar name for the meta grid's own Cultivar row — resolved even
        # when no ladder is frozen (cultivar set, grade absent).
        cultivar_name = None
        if coq["cultivar_id"]:
            cvrow = await c.fetchrow(
                "SELECT code, name FROM cultivars WHERE id=$1", coq["cultivar_id"])
            if cvrow:
                cultivar_name = cvrow["name"] or cvrow["code"]
        # Ordered by real dates (not the coa_number string — per-type/per-year
        # numbering means lexical order doesn't reliably track issuance order),
        # oldest first so the fallback pick below still means "the newest one".
        sources = await c.fetch(
            "SELECT * FROM qc_coq_sources WHERE coq_id=$1"
            " ORDER BY issue_date NULLS FIRST, created_at", coq_id)
        # primary source certificate — richest identity metadata for the meta
        # grid (prefer the in-house iCoA; fall back to the newest source).
        primary = None
        src_rows = [dict(s) for s in sources]
        if src_rows:
            pick = next((s for s in src_rows if s["cert_type"] == "ICOA"), src_rows[-1])
            primary = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1",
                                       pick["coa_id"])
        # ISO 17025 scope advisory (parity with the single-certificate CoQ, URS
        # Ch. 7): an aggregation CoQ draws each line from a DIFFERENT source
        # certificate — hence a different testing lab — so scope is judged PER
        # SOURCE: each line's method against ITS OWN lab's accredited scope.
        # Advisory only (a footnote), never an OOS, never blocking; a lab that
        # declares no scope is unjudgeable and flags nothing.
        scope_by_source: dict = {}
        src_coa_ids = list({ln["source_coa_id"] for ln in lines if ln["source_coa_id"]})
        # QC-25: the "ISO/IEC 17025 accredited" claim in the compliance
        # statement is made only when EVERY external source certificate names
        # a registered laboratory carrying an accreditation record (and, below,
        # nothing is out of scope); an in-house source needs none.
        accredited_by_lab: dict = {}
        ext_src_ids: list = []
        lab_of: dict = {}
        if src_coa_ids:
            lab_of = {r["id"]: r["laboratory_id"] for r in await c.fetch(
                "SELECT id, laboratory_id FROM qc_certificates WHERE id = ANY($1)", src_coa_ids)}
            lab_ids = list({v for v in lab_of.values() if v})
            scope_by_lab = {}
            if lab_ids:
                for lr in await c.fetch(
                        "SELECT id, iso17025_scope, accreditation_number, accreditation_body"
                        " FROM qc_laboratories WHERE id = ANY($1)", lab_ids):
                    scope_by_lab[lr["id"]] = _lab_scope_set(lr["iso17025_scope"])
                    accredited_by_lab[lr["id"]] = bool(lr["accreditation_number"]
                                                       or lr["accreditation_body"])
            scope_by_source = {cid: scope_by_lab.get(lab_of.get(cid), set()) for cid in src_coa_ids}
            ext_src_ids = [s["coa_id"] for s in src_rows if s["cert_type"] == "ECOA"]
        # Annex 11 e-signatures captured on the CoQ itself (QC-12) — COMPILED /
        # APPROVED by the roles of record, rendered in the signature block.
        coq_sigs = [_sig_out(dict(s)) for s in await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_coq' AND object_id=$1"
            " ORDER BY signed_at", coq_id)]
    if open_oos:
        # §6.16 (C8) — recorded in its own transaction, before the 409.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"reason": "coq_render_on_open_oos", "batch_id": coq["batch_id"],
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {coq['batch_id']}"
                 " — the CoQ document cannot be issued until the investigation is closed"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    params_by_id = {str(p["id"]): dict(p) for p in params}
    issue_by_number = {s["coa_number"]: s["issue_date"] for s in src_rows}
    primary = dict(primary) if primary else {}
    # Synthesize the renderer's certificate dict: CoQ identity + the primary
    # source's product metadata. Unknown fields stay absent — never invented.
    coa_view = {
        "coa_number": coq["coq_number"], "cert_type": "COQ", "decision": "PASS",
        # the CoQ's authorised approver is the HoQC who reviewed/approved it
        # (§6.4.3) — the mandatory-content manifest requires an approver of record.
        "approver_id": coq["reviewed_by"],
        "batch_id": coq["batch_id"], "cultivar_name": cultivar_name,
        "manufacture_date": coq["manufacture_date"] or primary.get("manufacture_date"),
        # the facility's calendar day of compilation, not the UTC day asyncpg's
        # aware timestamp renders under (review 2026-09-27 QC-21): a CoQ
        # compiled at 23:30 UTC on 31 Dec is numbered in the new facility year
        # and must print that year's date too.
        "report_date": coq["compiled_at"].astimezone(TZ).date() if coq["compiled_at"] else None,
        "botanical_type": primary.get("botanical_type"), "chemotype": primary.get("chemotype"),
        "cultivation_batch": primary.get("cultivation_batch"),
        "product_code": primary.get("product_code") or coq["product_name"],
        "packaging": primary.get("packaging"), "packaging_date": primary.get("packaging_date"),
        "expiry_date": primary.get("expiry_date"), "retest_date": primary.get("retest_date"),
        "source_lab": None,
    }
    results, out_of_scope = [], []
    for ln in lines:
        p = params_by_id.get(str(ln["parameter_id"])) if ln["parameter_id"] else {}
        p = p or {}
        results.append({
            "parameter_id": ln["parameter_id"], "test_name": ln["parameter_name"],
            "result_value": ln["result_value"],
            "result_numeric": float(ln["result_numeric"]) if ln["result_numeric"] is not None else None,
            "unit": ln["unit"],
            "lower_limit": float(p["lower_limit"]) if p.get("lower_limit") is not None else None,
            "upper_limit": float(p["upper_limit"]) if p.get("upper_limit") is not None else None,
            "complies": ln["complies"],
            "source_document_code": ln["source_coa_number"],
            "source_document_date": issue_by_number.get(ln["source_coa_number"]),
            "source_institution": ln["testing_lab"],
        })
        # scope check against THIS line's own source lab (the line records its
        # own test_method; fall back to the spec parameter's method).
        scope = scope_by_source.get(ln["source_coa_id"], set())
        if scope and not _result_in_scope(scope, ln["test_method"] or p.get("test_method"),
                                          ln["parameter_name"]):
            nm = ln["parameter_name"] or "?"
            if nm not in out_of_scope:
                out_of_scope.append(nm)
    # signature block — the CoQ's own two QC signatures (§6.4.3): compiled by /
    # reviewed+approved by HoQC. Names live in the users DB.
    signer_names = {}
    _role_ids = {"analyst": coq["compiled_by"], "reviewer": coq["reviewed_by"]}
    _uids = [str(v) for v in _role_ids.values() if v]
    if _uids:
        prows = await users_admin_pool().fetch(
            # org-scope the BYPASSRLS lookup (see coq_docx): a name from another org
            # must never be resolvable even if a cross-org id slipped in.
            "SELECT id, full_name FROM profiles WHERE id = ANY($1::uuid[]) AND org_id=$2"
            " AND is_deleted=false",
            _uids, user["org_id"])
        _by_id = {str(p["id"]): p["full_name"] for p in prows}
        signer_names = {k: _by_id.get(str(v)) for k, v in _role_ids.items()
                        if v and _by_id.get(str(v))}
    # WHO TRS 1010 / Annex 16 §9.3 mandatory-CONTENT gate (parity with the
    # single-certificate CoQ): never render a certificate missing a required
    # element. cert_type is COQ, so the single-testing-lab element is not
    # required here — the §02 crossref derives each line's lab from its own
    # source certificate instead.
    manifest_missing = _coq_manifest(coa_view, dict(spec) if spec else {},
                                     params_by_id, results, None)
    if manifest_missing:
        raise HTTPException(
            409, "Certificate is missing WHO/Annex-16 mandatory content: "
                 + "; ".join(manifest_missing))
    scope_note = None
    if out_of_scope:
        names = ", ".join(out_of_scope[:5])
        scope_note = (f"Тестови надвор од ISO 17025 опсегот на лабораторијата: {names}"
                      f"|||Tests outside the laboratory's ISO 17025 scope: {names}")
    labs_accredited = None
    if ext_src_ids:
        labs_accredited = (not out_of_scope and all(
            lab_of.get(cid) and accredited_by_lab.get(lab_of[cid]) for cid in ext_src_ids))
    md = _coq_markdown(coa_view, dict(spec) if spec else {}, params_by_id, results,
                       lab=None, scope_note=scope_note, sigs=coq_sigs or None,
                       signer_names=signer_names, potency=potency,
                       labs_accredited=labs_accredited)
    build = (await docengine.de_forward(
        "POST", "/build",
        {"markdown": md, "out_name": coq["coq_number"],
         "meta": {"code": coq["coq_number"], "title_mk": "Сертификат за квалитет",
                  "title_en": "Certificate of Quality", "version": "01"}},
        timeout=120.0, client_factory=_coq_client)).json()
    doc_id = build.get("document_id")
    async with rls(user) as c:
        # Re-assert APPROVED when stamping — the CoQ could have been voided
        # during the (up-to-120s) DocEngine build (TOCTOU).
        stamped = await c.fetchrow(
            "UPDATE qc_coq SET coq_document_id=$1, coq_generated_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 AND status='APPROVED' RETURNING id",
            doc_id, user["id"], coq_id)
        if stamped is None:
            raise HTTPException(409, "CoQ is no longer APPROVED — document not recorded")
        await safe_emit(c, user, verb="coq_rendered", object_type="qc_coq",
                   object_id=coq_id, recipients=[],
                   params={"coq_number": coq["coq_number"], "document_id": doc_id})
    return {"coq_number": coq["coq_number"], "document_id": doc_id,
            "verify": build.get("verify"), "bytes": build.get("bytes"),
            "out_of_scope": out_of_scope}
