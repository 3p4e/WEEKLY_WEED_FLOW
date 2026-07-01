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

from app.db import rls
from app.deps import require_password_set

router = APIRouter(tags=["collab"])

# Roles allowed to (un)assign others, in addition to a task's own owner.
# Mirrors the DB's app.is_elevated() definition — keep these in sync.
_ELEVATED = {"ADMIN", "DEPT_HEAD", "PROJECT_LEAD", "QA_AUDITOR"}


class CommentReq(BaseModel):
    content: str


class AssignReq(BaseModel):
    user_id: UUID
    role: str = "assignee"


class AckReq(BaseModel):
    accepted: bool
    reason: str | None = None


def _author(r) -> str:
    return r["full_name"] or r["username"] or "—"


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
            "SELECT cm.id, cm.user_id, cm.content, cm.created_at, p.full_name, p.username "
            "FROM task_comments cm LEFT JOIN profiles p ON p.id=cm.user_id "
            "WHERE cm.task_id=$1 ORDER BY cm.created_at", task_id)
    return [{"id": str(r["id"]), "user_id": str(r["user_id"]), "author": _author(r),
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
            "SELECT a.user_id, a.role, a.accepted, a.accepted_at, a.assigned_at, p.full_name, p.username "
            "FROM task_assignees a LEFT JOIN profiles p ON p.id=a.user_id "
            "WHERE a.task_id=$1 ORDER BY a.assigned_at", task_id)
    return [{"user_id": str(r["user_id"]), "name": _author(r), "role": r["role"],
             "accepted": r["accepted"],
             "accepted_at": r["accepted_at"].isoformat() if r["accepted_at"] else None} for r in rows]


@router.post("/tasks/{task_id}/assignees", status_code=201)
async def assign(task_id: str, body: AssignReq, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await _task_or_404(c, task_id)
        if not _can_manage_task(user, task):
            raise HTTPException(403, "Only the task owner or an elevated role can assign")
        # The FK on task_assignees.user_id only requires the row to exist in
        # profiles, not that it shares this org — check explicitly so a
        # cross-org id can't be assigned (which would leak the task via the
        # tasks_read assignee clause).
        target = await c.fetchrow(
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
