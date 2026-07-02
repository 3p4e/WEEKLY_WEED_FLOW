"""Regression test for the weekly report's summary: it used to omit a
'postponed' bucket even though it's a valid, reachable status, so a
postponed task counted toward summary.total but reconciled with no named
bucket in the frontend's stat cards."""


async def test_weekly_report_summary_counts_postponed_tasks(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Postponed today", "status": "postponed"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.get("/reports/weekly", headers=admin_headers)
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["postponed"] >= 1
    # Every bucket the summary reports must add up to (at most) the total —
    # the bug this test pins was postponed silently falling out of the sum.
    accounted = (
        summary["completed"] + summary["in_progress"] + summary["stuck"]
        + summary["pending"] + summary["review"] + summary["postponed"]
    )
    assert accounted == summary["total"]
