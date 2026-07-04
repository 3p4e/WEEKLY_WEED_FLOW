"""Auth + provisioning (SUMA methodology: no self-signup, OTP, forced change)."""
import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import settings
from app.db import admin_pool, rls
from app.deps import get_current_user, require_password_set, require_role
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_OTP_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def generate_otp() -> str:
    g = lambda: "".join(secrets.choice(_OTP_ALPHABET) for _ in range(4))
    return f"{g()}-{g()}-{g()}"


# ── Login rate limiting ──────────────────────────────────────────────
# In-process (single backend replica — see docs/DEPLOY.md), so a plain dict
# is enough; no Redis for a facility-internal app this size. Two independent
# thresholds: identifier is tight (guards one account against brute force),
# IP is much looser — this is a single-facility app where many real staff
# plausibly share one office IP, so a low IP threshold would let one
# person's typos lock out everyone else on the same network.
_LOGIN_WINDOW_S = 300
_LOGIN_MAX_ATTEMPTS_PER_ID = 8
_LOGIN_MAX_ATTEMPTS_PER_IP = 30
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _rate_limit_check(id_key: str, ip_key: str) -> None:
    now = time.monotonic()
    for key, limit in ((id_key, _LOGIN_MAX_ATTEMPTS_PER_ID), (ip_key, _LOGIN_MAX_ATTEMPTS_PER_IP)):
        attempts = _failed_attempts[key]
        while attempts and now - attempts[0] > _LOGIN_WINDOW_S:
            attempts.pop(0)
        if len(attempts) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts — try again later")


def _rate_limit_record_failure(*keys: str) -> None:
    now = time.monotonic()
    for key in keys:
        _failed_attempts[key].append(now)


def _rate_limit_clear(*keys: str) -> None:
    for key in keys:
        _failed_attempts.pop(key, None)


class LoginReq(BaseModel):
    email: str            # accepts username or email
    password: str
    remember_device: bool = False


class ChangePwReq(BaseModel):
    current_password: str | None = None
    new_password: str


