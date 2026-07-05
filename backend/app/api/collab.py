"""Task collaboration — comments + assignment/acknowledgment.

All routes run on the RLS-scoped `app_user` pool, so org isolation and task
visibility (the `tasks_read` policy) are enforced by the database. The
`task_comments` and `task_assignees` tables are org-isolated; assigning a user
to a task makes it visible to them (tasks_read has an assignee clause) and it
shows up in their week, which is what gives acknowledgment something to act on.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import rls, rls_users
from app.deps import require_password_set
from app.roles import ELEVATED_ROLES
from app.roster import display_name, roster

router = APIRouter(tags=["collab"])

# Roles allowed to (un)assign others, in addition to a task's own owner —
# app.roles.ELEVATED_ROLES is the single source of truth (mirrors the DB's
# app.is_elevated()).
_ELEVATED = ELEVATED_ROLES


class CommentReq(BaseModel):
    content: str


class AssignReq(BaseModel):
    user_id: UUID
    role: str = "assignee"


class AckReq(BaseModel):
    accepted: bool
    reason: str | None = None


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
        r = await c.fetchrow(
            "INSERT INTO task_comments(org_id, task_id, user_id, content) "
            "VALUES ($1,$2,$3,$4) RETURNING id, created_at",
            user["org_id"], task_id, user["id"], content)
    return {"id": str(r["id"]), "user_id": str(user["id"]),
            "author": user["full_name"] or user["username"], "content": content,
            "created_at": r["created_at"].isoformat()}


# ── Assignment + acknowledgment ─────────────────────────────────────────────
@router.get("/tasks/{task_id}/assignees")
async def list_assignees(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        await _task_or_404(c, task_id)
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
                "ON CONFLICT (task_id, user_id) DO UPDATE SET role=EXCLUDED.role",
                task_id, body.user_id, user["org_id"], body.role or "assignee", user["id"])
        except Exception as e:  # unique violation etc.
            raise HTTPException(400, f"Could not assign: {type(e).__name__}")
    return {"ok": True}


@router.delete("/tasks/{task_id}/assignees/{assignee_id}")
async def unassign(task_id: str, assignee_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await _task_or_404(c, task_id)
        if not _can_manage_task(user, task):
            raise HTTPException(403, "Only the task owner or an elevated role can unassign")
        await c.execute("DELETE FROM task_assignees WHERE task_id=$1 AND user_id=$2", task_id, assignee_id)
    return {"ok": True}


@router.post("/tasks/{task_id}/ack")
async def acknowledge(task_id: str, body: AckReq, user: dict = Depends(require_password_set)):
    """The assignee accepts or declines their own assignment (decline records a reason)."""
    async with rls(user) as c:
        await _task_or_404(c, task_id)
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
    return {"ok": True, "accepted": body.accepted}
