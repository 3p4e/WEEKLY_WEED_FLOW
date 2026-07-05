#!/usr/bin/env python3
"""Weekly snapshot job — the Thursday-14:00 report/plan generator.

Runs OUTSIDE the FastAPI app (standalone asyncpg, same pattern as
seed_e2e_org.py): connects with the BYPASSRLS admin DSN, so every query is
scoped to org_id explicitly. For each organization it:

  1. computes the current Fri->Thu work week (report) and next week (plan),
  2. gathers tasks / progress / assignments / hours in those windows,
  3. builds a RAG-friendly Markdown digest,
  4. asks the Letta planner agents for an org rollup + per-person weekly
     report and next-week plan,
  5. archives everything to the ai_pins table (org-scoped, week-linked),
  6. uploads the digest to the Letta RAG source so future AI calls have
     historical context.

Letta being unreachable never crashes a run: the DB snapshot + a
deterministic fallback body are always pinned. Kept dependency-light
(stdlib + asyncpg + httpx) and free of app.* imports so the pure helpers
are unit-testable without a DB or the config guard.

Usage:
  USERS_ADMIN_DATABASE_URL=... TASKS_ADMIN_DATABASE_URL=... python scripts/weekly_snapshot.py --once
  ... --ref-date 2026-07-02       # run as if "today" were this date
  ... --org-id <uuid>             # limit to one org
  ... --skip-letta                # DB-only (test/dry-run)
  ... --attach-source             # one-time: attach RAG source to coordinator
"""
import argparse
import asyncio
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

import sys

import asyncpg
import httpx

import planner_prompts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.worktime import classify, session_hours  # noqa: E402  (pure helpers, no config import)


# ── Config from env (no app.config dependency) ──────────────────────────────
# Two databases: identity (organizations/profiles) vs work data — see app/db.py.
USERS_ADMIN_DSN = os.environ.get("USERS_ADMIN_DATABASE_URL", "")
TASKS_ADMIN_DSN = os.environ.get("TASKS_ADMIN_DATABASE_URL", "")
LETTA_BASE_URL = os.environ.get("LETTA_BASE_URL", "http://host.docker.internal:8283")
LETTA_API_KEY = os.environ.get("LETTA_API_KEY", "")
SNAPSHOT_SOURCE_ID = os.environ.get(
    "LETTA_SNAPSHOT_SOURCE_ID", "source-7ad49834-0436-4f45-8214-7e1f7e3c9fa9")
SNAPSHOT_SOURCE_NAME = os.environ.get("LETTA_SNAPSHOT_SOURCE_NAME", "GrowFlow_Weekly_Snapshots")
COORDINATOR_AGENT_ID = os.environ.get("LETTA_COORDINATOR_AGENT_ID", "")
# Env fallbacks; primary is per-org ai_agent_bindings rows.
REPORT_AGENT_ID = os.environ.get("LETTA_WEEKLY_REPORT_AGENT_ID", "")
PLAN_AGENT_ID = os.environ.get("LETTA_NEXT_WEEK_PLAN_AGENT_ID", "")


def log(msg: str) -> None:
    print(f"[weekly_snapshot] {datetime.now(timezone.utc).isoformat()} {msg}", flush=True)


# ── Pure helpers (unit-testable, no I/O) ────────────────────────────────────
def fri_thu(ref: date) -> tuple[date, date]:
    """The Friday->Thursday window containing *ref* — mirrors
    app.api.reports._fri_thu (kept in sync; that endpoint is the source of
    truth for the app's report window)."""
    days_since_fri = (ref.weekday() - 4) % 7
    fri = ref - timedelta(days=days_since_fri)
    return fri, fri + timedelta(days=6)


def compute_windows(ref: date) -> tuple[tuple[date, date], tuple[date, date]]:
    """(report_window, plan_window). Report = the Fri->Thu window ending on
    (or containing) *ref* — correct when invoked Thursday 14:00. Plan = the
    next week (both dates +7)."""
    report = fri_thu(ref)
    plan = (report[0] + timedelta(days=7), report[1] + timedelta(days=7))
    return report, plan


def iso_week_label(fri: date, thu: date) -> str:
    # Week number from the FRIDAY, matching app.api.reports.weekly_report's
    # period label — a Fri->Thu window always straddles two ISO weeks, so
    # deriving from the Thursday would disagree with the in-app report by
    # one week, every week.
    return f"W{fri.isocalendar()[1]} {fri.year} ({fri.isoformat()} → {thu.isoformat()})"


