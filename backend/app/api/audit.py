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
                          a per-source (created_at, id) keyset carried in an
                          opaque `cursor` (returned in the X-Next-Cursor
                          response header) — NOT a bare timestamp: one
                          transaction's rows all share created_at (now() is
                          constant for a transaction; plant generation writes
                          50 such rows), and a page boundary inside that
                          group with `created_at < before` skipped the rest
                          of the group for good (CODE-REVIEW-DEEP-2026-07 M7,
                          review 2026-09-27 BC-08). The two chains have
                          colliding bigint ids, so the keyset is kept per
                          source. `before` (a timestamp) still works for old
                          clients and is lossy for exactly that reason. Every
                          row carries `source: "users" | "tasks"`.
  • GET /audit/tables   → distinct table names + counts across both chains.
  • GET /audit/verify   → walk BOTH global chains (admin pools; ADMIN plus the
                          QA_MGR / QP auditor roles — read-only verification)
                          and report each one's first linkage break, if any.
"""
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.config import settings
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

_SOURCES = ("tasks", "users")
CURSOR_HEADER = "X-Next-Cursor"


def _decode_cursor(raw: str | None) -> dict[str, tuple[datetime, int]]:
    """{source: (created_at, id)} of the last row the client has seen per
    chain. Opaque to the client; a malformed one is a 422, never a 500."""
    if not raw:
        return {}
    try:
        data = json.loads(base64.urlsafe_b64decode(raw.encode("ascii") + b"=" * (-len(raw) % 4)))
        out = {}
        for src in _SOURCES:
            if src in data:
                ts, rid = data[src]
                out[src] = (datetime.fromisoformat(ts), int(rid))
        return out
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(422, "cursor is not a value this endpoint issued")


def _encode_cursor(pos: dict[str, tuple[datetime, int]]) -> str:
    data = {src: [ts.isoformat(), rid] for src, (ts, rid) in pos.items()}
    return base64.urlsafe_b64encode(json.dumps(data).encode("ascii")).decode("ascii").rstrip("=")


@router.get("")
async def list_audit(
    response: Response,
    table_name: str | None = None,
    record_id: str | None = None,
    action: str | None = None,
    source: str | None = Query(None, pattern="^(users|tasks)$"),
    limit: int = Query(100, ge=1, le=500),
    before: str | None = Query(None, description="LEGACY keyset: rows created strictly before this ISO"
                                                 " timestamp. Lossy at a page boundary inside one"
                                                 " transaction's rows — prefer `cursor`."),
    cursor: str | None = Query(None, description="the X-Next-Cursor header of the previous page"),
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
    position = _decode_cursor(cursor)

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
        clauses.append(f"COALESCE(new_values->>'department_id', old_values->>'department_id')"
                       f" = ANY(app.dept_family(${len(args)}::uuid)::text[])")
    eff_source = "tasks" if dscope else source

    def _query(src: str) -> tuple[str, list]:
        """The per-source statement: the shared filters plus that chain's own
        composite keyset. (created_at, id) is a total order within a chain —
        ORDER BY the same pair, so the rows of one transaction (equal
        created_at) page in a fixed order and the cursor resumes inside them."""
        src_clauses, src_args = list(clauses), list(args)
        if src in position:
            ts, rid = position[src]
            src_args += [ts, rid]
            src_clauses.append(f"(created_at, id) < (${len(src_args)-1}::timestamptz, ${len(src_args)}::bigint)")
        src_args.append(limit)
        return (f"{_SELECT} WHERE {' AND '.join(src_clauses)}"
                f" ORDER BY created_at DESC, id DESC LIMIT ${len(src_args)}"), src_args

    # Each side is over-fetched to `limit`, merged, then cut — so the page is
    # correct no matter how the two chains interleave in time. The merge key
    # is (created_at, source, id): a total order, so equal timestamps across
    # the two chains still page deterministically.
    merged: list[dict] = []
    if eff_source in (None, "tasks"):
        q, a = _query("tasks")
        async with rls(user) as c:
            merged += [_ser(r, "tasks") for r in await c.fetch(q, *a)]
    if eff_source in (None, "users"):
        q, a = _query("users")
        async with rls_users(user) as c:
            merged += [_ser(r, "users") for r in await c.fetch(q, *a)]
    merged.sort(key=lambda r: (r["created_at"] or "", r["source"], r["id"]), reverse=True)
    page = merged[:limit]

    # The next cursor: the last emitted row per chain; a chain with nothing on
    # this page keeps its previous position (every row of it not yet emitted
    # is still older than that position, because the merge emits newest first).
    nxt = dict(position)
    for r in page:
        nxt[r["source"]] = (datetime.fromisoformat(r["created_at"]), r["id"])
    if page:
        response.headers[CURSOR_HEADER] = _encode_cursor(nxt)
        response.headers["Access-Control-Expose-Headers"] = CURSOR_HEADER
    return page


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


# M6/H2: verify RECOMPUTES each row's entry_hash from the stored columns and
# compares it to the recorded hash — not just the prev_hash⇄entry_hash pointer
# linkage. The recompute mirrors app.fn_audit_row's payload EXACTLY:
#   COALESCE(prev_hash,'') || actor || action || table_name || record_id
#   || created_at::text || new_values::text || old_values::text
#
# THE ACTOR AMBIGUITY. The trigger's actor is
# COALESCE(current_setting('app.user_id',true),'system'). For a real user the app
# SETs it to the canonical uuid text → the stored user_id, which `user_id::text`
# reproduces. For a system/admin write the actor is either '' (the empty-string
# placeholder a custom GUC reverts to on a connection that has had it set with SET
# LOCAL — the common warm-pool case) or 'system' (a never-set connection). Both
# leave user_id NULL and are indistinguishable from the stored row, so a
# NULL-user_id row is accepted if EITHER reconstruction matches — no false break,
# while a genuine content edit matches NEITHER.
#
# THE TIMEZONE AMBIGUITY (H2), and why this query is parameterised by zone.
# `now()::text` in the trigger and `created_at::text` here both render a
# timestamptz under the SESSION's TimeZone. A row written by a connection at UTC+2
# therefore cannot be recomputed under UTC — the instant is identical, the TEXT is
# not, so the digest differs. This was NOT hypothetical: production carried 377
# such rows from a single UTC+2 transaction which verified 377/377 under
# Europe/Skopje and 0/377 under UTC. An earlier version of this comment asserted
# that created_at "renders under the same server TimeZone the writes used", and
# that assumption was simply wrong.
#
# So the caller runs this once per candidate zone (UTC first, then the facility
# zone) and a row is HASH-VERIFIED if it matches under any of them. A row matching
# only a non-UTC zone is reported as `hash_legacy_tz` — explained, not hidden, and
# not counted as a break. Tolerating the zone costs nothing in tamper detection: a
# forger controls the row's content and would simply hash it correctly, and what
# actually catches them is that altering any row invalidates every downstream link.
# tasks-0050 / users-0009 pin the trigger's own TimeZone to UTC, so rows written
# from now on are zone-canonical and this tolerance only ever applies to history.
#
# LINK BREAKS ARE CLASSIFIED, not lumped together, because the two kinds mean
# opposite things:
#   fork   — prev_hash matches the entry_hash of a real row with a LOWER id. Two
#            writers read the same chain tail and both linked to it. That is the
#            pre-hardening concurrency bug tasks-0012 / users-0006 fixed with an
#            advisory lock (2026-07-14); production's 38 such rows are all dated
#            2026-07-11, before the lock existed, and nothing after id 2500 is
#            affected. Historical and explained — NOT a tamper signal.
#   orphan — prev_hash matches NO row at all. That is what a deleted or rewritten
#            predecessor looks like. THIS is the alarm.
# `ok` therefore requires zero hash breaks, zero orphans and zero head breaks.
# Forks are reported with their id range so a NEW one (which would mean the
# advisory lock failed) is visibly outside the known historical window.
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
)
SELECT id, rn,
       (calc_empty = entry_hash OR calc_system = entry_hash) AS hash_ok,
       (prior_entry IS NOT NULL AND COALESCE(prev_hash,'') <> prior_entry) AS link_bad,
       -- a broken link that still points at a REAL earlier row is a fork, not a
       -- deletion; resolved here so the caller needs no second round trip
       (prev_hash IS NOT NULL AND EXISTS (
          SELECT 1 FROM audit_log a WHERE a.entry_hash = recomputed.prev_hash
                                      AND a.id < recomputed.id)) AS prev_resolves,
       (rn = 1 AND COALESCE(prev_hash,'') <> '') AS head_bad
FROM recomputed
"""


