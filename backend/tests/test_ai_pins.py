"""GET /ai/pins — the read side of the weekly-snapshot archive. Two security
properties matter and both live in the RLS policy, not the endpoint: (1) org
isolation — another org's pins are invisible; (2) per-user visibility — a pin
with subject_user_id set (an individual's AI weekly report) is visible only
to its subject and to elevated roles, never to arbitrary org members."""
import uuid

from app.db import tasks_admin_pool, users_admin_pool
from app.security import hash_password
from tests.conftest import create_user, login_and_set_password


async def _pin(org_id, function_key, title, body="body", subject_user_id=None, prompt_version=None):
    await tasks_admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body, subject_user_id, prompt_version)"
        " VALUES ($1,$2,$3,$4,$5,$6)",
        org_id, function_key, title, body, subject_user_id, prompt_version)


async def test_pins_returned_newest_first_and_filterable(client, admin_headers, org):
    await _pin(org["org_id"], "weekly_report", "Weekly report — W1")
    await _pin(org["org_id"], "next_week_plan", "Next week plan — W2")

    r = await client.get("/ai/pins", headers=admin_headers)
    assert r.status_code == 200, r.text
    keys = [p["function_key"] for p in r.json()]
    assert "weekly_report" in keys and "next_week_plan" in keys

    r = await client.get("/ai/pins", params={"function_key": "weekly_report"}, headers=admin_headers)
    assert r.status_code == 200
    assert all(p["function_key"] == "weekly_report" for p in r.json())
    assert any("Weekly report" in p["title"] for p in r.json())


async def test_pins_require_auth(client):
    r = await client.get("/ai/pins")
    assert r.status_code in (401, 403)


async def test_pins_limit_out_of_range_is_422(client, admin_headers):
    assert (await client.get("/ai/pins", params={"limit": 0}, headers=admin_headers)).status_code == 422
    assert (await client.get("/ai/pins", params={"limit": 999}, headers=admin_headers)).status_code == 422


async def test_pins_isolated_across_orgs(client, admin_headers, org):
    """A pin written for a second, independent org must never surface here."""
    other_org = uuid.uuid4()
    other_admin = uuid.uuid4()
    pool = users_admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                       other_org, "Other Org", f"other-{other_org.hex[:8]}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        other_admin, other_org, f"o_{other_org.hex[:6]}", hash_password("x"), "Other Admin")
    try:
        await _pin(other_org, "weekly_report", "SECRET other-org report", "confidential")
        await _pin(org["org_id"], "weekly_report", "My org report")

        r = await client.get("/ai/pins", headers=admin_headers)
        assert r.status_code == 200
        titles = [p["title"] for p in r.json()]
        assert "My org report" in titles
        assert "SECRET other-org report" not in titles
    finally:
        from tests.conftest import purge_org
        await purge_org(other_org)


async def test_user_pins_visible_only_to_subject_and_elevated(client, admin_headers, org):
    """Two USER-role members: each must see their OWN weekly_report_user pin,
    never a colleague's — and not the org-level report either (review
    2026-09-27, BC-02: it is every task and owner in the organisation). The
    ADMIN sees everything. This is the privacy line for individual AI
    performance reports."""
    alice, alice_otp = await create_user(client, admin_headers, full_name="Alice")
    bob, bob_otp = await create_user(client, admin_headers, full_name="Bob")
    alice_tok = await login_and_set_password(client, alice["username"], alice_otp)
    bob_tok = await login_and_set_password(client, bob["username"], bob_otp)

    await _pin(org["org_id"], "weekly_report", "Org report — W1")
    await _pin(org["org_id"], "weekly_report_user", "Report — Alice", "alice private",
               subject_user_id=alice["id"])
    await _pin(org["org_id"], "weekly_report_user", "Report — Bob", "bob private",
               subject_user_id=bob["id"])

    r = await client.get("/ai/pins", headers={"Authorization": f"Bearer {alice_tok}"})
    assert r.status_code == 200, r.text
    titles = [p["title"] for p in r.json()]
    assert "Org report — W1" not in titles       # the org-wide narrative is elevated-only
    assert "Report — Alice" in titles
    assert "Report — Bob" not in titles          # a colleague's report is invisible

    r = await client.get("/ai/pins", headers={"Authorization": f"Bearer {bob_tok}"})
    titles = [p["title"] for p in r.json()]
    assert "Report — Bob" in titles and "Report — Alice" not in titles

    r = await client.get("/ai/pins", headers=admin_headers)  # elevated: sees all
    titles = [p["title"] for p in r.json()]
    assert {"Org report — W1", "Report — Alice", "Report — Bob"} <= set(titles)


