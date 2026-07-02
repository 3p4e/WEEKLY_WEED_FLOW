"""Auth dependencies: current user (re-read from DB) + role guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import admin_pool
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(cred.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    # Source of truth is the DB, not the JWT claim — a stale claim can't escalate.
    row = await admin_pool().fetchrow(
        "SELECT id, org_id, username, full_name, role, department_id, function_role,"
        "       is_active, must_change_password FROM profiles WHERE id=$1 AND is_deleted=false",
        payload["sub"],
    )
    if row is None or not row["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account inactive")
    return dict(row)


async def require_password_set(user: dict = Depends(get_current_user)) -> dict:
    """Block the app until a first-login password change is done."""
    if user["must_change_password"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password change required")
    return user


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
