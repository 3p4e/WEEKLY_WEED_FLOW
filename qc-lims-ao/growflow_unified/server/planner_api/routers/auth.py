"""Planner authentication — login (JWT, lockout), forced password change, and
admin OTP provisioning. Grafts the SUMA/WWF methodology onto T_PLAN's RBAC:
no self-signup; provisioned accounts get a one-time temp password and must change
it on first login; repeated failures lock the account temporarily.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .. import audit
from ..auth_deps import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from ..config import get_settings
from ..db import get_session
from ..schemas import (
    ActiveChange, AdminUserOut, LoginRequest, ProvisionRequest, ProvisionResult,
    ResetConfirm, ResetRequest, ResetResult, RoleChange, Token, UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_USER_SELECT = (
    "SELECT u.id, u.username, u.full_name, u.role, u.email, u.avatar_url, "
    "u.password_hash, u.dept_id, u.must_change_password, u.locked_until, "
    "u.failed_login_count, u.cross_department, d.key AS dept_key "
    "FROM app_user u LEFT JOIN planner_department d ON d.id = u.dept_id "
)


def _user_out(row) -> UserOut:
    return UserOut(
        id=str(row["id"]),
        username=row["username"],
        full_name=row["full_name"],
        role=row["role"],
        email=row["email"],
        avatar_url=row["avatar_url"],
        dept_id=str(row["dept_id"]) if row["dept_id"] else None,
        dept_key=row["dept_key"],
        must_change_password=bool(row["must_change_password"]),
        cross_department=bool(row["cross_department"]),
    )


# Account hierarchy (tiers, top → bottom): admin → executive (C-level) →
# hod (head of department) → qp / qa / operator (staff). Provisioning authority:
#   admin      → any role, any department, may set cross-department
#   executive  → hod / qp / qa / operator, any department, may set cross-department
#   hod        → qp / qa / operator, OWN department only, no cross-department
#   others     → none
_ROLES = {"operator", "qa", "qp", "hod", "executive", "admin"}
_STAFF = {"operator", "qa", "qp"}


def _provision_error(actor: CurrentUser, role: str, dept_id: str | None, cross: bool) -> str | None:
    if role not in _ROLES:
        return f"unknown role '{role}'"
    if actor.role == "admin":
        return None
    if actor.role == "executive":
        if role in ("admin", "executive"):
            return "C-level may not create admin or executive accounts"
        return None
    if actor.role == "hod":
        if role not in _STAFF:
            return "a Head of Department may only create staff accounts (operator / qa / qp)"
        if cross:
            return "a Head of Department may not create inter-department accounts"
        if not actor.dept_id or dept_id != actor.dept_id:
            return "a Head of Department may only create accounts in their own department"
        return None
    return "you are not permitted to create accounts"


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> Token:
    s = get_settings()
    now = datetime.now(timezone.utc)
    row = (
        await session.execute(
            text(_USER_SELECT + "WHERE (u.username = :id OR u.email = :id) AND u.is_active"),
            {"id": body.username},
        )
    ).mappings().first()

    if row is not None and row["locked_until"] is not None and row["locked_until"] > now:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="account temporarily locked")

    if row is None or not verify_password(body.password, row["password_hash"]):
        if row is not None:
            attempts = (row["failed_login_count"] or 0) + 1
            lock = now + timedelta(minutes=s.lockout_minutes) if attempts >= s.max_login_attempts else None
            await session.execute(
                text("UPDATE app_user SET failed_login_count = :n, locked_until = :lock WHERE id = :id"),
                {"n": attempts, "lock": lock, "id": str(row["id"])},
            )
            await session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

    await session.execute(
        text("UPDATE app_user SET failed_login_count = 0, locked_until = NULL, last_login_at = now() "
             "WHERE id = :id"),
        {"id": str(row["id"])},
    )
    await audit.record_event(
        session, actor_id=str(row["id"]), action="login", entity_type="app_user",
        entity_id=str(row["id"]), payload={"username": row["username"]},
    )
    await session.commit()
    user = _user_out(row)
    return Token(access_token=create_access_token(subject=user.id, role=user.role), user=user)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", response_model=UserOut)
async def change_password(
    body: ChangePasswordRequest,
    current: CurrentUser = Depends(get_current_user),  # allowed even while must_change_password
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    if len(body.new_password) < 10:
        raise HTTPException(status_code=422, detail="new password must be at least 10 characters")
    row = (
        await session.execute(text(_USER_SELECT + "WHERE u.id = :id"), {"id": current.id})
    ).mappings().first()
    if row is None or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="current password is incorrect")
    await session.execute(
        text("UPDATE app_user SET password_hash = :h, must_change_password = FALSE, "
             "password_set_at = now(), failed_login_count = 0, locked_until = NULL WHERE id = :id"),
        {"h": hash_password(body.new_password), "id": current.id},
    )
    await audit.record_event(
        session, actor_id=current.id, action="change_password", entity_type="app_user",
        entity_id=current.id, payload={"forced": bool(row["must_change_password"])},
    )
    await session.commit()
    fresh = (
        await session.execute(text(_USER_SELECT + "WHERE u.id = :id"), {"id": current.id})
    ).mappings().first()
    return _user_out(fresh)


@router.post("/provision", response_model=ProvisionResult, status_code=201)
async def provision(
    body: ProvisionRequest,
    admin: CurrentUser = Depends(require_role("admin", "executive", "hod")),
    session: AsyncSession = Depends(get_session),
) -> ProvisionResult:
    """Create an account with a one-time temp password. No self-signup. The OTP is
    returned ONCE; the user must change it on first login (must_change_password).
    Provisioning authority follows the account hierarchy (admin → executive → hod)."""
    err = _provision_error(admin, body.role, body.dept_id, body.cross_department)
    if err is not None:
        raise HTTPException(status_code=403, detail=err)
    exists = (
        await session.execute(text("SELECT 1 FROM app_user WHERE username = :u"), {"u": body.username})
    ).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    otp = secrets.token_urlsafe(9)  # ~12 chars, single use
    new_id = (
        await session.execute(
            text(
                "INSERT INTO app_user (username, full_name, role, email, dept_id, cross_department, "
                "password_hash, must_change_password, password_set_at) "
                "VALUES (:u, :fn, :role, :email, :dept, :cross, :h, TRUE, now()) RETURNING id"
            ),
            {
                "u": body.username, "fn": body.full_name, "role": body.role,
                "email": body.email, "dept": body.dept_id, "cross": body.cross_department,
                "h": hash_password(otp),
            },
        )
    ).scalar_one()
    await audit.record_event(
        session, actor_id=admin.id, action="provision_user", entity_type="app_user",
        entity_id=str(new_id),
        payload={"username": body.username, "role": body.role, "dept_id": body.dept_id,
                 "cross_department": body.cross_department, "by_role": admin.role},
    )
    await session.commit()
    return ProvisionResult(
        id=str(new_id), username=body.username, role=body.role, temp_password=otp,
        expires_hours=get_settings().otp_ttl_hours,
    )


@router.get("/me", response_model=UserOut)
async def me(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    row = (
        await session.execute(text(_USER_SELECT + "WHERE u.id = :id"), {"id": current.id})
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _user_out(row)


# ── Self-service password reset (forgot → reset code) ───────────────────────
@router.post("/reset-request", response_model=ResetResult)
async def reset_request(body: ResetRequest, session: AsyncSession = Depends(get_session)) -> ResetResult:
    """Issue a single-use 6-digit reset code. To avoid account enumeration the
    response is uniform when the account is unknown. With an email provider the
    code is emailed; without one (this deployment) it is returned on screen as a
    fallback — the same pattern as the provisioning OTP."""
    row = (
        await session.execute(
            text("SELECT id FROM app_user WHERE (username = :i OR email = :i) AND is_active"),
            {"i": body.identifier},
        )
    ).mappings().first()
    if row is None:
        return ResetResult(sent=True, delivery="email")
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=60)
    await session.execute(
        text("INSERT INTO password_reset_codes (user_id, code_hash, expires_at) VALUES (:u, :h, :e)"),
        {"u": str(row["id"]), "h": hash_password(code), "e": expires},
    )
    await audit.record_event(
        session, actor_id=str(row["id"]), action="password_reset_request",
        entity_type="app_user", entity_id=str(row["id"]), payload={},
    )
    await session.commit()
    return ResetResult(sent=True, delivery="shown", code=code)


@router.post("/reset-confirm", response_model=UserOut)
async def reset_confirm(body: ResetConfirm, session: AsyncSession = Depends(get_session)) -> UserOut:
    if len(body.new_password) < 10:
        raise HTTPException(status_code=422, detail="new password must be at least 10 characters")
    row = (
        await session.execute(text(_USER_SELECT + "WHERE (u.username = :i OR u.email = :i)"), {"i": body.identifier})
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=400, detail="invalid code")
    codes = (
        await session.execute(
            text("SELECT id, code_hash FROM password_reset_codes WHERE user_id = :u AND used = FALSE "
                 "AND expires_at > now() ORDER BY created_at DESC LIMIT 5"),
            {"u": str(row["id"])},
        )
    ).mappings().all()
    match = next((c["id"] for c in codes if verify_password(body.code, c["code_hash"])), None)
    if match is None:
        raise HTTPException(status_code=400, detail="invalid or expired code")
    await session.execute(text("UPDATE password_reset_codes SET used = TRUE WHERE id = :id"), {"id": str(match)})
    await session.execute(
        text("UPDATE app_user SET password_hash = :h, must_change_password = FALSE, password_set_at = now(), "
             "failed_login_count = 0, locked_until = NULL WHERE id = :u"),
        {"h": hash_password(body.new_password), "u": str(row["id"])},
    )
    await audit.record_event(
        session, actor_id=str(row["id"]), action="password_reset_confirm",
        entity_type="app_user", entity_id=str(row["id"]), payload={},
    )
    await session.commit()
    return _user_out(row)


# ── Admin account lifecycle (list / role / activate / reset) ────────────────
def _admin_user(r) -> AdminUserOut:
    return AdminUserOut(
        id=str(r["id"]), username=r["username"], full_name=r["full_name"], role=r["role"],
        email=r["email"], dept_id=str(r["dept_id"]) if r["dept_id"] else None, dept_key=r["dept_key"],
        is_active=bool(r["is_active"]), cross_department=bool(r["cross_department"]),
        must_change_password=bool(r["must_change_password"]), last_login_at=r["last_login_at"],
    )


_ADMIN_USER_SELECT = (
    "SELECT u.id, u.username, u.full_name, u.role, u.email, u.dept_id, u.is_active, "
    "u.cross_department, u.must_change_password, u.last_login_at, d.key AS dept_key "
    "FROM app_user u LEFT JOIN planner_department d ON d.id = u.dept_id "
)


@router.get("/users", response_model=list[AdminUserOut])
async def admin_list_users(
    actor: CurrentUser = Depends(require_role("admin", "executive", "hod")),
    session: AsyncSession = Depends(get_session),
) -> list[AdminUserOut]:
    where, params = "", {}
    if actor.role == "hod":                 # HODs see only their own department
        where = "WHERE u.dept_id = :d "
        params["d"] = actor.dept_id
    rows = (
        await session.execute(text(_ADMIN_USER_SELECT + where + "ORDER BY u.is_active DESC, u.full_name"), params)
    ).mappings().all()
    return [_admin_user(r) for r in rows]


async def _reload_admin_user(session: AsyncSession, uid: str) -> AdminUserOut:
    r = (await session.execute(text(_ADMIN_USER_SELECT + "WHERE u.id = :id"), {"id": uid})).mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="user not found")
    return _admin_user(r)


@router.patch("/users/{uid}/role", response_model=AdminUserOut)
async def admin_change_role(
    uid: str, body: RoleChange,
    actor: CurrentUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> AdminUserOut:
    if body.role not in _ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {sorted(_ROLES)}")
    res = await session.execute(
        text("UPDATE app_user SET role = :r WHERE id = :id RETURNING id"), {"r": body.role, "id": uid})
    if res.first() is None:
        raise HTTPException(status_code=404, detail="user not found")
    await audit.record_event(
        session, actor_id=actor.id, action="change_role", entity_type="app_user",
        entity_id=uid, payload={"role": body.role},
    )
    await session.commit()
    return await _reload_admin_user(session, uid)


@router.post("/users/{uid}/active", response_model=AdminUserOut)
async def admin_set_active(
    uid: str, body: ActiveChange,
    actor: CurrentUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> AdminUserOut:
    if uid == actor.id and not body.active:
        raise HTTPException(status_code=400, detail="you cannot deactivate your own account")
    res = await session.execute(
        text("UPDATE app_user SET is_active = :a WHERE id = :id RETURNING id"), {"a": body.active, "id": uid})
    if res.first() is None:
        raise HTTPException(status_code=404, detail="user not found")
    await audit.record_event(
        session, actor_id=actor.id, action="set_active", entity_type="app_user",
        entity_id=uid, payload={"active": body.active},
    )
    await session.commit()
    return await _reload_admin_user(session, uid)


@router.post("/users/{uid}/reset-password", response_model=ProvisionResult)
async def admin_reset_password(
    uid: str,
    actor: CurrentUser = Depends(require_role("admin", "executive", "hod")),
    session: AsyncSession = Depends(get_session),
) -> ProvisionResult:
    """Issue a fresh one-time password to an existing user (admin/HOD-driven reset),
    scoped by the same hierarchy as provisioning. The user must change it on next login."""
    target = (
        await session.execute(text("SELECT id, username, role, dept_id FROM app_user WHERE id = :id"), {"id": uid})
    ).mappings().first()
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    err = _provision_error(actor, target["role"], str(target["dept_id"]) if target["dept_id"] else None, False)
    if err is not None:
        raise HTTPException(status_code=403, detail=err)
    otp = secrets.token_urlsafe(9)
    await session.execute(
        text("UPDATE app_user SET password_hash = :h, must_change_password = TRUE, password_set_at = now(), "
             "failed_login_count = 0, locked_until = NULL WHERE id = :id"),
        {"h": hash_password(otp), "id": uid},
    )
    await audit.record_event(
        session, actor_id=actor.id, action="admin_reset_password", entity_type="app_user",
        entity_id=uid, payload={"username": target["username"]},
    )
    await session.commit()
    return ProvisionResult(
        id=uid, username=target["username"], role=target["role"], temp_password=otp,
        expires_hours=get_settings().otp_ttl_hours,
    )
