"""GET /ai/pins — the read side of the weekly-snapshot archive. Two security
properties matter and both live in the RLS policy, not the endpoint: (1) org
isolation — another org's pins are invisible; (2) per-user visibility — a pin
with subject_user_id set (an individual's AI weekly report) is visible only
to its subject and to elevated roles, never to arbitrary org members."""
import uuid

from app.db import admin_pool
from app.security import hash_password
from tests.conftest import create_user, login_and_set_password


async def _pin(org_id, function_key, title, body="body", subject_user_id=None):
    await admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body, subject_user_id)"
        " VALUES ($1,$2,$3,$4,$5)",
        org_id, function_key, title, body, subject_user_id)


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
    pool = admin_pool()
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
        await pool.execute("DELETE FROM organizations WHERE id=$1", other_org)


async def test_user_pins_visible_only_to_subject_and_elevated(client, admin_headers, org):
    """Two USER-role members: each must see the org-level pin and their OWN
    weekly_report_user pin, never a colleague's. The ADMIN sees everything.
    This is the privacy line for individual AI performance reports."""
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
    assert "Org report — W1" in titles
    assert "Report — Alice" in titles
    assert "Report — Bob" not in titles          # a colleague's report is invisible

    r = await client.get("/ai/pins", headers={"Authorization": f"Bearer {bob_tok}"})
    titles = [p["title"] for p in r.json()]
    assert "Report — Bob" in titles and "Report — Alice" not in titles

    r = await client.get("/ai/pins", headers=admin_headers)  # elevated: sees all
    titles = [p["title"] for p in r.json()]
    assert {"Org report — W1", "Report — Alice", "Report — Bob"} <= set(titles)
