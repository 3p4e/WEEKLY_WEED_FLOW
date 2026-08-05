from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import (_HOQC, _QP_ROLES, _WRITERS, _evaluate, _lab_verdict_bool, _uuid_or_404,
                     _uuid_or_422, router, splice_stamps)
from .laboratories import _lab_out, _lab_scope_set, _resolve_lab, _result_in_scope
from .signatures import _sig_out


_COA_STATUSES = ("DRAFT", "REVIEWED", "APPROVED", "RELEASED", "SUPERSEDED", "VOIDED")


_CERT_TYPES = ("ICOA", "ECOA", "COQ", "WATER", "OTHER")


_CERT_PREFIX = {"ICOA": "iCoA-PP", "ECOA": "eCoA-PP", "COQ": "CoQ-PP",
                "WATER": "WCoA-PP", "OTHER": "CoA-PP"}


async def _mint_cert_number(c, org_id: str, cert_type: str) -> str:
    """Advisory-locked per-(org, cert_type, year) sequential number, reset to
    0001 each 1 January — gap-free within the lock, never reused/reassigned.
    Forward-only: pre-existing 'PP-COA-YYYY-NNNN' numbers (minted before this
    format existed) are immutable and untouched; only newly issued certificates
    mint under the new per-type prefix, so the two formats coexist in the
    register by design."""
    prefix = _CERT_PREFIX.get(cert_type, "CoA-PP")
    yr = await c.fetchval("SELECT to_char(now(),'YYYY')")
    await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"certnum:{org_id}:{cert_type}:{yr}")
    seq = await c.fetchval(
        "SELECT coalesce(max((regexp_match(coa_number, '-([0-9]+)$'))[1]::int), 0) + 1"
        " FROM qc_certificates WHERE org_id=$1 AND cert_type=$2"
        " AND coa_number LIKE $3 || '-' || $4 || '-%'",
        org_id, cert_type, prefix, yr)
    if cert_type == "COQ":
        # The CoQ-PP register series is SHARED with the per-batch aggregation
        # records (qc_coq) — §6.13 defines ONE CoQ number series, whichever
        # surface minted it. Both minting paths take the same advisory lock
        # above, so the two maxes cannot race each other.
        agg = await c.fetchval(
            "SELECT coalesce(max((regexp_match(coq_number, '-([0-9]+)$'))[1]::int), 0) + 1"
            " FROM qc_coq WHERE org_id=$1 AND coq_number LIKE $2 || '-' || $3 || '-%'",
            org_id, prefix, yr)
        seq = max(seq, agg)
    return f"{prefix}-{yr}-{seq:04d}"


_VOIDABLE = {"DRAFT", "REVIEWED", "APPROVED", "RELEASED"}


_SOP_STATUS = {"DRAFT": "Draft", "REVIEWED": "Under Review", "APPROVED": "Approved",
               "RELEASED": "Issued", "SUPERSEDED": "Superseded", "VOIDED": "Voided"}


def _coa_sop_status(status, supersedes_id) -> str:
    if status == "RELEASED" and supersedes_id:
        return "Revised"
    return _SOP_STATUS.get(status, status)


_COA_TRANSITIONS = {
    "DRAFT": {"REVIEWED"},
    "REVIEWED": {"APPROVED", "DRAFT"},   # kick back to DRAFT on review findings
    "APPROVED": {"RELEASED"},
    "RELEASED": set(),
    # Terminal. Reached ONLY via the revise flow (releasing a revision flips
    # its origin RELEASED→SUPERSEDED); never a direct PATCH target.
    "SUPERSEDED": set(),
}


_COA_QP_TARGETS = {"APPROVED", "RELEASED"}


_QUARANTINABLE = {"IN_TEST", "TESTED", "RECEIVED", "COLLECTED"}


