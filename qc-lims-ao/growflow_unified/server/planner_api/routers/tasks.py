"""Planner task board — departments, users, tasks (+ subtasks/helpers/notes/deps/
handoffs) and weekly telemetry. JWT-gated (per-user); team-wide visibility.
"""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    AssignmentDecision,
    PlannerDepartment,
    PlannerHandoff,
    PlannerHandoffCreate,
    PlannerNoteCreate,
    PlannerProgressNote,
    PlannerSubtask,
    PlannerTask,
    PlannerTaskCreate,
    PlannerTaskUpdate,
    PlannerTelemetry,
    PlannerTreeNode,
    UserOut,
)

from ..auth_deps import CurrentUser, get_current_user, rls_session

router = APIRouter(prefix="/planner", tags=["planner"])

_DONE = "done"
_STATUSES = ("pending", "working", "review", "stuck", "postponed", "done")
_DAY_BUSY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

_TASK_SELECT = (
    "SELECT t.id, t.parent_id, t.department_id, d.key AS department_key, t.title, t.owner_id, "
    "u.full_name AS owner_name, t.status, t.priority, t.week_start, t.days, t.room, "
    "t.batch, t.tags, t.description, t.blocker, t.outcome, t.assignment_status, "
    "t.assignment_responded_at, t.assignment_note, t.position, t.node_kind, t.is_sop, "
    "t.annex_count, t.attributes, t.started_at, t.ended_at, t.created_at, t.updated_at, "
    "t.completed_at, (SELECT count(*) FROM planner_task c WHERE c.parent_id = t.id) AS child_count "
    "FROM planner_task t "
    "JOIN planner_department d ON d.id = t.department_id "
    "LEFT JOIN app_user u ON u.id = t.owner_id "
)


# --------------------------------------------------------------------------- #
# Reference lists
# --------------------------------------------------------------------------- #
@router.get("/departments", response_model=list[PlannerDepartment])
async def list_departments(session: AsyncSession = Depends(rls_session)) -> list[PlannerDepartment]:
    rows = (
        await session.execute(
            text(
                "SELECT id, key, name_en, name_mk, icon, color, handoff_to_id, position "
                "FROM planner_department ORDER BY position, name_en"
            )
        )
    ).mappings().all()
    return [
        PlannerDepartment(
            id=str(r["id"]),
            key=r["key"],
            name_en=r["name_en"],
            name_mk=r["name_mk"],
            icon=r["icon"],
            color=r["color"],
            handoff_to_id=str(r["handoff_to_id"]) if r["handoff_to_id"] else None,
            position=r["position"],
        )
        for r in rows
    ]


