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
from app.deps import dept_scope, require_role
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

    # M1: a department-scoped manager must not read OTHER departments' task
    # content through the audit trail. Audit rows carry the full task JSON but
    # no department column, so filter on the department_id embedded in the
    # row's new/old payload, and drop the users-DB (identity) chain entirely —
    # profiles events are org-wide/cross-department by nature. Org-wide elevated
    # roles (execs, QP, ADMIN) are unaffected: dept_scope() returns None for
    # them AND for a scoped manager with no department set yet, which then
    # falls through to org-wide — the app's usual anti-"manager-sees-nothing"
    # behaviour. Rows without a department_id in their payload (progress,
    # sessions, comments…) fall out for scoped managers, which is the safe side.
    dscope = dept_scope(user)
    if dscope:
        args.append(dscope)
        clauses.append(f"COALESCE(new_values->>'department_id', old_values->>'department_id')=${len(args)}")

    where = " AND ".join(clauses)
    args.append(limit)
    q = f"{_SELECT} WHERE {where} ORDER BY created_at DESC LIMIT ${len(args)}"
    eff_source = "tasks" if dscope else source

    # Each side is over-fetched to `limit`, merged, then cut — so the page is
    # correct no matter how the two chains interleave in time.
    merged: list[dict] = []
    if eff_source in (None, "tasks"):
        async with rls(user) as c:
            merged += [_ser(r, "tasks") for r in await c.fetch(q, *args)]
    if eff_source in (None, "users"):
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


# M6: verify RECOMPUTES each row's entry_hash from the stored columns and
# compares it to the recorded hash — not just the prev_hash⇄entry_hash pointer
# linkage. The recompute mirrors app.fn_audit_row's payload EXACTLY:
#   COALESCE(prev_hash,'') || actor || action || table_name || record_id
#   || created_at::text || new_values::text || old_values::text
# The trigger's actor is COALESCE(current_setting('app.user_id',true),'system').
# For a real user the app SETs it to the canonical uuid text → the stored user_id;
# `user_id::text` reproduces it. For a system/admin write the actor is either ''
# (the empty-string placeholder a custom GUC reverts to on a connection that has
# had it set with SET LOCAL — the common warm-pool case) or 'system' (a
# never-set connection). Both leave user_id NULL and are indistinguishable from
# the stored row, so a NULL-user_id row is accepted if EITHER reconstruction
# matches — no false break, while a genuine content edit matches NEITHER. This
# catches an in-place edit of old_values/new_values that left the hash columns
# intact (the precise BYPASSRLS/DBA tamper a hash chain exists to detect). It
# also anchors the head (row 1 must have an empty prev_hash) so head truncation
# surfaces, and retains the pointer-linkage / middle-deletion check. created_at
# renders under the same server TimeZone the writes used (neither the app nor the
# admin pool overrides it), reproducing the trigger's now()::text.
_CHAIN_SQL = """
WITH chained AS (
  SELECT id, entry_hash, prev_hash, user_id, action, table_name, record_id,
         old_values, new_values, created_at,
         lag(entry_hash) OVER (ORDER BY id) AS prior_entry,
         row_number()   OVER (ORDER BY id) AS rn
  FROM audit_log
),
recomputed AS (
  SELECT id, entry_hash, prev_hash, prior_entry, rn,
         encode(digest(convert_to(
             COALESCE(prev_hash,'') || COALESCE(user_id::text,'')
             || action || table_name || COALESCE(record_id,'')
             || created_at::text
             || COALESCE(new_values::text,'') || COALESCE(old_values::text,''),
           'UTF8'), 'sha256'), 'hex') AS calc_empty,
         encode(digest(convert_to(
             COALESCE(prev_hash,'') || COALESCE(user_id::text,'system')
             || action || table_name || COALESCE(record_id,'')
             || created_at::text
             || COALESCE(new_values::text,'') || COALESCE(old_values::text,''),
           'UTF8'), 'sha256'), 'hex') AS calc_system
  FROM chained
),
broken AS (
  SELECT id, rn,
         (calc_empty <> entry_hash AND calc_system <> entry_hash)           AS hash_bad,
         (prior_entry IS NOT NULL AND COALESCE(prev_hash,'') <> prior_entry) AS link_bad,
         (rn = 1 AND COALESCE(prev_hash,'') <> '')                          AS head_bad
  FROM recomputed
)
SELECT count(*)                                              AS total,
       count(*) FILTER (WHERE hash_bad)                      AS hash_breaks,
       count(*) FILTER (WHERE link_bad)                      AS link_breaks,
       count(*) FILTER (WHERE head_bad)                      AS head_breaks,
       count(*) FILTER (WHERE hash_bad OR link_bad OR head_bad) AS breaks,
       min(id)  FILTER (WHERE hash_bad OR link_bad OR head_bad) AS first_break
FROM broken
"""


@router.get("/verify")
async def verify_chain(user: dict = Depends(require_role("ADMIN"))):
    """Validate both global hash chains: recompute each row's hash from its stored
    columns AND check pointer linkage + head anchoring.

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
            "hash_breaks": row["hash_breaks"] or 0,
            "link_breaks": row["link_breaks"] or 0,
            "head_breaks": row["head_breaks"] or 0,
            "first_break_id": row["first_break"],
        }
    return {"ok": out["users"]["ok"] and out["tasks"]["ok"], **out}
