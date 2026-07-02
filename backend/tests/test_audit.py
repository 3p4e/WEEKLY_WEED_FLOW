"""P2 — the audit trail's tamper-evidence claim, precisely.

/audit/verify walks the hash chain checking that each row's prev_hash
matches the entry_hash of the row before it (schema.sql's app.fn_audit_row
trigger writes both at insert time). That's a real, useful guarantee: it
catches a row being deleted or reordered. It is a *narrower* guarantee than
"tamper-evident" might suggest, though — entry_hash is never recomputed
from a row's own current content, so editing old_values/new_values in place
without touching the hash columns is invisible to /verify. Both properties
are pinned below so the distinction stays visible in the test suite, not
just in a docstring.
"""
from app.db import admin_pool
from tests.conftest import create_user


async def test_list_audit_and_redaction(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Audited task", "status": "pending"},
                           headers=admin_headers)
    assert r.status_code == 201

    r = await client.get("/audit?table_name=tasks&action=INSERT", headers=admin_headers)
    assert r.status_code == 200
    assert any(e["table_name"] == "tasks" and e["action"] == "INSERT" for e in r.json())

    # A profile write must never leak password_hash through the trail.
    await create_user(client, admin_headers)
    r = await client.get("/audit?table_name=profiles&action=INSERT", headers=admin_headers)
    entries = r.json()
    assert entries, "expected at least one profiles INSERT entry"
    for e in entries:
        if e["new_values"] and "password_hash" in e["new_values"]:
            assert e["new_values"]["password_hash"] == "***"


async def test_audit_tables_endpoint(client, admin_headers):
    await client.post("/tasks", json={"title": "For tables endpoint", "status": "pending"},
                       headers=admin_headers)
    r = await client.get("/audit/tables", headers=admin_headers)
    assert r.status_code == 200
    names = [t["table_name"] for t in r.json()]
    assert "tasks" in names


async def test_non_elevated_cannot_read_audit(client, admin_headers):
    user, otp = await create_user(client, admin_headers, role="USER")
    from tests.conftest import login_and_set_password
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/audit", headers=headers)).status_code == 403
    assert (await client.get("/audit/tables", headers=headers)).status_code == 403
    assert (await client.get("/audit/verify", headers=headers)).status_code == 403


async def test_verify_only_allows_admin_not_just_any_elevated_role(client, admin_headers):
    """DEPT_HEAD is elevated enough for /audit and /audit/tables, but /verify
    is explicitly ADMIN-only (require_role("ADMIN"), not the _ELEVATED tuple)."""
    user, otp = await create_user(client, admin_headers, role="DEPT_HEAD")
    from tests.conftest import login_and_set_password
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/audit", headers=headers)).status_code == 200
    assert (await client.get("/audit/verify", headers=headers)).status_code == 403


async def test_verify_reports_ok_when_chain_intact(client, admin_headers):
    await client.post("/tasks", json={"title": "Keeps the chain honest", "status": "pending"},
                       headers=admin_headers)
    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["breaks"] == 0
    assert body["first_break_id"] is None


async def test_verify_does_not_detect_in_place_content_tampering(client, admin_headers):
    """Documents the real gap: /verify never recomputes entry_hash from a
    row's own content, so editing old_values/new_values without touching
    entry_hash/prev_hash passes verification. Safe to run anywhere — it
    never touches the hash columns, so it can't break chain linkage for
    any other test."""
    r = await client.post("/tasks", json={"title": "Tamper target", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    row = await admin_pool().fetchrow(
        "SELECT id FROM audit_log WHERE table_name='tasks' AND record_id=$1 AND action='INSERT'", task_id)
    assert row is not None
    tampered = {"title": "SOMEONE EDITED THIS ROW DIRECTLY", "status": "pending"}
    await admin_pool().execute("UPDATE audit_log SET new_values=$1 WHERE id=$2", tampered, row["id"])

    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    # This is the gap, asserted explicitly rather than implied: content was
    # altered but the chain still reports intact.
    assert r.json()["ok"] is True

    r = await client.get(f"/audit?table_name=tasks&record_id={task_id}", headers=admin_headers)
    tampered_entry = next(e for e in r.json() if e["id"] == row["id"])
    assert tampered_entry["new_values"]["title"] == "SOMEONE EDITED THIS ROW DIRECTLY"


async def test_verify_detects_a_deleted_row(client, admin_headers):
    """The property /verify DOES guarantee: deleting or reordering a row
    breaks the linkage of everything chained after it. Runs last in this
    file — deliberately, since it permanently breaks the chain for the rest
    of the test session (no other test in the suite calls /audit/verify
    after this one; alphabetical module collection keeps this file's
    internal order intact without depending on cross-file ordering)."""
    r = await client.post("/tasks", json={"title": "Will be erased from the trail", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    row = await admin_pool().fetchrow(
        "SELECT id FROM audit_log WHERE table_name='tasks' AND record_id=$1 AND action='INSERT'"
        " ORDER BY id DESC LIMIT 1", task_id)
    assert row is not None
    # A successor row must exist, or deleting the chain's current tail
    # wouldn't break any linkage at all (nothing points at it yet).
    await client.post("/tasks", json={"title": "Successor entry, proves a break occurred", "status": "pending"},
                       headers=admin_headers)

    # Confirm intact immediately before the delete, so a failure here can
    # only be attributed to the delete itself.
    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.json()["ok"] is True

    await admin_pool().execute("DELETE FROM audit_log WHERE id=$1", row["id"])

    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["breaks"] >= 1
    assert body["first_break_id"] is not None
