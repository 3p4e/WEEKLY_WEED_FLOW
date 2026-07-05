"""P1 — account provisioning, forced first-login password change, RBAC gates."""
from app.db import users_admin_pool
from tests.conftest import create_user, login_and_set_password


async def test_provision_login_forced_change_flow(client, admin_headers):
    user, otp = await create_user(client, admin_headers, role="USER")
    assert user["must_change_password"] is True
    await login_and_set_password(client, user["username"], otp)


async def test_change_password_response_carries_a_working_fresh_token(client, admin_headers):
    """The old token is invalidated the instant change-password succeeds
    (its pwv claim stops matching profiles.password_set_at) — the response
    must carry a new one that actually works, or the caller is stuck with
    no valid credential right after a successful change."""
    user, otp = await create_user(client, admin_headers, role="USER")
    r = await client.post("/auth/login", json={"email": user["username"], "password": otp})
    old_token = r.json()["access_token"]

    r = await client.post("/auth/change-password", json={"new_password": "NewPassword123456"},
                           headers={"Authorization": f"Bearer {old_token}"})
    assert r.status_code == 200, r.text
    new_token = r.json().get("access_token")
    assert new_token and new_token != old_token

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert r.status_code == 401

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert r.status_code == 200


async def test_password_below_minimum_length_rejected(client, admin_headers):
    user, otp = await create_user(client, admin_headers)
    r = await client.post("/auth/login", json={"email": user["username"], "password": otp})
    tmp_token = r.json()["access_token"]
    r = await client.post("/auth/change-password", json={"new_password": "short"},
                           headers={"Authorization": f"Bearer {tmp_token}"})
    assert r.status_code == 422


async def test_old_otp_rejected_after_password_change(client, admin_headers):
    user, otp = await create_user(client, admin_headers)
    await login_and_set_password(client, user["username"], otp)
    r = await client.post("/auth/login", json={"email": user["username"], "password": otp})
    assert r.status_code == 401


async def test_voluntary_password_change_requires_current_password(client, admin_headers):
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.post("/auth/change-password",
                           json={"current_password": "totally-wrong", "new_password": "AnotherPass123456"},
                           headers=headers)
    assert r.status_code == 401


async def test_password_change_invalidates_previously_issued_tokens(client, admin_headers):
    """A token minted before a password change must stop working after it —
    otherwise a stolen token stays valid for its full lifetime even once the
    real user has rotated their password."""
    user, otp = await create_user(client, admin_headers)
    old_token = await login_and_set_password(client, user["username"], otp)
    old_headers = {"Authorization": f"Bearer {old_token}"}

    r = await client.get("/auth/me", headers=old_headers)
    assert r.status_code == 200

    r = await client.post("/auth/change-password",
                           json={"current_password": "NewPassword123456", "new_password": "EvenNewerPass123456"},
                           headers=old_headers)
    assert r.status_code == 200

    r = await client.get("/auth/me", headers=old_headers)
    assert r.status_code == 401

    # A fresh login (new token, new password) must still work normally.
    r = await client.post("/auth/login", json={"email": user["username"], "password": "EvenNewerPass123456"})
    assert r.status_code == 200
    new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.get("/auth/me", headers=new_headers)
    assert r.status_code == 200


