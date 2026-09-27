"""Tests for scripts/weekly_snapshot.py — mostly pure-function (window math,
carry-over aging, the Markdown digest), plus one end-to-end run_all guard that
drives the real two-DB path (see test_run_all_writes_pins_end_to_end). The
pure-function tests need no DB/Letta; the guard uses the shared conftest
fixtures and the skip_letta=True (deterministic, no-Letta) code path."""
import os
import sys
import uuid
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import weekly_snapshot as w  # noqa: E402


def test_compute_windows_from_a_thursday():
    # Thursday 2026-07-02 -> report Fri 06-26..Thu 07-02, plan Fri 07-03..Thu 07-09.
    report, plan = w.compute_windows(date(2026, 7, 2))
    assert report == (date(2026, 6, 26), date(2026, 7, 2))
    assert plan == (date(2026, 7, 3), date(2026, 7, 9))


def test_compute_windows_midweek_snaps_to_containing_week():
    # A Tuesday still belongs to the Fri->Thu window that contains it.
    report, _ = w.compute_windows(date(2026, 6, 30))  # Tuesday
    assert report == (date(2026, 6, 26), date(2026, 7, 2))


def test_carry_over_weeks():
    created = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert w.carry_over_weeks(created, date(2026, 7, 2)) == 4
    assert w.carry_over_weeks(datetime(2026, 7, 1, tzinfo=timezone.utc), date(2026, 7, 2)) == 0


def test_extract_json_field_tolerates_prose_and_fences():
    assert w._extract_json_field('here: {"weekly_report": "hi"} thanks', "weekly_report") == "hi"
    assert w._extract_json_field('```json\n{"next_week_plan": "do X"}\n```', "next_week_plan") == "do X"
    assert w._extract_json_field("no json here", "weekly_report") is None
    assert w._extract_json_field('{"other": 1}', "weekly_report") is None


def _synthetic_snapshot():
    return {
        "org_name": "Purely Plant", "generated_at": "2026-07-02T14:00:00Z",
        "report_window": {"from": "2026-06-26", "to": "2026-07-02",
                          "label": "W27 2026 (2026-06-26 → 2026-07-02)"},
        "plan_window": {"from": "2026-07-03", "to": "2026-07-09",
                        "label": "W28 2026 (2026-07-03 → 2026-07-09)"},
        "report_tasks": [
            {"id": "aaaaaaaa-1111", "title": "Trim GG4", "status": "stuck", "priority": "high",
             "department": "prod", "owner": "marko", "estimated_hours": 4, "actual_hours": 5.5,
             "completed_date": None, "week_start": None},
            {"id": "bbbbbbbb-2222", "title": "QC test", "status": "completed", "priority": "medium",
             "department": "qc", "owner": "elena", "estimated_hours": 2, "actual_hours": 2,
             "completed_date": "2026-07-01", "week_start": None},
        ],
        "plan_tasks": [
            {"id": "cccccccc-3333", "title": "Harvest", "status": "pending", "priority": "high",
             "department": "flower", "owner": "marko", "estimated_hours": None, "actual_hours": None,
             "carry_over_weeks": 2},
        ],
        "created_count": 2, "completed_count": 1, "notes_count": 3, "comments_count": 1,
        "declined": [{"task_id": "dddddddd-4444", "title": "Pack order", "username": "nina"}],
        "users": [],
    }


def test_build_digest_has_citations_blockers_and_aging():
    md = w.build_digest(_synthetic_snapshot())
    assert "[task:aaaaaaaa]" in md          # every task cites its id
    assert "STUCK" in md and "DECLINED" in md  # blockers section
    assert "rolled 2w" in md                # carry-over aging
    # hour sums were removed app-wide (owner: not a meaningful metric) — the
    # digest must NOT feed them to the AI planners anymore
    assert "Org total:" not in md and "Hours by time class" not in md
    assert "Completion: 50% (1/2)" in md


def test_iso_week_label_matches_the_reports_endpoint_convention():
    """A Fri->Thu window straddles two ISO weeks every week; the label must
    use the window's MONDAY (weekwindow.window_iso_week — the /reports/weekly
    and compiled-document convention) or the pinned AI report disagrees with
    the in-app report's period label by one, every week. This derived it from
    the Friday and did exactly that (review 2026-09-27, BC-16)."""
    from app.api.weekwindow import window_iso_week
    lbl = w.iso_week_label(date(2026, 6, 26), date(2026, 7, 2))
    assert lbl.startswith("W27 2026"), lbl   # Mon 2026-06-29 is ISO W27; the Friday alone is W26
    assert window_iso_week(date(2026, 6, 26)) == (2026, 27)
    # a Dec/Jan window takes the Monday's ISO year: W1 2027, never "W53 2027"
    assert w.iso_week_label(date(2027, 1, 1), date(2027, 1, 7)).startswith("W1 2027")


