# docengine.app.security — single shared-secret header gate.
# The service is internal-only (no published ports); the WWF backend proxy is
# the sole caller and injects X-API-Key from its own env. Identical contract
# to the Phase-1 qms-api so the proxy code needs no special-casing.
import hmac

from fastapi import Header, HTTPException

from .config import settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.api_key:
        # unconfigured service refuses every call rather than running open
        raise HTTPException(status_code=503, detail="DocEngine not configured")
    # Compared as BYTES. compare_digest(str, str) raises TypeError on any
    # non-ASCII character (Starlette decodes headers as latin-1), which turned
    # a bad key with an accented letter into a 500 and a traceback instead of
    # a 401 (review 2026-09-27, DI-17).
    if not hmac.compare_digest(x_api_key.encode("utf-8"), settings.api_key.encode("utf-8")):
        raise HTTPException(status_code=401, detail="bad api key")
