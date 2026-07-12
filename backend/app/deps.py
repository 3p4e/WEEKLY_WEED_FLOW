"""Auth dependencies: current user (re-read from DB) + role guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import users_admin_pool
from app.roles import DEPT_SCOPED_ROLES
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(cred.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    # Source of truth is the DB, not the JWT claim — a stale claim can't escalate.
    row = await users_admin_pool().fetchrow(
        "SELECT id, org_id, username, full_name, role, department_id, function_role,"
        "       is_active, must_change_password, password_set_at FROM profiles"
        " WHERE id=$1 AND is_deleted=false",
        payload["sub"],
    )
    if row is None or not row["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account inactive")
    # A password change bumps password_set_at, invalidating every token
    # minted before it (embedded as the pwv claim) — otherwise a stolen
    # token stays valid for its full lifetime even after the real user
    # rotates their password.
    live_pwv = row["password_set_at"].isoformat() if row["password_set_at"] else None
    if payload.get("pwv") != live_pwv:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalidated by a password change")
    user = dict(row)
    del user["password_set_at"]
    return user


async def require_password_set(user: dict = Depends(get_current_user)) -> dict:
    """Block the app until a first-login password change is done."""
    if user["must_change_password"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password change required")
    return user


def dept_scope(user: dict) -> str | None:
    """The department a DEPT_SCOPED role is confined to, else None (org-wide).

    A scoped manager with no department assigned falls back to org-wide rather
    than an empty app — visibility scoping must never reproduce the
    OWNER-sees-nothing failure mode."""
    if user["role"] in DEPT_SCOPED_ROLES and user["department_id"]:
        return str(user["department_id"])
    return None


def is_dept_scoped_role(user: dict) -> bool:
    """True if the user's ROLE confines them to a single department (managers
    except QP), regardless of whether a department is actually assigned.

    dept_scope() returns None both for genuinely org-wide roles (execs/QP/ADMIN)
    AND for a scoped manager who simply has no department set yet — the two are
    indistinguishable to callers. For the live board/My-Week that conflation is
    fine (a department-less manager falling back to org-wide is the intended
    anti-'OWNER-sees-nothing' behaviour). But sensitive surfaces — the weekly
    GMP document (compile / lock / export the org-wide submitted record) — must
    NOT hand a department-less manager org-wide authority. They use this to tell
    the two apart and refuse instead."""
    return user["role"] in DEPT_SCOPED_ROLES


def require_role(*roles: str):
    # Depends on require_password_set (not get_current_user directly) so a
    # leaked/intercepted one-time password can't be used for role-gated
    # actions (user management, audit trail) before the real user has
    # completed their mandatory first-login password change.
    async def _guard(user: dict = Depends(require_password_set)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return _guard
