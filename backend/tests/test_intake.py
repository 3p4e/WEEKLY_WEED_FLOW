"""AI Intake — extract task candidates from pasted text, then adopt the chosen
ones through the capture-import path. Every Letta call is monkeypatched (no test
touches a real agent); adoption exercises the real /capture/import endpoint."""
from app.db import tasks_admin_pool


async def _bind(org_id, function_key, agent="fake-agent"):
    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,$2,'org',$3,true)", org_id, function_key, agent)


async def _seed_dept(org_id, code="PP-QC", name="Quality Control"):
    return await tasks_admin_pool().fetchval(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,$2,$3) RETURNING id",
        org_id, code, name)


async def test_extract_not_configured_without_binding(client, admin_headers, org):
    r = await client.post("/intake/extract", json={"text": "Do the HPLC validation and file the CAPA."},
                          headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"available": False, "reason": "not_configured"}


async def test_extract_normalizes_candidates(client, admin_headers, org, monkeypatch):
    import app.api.intake as intake
    await _seed_dept(org["org_id"])
    await _bind(org["org_id"], "task_extract")

    # Model reply: prose wrapper + code fence + a synonym priority + a dept NAME
    # (not code) + mixed string/object subtasks + one title-less junk entry.
    reply = '''Sure, here are the tasks:
```json
[
  {"title": "Validate HPLC method", "description": "System suitability + linearity",
   "department": "Quality Control", "priority": "urgent", "task_type": "validation",
   "due_date": "2026-02-01", "estimated_hours": 6,
   "subtasks": [{"title": "Prep standards", "description": "6-point curve"}, "Equilibrate column"]},
  {"title": "", "description": "junk with no title"}
]
```'''

    async def fake(agent_id, text):
        return reply
    monkeypatch.setattr(intake, "_letta_message", fake)

    r = await client.post("/intake/extract", json={"text": "please extract these tasks now"},
                          headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["count"] == 1  # junk dropped
    c = body["candidates"][0]
    assert c["title"] == "Validate HPLC method"
    assert c["department"] == "PP-QC"          # name → canonical code
    assert c["priority"] == "critical"          # 'urgent' synonym clamped
    assert c["task_type"] == "validation"
    assert c["due_date"] == "2026-02-01"
    assert [s["title"] for s in c["subtasks"]] == ["Prep standards", "Equilibrate column"]
    assert c["subtasks"][0]["description"] == "6-point curve"
    assert c["subtasks"][1]["description"] is None


async def test_extract_falls_back_to_voice_capture(client, admin_headers, org, monkeypatch):
    import app.api.intake as intake
    await _bind(org["org_id"], "voice_capture")  # only the fallback binding exists

    async def fake(agent_id, text):
        return '[{"title": "Ship the EU GMP dossier"}]'
    monkeypatch.setattr(intake, "_letta_message", fake)

    r = await client.post("/intake/extract", json={"text": "the CEO wants the dossier shipped"},
                          headers=admin_headers)
    assert r.status_code == 200 and r.json()["available"] is True
    assert r.json()["candidates"][0]["title"] == "Ship the EU GMP dossier"


async def test_extract_short_text_rejected(client, admin_headers, org):
    r = await client.post("/intake/extract", json={"text": "hi"}, headers=admin_headers)
    assert r.status_code == 422


async def test_adopt_extracted_tasks_via_capture(client, admin_headers, org):
    """The adopt step: post intake-shaped candidates to /capture/import — tasks
    land in the caller's account, subtasks (with descriptions) become child
    tasks, and a cross-department task keeps its department tag."""
    dept_id = await _seed_dept(org["org_id"], code="PP-SALES", name="Sales")
    payload = {"session_meta": {"source": "ai_intake"}, "tasks": [{
        "external_ref": "intake:test-1",
        "title": "Fulfil bulk order for EU client",
        "description": "500kg order, GMP paperwork",
        "priority": "high", "task_type": "admin",
        "department": "PP-SALES",
        "subtasks": [
            {"title": "Draft the CoA", "description": "Certificate of analysis for the lot"},
            {"title": "Confirm shipping window"},
        ],
    }]}
    r = await client.post("/capture/import", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1 and not r.json()["skipped"]

    # The parent task is owned by the caller and tagged to the (other) department.
    r = await client.get("/tasks", headers=admin_headers)
    parent = next(t for t in r.json() if t["title"] == "Fulfil bulk order for EU client")
    assert parent["department_id"] == str(dept_id)
    assert parent["subtask_count"] == 2

    # Subtasks are real child tasks and carry their descriptions.
    r = await client.get(f"/tasks/{parent['id']}", headers=admin_headers)
    subs = {s["title"]: s for s in r.json()["subtasks"]}
    assert set(subs) == {"Draft the CoA", "Confirm shipping window"}
    assert subs["Draft the CoA"]["description"] == "Certificate of analysis for the lot"


async def test_adopt_operator_scoped_to_self(client, admin_headers, org):
    """A base USER adopting extracted tasks can only create them in their own
    account (capture-import owner-scoping) — the feature is available to all."""
    from tests.conftest import create_user, login_and_set_password
    user, otp = await create_user(client, admin_headers, role="USER")
    tok = await login_and_set_password(client, user["username"], otp)
    h = {"Authorization": f"Bearer {tok}"}
    r = await client.post("/capture/import", json={"session_meta": {}, "tasks": [{
        "external_ref": "intake:op-1", "title": "My own extracted task",
    }]}, headers=h)
    assert r.status_code == 200 and r.json()["created"] == 1
