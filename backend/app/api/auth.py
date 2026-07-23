"""Auth + provisioning (SUMA methodology: no self-signup, OTP, forced change)."""
import logging
import re
import secrets
import time
import uuid
from collections import defaultdict

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import settings
from app.db import rls_users, tasks_admin_pool, users_admin_pool
from app.deps import get_current_user, require_password_set, require_role
from app.roles import ADMIN, CREATABLE_ROLES, ELEVATED_ROLES, MANAGER_ROLES
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins leave no audit_log row (those tables are populated by
# hash-chained DB triggers on data writes, and a login attempt writes
# nothing) — this structured log line is the forensic trail for brute-force
# investigation. JSON-formatted by logging_config.JsonFormatter.
log = logging.getLogger("app.auth")

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
# Authenticated mutation endpoints (change/reset password, create user) share
# the same window with per-actor keys — generous for real staff, tight enough
# that a stolen session can't grind passwords or spray accounts unthrottled.
_ACTION_MAX_PER_ACTOR = 20
_failed_attempts: dict[str, list[float]] = defaultdict(list)

# Windowed pruning above only trims lists that get re-checked; keys that stop
# being hit would otherwise sit in the dict forever (unbounded growth under a
# username/IP spray). Sweep the whole dict whenever it gets large.
_GC_THRESHOLD = 512


def _rate_limit_gc(now: float) -> None:
    if len(_failed_attempts) < _GC_THRESHOLD:
        return
    for key in [k for k, v in _failed_attempts.items() if not v or now - v[-1] > _LOGIN_WINDOW_S]:
        _failed_attempts.pop(key, None)


def _rate_limit_check(id_key: str, ip_key: str) -> None:
    now = time.monotonic()
    _rate_limit_gc(now)
    for key, limit in ((id_key, _LOGIN_MAX_ATTEMPTS_PER_ID), (ip_key, _LOGIN_MAX_ATTEMPTS_PER_IP)):
        attempts = _failed_attempts[key]
        while attempts and now - attempts[0] > _LOGIN_WINDOW_S:
            attempts.pop(0)
        if len(attempts) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts — try again later")


def _throttle_action(key: str, limit: int = _ACTION_MAX_PER_ACTOR) -> None:
    """Count-every-call throttle for authenticated auth mutations. Unlike the
    login limiter (which counts only FAILURES so real users are never locked
    out by their own successes), these endpoints are abuse-relevant on every
    call — 20 password changes / account creations per 5 minutes is far above
    any legitimate use."""
    now = time.monotonic()
    _rate_limit_gc(now)
    attempts = _failed_attempts[key]
    while attempts and now - attempts[0] > _LOGIN_WINDOW_S:
        attempts.pop(0)
    if len(attempts) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts — try again later")
    attempts.append(now)


def _rate_limit_record_failure(*keys: str) -> None:
    now = time.monotonic()
    for key in keys:
        _failed_attempts[key].append(now)


def _rate_limit_clear(*keys: str) -> None:
    for key in keys:
        _failed_attempts.pop(key, None)


# max_length bounds: none of these fields have any legitimate long form, and
# unbounded strings are a free memory/bcrypt-CPU lever (bcrypt reads only the
# first 72 bytes anyway, so a 1 MB "password" is pure cost, zero entropy).
class LoginReq(BaseModel):
    email: str = Field(max_length=254)            # accepts username or email
    password: str = Field(max_length=256)
    remember_device: bool = False


class ChangePwReq(BaseModel):
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(max_length=256)


class CreateUserReq(BaseModel):
    # No '@': an email-shaped username could shadow another account's login
    # email in the login lookup (see login()'s precedence comment).
    username: str = Field(min_length=1, max_length=64, pattern=r"^[^@\s]+$")
    full_name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    role: str = Field(default="USER", max_length=32)
    department_id: str | None = Field(default=None, max_length=64)
    function_role: str | None = Field(default=None, max_length=80)


class UpdateUserReq(BaseModel):
    # username is intentionally NOT editable — it's the login identity.
    full_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=32)
    department_id: str | None = Field(default=None, max_length=64)
    function_role: str | None = Field(default=None, max_length=80)


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

    # Username match takes strict precedence over email match. The combined
    # (username=$1 OR email=$1) fetchrow had no ORDER BY, and email carries no
    # uniqueness constraint — two accounts sharing an email (or a username
    # crafted to equal someone's login email) made authentication
    # nondeterministic: the "wrong" row could win the plan and the real
    # password would fail apparently at random.
    row = await users_admin_pool().fetchrow(
        "SELECT * FROM profiles WHERE username=$1 AND is_deleted=false", body.email)
    if row is None:
        row = await users_admin_pool().fetchrow(
            "SELECT * FROM profiles WHERE email=$1 AND is_deleted=false"
            " ORDER BY created_at LIMIT 1", body.email)
    # Rate-limit on the RESOLVED account id when one exists, not the raw typed
    # string — otherwise the same account is reachable through two separate
    # buckets (its username vs. its email, or case variants), doubling an
    # attacker's effective attempt budget against one profile. An identifier
    # that resolves to no account falls back to the typed string, which is the
    # only key available for a nonexistent login.
    id_key = f"id:{row['id']}" if row is not None else f"id:{identifier}"
    _rate_limit_check(id_key, f"ip:{ip}")

    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    # Always pay the bcrypt cost, even on a miss (unknown/inactive user) —
    # short-circuiting before it is a timing side-channel that lets an
    # attacker enumerate valid usernames by response latency.
    active = row is not None and row["is_active"]
    ok = verify_password(body.password, row["password_hash"] if active else None)
    if not active or not ok:
        _rate_limit_record_failure(f"ip:{ip}", id_key)
        # Forensic trail — audit_log is trigger-driven and never sees a failed
        # login. Identifier is what the client TYPED (may or may not exist);
        # never log the password.
        log.warning("login_failed", extra={"fields": {
            "event": "login_failed", "identifier": identifier, "ip": ip,
            "reason": "inactive_or_unknown" if not active else "bad_password"}})
        raise invalid
    _rate_limit_clear(f"ip:{ip}", id_key)
    days = settings.remember_device_expire_days if body.remember_device else None
    pwv = row["password_set_at"].isoformat() if row["password_set_at"] else None
    token = create_access_token(str(row["id"]), row["role"], str(row["org_id"]), password_set_at=pwv, days=days)
    return {"access_token": token, "token_type": "bearer", "user": _public(row)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public(user)


@router.post("/change-password")
async def change_password(body: ChangePwReq, user: dict = Depends(get_current_user)):
    _throttle_action(f"pwch:{user['id']}")
    if len(body.new_password) < settings.password_min_length:
        raise HTTPException(422, f"Password must be at least {settings.password_min_length} characters")
    # Voluntary change (flag already cleared) must prove the current password.
    if not user["must_change_password"]:
        row = await users_admin_pool().fetchrow("SELECT password_hash FROM profiles WHERE id=$1", user["id"])
        if row is None or not body.current_password or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password incorrect")
    async with rls_users(user, admin=True) as conn:
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
    # Admin (incl. qcm.blani, an ADMIN titled "QC Manager") manages any account
    # in the org, including other ADMIN accounts — assigning the ADMIN role
    # itself is blocked separately via CREATABLE_ROLES at each call site
    # (before _can_manage ever runs), so this can never promote anyone TO
    # admin; it only lets a real admin edit/delete/reset an existing one.
    if actor["role"] == ADMIN:
        return True
    # A department manager manages only USER staff, and only in their own
    # department. Managers can't create/deactivate other managers, executives,
    # or admins.
    if actor["role"] in MANAGER_ROLES:
        return (role == "USER" and department_id is not None
                and str(department_id) == str(actor["department_id"]))
    return False


def _require_uuid(value) -> None:
    """A malformed (non-uuid) {user_id} path param must be a clean 404, not a
    500 from asyncpg trying to cast it to uuid inside the lookup query."""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "User not found")


