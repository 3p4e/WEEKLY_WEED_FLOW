from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from app.security import verify_password
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _WRITERS, _uuid_or_404, router


_SIG_MEANINGS = ("AUTHORED", "REVIEWED", "APPROVED", "RELEASED", "VERIFIED", "COQ_ISSUED")


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
    lifecycle (the role + second-person gates on the transitions stand)."""
    _uuid_or_404(coa_id, "Certificate")
    if body.meaning not in _SIG_MEANINGS:
        raise HTTPException(422, f"meaning must be one of: {', '.join(_SIG_MEANINGS)}")
    # Re-authenticate against the signer's own account (Annex 11 §14) — the
    # profile (and its password hash) lives in the separate users DB.
    prof = await users_admin_pool().fetchrow(
        "SELECT full_name, password_hash FROM profiles WHERE id=$1 AND is_deleted=false", user["id"])
    if prof is None or not verify_password(body.password, prof["password_hash"]):
        raise HTTPException(401, "Signature not applied — re-authentication failed")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        row = await c.fetchrow(
            "INSERT INTO qc_signatures(org_id, object_type, object_id, signer_id, signer_name,"
            " signer_role, meaning, statement) VALUES ($1,'qc_certificate',$2,$3,$4,$5,$6,$7)"
            " RETURNING *",
            user["org_id"], coa_id, user["id"],
            prof["full_name"] or user.get("username") or "—", user["role"], body.meaning,
            body.statement)
        await safe_emit(c, user, verb="coa_signed", object_type="qc_certificate",
                   object_id=coa_id, recipients=[], params={"meaning": body.meaning})
    return _sig_out(dict(row))
