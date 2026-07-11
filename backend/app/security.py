"""Password hashing (bcrypt) + JWT mint/verify."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

# A fixed hash to verify against on a login miss (unknown/inactive user), so
# the response takes roughly the same time whether or not the identifier
# exists — otherwise skipping bcrypt entirely on a miss is a timing
# side-channel an attacker can use to enumerate valid usernames.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing-safety-only", bcrypt.gensalt())


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str | None) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), (h or _DUMMY_HASH.decode("utf-8")).encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    sub: str, role: str, org_id: str, *, password_set_at: str | None = None, days: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(days=days) if days else timedelta(minutes=settings.access_token_expire_minutes))
    # pwv ("password version") pins the token to the password that was
    # current when it was minted — a later password change invalidates
    # every token minted before it, since decode_token's caller re-checks
    # this against the live profiles.password_set_at.
    payload = {"sub": sub, "role": role, "org_id": org_id, "pwv": password_set_at, "iat": now, "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    # PyJWT (python-jose was unmaintained). algorithms is pinned to the single
    # configured value so an attacker-chosen `alg` header is never honored;
    # InvalidTokenError is the base of every PyJWT validation failure
    # (bad signature, expired, malformed).
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.InvalidTokenError:
        return None
