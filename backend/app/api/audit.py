"""Read-only audit trail API — merged across the two databases.

Uses GxP-style patterns (hash-chained, tamper-evident) for internal
traceability. This is informational, not a compliance claim — WWF is not a
validated Part 11 system (see docs/SCOPE.md).

Each database keeps its own `audit_log`, written by its own copy of the
`app.fn_audit_row` trigger and hash-chained independently: identity events
(profiles) chain in the users database, work events (tasks, sessions, ...)
chain in the tasks database. A row's `prev_hash` is the `entry_hash` of the
row inserted just before it in the SAME chain, so you cannot delete or
reorder a row without breaking the linkage of every row after it — per
database.

  • GET /audit          → org-scoped merged list, newest first. Pagination is
                          a created_at keyset (`before`), NOT id — the two
                          chains have colliding bigint ids. Every row carries
                          `source: "users" | "tasks"`.
  • GET /audit/tables   → distinct table names + counts across both chains.
  • GET /audit/verify   → walk BOTH global chains (admin pools, ADMIN only)
                          and report each one's first linkage break, if any.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import rls, rls_users, tasks_admin_pool, users_admin_pool
from app.deps import require_role
from app.roles import ELEVATED_ROLES

router = APIRouter(prefix="/audit", tags=["audit"])

# Roles the DB `audit_read` policy (app.is_elevated) admits — app.roles is the
# single source of truth, so the API rejects early instead of silently
# returning an empty list.
_ELEVATED = ELEVATED_ROLES


# Secret columns are never exposed through the trail, even to admins.
_REDACT = {"password_hash", "password", "otp", "secret", "token", "api_key"}


def _ser(r, source: str) -> dict:
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
        "source": source,
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


_SELECT = ("SELECT id,org_id,user_id,user_email,action,table_name,record_id,"
           "old_values,new_values,prev_hash,entry_hash,created_at FROM audit_log")


@router.get("")
async def list_audit(
    table_name: str | None = None,
    record_id: str | None = None,
    action: str | None = None,
    source: str | None = Query(None, pattern="^(users|tasks)$"),
    limit: int = Query(100, ge=1, le=500),
    before: str | None = Query(None, description="keyset paginate: rows created strictly before this ISO timestamp"),
    user: dict = Depends(require_role(*_ELEVATED)),
):
    clauses, args = ["true"], []
    if table_name:
        args.append(table_name); clauses.append(f"table_name=${len(args)}")
    if record_id:
        args.append(record_id); clauses.append(f"record_id=${len(args)}")
    if action:
        args.append(action.upper()); clauses.append(f"action=${len(args)}")
    if before:
        try:
            args.append(datetime.fromisoformat(before))
        except ValueError:
            raise HTTPException(422, "before must be an ISO timestamp")
        clauses.append(f"created_at<${len(args)}")
    where = " AND ".join(clauses)
    args.append(limit)
    q = f"{_SELECT} WHERE {where} ORDER BY created_at DESC LIMIT ${len(args)}"

    # Each side is over-fetched to `limit`, merged, then cut — so the page is
    # correct no matter how the two chains interleave in time.
    merged: list[dict] = []
    if source in (None, "tasks"):
        async with rls(user) as c:
            merged += [_ser(r, "tasks") for r in await c.fetch(q, *args)]
    if source in (None, "users"):
        async with rls_users(user) as c:
            merged += [_ser(r, "users") for r in await c.fetch(q, *args)]
    merged.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return merged[:limit]


@router.get("/tables")
async def audit_tables(user: dict = Depends(require_role(*_ELEVATED))):
    q = "SELECT table_name, count(*) AS n FROM audit_log GROUP BY table_name"
    async with rls(user) as c:
        t_rows = await c.fetch(q)
    async with rls_users(user) as c:
        u_rows = await c.fetch(q)
    counts: dict[str, int] = {}
    for r in list(t_rows) + list(u_rows):
        counts[r["table_name"]] = counts.get(r["table_name"], 0) + r["n"]
    return [{"table_name": t, "count": n}
            for t, n in sorted(counts.items(), key=lambda kv: -kv[1])]


_CHAIN_SQL = """
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
"""


@router.get("/verify")
async def verify_chain(user: dict = Depends(require_role("ADMIN"))):
    """Validate both global hash chains (each row links the prior one).

    Runs over the admin pools because each chain spans every org — verifying
    only the org-visible subset would report false breaks where other-org
    rows were filtered out."""
    out = {}
    for source, pool in (("users", users_admin_pool()), ("tasks", tasks_admin_pool())):
        row = await pool.fetchrow(_CHAIN_SQL)
        out[source] = {
            "ok": (row["breaks"] or 0) == 0,
            "total": row["total"],
            "breaks": row["breaks"] or 0,
            "first_break_id": row["first_break"],
        }
    return {"ok": out["users"]["ok"] and out["tasks"]["ok"], **out}
