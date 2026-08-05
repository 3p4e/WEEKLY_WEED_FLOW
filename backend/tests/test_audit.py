"""P2 — the audit trail's tamper-evidence claim, precisely.

/audit/verify (as of M6) RECOMPUTES each row's entry_hash from its stored
columns and compares it to the recorded hash, AND checks that each row's
prev_hash matches the entry_hash of the row before it, AND anchors the head
row. So it catches: a row deleted or reordered (linkage), an in-place edit
of old_values/new_values that left the hash columns intact (recompute), and
head truncation (anchor). The tests below pin all three, plus the clean-chain
baseline.
"""
from app.db import tasks_admin_pool, users_admin_pool
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


async def test_verify_restricted_to_admin_and_qa_auditor_roles(client, admin_headers):
    """QC_MGR is elevated enough for /audit and /audit/tables, but /verify is
    limited to ADMIN plus the QA auditor roles (QA_MGR, QP). A QC_MGR is
    elevated yet not among them, so it is still refused."""
    user, otp = await create_user(client, admin_headers, role="QC_MGR")
    from tests.conftest import login_and_set_password
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/audit", headers=headers)).status_code == 200
    assert (await client.get("/audit/verify", headers=headers)).status_code == 403


async def test_verify_open_to_qa_manager_and_qp_auditors(client, admin_headers):
    """Read-only chain verification is an audit function, so QA_MGR and QP (the
    Qualified Person) may run /audit/verify and get a verdict — not just ADMIN.
    A plain USER is still refused."""
    from tests.conftest import login_and_set_password
    for role in ("QA_MGR", "QP"):
        user, otp = await create_user(client, admin_headers, role=role)
        token = await login_and_set_password(client, user["username"], otp)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/audit/verify", headers=headers)
        assert r.status_code == 200, f"{role}: {r.text}"
        assert "ok" in r.json(), role
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/audit/verify", headers=headers)).status_code == 403


async def test_executives_are_elevated_but_cannot_verify(client, admin_headers):
    """OWNER, CEO, COO all sit above USER in the reshaped role model — each is
    recognized by app.is_elevated(), so each may read the audit trail and its
    table list. But /verify is not an executive function: it is limited to ADMIN
    and the QA auditor roles (QA_MGR, QP), so the executives are refused it."""
    from tests.conftest import login_and_set_password
    for role in ("OWNER", "CEO", "COO"):
        user, otp = await create_user(client, admin_headers, role=role)
        token = await login_and_set_password(client, user["username"], otp)
        headers = {"Authorization": f"Bearer {token}"}
        assert (await client.get("/audit", headers=headers)).status_code == 200, role
        assert (await client.get("/audit/tables", headers=headers)).status_code == 200, role
        assert (await client.get("/audit/verify", headers=headers)).status_code == 403, role


async def test_team_leader_role_no_longer_exists(client, admin_headers):
    """TEAM_LEADER was removed in the role-model reshape (Purely Plant has no
    such rank). create_user validates against CREATABLE_ROLES up front, so a
    non-assignable role is a clean 422 before it ever reaches the DB CHECK
    (profiles_role_check, which also no longer lists it — defence in depth)."""
    r = await client.post("/auth/users", json={
        "username": "no_team_leader", "full_name": "X", "role": "TEAM_LEADER",
    }, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_project_lead_role_no_longer_exists(client, admin_headers):
    """PROJECT_LEAD was removed entirely (Purely Plant has no such role).
    create_user rejects any role outside CREATABLE_ROLES up front with a clean
    422, before it can reach the DB — profiles_role_check no longer lists it
    either, so the database CHECK remains a second line of defence."""
    r = await client.post("/auth/users", json={
        "username": "no_project_lead", "full_name": "X", "role": "PROJECT_LEAD",
    }, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_qa_auditor_role_no_longer_exists(client, admin_headers):
    """QA_AUDITOR was removed entirely — a non-assignable role is rejected up
    front with a 422 (not in CREATABLE_ROLES), and profiles_role_check no
    longer lists it either (defence in depth)."""
    r = await client.post("/auth/users", json={
        "username": "should_not_be_creatable", "full_name": "X", "role": "QA_AUDITOR",
    }, headers=admin_headers)
    assert r.status_code == 422, r.text


async def _dept(org, code, name):
    from app.db import tasks_admin_pool
    row = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,$2,$3) RETURNING id",
        org["org_id"], code, name)
    return str(row["id"])