class CreateUserReq(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    role: str = "USER"
    department_id: str | None = None
    function_role: str | None = None


def _public(row) -> dict:
    return {
        "id": str(row["id"]), "username": row["username"], "full_name": row["full_name"],
        "role": row["role"], "department_id": str(row["department_id"]) if row["department_id"] else None,
        "function_role": row["function_role"], "must_change_password": row["must_change_password"],
    }


@router.post("/login")
async def login(body: LoginReq, request: Request):
    ip = request.client.host if request.client else "unknown"
    identifier = body.email.lower()
    _rate_limit_check(f"id:{identifier}", f"ip:{ip}")

    row = await admin_pool().fetchrow(
        "SELECT * FROM profiles WHERE (username=$1 OR email=$1) AND is_deleted=false",
        body.email,
    )
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    # Always pay the bcrypt cost, even on a miss (unknown/inactive user) —
    # short-circuiting before it is a timing side-channel that lets an
    # attacker enumerate valid usernames by response latency.
    active = row is not None and row["is_active"]
    ok = verify_password(body.password, row["password_hash"] if active else None)
    if not active or not ok:
        _rate_limit_record_failure(f"ip:{ip}", f"id:{identifier}")
        raise invalid
    _rate_limit_clear(f"ip:{ip}", f"id:{identifier}")
    days = settings.remember_device_expire_days if body.remember_device else None
    pwv = row["password_set_at"].isoformat() if row["password_set_at"] else None
    token = create_access_token(str(row["id"]), row["role"], str(row["org_id"]), password_set_at=pwv, days=days)
    return {"access_token": token, "token_type": "bearer", "user": _public(row)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public(user)


@router.post("/change-password")
async def change_password(body: ChangePwReq, user: dict = Depends(get_current_user)):
    if len(body.new_password) < settings.password_min_length:
        raise HTTPException(422, f"Password must be at least {settings.password_min_length} characters")
    # Voluntary change (flag already cleared) must prove the current password.
    if not user["must_change_password"]:
        row = await admin_pool().fetchrow("SELECT password_hash FROM profiles WHERE id=$1", user["id"])
        if row is None or not body.current_password or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password incorrect")
    async with rls(user, admin=True) as conn:
        new_pwv = await conn.fetchval(
            "UPDATE profiles SET password_hash=$1, must_change_password=false,"
            " password_set_at=now(), updated_at=now() WHERE id=$2 RETURNING password_set_at",
            hash_password(body.new_password), user["id"],
        )
    # The token that authenticated this request is now stale (its pwv claim
    # no longer matches the password_set_at we just wrote) — mint a fresh
    # one bound to the new value, or the caller's very next request 401s.
    token = create_access_token(
        str(user["id"]), user["role"], str(user["org_id"]), password_set_at=new_pwv.isoformat())
    return {"ok": True, "access_token": token, "token_type": "bearer"}


def _can_manage(actor: dict, role: str, department_id: str | None) -> bool:
    if actor["role"] == "ADMIN":
        return True
    if actor["role"] == "DEPT_HEAD":
        return role != "ADMIN" and department_id is not None and str(department_id) == str(actor["department_id"])
    return False


@router.post("/users", status_code=201)
async def create_user(body: CreateUserReq, actor: dict = Depends(require_role("ADMIN", "DEPT_HEAD"))):
    """Provision an account with a one-time password (always returned to the creator)."""
    if not _can_manage(actor, body.role, body.department_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to create this account")
    otp = generate_otp()
    async with rls(actor, admin=True) as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO profiles(org_id,username,email,password_hash,full_name,role,"
                " department_id,function_role,must_change_password,created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,true,$9) RETURNING *",
                actor["org_id"], body.username, body.email, hash_password(otp), body.full_name,
                body.role, body.department_id, body.function_role, actor["id"],
            )
        except Exception as e:  # unique violation etc.
            raise HTTPException(409, f"Could not create account: {type(e).__name__}")
    # OTP is shown on the creator's screen (email delivery is best-effort, added later).
    return {"user": _public(row), "otp": otp}


@router.get("/directory")
async def directory(user: dict = Depends(require_password_set)):
    """Read-only name/avatar roster for every ACTIVE org member — no management
    fields. Unlike /users (ADMIN/DEPT_HEAD-gated, includes is_active/
    must_change_password), this is safe for any authenticated user so avatars/
    assignee pickers work for non-elevated roles too. Deactivated accounts are
    excluded — same rule the weekly snapshot's roster query uses — so they
    can't be picked as assignees; /users still shows them for management."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id,username,full_name,role,department_id,function_role"
            " FROM profiles WHERE is_deleted=false AND is_active AND org_id=$1"
            " ORDER BY full_name", user["org_id"])
    return [{"id": str(r["id"]), "username": r["username"], "full_name": r["full_name"],
             "role": r["role"], "department_id": str(r["department_id"]) if r["department_id"] else None,
             "function_role": r["function_role"]} for r in rows]


@router.get("/users")
async def list_users(actor: dict = Depends(require_role("ADMIN", "DEPT_HEAD"))):
    # Scope to the caller's org explicitly: the admin pool is BYPASSRLS, so the
    # profiles_read policy does NOT filter it — without org_id this would leak
    # every organisation's user directory.
    async with rls(actor, admin=True) as conn:
        rows = await conn.fetch(
            "SELECT id,username,full_name,role,department_id,function_role,is_active,must_change_password"
            " FROM profiles WHERE is_deleted=false AND org_id=$1 ORDER BY full_name", actor["org_id"])
    return [{"id": str(r["id"]), "username": r["username"], "full_name": r["full_name"],
             "role": r["role"], "department_id": str(r["department_id"]) if r["department_id"] else None,
             "function_role": r["function_role"], "is_active": r["is_active"],
             "must_change_password": r["must_change_password"]} for r in rows]


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, actor: dict = Depends(require_role("ADMIN", "DEPT_HEAD"))):
    if str(user_id) == str(actor["id"]):
        raise HTTPException(400, "Cannot delete your own account")
    # Admin pool is BYPASSRLS, so authorisation is enforced here: the target
    # must be in the actor's org AND manageable by them (a DEPT_HEAD cannot
    # delete an ADMIN or anyone outside their department). Same gate as create.
    async with rls(actor, admin=True) as conn:
        target = await conn.fetchrow(
            "SELECT role, department_id FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=false",
            user_id, actor["org_id"])
        if target is None:
            raise HTTPException(404, "User not found")
        if not _can_manage(actor, target["role"], target["department_id"]):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to delete this account")
        await conn.execute(
            "UPDATE profiles SET is_deleted=true, is_active=false, updated_at=now() WHERE id=$1 AND org_id=$2",
            user_id, actor["org_id"])
    return {"ok": True}
