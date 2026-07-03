"""GET /ai/pins — the read side of the weekly-snapshot archive. Org isolation
is the security property that matters (pins hold generated reports); the
endpoint is RLS-scoped, so a pin written for another org must be invisible."""
import uuid

from app.db import admin_pool
from app.security import hash_password


async def _pin(org_id, function_key, title, body="body"):
    await admin_pool().execute(
        "INSERT INTO ai_pins(org_id, function_key, title, body) VALUES ($1,$2,$3,$4)",
        org_id, function_key, title, body)


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