# ── BC-02 (review 2026-09-27): the org-wide narratives are elevated, org-wide reading ──
# The scheduler writes the raw digest as `weekly_snapshot` and the AI report as
# `weekly_report` — neither is an invoke key, so the FUNCTION_ROLES filter never
# covered them and a base USER (or a department-scoped manager) read the whole
# organisation's task list, owners, overdue items and declined assignments.

async def _scoped_manager_headers(client, admin_headers, org):
    from app.db import tasks_admin_pool
    dept = await tasks_admin_pool().fetchval(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'pins_d','Pins Dept') RETURNING id",
        org["org_id"])
    mgr, otp = await create_user(client, admin_headers, role="QC_MGR", department_id=str(dept))
    tok = await login_and_set_password(client, mgr["username"], otp)
    return {"Authorization": f"Bearer {tok}"}


async def test_base_user_cannot_read_the_org_wide_digest_or_ai_report(client, admin_headers, org):
    user, otp = await create_user(client, admin_headers, full_name="Digest Reader")
    uh = {"Authorization": f"Bearer {await login_and_set_password(client, user['username'], otp)}"}
    await _pin(org["org_id"], "weekly_snapshot", "Weekly snapshot — W39", "every task, every owner")
    await _pin(org["org_id"], "weekly_report", "Weekly report — W39", "org narrative")
    await _pin(org["org_id"], "next_week_plan", "Next week plan — W40", "org plan")

    for key in ("weekly_snapshot", "weekly_report", "next_week_plan"):
        r = await client.get("/ai/pins", params={"function_key": key}, headers=uh)
        assert r.status_code == 200, r.text
        assert r.json() == [], f"USER must not read the org-wide {key} pin"
    titles = {p["title"] for p in (await client.get("/ai/pins", headers=uh)).json()}
    assert not titles & {"Weekly snapshot — W39", "Weekly report — W39", "Next week plan — W40"}
    # ADMIN (org-wide, elevated) still reads all three.
    titles = {p["title"] for p in (await client.get("/ai/pins", headers=admin_headers)).json()}
    assert {"Weekly snapshot — W39", "Weekly report — W39", "Next week plan — W40"} <= titles


async def test_department_scoped_manager_cannot_read_the_org_wide_pins(client, admin_headers, org):
    """A manager's AI context is their own department tree (DEPARTMENT-MODEL
    2026-09, "AI context"); the archived org-wide digest is every other
    department's work too, so it is for org-wide roles only. QP is manager
    rank but org-wide, and keeps it."""
    mgr_h = await _scoped_manager_headers(client, admin_headers, org)
    qp, otp = await create_user(client, admin_headers, role="QP", full_name="Qualified Person")
    qp_h = {"Authorization": f"Bearer {await login_and_set_password(client, qp['username'], otp)}"}
    await _pin(org["org_id"], "weekly_snapshot", "Org digest", "all departments")

    assert (await client.get("/ai/pins", params={"function_key": "weekly_snapshot"},
                             headers=mgr_h)).json() == []
    assert any(p["title"] == "Org digest" for p in
               (await client.get("/ai/pins", params={"function_key": "weekly_snapshot"},
                                 headers=qp_h)).json())


async def test_a_personal_pin_under_an_org_wide_key_stays_readable_by_its_subject(client, admin_headers, org):
    """The gate is on SUBJECT-LESS pins only — a per-person report archived
    under weekly_report with a subject is that person's own."""
    user, otp = await create_user(client, admin_headers, full_name="Own Report")
    uh = {"Authorization": f"Bearer {await login_and_set_password(client, user['username'], otp)}"}
    await _pin(org["org_id"], "weekly_report", "Mine", "personal", subject_user_id=user["id"])
    assert any(p["title"] == "Mine" for p in
               (await client.get("/ai/pins", params={"function_key": "weekly_report"}, headers=uh)).json())


async def test_pins_garbage_week_id_is_422_not_500(client, admin_headers):
    """BC-14: week_id was bound straight into a uuid comparison."""
    r = await client.get("/ai/pins", params={"week_id": "abc"}, headers=admin_headers)
    assert r.status_code == 422


async def test_pins_expose_prompt_version(client, admin_headers, org):
    """ai_pins.prompt_version (migration 0004) records which
    planner_prompts.PROMPT_VERSION produced a pin — or NULL for the raw
    digest, which is never LLM-authored. Must round-trip through the API."""
    await _pin(org["org_id"], "weekly_report", "AI report", prompt_version="wwf-prompts/v3")
    await _pin(org["org_id"], "weekly_snapshot", "Raw digest", prompt_version=None)

    r = await client.get("/ai/pins", headers=admin_headers)
    assert r.status_code == 200, r.text
    by_title = {p["title"]: p for p in r.json()}
    assert by_title["AI report"]["prompt_version"] == "wwf-prompts/v3"
    assert by_title["Raw digest"]["prompt_version"] is None
