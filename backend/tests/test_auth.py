"""P1 — account provisioning, forced first-login password change, RBAC gates."""
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
    """A leaked/intercepted OTP for a freshly-provisioned DEPT_HEAD must not
    grant role-gated actions (user management, audit) before the real user
    completes their mandatory first-login password change — require_role()
    must enforce the same gate as require_password_set(), not bypass it."""
    dept_head, otp = await create_user(client, admin_headers, role="DEPT_HEAD")
    r = await client.post("/auth/login", json={"email": dept_head["username"], "password": otp})
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
    token = await login_and_set_password(client, dept_head["username"], otp)
    r = await client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_dept_head_confined_to_own_department(client, admin_headers, org):
    """_can_manage()'s DEPT_HEAD branch is only ever exercised via the
    fixture's ADMIN in every other test — nothing pins that a DEPT_HEAD is
    actually confined to their own department, or barred from creating an
    ADMIN account."""
    from app.db import admin_pool
    rows = await admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'a','Dept A'), ($1,'b','Dept B')"
        " RETURNING id, code",
        org["org_id"],
    )
    dept_ids = {r["code"]: str(r["id"]) for r in rows}

    r = await client.post("/auth/users", json={
        "username": "depthead_a", "full_name": "Dept Head A", "role": "DEPT_HEAD",
        "department_id": dept_ids["a"],
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    dept_head, otp = r.json()["user"], r.json()["otp"]
    dh_token = await login_and_set_password(client, dept_head["username"], otp)
    dh_headers = {"Authorization": f"Bearer {dh_token}"}

    # Can create a USER within their own department.
    r = await client.post("/auth/users", json={
        "username": "same_dept_user", "full_name": "Same Dept", "role": "USER",
        "department_id": dept_ids["a"],
    }, headers=dh_headers)
    assert r.status_code == 201, r.text
    same_dept_user = r.json()["user"]

    # Cannot create a USER in a different department.
    r = await client.post("/auth/users", json={
        "username": "other_dept_user", "full_name": "Other Dept", "role": "USER",
        "department_id": dept_ids["b"],
    }, headers=dh_headers)
    assert r.status_code == 403

    # Cannot create an ADMIN, even within their own department.
    r = await client.post("/auth/users", json={
        "username": "sneaky_admin", "full_name": "Sneaky", "role": "ADMIN",
        "department_id": dept_ids["a"],
    }, headers=dh_headers)
    assert r.status_code == 403

    # Delete mirrors create: can delete within their department...
    r = await client.delete(f"/auth/users/{same_dept_user['id']}", headers=dh_headers)
    assert r.status_code == 200, r.text

    # ...but not a user in a different department.
    r = await client.post("/auth/users", json={
        "username": "victim_dept_b", "full_name": "Victim", "role": "USER", "department_id": dept_ids["b"],
    }, headers=admin_headers)
    victim = r.json()["user"]
    r = await client.delete(f"/auth/users/{victim['id']}", headers=dh_headers)
    assert r.status_code == 403
