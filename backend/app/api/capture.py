"""Capture import — the delivery end of the Master Task-Capture Prompt.

POST /capture/import takes the wwf-capture/v2 JSON contract
(docs/TASK-CAPTURE-PROMPT.md) and upserts it into the task database,
idempotently: tasks match on (org, external_ref); statuses only move
forward; sessions/links/subtasks/tags merge without duplicating. Importing
the same payload twice is a no-op — that is what makes multi-surface
capture (claude.ai, Cowork, Claude Code, the Drive sweep) safe.

Two ways in:
  • a normal authenticated user (the Import box in the UI) — may only
    import tasks owned by themselves, unless they are ADMIN;
  • the capture connector (claude.ai/Cowork MCP tool) — presents the
    static CAPTURE_IMPORT_TOKEN and acts as the configured capture user
    (qcm.blani). The token is valid ONLY on this route.
"""
import hmac
import os
from datetime import date, datetime

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.weekwindow import ensure_week
from app.db import rls, rls_users, users_admin_pool
from app.deps import dept_scope, require_password_set
from app.worktime import TZ

router = APIRouter(prefix="/capture", tags=["capture"])

_STATUSES = {"pending", "ongoing", "review", "stuck", "postponed", "completed"}
_TYPES = {"capa", "sop", "validation", "document", "lab", "meeting", "admin", "other"}
_PRIORITIES = {"low", "medium", "high", "critical"}
_RECURRENCE = {"daily", "weekly", "monthly"}
# Forward-only status movement: an import never regresses a task that has
# moved on since the capture was taken.
_STATUS_RANK = {"pending": 0, "ongoing": 1, "review": 2, "stuck": 3, "postponed": 3, "completed": 4}


class CaptureSession(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    hours: float | None = Field(default=None, gt=0)
    time_estimated: bool = False
    note: str | None = None


class CaptureSubtask(BaseModel):
    title: str
    status: str = "pending"
    description: str | None = None


class CaptureLink(BaseModel):
    url: str
    label: str | None = None
    kind: str = "other"


class CaptureTask(BaseModel):
    action: str = "create"
    external_ref: str
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str | None = None
    task_type: str | None = None
    reference_code: str | None = None
    department: str | None = None
    owner: str | None = None
    assignees: list[str] = Field(default_factory=list, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=64)
    week_start: date | None = None
    due_date: date | None = None
    estimated_hours: float | None = Field(default=None, ge=0)
    completed_date: date | None = None
    outcome: str | None = None
    blocker_reason: str | None = None
    recurrence_hint: str | None = None
    # Explicit caps, matching every other write surface in the app. A capture
    # is one person's session of work, so these bounds are far above any real
    # payload while keeping a hostile or runaway one from turning into an
    # unbounded per-task transaction loop below.
    subtasks: list[CaptureSubtask] = Field(default_factory=list, max_length=200)
    links: list[CaptureLink] = Field(default_factory=list, max_length=100)
    sessions: list[CaptureSession] = Field(default_factory=list, max_length=500)
    provenance: list[dict] = Field(default_factory=list, max_length=200)


class CapturePayload(BaseModel):
    session_meta: dict = {}
    tasks: list[CaptureTask] = Field(max_length=1000)


def _tz(dt: datetime | None) -> datetime | None:
    # Naive capture timestamps mean facility wall clock (Europe/Skopje) —
    # same rule as the work-session endpoint's _facility_tz.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt


async def _capture_actor(authorization: str | None) -> dict | None:
    """The connector path: a static token (env CAPTURE_IMPORT_TOKEN, only
    honored on this route) acting as the configured capture user."""
    token = os.environ.get("CAPTURE_IMPORT_TOKEN", "")
    username = os.environ.get("CAPTURE_IMPORT_USER", "qcm.blani")
    # Constant-time compare so the static token can't be recovered byte-by-byte
    # via response-timing (same reason security.py always pays the bcrypt cost).
    if not token or not authorization or not hmac.compare_digest(authorization, f"Bearer {token}"):
        return None
    row = await users_admin_pool().fetchrow(
        "SELECT id, org_id, username, full_name, role, department_id, function_role,"
        " is_active, must_change_password FROM profiles"
        " WHERE username=$1 AND is_deleted=false AND is_active", username)
    return dict(row) if row else None


async def _actor(authorization: str | None = Header(None)) -> dict:
    special = await _capture_actor(authorization)
    if special:
        return special
    # Fall through to the normal auth stack.
    from fastapi.security import HTTPAuthorizationCredentials

    from app.deps import get_current_user
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=authorization[7:])
    user = await get_current_user(cred)
    if user["must_change_password"]:
        raise HTTPException(403, "Password change required")
    return user