@router.get("/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(rls_session)) -> list[UserOut]:
    rows = (
        await session.execute(
            text(
                "SELECT u.id, u.username, u.full_name, u.role, u.email, u.avatar_url, "
                "u.dept_id, d.key AS dept_key "
                "FROM app_user u LEFT JOIN planner_department d ON d.id = u.dept_id "
                "WHERE u.is_active ORDER BY u.full_name"
            )
        )
    ).mappings().all()
    return [
        UserOut(
            id=str(r["id"]),
            username=r["username"],
            full_name=r["full_name"],
            role=r["role"],
            email=r["email"],
            avatar_url=r["avatar_url"],
            dept_id=str(r["dept_id"]) if r["dept_id"] else None,
            dept_key=r["dept_key"],
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Task assembly helpers
# --------------------------------------------------------------------------- #
async def _children(session: AsyncSession, ids: list[str]) -> dict[str, dict]:
    """Fetch helpers/subtasks/notes/deps/handoffs for the given task ids."""
    out = {tid: {"helpers": [], "subtasks": [], "notes": [], "deps": [], "handoffs": []} for tid in ids}
    if not ids:
        return out
    helpers = (
        await session.execute(
            text("SELECT task_id, user_id FROM planner_task_helper WHERE task_id = ANY(:ids)"),
            {"ids": ids},
        )
    ).mappings().all()
    for h in helpers:
        out[str(h["task_id"])]["helpers"].append(str(h["user_id"]))

    subs = (
        await session.execute(
            text(
                "SELECT id, task_id, text, done, position FROM planner_subtask "
                "WHERE task_id = ANY(:ids) ORDER BY position"
            ),
            {"ids": ids},
        )
    ).mappings().all()
    for s in subs:
        out[str(s["task_id"])]["subtasks"].append(
            PlannerSubtask(id=str(s["id"]), text=s["text"], done=s["done"], position=s["position"])
        )

    notes = (
        await session.execute(
            text(
                "SELECT n.id, n.task_id, n.day, n.note, n.author_id, a.full_name AS author_name, "
                "n.created_at FROM planner_progress_note n "
                "LEFT JOIN app_user a ON a.id = n.author_id "
                "WHERE n.task_id = ANY(:ids) ORDER BY n.created_at"
            ),
            {"ids": ids},
        )
    ).mappings().all()
    for n in notes:
        out[str(n["task_id"])]["notes"].append(
            PlannerProgressNote(
                id=str(n["id"]),
                day=n["day"],
                note=n["note"],
                author_id=str(n["author_id"]) if n["author_id"] else None,
                author_name=n["author_name"],
                created_at=n["created_at"],
            )
        )

    deps = (
        await session.execute(
            text(
                "SELECT task_id, depends_on_task_id FROM planner_task_dependency "
                "WHERE task_id = ANY(:ids)"
            ),
            {"ids": ids},
        )
    ).mappings().all()
    for d in deps:
        out[str(d["task_id"])]["deps"].append(str(d["depends_on_task_id"]))

    handoffs = (
        await session.execute(
            text(
                "SELECT h.id, h.task_id, h.to_department_id, d.key AS to_department_key, "
                "h.status, h.requested_by, h.created_at FROM planner_handoff h "
                "JOIN planner_department d ON d.id = h.to_department_id "
                "WHERE h.task_id = ANY(:ids) ORDER BY h.created_at"
            ),
            {"ids": ids},
        )
    ).mappings().all()
    for h in handoffs:
        out[str(h["task_id"])]["handoffs"].append(
            PlannerHandoff(
                id=str(h["id"]),
                to_department_id=str(h["to_department_id"]),
                to_department_key=h["to_department_key"],
                status=h["status"],
                requested_by=str(h["requested_by"]) if h["requested_by"] else None,
                created_at=h["created_at"],
            )
        )
    return out


def _attrs(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return {}


def _row_to_task(r, kids: dict) -> PlannerTask:
    return PlannerTask(
        id=str(r["id"]),
        parent_id=str(r["parent_id"]) if r["parent_id"] else None,
        department_id=str(r["department_id"]),
        department_key=r["department_key"],
        title=r["title"],
        owner_id=str(r["owner_id"]) if r["owner_id"] else None,
        owner_name=r["owner_name"],
        status=r["status"],
        priority=r["priority"],
        week_start=r["week_start"],
        days=list(r["days"] or []),
        room=r["room"],
        batch=r["batch"],
        tags=list(r["tags"] or []),
        description=r["description"],
        blocker=r["blocker"],
        outcome=r["outcome"],
        assignment_status=r["assignment_status"],
        assignment_responded_at=r["assignment_responded_at"],
        assignment_note=r["assignment_note"],
        position=r["position"],
        node_kind=r["node_kind"],
        is_sop=bool(r["is_sop"]),
        annex_count=r["annex_count"] or 0,
        attributes=_attrs(r["attributes"]),
        started_at=r["started_at"],
        ended_at=r["ended_at"],
        child_count=r["child_count"] or 0,
        helper_ids=kids["helpers"],
        subtasks=kids["subtasks"],
        notes=kids["notes"],
        deps=kids["deps"],
        handoffs=kids["handoffs"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        completed_at=r["completed_at"],
    )


async def _load_one(session: AsyncSession, task_id: str) -> PlannerTask:
    r = (
        await session.execute(text(_TASK_SELECT + "WHERE t.id = :id"), {"id": task_id})
    ).mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="task not found")
    kids = await _children(session, [str(r["id"])])
    return _row_to_task(r, kids[str(r["id"])])


# --------------------------------------------------------------------------- #
# Task queries
# --------------------------------------------------------------------------- #
@router.get("/tasks", response_model=list[PlannerTask])
async def list_tasks(
    week_start: date | None = None,
    department_id: str | None = None,
    owner_id: str | None = None,
    session: AsyncSession = Depends(rls_session),
) -> list[PlannerTask]:
    clauses, params = [], {}
    if week_start is not None:
        clauses.append("t.week_start = :ws")
        params["ws"] = week_start
    if department_id:
        clauses.append("t.department_id = :dept")
        params["dept"] = department_id
    if owner_id:
        clauses.append("t.owner_id = :owner")
        params["owner"] = owner_id
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = (
        await session.execute(
            text(_TASK_SELECT + where + " ORDER BY t.position, t.created_at"), params
        )
    ).mappings().all()
    kids = await _children(session, [str(r["id"]) for r in rows])
    return [_row_to_task(r, kids[str(r["id"])]) for r in rows]


@router.get("/tasks/{task_id}", response_model=PlannerTask)
async def get_task(task_id: str, session: AsyncSession = Depends(rls_session)) -> PlannerTask:
    return await _load_one(session, task_id)


@router.get("/tree", response_model=list[PlannerTreeNode])
async def task_tree(
    root_id: str | None = None,
    department_id: str | None = None,
    week_start: date | None = None,
    session: AsyncSession = Depends(rls_session),
) -> list[PlannerTreeNode]:
    """Adaptive task tree (task -> annex -> step, depth varies by need). Returns a
    forest of roots with nested children, or the subtree under root_id."""
    clauses, params = [], {}
    if department_id:
        clauses.append("t.department_id = :dept"); params["dept"] = department_id
    if week_start is not None:
        clauses.append("t.week_start = :ws"); params["ws"] = week_start
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = (
        await session.execute(
            text(
                "SELECT t.id, t.parent_id, t.title, t.node_kind, t.status, t.priority, "
                "t.is_sop, t.annex_count, t.attributes, t.started_at, t.ended_at, "
                "u.full_name AS owner_name, d.key AS department_key "
                "FROM planner_task t JOIN planner_department d ON d.id = t.department_id "
                "LEFT JOIN app_user u ON u.id = t.owner_id" + where +
                " ORDER BY t.node_kind DESC, t.position, t.created_at"
            ),
            params,
        )
    ).mappings().all()
    nodes: dict[str, PlannerTreeNode] = {
        str(r["id"]): PlannerTreeNode(
            id=str(r["id"]),
            parent_id=str(r["parent_id"]) if r["parent_id"] else None,
            title=r["title"], node_kind=r["node_kind"], status=r["status"],
            priority=r["priority"], is_sop=bool(r["is_sop"]),
            annex_count=r["annex_count"] or 0, owner_name=r["owner_name"],
            department_key=r["department_key"], attributes=_attrs(r["attributes"]),
            started_at=r["started_at"], ended_at=r["ended_at"],
        )
        for r in rows
    }
    roots: list[PlannerTreeNode] = []
    for n in nodes.values():
        if n.parent_id and n.parent_id in nodes:
            nodes[n.parent_id].children.append(n)
        else:
            roots.append(n)  # true root, or parent filtered out of this set
    if root_id:
        return [nodes[root_id]] if root_id in nodes else []
    return roots


@router.post("/tasks", response_model=PlannerTask, status_code=201)
async def create_task(
    body: PlannerTaskCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(rls_session),
) -> PlannerTask:
    if body.status not in _STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {list(_STATUSES)}")
    completed = "now()" if body.status == _DONE else "NULL"
    # Self-assigned or unassigned work needs no acknowledgment; assigning it to
    # someone else leaves it 'pending' until that person accepts/declines.
    assignment = "accepted" if (not body.owner_id or str(body.owner_id) == str(user.id)) else "pending"
    new_id = (
        await session.execute(
            text(
                "INSERT INTO planner_task "
                "(department_id, title, owner_id, status, priority, week_start, days, room, "
                " batch, tags, description, blocker, outcome, assignment_status, parent_id, "
                " node_kind, is_sop, attributes, created_by, completed_at) "
                f"VALUES (:dept, :title, :owner, :status, :priority, :ws, :days, :room, "
                f":batch, :tags, :description, :blocker, :outcome, :assignment, :parent, "
                f":kind, :sop, CAST(:attrs AS JSONB), :creator, {completed}) RETURNING id"
            ),
            {
                "dept": body.department_id,
                "title": body.title,
                "owner": body.owner_id,
                "status": body.status,
                "priority": body.priority,
                "ws": body.week_start,
                "days": body.days,
                "room": body.room,
                "batch": body.batch,
                "tags": body.tags,
                "description": body.description,
                "blocker": body.blocker,
                "outcome": body.outcome,
                "assignment": assignment,
                "parent": body.parent_id,
                "kind": body.node_kind,
                "sop": body.is_sop,
                "attrs": json.dumps(body.attributes or {}),
                "creator": user.id,
            },
        )
    ).scalar_one()
    tid = str(new_id)
    await _replace_helpers(session, tid, body.helper_ids)
    await _replace_subtasks(session, tid, body.subtasks)
    await _replace_deps(session, tid, body.deps)
    await session.commit()
    return await _load_one(session, tid)


@router.patch("/tasks/{task_id}", response_model=PlannerTask)
async def update_task(
    task_id: str, body: PlannerTaskUpdate, session: AsyncSession = Depends(rls_session)
) -> PlannerTask:
    fields = body.model_dump(exclude_unset=True)
    # Children handled separately.
    helper_ids = fields.pop("helper_ids", None)
    subtasks = fields.pop("subtasks", None)
    deps = fields.pop("deps", None)
    attributes = fields.pop("attributes", None)

    col_map = {
        "department_id": "department_id", "title": "title", "owner_id": "owner_id",
        "status": "status", "priority": "priority", "week_start": "week_start",
        "days": "days", "room": "room", "batch": "batch", "tags": "tags",
        "description": "description", "blocker": "blocker", "outcome": "outcome",
        "position": "position", "parent_id": "parent_id", "node_kind": "node_kind",
        "is_sop": "is_sop",
    }
    set_parts, params = [], {"id": task_id}
    for key, col in col_map.items():
        if key in fields:
            set_parts.append(f"{col} = :{key}")
            params[key] = fields[key]
    if attributes is not None:
        set_parts.append("attributes = CAST(:attrs AS JSONB)")
        params["attrs"] = json.dumps(attributes)
    if "status" in fields:
        if fields["status"] not in _STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {list(_STATUSES)}")
        set_parts.append("completed_at = CASE WHEN :status = 'done' THEN now() ELSE NULL END")
    # Re-assigning to a different owner requires a fresh acknowledgment.
    if "owner_id" in fields:
        cur_owner = (
            await session.execute(text("SELECT owner_id FROM planner_task WHERE id = :id"), {"id": task_id})
        ).scalar()
        old = str(cur_owner) if cur_owner else None
        new = str(fields["owner_id"]) if fields["owner_id"] else None
        if old != new:
            set_parts.append("assignment_status = :asg_status")
            set_parts.append("assignment_responded_at = NULL")
            set_parts.append("assignment_note = NULL")
            params["asg_status"] = "pending" if new else "accepted"

    if set_parts:
        set_parts.append("updated_at = now()")
        res = await session.execute(
            text(f"UPDATE planner_task SET {', '.join(set_parts)} WHERE id = :id RETURNING id"),
            params,
        )
        if res.first() is None:
            raise HTTPException(status_code=404, detail="task not found")
    else:
        # No scalar fields — confirm the task exists before touching children.
        exists = (
            await session.execute(text("SELECT 1 FROM planner_task WHERE id = :id"), {"id": task_id})
        ).first()
        if exists is None:
            raise HTTPException(status_code=404, detail="task not found")

    if helper_ids is not None:
        await _replace_helpers(session, task_id, helper_ids)
    if subtasks is not None:
        await _replace_subtasks(session, task_id, [PlannerSubtask(**s) for s in subtasks])
    if deps is not None:
        await _replace_deps(session, task_id, deps)
    await session.commit()
    return await _load_one(session, task_id)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, session: AsyncSession = Depends(rls_session)) -> None:
    res = await session.execute(
        text("DELETE FROM planner_task WHERE id = :id"), {"id": task_id}
    )
    await session.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="task not found")


# --------------------------------------------------------------------------- #
# Notes & handoffs
# --------------------------------------------------------------------------- #
@router.post("/tasks/{task_id}/notes", response_model=PlannerTask, status_code=201)
async def add_note(
    task_id: str,
    body: PlannerNoteCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(rls_session),
) -> PlannerTask:
    await session.execute(
        text(
            "INSERT INTO planner_progress_note (task_id, day, note, author_id) "
            "VALUES (:t, :day, :note, :author)"
        ),
        {"t": task_id, "day": body.day, "note": body.note, "author": user.id},
    )
    await session.commit()
    return await _load_one(session, task_id)


@router.post("/tasks/{task_id}/handoffs", response_model=PlannerTask, status_code=201)
async def add_handoff(
    task_id: str,
    body: PlannerHandoffCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(rls_session),
) -> PlannerTask:
    await session.execute(
        text(
            "INSERT INTO planner_handoff (task_id, to_department_id, requested_by) "
            "VALUES (:t, :dept, :by)"
        ),
        {"t": task_id, "dept": body.to_department_id, "by": user.id},
    )
    await session.commit()
    return await _load_one(session, task_id)


# --------------------------------------------------------------------------- #
# Assignment acknowledgment (assignee accepts/declines the work)
# --------------------------------------------------------------------------- #
@router.post("/tasks/{task_id}/assignment", response_model=PlannerTask)
async def respond_assignment(
    task_id: str,
    body: AssignmentDecision,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(rls_session),
) -> PlannerTask:
    if body.decision not in ("accepted", "declined"):
        raise HTTPException(status_code=422, detail="decision must be 'accepted' or 'declined'")
    row = (
        await session.execute(text("SELECT owner_id FROM planner_task WHERE id = :id"), {"id": task_id})
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")
    if not row["owner_id"] or str(row["owner_id"]) != str(user.id):
        raise HTTPException(status_code=403, detail="only the assignee can respond to the assignment")
    await session.execute(
        text(
            "UPDATE planner_task SET assignment_status = :s, assignment_responded_at = now(), "
            "assignment_note = :n, updated_at = now() WHERE id = :id"
        ),
        {"s": body.decision, "n": body.note, "id": task_id},
    )
    await session.commit()
    return await _load_one(session, task_id)


# --------------------------------------------------------------------------- #
# Telemetry (computed on demand)
# --------------------------------------------------------------------------- #
@router.get("/telemetry", response_model=PlannerTelemetry)
async def telemetry(
    week_start: date, session: AsyncSession = Depends(rls_session)
) -> PlannerTelemetry:
    rows = (
        await session.execute(
            text("SELECT status, days FROM planner_task WHERE week_start = :ws"),
            {"ws": week_start},
        )
    ).mappings().all()
    total = len(rows)
    by_status = {s: 0 for s in _STATUSES}
    day_counts = {d: 0 for d in _DAY_BUSY}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        for d in r["days"] or []:
            if d in day_counts:
                day_counts[d] += 1
    completion = round((by_status.get(_DONE, 0) / total) * 100) if total else 0
    busiest = max(day_counts.items(), key=lambda kv: kv[1])[0] if total else None
    return PlannerTelemetry(
        week_start=week_start,
        total=total,
        completion=completion,
        by_status=by_status,
        busiest_day=busiest,
    )


# --------------------------------------------------------------------------- #
# Child-collection replacers (used by create/update)
# --------------------------------------------------------------------------- #
async def _replace_helpers(session: AsyncSession, task_id: str, helper_ids: list[str]) -> None:
    await session.execute(
        text("DELETE FROM planner_task_helper WHERE task_id = :t"), {"t": task_id}
    )
    for uid in helper_ids:
        await session.execute(
            text("INSERT INTO planner_task_helper (task_id, user_id) VALUES (:t, :u) "
                 "ON CONFLICT DO NOTHING"),
            {"t": task_id, "u": uid},
        )


async def _replace_subtasks(session: AsyncSession, task_id: str, subtasks: list[PlannerSubtask]) -> None:
    await session.execute(
        text("DELETE FROM planner_subtask WHERE task_id = :t"), {"t": task_id}
    )
    for i, s in enumerate(subtasks):
        await session.execute(
            text(
                "INSERT INTO planner_subtask (task_id, text, done, position) "
                "VALUES (:t, :text, :done, :pos)"
            ),
            {"t": task_id, "text": s.text, "done": s.done, "pos": s.position or i},
        )


async def _replace_deps(session: AsyncSession, task_id: str, deps: list[str]) -> None:
    await session.execute(
        text("DELETE FROM planner_task_dependency WHERE task_id = :t"), {"t": task_id}
    )
    for dep in deps:
        if dep == task_id:
            continue
        await session.execute(
            text(
                "INSERT INTO planner_task_dependency (task_id, depends_on_task_id) "
                "VALUES (:t, :d) ON CONFLICT DO NOTHING"
            ),
            {"t": task_id, "d": dep},
        )