class CoaIn(BaseModel):
    batch_id: str = Field(max_length=120)
    specification_id: str
    sample_id: str | None = None
    cert_type: str = "ICOA"
    report_date: date | None = None
    source_lab: str | None = Field(default=None, max_length=200)
    # The accredited laboratory that issued the source data (URS Chapter 7);
    # the structured replacement for the free-text source_lab, kept alongside it.
    laboratory_id: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CoaPatch(BaseModel):
    source_lab: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    report_date: date | None = None
    # QCLB 020 §6.13 register fields — where the original is filed + the
    # retention window. Nullable; never back-filled with an invented value.
    retention_start: date | None = None
    retention_expiry: date | None = None
    archive_ref: str | None = Field(default=None, max_length=300)
    # CoQ house-template metadata (CoQ_Template_v02_VariationF meta grid). All
    # nullable — the CoQ renderer surfaces each when present, omits it when not;
    # GxP: an unknown value stays blank for a human, never fabricated.
    cultivation_batch: str | None = Field(default=None, max_length=120)
    product_code: str | None = Field(default=None, max_length=120)
    packaging: str | None = Field(default=None, max_length=200)
    packaging_date: date | None = None
    manufacture_date: date | None = None
    expiry_date: date | None = None
    retest_date: date | None = None
    botanical_type: str | None = Field(default=None, max_length=120)
    chemotype: str | None = Field(default=None, max_length=120)
    # QCSOP 012 §6.2.2 (C6) — the SOP wants an analysis date RANGE plus the
    # sampling location echoed onto the certificate itself.
    analysis_start_date: date | None = None
    analysis_end_date: date | None = None
    sampling_location: str | None = Field(default=None, max_length=300)
    # §6.7 (C7) — issue language: EN is the SOP's primary controlled language;
    # EN-MK bilingual on demand (the renderer's current default).
    issue_language: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = None            # guarded lifecycle transition
    decision: str | None = None          # PASS | FAIL


class ResultIn(BaseModel):
    parameter_id: str | None = None
    test_name: str = Field(max_length=300)
    result_value: str | None = Field(default=None, max_length=200)
    result_numeric: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    lower_limit: float | None = None
    upper_limit: float | None = None
    result_date: date | None = None
    # provenance — the source iCoA/eCoA this result was transcribed from; the
    # COQ maps every line back to its source document (unknown stays blank).
    source_document_code: str | None = Field(default=None, max_length=120)
    source_document_date: date | None = None
    source_institution: str | None = Field(default=None, max_length=200)
    # The lab's OWN stated pass/fail as printed on the source certificate —
    # captured verbatim for the reconciliation record, reference-only. Purely
    # Plant's in-house `complies` is the determination; this never feeds it
    # (QCSOP 012 §6.3.2). A disagreement is surfaced, never silently discarded.
    lab_verdict: str | None = Field(default=None, max_length=60)


def _coa_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_number": r["coa_number"], "batch_id": r["batch_id"],
        "specification_id": str(r["specification_id"]),
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "report_date": r["report_date"].isoformat() if r["report_date"] else None,
        "status": r["status"], "decision": r["decision"], "cert_type": r["cert_type"],
        "source_lab": r["source_lab"],
        "laboratory_id": str(r["laboratory_id"]) if r.get("laboratory_id") else None,
        "analyst_id": str(r["analyst_id"]) if r["analyst_id"] else None,
        "reviewer_id": str(r["reviewer_id"]) if r["reviewer_id"] else None,
        "approver_id": str(r["approver_id"]) if r["approver_id"] else None,
        "coq_document_id": r["coq_document_id"],
        "coq_generated_at": r["coq_generated_at"].isoformat() if r["coq_generated_at"] else None,
        "supersedes_id": str(r["supersedes_id"]) if r.get("supersedes_id") else None,
        "revision_reason": r.get("revision_reason"),
        "retention_start": r["retention_start"].isoformat() if r.get("retention_start") else None,
        "retention_expiry": r["retention_expiry"].isoformat() if r.get("retention_expiry") else None,
        "archive_ref": r.get("archive_ref"),
        # CoQ house-template metadata (mig 0038) — surfaced on the certificate
        # record and the rendered Certificate of Quality.
        "cultivation_batch": r.get("cultivation_batch"),
        "product_code": r.get("product_code"),
        "packaging": r.get("packaging"),
        "packaging_date": r["packaging_date"].isoformat() if r.get("packaging_date") else None,
        "manufacture_date": r["manufacture_date"].isoformat() if r.get("manufacture_date") else None,
        "expiry_date": r["expiry_date"].isoformat() if r.get("expiry_date") else None,
        "retest_date": r["retest_date"].isoformat() if r.get("retest_date") else None,
        "botanical_type": r.get("botanical_type"),
        "chemotype": r.get("chemotype"),
        # §6.2.2 analysis range + sampling location (C6)
        "analysis_start_date": r["analysis_start_date"].isoformat() if r.get("analysis_start_date") else None,
        "analysis_end_date": r["analysis_end_date"].isoformat() if r.get("analysis_end_date") else None,
        "sampling_location": r.get("sampling_location"),
        # §6.7 language + translation verification (C7)
        "issue_language": r.get("issue_language"),
        "translation_verified_by": str(r["translation_verified_by"]) if r.get("translation_verified_by") else None,
        "translation_verified_at": r["translation_verified_at"].isoformat() if r.get("translation_verified_at") else None,
        # §6.13 Certificate Issuance Register status label
        "sop_status": _coa_sop_status(r["status"], r.get("supersedes_id")),
        # §6.6 void disposition
        "void_reason": r.get("void_reason"),
        "voided_by": str(r["voided_by"]) if r.get("voided_by") else None,
        "voided_at": r["voided_at"].isoformat() if r.get("voided_at") else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


