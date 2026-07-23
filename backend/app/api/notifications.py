"""Per-user inbox + shared activity feed (Phase-1 notifications).

Design per docs/RESEARCH-NOTIFICATIONS-2026-07.md:
  • GET  /notifications                → my inbox (reason label on every item,
                                         unread filter, keyset pagination)
  • GET  /notifications/unread-count   → server-computed single source of
                                         truth for the bell badge (polled)
  • POST /notifications/{id}/read      → mark one read (on open)
  • POST /notifications/read-all       → mark all read
  • POST /notifications/{id}/done      → soft-archive (lifecycle beyond read)
  • GET  /activity                     → the shared append-only feed. Org-wide
                                         for elevated non-dept-scoped roles;
                                         department-scoped users see their
                                         department's events plus their own.

RLS already confines notification rows to their recipient (notif_select), so
the inbox endpoints add no extra scoping. The feed's department filter is
app-layer, mirroring list_tasks' scoping approach.
"""
from datetime import datetime, timedelta, timezone

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import rls
from app.deps import dept_scope, is_dept_scoped_role, require_password_set

router = APIRouter(tags=["notifications"])

# Kept in lockstep with the notifications.reason CHECK constraint
# (migration 0016 widened it for the canned automation rules; this regex
# had gone stale, 422-ing a filter on the very reasons the CI-visible
# feature added — every valid reason value must appear here).
_REASONS = "assigned|mentioned|comment|status|due|report|capa_stuck|validation_stuck|workflow"

_ITEM = ("SELECT n.id, n.reason, n.read_at, n.done_at, n.created_at,"
         " e.actor_id, e.verb, e.object_type, e.object_id, e.task_id,"
         " e.department_id, e.params"
         " FROM notifications n JOIN events e ON e.id = n.event_id")


def _ser(r) -> dict:
    return {
        "id": str(r["id"]), "reason": r["reason"], "verb": r["verb"],
        "actor_id": str(r["actor_id"]),
        "object_type": r["object_type"], "object_id": r["object_id"],
        "task_id": str(r["task_id"]) if r["task_id"] else None,
        "department_id": str(r["department_id"]) if r["department_id"] else None,
        "params": r["params"] or {},
        "read": r["read_at"] is not None, "done": r["done_at"] is not None,
        "created_at": r["created_at"].isoformat(),
    }


@router.get("/notifications")
async def list_notifications(
    unread: bool = False,
    reason: str | None = Query(None, pattern=f"^({_REASONS})$"),
    limit: int = Query(50, ge=1, le=200),
    before: str | None = None,
    user: dict = Depends(require_password_set),
):
    clauses, args = ["n.done_at IS NULL"], []
    if unread:
        clauses.append("n.read_at IS NULL")
    if reason:
        args.append(reason); clauses.append(f"n.reason=${len(args)}")
    if before:
        try:
            args.append(datetime.fromisoformat(before))
        except ValueError:
            raise HTTPException(422, "before must be an ISO timestamp")
        clauses.append(f"n.created_at<${len(args)}")
    args.append(limit)
    q = f"{_ITEM} WHERE {' AND '.join(clauses)} ORDER BY n.created_at DESC LIMIT ${len(args)}"
    async with rls(user) as c:
        rows = await c.fetch(q, *args)
    return [_ser(r) for r in rows]


