"""Read-only audit trail API (GxP / 21 CFR Part 11 style).

The `audit_log` table is written by the `app.fn_audit_row` trigger and is
hash-chained: every row's `prev_hash` is the `entry_hash` of the row inserted
just before it, and `entry_hash = sha256(prev_hash || actor || op || table ||
record_id || ts || new || old)`. That makes the trail tamper-evident — you
cannot delete or reorder a row without breaking the linkage of every row after
it.

  • GET /audit          → org-scoped list (user pool; the DB `audit_read`
                          policy already limits rows to elevated roles in the
                          caller's org, the role guard mirrors it).
  • GET /audit/tables   → distinct table names + counts, to drive the filter UI.
  • GET /audit/verify   → walk the *global* chain (admin pool, ADMIN only) and
                          report the first linkage break, if any.
"""
from fastapi import APIRouter, Depends, Query

from app.db import admin_pool, rls
from app.deps import require_role

router = APIRouter(prefix="/audit", tags=["audit"])

# Roles the DB `audit_read` policy (app.is_elevated) admits — mirrored here so
# the API rejects early instead of silently returning an empty list.
_ELEVATED = ("ADMIN", "DEPT_HEAD", "PROJECT_LEAD", "QA_AUDITOR")


# Secret columns are never exposed through the trail, even to admins.
_REDACT = {"password_hash", "password", "otp", "secret", "token", "api_key"}


def _ser(r) -> dict:
    """old_values/new_values arrive already parsed (db.py registers a jsonb
    codec). Sensitive columns captured by the row-level trigger (e.g.
    password_hash) are redacted here so they never leave the API."""
    def _j(v):
        if isinstance(v, dict):
            for k in list(v.keys()):
                if k in _REDACT and v[k] is not None:
                    v[k] = "***"
        return v
    return {
        "id": r["id"],
        "org_id": str(r["org_id"]) if r["org_id"] else None,
        "user_id": str(r["user_id"]) if r["user_id"] else None,
        "user_email": r["user_email"],
        "action": r["action"],
        "table_name": r["table_name"],
        "record_id": r["record_id"],
        "old_values": _j(r["old_values"]),
        "new_values": _j(r["new_values"]),
        "prev_hash": r["prev_hash"],
        "entry_hash": r["entry_hash"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


@router.get("")
async def list_audit(
    table_name: str | None = None,
    record_id: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    before_id: int | None = Query(None, description="keyset paginate: rows with id < before_id"),
    user: dict = Depends(require_role(*_ELEVATED)),
):
    clauses, args = ["true"], []
    if table_name:
        args.append(table_name); clauses.append(f"table_name=${len(args)}")
    if record_id:
        args.append(record_id); clauses.append(f"record_id=${len(args)}")
    if action:
        args.append(action.upper()); clauses.append(f"action=${len(args)}")
    if before_id:
        args.append(before_id); clauses.append(f"id<${len(args)}")
    where = " AND ".join(clauses)
    args.append(limit)
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT id,org_id,user_id,user_email,action,table_name,record_id,"
            f"old_values,new_values,prev_hash,entry_hash,created_at "
            f"FROM audit_log WHERE {where} ORDER BY id DESC LIMIT ${len(args)}", *args)
    return [_ser(r) for r in rows]


@router.get("/tables")
async def audit_tables(user: dict = Depends(require_role(*_ELEVATED))):
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT table_name, count(*) AS n FROM audit_log "
            "GROUP BY table_name ORDER BY n DESC")
    return [{"table_name": r["table_name"], "count": r["n"]} for r in rows]


@router.get("/verify")
async def verify_chain(user: dict = Depends(require_role("ADMIN"))):
    """Validate the global hash-chain linkage (each row links the prior one).

    Runs over the admin pool because the chain spans every org — verifying only
    the org-visible subset would report false breaks where other-org rows were
    filtered out. Reports the first id whose prev_hash != the prior entry_hash.
    """
    row = await admin_pool().fetchrow(
        """
        WITH chained AS (
          SELECT id, entry_hash, prev_hash,
                 lag(entry_hash) OVER (ORDER BY id) AS prior_entry
          FROM audit_log
        )
        SELECT count(*)                                                       AS total,
               count(*) FILTER (
                 WHERE prior_entry IS NOT NULL
                   AND COALESCE(prev_hash,'') <> prior_entry)                 AS breaks,
               min(id) FILTER (
                 WHERE prior_entry IS NOT NULL
                   AND COALESCE(prev_hash,'') <> prior_entry)                 AS first_break
        FROM chained
        """)
    return {
        "ok": (row["breaks"] or 0) == 0,
        "total": row["total"],
        "breaks": row["breaks"] or 0,
        "first_break_id": row["first_break"],
    }
