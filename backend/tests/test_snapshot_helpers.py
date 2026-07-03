"""Pure-function unit tests for scripts/weekly_snapshot.py — window math,
carry-over aging, and the Markdown digest. No DB, no Letta (the script is
dependency-light and free of app.* imports precisely so this works)."""
import os
import sys
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


def test_build_digest_has_citations_blockers_aging_and_hours():
    md = w.build_digest(_synthetic_snapshot())
    assert "[task:aaaaaaaa]" in md          # every task cites its id
    assert "STUCK" in md and "DECLINED" in md  # blockers section
    assert "rolled 2w" in md                # carry-over aging
    assert "Org total: 7.5 / 6" in md       # hours actual/estimated
    assert "Completion: 50% (1/2)" in md