def carry_over_weeks(created_at, window_end: date) -> int:
    """How many whole weeks an unfinished task has rolled past its creation."""
    d = created_at.date() if hasattr(created_at, "date") else created_at
    return max(0, (window_end - d).days // 7)


def _hrs(v) -> str:
    return "-" if v is None else f"{float(v):g}"


def _cite(task_id) -> str:
    return f"[task:{str(task_id)[:8]}]"


def _clean(text) -> str:
    """Collapse all whitespace (incl. newlines) in free text before it goes
    into a digest line. Titles are unrestricted user input; a newline in one
    would otherwise let a title fabricate its own markdown section — or
    collide with TASKS_HEADER below."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


# The heading that separates the digest's aggregate sections from the
# unbounded per-task list. process_org splits on this (newline-anchored) to
# build the size-bounded org-rollup prompt — keep the two in sync via this
# constant, never a literal.
TASKS_HEADER = "## Tasks this week"


def build_digest(snap: dict) -> str:
    """RAG-friendly Markdown from a gathered snapshot dict."""
    r = snap["report_window"]
    L: list[str] = []
    L.append(f"# GrowFlow Weekly Snapshot — {snap['org_name']} — {r['label']}")
    L.append("")
    L.append(f"Generated: {snap['generated_at']}  ·  Work week Fri→Thu  ·  "
             f"Source: weekly_snapshot (KVM4 WWF Postgres)")
    L.append("")

    tasks = snap["report_tasks"]
    done = sum(1 for t in tasks if t["status"] == "completed")
    L.append("## Totals")
    L.append(f"- Tasks active in window: {len(tasks)}")
    L.append(f"- Created this week: {snap['created_count']}")
    L.append(f"- Completed this week: {snap['completed_count']}")
    L.append(f"- Progress notes: {snap['notes_count']}  ·  Comments: {snap['comments_count']}")
    L.append(f"- Completion: {round(done / len(tasks) * 100) if tasks else 0}% ({done}/{len(tasks)})")
    L.append("")

    def _counter(key):
        c: dict[str, int] = {}
        for t in tasks:
            c[t[key] or "—"] = c.get(t[key] or "—", 0) + 1
        return c

    L.append("## By status")
    for s in ("completed", "ongoing", "review", "stuck", "postponed", "pending"):
        n = sum(1 for t in tasks if t["status"] == s)
        if n:
            L.append(f"- {s}: {n}")
    L.append("")
    L.append("## By priority")
    for p, n in sorted(_counter("priority").items(), key=lambda kv: -kv[1]):
        L.append(f"- {p}: {n}")
    L.append("")
    L.append("## By department")
    for dpt, n in sorted(_counter("department").items(), key=lambda kv: -kv[1]):
        L.append(f"- {dpt}: {n}")
    L.append("")
    L.append("## By owner")
    for o, n in sorted(_counter("owner").items(), key=lambda kv: -kv[1]):
        L.append(f"- {o}: {n}")
    L.append("")

    # Hours actual vs estimated
    act = sum(float(t["actual_hours"]) for t in tasks if t["actual_hours"] is not None)
    est = sum(float(t["estimated_hours"]) for t in tasks if t["estimated_hours"] is not None)
    L.append("## Hours (actual / estimated)")
    L.append(f"- Org total: {act:g} / {est:g}")
    per_owner: dict[str, list[float]] = {}
    for t in tasks:
        o = t["owner"] or "—"
        pa, pe = per_owner.setdefault(o, [0.0, 0.0])
        per_owner[o] = [pa + float(t["actual_hours"] or 0), pe + float(t["estimated_hours"] or 0)]
    for o, (pa, pe) in per_owner.items():
        if pa or pe:
            L.append(f"- {o}: {pa:g} / {pe:g}")
    L.append("")

    # Time-class hours from logged work sessions — the overtime evidence.
    L.append("## Hours by time class (work sessions)")
    hbp = snap.get("hours_by_person") or {}
    if hbp:
        for o, b in sorted(hbp.items(), key=lambda kv: -kv[1]["total"]):
            L.append(f"- {o}: total {b['total']:g}h — regular {b['regular']:g}, "
                     f"overtime {b['overtime']:g}, night {b['night']:g}, weekend {b['weekend']:g}")
    else:
        L.append("- none logged")
    L.append("")

    L.append("## Overdue")
    if snap.get("overdue"):
        for o in snap["overdue"]:
            L.append(f"- {_cite(o['id'])} {_clean(o['title'])} — due {o['due_date']}, "
                     f"[{o['status']}, owner={o['owner']}]")
    else:
        L.append("- none")
    L.append("")

    # Carry-over aging
    aged = [t for t in snap["plan_tasks"] if t["carry_over_weeks"] > 0]
    L.append("## Carry-over aging (unfinished, rolled N weeks)")
    if aged:
        for t in sorted(aged, key=lambda x: -x["carry_over_weeks"]):
            L.append(f"- {_cite(t['id'])} {_clean(t['title'])} — rolled {t['carry_over_weeks']}w "
                     f"[{t['status']}, owner={t['owner']}]")
    else:
        L.append("- none")
    L.append("")

    # Blockers: stuck tasks + declined assignments
    L.append("## Blockers")
    stuck = [t for t in tasks if t["status"] == "stuck"]
    for t in stuck:
        L.append(f"- {_cite(t['id'])} {_clean(t['title'])} — STUCK, owner={t['owner']}")
    for a in snap["declined"]:
        L.append(f"- {_cite(a['task_id'])} {_clean(a['title'])} — assignment DECLINED by {a['username']}")
    if not stuck and not snap["declined"]:
        L.append("- none")
    L.append("")

    # Task lines with citations
    L.append(TASKS_HEADER)
    for t in tasks:
        done_s = f", done={t['completed_date']}" if t["completed_date"] else ""
        L.append(f"- {_cite(t['id'])} [{t['status']}/{t['priority']}] {_clean(t['title'])} "
                 f"(dept={t['department']}, owner={t['owner']}, "
                 f"hours={_hrs(t['actual_hours'])}/{_hrs(t['estimated_hours'])}{done_s})")
    L.append("")
    return "\n".join(L)


def _task_bullets(tasks: list[dict], limit: int = 120) -> str:
    out = []
    for t in tasks[:limit]:
        out.append(f"- {_cite(t['id'])} [{t['status']}/{t['priority']}] {_clean(t['title'])} "
                   f"(owner={t['owner']}, hours={_hrs(t['actual_hours'])}/{_hrs(t['estimated_hours'])})")
    return "\n".join(out)


def rollup_task_sample(tasks: list[dict], limit: int = 60) -> list[dict]:
    """A bounded, citation-worthy subset of the week's tasks for the org
    rollup prompt: everything stuck, then everything completed, then the
    rest in their existing (priority) order — so the agent can cite real
    [task:id] tokens for the claims its rules require, at constant prompt
    size regardless of org volume."""
    stuck = [t for t in tasks if t["status"] == "stuck"]
    done = [t for t in tasks if t["status"] == "completed"]
    rest = [t for t in tasks if t not in stuck and t not in done]
    seen, out = set(), []
    for t in stuck + done + rest:
        if t["id"] not in seen:
            seen.add(t["id"]); out.append(t)
        if len(out) >= limit:
            break
    return out


def _extract_json_field(raw: str, key: str) -> str | None:
    """Pull {"<key>": "..."} out of an agent reply; tolerate prose/fences."""
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and key in obj and obj[key]:
                return str(obj[key])
        except Exception:
            pass
    return None


# ── Letta REST helpers ──────────────────────────────────────────────────────
def _letta_headers() -> dict:
    return {"Authorization": f"Bearer {LETTA_API_KEY}"} if LETTA_API_KEY else {}


async def letta_message(client: httpx.AsyncClient, agent_id: str, text: str) -> str | None:
    try:
        r = await client.post(
            f"{LETTA_BASE_URL}/v1/agents/{agent_id}/messages",
            headers=_letta_headers(),
            json={"messages": [{"role": "user", "content": text}]},
        )
        r.raise_for_status()
        data = r.json()
        msgs = data.get("messages", data if isinstance(data, list) else [])
        for m in reversed(msgs):
            if m.get("message_type") in ("assistant_message", "tool_call_message") and m.get("content"):
                c = m["content"]
                return c if isinstance(c, str) else str(c)
        return None
    except Exception as e:
        log(f"letta_message failed for {agent_id}: {type(e).__name__}")
        return None


async def letta_upload_digest(client: httpx.AsyncClient, source_id: str, filename: str, md: str) -> bool:
    files = {"file": (filename, md.encode("utf-8"), "text/markdown")}
    for path in (f"/v1/sources/{source_id}/upload", f"/v1/folders/{source_id}/upload"):
        try:
            r = await client.post(LETTA_BASE_URL + path, headers=_letta_headers(), files=files)
            if r.status_code < 300:
                log(f"digest uploaded via {path}")
                return True
        except Exception:
            continue
    log("digest upload failed (all routes)")
    return False


async def letta_attach_source(client: httpx.AsyncClient, agent_id: str, source_id: str) -> bool:
    """Attach the RAG source (a.k.a. folder) to an agent. Self-hosted Letta
    versions differ on sources-vs-folders and PATCH-vs-POST — try each,
    treat 'already attached' as success."""
    routes = [
        ("PATCH", f"/v1/agents/{agent_id}/sources/attach/{source_id}"),
        ("PATCH", f"/v1/agents/{agent_id}/folders/attach/{source_id}"),
        ("POST", f"/v1/agents/{agent_id}/sources/attach/{source_id}"),
        ("POST", f"/v1/agents/{agent_id}/folders/attach/{source_id}"),
    ]
    for method, path in routes:
        try:
            r = await client.request(method, LETTA_BASE_URL + path, headers=_letta_headers())
            if r.status_code < 300 or "already" in (r.text or "").lower():
                log(f"source attached to {agent_id} via {method} {path} ({r.status_code})")
                return True
        except Exception:
            continue
    log(f"source attach to {agent_id} failed (all routes)")
    return False


async def _ensure_week(conn, org_id, day: date):
    """id of the ISO (Mon->Sun) calendar week containing *day*, creating the
    row if the org hasn't seeded that far ahead. ON CONFLICT DO UPDATE is a
    no-op field-set purely so RETURNING id works on the existing row."""
    iso_year, iso_week, _ = day.isocalendar()
    monday = day - timedelta(days=day.weekday())
    return await conn.fetchval(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on)"
        " VALUES ($1,$2,$3,$4,$5)"
        " ON CONFLICT (org_id, iso_year, iso_week) DO UPDATE SET iso_year=EXCLUDED.iso_year"
        " RETURNING id",
        org_id, iso_year, iso_week, monday, monday + timedelta(days=6))


# ── DB gather (all queries org_id-scoped; runs on BYPASSRLS admin conn) ──────
async def gather(conn, uconn, org_id, org_name, report_win, plan_win) -> dict:
    """*conn* is the tasks database, *uconn* the users database — owner names
    are merged app-side (no cross-database SQL join exists)."""
    r_fri, r_thu = report_win
    p_fri, p_thu = plan_win

    report_tasks = await conn.fetch(
        "SELECT t.id, t.title, t.status, t.priority, t.department, t.week_start,"
        " t.estimated_hours, t.actual_hours, t.completed_date, t.created_at,"
        " t.user_id, t.task_type, t.due_date, t.blocker_reason"
        " FROM tasks t"
        " WHERE t.org_id=$1 AND t.is_deleted=false AND ("
        "   (t.created_at >= $2::date AND t.created_at < ($3::date + 1))"
        "   OR (t.updated_at >= $2::date AND t.updated_at < ($3::date + 1))"
        "   OR (t.completed_date >= $2 AND t.completed_date <= $3)"
        "   OR EXISTS (SELECT 1 FROM task_progress tp WHERE tp.task_id=t.id"
        "              AND tp.created_at >= $2::date AND tp.created_at < ($3::date + 1))"
        "   OR EXISTS (SELECT 1 FROM work_sessions ws WHERE ws.task_id=t.id"
        "              AND ws.started_at >= $2::date AND ws.started_at < ($3::date + 1)))"
        " ORDER BY CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END,"
        " t.priority DESC, t.created_at",
        org_id, r_fri, r_thu)

    plan_rows = await conn.fetch(
        "SELECT t.id, t.title, t.status, t.priority, t.department, t.created_at,"
        " t.estimated_hours, t.actual_hours, t.user_id, t.due_date"
        " FROM tasks t"
        " WHERE t.org_id=$1 AND t.is_deleted=false AND t.is_archived=false"
        " AND t.status <> 'completed'"
        " ORDER BY t.priority DESC, t.department, t.created_at",
        org_id)

    created_count = await conn.fetchval(
        "SELECT count(*) FROM tasks WHERE org_id=$1 AND is_deleted=false"
        " AND created_at >= $2::date AND created_at < ($3::date + 1)", org_id, r_fri, r_thu)
    completed_count = await conn.fetchval(
        "SELECT count(*) FROM tasks WHERE org_id=$1 AND is_deleted=false"
        " AND completed_date >= $2 AND completed_date <= $3", org_id, r_fri, r_thu)
    notes_count = await conn.fetchval(
        "SELECT count(*) FROM task_progress tp JOIN tasks t ON t.id=tp.task_id"
        " WHERE t.org_id=$1 AND tp.created_at >= $2::date AND tp.created_at < ($3::date + 1)",
        org_id, r_fri, r_thu)
    comments_count = await conn.fetchval(
        "SELECT count(*) FROM task_comments cm JOIN tasks t ON t.id=cm.task_id"
        " WHERE t.org_id=$1 AND cm.created_at >= $2::date AND cm.created_at < ($3::date + 1)",
        org_id, r_fri, r_thu)

    declined = await conn.fetch(
        "SELECT a.task_id, t.title, a.user_id FROM task_assignees a"
        " JOIN tasks t ON t.id=a.task_id"
        " WHERE t.org_id=$1 AND a.accepted=false", org_id)

    # Work sessions in the report window — the overtime evidence.
    sessions = await conn.fetch(
        "SELECT user_id, started_at, ended_at, hours FROM work_sessions"
        " WHERE org_id=$1 AND started_at >= $2::date AND started_at < ($3::date + 1)",
        org_id, r_fri, r_thu)

    overdue_rows = await conn.fetch(
        "SELECT t.id, t.title, t.status, t.priority, t.due_date, t.user_id FROM tasks t"
        " WHERE t.org_id=$1 AND t.is_deleted=false AND t.is_archived=false"
        " AND t.due_date IS NOT NULL AND t.due_date <= $2 AND t.status <> 'completed'"
        " ORDER BY t.due_date", org_id, r_thu)

    users = await uconn.fetch(
        "SELECT id, username, full_name FROM profiles"
        " WHERE org_id=$1 AND is_active AND NOT is_deleted ORDER BY full_name", org_id)
    # Owner names for ALL referenced profiles (incl. deactivated) — merged
    # app-side because profiles live in the other database.
    names = {str(r["id"]): r["username"]
             for r in await uconn.fetch(
                 "SELECT id, username FROM profiles WHERE org_id=$1", org_id)}

    # Per-person regular/overtime/night/weekend buckets.
    hours_by_person: dict[str, dict] = {}
    for sess in sessions:
        uname = names.get(str(sess["user_id"]), "—")
        b = hours_by_person.setdefault(
            uname, {"regular": 0.0, "overtime": 0.0, "night": 0.0, "weekend": 0.0, "total": 0.0})
        h = session_hours(sess)
        b[classify(sess["started_at"])] += h
        b["total"] += h

    # Resolve — and auto-provision — the calendar week for each window.
    # Nothing else in the app creates calendar_weeks rows ahead of time, so a
    # plain SELECT returns NULL for un-seeded weeks; NULL week_id made every
    # run's replace-DELETE match ALL prior NULL-keyed pins, silently erasing
    # the archive instead of appending to it. Upserting here guarantees the
    # pins are always week-linked.
    report_week_id = await _ensure_week(conn, org_id, r_thu)
    plan_week_id = await _ensure_week(conn, org_id, p_thu)

    def _t(row):
        d = dict(row)
        d["id"] = str(d["id"])
        d["owner"] = names.get(str(d.pop("user_id")), "—")
        return d

    rtasks = [_t(r) for r in report_tasks]
    ptasks = []
    for r in plan_rows:
        d = _t(r)
        d["carry_over_weeks"] = carry_over_weeks(r["created_at"], p_thu)
        ptasks.append(d)

    return {
        "org_id": str(org_id), "org_name": org_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_window": {"from": r_fri.isoformat(), "to": r_thu.isoformat(),
                          "label": iso_week_label(r_fri, r_thu)},
        "plan_window": {"from": p_fri.isoformat(), "to": p_thu.isoformat(),
                        "label": iso_week_label(p_fri, p_thu)},
        "report_week_id": str(report_week_id) if report_week_id else None,
        "plan_week_id": str(plan_week_id) if plan_week_id else None,
        "report_tasks": rtasks, "plan_tasks": ptasks,
        "created_count": created_count, "completed_count": completed_count,
        "notes_count": notes_count, "comments_count": comments_count,
        "declined": [{"task_id": str(a["task_id"]), "title": a["title"],
                      "username": names.get(str(a["user_id"]), "—")} for a in declined],
        "hours_by_person": hours_by_person,
        "overdue": [{"id": str(o["id"]), "title": o["title"], "status": o["status"],
                     "priority": o["priority"], "due_date": o["due_date"].isoformat(),
                     "owner": names.get(str(o["user_id"]), "—")} for o in overdue_rows],
        "users": [dict(u, id=str(u["id"])) for u in users],
    }


async def resolve_agents(conn, org_id) -> tuple[str | None, str | None]:
    """Per-org ai_agent_bindings first, env fallback second."""
    rows = await conn.fetch(
        "SELECT function_key, letta_agent_id FROM ai_agent_bindings"
        " WHERE org_id=$1 AND is_active=true AND function_key IN ('weekly_report','next_week_plan')",
        org_id)
    m = {r["function_key"]: r["letta_agent_id"] for r in rows}
    return m.get("weekly_report") or REPORT_AGENT_ID or None, \
        m.get("next_week_plan") or PLAN_AGENT_ID or None


# ── ai_pins archival ────────────────────────────────────────────────────────
async def _replace_pin(conn, org_id, function_key, week_id, title, body,
                       created_by=None, prompt_version=None):
    # Atomic swap: a crash (or overlapping re-run) between the delete and the
    # insert must never leave the org with the pin missing.
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM ai_pins WHERE org_id=$1 AND function_key=$2"
            " AND week_id IS NOT DISTINCT FROM $3 AND title=$4",
            org_id, function_key, week_id, title)
        await conn.execute(
            "INSERT INTO ai_pins(org_id, function_key, week_id, title, body, created_by, prompt_version)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7)",
            org_id, function_key, week_id, title, body, created_by, prompt_version)


async def write_pins(conn, snap, digest, org_report, org_plan, user_reports, user_plans,
                     report_pv=None, plan_pv=None):
    org_id = snap["org_id"]
    r_lbl, p_lbl = snap["report_window"]["label"], snap["plan_window"]["label"]
    r_wk, p_wk = snap["report_week_id"], snap["plan_week_id"]

    # weekly_snapshot is the raw deterministic digest — no prompt was ever
    # involved, so its prompt_version stays NULL rather than a fake sentinel.
    await _replace_pin(conn, org_id, "weekly_snapshot", r_wk,
                       f"Weekly snapshot — {r_lbl}", digest)
    await _replace_pin(conn, org_id, "weekly_report", r_wk,
                       f"Weekly report — {r_lbl}", org_report, prompt_version=report_pv)
    await _replace_pin(conn, org_id, "next_week_plan", p_wk,
                       f"Next week plan — {p_lbl}", org_plan, prompt_version=plan_pv)
    # Per-user: clear the week's set first, then insert each. subject_user_id
    # is what the tightened RLS policy keys visibility on — a per-user pin
    # without it would be readable by the whole org. Per-user pins only ever
    # exist when the agent actually replied (no fallback path for them), so
    # they always carry the real prompt version.
    uid_by_name = {u["username"]: u["id"] for u in snap["users"]}
    await conn.execute(
        "DELETE FROM ai_pins WHERE org_id=$1 AND function_key='weekly_report_user'"
        " AND week_id IS NOT DISTINCT FROM $2", org_id, r_wk)
    await conn.execute(
        "DELETE FROM ai_pins WHERE org_id=$1 AND function_key='next_week_plan_user'"
        " AND week_id IS NOT DISTINCT FROM $2", org_id, p_wk)
    for username, body in user_reports.items():
        await conn.execute(
            "INSERT INTO ai_pins(org_id, function_key, week_id, title, body, subject_user_id, prompt_version)"
            " VALUES ($1,'weekly_report_user',$2,$3,$4,$5,$6)",
            org_id, r_wk, f"Weekly report — {r_lbl} — {username}", body,
            uid_by_name.get(username), planner_prompts.PROMPT_VERSION)
    for username, body in user_plans.items():
        await conn.execute(
            "INSERT INTO ai_pins(org_id, function_key, week_id, title, body, subject_user_id, prompt_version)"
            " VALUES ($1,'next_week_plan_user',$2,$3,$4,$5,$6)",
            org_id, p_wk, f"Next week plan — {p_lbl} — {username}", body,
            uid_by_name.get(username), planner_prompts.PROMPT_VERSION)


# ── Per-org orchestration ───────────────────────────────────────────────────
async def process_org(conn, uconn, client, org_id, org_name, ref: date, skip_letta: bool):
    report_win, plan_win = compute_windows(ref)
    snap = await gather(conn, uconn, org_id, org_name, report_win, plan_win)
    digest = build_digest(snap)

    report_agent, plan_agent = (None, None) if skip_letta else await resolve_agents(conn, org_id)

    # Upload the full digest to the RAG source FIRST (best effort), so the
    # planner agents called below can in principle retrieve this week's
    # per-task detail, not only prior weeks'.
    if not skip_letta and SNAPSHOT_SOURCE_ID:
        slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"
        fname = f"wwf_{slug}_{snap['report_window']['from']}_{snap['report_window']['to']}.md"
        await letta_upload_digest(client, SNAPSHOT_SOURCE_ID, fname, digest)

    # Org rollup. The digest's per-task section grows unbounded with task
    # count (33K+ chars for ~200 tasks) and blew the weekly_report agent's
    # context on the first production run. The rollup prompt is therefore
    # the aggregate sections plus a bounded, citation-worthy task sample
    # (stuck + completed + top-priority), so the agent can honor its
    # cite-every-claim rule at constant prompt size regardless of volume.
    digest_summary = digest.split("\n" + TASKS_HEADER + "\n")[0].rstrip()
    sample = rollup_task_sample(snap["report_tasks"])
    rollup_ctx = (f"{digest_summary}\n\n## Task sample for citations "
                  f"({len(sample)} of {len(snap['report_tasks'])} tasks: all stuck, "
                  f"all completed, then top priority)\n{_task_bullets(sample)}")

    def _fallback(label):
        return (f"> AI unavailable at {datetime.now(timezone.utc).strftime('%H:%M UTC')} "
                f"— deterministic fallback.\n\n{label}\n\n" + digest_summary)

    org_report = org_plan = None
    if report_agent:
        rp = (f"{rollup_ctx}\n\nREQUEST: Produce the WEEKLY REPORT for the whole facility "
              f"'{org_name}' for {snap['report_window']['label']}. "
              f"Return ONLY JSON: {{\"weekly_report\": \"<markdown>\"}}")
        org_report = _extract_json_field(await letta_message(client, report_agent, rp), "weekly_report")
    if plan_agent:
        pp = (f"CARRY-OVER + OPEN TASKS:\n{_task_bullets(snap['plan_tasks'])}\n\n"
              f"REQUEST: Produce the NEXT-WEEK PLAN for the facility '{org_name}' for "
              f"{snap['plan_window']['label']}. Return ONLY JSON: {{\"next_week_plan\": \"<markdown>\"}}")
        org_plan = _extract_json_field(await letta_message(client, plan_agent, pp), "next_week_plan")
    # Capture AI-vs-fallback before _fallback()'s `or` reassignment below
    # overwrites the variable — prompt_version needs to know which happened.
    report_pv = planner_prompts.PROMPT_VERSION if org_report else "fallback"
    plan_pv = planner_prompts.PROMPT_VERSION if org_plan else "fallback"
    org_report = org_report or _fallback(f"# Weekly report — {snap['report_window']['label']}")
    org_plan = org_plan or _fallback(f"# Next-week plan — {snap['plan_window']['label']}")

    # Per-person. Each user's report+plan go to two DIFFERENT agents, so the
    # pair runs concurrently (2x). Users stay sequential on purpose: all the
    # report calls target the same stateful Letta agent, and hammering one
    # agent with concurrent messages risks serialized-queue contention there
    # for no reliable speedup.
    user_reports: dict[str, str] = {}
    user_plans: dict[str, str] = {}

    async def _ask(agent_id, prompt, key):
        return _extract_json_field(await letta_message(client, agent_id, prompt), key)

    async def _none():
        return None

    for u in snap["users"]:
        uname = u["username"]
        who = u["full_name"] or uname
        mine_r = [t for t in snap["report_tasks"] if t["owner"] == uname]
        mine_p = [t for t in snap["plan_tasks"] if t["owner"] == uname]
        # Build each side conditionally — a pre-created placeholder coroutine
        # that then gets replaced is never awaited and warns at shutdown.
        r_coro = (_ask(report_agent,
                       f"TASK DATA for {who}:\n{_task_bullets(mine_r)}\n\n"
                       f"REQUEST: Weekly report for {who}, {snap['report_window']['label']}. "
                       f"Return ONLY JSON: {{\"weekly_report\": \"<markdown>\"}}",
                       "weekly_report")
                  if report_agent and mine_r else _none())
        p_coro = (_ask(plan_agent,
                       f"OPEN/CARRY-OVER for {who}:\n{_task_bullets(mine_p)}\n\n"
                       f"REQUEST: Next-week plan for {who}, {snap['plan_window']['label']}. "
                       f"Return ONLY JSON: {{\"next_week_plan\": \"<markdown>\"}}",
                       "next_week_plan")
                  if plan_agent and mine_p else _none())
        r_out, p_out = await asyncio.gather(r_coro, p_coro)
        if r_out:
            user_reports[uname] = r_out
        if p_out:
            user_plans[uname] = p_out

    await write_pins(conn, snap, digest, org_report, org_plan, user_reports, user_plans,
                     report_pv=report_pv, plan_pv=plan_pv)
    log(f"org {org_name}: pinned report/plan ({len(user_reports)} user reports, "
        f"{len(user_plans)} user plans); {len(snap['report_tasks'])} tasks in window")


async def run_all(ref: date, only_org=None, skip_letta: bool = False) -> None:
    if not USERS_ADMIN_DSN or not TASKS_ADMIN_DSN:
        raise SystemExit("USERS_ADMIN_DATABASE_URL / TASKS_ADMIN_DATABASE_URL not set")
    uconn = await asyncpg.connect(USERS_ADMIN_DSN)
    try:
        conn = await asyncpg.connect(TASKS_ADMIN_DSN)
    except Exception:
        await uconn.close()
        raise
    client = None if skip_letta else httpx.AsyncClient(timeout=60)
    try:
        orgs = await uconn.fetch("SELECT id, name FROM organizations"
                                 + (" WHERE id=$1" if only_org else ""),
                                 *([only_org] if only_org else []))
        log(f"processing {len(orgs)} org(s) for ref={ref.isoformat()} skip_letta={skip_letta}")
        for o in orgs:
            try:
                await process_org(conn, uconn, client, o["id"], o["name"], ref, skip_letta)
            except Exception as e:
                log(f"org {o['name']} FAILED: {type(e).__name__}: {e}")
    finally:
        await conn.close()
        await uconn.close()
        if client:
            await client.aclose()


async def attach_source_once() -> None:
    """One-time: attach the RAG source to the coordinator + planner agents so
    future AI calls can retrieve historical digests."""
    if not COORDINATOR_AGENT_ID:
        log("LETTA_COORDINATOR_AGENT_ID not set — skipping attach")
        return
    async with httpx.AsyncClient(timeout=30) as client:
        await letta_attach_source(client, COORDINATOR_AGENT_ID, SNAPSHOT_SOURCE_ID)


def main() -> None:
    ap = argparse.ArgumentParser(description="WWF weekly snapshot job")
    ap.add_argument("--once", action="store_true", help="run now for today's date")
    ap.add_argument("--ref-date", help="run as if today were YYYY-MM-DD")
    ap.add_argument("--org-id", help="limit to one organization id")
    ap.add_argument("--skip-letta", action="store_true", help="DB-only, no Letta calls")
    ap.add_argument("--attach-source", action="store_true",
                    help="one-time: attach the RAG source to the coordinator and exit")
    args = ap.parse_args()

    if args.attach_source:
        asyncio.run(attach_source_once())
        return

    ref = date.fromisoformat(args.ref_date) if args.ref_date else date.today()
    asyncio.run(run_all(ref, only_org=args.org_id, skip_letta=args.skip_letta))


if __name__ == "__main__":
    main()
