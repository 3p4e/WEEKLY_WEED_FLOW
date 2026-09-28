import asyncio

from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from app.security import verify_password
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _COQ_ROLES, _QP_ROLES, _WRITERS, _uuid_or_404, router


_SIG_MEANINGS = ("AUTHORED", "REVIEWED", "APPROVED", "RELEASED", "VERIFIED", "COQ_ISSUED")


# Meanings an aggregation CoQ (qc_coq) may carry — the two QC acts of §6.4.3.
_COQ_SIG_MEANINGS = ("COMPILED", "APPROVED")

# H4 — four of the meanings name a point in the certificate's own lifecycle, so
# they may only be attested once the certificate has actually reached it. A
# "RELEASED" attestation on a DRAFT is a signed claim about something that has
# not happened, which is precisely what an Annex 11 signature must never be.
# Ranked, not equality-matched: signatures are recorded after the fact, so
# signing REVIEWED on an already-APPROVED certificate is legitimate — the review
# did happen. SUPERSEDED/VOIDED certificates have been through the whole
# lifecycle, so they rank at the top and constrain nothing further.
# VERIFIED and COQ_ISSUED are deliberately absent: they attest the eCoA verify
# loop and CoQ issuance, not a qc_certificates status, so they stay unranked.
_MEANING_MIN_RANK = {"AUTHORED": 0, "REVIEWED": 1, "APPROVED": 2, "RELEASED": 3}
_STATUS_RANK = {"DRAFT": 0, "REVIEWED": 1, "APPROVED": 2, "RELEASED": 3,
                "SUPERSEDED": 3, "VOIDED": 3}

# Review 2026-09-27 QC-12 (resolving the 2026-08 audit's open MEDIUM): an
# Annex 11 signature asserts "I, the <role> of record, did this". The signer
# of AUTHORED / REVIEWED / APPROVED must therefore BE the certificate's
# analyst_id / reviewer_id / approver_id — the roles the lifecycle gate in
# certificates.update_coa stamped. Any WRITER used to be able to sign any
# meaning the certificate had reached, and the CoQ printed every signature as
# a role row: an analyst signing "APPROVED" on their own certificate rendered
# as "Одобрил / Approved by: <analyst>". Mismatch is now refused, not merely
# reported. RELEASED is gated to the roles that may release that certificate
# type; COQ_ISSUED to the CoQ-issuing roles (_COQ_ROLES — QP is excluded from
# issuing a CoQ, so a QP's "CoQ issued by" row was a false attestation);
# VERIFIED (the eCoA verify loop) stays open to any writer.
_ROLE_OF_RECORD_COL = {"AUTHORED": "analyst_id", "REVIEWED": "reviewer_id", "APPROVED": "approver_id"}


class SignIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    meaning: str
    statement: str | None = Field(default=None, max_length=500)


def _sig_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "object_type": r["object_type"],
        "object_id": str(r["object_id"]), "signer_id": str(r["signer_id"]),
        "signer_name": r["signer_name"], "signer_role": r["signer_role"],
        "meaning": r["meaning"], "statement": r["statement"],
        "signed_at": r["signed_at"].isoformat() if r["signed_at"] else None,
    }


