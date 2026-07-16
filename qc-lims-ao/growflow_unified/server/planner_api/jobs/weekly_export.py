"""Weekly task snapshot — Fri→Thu work week.

Captures task creations, progress notes and descriptions for the work week,
writes a JSON file, and upserts the snapshot into the app's own PostgreSQL
(table planner_weekly_snapshot). Designed to run on a weekly schedule (cron),
typically Thursday evening so it captures the week that just finished.

Run inside the API container:
    python -m planner_api.jobs.weekly_export                # current Fri→Thu week
    python -m planner_api.jobs.weekly_export --offset -1     # the previous week
    python -m planner_api.jobs.weekly_export --from 2026-06-26 --to 2026-07-02
    python -m planner_api.jobs.weekly_export --no-db         # JSON file only

Targets the GrowFlow database from PLANNER_DATABASE_URL (NOT the SUMA Supabase).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request
import uuid

import psycopg
from psycopg.rows import dict_row

from ..config import get_settings
from .weekly_digest import build_digest_md


def _dsn() -> str:
    """libpq DSN from the SQLAlchemy URL (strip the +psycopg driver suffix)."""
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def push_digest_to_letta(digest_md: str, file_name: str) -> str | None:
    """Upload the digest to the configured Letta source so the weekly_coordinator /
    executive_analytics agents can reason over it. Idempotent: removes any prior file
    with the same name first. No-op (returns None) unless base URL + key + source id
    are all configured. Never raises — Letta downtime must not fail the export."""
    s = get_settings()
    base, key, sid = s.letta_base_url.rstrip("/"), s.letta_api_key, s.letta_snapshot_source_id
    if not (base and key and sid):
        return None
    h = {"Authorization": "Bearer " + key}
    try:
        # Remove a prior same-name file (replace semantics).
        req = urllib.request.Request(f"{base}/v1/sources/{sid}/files", headers=h, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            for f in json.load(r):
                if f.get("file_name") == file_name:
                    d = urllib.request.Request(f"{base}/v1/sources/{sid}/{f['id']}", headers=h, method="DELETE")
                    try:
                        urllib.request.urlopen(d, timeout=20).read()
                    except urllib.error.HTTPError:
                        pass
        # Multipart upload of the new digest.
        boundary = "----growflow" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            "Content-Type: text/markdown\r\n\r\n"
        ).encode() + digest_md.encode("utf-8") + f"\r\n--{boundary}--\r\n".encode()
        up = urllib.request.Request(
            f"{base}/v1/sources/{sid}/upload?duplicate_handling=replace",
            data=body, method="POST",
            headers={**h, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(up, timeout=60) as r:
            out = json.load(r)
        fid = out.get("file_id") or (out.get("data") or {}).get("file_id") or out.get("id")
        print(f"[weekly_export] pushed digest to Letta source {sid} (file {fid})")
        return fid
    except Exception as e:  # noqa: BLE001 — graceful degradation
        print(f"[weekly_export] Letta push skipped: {e}")
        return None


def work_week(ref: date, offset: int = 0) -> tuple[date, date]:
    """The Fri→Thu work week containing `ref` (Mon=0 … Fri=4), shifted by `offset` weeks."""
    days_since_friday = (ref.weekday() - 4) % 7
    friday = ref - timedelta(days=days_since_friday) + timedelta(weeks=offset)
    return friday, friday + timedelta(days=6)


def _json_default(o: Any) -> str:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)


def _children(cur: psycopg.Cursor, ids: list[str], f: datetime, te: datetime) -> dict[str, dict]:
    out = {tid: {"helpers": [], "subtasks": [], "notes": [], "deps": [], "handoffs": []} for tid in ids}
    if not ids:
        return out
    p = {"ids": ids, "f": f, "te": te}
    cur.execute("SELECT h.task_id, h.user_id, u.full_name FROM planner_task_helper h "
                "LEFT JOIN app_user u ON u.id = h.user_id WHERE h.task_id = ANY(%(ids)s::uuid[])", p)
    for r in cur.fetchall():
        out[str(r["task_id"])]["helpers"].append({"user_id": str(r["user_id"]), "name": r["full_name"]})
    cur.execute("SELECT id, task_id, text, done, position FROM planner_subtask "
                "WHERE task_id = ANY(%(ids)s::uuid[]) ORDER BY position", p)
    for r in cur.fetchall():
        out[str(r["task_id"])]["subtasks"].append({"text": r["text"], "done": r["done"], "position": r["position"]})
    cur.execute("SELECT n.id, n.task_id, n.day, n.note, n.created_at, a.full_name AS author "
                "FROM planner_progress_note n LEFT JOIN app_user a ON a.id = n.author_id "
                "WHERE n.task_id = ANY(%(ids)s::uuid[]) ORDER BY n.created_at", p)
    for r in cur.fetchall():
        out[str(r["task_id"])]["notes"].append({
            "day": r["day"], "note": r["note"], "author": r["author"],
            "created_at": r["created_at"], "in_window": bool(r["created_at"] and f <= r["created_at"] < te),
        })
    cur.execute("SELECT d.task_id, d.depends_on_task_id, t.title, t.status FROM planner_task_dependency d "
                "LEFT JOIN planner_task t ON t.id = d.depends_on_task_id WHERE d.task_id = ANY(%(ids)s::uuid[])", p)
    for r in cur.fetchall():
        out[str(r["task_id"])]["deps"].append({"id": str(r["depends_on_task_id"]), "title": r["title"], "status": r["status"]})
    cur.execute("SELECT h.task_id, h.to_department_id, d.key AS to_key, h.status, h.created_at "
                "FROM planner_handoff h JOIN planner_department d ON d.id = h.to_department_id "
                "WHERE h.task_id = ANY(%(ids)s::uuid[]) ORDER BY h.created_at", p)
    for r in cur.fetchall():
        out[str(r["task_id"])]["handoffs"].append({"to_department": r["to_key"], "status": r["status"], "created_at": r["created_at"]})
    return out


def build_snapshot(cur: psycopg.Cursor, friday: date, thursday: date) -> dict:
    # UTC-aware bounds — planner_task timestamps are timestamptz (offset-aware).
    f = datetime.combine(friday, datetime.min.time(), timezone.utc)
    te = datetime.combine(thursday + timedelta(days=1), datetime.min.time(), timezone.utc)
    cur.execute(
        "SELECT t.id, d.key AS dept_key, d.name_en AS dept_en, d.name_mk AS dept_mk, t.title, "
        "u.full_name AS owner_name, cb.full_name AS created_by, t.status, t.priority, t.week_start, "
        "t.days, t.room, t.batch, t.tags, t.description, t.blocker, t.outcome, "
        "t.assignment_status, t.assignment_responded_at, t.assignment_note, "
        "t.created_at, t.updated_at, t.completed_at "
        "FROM planner_task t JOIN planner_department d ON d.id = t.department_id "
        "LEFT JOIN app_user u ON u.id = t.owner_id LEFT JOIN app_user cb ON cb.id = t.created_by "
        "WHERE (t.created_at >= %(f)s AND t.created_at < %(te)s) "
        "   OR (t.completed_at >= %(f)s AND t.completed_at < %(te)s) "
        "   OR (t.updated_at >= %(f)s AND t.updated_at < %(te)s) "
        "   OR EXISTS (SELECT 1 FROM planner_progress_note n WHERE n.task_id = t.id "
        "              AND n.created_at >= %(f)s AND n.created_at < %(te)s) "
        "ORDER BY t.created_at",
        {"f": f, "te": te},
    )
    rows = cur.fetchall()
    ids = [str(r["id"]) for r in rows]
    kids = _children(cur, ids, f, te)
    created = completed = notes = 0
    tasks = []
    for r in rows:
        tid = str(r["id"])
        k = kids[tid]
        notes += sum(1 for n in k["notes"] if n["in_window"])
        if r["created_at"] and f <= r["created_at"] < te:
            created += 1
        if r["completed_at"] and f <= r["completed_at"] < te:
            completed += 1
        tasks.append({
            "id": tid, "title": r["title"], "department": r["dept_key"],
            "department_name": {"en": r["dept_en"], "mk": r["dept_mk"]},
            "owner": r["owner_name"], "created_by": r["created_by"],
            "status": r["status"], "priority": r["priority"],
            "week_start": r["week_start"], "days": list(r["days"] or []),
            "room": r["room"], "batch": r["batch"], "tags": list(r["tags"] or []),
            "description": r["description"], "blocker": r["blocker"], "outcome": r["outcome"],
            "assignment_status": r["assignment_status"], "assignment_responded_at": r["assignment_responded_at"],
            "assignment_note": r["assignment_note"],
            "created_at": r["created_at"], "updated_at": r["updated_at"], "completed_at": r["completed_at"],
            "created_in_window": bool(r["created_at"] and f <= r["created_at"] < te),
            "completed_in_window": bool(r["completed_at"] and f <= r["completed_at"] < te),
            "helpers": k["helpers"], "subtasks": k["subtasks"], "notes": k["notes"],
            "dependencies": k["deps"], "handoffs": k["handoffs"],
        })
    return {
        "kind": "growflow.weekly_snapshot", "version": 1,
        "generated_at": datetime.now().astimezone(),
        "work_week": "Fri-Thu",
        "window": {"from": friday.isoformat(), "to": thursday.isoformat()},
        "counts": {"tasks": len(tasks), "created": created, "completed": completed, "notes": notes},
        "tasks": tasks,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GrowFlow weekly (Fri→Thu) task snapshot → JSON + DB.")
    ap.add_argument("--offset", type=int, default=0, help="shift the work week by N weeks (default 0 = this week)")
    ap.add_argument("--from", dest="frm", help="explicit window start YYYY-MM-DD (overrides --offset)")
    ap.add_argument("--to", dest="to", help="explicit window end YYYY-MM-DD")
    ap.add_argument("--out-dir", default=os.environ.get("GROWFLOW_EXPORT_DIR", "/app/exports"))
    ap.add_argument("--no-db", action="store_true", help="do not upsert the snapshot into the database")
    ap.add_argument("--no-file", action="store_true", help="do not write the JSON file")
    ap.add_argument("--no-digest", action="store_true", help="do not write the Markdown digest")
    ap.add_argument("--no-letta", action="store_true", help="do not push the digest to the Letta source")
    args = ap.parse_args(argv)

    if args.frm and args.to:
        friday, thursday = date.fromisoformat(args.frm), date.fromisoformat(args.to)
    else:
        friday, thursday = work_week(date.today(), args.offset)

    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            snap = build_snapshot(cur, friday, thursday)
        payload = json.dumps(snap, default=_json_default)
        c = snap["counts"]
        digest_name = f"weekly_digest_{friday.isoformat()}_{thursday.isoformat()}.md"
        digest_md = build_digest_md(snap)
        if not args.no_file:
            out = Path(args.out_dir)
            out.mkdir(parents=True, exist_ok=True)
            fp = out / f"growflow_week_{friday.isoformat()}_{thursday.isoformat()}.json"
            fp.write_text(payload, encoding="utf-8")
            print(f"[weekly_export] wrote {fp}")
            if not args.no_digest:
                dp = out / digest_name
                dp.write_text(digest_md, encoding="utf-8")
                print(f"[weekly_export] wrote {dp}")
        if not args.no_letta:
            push_digest_to_letta(digest_md, digest_name)
        if not args.no_db:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO planner_weekly_snapshot "
                    "(week_from, week_to, generated_at, task_count, created_count, completed_count, note_count, payload) "
                    "VALUES (%(f)s, %(t)s, now(), %(n)s, %(cr)s, %(cp)s, %(nt)s, %(p)s::jsonb) "
                    "ON CONFLICT (week_from, week_to) DO UPDATE SET "
                    "generated_at = now(), task_count = EXCLUDED.task_count, created_count = EXCLUDED.created_count, "
                    "completed_count = EXCLUDED.completed_count, note_count = EXCLUDED.note_count, payload = EXCLUDED.payload",
                    {"f": friday, "t": thursday, "n": c["tasks"], "cr": c["created"], "cp": c["completed"], "nt": c["notes"], "p": payload},
                )
            conn.commit()
            print(f"[weekly_export] upserted snapshot into planner_weekly_snapshot")
    print(f"[weekly_export] window {friday}→{thursday}: {c['tasks']} tasks "
          f"({c['created']} created, {c['completed']} completed, {c['notes']} notes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
