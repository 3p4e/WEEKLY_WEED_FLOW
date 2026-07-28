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


# bcrypt hashes at most the first 72 BYTES of its input and silently ignores
# the rest — 4.2.1 does not raise, it truncates. The API accepts passwords up
# to 256 characters (auth.py's `Field(max_length=256)`), so without this a user
# who sets a long passphrase authenticates on its first 72 bytes alone, while
# believing the whole thing is checked.
#
# Bytes, not characters, and that matters here: this is a bilingual MK/EN
# application, and Cyrillic costs 2 bytes per character in UTF-8 — a
# 40-character Macedonian passphrase is already over the limit. Not theoretical.
BCRYPT_MAX_BYTES = 72


class PasswordTooLong(ValueError):
    """Raised by hash_password for input bcrypt could not hash in full."""


def hash_password(p: str) -> str:
    pw = p.encode("utf-8")
    if len(pw) > BCRYPT_MAX_BYTES:
        raise PasswordTooLong(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes "
            "(non-Latin characters cost more than one byte each)"
        )
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str | None) -> bool:
    # Deliberately NOT bounded the way hash_password is. Any password set
    # before that bound existed was stored as its own 72-byte truncation, and
    # rejecting the full input here would lock those accounts out of an app
    # they can still legitimately sign in to. bcrypt truncates on this path
    # exactly as it did when the hash was written, so they keep working and are
    # told to shorten it the next time they set one.
    try:
        return bcrypt.checkpw(p.encode("utf-8"), (h or _DUMMY_HASH.decode("utf-8")).encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    sub: str, role: str, org_id: str, *, password_set_at: str | None = None, days: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(days=days) if days is not None else timedelta(minutes=settings.access_token_expire_minutes))
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