@router.get("/notifications/unread-count")
async def unread_count(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        n = await c.fetchval(
            "SELECT count(*) FROM notifications WHERE read_at IS NULL AND done_at IS NULL")
    return {"unread": n}


@router.post("/notifications/read-all")
async def read_all(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        res = await c.execute(
            "UPDATE notifications SET read_at=now() WHERE read_at IS NULL AND done_at IS NULL")
    return {"ok": True, "marked": int(res.split()[-1])}


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@router.post("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(require_password_set)):
    if not _UUID_RE.match(str(nid)):
        raise HTTPException(404, "Not found")
    async with rls(user) as c:
        res = await c.execute(
            "UPDATE notifications SET read_at=COALESCE(read_at, now()) WHERE id=$1", nid)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


@router.post("/notifications/{nid}/done")
async def mark_done(nid: str, user: dict = Depends(require_password_set)):
    if not _UUID_RE.match(str(nid)):
        raise HTTPException(404, "Not found")
    async with rls(user) as c:
        res = await c.execute(
            "UPDATE notifications SET done_at=now(), read_at=COALESCE(read_at, now()) WHERE id=$1", nid)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


@router.get("/activity")
async def activity(
    limit: int = Query(50, ge=1, le=200),
    before: str | None = None,
    user: dict = Depends(require_password_set),
):
    """The shared feed. Department-scoped visibility mirrors the task board:
    dept-scoped managers and USERs see their department's events + their own
    actions; org-wide roles (execs, QP, ADMIN) see everything."""
    clauses, args = ["true"], []
    dept = dept_scope(user) if is_dept_scoped_role(user) else (
        str(user["department_id"]) if user["role"] == "USER" and user["department_id"] else None)
    org_wide = user["role"] != "USER" and not is_dept_scoped_role(user)
    if not org_wide:
        args.append(dept)
        args.append(str(user["id"]))
        clauses.append(f"(department_id=${len(args)-1}::uuid OR actor_id=${len(args)}::uuid)")
    if before:
        try:
            args.append(datetime.fromisoformat(before))
        except ValueError:
            raise HTTPException(422, "before must be an ISO timestamp")
        clauses.append(f"created_at<${len(args)}")
    args.append(limit)
    q = (f"SELECT id, actor_id, verb, object_type, object_id, task_id, department_id,"
         f" params, created_at FROM events WHERE {' AND '.join(clauses)}"
         f" ORDER BY created_at DESC LIMIT ${len(args)}")
    async with rls(user) as c:
        rows = await c.fetch(q, *args)
    return [{
        "id": str(r["id"]), "actor_id": str(r["actor_id"]), "verb": r["verb"],
        "object_type": r["object_type"], "object_id": r["object_id"],
        "task_id": str(r["task_id"]) if r["task_id"] else None,
        "department_id": str(r["department_id"]) if r["department_id"] else None,
        "params": r["params"] or {}, "created_at": r["created_at"].isoformat(),
    } for r in rows]


@router.get("/notifications/digest")
async def digest(
    window: str = Query("daily", pattern="^(daily|weekly)$"),
    user: dict = Depends(require_password_set),
):
    """'What did my team do' — an in-app summary over the events table, same
    scoping as /activity (dept-scoped roles see their department + their own
    actions; org-wide roles see everything). daily = last 24h, weekly = last
    7d. This is the v2 in-app digest; an emailed manager/exec digest and
    quiet-hours-gated push are explicitly OUT of scope until SMTP / a push
    channel exist (docs/RESEARCH-NOTIFICATIONS-2026-07.md's own v2 path) —
    building either now would be unenforceable dead code."""
    since = datetime.now(timezone.utc) - (timedelta(days=1) if window == "daily" else timedelta(days=7))
    clauses, args = ["created_at >= $1"], [since]
    dept = dept_scope(user) if is_dept_scoped_role(user) else (
        str(user["department_id"]) if user["role"] == "USER" and user["department_id"] else None)
    org_wide = user["role"] != "USER" and not is_dept_scoped_role(user)
    if not org_wide:
        args.append(dept); args.append(str(user["id"]))
        clauses.append(f"(department_id=${len(args)-1}::uuid OR actor_id=${len(args)}::uuid)")
    where = " AND ".join(clauses)
    async with rls(user) as c:
        by_verb = await c.fetch(
            f"SELECT verb, count(*) AS n FROM events WHERE {where} GROUP BY verb ORDER BY n DESC", *args)
        by_actor = await c.fetch(
            f"SELECT actor_id, count(*) AS n FROM events WHERE {where} GROUP BY actor_id ORDER BY n DESC LIMIT 10",
            *args)
        recent = await c.fetch(
            f"SELECT id, actor_id, verb, object_type, object_id, task_id, department_id, params, created_at"
            f" FROM events WHERE {where} ORDER BY created_at DESC LIMIT 30", *args)
    return {
        "window": window, "since": since.isoformat(),
        "by_verb": [{"verb": r["verb"], "count": r["n"]} for r in by_verb],
        "by_actor": [{"actor_id": str(r["actor_id"]), "count": r["n"]} for r in by_actor],
        "total": sum(r["n"] for r in by_verb),
        "recent": [{
            "id": str(r["id"]), "actor_id": str(r["actor_id"]), "verb": r["verb"],
            "object_type": r["object_type"], "object_id": r["object_id"],
            "task_id": str(r["task_id"]) if r["task_id"] else None,
            "department_id": str(r["department_id"]) if r["department_id"] else None,
            "params": r["params"] or {}, "created_at": r["created_at"].isoformat(),
        } for r in recent],
    }
