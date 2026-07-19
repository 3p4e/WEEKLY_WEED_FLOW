"""Task collaboration — comments + assignment/acknowledgment.

All routes run on the RLS-scoped `app_user` pool, so org isolation and task
visibility (the `tasks_read` policy) are enforced by the database. The
`task_comments` and `task_assignees` tables are org-isolated; assigning a user
to a task makes it visible to them (tasks_read has an assignee clause) and it
shows up in their week, which is what gives acknowledgment something to act on.
"""
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.tasks import _assert_scope_visible
from app.db import rls, rls_users, tasks_admin_pool
from app.deps import dept_scope, require_password_set
from app.roles import ELEVATED_ROLES
from app.notify import emit, participants
from app.roster import display_name, roster

# @username mentions in comments — usernames are the login handles
# (lowercase word chars, dots, hyphens), matched conservatively so an email
# address in a comment doesn't half-match as a mention.
_MENTION_RE = re.compile(r"(?<![\w@])@([a-z0-9][a-z0-9_.\-]{1,63})", re.IGNORECASE)

router = APIRouter(tags=["collab"])

# Roles allowed to (un)assign others, in addition to a task's own owner —
# app.roles.ELEVATED_ROLES is the single source of truth (mirrors the DB's
# app.is_elevated()).
_ELEVATED = ELEVATED_ROLES


class CommentReq(BaseModel):
    content: str = Field(max_length=10_000)


class AssignReq(BaseModel):
    user_id: UUID
    role: str = Field(default="assignee", max_length=64)


class AckReq(BaseModel):
    accepted: bool
    reason: str | None = Field(default=None, max_length=2000)


