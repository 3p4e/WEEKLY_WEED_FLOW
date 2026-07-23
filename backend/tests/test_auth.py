"""P1 — account provisioning, forced first-login password change, RBAC gates."""
import uuid

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


async def test_deleting_a_user_frees_their_username_for_reuse(client, admin_headers):
    """profiles_username_key is a plain UNIQUE constraint with no is_deleted
    scoping — a bare soft delete (is_deleted=true only, username untouched)
    would permanently squat the username, so "delete this account, then
    recreate it the same way" would 409 forever. delete_user mangles the
    username on delete specifically to prevent that."""
    r = await client.post("/auth/users", json={
        "username": "reusable_name", "full_name": "First Account", "role": "USER",
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    user = r.json()["user"]
    r = await client.delete(f"/auth/users/{user['id']}", headers=admin_headers)
    assert r.status_code == 200
    r = await client.post("/auth/users", json={
        "username": "reusable_name", "full_name": "Second Account", "role": "USER",
    }, headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_deleted_users_list_shows_the_original_username(client, admin_headers):
    """GET /auth/users/deleted is how an admin discovers a mangled username
    without having to guess it — it should report the pre-delete username,
    not the mangled row, and never include an active account."""
    r = await client.post("/auth/users", json={
        "username": "will_be_removed", "full_name": "Removed Person", "role": "USER",
    }, headers=admin_headers)
    user = r.json()["user"]
    await client.delete(f"/auth/users/{user['id']}", headers=admin_headers)

    r = await client.get("/auth/users/deleted", headers=admin_headers)
    assert r.status_code == 200
    entries = {e["id"]: e for e in r.json()}
    assert user["id"] in entries
    assert entries[user["id"]]["username"] == "will_be_removed"
    assert all("__deleted_" not in e["username"] for e in entries.values())


async def test_purge_removes_a_deleted_account_permanently(client, admin_headers):
    r = await client.post("/auth/users", json={
        "username": "to_be_purged", "full_name": "Purge Me", "role": "USER",
    }, headers=admin_headers)
    user = r.json()["user"]
    await client.delete(f"/auth/users/{user['id']}", headers=admin_headers)

    r = await client.delete(f"/auth/users/{user['id']}/purge", headers=admin_headers)
    assert r.status_code == 200

    r = await client.get("/auth/users/deleted", headers=admin_headers)
    assert user["id"] not in {e["id"] for e in r.json()}
    # Purge is idempotent-safe against double-calling — the row is gone, 404 not 500.
    r = await client.delete(f"/auth/users/{user['id']}/purge", headers=admin_headers)
    assert r.status_code == 404


async def test_purge_rejects_an_account_that_was_never_deleted(client, admin_headers, org):
    """Purge only ever targets an already soft-deleted row — it can't be used
    to skip the ordinary delete flow (and its _can_manage authorisation) in
    one step."""
    r = await client.delete(f"/auth/users/{org['admin_id']}/purge", headers=admin_headers)
    assert r.status_code == 404


async def test_purge_is_admin_only(client, admin_headers):
    """A department manager can soft-delete their own staff, but purging is
    ADMIN-only — permanently dropping the roster-join name/avatar for that
    person's historical tasks/reports is a heavier call than a manager
    should get to make alone."""
    r = await client.post("/auth/users", json={
        "username": "mgr_for_purge_test", "full_name": "Mgr", "role": "QC_MGR",
    }, headers=admin_headers)
    mgr, otp = r.json()["user"], r.json()["otp"]
    mgr_token = await login_and_set_password(client, mgr["username"], otp)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    r = await client.post("/auth/users", json={
        "username": "staff_for_purge_test", "full_name": "Staff", "role": "USER",
        "department_id": None,
    }, headers=admin_headers)
    staff = r.json()["user"]
    await client.delete(f"/auth/users/{staff['id']}", headers=admin_headers)

    r = await client.delete(f"/auth/users/{staff['id']}/purge", headers=mgr_headers)
    assert r.status_code == 403


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
    department managers, the QP, and executives (OWNER/CEO/COO) alike — but
    ADMIN itself is never assignable, even by an admin (DB-seeded only → 422)."""
    for role in ("QC_MGR", "QP", "OWNER", "CEO", "COO"):
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


async def test_admin_can_edit_an_existing_admin_account(client, admin_headers, org):
    """A second ADMIN-role account (e.g. a QC manager who is also an admin, like
    production's qcm.blani) must still be editable/manageable by the real admin
    — _can_manage() must not blanket-reject a target whose CURRENT role is
    ADMIN, only ever block ASSIGNING the ADMIN role (already 422'd separately)."""
    from app.db import tasks_admin_pool, users_admin_pool
    import uuid
    dept = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC') RETURNING id",
        org["org_id"])
    other_admin_id = str(uuid.uuid4())
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role,"
        " department_id, function_role, must_change_password)"
        " VALUES ($1,$2,'qcm.other','qcm.other@test.invalid','x','QC Manager','ADMIN',$3,'QC Manager',false)",
        other_admin_id, org["org_id"], dept["id"])

    r = await client.patch(f"/auth/users/{other_admin_id}",
        json={"full_name": "QC Manager Renamed", "function_role": "Senior QC Manager"},
        headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "QC Manager Renamed"

    # Demoting an existing admin to a normal elevated role is allowed too.
    r = await client.patch(f"/auth/users/{other_admin_id}", json={"role": "QC_MGR"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "QC_MGR"

    # Reset-password and delete on an (still-)admin account also work for the real admin.
    other_admin_id2 = str(uuid.uuid4())
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,'qcm.other2','qcm.other2@test.invalid','x','Other Admin','ADMIN',false)",
        other_admin_id2, org["org_id"])
    assert (await client.post(f"/auth/users/{other_admin_id2}/reset-password", headers=admin_headers)).status_code == 200
    assert (await client.delete(f"/auth/users/{other_admin_id2}", headers=admin_headers)).status_code == 200


async def test_admin_cannot_change_own_role_or_department(client, admin_headers, org):
    """Now that a real ADMIN passes _can_manage for any target (incl. their own
    ADMIN account), update_user must still refuse a SELF role/department change —
    otherwise an admin could PATCH their own id and instantly drop their own
    privileges. Renaming yourself stays allowed."""
    me = (await client.get("/auth/me", headers=admin_headers)).json()
    my_id = me["id"]
    # Self role change → 400.
    r = await client.patch(f"/auth/users/{my_id}", json={"role": "QC_MGR"}, headers=admin_headers)
    assert r.status_code == 400, r.text
    # Self department change → 400.
    from app.db import tasks_admin_pool
    dept = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC') RETURNING id", org["org_id"])
    r = await client.patch(f"/auth/users/{my_id}", json={"department_id": str(dept["id"])}, headers=admin_headers)
    assert r.status_code == 400, r.text
    # But renaming yourself is fine.
    r = await client.patch(f"/auth/users/{my_id}", json={"full_name": "Renamed Self"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Renamed Self"


async def test_manager_still_cannot_touch_an_admin_account(client, admin_headers, org):
    """A department manager must never be able to edit/delete/reset an ADMIN
    account, even one parked in their own department."""
    from app.db import tasks_admin_pool, users_admin_pool
    import uuid
    dept = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC') RETURNING id",
        org["org_id"])
    r = await client.post("/auth/users", json={"username": "mgr3", "full_name": "Mgr",
        "role": "QC_MGR", "department_id": str(dept["id"])}, headers=admin_headers)
    mgr, motp = r.json()["user"], r.json()["otp"]
    mgr_h = {"Authorization": f"Bearer {await login_and_set_password(client, mgr['username'], motp)}"}

    admin_in_dept_id = str(uuid.uuid4())
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role,"
        " department_id, must_change_password)"
        " VALUES ($1,$2,'qcm.other3','qcm.other3@test.invalid','x','QC Admin','ADMIN',$3,false)",
        admin_in_dept_id, org["org_id"], dept["id"])

    assert (await client.patch(f"/auth/users/{admin_in_dept_id}",
        json={"full_name": "x"}, headers=mgr_h)).status_code == 403
    assert (await client.post(f"/auth/users/{admin_in_dept_id}/reset-password", headers=mgr_h)).status_code == 403
    assert (await client.delete(f"/auth/users/{admin_in_dept_id}", headers=mgr_h)).status_code == 403


async def test_account_endpoints_reject_malformed_id_with_404(client, admin_headers):
    """A non-uuid {user_id} path param must be a clean 404, not a 500 from
    asyncpg failing to cast it to uuid inside the lookup query."""
    assert (await client.post("/auth/users/not-a-uuid/reset-password", headers=admin_headers)).status_code == 404
    assert (await client.patch("/auth/users/not-a-uuid", json={"full_name": "x"}, headers=admin_headers)).status_code == 404
    assert (await client.delete("/auth/users/not-a-uuid", headers=admin_headers)).status_code == 404


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


async def test_owner_sees_org_wide_tasks_and_departments(client, admin_headers):
    """Regression for the empty-app OWNER bug: the tasks DB carries its own
    app.is_elevated() used by every RLS policy there, and it fell out of sync
    with the users DB when OWNER (and SE_MGR/MU_MGR) were added — so an OWNER
    passed the app-side role gates but RLS filtered every row, and the owner
    logged in to a blank application. Pins that an OWNER (who owns no tasks)
    reads the org's tasks and departments through RLS."""
    r = await client.post("/tasks", json={"title": "Visible to the owner", "status": "pending"},
                          headers=admin_headers)
    assert r.status_code == 201

    owner, otp = await create_user(client, admin_headers, role="OWNER")
    token = await login_and_set_password(client, owner["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/tasks", headers=headers)
    assert r.status_code == 200
    assert any(t["title"] == "Visible to the owner" for t in r.json()), \
        "OWNER must have org-wide task visibility (tasks-DB is_elevated regressed)"

    # And the same for the other RLS-gated reads the app boots with.
    assert (await client.get("/departments", headers=headers)).status_code == 200
    assert (await client.get("/audit", headers=headers)).status_code == 200


async def test_login_rate_limit_keys_on_resolved_account_not_typed_string(client, admin_headers):
    """Two different login strings for the SAME account (its username vs. its
    email) must share one rate-limit bucket, keyed on the resolved account id
    — otherwise an attacker doubles their effective attempt budget by
    switching which string they submit for the same profile."""
    username = f"ratekey_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.test"
    r = await client.post("/auth/users", json={
        "username": username, "full_name": "Rate Key Test", "role": "USER", "email": email,
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    otp = r.json()["otp"]
    await login_and_set_password(client, username, otp)
    # Exhaust the 8-attempt per-account bucket via the USERNAME.
    for _ in range(8):
        r = await client.post("/auth/login", json={"email": username, "password": "wrong-password"})
        assert r.status_code == 401
    # The 9th attempt, submitted via the EMAIL (a different typed string, same
    # resolved account), must already be rate-limited — if it opened a fresh
    # bucket keyed on the raw string instead of the resolved id, this would
    # still return 401 instead of 429.
    r = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert r.status_code == 429
