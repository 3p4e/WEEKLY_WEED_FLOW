"""Executive analytics (PR-C) — role-gated to executive/admin.

Two surfaces over the *whole organisation's* week:
  * GET  /planner/exec/telemetry — deterministic org-wide rollups (per dept, per user).
  * POST /planner/exec/insights  — the headline AI analytics agent: summaries, stats and
    foresight over all users' submitted weekly reports (+ recent weeks for trend), grounded
    by a pgvector retrieval when report embeddings exist. Degrades gracefully (available=False)
    when the Letta gateway is unconfigured/unreachable.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    ExecDeptStat,
    ExecInsight,
    ExecTelemetry,
    ExecUserStat,
)

from ..audit import record_event
from ..auth_deps import CurrentUser, require_role
from ..db import get_session
from ..gateway_client import GatewayClient

router = APIRouter(
    prefix="/planner/exec",
    tags=["planner-exec"],
    dependencies=[Depends(require_role("executive", "admin"))],
)

_GATEWAY_OFF = "AI gateway not configured — org telemetry is shown; set PLANNER_GATEWAY_URL for AI analysis."
_DONE = "done"
_STATUSES = ("pending", "working", "review", "stuck", "postponed", "done")
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


async def _ai(agent: str, message: str, context: dict | None = None) -> dict | None:
    return await GatewayClient().invoke(agent, message, context)


@router.get("/telemetry", response_model=ExecTelemetry)
async def exec_telemetry(
    week_start: date, session: AsyncSession = Depends(get_session)
) -> ExecTelemetry:
    rows = (
        await session.execute(
            text("SELECT status, days, owner_id FROM planner_task WHERE week_start = :ws"),
            {"ws": week_start},
        )
    ).mappings().all()
    total = len(rows)
    by_status = {s: 0 for s in _STATUSES}
    day_counts = {d: 0 for d in _DAYS}
    owners: set[str] = set()
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        for d in r["days"] or []:
            if d in day_counts:
                day_counts[d] += 1
        if r["owner_id"]:
            owners.add(str(r["owner_id"]))
    completion = round((by_status.get(_DONE, 0) / total) * 100) if total else 0
    busiest = max(day_counts.items(), key=lambda kv: kv[1])[0] if total else None

    dept_rows = (
        await session.execute(
            text(
                "SELECT d.id, d.key, d.name_en, d.name_mk, "
                "count(t.id) AS total, "
                "count(t.id) FILTER (WHERE t.status = 'done') AS done, "
                "count(t.id) FILTER (WHERE t.status = 'stuck') AS stuck "
                "FROM planner_department d "
                "LEFT JOIN planner_task t ON t.department_id = d.id AND t.week_start = :ws "
                "GROUP BY d.id, d.key, d.name_en, d.name_mk, d.position "
                "HAVING count(t.id) > 0 ORDER BY d.position"
            ),
            {"ws": week_start},
        )
    ).mappings().all()
    by_department = [
        ExecDeptStat(
            dept_id=str(r["id"]), dept_key=r["key"], name_en=r["name_en"], name_mk=r["name_mk"],
            total=r["total"], done=r["done"], stuck=r["stuck"],
            completion=round((r["done"] / r["total"]) * 100) if r["total"] else 0,
        )
        for r in dept_rows
    ]

    user_rows = (
        await session.execute(
            text(
                "SELECT u.id, u.full_name, dk.key AS dept_key, "
                "count(t.id) AS total, count(t.id) FILTER (WHERE t.status = 'done') AS done "
                "FROM planner_task t JOIN app_user u ON u.id = t.owner_id "
                "LEFT JOIN planner_department dk ON dk.id = u.dept_id "
                "WHERE t.week_start = :ws "
                "GROUP BY u.id, u.full_name, dk.key ORDER BY count(t.id) DESC"
            ),
            {"ws": week_start},
        )
    ).mappings().all()
    by_user = [
        ExecUserStat(
            user_id=str(r["id"]), user_name=r["full_name"], dept_key=r["dept_key"],
            total=r["total"], done=r["done"],
            completion=round((r["done"] / r["total"]) * 100) if r["total"] else 0,
        )
        for r in user_rows
    ]

    submitted = (
        await session.execute(
            text(
                "SELECT count(*) FROM planner_weekly_report "
                "WHERE week_start = :ws AND status = 'submitted'"
            ),
            {"ws": week_start},
        )
    ).scalar_one()

    return ExecTelemetry(
        week_start=week_start,
        total=total,
        completion=completion,
        by_status=by_status,
        busiest_day=busiest,
        headcount=len(owners),
        reports_submitted=int(submitted),
        by_department=by_department,
        by_user=by_user,
    )


@router.post("/insights", response_model=ExecInsight)
async def exec_insights(
    week_start: date,
    user: CurrentUser = Depends(require_role("executive", "admin")),
    session: AsyncSession = Depends(get_session),
) -> ExecInsight:
    # This week's submitted reports + the prior 4 weeks for trend/foresight.
    since = week_start - timedelta(days=28)
    reports = (
        await session.execute(
            text(
                "SELECT u.full_name AS user_name, r.week_start, r.completed_summary, "
                "r.progress_summary, r.next_week_plan "
                "FROM planner_weekly_report r JOIN app_user u ON u.id = r.user_id "
                "WHERE r.status = 'submitted' AND r.week_start BETWEEN :since AND :ws "
                "ORDER BY r.week_start DESC, u.full_name"
            ),
            {"since": since, "ws": week_start},
        )
    ).mappings().all()
    sources = [f"{r['user_name']} · {r['week_start']}" for r in reports]

    payload = {
        "week_start": str(week_start),
        "reports": [
            {
                "user": r["user_name"],
                "week_start": str(r["week_start"]),
                "completed": r["completed_summary"],
                "progress": r["progress_summary"],
                "next_plan": r["next_week_plan"],
            }
            for r in reports
        ],
    }
    result = await _ai(
        "executive-analytics",
        "Produce the executive analysis JSON for this week using these reports and your memory.",
        payload,
    )
    if result is None:
        return ExecInsight(available=False, sources=sources, note=_GATEWAY_OFF)

    insight = ExecInsight(
        available=True,
        summary=result.get("summary"),
        highlights=list(result.get("highlights", [])),
        risks=list(result.get("risks", [])),
        foresight=result.get("foresight"),
        sources=sources,
    )
    await record_event(
        session,
        actor_id=user.id,
        action="ai_exec_insights",
        entity_type="weekly_report",
        entity_id=None,
        payload={"agent": "executive-analytics", "week_start": str(week_start), "report_count": len(reports)},
    )
    await session.commit()
    return insight
