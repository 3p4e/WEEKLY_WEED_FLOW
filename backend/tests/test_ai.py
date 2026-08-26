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


async def test_data_func_rejects_malformed_context_week_id(client, admin_headers):
    """H11: context.week_id is a caller-supplied body field reaching a raw
    SQL WHERE clause (_task_context) — a garbage value used to 500 from an
    uncaught asyncpg cast error instead of a clean 422."""
    r = await client.post("/ai/weekly_summary",
                          json={"input": "summarise please", "context": {"week_id": "not-a-uuid"}},
                          headers=admin_headers)
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


async def test_put_binding_validates_agent_id_when_letta_reachable(client, admin_headers, org, monkeypatch):
    """Best-effort typo guard on set_binding: when the Letta agent list CAN be
    retrieved, a binding to an id that isn't in it is rejected (422), while a
    binding to a real id succeeds. When the list source is UNavailable (Letta
    down/offline), the check is skipped and the binding still goes through — the
    guard defends against typos, it is never a hard dependency that would break
    binding while Letta is unreachable."""
    async def fake_agents():
        return [{"id": "agent-real", "name": "Planner"}]
    monkeypatch.setattr(ai_module, "_letta_agents", fake_agents)
    # a bogus id (not in the retrieved roster) is refused
    r = await client.put("/ai/bindings/weekly_summary",
                         json={"letta_agent_id": "agent-does-not-exist", "is_active": True},
                         headers=admin_headers)
    assert r.status_code == 422, r.text
    # a real id binds cleanly
    r = await client.put("/ai/bindings/weekly_summary",
                         json={"letta_agent_id": "agent-real", "is_active": True},
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["letta_agent_id"] == "agent-real"

    # Letta unreachable → validation skipped, binding still works (best-effort).
    async def boom():
        raise RuntimeError("Letta unreachable")
    monkeypatch.setattr(ai_module, "_letta_agents", boom)
    r = await client.put("/ai/bindings/weekly_summary",
                         json={"letta_agent_id": "agent-unchecked", "is_active": True},
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["letta_agent_id"] == "agent-unchecked"


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


# ── TMS T3: AI-native planning — new catalog functions + task-scoped context ─
async def test_workload_balance_and_next_week_plan_in_catalog(client, admin_headers):
    """The two new T3 functions are just catalog entries — reusing the same
    generic invoke() path (the fleet pattern the DocEngine established): no
    new endpoint, just an admin binding away from being active."""
    r = await client.get("/ai/functions", headers=admin_headers)
    assert r.status_code == 200
    catalog = r.json()["catalog"]
    assert "workload_balance" in catalog
    assert "next_week_plan" in catalog


async def test_dependency_advisor_scopes_to_task_family_not_whole_corpus(client, admin_headers, org, monkeypatch):
    """T3: dependency_advisor invoked with context.task_id should ground on
    that task's family (itself + parent + siblings) instead of the org-wide
    _task_context — verified the same way as the week-scope regression test,
    by intercepting _letta_message and inspecting the prompt it received."""
    import app.api.ai as ai_module

    captured = {}

    async def fake_letta_message(agent_id, text):
        captured["prompt"] = text
        return "ok"

    monkeypatch.setattr(ai_module, "_letta_message", fake_letta_message)

    await tasks_admin_pool().execute(
        "INSERT INTO ai_agent_bindings(org_id, function_key, scope, letta_agent_id, is_active)"
        " VALUES ($1,'dependency_advisor','org','fake-agent-id',true)", org["org_id"])

    parent = (await client.post("/tasks", json={"title": "Family Parent"},
                                headers=admin_headers)).json()
    await client.post("/tasks", json={"title": "Family Sibling", "parent_id": parent["id"]},
                      headers=admin_headers)
    target = (await client.post("/tasks", json={"title": "Family Target", "parent_id": parent["id"]},
                                 headers=admin_headers)).json()
    await client.post("/tasks", json={"title": "Unrelated Outsider Task"}, headers=admin_headers)

    r = await client.post("/ai/dependency_advisor",
                          json={"input": "suggest dependencies", "context": {"task_id": target["id"]}},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["available"] is True

    prompt = captured["prompt"]
    assert "Family Target" in prompt
    assert "Family Parent" in prompt
    assert "Family Sibling" in prompt
    assert "Unrelated Outsider Task" not in prompt


# ── Role→capability matrix (FUNCTION_ROLES) ─────────────────────────────────
# The generic invoke() used to admit any authenticated user to any bound
# function; the matrix gates each function to a role tier and /ai/functions
# filters its catalog to what the caller may actually use.

async def test_user_role_blocked_from_planning_and_elevated_tiers(client, admin_headers):
    headers = await _user_headers(client, admin_headers, role="USER")
    for fn in ("weekly_summary", "workload_balance", "next_week_plan",
               "corpus_qa", "task_extract"):
        r = await client.post(f"/ai/{fn}", json={"input": "hi"}, headers=headers)
        assert r.status_code == 403, f"{fn}: {r.status_code} {r.text}"


async def test_user_role_keeps_personal_tier(client, admin_headers):
    headers = await _user_headers(client, admin_headers, role="USER")
    # Personal-tier function passes the gate; with no binding it degrades to
    # the normal not_configured envelope rather than 403.
    r = await client.post("/ai/translate_bilingual", json={"input": "hello"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["reason"] == "not_configured"


async def test_manager_gets_elevated_tier(client, admin_headers):
    """Managers pass the access gate for every elevated function — their
    DIFFERENTIATION from executives is grounding breadth, not denial:
    test_ai_corpus_is_scoped_to_managers_department proves the same function
    grounds only on the manager's own department."""
    headers = await _user_headers(client, admin_headers, role="QC_MGR")
    for fn in ("corpus_qa", "next_week_plan", "weekly_summary"):
        r = await client.post(f"/ai/{fn}", json={"input": "q"}, headers=headers)
        assert r.status_code == 200, f"{fn}: {r.text}"
        assert r.json()["reason"] == "not_configured"


async def test_executive_gets_planning_tier(client, admin_headers):
    headers = await _user_headers(client, admin_headers, role="CEO")
    r = await client.post("/ai/weekly_summary", json={"input": "summarise"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["reason"] == "not_configured"


async def test_functions_listing_is_filtered_by_role(client, admin_headers):
    r = await client.get("/ai/functions", headers=admin_headers)
    assert r.status_code == 200
    assert "weekly_summary" in r.json()["catalog"]          # ADMIN sees everything

    headers = await _user_headers(client, admin_headers, role="USER")
    r = await client.get("/ai/functions", headers=headers)
    assert r.status_code == 200
    cat = r.json()["catalog"]
    assert "translate_bilingual" in cat                      # personal tier stays
    assert "weekly_summary" not in cat                       # planning tier hidden
    assert "corpus_qa" not in cat                            # elevated tier hidden


async def test_dependency_advisor_rejects_garbage_task_id(client, admin_headers):
    """M1: the dependency_advisor task_id is a caller-supplied BODY param. It is
    uuid-guarded (garbage → 422, not an asyncpg cast 500) before the family-context
    load, and the same code path runs _assert_scope_visible so a dept-scoped manager
    cannot read another department's task family through the agent."""
    r = await client.post("/ai/dependency_advisor",
                          json={"input": "suggest dependencies",
                                "context": {"task_id": "not-a-uuid"}},
                          headers=admin_headers)
    assert r.status_code == 422


# ── GET /ai/pins: FUNCTION_ROLES applied to org-wide (subject-less) pins ────
# H-severity fix: list_pins used to be gated only by require_password_set, so
# any authenticated USER could read the org-wide weekly_report/next_week_plan
# narrative the scheduler archives with subject_user_id NULL — even though
# invoke() 403s that same USER for POST /ai/next_week_plan. RLS's org_isolation
# policy opens subject_user_id IS NULL rows to every org member by design (that
# part is correct and untouched); the missing piece was applying the same
# role tier invoke() enforces to those subject-less rows specifically.


async def test_pins_filter_org_wide_elevated_pin_but_keep_users_own_pin(client, admin_headers, org):
    headers = await _user_headers(client, admin_headers, role="USER")
    r = await client.get("/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    my_id = r.json()["id"]

    # Org-wide (subject_user_id NULL) pin for an elevated-only function — the
    # scheduler's real shape for the weekly next_week_plan narrative.
    await tasks_admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body, subject_user_id)"
        " VALUES ($1,'next_week_plan','Org next week plan','elevated-only narrative',NULL)",
        org["org_id"])
    # The same USER's own per-user pin, under a personal-tier function_key
    # (weekly_report_user is not in FUNCTION_ROLES, matching what
    # weekly_snapshot.py actually writes for per-person reports) — must stay
    # visible regardless of the org-wide filter above.
    await tasks_admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body, subject_user_id)"
        " VALUES ($1,'weekly_report_user','My own weekly report','personal narrative',$2)",
        org["org_id"], my_id)

    # Filtered by the elevated-only function_key: the org-wide pin must not
    # come back for a base USER.
    r = await client.get("/ai/pins", params={"function_key": "next_week_plan"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == [], "USER must not read the org-wide pin for an elevated-only function"

    # Unfiltered listing: the org-wide elevated pin is absent, the user's own
    # personal pin is present.
    r = await client.get("/ai/pins", headers=headers)
    assert r.status_code == 200, r.text
    titles = [p["title"] for p in r.json()]
    assert "Org next week plan" not in titles
    assert "My own weekly report" in titles

    # An elevated role (ADMIN) still sees the org-wide pin — this is a read
    # filter for base USERs, not a data deletion or a blanket block.
    r = await client.get("/ai/pins", params={"function_key": "next_week_plan"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert any(p["title"] == "Org next week plan" for p in r.json())


async def test_pins_user_own_pin_visible_even_under_elevated_function_key(client, admin_headers, org):
    """Defense in depth: even if a PER-USER pin were archived under an
    elevated-only function_key (subject_user_id set, not just the
    _user-suffixed keys the scheduler happens to use today), its subject must
    still read it — the FUNCTION_ROLES gate in list_pins applies only to
    subject-less rows, never to a pin that already names its own owner."""
    headers = await _user_headers(client, admin_headers, role="USER")
    r = await client.get("/auth/me", headers=headers)
    my_id = r.json()["id"]

    await tasks_admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body, subject_user_id)"
        " VALUES ($1,'next_week_plan','My personal next-week plan','mine',$2)",
        org["org_id"], my_id)

    r = await client.get("/ai/pins", params={"function_key": "next_week_plan"}, headers=headers)
    assert r.status_code == 200, r.text
    titles = [p["title"] for p in r.json()]
    assert "My personal next-week plan" in titles