async def _verify_one(pool) -> dict:
    """Verify one chain, recomputing under each candidate TimeZone.

    The zone is applied with SET LOCAL inside a transaction so Postgres itself
    renders the timestamp — reproducing `timestamptz::text` by hand is a trap
    (it trims trailing zeros in the microseconds, among other things), and the
    whole point is to reproduce the trigger's rendering byte for byte."""
    zones = ["UTC"]
    if settings.snapshot_tz and settings.snapshot_tz != "UTC":
        zones.append(settings.snapshot_tz)

    hash_ok_utc: set[int] = set()
    hash_ok_any: set[int] = set()
    rows: list = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            for zone in zones:
                # set_config, not an interpolated SET: the zone comes from config
                # and must never be concatenated into SQL.
                await conn.execute("SELECT set_config('TimeZone', $1, true)", zone)
                rows = await conn.fetch(_CHAIN_SQL)
                ok = {r["id"] for r in rows if r["hash_ok"]}
                if zone == "UTC":
                    hash_ok_utc = ok
                hash_ok_any |= ok

    total = len(rows)
    hash_breaks, legacy_tz, forks, orphans, head_breaks = 0, 0, 0, 0, 0
    fork_ids: list[int] = []
    break_ids: list[int] = []
    for r in rows:
        rid = r["id"]
        if rid not in hash_ok_any:
            hash_breaks += 1
            break_ids.append(rid)
        elif rid not in hash_ok_utc:
            legacy_tz += 1
        if r["link_bad"]:
            if r["prev_resolves"]:
                forks += 1
                fork_ids.append(rid)
            else:
                orphans += 1
                break_ids.append(rid)
        if r["head_bad"]:
            head_breaks += 1
            break_ids.append(rid)

    breaks = hash_breaks + orphans + head_breaks
    out = {
        "ok": breaks == 0,
        "total": total,
        "breaks": breaks,
        "hash_breaks": hash_breaks,
        "link_orphans": orphans,
        "head_breaks": head_breaks,
        # Informational: intact rows that only reproduce under a non-UTC zone.
        "hash_legacy_tz": legacy_tz,
        # Informational: pre-advisory-lock chain forks (tasks-0012 / users-0006).
        "link_forks": forks,
        "first_break_id": min(break_ids) if break_ids else None,
        "zones_tried": zones,
    }
    if fork_ids:
        out["fork_id_range"] = [min(fork_ids), max(fork_ids)]
    return out


@router.get("/verify")
async def verify_chain(user: dict = Depends(require_role("ADMIN", "QA_MGR", "QP"))):
    """Validate both global hash chains: recompute each row's hash from its stored
    columns AND check pointer linkage + head anchoring.

    Runs over the admin pools because each chain spans every org — verifying
    only the org-visible subset would report false breaks where other-org
    rows were filtered out.

    `ok` is false only for a genuine integrity failure: a row whose content does
    not reproduce its hash under ANY candidate zone, a link pointing at a row that
    does not exist, or a rewritten head. `hash_legacy_tz` and `link_forks` are
    reported alongside because they are explained history (see _CHAIN_SQL above),
    and burying them would be as wrong as failing on them."""
    out = {}
    for source, pool in (("users", users_admin_pool()), ("tasks", tasks_admin_pool())):
        out[source] = await _verify_one(pool)
    return {"ok": out["users"]["ok"] and out["tasks"]["ok"], **out}