def _validate(t: CaptureTask) -> str | None:
    if t.status not in _STATUSES:
        return f"invalid status '{t.status}'"
    if t.task_type is not None and t.task_type not in _TYPES:
        return f"invalid task_type '{t.task_type}'"
    if t.priority is not None and t.priority not in _PRIORITIES:
        return f"invalid priority '{t.priority}'"
    if t.recurrence_hint and t.recurrence_hint not in _RECURRENCE:
        return f"invalid recurrence_hint '{t.recurrence_hint}'"
    if t.status == "completed" and not t.completed_date:
        return "completed without completed_date"
    return None


@router.post("/import")
async def import_capture(body: CapturePayload, actor: dict = Depends(_actor)):
    created, updated, sessions_added, skipped = 0, 0, 0, []

    # Owner usernames live in the users DB — resolve the whole org once.
    async with rls_users(actor) as uc:
        owner_rows = await uc.fetch(
            "SELECT id, username FROM profiles WHERE org_id=$1 AND is_deleted=false",
            actor["org_id"])
    owners = {r["username"]: r["id"] for r in owner_rows}

    async with rls(actor) as c:
        dept_rows = await c.fetch("SELECT id, code FROM departments")
    depts = {r["code"]: r["id"] for r in dept_rows}

    # A dept-scoped manager imports into their OWN department only — the same
    # restriction create_task enforces (tasks.py:379-390) and that this endpoint
    # never had: it resolved the capture's department code and used it verbatim,
    # so a scoped manager could file work into any department just by naming it
    # in the payload. An omitted department defaults to theirs rather than
    # landing unassigned, where their own scoped list could never surface it
    # again. Pure function of the actor, so it is resolved once here.
    # This binds the connector path too (_capture_actor acts as the configured
    # capture user) — whatever scope that account carries now applies to imports
    # arriving through the MCP tool.
    scope = dept_scope(actor)
    scope_id = actor["department_id"] if scope else None
    scope_code = next((r["code"] for r in dept_rows if str(r["id"]) == scope), None)

    for t in body.tasks:
        reason = _validate(t)
        if reason:
            skipped.append({"external_ref": t.external_ref, "reason": reason})
            continue
        owner_name = t.owner or actor["username"]
        owner_id = owners.get(owner_name)
        if owner_id is None:
            skipped.append({"external_ref": t.external_ref, "reason": f"unknown owner '{owner_name}'"})
            continue
        # Owner-scoping: only ADMIN may import work owned by someone else.
        if str(owner_id) != str(actor["id"]) and actor["role"] != "ADMIN":
            skipped.append({"external_ref": t.external_ref, "reason": "not allowed to import for another owner"})
            continue

        recurrence = {"freq": t.recurrence_hint, "interval": 1} if t.recurrence_hint else None
        dept_code = t.department
        dept_id = depts.get(t.department) if t.department else None
        if scope:
            if t.department:
                # An unresolvable code cannot be shown to be the actor's own, so
                # it is refused rather than silently stored with a null
                # department_id (which would land the task outside any scope).
                if dept_id is None or str(dept_id) != scope:
                    skipped.append({"external_ref": t.external_ref,
                                    "reason": f"department '{t.department}' is outside"
                                              " your department scope"})
                    continue
            else:
                dept_code, dept_id = scope_code, scope_id

        try:
            async with rls(actor) as c:
                week_id = await ensure_week(c, actor["org_id"], t.week_start) if t.week_start else None
                row = await c.fetchrow(
                    "SELECT * FROM tasks WHERE org_id=$1 AND external_ref=$2 AND is_deleted=false",
                    actor["org_id"], t.external_ref)
                is_new = row is None
                if is_new:
                    try:
                        # SAVEPOINT: a UniqueViolationError aborts the whole
                        # enclosing transaction (rls() runs the loop body in
                        # one), which would make the recovery SELECT below fail
                        # with InFailedSQLTransactionError. A nested
                        # transaction rolls back only this INSERT, leaving the
                        # outer transaction usable for the re-SELECT + merge.
                        async with c.transaction():
                            row = await c.fetchrow(
                                "INSERT INTO tasks(org_id,user_id,title,description,status,priority,"
                                " task_type,reference_code,external_ref,blocker_reason,recurrence,"
                                " department,department_id,week_id,week_start,due_date,completed_date,"
                                " outcome,tags,estimated_hours,created_by,updated_by)"
                                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,"
                                " $19,$20,$21,$21) RETURNING *",
                                actor["org_id"], owner_id, t.title, t.description, t.status,
                                t.priority or "medium", t.task_type or "other", t.reference_code,
                                t.external_ref, t.blocker_reason, recurrence,
                                dept_code, dept_id, week_id, t.week_start, t.due_date, t.completed_date,
                                t.outcome, t.tags, t.estimated_hours, actor["id"])
                    except asyncpg.exceptions.UniqueViolationError:
                        # Lost a concurrent-import race for this external_ref
                        # (tasks_org_external_ref_key) — the other request's
                        # INSERT won between our SELECT and INSERT. The savepoint
                        # rolled back cleanly, so the outer transaction is still
                        # live: re-SELECT the winner's row and fall through to
                        # the update-merge branch instead of a spurious db-error
                        # skip.
                        row = await c.fetchrow(
                            "SELECT * FROM tasks WHERE org_id=$1 AND external_ref=$2 AND is_deleted=false",
                            actor["org_id"], t.external_ref)
                        if row is None:
                            raise
                        is_new = False
                if is_new:
                    created += 1
                else:
                    # Forward-only merge: never regress status; fill blanks;
                    # union tags. Title/description follow the capture (it is
                    # the newer statement of the work).
                    new_status = (t.status if _STATUS_RANK.get(t.status, 0) >= _STATUS_RANK.get(row["status"], 0)
                                  else row["status"])
                    merged_tags = sorted(set(row["tags"] or []) | set(t.tags))
                    row = await c.fetchrow(
                        "UPDATE tasks SET title=$2, description=COALESCE($3, description), status=$4,"
                        " priority=COALESCE($5, priority), task_type=COALESCE($6, task_type),"
                        " reference_code=COALESCE($7, reference_code),"
                        " blocker_reason=COALESCE($8, blocker_reason), outcome=COALESCE($9, outcome),"
                        " due_date=COALESCE($10, due_date), completed_date=COALESCE($11, completed_date),"
                        " week_id=COALESCE($12, week_id), week_start=COALESCE($13, week_start),"
                        " estimated_hours=COALESCE($14, estimated_hours), tags=$15,"
                        " updated_by=$16, updated_at=now() WHERE id=$1 RETURNING *",
                        row["id"], t.title, t.description, new_status, t.priority, t.task_type,
                        t.reference_code, t.blocker_reason, t.outcome, t.due_date, t.completed_date,
                        week_id, t.week_start, t.estimated_hours, merged_tags, actor["id"])
                    updated += 1

                task_id = row["id"]
                # Sessions: dedup by (started_at, note) within the task.
                existing = {(s["started_at"], s["note"]) for s in await c.fetch(
                    "SELECT started_at, note FROM work_sessions WHERE task_id=$1", task_id)}
                for s in t.sessions:
                    started = _tz(s.started_at)
                    note = s.note or ""
                    if s.time_estimated:
                        note = (note + " " if note else "") + "[time estimated]"
                    if (started, note) in existing:
                        continue
                    await c.execute(
                        "INSERT INTO work_sessions(org_id,task_id,user_id,started_at,ended_at,hours,note,source)"
                        " VALUES ($1,$2,$3,$4,$5,$6,$7,'capture')",
                        actor["org_id"], task_id, owner_id, started, _tz(s.ended_at), s.hours, note)
                    existing.add((started, note))
                    sessions_added += 1

                # Links: dedup by url.
                have_urls = {r["url"] for r in await c.fetch(
                    "SELECT url FROM task_links WHERE task_id=$1", task_id)}
                for ln in t.links:
                    url = (ln.url or "").strip()
                    if not url.startswith(("http://", "https://")) or url in have_urls:
                        continue
                    kind = ln.kind if ln.kind in {"drive", "sop", "doc", "other"} else "other"
                    await c.execute(
                        "INSERT INTO task_links(org_id,task_id,url,label,kind,created_by)"
                        " VALUES ($1,$2,$3,$4,$5,$6)",
                        actor["org_id"], task_id, url, ln.label, kind, actor["id"])
                    have_urls.add(url)

                # Subtasks: dedup by title under this parent.
                have_titles = {r["title"] for r in await c.fetch(
                    "SELECT title FROM tasks WHERE parent_id=$1 AND is_deleted=false", task_id)}
                for st in t.subtasks:
                    if not st.title or st.title in have_titles:
                        continue
                    st_status = st.status if st.status in _STATUSES else "pending"
                    await c.execute(
                        "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,task_type,"
                        " department,department_id,week_id,week_start,created_by,updated_by)"
                        " VALUES ($1,$2,$3,$4,$5,$6,'medium',$7,$8,$9,$10,$11,$12,$12)",
                        actor["org_id"], owner_id, task_id, st.title, st.description, st_status, t.task_type,
                        dept_code, dept_id, week_id, t.week_start, actor["id"])
                    have_titles.add(st.title)
        except Exception as e:
            skipped.append({"external_ref": t.external_ref, "reason": f"db error: {type(e).__name__}"})

    return {"ok": True, "created": created, "updated": updated,
            "sessions_added": sessions_added, "skipped": skipped,
            "prompt_version": (body.session_meta or {}).get("prompt_version")}