async def _task_or_404(conn, task_id: str) -> dict:
    t = await conn.fetchrow("SELECT id, user_id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
    if t is None:
        raise HTTPException(404, "Task not found")
    return t


def _can_manage_task(user: dict, task: dict) -> bool:
    return user["role"] in _ELEVATED or str(task["user_id"]) == str(user["id"])


# ── Comments ────────────────────────────────────────────────────────────────
@router.get("/tasks/{task_id}/comments")
async def list_comments(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        await _task_or_404(c, task_id)
        await _assert_scope_visible(c, task_id, user)
        rows = await c.fetch(
            "SELECT id, user_id, content, created_at "
            "FROM task_comments WHERE task_id=$1 ORDER BY created_at", task_id)
    # Author names live in the users database — merge app-side.
    names = await roster(user) if rows else {}
    return [{"id": str(r["id"]), "user_id": str(r["user_id"]),
             "author": display_name(names, r["user_id"]),
             "content": r["content"], "created_at": r["created_at"].isoformat()} for r in rows]


@router.post("/tasks/{task_id}/comments", status_code=201)
async def add_comment(task_id: str, body: CommentReq, user: dict = Depends(require_password_set)):
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(422, "Comment cannot be empty")
    async with rls(user) as c:
        await _task_or_404(c, task_id)
        await _assert_scope_visible(c, task_id, user)
        r = await c.fetchrow(
            "INSERT INTO task_comments(org_id, task_id, user_id, content) "
            "VALUES ($1,$2,$3,$4) RETURNING id, created_at",
            user["org_id"], task_id, user["id"], content)
        # Notify everyone with a participation stake (creator/owner/assignees/
        # prior commenters), never the author (emit guards that). @username
        # mentions (usernames are unique, so plain @token resolves exactly)
        # are listed FIRST so emit's first-reason-wins dedupe labels a
        # mentioned participant as `mentioned`, not `comment` — mentions are
        # the strongest signal in every vendor default.
        try:
            t = await c.fetchrow("SELECT title, department_id FROM tasks WHERE id=$1", task_id)
            mentioned = []
            handles = {h.lower() for h in _MENTION_RE.findall(content)}
            who = await participants(c, task_id)
            if handles:
                async with rls_users(user) as uc:
                    rows = await uc.fetch(
                        "SELECT id, role, department_id FROM profiles"
                        " WHERE org_id=$1 AND is_deleted=false"
                        " AND lower(username) = ANY($2::text[])",
                        user["org_id"], sorted(handles)[:16])
                # A mention notification carries the task title + a comment
                # preview — deliver it only to people who can actually see the
                # task (elevated roles, same-department staff, or existing
                # participants). Otherwise "@operator see <detail>" on an
                # elevated-only task leaks its title+content into the inbox of
                # someone who gets 404 on the task itself.
                task_dept = str(t["department_id"]) if t and t["department_id"] else None
                who_set = {str(w) for w in who}
                mentioned = [str(r["id"]) for r in rows
                             if r["role"] != "USER"
                             or (task_dept and str(r["department_id"] or "") == task_dept)
                             or str(r["id"]) in who_set]
            await emit(c, user, verb="commented", object_type="task", object_id=task_id,
                       recipients=[(u, "mentioned") for u in mentioned]
                                  + [(u, "comment") for u in who],
                       task_id=task_id,
                       department_id=t["department_id"] if t else None,
                       params={"title": (t["title"] if t else ""), "preview": content[:80]})
        except Exception:
            pass
    return {"id": str(r["id"]), "user_id": str(user["id"]),
            "author": user["full_name"] or user["username"], "content": content,
            "created_at": r["created_at"].isoformat()}


# ── Assignment + acknowledgment ─────────────────────────────────────────────
@router.get("/tasks/{task_id}/assignees")
async def list_assignees(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        await _task_or_404(c, task_id)
        await _assert_scope_visible(c, task_id, user)
        rows = await c.fetch(
            "SELECT user_id, role, accepted, accepted_at, assigned_at "
            "FROM task_assignees WHERE task_id=$1 ORDER BY assigned_at", task_id)
    names = await roster(user) if rows else {}
    return [{"user_id": str(r["user_id"]), "name": display_name(names, r["user_id"]), "role": r["role"],
             "accepted": r["accepted"],
             "accepted_at": r["accepted_at"].isoformat() if r["accepted_at"] else None} for r in rows]


@router.post("/tasks/{task_id}/assignees", status_code=201)
async def assign(task_id: str, body: AssignReq, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await _task_or_404(c, task_id)
        if not _can_manage_task(user, task):
            raise HTTPException(403, "Only the task owner or an elevated role can assign")
        # An elevated role is any manager, not just an org-wide one — without
        # this, a dept-scoped manager's "elevated" status above would let them
        # assign/unassign on ANY task in the org, not just their own scope.
        await _assert_scope_visible(c, task_id, user)
        # task_assignees.user_id has NO foreign key (profiles live in the
        # users database), so this org-membership check is the ONLY integrity
        # guard on assignee ids: it stops both a dangling uuid and a cross-org
        # id (which would leak the task via the tasks_read assignee clause).
        async with rls_users(user) as uc:
            target = await uc.fetchrow(
                "SELECT id FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=false",
                body.user_id, user["org_id"])
        if target is None:
            raise HTTPException(404, "User not found in this organization")
        try:
            await c.execute(
                "INSERT INTO task_assignees(task_id, user_id, org_id, role, assigned_by) "
                "VALUES ($1,$2,$3,$4,$5) "
                "ON CONFLICT (task_id, user_id) DO UPDATE SET "
                "role=EXCLUDED.role, accepted=NULL, accepted_at=NULL",
                task_id, body.user_id, user["org_id"], body.role or "assignee", user["id"])
        except Exception as e:  # unique violation etc.
            raise HTTPException(400, f"Could not assign: {type(e).__name__}")
        # Awareness (best-effort): the assignee gets an inbox notification;
        # the event also feeds the shared activity stream.
        try:
            t = await c.fetchrow("SELECT title, department_id FROM tasks WHERE id=$1", task_id)
            await emit(c, user, verb="assigned", object_type="task", object_id=task_id,
                       recipients=[(body.user_id, "assigned")], task_id=task_id,
                       department_id=t["department_id"] if t else None,
                       params={"title": (t["title"] if t else "")})
        except Exception:
            pass
    return {"ok": True}


@router.delete("/tasks/{task_id}/assignees/{assignee_id}")
async def unassign(task_id: str, assignee_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await _task_or_404(c, task_id)
        if not _can_manage_task(user, task):
            raise HTTPException(403, "Only the task owner or an elevated role can unassign")
        await _assert_scope_visible(c, task_id, user)
        res = await c.execute("DELETE FROM task_assignees WHERE task_id=$1 AND user_id=$2", task_id, assignee_id)
        # Research matrix: assigned AND unassigned notify the (ex-)assignee.
        if res.split()[-1] != "0":
            try:
                t = await c.fetchrow("SELECT title, department_id FROM tasks WHERE id=$1", task_id)
                await emit(c, user, verb="unassigned", object_type="task", object_id=task_id,
                           recipients=[(assignee_id, "assigned")], task_id=task_id,
                           department_id=t["department_id"] if t else None,
                           params={"title": (t["title"] if t else "")})
            except Exception:
                pass
    return {"ok": True}


@router.post("/tasks/{task_id}/ack")
async def acknowledge(task_id: str, body: AckReq, user: dict = Depends(require_password_set)):
    """The assignee accepts or declines their own assignment (decline records a reason)."""
    async with rls(user) as c:
        await _task_or_404(c, task_id)
        await _assert_scope_visible(c, task_id, user)
        res = await c.execute(
            "UPDATE task_assignees SET accepted=$1, accepted_at=now() WHERE task_id=$2 AND user_id=$3",
            body.accepted, task_id, user["id"])
        if res.split()[-1] == "0":   # asyncpg returns 'UPDATE <n>'
            raise HTTPException(404, "You are not assigned to this task")
        # Record the decision (especially a decline reason) as a visible comment.
        note = "✓ Accepted" if body.accepted else "✋ Declined"
        if body.reason and body.reason.strip():
            note += ": " + body.reason.strip()
        await c.execute(
            "INSERT INTO task_comments(org_id, task_id, user_id, content) VALUES ($1,$2,$3,$4)",
            user["org_id"], task_id, user["id"], note)
        # The assigner/owner learns the assignment was accepted or declined.
        try:
            t = await c.fetchrow("SELECT title, department_id FROM tasks WHERE id=$1", task_id)
            who = await participants(c, task_id)
            await emit(c, user, verb="ack", object_type="task", object_id=task_id,
                       recipients=[(u, "status") for u in who], task_id=task_id,
                       department_id=t["department_id"] if t else None,
                       params={"title": (t["title"] if t else ""), "accepted": body.accepted})
        except Exception:
            pass
    return {"ok": True, "accepted": body.accepted}


# ── Cross-department handoffs ───────────────────────────────────────────────
# The handoffs table has always existed (schema.tasks.sql, 4-state lifecycle);
# T1 surfaces it. Proposing a handoff pings the TARGET department's head so the
# receiving side actually learns about it; accepting it re-homes the task into
# that department (which also makes it visible to that department's board).
class HandoffIn(BaseModel):
    to_dept_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class HandoffResolve(BaseModel):
    status: str  # accepted | rejected | cancelled


@router.post("/tasks/{task_id}/handoffs", status_code=201)
async def propose_handoff(task_id: str, body: HandoffIn, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        t = await c.fetchrow(
            "SELECT id, title, department_id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if t is None:
            raise HTTPException(404, "Task not found")
        await _assert_scope_visible(c, task_id, user)
        dst = await c.fetchrow(
            "SELECT id, name, head_user_id FROM departments WHERE id=$1 AND is_active=true", body.to_dept_id)
        if dst is None:
            raise HTTPException(422, "Unknown target department")
        if t["department_id"] and str(t["department_id"]) == str(body.to_dept_id):
            raise HTTPException(422, "Task is already in that department")
        row = await c.fetchrow(
            "INSERT INTO handoffs(org_id, task_id, from_dept_id, to_dept_id, requested_by, note)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], task_id, t["department_id"], body.to_dept_id, user["id"], body.note)
        await c.execute(
            "INSERT INTO task_comments(org_id, task_id, user_id, content) VALUES ($1,$2,$3,$4)",
            user["org_id"], task_id, user["id"], f"↪ Handoff proposed to {dst['name']}")
        # Ping the receiving department's head + the task's own participants.
        try:
            recips = [(u, "status") for u in await participants(c, task_id)]
            if dst["head_user_id"]:
                recips.append((dst["head_user_id"], "status"))
            await emit(c, user, verb="handoff", object_type="task", object_id=task_id,
                       recipients=recips, task_id=task_id, department_id=body.to_dept_id,
                       params={"title": t["title"], "to_dept": dst["name"]})
        except Exception:
            pass
    return dict(row)


@router.get("/tasks/{task_id}/handoffs")
async def list_handoffs(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        await _task_or_404(c, task_id)
        await _assert_scope_visible(c, task_id, user)
        rows = await c.fetch("SELECT * FROM handoffs WHERE task_id=$1 ORDER BY created_at DESC", task_id)
    return [dict(r) for r in rows]


@router.post("/handoffs/{handoff_id}/resolve")
async def resolve_handoff(handoff_id: str, body: HandoffResolve, user: dict = Depends(require_password_set)):
    """accepted → the task moves into the target department; rejected/cancelled
    just close the request. Only an elevated role, the target department's
    head, or (for cancel) the original requester may resolve."""
    if body.status not in ("accepted", "rejected", "cancelled"):
        raise HTTPException(422, "status must be accepted, rejected, or cancelled")
    async with rls(user) as c:
        # FOR UPDATE: without the row lock, concurrent accept+reject both pass
        # the proposed-status check and the task can move departments while the
        # handoff record ends "rejected".
        h = await c.fetchrow("SELECT * FROM handoffs WHERE id=$1 FOR UPDATE", handoff_id)
        if h is None:
            raise HTTPException(404, "Handoff not found")
        if h["status"] != "proposed":
            raise HTTPException(409, f"Handoff already {h['status']}")
        dst = await c.fetchrow("SELECT head_user_id FROM departments WHERE id=$1", h["to_dept_id"])
        is_head = dst is not None and str(dst["head_user_id"] or "") == str(user["id"])
        is_requester = str(h["requested_by"]) == str(user["id"])
        # Receiving-side authority: the target department's head, or a manager
        # whose department IS the target. The old scope-visibility check ran
        # first, which 404'd the exact person the proposal pings (the target
        # dept's scoped manager — the task still sits in the SOURCE dept), so
        # the handoff's primary actor could never resolve it.
        target_side = is_head or (
            user["role"] in _ELEVATED
            and str(user.get("department_id") or "") == str(h["to_dept_id"]))
        # Org-wide elevated roles (ADMIN/executives/QP — not dept-scoped) may
        # arbitrate, but the PROPOSER may not accept their own handoff into a
        # department that never consented (second-person rule). They may still
        # reject/cancel it (withdrawing an own proposal is harmless).
        org_wide = user["role"] in _ELEVATED and dept_scope(user) is None
        if body.status == "accepted":
            allowed = target_side or (org_wide and not is_requester)
        else:
            allowed = target_side or org_wide or is_requester
        if not allowed:
            raise HTTPException(403, "Not permitted to resolve this handoff")
        # Non-target resolvers still need ordinary visibility of the task.
        if not target_side:
            await _assert_scope_visible(c, str(h["task_id"]), user)
        await c.execute(
            "UPDATE handoffs SET status=$1, resolved_by=$2, resolved_at=now() WHERE id=$3",
            body.status, user["id"], handoff_id)
        if body.status == "accepted":
            # Admin pool with explicit org+id filter: a USER-role department
            # head passes the permission check but the caller-scoped RLS
            # tasks_write policy silently filters their UPDATE to 0 rows —
            # handoff marked accepted while the task never moved.
            tag = await tasks_admin_pool().execute(
                "UPDATE tasks SET department_id=$1, updated_at=now()"
                " WHERE id=$2 AND org_id=$3",
                h["to_dept_id"], h["task_id"], user["org_id"])
            if tag == "UPDATE 0":
                raise HTTPException(409, "Task no longer exists — handoff not applied")
        t = await c.fetchrow("SELECT title, department_id FROM tasks WHERE id=$1", h["task_id"])
        verb_txt = {"accepted": "✓ Handoff accepted", "rejected": "✗ Handoff rejected",
                    "cancelled": "⊘ Handoff cancelled"}[body.status]
        await c.execute(
            "INSERT INTO task_comments(org_id, task_id, user_id, content) VALUES ($1,$2,$3,$4)",
            user["org_id"], h["task_id"], user["id"], verb_txt)
        try:
            recips = [(u, "status") for u in await participants(c, str(h["task_id"]))]
            recips.append((h["requested_by"], "status"))
            await emit(c, user, verb="handoff_resolved", object_type="task", object_id=str(h["task_id"]),
                       recipients=recips, task_id=h["task_id"],
                       department_id=t["department_id"] if t else None,
                       params={"title": (t["title"] if t else ""), "status": body.status})
        except Exception:
            pass
    return {"ok": True, "status": body.status}
