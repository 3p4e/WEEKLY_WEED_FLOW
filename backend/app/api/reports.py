"""Weekly report + plan — Fri→Thu rolling window with activity time band.

Report mode: tasks that had activity (created, updated, completed, or received
progress notes) during the Fri→Thu window. Includes a 7-day time band bucketed
by hour from real task_progress timestamps — no fabrication.

Plan mode: active/incomplete tasks that carry forward into the next week.
"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.db import rls
from app.deps import require_password_set

router = APIRouter(prefix="/reports", tags=["reports"])


def _fri_thu(ref: date) -> tuple[date, date]:
    """Return the Friday→Thursday window containing *ref*."""
    days_since_fri = (ref.weekday() - 4) % 7
    fri = ref - timedelta(days=days_since_fri)
    return fri, fri + timedelta(days=6)


def _num(v) -> float:
    if v is None:
        return 0.0
    return float(v) if isinstance(v, Decimal) else float(v)


def _task_row(r) -> dict:
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "description": r["description"] or "",
        "status": r["status"],
        "priority": r["priority"],
        "department": r["department"],
        "department_id": str(r["department_id"]) if r["department_id"] else None,
        "completed_date": r["completed_date"].isoformat() if r["completed_date"] else None,
        "estimated_hours": _num(r["estimated_hours"]),
        "actual_hours": _num(r["actual_hours"]),
        "days": list(r["days"] or []),
        "tags": list(r["tags"] or []),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


_COLS = (
    "t.id, t.title, t.description, t.status, t.priority, "
    "t.department, t.department_id, t.week_start, t.completed_date, "
    "t.estimated_hours, t.actual_hours, t.days, t.tags, "
    "t.created_at, t.updated_at"
)


@router.get("/weekly")
async def weekly_report(
    mode: str = Query("report", pattern="^(report|plan)$"),
    ref_date: str | None = None,
    department_id: str | None = None,
    user: dict = Depends(require_password_set),
):
    ref = date.fromisoformat(ref_date) if ref_date else date.today()
    fri, thu = _fri_thu(ref)

    if mode == "plan":
        fri = fri + timedelta(days=7)
        thu = thu + timedelta(days=7)

    async with rls(user) as c:
        if mode == "report":
            args: list = [fri, thu]
            dept_clause = ""
            if department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false{dept_clause} "
                f"AND ("
                f"  (t.created_at >= $1::date AND t.created_at < ($2::date + 1))"
                f"  OR (t.updated_at >= $1::date AND t.updated_at < ($2::date + 1))"
                f"  OR (t.completed_date >= $1 AND t.completed_date <= $2)"
                f"  OR EXISTS (SELECT 1 FROM task_progress tp "
                f"             WHERE tp.task_id=t.id "
                f"             AND tp.created_at >= $1::date AND tp.created_at < ($2::date + 1))"
                f") "
                f"ORDER BY CASE WHEN t.status IN ('completed','done') THEN 1 ELSE 0 END, "
                f"t.priority DESC, t.created_at",
                *args,
            )

            events = await c.fetch(
                "SELECT created_at FROM task_progress "
                "WHERE created_at >= $1::date AND created_at < ($2::date + 1) "
                "ORDER BY created_at",
                fri, thu,
            )

            buckets: dict[str, list[int]] = {}
            for d in range(7):
                day = fri + timedelta(days=d)
                buckets[day.isoformat()] = [0] * 24
            for ev in events:
                ts = ev["created_at"]
                if ts is None:
                    continue
                dk = ts.date().isoformat()
                if dk in buckets:
                    buckets[dk][ts.hour] += 1

            time_band = []
            for d in range(7):
                day = fri + timedelta(days=d)
                time_band.append({
                    "date": day.isoformat(),
                    "dow": day.weekday(),
                    "day_name": day.strftime("%a"),
                    "hours": buckets[day.isoformat()],
                })
        else:
            args = []
            dept_clause = ""
            if department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false AND t.is_archived=false{dept_clause} "
                f"AND t.status NOT IN ('completed','done') "
                f"ORDER BY t.priority DESC, t.department, t.created_at",
                *args,
            )
            time_band = []

    tasks_out = [_task_row(r) for r in rows]

    statuses: dict[str, int] = {}
    est_h, act_h = 0.0, 0.0
    for t in tasks_out:
        s = t["status"] or "pending"
        statuses[s] = statuses.get(s, 0) + 1
        est_h += t["estimated_hours"]
        act_h += t["actual_hours"]

    dept_map: dict[str, dict] = {}
    for t in tasks_out:
        dn = t["department"] or "Unassigned"
        if dn not in dept_map:
            dept_map[dn] = {"name": dn, "total": 0, "completed": 0}
        dept_map[dn]["total"] += 1
        if t["status"] in ("completed", "done"):
            dept_map[dn]["completed"] += 1

    iso_week = fri.isocalendar()[1]
    return {
        "period": {
            "start": fri.isoformat(),
            "end": thu.isoformat(),
            "label": (
                f"W{iso_week} {fri.year} "
                f"({fri.strftime('%a %b %d')} → {thu.strftime('%a %b %d')})"
            ),
        },
        "mode": mode,
        "summary": {
            "total": len(tasks_out),
            "completed": statuses.get("completed", 0) + statuses.get("done", 0),
            "in_progress": statuses.get("ongoing", 0) + statuses.get("in_progress", 0),
            "stuck": statuses.get("stuck", 0),
            "pending": statuses.get("pending", 0),
            "review": statuses.get("review", 0),
            "estimated_hours": round(est_h, 1),
            "actual_hours": round(act_h, 1),
        },
        "departments": sorted(dept_map.values(), key=lambda x: x["total"], reverse=True),
        "tasks": tasks_out,
        "time_band": time_band,
    }
