"""Planner weekly reports + core AI (PR-B).

Each user keeps one report per week (completed / progress / next-week plan). Reports can be
AI-drafted via the Letta gateway and are submitted after human review. Every AI call degrades
gracefully when the gateway is unconfigured or unreachable (returns available=False, HTTP 200 —
the planner stays fully usable) and successful AI generations + submissions are written to the
hash-chained audit trail.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    AiDraftResult,
    PlannerWeeklyReport,
    PlannerWeeklyReportUpdate,
    RewriteRequest,
    RewriteResult,
    RolloverResult,
)

from ..audit import record_event
from ..auth_deps import CurrentUser, get_current_user
from ..db import get_session
from ..gateway_client import GatewayClient

router = APIRouter(
    prefix="/planner",
    tags=["planner-reports"],
    dependencies=[Depends(get_current_user)],
)

_GATEWAY_OFF = "AI gateway not configured — write the report manually (set PLANNER_GATEWAY_URL to enable AI)."

_REPORT_SELECT = (
    "SELECT r.id, r.user_id, u.full_name AS user_name, r.week_start, r.completed_summary, "
    "r.progress_summary, r.next_week_plan, r.status, r.ai_generated, r.submitted_at, "
    "r.created_at, r.updated_at "
    "FROM planner_weekly_report r JOIN app_user u ON u.id = r.user_id "
)


# --------------------------------------------------------------------------- #
# AI helper — single choke point for graceful degradation (planner -> gateway -> Letta)
# --------------------------------------------------------------------------- #
async def _ai(agent: str, message: str, context: dict | None = None) -> dict | None:
    return await GatewayClient().invoke(agent, message, context)


def _row_to_report(r) -> PlannerWeeklyReport:
    return PlannerWeeklyReport(
        id=str(r["id"]),
        user_id=str(r["user_id"]),
        user_name=r["user_name"],
        week_start=r["week_start"],
        completed_summary=r["completed_summary"],
        progress_summary=r["progress_summary"],
        next_week_plan=r["next_week_plan"],
        status=r["status"],
        ai_generated=r["ai_generated"],
        submitted_at=r["submitted_at"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


async def _fetch(session: AsyncSession, user_id: str, week_start: date):
    return (
        await session.execute(
            text(_REPORT_SELECT + "WHERE r.user_id = :u AND r.week_start = :w"),
            {"u": user_id, "w": week_start},
        )
    ).mappings().first()


# --------------------------------------------------------------------------- #
# Report read / upsert
# --------------------------------------------------------------------------- #
@router.get("/reports", response_model=PlannerWeeklyReport)
async def get_report(
    week_start: date,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlannerWeeklyReport:
    row = await _fetch(session, user.id, week_start)
    if row is not None:
        return _row_to_report(row)
    # Transient (unsaved) draft so the UI always has something to render.
    return PlannerWeeklyReport(id="", user_id=user.id, user_name=user.full_name, week_start=week_start)


async def _upsert(
    session: AsyncSession, user_id: str, week_start: date, body: PlannerWeeklyReportUpdate,
    *, ai_generated: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO planner_weekly_report "
            "(user_id, week_start, completed_summary, progress_summary, next_week_plan, ai_generated) "
            "VALUES (:u, :w, :c, :p, :n, :ai) "
            "ON CONFLICT (user_id, week_start) DO UPDATE SET "
            "completed_summary = EXCLUDED.completed_summary, "
            "progress_summary = EXCLUDED.progress_summary, "
            "next_week_plan = EXCLUDED.next_week_plan, "
            "ai_generated = planner_weekly_report.ai_generated OR EXCLUDED.ai_generated, "
            "updated_at = now()"
        ),
        {
            "u": user_id, "w": week_start, "c": body.completed_summary,
            "p": body.progress_summary, "n": body.next_week_plan, "ai": ai_generated,
        },
    )


@router.put("/reports", response_model=PlannerWeeklyReport)
async def save_report(
    week_start: date,
    body: PlannerWeeklyReportUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlannerWeeklyReport:
    existing = await _fetch(session, user.id, week_start)
    if existing is not None and existing["status"] == "submitted":
        raise HTTPException(status_code=409, detail="report already submitted")
    await _upsert(session, user.id, week_start, body)
    await session.commit()
    return _row_to_report(await _fetch(session, user.id, week_start))


@router.post("/reports/submit", response_model=PlannerWeeklyReport)
async def submit_report(
    week_start: date,
    body: PlannerWeeklyReportUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlannerWeeklyReport:
    await _upsert(session, user.id, week_start, body)
    await session.execute(
        text(
            "UPDATE planner_weekly_report SET status = 'submitted', "
            "submitted_at = COALESCE(submitted_at, now()), updated_at = now() "
            "WHERE user_id = :u AND week_start = :w"
        ),
        {"u": user.id, "w": week_start},
    )
    row = await _fetch(session, user.id, week_start)
    await record_event(
        session,
        actor_id=user.id,
        action="submit",
        entity_type="weekly_report",
        entity_id=str(row["id"]),
        payload={"week_start": str(week_start), "user": user.username, "ai_generated": row["ai_generated"]},
    )
    await session.commit()
    # Persist the report into the executive agent's durable Letta memory (best-effort, post-commit).
    await GatewayClient().record_exec_report({
        "week_start": str(week_start),
        "user": user.full_name,
        "completed": row["completed_summary"],
        "progress": row["progress_summary"],
        "next_plan": row["next_week_plan"],
    })
    return _row_to_report(row)


# --------------------------------------------------------------------------- #
# AI: weekly-report draft, task/note rewrite
# --------------------------------------------------------------------------- #
@router.post("/reports/ai-draft", response_model=AiDraftResult)
async def ai_draft(
    week_start: date,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AiDraftResult:
    tasks = (
        await session.execute(
            text(
                "SELECT title, status, priority, blocker, days FROM planner_task "
                "WHERE owner_id = :u AND week_start = :w ORDER BY status"
            ),
            {"u": user.id, "w": week_start},
        )
    ).mappings().all()
    context = {
        "week_start": str(week_start),
        "user": user.full_name,
        "tasks": [dict(t) for t in tasks],
    }
    result = await _ai("weekly-report", "Draft my weekly report from these tasks.", context)
    if result is None:
        return AiDraftResult(available=False, note=_GATEWAY_OFF)

    draft = AiDraftResult(
        available=True,
        completed_summary=result.get("completed_summary"),
        progress_summary=result.get("progress_summary"),
        next_week_plan=result.get("next_week_plan"),
    )
    await record_event(
        session,
        actor_id=user.id,
        action="ai_draft",
        entity_type="weekly_report",
        entity_id=None,
        payload={"agent": "weekly-report", "week_start": str(week_start), "task_count": len(tasks)},
    )
    await session.commit()
    return draft


@router.post("/ai/rewrite", response_model=RewriteResult)
async def ai_rewrite(
    body: RewriteRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RewriteResult:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text is required")
    result = await _ai("task-rewrite", f"Rewrite in a {body.tone} tone:\n{body.text}", {"tone": body.tone})
    if result is None or not result.get("text"):
        return RewriteResult(available=False, text=body.text, note=_GATEWAY_OFF)
    await record_event(
        session,
        actor_id=user.id,
        action="ai_rewrite",
        entity_type="task",
        entity_id=None,
        payload={"agent": "task-rewrite", "tone": body.tone},
    )
    await session.commit()
    return RewriteResult(available=True, text=result["text"])


# --------------------------------------------------------------------------- #
# Roll over unfinished tasks into next week
# --------------------------------------------------------------------------- #
@router.post("/reports/rollover", response_model=RolloverResult)
async def rollover(
    week_start: date,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RolloverResult:
    target = week_start + timedelta(days=7)
    res = await session.execute(
        text(
            "INSERT INTO planner_task "
            "(department_id, title, owner_id, status, priority, week_start, days, room, batch, "
            " tags, description, created_by) "
            "SELECT department_id, title, owner_id, 'pending', priority, :target, days, room, batch, "
            " tags, description, :actor "
            "FROM planner_task src "
            "WHERE src.owner_id = :u AND src.week_start = :w AND src.status <> 'done' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM planner_task dst "
            "  WHERE dst.owner_id = src.owner_id AND dst.week_start = :target AND dst.title = src.title"
            ") RETURNING id"
        ),
        {"target": target, "actor": user.id, "u": user.id, "w": week_start},
    )
    created = len(res.fetchall())
    await session.commit()
    return RolloverResult(created=created, target_week=target)
