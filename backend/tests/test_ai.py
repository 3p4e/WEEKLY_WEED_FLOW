"""P2 — the AI gateway's graceful-degradation contract (ai.py's own docstring:
"Every call degrades gracefully ... instead of erroring, so the UI can fall
back"). No Letta stack exists in the test environment, so every scenario
here exercises that degradation path for real rather than mocking it away —
which is also the only way most self-hosted orgs will ever see this
endpoint behave, since most won't have an ai_agent_bindings row configured
for every function."""
from app.db import admin_pool


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

    await admin_pool().execute(
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

    await admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'weekly_summary','org','fake-agent-id',true)", org["org_id"])

    # A fresh org has no calendar_weeks (org-scoped, not seeded by the `org`
    # fixture) — insert the two this test actually needs.
    await admin_pool().execute(
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