async def test_dept_manager_audit_is_scoped_to_own_department(client, admin_headers, org):
    """M1: a department-scoped manager reads the audit trail but must see only
    their OWN department's task rows — never another department's task content,
    and never the users-DB (profiles) identity chain."""
    from tests.conftest import login_and_set_password
    d_qc = await _dept(org, "qc", "QC")
    d_pr = await _dept(org, "pr", "Production")

    assert (await client.post("/tasks", json={"title": "QC secret", "department_id": d_qc},
                              headers=admin_headers)).status_code == 201
    assert (await client.post("/tasks", json={"title": "PR secret", "department_id": d_pr},
                              headers=admin_headers)).status_code == 201
    await create_user(client, admin_headers)  # guarantees a users-DB (profiles) row exists

    mgr, otp = await create_user(client, admin_headers, role="QC_MGR", department_id=d_qc)
    token = await login_and_set_password(client, mgr["username"], otp)
    h = {"Authorization": f"Bearer {token}"}

    rows = (await client.get("/audit?limit=500", headers=h)).json()
    # sees its own department's task rows
    assert any(e["source"] == "tasks" and (e.get("new_values") or {}).get("department_id") == d_qc
               for e in rows), "QC manager should see its own department's audit rows"
    # never another department's task content (in either payload side)
    assert all((e.get("new_values") or {}).get("department_id") != d_pr for e in rows)
    assert all((e.get("old_values") or {}).get("department_id") != d_pr for e in rows)
    # never the identity (profiles/users) chain
    assert all(e["source"] != "users" for e in rows)


async def test_org_wide_role_still_sees_all_departments_in_audit(client, admin_headers, org):
    """M1 must not over-restrict: an org-wide role (CEO) still sees every
    department's task rows AND the users chain."""
    from tests.conftest import login_and_set_password
    d_qc = await _dept(org, "qc", "QC")
    d_pr = await _dept(org, "pr", "Production")
    await client.post("/tasks", json={"title": "QC t", "department_id": d_qc}, headers=admin_headers)
    await client.post("/tasks", json={"title": "PR t", "department_id": d_pr}, headers=admin_headers)
    ceo, otp = await create_user(client, admin_headers, role="CEO")
    token = await login_and_set_password(client, ceo["username"], otp)
    h = {"Authorization": f"Bearer {token}"}
    rows = (await client.get("/audit?limit=500", headers=h)).json()
    depts = {(e.get("new_values") or {}).get("department_id") for e in rows if e["source"] == "tasks"}
    assert d_qc in depts and d_pr in depts
    assert any(e["source"] == "users" for e in rows), "org-wide role should still see the identity chain"


async def test_verify_reports_ok_when_chain_intact(client, admin_headers):
    await client.post("/tasks", json={"title": "Keeps the chain honest", "status": "pending"},
                       headers=admin_headers)
    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["users"]["ok"] is True and body["tasks"]["ok"] is True
    assert body["tasks"]["breaks"] == 0
    assert body["tasks"]["first_break_id"] is None