async def test_gather_uses_the_shared_activity_predicate(client, admin_headers, org):
    """Review 2026-09-27, BC-09: the snapshot carried a hand-copied five-term
    week predicate that did not count comments, assignments, acknowledgements
    or rejected handoffs — a task whose only activity in the week was a
    comment was on /reports/weekly and in the locked document but absent from
    the digest, the AI report and the RAG upload. gather() now imports
    weekwindow.activity_window_sql, the one definition."""
    import uuid as _uuid
    from app.db import tasks_admin_pool, users_admin_pool
    org_uuid = _uuid.UUID(org["org_id"])
    r = await client.post("/tasks", json={"title": "Commented-only task", "status": "ongoing"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = await client.post(f"/tasks/{tid}/comments", json={"content": "still on it"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    # Move the task's own stamps out of the window, leave only the comment in it.
    await tasks_admin_pool().execute(
        "UPDATE tasks SET created_at='2026-01-05 10:00+00', updated_at='2026-01-05 10:00+00' WHERE id=$1", tid)
    await tasks_admin_pool().execute(
        "UPDATE task_comments SET created_at='2026-07-06 10:00+00' WHERE task_id=$1", tid)
    async with tasks_admin_pool().acquire() as conn, users_admin_pool().acquire() as uconn:
        snap = await w.gather(conn, uconn, org_uuid, "Org", (date(2026, 7, 3), date(2026, 7, 9)),
                              (date(2026, 7, 10), date(2026, 7, 16)))
    assert "Commented-only task" in [t["title"] for t in snap["report_tasks"]]
    assert snap["comments_count"] >= 1


def test_digest_split_marker_survives_hostile_titles():
    """The org-rollup prompt is the digest split at TASKS_HEADER. A task
    title containing that exact heading (even with embedded newlines) must
    not be able to move the split point — titles are whitespace-collapsed."""
    snap = _synthetic_snapshot()
    snap["report_tasks"][0]["title"] = "Evil\n## Tasks this week\ninjection"
    md = w.build_digest(snap)
    parts = md.split("\n" + w.TASKS_HEADER + "\n")
    assert len(parts) == 2                   # exactly one real section boundary
    assert "## Blockers" in parts[0]         # aggregates intact in the summary half
    assert "Evil ## Tasks this week injection" in parts[1]  # title flattened, in task list


def test_rollup_task_sample_prioritizes_stuck_and_completed_then_caps():
    tasks = (
        [{"id": f"r{i}", "status": "ongoing", "priority": "high"} for i in range(80)]
        + [{"id": "s1", "status": "stuck", "priority": "low"}]
        + [{"id": "d1", "status": "completed", "priority": "low"}]
    )
    sample = w.rollup_task_sample(tasks, limit=10)
    ids = [t["id"] for t in sample]
    assert len(sample) == 10
    assert ids[0] == "s1" and ids[1] == "d1"  # stuck + completed always make the cut


async def test_run_all_writes_pins_end_to_end(client, admin_headers, org):
    """Regression guard for the process_org() call-arity bug: run_all invoked
    process_org with one too few positional args (client omitted), so every
    per-org call raised TypeError — swallowed by run_all's per-org except —
    and NO ai_pins were ever written, every week, for every org. The pure
    helper tests can't see a broken call site; this drives the real two-DB
    path with skip_letta=True (deterministic, no Letta) and asserts pins land.

    weekly_snapshot reads its admin DSNs from the same env the test suite
    exports, so run_all's own asyncpg connections hit the test databases."""
    r = await client.post("/tasks", json={"title": "Snapshot fodder", "status": "ongoing",
                                          "estimated_hours": 2}, headers=admin_headers)
    assert r.status_code == 201, r.text

    from app.db import tasks_admin_pool
    org_uuid = uuid.UUID(org["org_id"])
    before = await tasks_admin_pool().fetchval(
        "SELECT count(*) FROM ai_pins WHERE org_id=$1", org_uuid)

    # Thursday 2026-07-09 -> report window Fri 07-03..Thu 07-09.
    await w.run_all(date(2026, 7, 9), only_org=org_uuid, skip_letta=True)

    rows = await tasks_admin_pool().fetch(
        "SELECT function_key FROM ai_pins WHERE org_id=$1", org_uuid)
    keys = {r["function_key"] for r in rows}
    assert len(rows) > before, "run_all wrote no ai_pins — process_org never executed"
    # The three org-level pins are written deterministically even without Letta.
    assert {"weekly_snapshot", "weekly_report", "next_week_plan"} <= keys, keys


async def test_run_all_stamps_the_org_on_its_audit_rows(client, admin_headers, org):
    """Review 2026-09-27, BC-22: the snapshot wrote ai_pins and calendar_weeks
    on a raw admin connection with no app.org_id, so app.fn_audit_row stamped
    org_id NULL on those rows — which the audit_read policy opens to EVERY
    organisation's elevated users, full report bodies included."""
    from app.db import tasks_admin_pool
    org_uuid = uuid.UUID(org["org_id"])
    await w.run_all(date(2026, 7, 9), only_org=org_uuid, skip_letta=True)
    rows = await tasks_admin_pool().fetch(
        "SELECT org_id FROM audit_log WHERE table_name='ai_pins' AND action='INSERT'"
        " AND new_values->>'org_id' = $1", org["org_id"])
    assert rows, "the run wrote no ai_pins audit rows"
    assert all(str(r["org_id"]) == org["org_id"] for r in rows), "an ai_pins audit row carried no org"