def _result_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "test_name": r["test_name"], "result_value": r["result_value"],
        "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
        "unit": r["unit"],
        "lower_limit": float(r["lower_limit"]) if r["lower_limit"] is not None else None,
        "upper_limit": float(r["upper_limit"]) if r["upper_limit"] is not None else None,
        "complies": r["complies"], "status": r["status"],
        "analyst_id": str(r["analyst_id"]) if r["analyst_id"] else None,
        "result_date": r["result_date"].isoformat() if r["result_date"] else None,
        "source_document_code": r["source_document_code"],
        "source_document_date":
            r["source_document_date"].isoformat() if r["source_document_date"] else None,
        "source_institution": r["source_institution"],
        # Lab's stated verdict (reference) + the reconciliation flag: True only
        # when the lab's own pass/fail disagrees with our determination — a
        # signal for the reviewer, never a change to `complies`.
        "lab_verdict": r.get("lab_verdict"),
        "lab_verdict_mismatch": (
            _lab_verdict_bool(r.get("lab_verdict")) is not None and r["complies"] is not None
            and _lab_verdict_bool(r.get("lab_verdict")) != r["complies"]),
    }


@router.get("/certificates")
async def list_coas(batch_id: str | None = None, status: str | None = None,
                    user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_certificates{where} ORDER BY created_at DESC", *args)
    return [_coa_out(dict(r)) for r in rows]


@router.get("/certificates/{coa_id}")
async def get_coa(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1",
                               coa["laboratory_id"]) if coa["laboratory_id"] else None
        sigs = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
        # method per cited spec parameter, for the scope check below
        pmethods = {}
        pids = [r["parameter_id"] for r in results if r["parameter_id"]]
        if pids:
            prows = await c.fetch(
                "SELECT id, test_method FROM qc_spec_parameters WHERE id = ANY($1::uuid[])", pids)
            pmethods = {str(p["id"]): p["test_method"] for p in prows}
    # ISO 17025 scope flag: when the issuing lab declares an accredited scope,
    # mark each result whose method/test is not accredited (advisory, per URS
    # Chapter 7 — surfaced for the reviewer, never an automatic OOS).
    scope = _lab_scope_set(lab["iso17025_scope"]) if lab else set()
    out_results = []
    for r in results:
        d = _result_out(dict(r))
        method = pmethods.get(str(r["parameter_id"])) if r["parameter_id"] else None
        d["in_scope"] = _result_in_scope(scope, method, r["test_name"]) if scope else None
        out_results.append(d)
    # §6.2.1 (C6) — same-day drafting timeliness, computed from REAL timestamps
    # only (never fabricated): the date the last result became available (max
    # result_date) vs the calendar date the last result row was entered on the
    # certificate. Named honestly: this is a calendar-day comparison, not a
    # working-day calendar. Unknown (no dated results) stays null.
    drafted_same_day = None
    dated = [r for r in results if r["result_date"]]
    if dated:
        last_available = max(r["result_date"] for r in dated)
        last_entered = max(r["created_at"] for r in results).date()
        drafted_same_day = last_entered <= last_available
    return {"coa": _coa_out(dict(coa)),
            "laboratory": _lab_out(dict(lab)) if lab else None,
            "results": out_results,
            "drafted_same_day": drafted_same_day,
            "signatures": [_sig_out(dict(s)) for s in sigs]}


@router.post("/certificates", status_code=201)
async def create_coa(body: CoaIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.sample_id, "sample_id")
    _uuid_or_422(body.laboratory_id, "laboratory_id")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id)
        if spec is None:
            raise HTTPException(422, "Unknown specification")
        if body.sample_id:
            s = await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id)
            if s is None:
                raise HTTPException(422, "Unknown sample")
        await _resolve_lab(c, user["org_id"], body.laboratory_id)
        coa_number = await _mint_cert_number(c, user["org_id"], body.cert_type)
        row = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
            " cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8,$9,$10,$11,$11,$11) RETURNING *",
            user["org_id"], coa_number, body.batch_id, body.specification_id, body.sample_id,
            body.cert_type, body.report_date, body.source_lab, body.laboratory_id,
            body.notes, user["id"])
    return _coa_out(dict(row))


