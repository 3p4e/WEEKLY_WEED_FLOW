"""Weekly report + plan — Fri→Thu rolling window with activity time band.

Report mode: tasks that had activity (created, updated, completed, or received
progress notes / work sessions) during the Fri→Thu window. Includes:
  • a 7-day time band bucketed by hour from real task_progress AND
    work_session timestamps — no fabrication;
  • per-person hours split into regular / overtime / night / weekend from
    work_sessions (see app/worktime.py for the rules) — this is what makes
    the Thursday report actually evidence off-hours commitment;
  • overdue tasks (due_date passed, not completed);
  • a task_type breakdown.

Plan mode: active/incomplete tasks that carry forward into the next week.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tasks import _scope_clause
from app.api.weekwindow import TASK_COLS as _COLS
from app.api.weekwindow import activity_window_sql, fri_thu as _fri_thu, task_row as _task_row
from app.db import rls
from app.deps import dept_scope, require_password_set, uuid_or_422
from app.roles import ELEVATED_ROLES
from app.roster import roster
from app.worktime import facility_today, TZ, classify, session_hours

router = APIRouter(prefix="/reports", tags=["reports"])

# work_sessions/task_progress RLS is org-scoped only (no owner/assignee
# restriction like tasks_read), so a non-elevated caller must be filtered to
# their own rows here — otherwise the per-person hours and activity time
# band leak every colleague's sessions regardless of task visibility.
# app.roles.ELEVATED_ROLES is the single source of truth.
_ELEVATED = ELEVATED_ROLES

# "normal" is the wire value the GrowFlow UI sends for medium (see tasks.py's
# Priority literal + integrate.js P_OUT) — it must rank alongside "medium",
# not fall through to the ELSE tier below every real priority, or every
# default-priority task created in the UI sorts last in the weekly report.
_PRIORITY_RANK = ("CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
                  "WHEN 'medium' THEN 2 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END")


@router.get("/weekly")
async def weekly_report(
    mode: str = Query("report", pattern="^(report|plan)$"),
    ref_date: str | None = None,
    department_id: str | None = None,
    user: dict = Depends(require_password_set),
):
    # A caller-supplied department_id is bound straight into raw SQL against a
    # uuid column, so a non-uuid value would otherwise surface as an asyncpg
    # cast error -> 500. Validate up front (before the dept_scope override,
    # which only ever assigns a known-good uuid). None is a legitimate value
    # (org-wide) so it is skipped — uuid_or_422 would reject str(None).
    if department_id is not None:
        uuid_or_422(department_id, "department_id must be a uuid")
    if ref_date:
        try:
            ref = date.fromisoformat(ref_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="ref_date must be ISO format YYYY-MM-DD")
    else:
        ref = facility_today()
    fri, thu = _fri_thu(ref)

    if mode == "plan":
        fri = fri + timedelta(days=7)
        thu = thu + timedelta(days=7)

    # A dept-scoped manager's report/plan covers ONLY their department — the
    # existing department_id filter is forced to theirs regardless of what the
    # caller passed. Executives / QP / ADMIN keep free choice (org-wide or any
    # single department).
    scope = dept_scope(user)
    if scope:
        department_id = scope

    hours_by_person: dict[str, dict] = {}
    overdue: list[dict] = []

    async with rls(user) as c:
        # Resolve the department breakdown by the canonical department_id → name,
        # not the denormalized free-text `department` column (which historically
        # stored codes and could split one department across code/name variants).
        dept_names = {str(r["id"]): r["name"] for r in await c.fetch("SELECT id, name FROM departments")}
        if mode == "report":
            # $3 = TZ.key (e.g. "Europe/Skopje"): every timestamptz column is
            # converted to facility-local wall-clock time BEFORE comparing
            # against the plain fri/thu dates below — otherwise Postgres
            # resolves the date casts in the session's (UTC) TimeZone GUC,
            # miscounting events within ~1-3 hours of local midnight into the
            # wrong day/week. completed_date is already a plain `date` column
            # (no timezone involved), so it's compared as-is.
            args: list = [fri, thu, TZ.key]
            # A dept-scoped manager's report must include the SAME task family
            # their board shows (own dept + personally owned/assigned + either
            # side of a cross-department delegation) — plain department_id
            # equality undercounts them relative to what /tasks already lets
            # them see. An org-wide caller's own explicit department_id choice
            # stays a plain filter (they're choosing to view one department,
            # not restricted to it).
            if scope:
                dept_clause = _scope_clause(user, args)
            elif department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            else:
                dept_clause = ""
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false{dept_clause} "
                f"AND {activity_window_sql('$1', '$2', '$3')} "
                f"ORDER BY CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END, "
                f"{_PRIORITY_RANK}, t.created_at",
                *args,
            )

            # Non-elevated callers only ever see their OWN sessions/notes here:
            # work_sessions/task_progress RLS is org-scoped only, not
            # owner/assignee-scoped like tasks_read, so without this filter a
            # regular user would get every colleague's hours and activity.
            elevated = user["role"] in _ELEVATED
            # Build the shared window/who/department scoping once so the events
            # feed and the per-person hours agree. department_id filters
            # task_progress/work_sessions by their task's department (neither
            # table carries department_id itself) — without it a dept-filtered
            # report mixed in every department's hours.
            # $3 = TZ.key: same facility-local-time conversion the main tasks
            # query above applies — without it these two feeds compare in the
            # session's (UTC) TimeZone GUC and miscount events within ~1-3h of
            # local midnight into the wrong day/week, so the report's task list
            # and its own hours/time-band would disagree near week boundaries.
            band_args: list = [fri, thu, TZ.key]
            who = ""
            if not elevated:
                band_args.append(user["id"]); who = f" AND user_id = ${len(band_args)}"
            if scope:
                dept_sub = f" AND task_id IN (SELECT t.id FROM tasks t WHERE true{_scope_clause(user, band_args)})"
            elif department_id:
                band_args.append(department_id)
                dept_sub = f" AND task_id IN (SELECT id FROM tasks WHERE department_id=${len(band_args)})"
            else:
                dept_sub = ""

            events = await c.fetch(
                "SELECT created_at AS at FROM task_progress "
                f"WHERE (created_at AT TIME ZONE $3) >= $1::date AND (created_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub} "
                "UNION ALL "
                "SELECT started_at AS at FROM work_sessions "
                f"WHERE (started_at AT TIME ZONE $3) >= $1::date AND (started_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub} "
                "ORDER BY at",
                *band_args,
            )

            # Per-person regular/overtime/night/weekend from work sessions.
            sess = await c.fetch(
                "SELECT user_id, started_at, ended_at, hours FROM work_sessions "
                f"WHERE (started_at AT TIME ZONE $3) >= $1::date AND (started_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub}",
                *band_args,
            )
            for s in sess:
                uid = str(s["user_id"])
                b = hours_by_person.setdefault(
                    uid, {"user_id": uid, "regular": 0.0, "overtime": 0.0,
                          "night": 0.0, "weekend": 0.0, "total": 0.0})
                h = session_hours(s)
                b[classify(s["started_at"])] += h
                b["total"] += h

            # A task due later THIS SAME week isn't overdue yet — clamp the
            # cutoff to real "today" when the report covers a week still in
            # progress (thu+1 is in the future), matching the per-op overdue
            # semantics used elsewhere in this file (due_date < today).
            # Viewing a past week's report is unaffected (thu+1 <= today there).
            over_args: list = [min(facility_today(), thu + timedelta(days=1))]
            if scope:
                over_clause = _scope_clause(user, over_args)
            elif department_id:
                over_args.append(department_id)
                over_clause = " AND t.department_id=$2"
            else:
                over_clause = ""
            over_rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false AND t.is_archived=false{over_clause} "
                f"AND t.due_date IS NOT NULL AND t.due_date < $1 "
                f"AND t.status <> 'completed' ORDER BY t.due_date",
                *over_args,
            )
            overdue = [_task_row(r) for r in over_rows]

            buckets: dict[str, list[int]] = {}
            for d in range(7):
                day = fri + timedelta(days=d)
                buckets[day.isoformat()] = [0] * 24
            for ev in events:
                ts = ev["at"]
                if ts is None:
                    continue
                local = ts.astimezone(TZ)
                dk = local.date().isoformat()
                if dk in buckets:
                    buckets[dk][local.hour] += 1

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
            if scope:
                dept_clause = _scope_clause(user, args)
            elif department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            else:
                dept_clause = ""
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false AND t.is_archived=false{dept_clause} "
                f"AND t.status <> 'completed' "
                f"ORDER BY {_PRIORITY_RANK}, t.department, t.created_at",
                *args,
            )
            time_band = []

    # Attach names to per-person hours (usernames live in the users database).
    if hours_by_person:
        names = await roster(user)
        for uid, b in hours_by_person.items():
            p = names.get(uid) or {}
            b["username"] = p.get("username")
            b["full_name"] = p.get("full_name")
            for k in ("regular", "overtime", "night", "weekend", "total"):
                b[k] = round(b[k], 2)

    tasks_out = [_task_row(r) for r in rows]

    statuses: dict[str, int] = {}
    types: dict[str, int] = {}
    est_h, act_h = 0.0, 0.0
    for t in tasks_out:
        s = t["status"] or "pending"
        statuses[s] = statuses.get(s, 0) + 1
        tt = t["task_type"] or "other"
        types[tt] = types.get(tt, 0) + 1
        est_h += t["estimated_hours"]
        act_h += t["actual_hours"]

    dept_map: dict[str, dict] = {}
    for t in tasks_out:
        dn = dept_names.get(str(t.get("department_id"))) or t["department"] or "Unassigned"
        if dn not in dept_map:
            dept_map[dn] = {"name": dn, "total": 0, "completed": 0}
        dept_map[dn]["total"] += 1
        if t["status"] == "completed":
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
            "completed": statuses.get("completed", 0),
            "in_progress": statuses.get("ongoing", 0),
            "stuck": statuses.get("stuck", 0),
            "pending": statuses.get("pending", 0),
            "review": statuses.get("review", 0),
            "postponed": statuses.get("postponed", 0),
            "estimated_hours": round(est_h, 1),
            "actual_hours": round(act_h, 1),
        },
        "task_types": types,
        "hours_by_person": sorted(hours_by_person.values(), key=lambda b: -b["total"]),
        "overdue": overdue,
        "departments": sorted(dept_map.values(), key=lambda x: x["total"], reverse=True),
        "tasks": tasks_out,
        "time_band": time_band,
    }


@router.get("/analytics")
async def analytics(
    weeks: int = Query(8, ge=4, le=16),
    user: dict = Depends(require_password_set),
):
    """Cross-week trends for managers and executives — task throughput,
    on-time delivery, activity, and a current department snapshot.

    Deliberately hour-free (owner: hour sums are not a meaningful metric
    here): weekly buckets count tasks and logged sessions, never durations.
    Buckets are the same Fri→Thu windows as the weekly report, oldest first,
    ending with the current window. Dept-scoped managers are pinned to their
    department exactly like /reports/weekly.
    """
    if user["role"] == "USER":
        raise HTTPException(status_code=403, detail="Managers and executives only")
    tz = str(TZ)
    today = facility_today()
    fri0, _ = _fri_thu(today)
    start = fri0 - timedelta(days=7 * (weeks - 1))
    # _scope_clause no-ops (returns "", appends nothing) for an org-wide caller
    # — same full membership clause as /reports/weekly, so a dept-scoped
    # manager's trends count the same task family their board and weekly
    # report do, not just tasks whose department_id happens to match theirs.

    async with rls(user) as c:
        created_args = [start, tz, weeks * 7]
        created_dept = _scope_clause(user, created_args)
        created = await c.fetch(
            "SELECT ((t.created_at AT TIME ZONE $2)::date - $1::date) / 7 AS wk, count(*) AS n"
            " FROM tasks t WHERE t.is_deleted=false"
            " AND (t.created_at AT TIME ZONE $2)::date >= $1"
            " AND (t.created_at AT TIME ZONE $2)::date < $1::date + $3::int" + created_dept +
            " GROUP BY 1",
            *created_args)
        completed_args = [start, weeks * 7]
        completed_dept = _scope_clause(user, completed_args)
        completed = await c.fetch(
            "SELECT (t.completed_date - $1::date) / 7 AS wk, count(*) AS n,"
            " count(*) FILTER (WHERE t.due_date IS NULL OR t.completed_date <= t.due_date) AS on_time"
            " FROM tasks t WHERE t.is_deleted=false"
            " AND t.completed_date >= $1 AND t.completed_date < $1::date + $2::int"
            + completed_dept +
            " GROUP BY 1",
            *completed_args)
        # Join through tasks so task-visibility RLS bounds what sessions are
        # counted (work_sessions RLS alone is org-wide — see /weekly's note).
        sessions_args = [start, tz, weeks * 7]
        sessions_dept = _scope_clause(user, sessions_args)
        sessions = await c.fetch(
            "SELECT ((ws.started_at AT TIME ZONE $2)::date - $1::date) / 7 AS wk,"
            " count(*) AS n, count(DISTINCT ws.user_id) AS people"
            " FROM work_sessions ws JOIN tasks t ON t.id = ws.task_id"
            " WHERE t.is_deleted=false"
            " AND (ws.started_at AT TIME ZONE $2)::date >= $1"
            " AND (ws.started_at AT TIME ZONE $2)::date < $1::date + $3::int" + sessions_dept +
            " GROUP BY 1",
            *sessions_args)
        dept_rows_args = [today, start]
        dept_rows_dept = _scope_clause(user, dept_rows_args)
        dept_rows = await c.fetch(
            "SELECT t.department_id,"
            " count(*) FILTER (WHERE t.status <> 'completed') AS open,"
            " count(*) FILTER (WHERE t.status = 'stuck') AS stuck,"
            " count(*) FILTER (WHERE t.status <> 'completed' AND t.due_date < $1) AS overdue,"
            " count(*) FILTER (WHERE t.status = 'completed' AND t.completed_date >= $2) AS completed"
            " FROM tasks t WHERE t.is_deleted=false AND t.is_archived=false"
            + dept_rows_dept +
            " GROUP BY 1",
            *dept_rows_args)
        types_args: list = []
        types_dept = _scope_clause(user, types_args)
        types = await c.fetch(
            "SELECT t.task_type, count(*) AS n FROM tasks t"
            " WHERE t.is_deleted=false AND t.is_archived=false AND t.status <> 'completed'"
            + types_dept +
            " GROUP BY 1 ORDER BY 2 DESC",
            *types_args)
        dept_names = {str(r["id"]): {"code": r["code"], "name": r["name"], "name_mk": r["name_mk"]}
                      for r in await c.fetch("SELECT id, code, name, name_mk FROM departments")}

    c_by = {r["wk"]: r["n"] for r in created}
    d_by = {r["wk"]: (r["n"], r["on_time"]) for r in completed}
    s_by = {r["wk"]: (r["n"], r["people"]) for r in sessions}
    week_series = []
    for i in range(weeks):
        done, on_time = d_by.get(i, (0, 0))
        sess, people = s_by.get(i, (0, 0))
        week_series.append({
            "week_start": (start + timedelta(days=7 * i)).isoformat(),
            "created": c_by.get(i, 0), "completed": done, "on_time": on_time,
            "sessions": sess, "active_people": people,
        })

    departments = []
    for r in dept_rows:
        did = str(r["department_id"]) if r["department_id"] else None
        meta = dept_names.get(did, {})
        departments.append({
            "id": did, "code": meta.get("code"),
            "name": meta.get("name") or "—", "name_mk": meta.get("name_mk"),
            "open": r["open"], "stuck": r["stuck"], "overdue": r["overdue"],
            "completed": r["completed"],
        })
    departments.sort(key=lambda d: -d["open"])

    return {
        "range": {"start": start.isoformat(), "end": (fri0 + timedelta(days=6)).isoformat(),
                  "weeks": weeks},
        "weeks": week_series,
        "departments": departments,
        "task_types": [{"task_type": r["task_type"], "count": r["n"]} for r in types],
    }


# Canonical GMP audit-preparation programs, tracked as task TAGS (not dedicated
# tables) — the SUMA/ISO17verSUMA ADR-001 decision, assimilated here: SOP and
# audit-prep work is just tagged tasks, and filtering by tag gives a dedicated
# readiness view without new schema. Overridable per call via ?programs=.
_AUDIT_PROGRAMS = ("MK-GMP", "EU-GMP", "SOP-writing")
# tasks.days carries Mon..Sun tokens (see tasks.py _DAY_TOKENS); this fixes the
# display/rollup order so "busiest day" is deterministic and week-ordered.
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@router.get("/audit-prep")
async def audit_prep(
    programs: str | None = Query(None, description="comma-separated tag names; defaults to the GMP set"),
    department_id: str | None = None,
    user: dict = Depends(require_password_set),
):
    """GMP audit-preparation readiness — assimilated from the SUMA executive
    dashboard's "GMP & SOP Preparation Tracker" + "Audit Preparation Timeline".

    Per-program completion over tasks tagged MK-GMP / EU-GMP / SOP-writing
    (configurable via ?programs=), a due-date milestone timeline, and planning
    telemetry (status distribution, busiest scheduled day, outcome-traceability
    sanity check). This is a PLANNING aid over the existing tasks.tags facet —
    NOT a controlled record; the QMS/DocEngine zone owns audit deliverables
    (per SUMA ADR-001 §2 and docs/SCOPE.md's two-zone statement).

    Dept-scoped managers are pinned to their own department exactly like
    /reports/analytics; base USER is refused.
    """
    if user["role"] == "USER":
        raise HTTPException(status_code=403, detail="Managers and executives only")
    # Same guard as /reports/weekly: a non-uuid department_id is bound into raw
    # SQL as ::uuid below and would 500 without this. None (org-wide) is fine.
    if department_id is not None:
        uuid_or_422(department_id, "department_id must be a uuid")
    if programs:
        progs = [p.strip() for p in programs.split(",") if p.strip()]
        if len(progs) > 12:
            raise HTTPException(status_code=422, detail="programs: at most 12")
        if any(len(p) > 64 for p in progs):
            raise HTTPException(status_code=422, detail="programs: each at most 64 chars")
    else:
        progs = list(_AUDIT_PROGRAMS)
    if not progs:
        progs = list(_AUDIT_PROGRAMS)

    today = facility_today()
    # Dept-scoped managers are forced to their department; execs/QP/ADMIN keep
    # free choice — same rule as /reports/weekly and /reports/analytics.
    scope = dept_scope(user)
    if scope:
        department_id = scope

    def _dept_filter(args: list) -> str:
        """Same clause selection /reports/weekly makes for its own queries: a
        dept-scoped manager gets the full _scope_clause family-visibility
        predicate (own dept OR personally owned/assigned OR either side of a
        cross-department delegation) — a plain `department_id =` equality
        silently dropped their own audit-prep tasks living in another
        department, and subtasks delegated to them cross-department, from
        every readiness number below, contradicting this endpoint's own
        docstring ("pinned to their own department exactly like
        /reports/analytics"). An org-wide caller's own explicit
        ?department_id= choice stays a plain filter — same as weekly/
        analytics, they're choosing to view one department, not restricted
        to it. Appends its own bind params to `args`, same calling
        convention as _scope_clause itself."""
        if scope:
            return _scope_clause(user, args)
        if department_id:
            args.append(department_id)
            return f" AND t.department_id=${len(args)}::uuid"
        return ""

    async with rls(user) as c:
        # Per-program readiness. unnest($1) LEFT JOIN tasks so a program with
        # zero matching tasks still returns a row (total 0) rather than
        # silently vanishing from the tracker. $2=today (overdue).
        prog_args = [progs, today]
        prog_dept = _dept_filter(prog_args)
        prog_rows = await c.fetch(
            "SELECT p.prog,"
            " count(t.id) AS total,"
            " count(t.id) FILTER (WHERE t.status='completed') AS completed,"
            " count(t.id) FILTER (WHERE t.status='ongoing') AS ongoing,"
            " count(t.id) FILTER (WHERE t.status='review') AS review,"
            " count(t.id) FILTER (WHERE t.status='stuck') AS stuck,"
            " count(t.id) FILTER (WHERE t.status='postponed') AS postponed,"
            " count(t.id) FILTER (WHERE t.status='pending') AS pending,"
            " count(t.id) FILTER (WHERE t.status<>'completed' AND t.due_date IS NOT NULL"
            "   AND t.due_date < $2) AS overdue"
            " FROM unnest($1::text[]) AS p(prog)"
            " LEFT JOIN tasks t ON p.prog = ANY(t.tags)"
            "   AND t.is_deleted=false AND t.is_archived=false"
            + prog_dept +
            " GROUP BY p.prog",
            *prog_args)

        # Milestone timeline — every program-tagged task carrying a due_date,
        # soonest first. $1=programs. overdue computed in Python.
        tl_args = [progs]
        tl_dept = _dept_filter(tl_args)
        tl_rows = await c.fetch(
            "SELECT t.id, t.title, t.status, t.due_date, t.tags, t.department_id"
            " FROM tasks t"
            " WHERE t.is_deleted=false AND t.is_archived=false"
            "   AND t.due_date IS NOT NULL AND t.tags && $1::text[]"
            + tl_dept +
            " ORDER BY t.due_date, t.created_at LIMIT 200",
            *tl_args)

        # Status distribution across the whole audit-prep task set.
        status_args = [progs]
        status_dept = _dept_filter(status_args)
        status_rows = await c.fetch(
            "SELECT t.status, count(*) AS n FROM tasks t"
            " WHERE t.is_deleted=false AND t.is_archived=false AND t.tags && $1::text[]"
            + status_dept +
            " GROUP BY t.status",
            *status_args)

        # Busiest scheduled day — unnest the days[] tags over the audit-prep set.
        day_args = [progs]
        day_dept = _dept_filter(day_args)
        day_rows = await c.fetch(
            "SELECT d AS day, count(*) AS n FROM tasks t, unnest(t.days) AS d"
            " WHERE t.is_deleted=false AND t.is_archived=false AND t.tags && $1::text[]"
            + day_dept +
            " GROUP BY d",
            *day_args)

        # Outcome-traceability sanity check — completed audit-prep tasks that
        # carry an outcome vs those left blank. A PLANNING nudge (SUMA's
        # "Outcome Traceability" / detectAnomalies), explicitly not a GMP gate.
        trace_args = [progs]
        trace_dept = _dept_filter(trace_args)
        trace = await c.fetchrow(
            "SELECT count(*) AS completed,"
            " count(*) FILTER (WHERE t.outcome IS NOT NULL AND btrim(t.outcome) <> '') AS with_outcome"
            " FROM tasks t"
            " WHERE t.is_deleted=false AND t.is_archived=false"
            "   AND t.status='completed' AND t.tags && $1::text[]"
            + trace_dept,
            *trace_args)

    by_prog = {r["prog"]: r for r in prog_rows}
    programs_out = []
    for p in progs:
        r = by_prog.get(p)
        total = r["total"] if r else 0
        done = r["completed"] if r else 0
        programs_out.append({
            "program": p, "total": total, "completed": done,
            "ongoing": r["ongoing"] if r else 0, "review": r["review"] if r else 0,
            "stuck": r["stuck"] if r else 0, "postponed": r["postponed"] if r else 0,
            "pending": r["pending"] if r else 0, "overdue": r["overdue"] if r else 0,
            "completion_rate": round(done / total, 4) if total else 0.0,
        })

    prog_set = set(progs)
    timeline = [{
        "id": str(r["id"]), "title": r["title"], "status": r["status"],
        "due_date": r["due_date"].isoformat(),
        "overdue": r["status"] != "completed" and r["due_date"] < today,
        "programs": [t for t in (r["tags"] or []) if t in prog_set],
    } for r in tl_rows]

    status_distribution = {r["status"]: r["n"] for r in status_rows}
    day_distribution = {d: 0 for d in _DOW}
    for r in day_rows:
        if r["day"] in day_distribution:
            day_distribution[r["day"]] = r["n"]
    busiest = max(_DOW, key=lambda d: day_distribution[d])
    busiest_day = ({"day": busiest, "count": day_distribution[busiest]}
                   if day_distribution[busiest] else None)

    comp = trace["completed"] if trace else 0
    with_o = trace["with_outcome"] if trace else 0
    traceability = {
        "completed": comp, "with_outcome": with_o, "without_outcome": comp - with_o,
        "rate": round(with_o / comp, 4) if comp else 0.0,
    }

    return {
        "as_of": today.isoformat(),
        "department_id": str(department_id) if department_id else None,
        "programs": programs_out,
        "timeline": timeline,
        "status_distribution": status_distribution,
        "day_distribution": day_distribution,
        "busiest_day": busiest_day,
        "traceability": traceability,
    }
