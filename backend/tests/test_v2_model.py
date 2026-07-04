"""v2 task model — work sessions (the overtime engine), links, new task
fields, recurrence materialization, and the report's per-person time-class
buckets. The classification rules themselves live in app/worktime.py."""
from datetime import datetime, timedelta

from app.worktime import TZ, classify


def test_classification_rules():
    def at(y, m, d, h):
        return datetime(y, m, d, h, 0, tzinfo=TZ)
    assert classify(at(2026, 7, 6, 10)) == "regular"    # Mon 10:00
    assert classify(at(2026, 7, 6, 18)) == "overtime"   # Mon 18:00
    assert classify(at(2026, 7, 6, 7)) == "overtime"    # Mon 07:00
    assert classify(at(2026, 7, 6, 23)) == "night"      # Mon 23:00
    assert classify(at(2026, 7, 7, 2)) == "night"       # Tue 02:00
    assert classify(at(2026, 7, 4, 14)) == "weekend"    # Sat
    assert classify(at(2026, 7, 5, 2)) == "weekend"     # Sun 02:00 — weekend wins over night


async def _task(client, headers, **extra):
    r = await client.post("/tasks", json={"title": "v2 task", "status": "pending", **extra},
                           headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_new_task_fields_round_trip(client, admin_headers, org):
    t = await _task(client, admin_headers, task_type="sop", reference_code="PP-QC-SOP-012",
                    due_date="2026-07-10", tags=["hplc", "validation"])
    assert t["task_type"] == "sop" and t["reference_code"] == "PP-QC-SOP-012"
    assert t["due_date"] == "2026-07-10"

    r = await client.patch(f"/tasks/{t['id']}", json={"status": "stuck", "blocker_reason": "waiting on QA sign-off"},
                            headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["blocker_reason"] == "waiting on QA sign-off"

    r = await client.get("/tasks", headers=admin_headers)
    listed = next(x for x in r.json() if x["id"] == t["id"])
    assert listed["task_type"] == "sop" and listed["due_date"] == "2026-07-10"


async def test_invalid_task_type_rejected(client, admin_headers, org):
    r = await client.post("/tasks", json={"title": "x", "task_type": "nonsense"}, headers=admin_headers)
    assert r.status_code == 422


async def test_completion_stamps_completed_date_and_outcome(client, admin_headers, org):
    t = await _task(client, admin_headers)
    r = await client.patch(f"/tasks/{t['id']}",
                            json={"status": "completed", "outcome": "Report approved and filed"},
                            headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["completed_date"] is not None
    assert body["outcome"] == "Report approved and filed"


async def test_archive_hides_task_from_default_list(client, admin_headers, org):
    t = await _task(client, admin_headers)
    r = await client.patch(f"/tasks/{t['id']}", json={"is_archived": True}, headers=admin_headers)
    assert r.status_code == 200
    r = await client.get("/tasks", headers=admin_headers)
    assert not any(x["id"] == t["id"] for x in r.json())
    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    assert any(x["id"] == t["id"] for x in r.json())


async def test_work_session_round_trip_and_classification(client, admin_headers, org):
    t = await _task(client, admin_headers)
    # Saturday 14:00 facility time, no offset given — must classify weekend.
    r = await client.post(f"/tasks/{t['id']}/sessions",
                           json={"started_at": "2026-07-04T14:00:00", "hours": 2.5,
                                 "note": "weekend lab work"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["classification"] == "weekend" and s["hours"] == 2.5

    # Interval session: hours derived from started/ended.
    r = await client.post(f"/tasks/{t['id']}/sessions",
                           json={"started_at": "2026-07-06T09:00:00", "ended_at": "2026-07-06T12:30:00"},
                           headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["hours"] == 3.5 and r.json()["classification"] == "regular"

    # Neither hours nor ended_at → rejected.
    r = await client.post(f"/tasks/{t['id']}/sessions",
                           json={"started_at": "2026-07-06T09:00:00"}, headers=admin_headers)
    assert r.status_code == 422

    r = await client.get(f"/tasks/{t['id']}/sessions", headers=admin_headers)
    assert len(r.json()) == 2
    # The list view aggregates session hours.
    r = await client.get("/tasks", headers=admin_headers)
    listed = next(x for x in r.json() if x["id"] == t["id"])
    assert float(listed["session_hours"]) == 6.0


async def test_session_delete_requires_author_or_elevated(client, admin_headers, org):
    from tests.conftest import create_user, login_and_set_password
    t = await _task(client, admin_headers)
    r = await client.post(f"/tasks/{t['id']}/sessions",
                           json={"started_at": "2026-07-06T09:00:00", "hours": 1},
                           headers=admin_headers)
    sid = r.json()["id"]
    # Another (non-elevated) user, assigned so they can see the task at all.
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    await client.post(f"/tasks/{t['id']}/assignees", json={"user_id": user["id"]}, headers=admin_headers)
    r = await client.delete(f"/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    r = await client.delete(f"/sessions/{sid}", headers=admin_headers)  # admin = elevated
    assert r.status_code == 200


async def test_task_links_round_trip(client, admin_headers, org):
    t = await _task(client, admin_headers)
    r = await client.post(f"/tasks/{t['id']}/links",
                           json={"url": "https://drive.google.com/file/d/abc", "label": "MVR draft", "kind": "drive"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    link_id = r.json()["id"]
    assert (await client.post(f"/tasks/{t['id']}/links", json={"url": "javascript:alert(1)"},
                              headers=admin_headers)).status_code == 422
    r = await client.get(f"/tasks/{t['id']}", headers=admin_headers)
    assert len(r.json()["links"]) == 1
    assert (await client.delete(f"/tasks/{t['id']}/links/{link_id}", headers=admin_headers)).status_code == 200


async def test_recurrence_materializes_next_instance_on_completion(client, admin_headers, org):
    t = await _task(client, admin_headers, due_date="2026-07-06",
                    recurrence={"freq": "weekly", "interval": 1})
    r = await client.patch(f"/tasks/{t['id']}", json={"status": "completed"}, headers=admin_headers)
    assert r.status_code == 200
    nxt = r.json().get("next_instance")
    assert nxt, "completing a recurring task must spawn the next instance"
    assert nxt["status"] == "pending"
    assert nxt["due_date"] == "2026-07-13"

    # `until` in the past stops the chain.
    t2 = await _task(client, admin_headers, due_date="2026-07-06",
                     recurrence={"freq": "weekly", "interval": 1, "until": "2026-07-10"})
    r = await client.patch(f"/tasks/{t2['id']}", json={"status": "completed"}, headers=admin_headers)
    assert r.json().get("next_instance") is None

    # Bad recurrence rejected up front.
    r = await client.post("/tasks", json={"title": "x", "recurrence": {"freq": "hourly"}}, headers=admin_headers)
    assert r.status_code == 422


async def test_report_hours_by_person_and_overdue(client, admin_headers, org):
    t = await _task(client, admin_headers, due_date="2026-06-01")  # overdue vs any later ref
    # One weekend + one regular session inside the Fri 2026-07-03 → Thu 2026-07-09 window.
    for payload in ({"started_at": "2026-07-04T14:00:00", "hours": 3},      # Sat → weekend
                    {"started_at": "2026-07-06T10:00:00", "hours": 2}):     # Mon → regular
        r = await client.post(f"/tasks/{t['id']}/sessions", json=payload, headers=admin_headers)
        assert r.status_code == 201

    r = await client.get("/reports/weekly?ref_date=2026-07-08", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    people = body["hours_by_person"]
    assert len(people) == 1
    b = people[0]
    assert b["weekend"] == 3 and b["regular"] == 2 and b["total"] == 5
    assert b["username"], "per-person hours must resolve the username app-side"
    assert any(o["id"] == t["id"] for o in body["overdue"])
    assert body["task_types"].get("other", 0) >= 1