async def test_non_admin_cannot_list_users(client, admin_headers):
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    r = await client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_non_admin_can_read_directory(client, admin_headers):
    """/auth/directory (unlike /auth/users) is open to any authenticated
    user — regression test for the fix that gave non-elevated roles a real
    people directory instead of only seeing themselves."""
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    r = await client.get("/auth/directory", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 2  # the admin + this new user, at least
    assert "is_active" not in r.json()[0]  # management-only field must not leak here
    assert "must_change_password" not in r.json()[0]


async def test_directory_excludes_deactivated_accounts(client, admin_headers, org):
    """A deactivated (is_active=false) account must vanish from the
    /auth/directory roster — it feeds avatars and assignee pickers, so an
    inactive account would otherwise remain assignable forever. /users (the
    management view) is where inactive accounts stay visible."""
    user, _ = await create_user(client, admin_headers, full_name="Soon Inactive")
    await users_admin_pool().execute(
        "UPDATE profiles SET is_active=false WHERE id=$1", user["id"])

    r = await client.get("/auth/directory", headers=admin_headers)
    assert r.status_code == 200
    assert user["username"] not in [u["username"] for u in r.json()]

    r = await client.get("/auth/users", headers=admin_headers)
    assert r.status_code == 200
    inactive = next(u for u in r.json() if u["username"] == user["username"])
    assert inactive["is_active"] is False


async def test_admin_cannot_delete_own_account(client, admin_headers, org):
    r = await client.delete(f"/auth/users/{org['admin_id']}", headers=admin_headers)
    assert r.status_code == 400


async def test_deleted_user_cannot_log_in(client, admin_headers):
    user, otp = await create_user(client, admin_headers)
    await login_and_set_password(client, user["username"], otp)
    r = await client.delete(f"/auth/users/{user['id']}", headers=admin_headers)
    assert r.status_code == 200
    r = await client.post("/auth/login", json={"email": user["username"], "password": "NewPassword123456"})
    assert r.status_code == 401


async def test_role_gated_endpoints_blocked_before_forced_password_change(client, admin_headers):
    """A leaked/intercepted OTP for a freshly-provisioned QC_MGR must not
    grant role-gated actions (user management, audit) before the real user
    completes their mandatory first-login password change — require_role()
    must enforce the same gate as require_password_set(), not bypass it."""
    mgr, otp = await create_user(client, admin_headers, role="QC_MGR")
    r = await client.post("/auth/login", json={"email": mgr["username"], "password": otp})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is True
    otp_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.get("/auth/users", headers=otp_headers)
    assert r.status_code == 403
    assert "password" in r.json()["detail"].lower()

    r = await client.post("/auth/users", json={"username": "should_fail", "full_name": "X", "role": "USER"},
                           headers=otp_headers)
    assert r.status_code == 403

    r = await client.get("/audit", headers=otp_headers)
    assert r.status_code == 403

    # Sanity: the same account can use the role-gated endpoints normally
    # once the forced password change is actually completed.
    token = await login_and_set_password(client, mgr["username"], otp)
    r = await client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_manager_confined_to_own_department(client, admin_headers, org):
    """_can_manage()'s manager branch is only ever exercised via the fixture's
    ADMIN in every other test — nothing pins that a department manager is
    actually confined to their own department, barred from creating a peer
    manager, or barred from creating an ADMIN account."""
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'a','Dept A'), ($1,'b','Dept B')"
        " RETURNING id, code",
        org["org_id"],
    )
    dept_ids = {r["code"]: str(r["id"]) for r in rows}

    r = await client.post("/auth/users", json={
        "username": "qc_mgr_a", "full_name": "QC Manager A", "role": "QC_MGR",
        "department_id": dept_ids["a"],
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    mgr, otp = r.json()["user"], r.json()["otp"]
    mgr_token = await login_and_set_password(client, mgr["username"], otp)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # Can create a USER within their own department.
    r = await client.post("/auth/users", json={
        "username": "same_dept_user", "full_name": "Same Dept", "role": "USER",
        "department_id": dept_ids["a"],
    }, headers=mgr_headers)
    assert r.status_code == 201, r.text
    same_dept_user = r.json()["user"]

    # Cannot create a USER in a different department.
    r = await client.post("/auth/users", json={
        "username": "other_dept_user", "full_name": "Other Dept", "role": "USER",
        "department_id": dept_ids["b"],
    }, headers=mgr_headers)
    assert r.status_code == 403

    # Cannot create a peer manager, even in their own department — managers
    # provision only USER staff; managers/executives are admin-only.
    r = await client.post("/auth/users", json={
        "username": "peer_mgr", "full_name": "Peer Manager", "role": "PR_MGR",
        "department_id": dept_ids["a"],
    }, headers=mgr_headers)
    assert r.status_code == 403

    # Cannot create an ADMIN — rejected up front as a non-assignable role (422),
    # before _can_manage is ever consulted.
    r = await client.post("/auth/users", json={
        "username": "sneaky_admin", "full_name": "Sneaky", "role": "ADMIN",
        "department_id": dept_ids["a"],
    }, headers=mgr_headers)
    assert r.status_code == 422

    # Delete mirrors create: can delete within their department...
    r = await client.delete(f"/auth/users/{same_dept_user['id']}", headers=mgr_headers)
    assert r.status_code == 200, r.text

    # ...but not a user in a different department.
    r = await client.post("/auth/users", json={
        "username": "victim_dept_b", "full_name": "Victim", "role": "USER", "department_id": dept_ids["b"],
    }, headers=admin_headers)
    victim = r.json()["user"]
    r = await client.delete(f"/auth/users/{victim['id']}", headers=mgr_headers)
    assert r.status_code == 403


async def test_admin_creates_managers_and_executives(client, admin_headers):
    """The create matrix's top row: an admin may provision any non-admin role —
    department managers, the QP, and executives (CEO/COO) alike — but ADMIN
    itself is never assignable, even by an admin (DB-seeded only → 422)."""
    for role in ("QC_MGR", "QP", "CEO", "COO"):
        r = await client.post("/auth/users", json={
            "username": f"role_{role.lower()}", "full_name": role, "role": role,
        }, headers=admin_headers)
        assert r.status_code == 201, r.text
        assert r.json()["user"]["role"] == role

    r = await client.post("/auth/users", json={
        "username": "another_admin", "full_name": "Nope", "role": "ADMIN",
    }, headers=admin_headers)
    assert r.status_code == 422


async def test_create_user_rejects_unknown_department(client, admin_headers):
    """department_id is a bare uuid (departments live in the tasks DB, no FK) —
    create_user now validates it against a real department for the org."""
    r = await client.post("/auth/users", json={
        "username": "baddept", "full_name": "X", "role": "USER",
        "department_id": "00000000-0000-0000-0000-000000000000",
    }, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_admin_reset_password_flow(client, admin_headers):
    """The reported gap, now built: an admin resets another account's password
    to a fresh one-time password. The old password stops working immediately
    and the OTP forces a change on next login (same as account creation)."""
    user, otp = await create_user(client, admin_headers, role="USER")
    await login_and_set_password(client, user["username"], otp)  # sets NewPassword123456
    r = await client.post("/auth/login", json={"email": user["username"], "password": "NewPassword123456"})
    assert r.status_code == 200

    r = await client.post(f"/auth/users/{user['id']}/reset-password", headers=admin_headers)
    assert r.status_code == 200, r.text
    new_otp = r.json()["otp"]
    assert new_otp and new_otp != otp
    assert r.json()["user"]["must_change_password"] is True

    # The account's previous password no longer works...
    r = await client.post("/auth/login", json={"email": user["username"], "password": "NewPassword123456"})
    assert r.status_code == 401
    # ...and the fresh OTP works and forces a change.
    r = await client.post("/auth/login", json={"email": user["username"], "password": new_otp})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is True


async def test_reset_password_authorization(client, admin_headers, org):
    """Same gate as create/delete: a manager may reset only a USER in their own
    department — never another department's user, a peer manager, or an ADMIN.
    An admin can't reset its own account (that's change-password's job)."""
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'a','A'),($1,'b','B') RETURNING id, code",
        org["org_id"])
    dept = {r["code"]: str(r["id"]) for r in rows}

    r = await client.post("/auth/users", json={"username": "mgr_a", "full_name": "Mgr A",
        "role": "QC_MGR", "department_id": dept["a"]}, headers=admin_headers)
    mgr, motp = r.json()["user"], r.json()["otp"]
    mgr_h = {"Authorization": f"Bearer {await login_and_set_password(client, mgr['username'], motp)}"}

    async def mk(username, role, dept_id):
        r = await client.post("/auth/users", json={"username": username, "full_name": username,
            "role": role, "department_id": dept_id}, headers=admin_headers)
        assert r.status_code == 201, r.text
        return r.json()["user"]["id"]
    user_a = await mk("ru_a", "USER", dept["a"])
    user_b = await mk("ru_b", "USER", dept["b"])
    peer = await mk("ru_peer", "PR_MGR", dept["a"])

    assert (await client.post(f"/auth/users/{user_a}/reset-password", headers=mgr_h)).status_code == 200
    assert (await client.post(f"/auth/users/{user_b}/reset-password", headers=mgr_h)).status_code == 403
    assert (await client.post(f"/auth/users/{peer}/reset-password", headers=mgr_h)).status_code == 403
    assert (await client.post(f"/auth/users/{org['admin_id']}/reset-password", headers=mgr_h)).status_code == 403
    # Admin resetting its own account → 400 (use change-password instead).
    assert (await client.post(f"/auth/users/{org['admin_id']}/reset-password", headers=admin_headers)).status_code == 400


async def test_update_user_edit(client, admin_headers, org):
    """Full edit-person: admin renames + changes role/department/title. ADMIN is
    never assignable via edit (422); an unknown department is rejected (422)."""
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'a','A'),($1,'b','B') RETURNING id, code",
        org["org_id"])
    dept = {r["code"]: str(r["id"]) for r in rows}
    r = await client.post("/auth/users", json={"username": "editme", "full_name": "Before",
        "role": "USER", "department_id": dept["a"]}, headers=admin_headers)
    uid = r.json()["user"]["id"]

    r = await client.patch(f"/auth/users/{uid}", json={"full_name": "After", "role": "QC_MGR",
        "department_id": dept["b"], "function_role": "QC Lead"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "After" and body["role"] == "QC_MGR"
    assert body["department_id"] == dept["b"] and body["function_role"] == "QC Lead"

    assert (await client.patch(f"/auth/users/{uid}", json={"role": "ADMIN"}, headers=admin_headers)).status_code == 422
    assert (await client.patch(f"/auth/users/{uid}",
        json={"department_id": "00000000-0000-0000-0000-000000000000"}, headers=admin_headers)).status_code == 422


async def test_update_user_manager_confined(client, admin_headers, org):
    """A manager may rename a USER in their own department, but may not move that
    user to another department or promote them to a manager role."""
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'a','A'),($1,'b','B') RETURNING id, code",
        org["org_id"])
    dept = {r["code"]: str(r["id"]) for r in rows}
    r = await client.post("/auth/users", json={"username": "mgr2", "full_name": "Mgr",
        "role": "QC_MGR", "department_id": dept["a"]}, headers=admin_headers)
    mgr, motp = r.json()["user"], r.json()["otp"]
    mgr_h = {"Authorization": f"Bearer {await login_and_set_password(client, mgr['username'], motp)}"}
    r = await client.post("/auth/users", json={"username": "staff", "full_name": "Staff",
        "role": "USER", "department_id": dept["a"]}, headers=admin_headers)
    uid = r.json()["user"]["id"]

    # Rename in own dept → 200.
    assert (await client.patch(f"/auth/users/{uid}", json={"full_name": "Renamed"}, headers=mgr_h)).status_code == 200
    # Move to another dept → 403.
    assert (await client.patch(f"/auth/users/{uid}", json={"department_id": dept["b"]}, headers=mgr_h)).status_code == 403
    # Promote to a manager role → 403.
    assert (await client.patch(f"/auth/users/{uid}", json={"role": "PR_MGR"}, headers=mgr_h)).status_code == 403
