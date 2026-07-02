"""P1 — account provisioning, forced first-login password change, RBAC gates."""
from tests.conftest import create_user, login_and_set_password


async def test_provision_login_forced_change_flow(client, admin_headers):
    user, otp = await create_user(client, admin_headers, role="USER")
    assert user["must_change_password"] is True
    await login_and_set_password(client, user["username"], otp)


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