@router.post("/certificates/{coa_id}/results", status_code=201)
async def add_result(coa_id: str, body: ResultIn, user: dict = Depends(require_role(*_WRITERS))):
    """Record a measured result. `complies` is computed from the numeric value
    vs the limits — never typed by hand. If the result FAILS and the CoA links
    a sample that is still in a testable state, the sample is quarantined (the
    OOS hook). Results may only be entered while the CoA is DRAFT."""
    _uuid_or_404(coa_id, "Certificate")
    _uuid_or_422(body.parameter_id, "parameter_id")
    # H3 — an acceptance criterion must come from an APPROVED specification.
    # Without a cited parameter these limits are whatever the caller typed, yet
    # _evaluate grades against them and the result renders as a §01 Analytical
    # Results row on the issued CoQ (coq_docx._coq_markdown iterates EVERY
    # result and prints r.lower_limit/r.upper_limit in the Acceptance column) —
    # certified conformance against a criterion no specification backs.
    # Refused explicitly rather than silently dropped, so the operator is told
    # to cite the spec parameter instead of losing the limits they entered.
    if not body.parameter_id and (body.lower_limit is not None or body.upper_limit is not None):
        raise HTTPException(
            422, "Acceptance limits require a parameter_id — a certified criterion must come"
                 " from the approved specification, not from the request. Cite the spec"
                 " parameter, or record the value without limits as reference data.")
    async with rls(user) as c:
        coa = await c.fetchrow(
            "SELECT id, status, sample_id, specification_id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "DRAFT":
            raise HTTPException(409, "Results may only be entered while the CoA is DRAFT")
        lo, hi = body.lower_limit, body.upper_limit
        # A cited spec parameter must exist and belong to THIS certificate's
        # specification (an unknown or cross-spec/cross-org id must 422, never a
        # dangling FK / 500). When cited and limits weren't supplied, snapshot the
        # parameter's limits (the spec is the single source of truth).
        if body.parameter_id:
            p = await c.fetchrow(
                "SELECT spec_id, lower_limit, upper_limit, unit, computed_kind"
                " FROM qc_spec_parameters WHERE id=$1",
                body.parameter_id)
            if p is None:
                raise HTTPException(422, "Unknown spec parameter")
            if coa["specification_id"] is not None and p["spec_id"] != coa["specification_id"]:
                raise HTTPException(422, "Parameter does not belong to this certificate's specification")
            # Ph. Eur. 3028: a derived total is COMPUTED by the engine at COQ
            # time from its component results — transcribing one is forbidden.
            if p["computed_kind"] is not None:
                raise HTTPException(422, "This parameter is computed (Ph. Eur. 3028 derived total)"
                                         " — enter its component results instead")
            # H1 (§6.3.2): the acceptance criterion is the APPROVED specification's,
            # never the request's. Earlier this only FILLED a null side from the
            # spec — a side the caller *supplied* was kept verbatim, so a bogus
            # `upper_limit` (or a limit on a side the spec leaves open) graded the
            # value against a criterion no spec backs (a fabricated conformance).
            # Now: a supplied bound must MATCH the spec parameter's (within float
            # tolerance) or it is refused; an omitted side inherits the spec's; and
            # the stored lo/hi are ALWAYS the spec's authoritative bounds. (The
            # normal UI never sends limits with a parameter_id — it cites the param
            # and lets the server snapshot — so only a programmatic caller can trip
            # this, which is exactly the path that must not override the spec.)
            spec_lo = float(p["lower_limit"]) if p["lower_limit"] is not None else None
            spec_hi = float(p["upper_limit"]) if p["upper_limit"] is not None else None
            if lo is not None and (spec_lo is None or abs(lo - spec_lo) > 1e-9):
                raise HTTPException(
                    422, "lower_limit does not match the cited spec parameter"
                         f" (spec: {spec_lo}) — the acceptance criterion comes from the"
                         " specification; omit it to use the spec's bound.")
            if hi is not None and (spec_hi is None or abs(hi - spec_hi) > 1e-9):
                raise HTTPException(
                    422, "upper_limit does not match the cited spec parameter"
                         f" (spec: {spec_hi}) — the acceptance criterion comes from the"
                         " specification; omit it to use the spec's bound.")
            lo, hi = spec_lo, spec_hi
        complies, status = _evaluate(body.result_numeric, lo, hi)
        row = await c.fetchrow(
            "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
            " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
            " result_date, source_document_code, source_document_date, source_institution,"
            " lab_verdict, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$12) RETURNING *",
            user["org_id"], coa_id, body.parameter_id, body.test_name, body.result_value,
            body.result_numeric, body.unit, lo, hi, complies, status, user["id"], body.result_date,
            body.source_document_code, body.source_document_date, body.source_institution,
            body.lab_verdict)
        # OOS hook: a failing result quarantines the linked sample.
        if complies is False and coa["sample_id"]:
            smp = await c.fetchrow("SELECT id, status FROM qc_samples WHERE id=$1", coa["sample_id"])
            if smp is not None and smp["status"] in _QUARANTINABLE:
                await c.execute(
                    "UPDATE qc_samples SET status='QUARANTINE', updated_by=$1, updated_at=now() WHERE id=$2",
                    user["id"], coa["sample_id"])
                await safe_emit(c, user, verb="sample_quarantined", object_type="qc_sample",
                           object_id=coa["sample_id"], recipients=[],
                           params={"test_name": body.test_name})
    return _result_out(dict(row))


_REGISTER_ONLY = {"retention_start", "retention_expiry", "archive_ref"}


# The CoQ-template metadata fields (cultivation_batch, product_code,
# packaging[_date], manufacture_date, expiry_date, retest_date,
# botanical_type, chemotype — see coq_docx.py) are what's literally printed
# on the issued CoQ, so they get the same set-once treatment as every other
# analytical field on an issued cert (back-fill from blank is an audited
# correction; changing an already-set value requires a revision) — NOT
# unconditional editability (H4).
_ISSUED_EDITABLE = _REGISTER_ONLY


_ARCHIVED_STATUSES = ("VOIDED", "SUPERSEDED")


_ISSUED_FROZEN = ("APPROVED", "RELEASED")


_FROZEN_STATUSES = _ARCHIVED_STATUSES + _ISSUED_FROZEN


def _frozen_content_edit(patch: dict, cur: dict) -> bool:
    """True when `patch` would change the immutable analytical record of a
    frozen (issued/archived) certificate. Rules:
      • register + CoQ-template fields are always editable (issued certs);
      • a status change is allowed only on an ISSUED cert (legality enforced by
        the transition map) — never on an archived one;
      • analytical fields (decision, dates, sampling location, lab, language,
        notes) are SET-ONCE on an issued cert: back-filling a currently-blank
        mandatory value is an audited correction, but changing a value already
        of record — or clearing one — requires a revision (§6.7). An archived
        (VOIDED/SUPERSEDED) cert freezes everything but the register fields."""
    status = cur["status"]
    issued = status in _ISSUED_FROZEN
    allowed = _ISSUED_EDITABLE if issued else _REGISTER_ONLY
    for k, v in patch.items():
        if k in allowed:
            continue
        if k == "status":
            if v == status:
                continue                       # same-value echo
            if issued:
                continue                       # a real transition attempt on an issued cert
            return True                        # status move on an archived cert
        if issued and cur.get(k) in (None, "") and v not in (None, ""):
            continue                           # set-once: back-fill a blank analytical field
        return True                            # change/clear of a recorded value, or archived edit
    return False


@router.patch("/certificates/{coa_id}")
async def update_coa(coa_id: str, body: CoaPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(coa_id, "Certificate")
    patch = body.model_dump(exclude_unset=True)
    if "decision" in patch and patch["decision"] is not None and patch["decision"] not in ("PASS", "FAIL"):
        raise HTTPException(422, "decision must be PASS or FAIL")
    if patch.get("issue_language") is not None and patch["issue_language"] not in ("EN", "EN-MK"):
        raise HTTPException(422, "issue_language must be EN or EN-MK (§6.7)")
    if patch.get("laboratory_id") is not None:
        _uuid_or_422(patch["laboratory_id"], "laboratory_id")
    frozen_status = None
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        # §6.6/§6.7 — an issued (APPROVED/RELEASED) or archived (VOIDED/SUPERSEDED)
        # certificate is immutable: a substantive content edit is refused (a
        # correction is a NEW certificate via /revise). Register fields + a legal
        # status transition (issued certs only) remain permitted.
        if cur["status"] in _FROZEN_STATUSES and _frozen_content_edit(patch, dict(cur)):
            frozen_status = cur["status"]
    if frozen_status:
        # §6.16 (C8) — an attempted edit of a frozen certificate is itself a
        # reportable deviation (QASOP 010), not just a rejected request. Recorded
        # in a fresh transaction: the 409 must not roll the event back.
        archived = frozen_status in _ARCHIVED_STATUSES
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_certificate",
                       object_id=coa_id, recipients=[],
                       params={"reason": "edit_archived_certificate" if archived
                                         else "edit_issued_certificate",
                               "status": frozen_status, "sop": "QCSOP 012 §6.16"})
        noun = "archived" if archived else "issued"
        raise HTTPException(409, f"a {frozen_status} certificate is {noun} and immutable —"
                                 " correct it with a revision (/revise); only the retention/"
                                 "archive register fields may be updated in place"
                                 " (attempt recorded as a deviation, §6.16)")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        # TOCTOU guard: the certificate can become frozen (approved/released/
        # voided/superseded) between the check above and this transaction — the
        # same freeze must hold here or a racing edit lands on an immutable record.
        if cur["status"] in _FROZEN_STATUSES and _frozen_content_edit(patch, dict(cur)):
            raise HTTPException(409, f"a {cur['status']} certificate is immutable —"
                                     " correct it with a revision; only register fields update in place")
        if patch.get("laboratory_id") is not None:
            await _resolve_lab(c, user["org_id"], patch["laboratory_id"])
        extra_sql, extra_args = [], []
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _COA_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target == "SUPERSEDED":
                # only the revise flow retires a certificate (QCSOP 012 §6.7)
                raise HTTPException(409, "SUPERSEDED is set by releasing a revision, not directly")
            if target not in _COA_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            if target in _COA_QP_TARGETS and user["role"] not in _QP_ROLES:
                raise HTTPException(403, f"{target} is a Qualified-Person decision")
            # A certificate cannot be APPROVED or RELEASED without a recorded
            # PASS/FAIL disposition — approval attests a decision, and there is
            # none to attest until one is on record. The effective disposition is
            # the one this patch sets, else the value already of record.
            if target in _COA_QP_TARGETS:
                eff_decision = patch["decision"] if "decision" in patch else cur["decision"]
                if eff_decision not in ("PASS", "FAIL"):
                    raise HTTPException(
                        409, f"record a PASS or FAIL disposition before {target.lower()}"
                             " — a certificate's approval attests its disposition of record")
            # GxP second-person review: the reviewer must not be anyone who
            # produced the data — neither the CoA's analyst-of-record NOR any
            # analyst who entered a result on it (each qc_results row stamps its
            # own analyst_id, so checking only the certificate's would let a
            # second data-enterer sign off their own measurements).
            if target == "REVIEWED":
                entered = await c.fetchval(
                    "SELECT 1 FROM qc_results WHERE coa_id=$1 AND analyst_id=$2 LIMIT 1",
                    coa_id, user["id"])
                if entered or (cur["analyst_id"] and str(cur["analyst_id"]) == str(user["id"])):
                    raise HTTPException(403, "The reviewer must be a different person than the analyst")
                extra_args.append(user["id"]); extra_sql.append(f"reviewer_id=${'PLACEHOLDER'}")
            if target == "APPROVED":
                # Same second-person principle as REVIEWED: the approver must
                # not be anyone who produced the data. (Reviewer == approver
                # is NOT restricted here — this codebase's established model
                # is a single QP walking a cert through REVIEWED->APPROVED->
                # RELEASED, exercised throughout the existing test suite; only
                # analyst self-approval was the confirmed gap.)
                entered = await c.fetchval(
                    "SELECT 1 FROM qc_results WHERE coa_id=$1 AND analyst_id=$2 LIMIT 1",
                    coa_id, user["id"])
                if entered or (cur["analyst_id"] and str(cur["analyst_id"]) == str(user["id"])):
                    raise HTTPException(403, "The approver must be a different person than the analyst")
                extra_args.append(user["id"]); extra_sql.append(f"approver_id=${'PLACEHOLDER'}")
        fields, args = [], []
        _NULLABLE = {"source_lab", "laboratory_id", "report_date", "retention_start",
                     "retention_expiry", "archive_ref", "notes", "decision",
                     "cultivation_batch", "product_code", "packaging", "packaging_date",
                     "manufacture_date", "expiry_date", "retest_date",
                     "botanical_type", "chemotype",
                     "analysis_start_date", "analysis_end_date", "sampling_location"}
        _DATE_COLS = {"report_date", "retention_start", "retention_expiry",
                      "packaging_date", "manufacture_date", "expiry_date", "retest_date",
                      "analysis_start_date", "analysis_end_date"}
        content_changed = False
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col not in ("retention_start", "retention_expiry", "archive_ref", "status"):
                content_changed = True
            if col in _DATE_COLS:
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            else:
                args.append(val); fields.append(f"{col}=${len(args)}")
        # §6.7 (C7) — a content edit (including a language switch) invalidates
        # any earlier translation verification: the stamp attests THIS text,
        # not some prior revision of it. Status transitions and the register
        # fields don't touch content and keep the stamp.
        if content_changed:
            fields.append("translation_verified_by=NULL")
            fields.append("translation_verified_at=NULL")
        # splice reviewer_id/approver_id stamps with correct positional params
        splice_stamps(fields, args, extra_sql, extra_args)
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(coa_id)
        row = await c.fetchrow(
            f"UPDATE qc_certificates SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
        # Releasing a revision retires its origin: RELEASED → SUPERSEDED in the
        # same transaction, so the register never shows two live certificates
        # for the same correction chain (QCSOP 012 §6.7). Status-guarded so a
        # replayed release can't touch an already-superseded origin.
        if patch.get("status") == "RELEASED" and cur["supersedes_id"]:
            await c.execute(
                "UPDATE qc_certificates SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
                " WHERE id=$2 AND status='RELEASED'", user["id"], cur["supersedes_id"])
    return _coa_out(dict(row))


class ReviseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/certificates/{coa_id}/revise", status_code=201)
async def revise_certificate(coa_id: str, body: ReviseIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """QCSOP 012 §6.7: an approved certificate is immutable — a correction is a
    NEW certificate with a NEW number, carrying "Supersedes [n] — reason".
    The revision starts as a DRAFT copy (results AND the PASS/FAIL disposition
    included, so the compiler corrects from the current state — and no revision
    can reach APPROVED without a disposition of record, §M3); the original stays
    RELEASED until the revision is itself RELEASED, at which point it flips to
    SUPERSEDED."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        if cur["status"] != "RELEASED":
            raise HTTPException(409, f"Only a RELEASED certificate is revised — this one is"
                                     f" {cur['status']} (edit or re-review it directly)")
        open_rev = await c.fetchval(
            "SELECT coa_number FROM qc_certificates WHERE supersedes_id=$1"
            " AND status <> 'SUPERSEDED' LIMIT 1", coa_id)
        if open_rev:
            raise HTTPException(409, f"A revision already exists ({open_rev})")
        coa_number = await _mint_cert_number(c, user["org_id"], cur["cert_type"])
        row = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id,"
            " sample_id, cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " supersedes_id, revision_reason, decision, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$11,$11) RETURNING *",
            user["org_id"], coa_number, cur["batch_id"], cur["specification_id"], cur["sample_id"],
            cur["cert_type"], cur["report_date"], cur["source_lab"], cur["laboratory_id"],
            cur["notes"], user["id"], coa_id, body.reason, cur["decision"])
        # carry the result set forward so the correction edits the real state
        await c.execute(
            "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
            " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
            " result_date, source_document_code, source_document_date, source_institution,"
            " lab_verdict, created_by)"
            " SELECT org_id, $1, parameter_id, test_name, result_value, result_numeric,"
            " unit, lower_limit, upper_limit, complies, status, analyst_id, result_date,"
            " source_document_code, source_document_date, source_institution, lab_verdict, $2"
            " FROM qc_results WHERE coa_id=$3", row["id"], user["id"], coa_id)
    return _coa_out(dict(row))


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/certificates/{coa_id}/void")
async def void_certificate(coa_id: str, body: VoidIn,
                           user: dict = Depends(require_role(*_HOQC))):
    """QCSOP 012 §6.6 — void a fundamentally-invalid certificate (e.g. wrong
    batch identified, wrong sample tested). Authorised by the Head of QC in
    writing (a reason is mandatory). The original record is NOT deleted — it is
    retained, archived, with the voiding decision (GxP: issued records are
    immutable). An already-superseded or already-voided certificate cannot be
    voided; use revise for a correction to a valid certificate."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        if cur["status"] not in _VOIDABLE:
            raise HTTPException(409, f"a {cur['status']} certificate cannot be voided")
        row = await c.fetchrow(
            "UPDATE qc_certificates SET status='VOIDED', void_reason=$1, voided_by=$2,"
            " voided_at=now(), updated_by=$2, updated_at=now() WHERE id=$3 RETURNING *",
            body.reason.strip(), user["id"], coa_id)
    return _coa_out(dict(row))


@router.post("/certificates/{coa_id}/translation-verified")
async def verify_translation(coa_id: str, user: dict = Depends(require_role(*_WRITERS))):
    """QCSOP 012 §6.7 (C7) — record that the bilingual (EN-MK) issue's translation
    was verified against the English source by a SECOND qualified reviewer. The
    verifier must not be the certificate's analyst-of-record (second person), and
    the capture only applies to a bilingual issue."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, analyst_id, issue_language FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        if cur["status"] in ("VOIDED", "SUPERSEDED"):
            raise HTTPException(409, f"a {cur['status']} certificate is archived — nothing to verify")
        if cur["issue_language"] != "EN-MK":
            raise HTTPException(409, "translation verification applies to a bilingual (EN-MK) issue")
        if cur["analyst_id"] and str(cur["analyst_id"]) == str(user["id"]):
            raise HTTPException(403, "the translation is verified by a second qualified reviewer (§6.7)")
        row = await c.fetchrow(
            "UPDATE qc_certificates SET translation_verified_by=$1, translation_verified_at=now(),"
            " updated_by=$1, updated_at=now() WHERE id=$2 RETURNING *", user["id"], coa_id)
    return _coa_out(dict(row))