async def _validate_department(org_id, department_id) -> None:
    """profiles.department_id is a bare uuid — departments live in the tasks DB
    with no cross-database FK, so validate app-side that it names a real
    department in this org (a malformed uuid or a foreign/typo'd id would
    otherwise be stored silently and dangle when the UI joins /departments)."""
    if department_id is None:
        return
    try:
        exists = await tasks_admin_pool().fetchval(
            "SELECT 1 FROM departments WHERE id=$1 AND org_id=$2", department_id, org_id)
    except Exception:  # malformed (non-uuid) value
        raise HTTPException(422, "Unknown department")
    if not exists:
        raise HTTPException(422, "Unknown department")


@router.post("/users", status_code=201)
async def create_user(body: CreateUserReq, actor: dict = Depends(require_role(ADMIN, *MANAGER_ROLES))):
    """Provision an account with a one-time password (always returned to the creator)."""
    _throttle_action(f"usercreate:{actor['id']}")
    # Reject unknown / non-assignable roles (esp. ADMIN) up front with a clean
    # 422, rather than letting a bad value reach the DB CHECK as a 409.
    if body.role not in CREATABLE_ROLES:
        raise HTTPException(422, f"Role '{body.role}' cannot be assigned")
    if not _can_manage(actor, body.role, body.department_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to create this account")
    await _validate_department(actor["org_id"], body.department_id)
    otp = generate_otp()
    async with rls_users(actor, admin=True) as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO profiles(org_id,username,email,password_hash,full_name,role,"
                " department_id,function_role,must_change_password,created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,true,$9) RETURNING *",
                actor["org_id"], body.username, body.email, hash_password(otp), body.full_name,
                body.role, body.department_id, body.function_role, actor["id"],
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, f"Username '{body.username}' is already taken")
        except Exception as e:
            raise HTTPException(409, f"Could not create account: {type(e).__name__}")
    # OTP is shown on the creator's screen (email delivery is best-effort, added later).
    return {"user": _public(row), "otp": otp}


@router.get("/directory")
async def directory(user: dict = Depends(require_password_set)):
    """Read-only name/avatar roster for every ACTIVE org member — no management
    fields. Unlike /users (elevated-gated, includes is_active/
    must_change_password), this is safe for any authenticated user so avatars/
    assignee pickers work for non-elevated roles too. Deactivated accounts are
    excluded — same rule the weekly snapshot's roster query uses — so they
    can't be picked as assignees; /users still shows them for management."""
    async with rls_users(user) as c:
        rows = await c.fetch(
            "SELECT id,username,full_name,role,department_id,function_role"
            " FROM profiles WHERE is_deleted=false AND is_active AND org_id=$1"
            " ORDER BY full_name", user["org_id"])
    return [{"id": str(r["id"]), "username": r["username"], "full_name": r["full_name"],
             "role": r["role"], "department_id": str(r["department_id"]) if r["department_id"] else None,
             "function_role": r["function_role"]} for r in rows]


_DELETED_SUFFIX_RE = re.compile(r"__deleted_[0-9a-f]{32}$")


@router.get("/users/deleted")
async def list_deleted_users(actor: dict = Depends(require_role(ADMIN, *MANAGER_ROLES))):
    """Soft-deleted accounts in the org — the only way to discover a username
    is stuck (delete_user mangles it on the way out so it's free for reuse,
    but the mangled form isn't something anyone would guess) or to purge one
    for good. Same authorisation as create/delete/reset: admin sees everyone,
    a manager sees only their own department's former staff."""
    async with rls_users(actor, admin=True) as conn:
        rows = await conn.fetch(
            "SELECT id,username,full_name,role,department_id,updated_at FROM profiles"
            " WHERE is_deleted=true AND org_id=$1 ORDER BY updated_at DESC", actor["org_id"])
    out = []
    for r in rows:
        if not _can_manage(actor, r["role"], r["department_id"]):
            continue
        out.append({
            "id": str(r["id"]), "username": _DELETED_SUFFIX_RE.sub("", r["username"]),
            "full_name": r["full_name"], "role": r["role"],
            "department_id": str(r["department_id"]) if r["department_id"] else None,
            "deleted_at": r["updated_at"].isoformat(),
        })
    return out


@router.delete("/users/{user_id}/purge", status_code=200)
async def purge_user(user_id: str, actor: dict = Depends(require_role(ADMIN))):
    """Permanently remove a soft-deleted account. ADMIN-only (unlike the
    ordinary soft delete, this is unrecoverable and drops the name/avatar
    the tasks DB's bare-uuid roster join would otherwise still resolve for
    that person's historical tasks/reports — the audit trail is unaffected,
    since audit_log rows are never deleted). Only ever targets a row that
    is ALREADY soft-deleted, so this can't be used to skip the normal
    delete flow (and its _can_manage authorisation) in one step."""
    _require_uuid(user_id)
    async with rls_users(actor, admin=True) as conn:
        row = await conn.fetchrow(
            "DELETE FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=true RETURNING id",
            user_id, actor["org_id"])
    if row is None:
        raise HTTPException(404, "Deleted account not found")
    return {"ok": True}


@router.get("/users")
async def list_users(actor: dict = Depends(require_role(*ELEVATED_ROLES))):
    # Scope to the caller's org explicitly: the admin pool is BYPASSRLS, so the
    # profiles_read policy does NOT filter it — without org_id this would leak
    # every organisation's user directory.
    async with rls_users(actor, admin=True) as conn:
        rows = await conn.fetch(
            "SELECT id,username,full_name,role,department_id,function_role,is_active,must_change_password"
            " FROM profiles WHERE is_deleted=false AND org_id=$1 ORDER BY full_name", actor["org_id"])
    return [{"id": str(r["id"]), "username": r["username"], "full_name": r["full_name"],
             "role": r["role"], "department_id": str(r["department_id"]) if r["department_id"] else None,
             "function_role": r["function_role"], "is_active": r["is_active"],
             "must_change_password": r["must_change_password"]} for r in rows]


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, actor: dict = Depends(require_role(ADMIN, *MANAGER_ROLES))):
    _require_uuid(user_id)
    if str(user_id) == str(actor["id"]):
        raise HTTPException(400, "Cannot delete your own account")
    # Admin pool is BYPASSRLS, so authorisation is enforced here: the target
    # must be in the actor's org AND manageable by them (a manager cannot
    # delete an ADMIN or anyone outside their department). Same gate as create.
    async with rls_users(actor, admin=True) as conn:
        target = await conn.fetchrow(
            "SELECT role, department_id FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=false",
            user_id, actor["org_id"])
        if target is None:
            raise HTTPException(404, "User not found")
        if not _can_manage(actor, target["role"], target["department_id"]):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to delete this account")
        # Mangle the username so it's released for reuse — profiles_username_key
        # is a plain UNIQUE constraint with no is_deleted scoping, so a bare soft
        # delete (is_deleted=true only) permanently squats the username, making
        # "delete this account, then recreate it the same way" impossible. The
        # suffixed id keeps the row unique and still traceable; login/directory/
        # list_users all already filter is_deleted=false so this is invisible
        # anywhere the username is looked up going forward.
        await conn.execute(
            "UPDATE profiles SET is_deleted=true, is_active=false,"
            " username=username || '__deleted_' || replace(id::text,'-',''), updated_at=now()"
            " WHERE id=$1 AND org_id=$2",
            user_id, actor["org_id"])
    return {"ok": True}


