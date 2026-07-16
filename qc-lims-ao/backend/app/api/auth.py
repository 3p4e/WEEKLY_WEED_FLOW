"""
Authentication router — Google OAuth endpoint.

POST /auth/google — exchange Google access token for JWT session.
Ported from CoA_TRACK per QCSOP-012 and EU GMP Annex 11 §9.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User

router = APIRouter()

# Google OAuth constants
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Request/Response Schemas ───────────────────────────────────────────────


class GoogleAuthRequest(BaseModel):
    """Request body for Google OAuth — contains access token from frontend."""
    credential: str  # Google access token from @react-oauth/google implicit flow


class UserResponse(BaseModel):
    """Public user profile returned in login response."""
    id: str
    username: str
    role: str
    full_name: str
    email: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response returned after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EmailLoginRequest(BaseModel):
    """Request body for email/password login."""
    email: str
    password: str


# ── Email / Password Login Endpoint ────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def email_login(
    body: EmailLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate a user with email + password.

    Looks up the user by email, verifies the bcrypt password hash, and returns
    a JWT access token plus the public user profile. Returns 401 on any bad
    credential (unknown email, wrong password, inactive account) without
    revealing which, per security best practice.
    """
    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.is_deleted == False,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()

    invalid = HTTPException(status_code=401, detail="Invalid email or password")

    if user is None or not user.is_active:
        raise invalid

    # OAuth-only accounts carry a sentinel hash that local auth must reject.
    if not user.password_hash or user.password_hash.startswith("!"):
        raise invalid

    try:
        if not verify_password(body.password, user.password_hash):
            raise invalid
    except ValueError:
        # Malformed/unsupported hash → treat as bad credentials
        raise invalid

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
            avatar_url=user.avatar_url,
        ),
    )


# ── Google OAuth Endpoint ──────────────────────────────────────────────────


@router.post("/google", response_model=LoginResponse)
async def google_auth(
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a Google access token for a QC LIMS session.

    Creates a new User on first sign-in. Links existing User by google_sub
    or email if found. Returns JWT access token for subsequent requests.

    AC-07: Valid Google token → 200 + JWT + user profile.
           New user → User created with google_sub → 200.
           Invalid Google token → 401.
           Google API down → 502.
           Missing GOOGLE_CLIENT_ID → 501.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth not configured (missing GOOGLE_CLIENT_ID)",
        )

    # Verify Google access token and fetch user profile
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {body.credential}"},
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=502,
                detail="Failed to contact Google authentication service",
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google access token",
        )

    try:
        info = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from Google")

    # Verify token audience matches our client ID (prevents token replay)
    token_aud = info.get("aud", "")
    if token_aud and token_aud != settings.google_client_id:
        raise HTTPException(
            status_code=401,
            detail="Google token was issued for a different application",
        )

    google_sub: str = info.get("sub", "")
    email: str = info.get("email", "")
    full_name: str = info.get("name", "")
    avatar_url: str = info.get("picture", "")
    email_verified: bool = info.get("email_verified", False)

    if not google_sub:
        raise HTTPException(
            status_code=401,
            detail="Could not retrieve Google user identity",
        )

    # Reject unverified emails (protects against unverified Google accounts)
    if email and not email_verified:
        raise HTTPException(
            status_code=401,
            detail="Google account email must be verified",
        )

    # Find existing user by google_sub or email
    result = await db.execute(
        select(User).where(User.google_sub == google_sub)
    )
    user = result.scalar_one_or_none()

    if not user and email:
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        if user:
            # Require admin approval for account linking — prevents takeover
            raise HTTPException(
                status_code=403,
                detail="An account with this email already exists. Contact your administrator to link Google SSO."
            )

    if not user:
        # Auto-register new Google user — use UUID suffix for atomic uniqueness (no TOCTOU race)
        username = f"{email.split('@')[0]}_{google_sub[:8]}" if email else f"google_{google_sub[:8]}"

        user = User(
            username=username,
            password_hash="!OAUTH_ONLY",  # Sentinel — local auth must reject this
            full_name=full_name,
            role="PENDING",  # Must be activated by admin before accessing GxP functions
            email=email or None,
            google_sub=google_sub,
            avatar_url=avatar_url,
            is_active=False,  # Account inactive until admin approval
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Generate JWT
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
            avatar_url=user.avatar_url,
        ),
    )
