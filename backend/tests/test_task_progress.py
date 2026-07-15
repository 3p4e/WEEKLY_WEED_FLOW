"""tasks.progress — the explicit completion percentage (migration 0014).

Pins the decoupling rules: progress is display state the worklog panel sets;
completing a task forward-fills 100, but progress=100 NEVER forces status
(never hard-enforce completion), and reopening keeps the percentage.
"""


async def test_progress_roundtrip_and_default(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Bar to fill"}, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["progress"] == 0
    tid = r.json()["id"]
    r = await client.patch(f"/tasks/{tid}", json={"progress": 40}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["progress"] == 40
    # survives the list SELECT
    listed = (await client.get("/tasks", headers=admin_headers)).json()
    assert next(t for t in listed if t["id"] == tid)["progress"] == 40


async def test_progress_bounds_422(client, admin_headers):
    assert (await client.post("/tasks", json={"title": "x", "progress": 101},
                              headers=admin_headers)).status_code == 422
    assert (await client.post("/tasks", json={"title": "x", "progress": -1},
                              headers=admin_headers)).status_code == 422
    r = await client.post("/tasks", json={"title": "x", "progress": 100}, headers=admin_headers)
    assert r.status_code == 201
    assert (await client.patch(f"/tasks/{r.json()['id']}", json={"progress": 250},
                               headers=admin_headers)).status_code == 422


async def test_completion_forward_fills_100(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Finish me", "progress": 30}, headers=admin_headers)
    tid = r.json()["id"]
    done = (await client.patch(f"/tasks/{tid}", json={"status": "completed"}, headers=admin_headers)).json()
    assert done["progress"] == 100
    # reopening keeps the percentage — no silent reset
    back = (await client.patch(f"/tasks/{tid}", json={"status": "ongoing"}, headers=admin_headers)).json()
    assert back["progress"] == 100 and back["status"] == "ongoing"


async def test_progress_100_never_forces_status(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Never auto-done"}, headers=admin_headers)
    tid = r.json()["id"]
    row = (await client.patch(f"/tasks/{tid}", json={"progress": 100}, headers=admin_headers)).json()
    assert row["progress"] == 100
    assert row["status"] == "pending"          # untouched
    assert row["completed_date"] is None        # not stamped


async def test_recurring_next_instance_starts_at_zero(client, admin_headers):
    r = await client.post("/tasks", json={
        "title": "Weekly check", "progress": 60,
        "recurrence": {"freq": "weekly", "interval": 1},
        "due_date": "2026-07-17",
    }, headers=admin_headers)
    tid = r.json()["id"]
    done = (await client.patch(f"/tasks/{tid}", json={"status": "completed"}, headers=admin_headers)).json()
    assert done["progress"] == 100
    assert done["next_instance"]["progress"] == 0