@router.post("/users/{user_id}/reset-password", status_code=200)
async def reset_password(user_id: str, actor: dict = Depends(require_role(ADMIN, *MANAGER_ROLES))):
    """Admin/manager resets an existing account's password to a fresh one-time
    password (shown once to the caller). The user must set their own on next
    login — same flow as account creation, so an admin never learns or sets the
    real password. Same authorisation gate as create/delete: a manager may only
    reset a USER in their own department; nobody may reset an ADMIN through the
    app."""
    _throttle_action(f"pwreset:{actor['id']}")
    _require_uuid(user_id)
    if str(user_id) == str(actor["id"]):
        # Self-service password change goes through /auth/change-password (which
        # proves the current password); the admin reset path is for OTHER users.
        raise HTTPException(400, "Use change-password for your own account")
    otp = generate_otp()
    async with rls_users(actor, admin=True) as conn:
        target = await conn.fetchrow(
            "SELECT id, username, full_name, role, department_id, function_role, must_change_password"
            " FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=false", user_id, actor["org_id"])
        if target is None:
            raise HTTPException(404, "User not found")
        if not _can_manage(actor, target["role"], target["department_id"]):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to reset this account")
        row = await conn.fetchrow(
            "UPDATE profiles SET password_hash=$1, must_change_password=true,"
            " password_set_at=now(), updated_at=now() WHERE id=$2 AND org_id=$3 RETURNING *",
            hash_password(otp), user_id, actor["org_id"])
    return {"user": _public(row), "otp": otp}


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserReq,
                      actor: dict = Depends(require_role(ADMIN, *MANAGER_ROLES))):
    """Edit an existing account's profile (name, role, department, title). Same
    authorisation model as create/delete — a manager may only touch a USER in
    their own department, ADMIN is never assignable, and the caller must be able
    to manage BOTH the account's current state and its requested new state."""
    _require_uuid(user_id)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return {"ok": True, "noop": True}
    if "role" in fields and fields["role"] not in CREATABLE_ROLES:
        raise HTTPException(422, f"Role '{fields['role']}' cannot be assigned")
    # No self-demotion: an ADMIN passes _can_manage for any target now (incl.
    # their own ADMIN account), so without this an admin could PATCH their own
    # role/department and instantly drop their own privileges. Renaming
    # yourself is fine; changing your own role/department is not — use another
    # admin for that (mirrors delete_user/reset_password's self-action guards).
    if str(user_id) == str(actor["id"]) and ("role" in fields or "department_id" in fields):
        raise HTTPException(400, "Cannot change your own role or department")
    async with rls_users(actor, admin=True) as conn:
        target = await conn.fetchrow(
            "SELECT id, role, department_id FROM profiles WHERE id=$1 AND org_id=$2 AND is_deleted=false",
            user_id, actor["org_id"])
        if target is None:
            raise HTTPException(404, "User not found")
        # Manageable both as it stands now AND as it would be after the edit —
        # so a manager can't move a USER out of their department, or promote one.
        new_role = fields.get("role", target["role"])
        new_dept = fields.get("department_id", target["department_id"])
        if not _can_manage(actor, target["role"], target["department_id"]) or \
           not _can_manage(actor, new_role, new_dept):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to edit this account")
        if "department_id" in fields:
            await _validate_department(actor["org_id"], fields["department_id"])
        sets, args = [], []
        for col in ("full_name", "role", "department_id", "function_role"):
            if col not in fields:
                continue
            val = fields[col]
            if val is None and col in ("full_name", "role"):
                continue  # NOT NULL columns — an explicit null means "leave as-is"
            args.append(val); sets.append(f"{col}=${len(args)}")
        if not sets:
            return {"ok": True, "noop": True}
        args.append(user_id); args.append(actor["org_id"])
        row = await conn.fetchrow(
            f"UPDATE profiles SET {', '.join(sets)}, updated_at=now()"
            f" WHERE id=${len(args)-1} AND org_id=${len(args)} RETURNING *", *args)
    return _public(row)
