"""Password hashing (bcrypt) + JWT mint/verify."""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return _pwd.verify(p, h)
    except ValueError:
        return False


def create_access_token(sub: str, role: str, org_id: str, *, days: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(days=days) if days else timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": sub, "role": role, "org_id": org_id, "iat": now, "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
