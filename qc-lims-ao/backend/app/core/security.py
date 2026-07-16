"""
Authentication and authorization utilities.

- Password hashing with passlib bcrypt
- JWT token creation and decoding with python-jose
- Role-based access control dependencies
- Current user extraction from JWT

EU GMP Annex 11 requires two-component electronic signatures.
21 CFR Part 11 §11.200 mandates two distinct identification components.
"""

from datetime import datetime, timedelta, timezone
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db


class Role(StrEnum):
    """User roles for role-based access control."""

    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    QC_ANALYST = "QC_ANALYST"
    QC_REVIEWER = "QC_REVIEWER"
    QC_MANAGER = "QC_MANAGER"
    QP = "QP"  # Qualified Person (EU GMP)
    QA_AUDITOR = "QA_AUDITOR"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload to encode (must include 'sub' for user ID).
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and validate a JWT access token.

    Returns:
        Payload dict if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Dependency that extracts the current authenticated user from the JWT.

    Raises 401 if token is invalid or user is not found/active.
    """
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    from app.models.user import User  # deferred import to avoid circular

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

class require_role:
    """
    Dependency factory for role-based access control.

    Usage:
        @router.post("/samples")
        async def create_sample(
            current_user = Depends(require_role([Role.QC_ANALYST, Role.QC_MANAGER]))
        ):
            ...
    """

    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = set(allowed_roles)

    async def __call__(
        self, current_user=Depends(get_current_user)
    ):
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role}' not authorized. "
                    f"Required: {[r.value for r in self.allowed_roles]}"
                ),
            )
        return current_user
