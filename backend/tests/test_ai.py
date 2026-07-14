"""P2 — the AI gateway's graceful-degradation contract (ai.py's own docstring:
"Every call degrades gracefully ... instead of erroring, so the UI can fall
back"). No Letta stack exists in the test environment, so every scenario
here exercises that degradation path for real rather than mocking it away —
which is also the only way most self-hosted orgs will ever see this
endpoint behave, since most won't have an ai_agent_bindings row configured
for every function.

The second half covers the admin surface that the Settings "AI" tab drives —
the ai_agent_bindings CRUD (GET/PUT/DELETE /ai/bindings) and the Letta agent
picker (GET /ai/agents). Those endpoints are role-gated (require_role(ADMIN)),
and every outbound Letta call is monkeypatched, so no test here ever touches
the network."""
import app.api.ai as ai_module
from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


async def _user_headers(client, admin_headers, role="USER"):
    """A real (non-admin) session: provision via the API, complete the forced
    first-login password change, and return its bearer header."""
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return {"Authorization": f"Bearer {token}"}


async def test_unknown_function_key(client, admin_headers):
    r = await client.post("/ai/not_a_real_function", json={"input": "hello"}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["reason"] == "unknown_function"


async def test_known_function_with_no_binding_is_not_configured(client, admin_headers):
    r = await client.post("/ai/weekly_summary", json={"input": "summarise please"}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["reason"] == "not_configured"


async def test_missing_input_field_rejected(client, admin_headers):
    """Regression: the frontend used to send {week_id, kind} / {message}
    instead of {input}, guaranteeing a 422 the UI never surfaced clearly."""
    r = await client.post("/ai/weekly_summary", json={"week_id": "x", "kind": "report"}, headers=admin_headers)
    assert r.status_code == 422


async def test_configured_but_unreachable_agent_degrades_gracefully(client, admin_headers, org, monkeypatch):
    """A binding exists (so the function is "configured"), but the Letta
    endpoint itself doesn't exist in this environment — exercises the
    _letta_message failure path end-to-end instead of asserting it in the
    abstract. Point at a fast-failing address so this doesn't hang on the
    real 30s httpx timeout or on host.docker.internal DNS resolution."""
    from app.config import settings
    monkeypatch.setattr(settings, "letta_base_url", "http://127.0.0.1:1")

    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'weekly_summary','org','fake-agent-id',true)", org["org_id"])

    r = await client.post("/ai/weekly_summary", json={"input": "summarise please"}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["reason"] == "letta_unreachable"


async def test_week_scoped_context_filters_task_corpus(client, admin_headers, org, monkeypatch):
    """Regression for the context-ignored bug: _task_context used to always
    ground on an org-wide recent-200-tasks scan regardless of which week the
    caller asked about. Can't reach a real Letta agent here, but we can
    intercept _letta_message and assert on the prompt it was actually given —
    proving the week filter reached the grounding query."""
    import app.api.ai as ai_module

    captured = {}

    async def fake_letta_message(agent_id, text):
        captured["prompt"] = text
        return "ok"

    monkeypatch.setattr(ai_module, "_letta_message", fake_letta_message)

    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'weekly_summary','org','fake-agent-id',true)", org["org_id"])

    # A fresh org has no calendar_weeks (org-scoped, not seeded by the `org`
    # fixture) — insert the two this test actually needs.
    await tasks_admin_pool().execute(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
        " ($1,2026,1,'2026-01-05','2026-01-11'), ($1,2026,2,'2026-01-12','2026-01-18')", org["org_id"])
    r = await client.get("/weeks", headers=admin_headers)
    weeks = r.json()
    target_week = weeks[0]

    await client.post("/tasks", json={
        "title": "In the target week", "status": "pending", "week_id": target_week["id"],
    }, headers=admin_headers)
    other_week = next((w for w in weeks if w["id"] != target_week["id"]), None)
    if other_week:
        await client.post("/tasks", json={
            "title": "In a different week", "status": "pending", "week_id": other_week["id"],
        }, headers=admin_headers)

    r = await client.post("/ai/weekly_summary", json={
        "input": "Summarise this week", "context": {"week_id": target_week["id"], "kind": "report"},
    }, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["available"] is True

    assert "In the target week" in captured["prompt"]
    if other_week:
        assert "In a different week" not in captured["prompt"]


# ── Admin: ai_agent_bindings CRUD (Settings "AI" tab) ───────────────────────


async def test_list_bindings_empty_for_new_org(client, admin_headers, org):
    """A fresh org has no bindings configured — the endpoint returns a plain
    (empty) list, not an error, so the Settings tab can render a clean slate."""
    r = await client.get("/ai/bindings", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


async def test_list_bindings_forbidden_for_non_admin(client, admin_headers):
    headers = await _user_headers(client, admin_headers)
    r = await client.get("/ai/bindings", headers=headers)
    assert r.status_code == 403


async def test_put_binding_creates_then_upserts(client, admin_headers, org):
    """PUT points an AI function at a Letta agent (org-scoped). A second PUT for
    the SAME function_key must update in place — there's no unique constraint,
    so a duplicated row would silently shadow the intended binding."""
    r = await client.put("/ai/bindings/weekly_summary",
                          json={"letta_agent_id": "agent-xyz", "is_active": True},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["function_key"] == "weekly_summary"
    assert body["letta_agent_id"] == "agent-xyz"
    assert body["is_active"] is True

    r = await client.get("/ai/bindings", headers=admin_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["function_key"] == "weekly_summary"
    assert rows[0]["letta_agent_id"] == "agent-xyz"
    assert rows[0]["is_active"] is True

    # Upsert: same key, different agent → updated in place, still one row.
    r = await client.put("/ai/bindings/weekly_summary",
                          json={"letta_agent_id": "agent-abc", "is_active": True},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["letta_agent_id"] == "agent-abc"

    r = await client.get("/ai/bindings", headers=admin_headers)
    rows = [b for b in r.json() if b["function_key"] == "weekly_summary"]
    assert len(rows) == 1  # updated, not duplicated
    assert rows[0]["letta_agent_id"] == "agent-abc"


async def test_put_binding_unknown_function_key_rejected(client, admin_headers):
    """A function_key not in the CATALOG is a 422 — bindings may only point at
    functions the gateway actually knows how to invoke."""
    r = await client.put("/ai/bindings/not_a_real_function",
                          json={"letta_agent_id": "agent-xyz", "is_active": True},
                          headers=admin_headers)
    assert r.status_code == 422


async def test_put_binding_forbidden_for_non_admin(client, admin_headers):
    headers = await _user_headers(client, admin_headers)
    r = await client.put("/ai/bindings/weekly_summary",
                          json={"letta_agent_id": "agent-xyz", "is_active": True},
                          headers=headers)
    assert r.status_code == 403


async def test_delete_binding_removes_it(client, admin_headers, org):
    r = await client.put("/ai/bindings/voice_capture",
                          json={"letta_agent_id": "agent-xyz", "is_active": True},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.get("/ai/bindings", headers=admin_headers)
    assert any(b["function_key"] == "voice_capture" for b in r.json())

    r = await client.delete("/ai/bindings/voice_capture", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    r = await client.get("/ai/bindings", headers=admin_headers)
    assert not any(b["function_key"] == "voice_capture" for b in r.json())


async def test_delete_binding_forbidden_for_non_admin(client, admin_headers):
    headers = await _user_headers(client, admin_headers)
    r = await client.delete("/ai/bindings/weekly_summary", headers=headers)
    assert r.status_code == 403


# ── Admin: the Letta agent picker (GET /ai/agents) ──────────────────────────


async def test_list_agents_returns_letta_agents(client, admin_headers, monkeypatch):
    """The agent picker surfaces the Letta agents a binding can point at. The
    real call reaches the Letta stack (absent here), so patch _letta_agents to
    a canned roster and assert the endpoint returns it under {"agents": ...}."""
    async def fake_agents():
        return [{"id": "agent-1", "name": "Planner"},
                {"id": "agent-2", "name": "Scribe"}]

    monkeypatch.setattr(ai_module, "_letta_agents", fake_agents)

    r = await client.get("/ai/agents", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"agents": [
        {"id": "agent-1", "name": "Planner"},
        {"id": "agent-2", "name": "Scribe"},
    ]}


async def test_list_agents_forbidden_before_any_network_call(client, admin_headers, monkeypatch):
    """require_role(ADMIN) must reject a non-admin before any Letta call is
    made — patch _letta_agents to blow up if it's ever reached, proving the
    403 short-circuits ahead of the network."""
    async def boom():
        raise AssertionError("Letta must not be contacted for a forbidden caller")

    monkeypatch.setattr(ai_module, "_letta_agents", boom)

    headers = await _user_headers(client, admin_headers)
    r = await client.get("/ai/agents", headers=headers)
    assert r.status_code == 403


# ── Invoke: the configured (available:true) path ────────────────────────────


async def test_invoke_with_binding_returns_letta_message(client, admin_headers, org, monkeypatch):
    """With an active binding and a reachable agent, invoke returns
    available:true and the agent's message text. draft_description is not a
    corpus-grounded function, so no task context is needed — patch
    _letta_message to a canned reply and assert it round-trips as `output`."""
    captured = {}

    async def fake_letta_message(agent_id, text):
        captured["agent_id"] = agent_id
        return "Here is your drafted description."

    monkeypatch.setattr(ai_module, "_letta_message", fake_letta_message)

    r = await client.put("/ai/bindings/draft_description",
                          json={"letta_agent_id": "agent-xyz", "is_active": True},
                          headers=admin_headers)
    assert r.status_code == 200, r.text

    r = await client.post("/ai/draft_description",
                          json={"input": "Repot the mother plants"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["function"] == "draft_description"
    assert body["output"] == "Here is your drafted description."
    assert captured["agent_id"] == "agent-xyz"


async def test_ai_corpus_is_scoped_to_managers_department(client, admin_headers, org, monkeypatch):
    """M2: a department-scoped manager's AI grounding corpus must contain ONLY
    their own department's tasks. RLS grants any elevated role org-wide task
    read, so without the dept filter in _task_context the corpus would leak
    other departments' work into the manager's AI answer. Intercept the Letta
    call and assert on the prompt that was actually built."""
    captured = {}

    async def fake_letta_message(agent_id, text):
        captured["prompt"] = text
        return "ok"

    monkeypatch.setattr(ai_module, "_letta_message", fake_letta_message)

    d_qc = (await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id,code,name) VALUES ($1,'qc','QC') RETURNING id", org["org_id"]))["id"]
    d_pr = (await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id,code,name) VALUES ($1,'pr','Production') RETURNING id", org["org_id"]))["id"]

    await client.post("/tasks", json={"title": "QCONLYMARKER", "department_id": str(d_qc)}, headers=admin_headers)
    await client.post("/tasks", json={"title": "PRONLYMARKER", "department_id": str(d_pr)}, headers=admin_headers)

    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'weekly_summary','org','fake-agent-id',true)", org["org_id"])

    mgr, otp = await create_user(client, admin_headers, role="QC_MGR", department_id=str(d_qc))
    token = await login_and_set_password(client, mgr["username"], otp)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post("/ai/weekly_summary", json={"input": "summarise"}, headers=h)
    assert r.status_code == 200
    assert "QCONLYMARKER" in captured["prompt"], "manager's own department task must ground the answer"
    assert "PRONLYMARKER" not in captured["prompt"], "another department's task must NOT leak into the corpus"


async def test_ai_corpus_is_org_wide_for_executives(client, admin_headers, org, monkeypatch):
    """M2 must not over-restrict: an org-wide role (CEO) still grounds on every
    department's tasks."""
    captured = {}

    async def fake_letta_message(agent_id, text):
        captured["prompt"] = text
        return "ok"

    monkeypatch.setattr(ai_module, "_letta_message", fake_letta_message)

    d_qc = (await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id,code,name) VALUES ($1,'qc','QC') RETURNING id", org["org_id"]))["id"]
    d_pr = (await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id,code,name) VALUES ($1,'pr','Production') RETURNING id", org["org_id"]))["id"]
    await client.post("/tasks", json={"title": "QCMARK", "department_id": str(d_qc)}, headers=admin_headers)
    await client.post("/tasks", json={"title": "PRMARK", "department_id": str(d_pr)}, headers=admin_headers)
    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'weekly_summary','org','fake-agent-id',true)", org["org_id"])

    ceo, otp = await create_user(client, admin_headers, role="CEO")
    token = await login_and_set_password(client, ceo["username"], otp)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/ai/weekly_summary", json={"input": "summarise"}, headers=h)
    assert r.status_code == 200
    assert "QCMARK" in captured["prompt"] and "PRMARK" in captured["prompt"]
