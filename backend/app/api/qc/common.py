from app.roles import ADMIN, EXECUTIVE_ROLES
from fastapi import APIRouter, HTTPException
import uuid


router = APIRouter(prefix="/qc", tags=["qc"])


_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "QC_MGR", "QP")


_QP_ROLES = (ADMIN, "QP")


_COQ_ROLES = (ADMIN, "QC_MGR")


def _uuid_or_404(value, what: str = "Resource") -> None:
    """A malformed {id} path segment must be a clean 404, not a 500 from asyncpg
    trying to cast it to a uuid inside the lookup query (mirrors auth._require_uuid)."""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, f"{what} not found")


def _uuid_or_422(value, field: str) -> None:
    """A user-supplied uuid BODY field (cross-DB actor refs have no FK to catch a
    bad value) must 422 on a malformed id rather than 500 on the insert."""
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(422, f"{field} must be a valid id")


_HOQC = (ADMIN, "QC_MGR", "QP")


def _evaluate(value: float | None, lo: float | None, hi: float | None):
    """Return (complies, status). Unknown when there's no numeric value to
    judge — GxP: we never invent a verdict for a missing measurement."""
    if value is None:
        return None, "unknown"
    ok = (lo is None or value >= lo) and (hi is None or value <= hi)
    return ok, ("pass" if ok else "fail")


def _lab_verdict_bool(v: str | None) -> bool | None:
    """Best-effort reading of the lab's stated verdict for the reconciliation
    flag. Deliberately conservative: anything ambiguous returns None and no
    mismatch is computed — the flag must never manufacture a disagreement."""
    if not v:
        return None
    t = v.strip().lower()
    if t in ("no", "не") or any(n in t for n in ("not", "non", "fail", "oos", "не ")):
        return False
    if any(p in t for p in ("pass", "conform", "compl", "задоволува", "соодветств")):
        return True
    return None


_SAMPLE_KINDS = ("PC", "MB", "EXT", "RET", "STAB", "RT", "CC")


_QC_REGISTRAR = (ADMIN, "QC_MGR", "QP")


def splice_stamps(fields: list[str], args: list, extra_sql: list[str], extra_args: list):
    """Append actor-stamp fragments to a positional-parameter UPDATE.

    `extra_sql` fragments carry the literal token PLACEHOLDER where a `$n`
    belongs; `n` is only knowable once the fragment's value has been appended to
    `args`, which is why this cannot just be built inline with the rest.
    Fragments WITHOUT the token (e.g. "phase_ii_completed_at=now()") consume no
    argument and pass through untouched.

    Factored out of certificates.py and oos.py, which had grown two copies.
    They were not equivalent: certificates.py used
    `zip(extra_sql, extra_args)`, which is only correct while every fragment
    happens to carry a placeholder — adding one no-placeholder fragment there
    would have silently mis-paired every value after it against the wrong
    column, with no error. oos.py's token-checking form is the correct one and
    is what this keeps. Mutates `fields`/`args` in place, as both call sites do
    throughout.
    """
    pending = list(extra_args)
    for frag in extra_sql:
        if "PLACEHOLDER" in frag:
            args.append(pending.pop(0))
            fields.append(frag.replace("PLACEHOLDER", str(len(args))))
        else:
            fields.append(frag)
    if pending:
        raise ValueError(
            f"splice_stamps: {len(pending)} stamp value(s) had no PLACEHOLDER fragment"
        )