async def test_verify_detects_in_place_content_tampering(client, admin_headers):
    """M6: /verify now recomputes entry_hash from the row's own content, so a
    direct edit of new_values that leaves the hash columns intact is DETECTED —
    the precise BYPASSRLS/DBA tamper a hash chain exists to catch. The original
    content is restored at the end so the chain is left clean for later tests (the
    linkage never changed, so nothing downstream is affected either way)."""
    r = await client.post("/tasks", json={"title": "Tamper target", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    row = await tasks_admin_pool().fetchrow(
        "SELECT id, new_values FROM audit_log WHERE table_name='tasks' AND record_id=$1 AND action='INSERT'",
        task_id)
    assert row is not None
    original = row["new_values"]
    tampered = {"title": "SOMEONE EDITED THIS ROW DIRECTLY", "status": "pending"}
    await tasks_admin_pool().execute("UPDATE audit_log SET new_values=$1 WHERE id=$2", tampered, row["id"])
    try:
        r = await client.get("/audit/verify", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        # the recompute no longer matches the recorded hash → the chain is flagged
        assert body["ok"] is False
        assert body["tasks"]["ok"] is False
        assert body["tasks"]["hash_breaks"] >= 1
        assert body["tasks"]["first_break_id"] is not None
    finally:
        # restore the row's content so the recompute matches again
        await tasks_admin_pool().execute(
            "UPDATE audit_log SET new_values=$1 WHERE id=$2", original, row["id"])
    # the chain verifies clean again once the content is restored
    assert (await client.get("/audit/verify", headers=admin_headers)).json()["ok"] is True


async def test_verify_tolerates_a_row_written_under_a_NON_UTC_timezone(client, admin_headers):
    """H2 REGRESSION — the exact production defect, reproduced.

    The trigger hashes now()::text and /verify recomputes created_at::text. Both
    render a timestamptz under the SESSION TimeZone, so a row written by a
    connection at UTC+2 could not be recomputed under UTC: same instant, different
    text, different digest. Production carried 377 such rows that verified 377/377
    under Europe/Skopje and 0/377 under UTC, and /verify called them tamper.

    This writes a row through a connection pinned to Europe/Skopje, exactly as that
    session did, and asserts /verify does NOT report a break — and counts it as
    `hash_legacy_tz` so the history is explained rather than hidden.

    NOTE the deliberate `SET TimeZone` on the connection: tasks-0050 pins the
    FUNCTION's TimeZone to UTC, which is what stops this recurring. To reproduce
    the legacy row this test must defeat that pin, so it writes the audit row by
    hand with the pre-0050 payload rather than through the trigger."""
    r = await client.post("/tasks", json={"title": "TZ probe", "status": "pending"},
                          headers=admin_headers)
    task_id = r.json()["id"]

    # Forge a LEGACY-style row: hashed from created_at rendered at UTC+2, which is
    # what a pre-0050 writer at that zone produced. Appended at the chain tail so
    # linkage stays intact and only the hash rendering is at issue.
    async with tasks_admin_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('TimeZone','Europe/Skopje',true)")
            legacy_id = await conn.fetchval(
                """
                WITH tail AS (SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1),
                ins AS (
                  SELECT (SELECT entry_hash FROM tail) AS prev,
                         now() AS ts,
                         'UPDATE'::text AS act,
                         'tasks'::text AS tbl,
                         $1::text AS rec,
                         '{"title": "written at UTC+2"}'::jsonb AS nv
                )
                INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,
                                      old_values,new_values,prev_hash,entry_hash,created_at)
                SELECT NULL, NULL, act, tbl, rec, NULL, nv, prev,
                       encode(digest(convert_to(
                         COALESCE(prev,'') || 'system' || act || tbl || rec
                         || ts::text || nv::text, 'UTF8'), 'sha256'), 'hex'),
                       ts
                FROM ins RETURNING id
                """, task_id)
    try:
        body = (await client.get("/audit/verify", headers=admin_headers)).json()
        assert body["tasks"]["ok"] is True, (
            "a row written under a non-UTC session must not be reported as tampered: "
            f"{body['tasks']}")
        assert body["tasks"]["breaks"] == 0
        assert body["tasks"]["hash_breaks"] == 0
        assert body["tasks"]["hash_legacy_tz"] >= 1, \
            "the non-UTC row must still be REPORTED, as explained history"
        assert "Europe/Skopje" in body["tasks"]["zones_tried"]
    finally:
        await tasks_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", legacy_id)


async def test_verify_still_catches_tampering_in_a_row_that_needs_the_legacy_zone(
        client, admin_headers):
    """The zone tolerance must not become a hole. A legacy-rendered row whose
    CONTENT is then edited matches under neither zone, so it is still a break."""
    r = await client.post("/tasks", json={"title": "TZ tamper probe", "status": "pending"},
                          headers=admin_headers)
    task_id = r.json()["id"]
    async with tasks_admin_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('TimeZone','Europe/Skopje',true)")
            legacy_id = await conn.fetchval(
                """
                WITH tail AS (SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1),
                ins AS (SELECT (SELECT entry_hash FROM tail) AS prev, now() AS ts,
                               $1::text AS rec, '{"title": "honest"}'::jsonb AS nv)
                INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,
                                      old_values,new_values,prev_hash,entry_hash,created_at)
                SELECT NULL, NULL, 'UPDATE', 'tasks', rec, NULL, nv, prev,
                       encode(digest(convert_to(COALESCE(prev,'')||'system'||'UPDATE'||'tasks'
                         ||rec||ts::text||nv::text,'UTF8'),'sha256'),'hex'), ts
                FROM ins RETURNING id
                """, task_id)
    try:
        assert (await client.get("/audit/verify", headers=admin_headers)).json()["tasks"]["ok"] is True
        # now edit its content in place, the DBA tamper the chain exists to catch
        await tasks_admin_pool().execute(
            "UPDATE audit_log SET new_values=$1 WHERE id=$2",
            {"title": "SOMEONE EDITED THIS"}, legacy_id)
        body = (await client.get("/audit/verify", headers=admin_headers)).json()
        assert body["tasks"]["ok"] is False, "zone tolerance must not excuse edited content"
        assert body["tasks"]["hash_breaks"] >= 1
    finally:
        await tasks_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", legacy_id)
    assert (await client.get("/audit/verify", headers=admin_headers)).json()["tasks"]["ok"] is True


async def test_verify_classifies_a_chain_FORK_separately_from_a_deletion(client, admin_headers):
    """A fork (two rows claiming the same predecessor) is the pre-advisory-lock
    concurrency bug tasks-0012 fixed; an orphan (prev_hash pointing at nothing) is
    a deletion. Production has 38 of the former, dated three days before the lock
    landed, and 0 of the latter. Lumping them together is what made /verify report
    an intact chain as broken, so the distinction is pinned here."""
    await client.post("/tasks", json={"title": "Fork probe", "status": "pending"},
                      headers=admin_headers)
    # Append a row that links to the SECOND-to-last entry_hash: a real earlier row,
    # which is precisely what two concurrent tail-reads produce.
    fork_id = await tasks_admin_pool().fetchval(
        """
        WITH prior AS (SELECT entry_hash FROM audit_log ORDER BY id DESC OFFSET 1 LIMIT 1),
        ins AS (SELECT (SELECT entry_hash FROM prior) AS prev, now() AS ts)
        INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,
                              old_values,new_values,prev_hash,entry_hash,created_at)
        SELECT NULL, NULL, 'UPDATE', 'tasks', 'fork', NULL, NULL, prev,
               encode(digest(convert_to(COALESCE(prev,'')||'system'||'UPDATE'||'tasks'
                 ||'fork'||ts::text,'UTF8'),'sha256'),'hex'), ts
        FROM ins RETURNING id
        """)
    try:
        body = (await client.get("/audit/verify", headers=admin_headers)).json()["tasks"]
        assert body["link_forks"] >= 1, "a fork must be reported as a fork"
        assert body["link_orphans"] == 0, "a fork is not an orphan"
        assert body["ok"] is True, (
            "an explained pre-hardening fork must not fail the chain — that is the "
            f"false alarm this fix removes: {body}")
        assert body["fork_id_range"][1] == fork_id
    finally:
        await tasks_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", fork_id)


async def test_verify_flags_an_ORPHAN_link_as_a_real_break(client, admin_headers):
    """The other half: prev_hash pointing at no row at all is what a deleted or
    rewritten predecessor looks like, and it must fail."""
    await client.post("/tasks", json={"title": "Orphan probe", "status": "pending"},
                      headers=admin_headers)
    orphan_id = await tasks_admin_pool().fetchval(
        """
        INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,
                              old_values,new_values,prev_hash,entry_hash,created_at)
        SELECT NULL, NULL, 'UPDATE', 'tasks', 'orphan', NULL, NULL,
               repeat('f', 64),
               encode(digest(convert_to(repeat('f',64)||'system'||'UPDATE'||'tasks'
                 ||'orphan'||now()::text,'UTF8'),'sha256'),'hex'), now()
        RETURNING id
        """)
    try:
        body = (await client.get("/audit/verify", headers=admin_headers)).json()["tasks"]
        assert body["link_orphans"] >= 1, "a prev_hash pointing nowhere must be an orphan"
        assert body["ok"] is False, "an orphan link is a genuine integrity failure"
        assert body["first_break_id"] is not None
    finally:
        await tasks_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", orphan_id)


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
    row = await tasks_admin_pool().fetchrow(
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

    await tasks_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", row["id"])

    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["tasks"]["ok"] is False
    assert body["tasks"]["breaks"] >= 1
    assert body["tasks"]["first_break_id"] is not None
    # The users chain was untouched — per-chain verification must say so.
    assert body["users"]["ok"] is True


async def test_verify_detects_a_deleted_row_in_the_users_chain(client, admin_headers):
    """Same guarantee, other database: profile events chain in the users DB,
    and deleting one of those rows must flip users.ok while leaving the
    (already-broken-by-the-previous-test) tasks chain result independent.
    Runs last — it permanently breaks the users chain for this session."""
    user, _ = await create_user(client, admin_headers, full_name="Users Chain Victim")
    row = await users_admin_pool().fetchrow(
        "SELECT id FROM audit_log WHERE table_name='profiles' AND record_id=$1 AND action='INSERT'"
        " ORDER BY id DESC LIMIT 1", user["id"])
    assert row is not None
    # A successor row must exist, or deleting the tail wouldn't break linkage.
    await create_user(client, admin_headers, full_name="Users Chain Successor")

    await users_admin_pool().execute("DELETE FROM audit_log WHERE id=$1", row["id"])

    r = await client.get("/audit/verify", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["users"]["ok"] is False
    assert body["users"]["breaks"] >= 1
