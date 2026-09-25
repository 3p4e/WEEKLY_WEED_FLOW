"""Approvals — everything waiting on someone's decision, one call.

Two lists, both derived from task_assignees.accepted IS NULL (a pending
acknowledgment) on live work (not deleted / archived / completed):

  mine — assignments waiting on the CALLER to accept or decline. Everyone
         gets this (operators act on it from My Day).
  team — assignments other people haven't acknowledged yet, for follow-up.
         Elevated roles only; department-scoped managers see their own
         department's, org-wide roles see everything.

The rest of the Approvals surface (draft documents awaiting lock, unapproved
report sections, stuck tasks) is composed client-side from endpoints that
already exist — this endpoint only adds the aggregate the client cannot
compute without N per-task calls.
"""
from fastapi import APIRouter, Depends

from app.db import rls
from app.deps import dept_scope, require_password_set
from app.roles import ELEVATED_ROLES

router = APIRouter(prefix="/approvals", tags=["approvals"])

_BASE = (
    "SELECT ta.task_id, ta.user_id, ta.assigned_by, ta.assigned_at,"
    " t.title, t.priority, t.due_date, t.department_id"
    " FROM task_assignees ta JOIN tasks t ON t.id = ta.task_id"
    " WHERE ta.accepted IS NULL AND t.is_deleted = false"
    " AND t.is_archived = false AND t.status <> 'completed'"
)


def _ser(r) -> dict:
    return {
        "task_id": str(r["task_id"]), "user_id": str(r["user_id"]),
        "assigned_by": str(r["assigned_by"]) if r["assigned_by"] else None,
        "assigned_at": r["assigned_at"].isoformat(),
        "title": r["title"], "priority": r["priority"],
        "due_date": r["due_date"].isoformat() if r["due_date"] else None,
        "department_id": str(r["department_id"]) if r["department_id"] else None,
    }


@router.get("/pending")
async def pending(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        mine = await c.fetch(
            f"{_BASE} AND ta.user_id = $1 ORDER BY ta.assigned_at", user["id"])
        team = []
        if user["role"] in ELEVATED_ROLES:
            scope = dept_scope(user)
            if scope:
                team = await c.fetch(
                    f"{_BASE} AND ta.user_id <> $1 AND t.department_id = ANY(app.dept_family($2))"
                    f" ORDER BY ta.assigned_at", user["id"], scope)
            else:
                team = await c.fetch(
                    f"{_BASE} AND ta.user_id <> $1 ORDER BY ta.assigned_at", user["id"])
    return {"mine": [_ser(r) for r in mine], "team": [_ser(r) for r in team]}
