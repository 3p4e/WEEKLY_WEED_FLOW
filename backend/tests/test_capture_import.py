"""POST /capture/import — the capture prompt's delivery end. The properties
that matter: idempotency (same payload twice → second run is a no-op),
forward-only status merges, session/link/subtask dedup, owner gating, and
per-task skip (one bad task never aborts the batch)."""
import os

from tests.conftest import create_user, login_and_set_password


def _payload(ref="pp-qc-sop-099", owner=None, **task_over):
    task = {
        "action": "create",
        "external_ref": ref,
        "title": "PP-QC-SOP-099 Test SOP",
        "description": "Drafting the test SOP",
        "status": "ongoing",
        "priority": "high",
        "task_type": "sop",
        "reference_code": "PP-QC-SOP-099",
        "department": "qc",
        "tags": ["sop", "test"],
        "week_start": "2026-07-03",
        "due_date": "2026-07-16",
        "sessions": [
            {"started_at": "2026-07-04T14:00:00", "hours": 2.0,
             "time_estimated": False, "note": "first sitting"},
        ],
        "links": [{"url": "https://drive.google.com/x", "label": "draft", "kind": "drive"}],
        "subtasks": [{"title": "Annex A01", "status": "pending"}],
    }
    if owner:
        task["owner"] = owner
    task.update(task_over)
    return {"session_meta": {"prompt_version": "wwf-capture/v2.1"}, "tasks": [task]}


async def test_import_create_then_idempotent_reimport(client, admin_headers, org):
    r = await client.post("/capture/import", json=_payload(), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 0
    assert body["sessions_added"] == 1 and body["skipped"] == []

    # Same payload again: updates the row (forward merge) but adds nothing.
    r = await client.post("/capture/import", json=_payload(), headers=admin_headers)
    body = r.json()
    assert body["created"] == 0 and body["updated"] == 1
    assert body["sessions_added"] == 0

    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    matches = [t for t in r.json() if t.get("external_ref") == "pp-qc-sop-099"]
    assert len(matches) == 1
    t = matches[0]
    assert t["task_type"] == "sop" and t["due_date"] == "2026-07-16"
    assert float(t["session_hours"]) == 2.0
    assert t["subtask_count"] == 1

    # The imported weekend session must be classification-ready.
    r = await client.get(f"/tasks/{t['id']}/sessions", headers=admin_headers)
    s = r.json()[0]
    assert s["classification"] == "weekend" and s["source"] == "capture"


async def test_import_date_only_session(client, admin_headers, org):
    """A session with only started_at — duration genuinely unknown, per the
    capture contract — is legal: it contributes 0 hours but is still recorded
    and classified from its start time."""
    r = await client.post("/capture/import", json=_payload(
        ref="date-only-1",
        sessions=[{"started_at": "2026-07-04T14:00:00", "hours": None,
                   "ended_at": None, "time_estimated": True, "note": "unknown duration"}],
    ), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and body["skipped"] == []
    assert body["sessions_added"] == 1

    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    t = next(x for x in r.json() if x.get("external_ref") == "date-only-1")
    assert float(t["session_hours"]) == 0.0

    r = await client.get(f"/tasks/{t['id']}/sessions", headers=admin_headers)
    s = r.json()[0]
    assert s["hours"] == 0.0 and s["classification"] == "weekend"


async def test_import_status_never_regresses(client, admin_headers, org):
    await client.post("/capture/import",
                      json=_payload(ref="reg-1", status="completed", completed_date="2026-07-01"),
                      headers=admin_headers)
    r = await client.post("/capture/import", json=_payload(ref="reg-1", status="ongoing"),
                          headers=admin_headers)
    assert r.json()["updated"] == 1
    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    t = next(x for x in r.json() if x.get("external_ref") == "reg-1")
    assert t["status"] == "completed"


async def test_import_owner_gating(client, admin_headers, org):
    """A non-admin can import their own work but not someone else's."""
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/capture/import", json=_payload(ref="own-1", owner=user["username"]),
                          headers=headers)
    assert r.json()["created"] == 1

    r = await client.post("/capture/import", json=_payload(ref="theft-1", owner=org["username"]),
                          headers=headers)
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"][0]["reason"] == "not allowed to import for another owner"

    # ADMIN importing for another owner is allowed.
    r = await client.post("/capture/import", json=_payload(ref="admin-for-user", owner=user["username"]),
                          headers=admin_headers)
    assert r.json()["created"] == 1


async def test_import_bad_task_skipped_batch_continues(client, admin_headers, org):
    payload = _payload(ref="good-1")
    bad = _payload(ref="bad-1", status="working")["tasks"][0]          # invalid enum
    bad2 = _payload(ref="bad-2", owner="nobody_here")["tasks"][0]      # unknown owner
    payload["tasks"] += [bad, bad2]
    r = await client.post("/capture/import", json=payload, headers=admin_headers)
    body = r.json()
    assert body["created"] == 1
    reasons = {s["external_ref"]: s["reason"] for s in body["skipped"]}
    assert "invalid status" in reasons["bad-1"]
    assert "unknown owner" in reasons["bad-2"]


async def test_import_provisions_calendar_week(client, admin_headers, org):
    await client.post("/capture/import", json=_payload(ref="week-1", week_start="2026-06-26"),
                      headers=admin_headers)
    r = await client.get("/weeks", headers=admin_headers)
    assert any(w["starts_on"] <= "2026-06-26" <= w["ends_on"] for w in r.json())


async def test_static_capture_token_acts_as_configured_user(client, admin_headers, org, monkeypatch):
    """The connector path: CAPTURE_IMPORT_TOKEN (only on this route) acts as
    CAPTURE_IMPORT_USER. Wrong token → 401; right token → import lands on
    the configured user; the token opens no other route."""
    user, otp = await create_user(client, admin_headers, full_name="Capture Bot Target")
    token = await login_and_set_password(client, user["username"], otp)
    monkeypatch.setenv("CAPTURE_IMPORT_TOKEN", "test-capture-token-123")
    monkeypatch.setenv("CAPTURE_IMPORT_USER", user["username"])

    r = await client.post("/capture/import", json=_payload(ref="conn-1"),
                          headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401

    r = await client.post("/capture/import", json=_payload(ref="conn-1"),
                          headers={"Authorization": "Bearer test-capture-token-123"})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    # Owner defaulted to the configured capture user, not anyone else.
    hdrs = {"Authorization": f"Bearer {token}"}
    r = await client.get("/tasks?include_archived=true", headers=hdrs)
    assert any(t.get("external_ref") == "conn-1" for t in r.json())

    # The static token is NOT a general credential.
    r = await client.get("/tasks", headers={"Authorization": "Bearer test-capture-token-123"})
    assert r.status_code == 401