@router.get("/certificates/{coa_id}/signatures")
async def list_signatures(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
    return [_sig_out(dict(r)) for r in rows]


@router.post("/certificates/{coa_id}/sign", status_code=201)
async def sign_certificate(coa_id: str, body: SignIn,
                           user: dict = Depends(require_role(*_WRITERS))):
    """Apply an Annex 11 electronic signature to a certificate. The signer
    RE-AUTHENTICATES (their account password) at the moment of signing; the
    signature records the name, role, meaning, and time, permanently linked to
    the certificate. Reference/attestation — it does not itself drive the
    lifecycle (the role + second-person gates on the transitions stand) — but
    it is tied to the role of record (see _ROLE_OF_RECORD_COL): the signer of
    a lifecycle meaning must be the person the lifecycle stamped for it."""
    _uuid_or_404(coa_id, "Certificate")
    if body.meaning not in _SIG_MEANINGS:
        raise HTTPException(422, f"meaning must be one of: {', '.join(_SIG_MEANINGS)}")
    prof = await _reauthenticate(user, body.password)
    async with rls(user) as c:
        coa = await c.fetchrow(
            "SELECT id, status, cert_type, analyst_id, reviewer_id, approver_id"
            " FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        # M10: a VOIDED or SUPERSEDED certificate is a closed record — appending a
        # fresh Annex-11 attestation (esp. a RELEASED meaning) to a dead cert is
        # misleading. The rank gate below alone allowed it (SUPERSEDED/VOIDED rank
        # equal to RELEASED), so block terminal states explicitly. Sign the live /
        # superseding certificate instead.
        if coa["status"] in ("VOIDED", "SUPERSEDED"):
            raise HTTPException(
                409, f"Certificate is {coa['status']} — a closed record cannot receive new"
                     " signatures; apply them to the live or superseding certificate.")
        need = _MEANING_MIN_RANK.get(body.meaning)
        if need is not None and _STATUS_RANK.get(coa["status"], 0) < need:
            raise HTTPException(
                409, f"Certificate is {coa['status']} — a '{body.meaning}' signature attests a"
                     " step it has not reached yet (Annex 11 §14: a signature records an act"
                     " that happened)")
        # QC-12: the signer IS the role of record, or the signature is refused.
        role_col = _ROLE_OF_RECORD_COL.get(body.meaning)
        role_of_record_match = None
        if role_col:
            if not coa[role_col]:
                raise HTTPException(
                    409, f"the certificate has no {body.meaning.lower()} role of record yet —"
                         " a signature attests the act of the person the lifecycle recorded")
            role_of_record_match = str(coa[role_col]) == str(user["id"])
            if not role_of_record_match:
                raise HTTPException(
                    403, f"'{body.meaning}' is signed by the certificate's"
                         f" {role_col.replace('_id', '')} of record, not by another writer"
                         " (Annex 11 §14: a signature asserts the signer's own act)")
        elif body.meaning == "RELEASED":
            # release authority is cert-type-aware, as in certificates.update_coa
            allowed = (("ADMIN", "QC_MGR") if coa["cert_type"] == "ICOA"
                       else _COQ_ROLES if coa["cert_type"] == "COQ" else _QP_ROLES)
            if user["role"] not in allowed:
                raise HTTPException(
                    403, f"'RELEASED' on a {coa['cert_type']} certificate is signed by the role"
                         " that releases it")
        elif body.meaning == "COQ_ISSUED" and user["role"] not in _COQ_ROLES:
            raise HTTPException(
                403, "'COQ_ISSUED' is signed by the QC roles that issue a Certificate of Quality"
                     " — the Qualified Person receives the CoQ and does not issue it")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_signatures(org_id, object_type, object_id, signer_id, signer_name,"
                " signer_role, meaning, statement) VALUES ($1,'qc_certificate',$2,$3,$4,$5,$6,$7)"
                " RETURNING *",
                user["org_id"], coa_id, user["id"],
                prof["full_name"] or user.get("username") or "—", user["role"], body.meaning,
                body.statement)
        except Exception as e:
            # 0060: the same person signing the same meaning on the same record
            # twice asserts nothing new — refuse rather than duplicate.
            if "qc_signatures_unique_meaning_idx" in str(e):
                raise HTTPException(
                    409, f"You have already signed '{body.meaning}' on this certificate")
            raise
        await safe_emit(c, user, verb="coa_signed", object_type="qc_certificate",
                   object_id=coa_id, recipients=[],
                   params={"meaning": body.meaning, "role_of_record_match": role_of_record_match})
    out = _sig_out(dict(row))
    out["role_of_record_match"] = role_of_record_match
    return out


async def _reauthenticate(user: dict, password: str):
    """Annex 11 §14 — the signer re-enters their own account password at the
    moment of signing. The profile (and its hash) lives in the users DB."""
    prof = await users_admin_pool().fetchrow(
        "SELECT full_name, password_hash FROM profiles WHERE id=$1 AND org_id=$2"
        " AND is_deleted=false", user["id"], user["org_id"])
    if prof is None or not await asyncio.to_thread(verify_password, password, prof["password_hash"]):
        raise HTTPException(401, "Signature not applied — re-authentication failed")
    return prof


@router.get("/coq/{coq_id}/signatures")
async def list_coq_signatures(coq_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_coq' AND object_id=$1"
            " ORDER BY signed_at", coq_id)
    return [_sig_out(dict(r)) for r in rows]


@router.post("/coq/{coq_id}/sign", status_code=201)
async def sign_coq(coq_id: str, body: SignIn, user: dict = Depends(require_role(*_WRITERS))):
    """Annex 11 e-signature on the SOP-path aggregation CoQ (review 2026-09-27
    QC-12: the record the QP actually receives could never carry one, so the
    printed CoQ always read "this document carries no electronic signature").
    Two meanings, tied to the two roles of record of §6.4.3: COMPILED by the
    compiler (compiled_by), APPROVED by the Head of QC who reviewed it
    (reviewed_by, once APPROVED). render_coq prints these."""
    _uuid_or_404(coq_id, "CoQ")
    if body.meaning not in _COQ_SIG_MEANINGS:
        raise HTTPException(422, f"meaning must be one of: {', '.join(_COQ_SIG_MEANINGS)}")
    prof = await _reauthenticate(user, body.password)
    async with rls(user) as c:
        coq = await c.fetchrow(
            "SELECT id, status, compiled_by, reviewed_by FROM qc_coq WHERE id=$1", coq_id)
        if coq is None:
            raise HTTPException(404, "CoQ not found")
        if coq["status"] == "VOIDED":
            raise HTTPException(409, "the CoQ is VOIDED — a closed record cannot receive new signatures")
        if body.meaning == "APPROVED" and coq["status"] != "APPROVED":
            raise HTTPException(
                409, f"CoQ is {coq['status']} — an 'APPROVED' signature attests a step it has"
                     " not reached yet (Annex 11 §14: a signature records an act that happened)")
        role_col = "compiled_by" if body.meaning == "COMPILED" else "reviewed_by"
        if not coq[role_col] or str(coq[role_col]) != str(user["id"]):
            raise HTTPException(
                403, f"'{body.meaning}' is signed by the CoQ's {role_col.replace('_by', 'r')}"
                     " of record (§6.4.3), not by another writer")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_signatures(org_id, object_type, object_id, signer_id, signer_name,"
                " signer_role, meaning, statement) VALUES ($1,'qc_coq',$2,$3,$4,$5,$6,$7)"
                " RETURNING *",
                user["org_id"], coq_id, user["id"],
                prof["full_name"] or user.get("username") or "—", user["role"], body.meaning,
                body.statement)
        except Exception as e:
            if "qc_signatures_unique_meaning_idx" in str(e):
                raise HTTPException(409, f"You have already signed '{body.meaning}' on this CoQ")
            raise
        await safe_emit(c, user, verb="coq_signed", object_type="qc_coq",
                   object_id=coq_id, recipients=[], params={"meaning": body.meaning})
    return _sig_out(dict(row))
