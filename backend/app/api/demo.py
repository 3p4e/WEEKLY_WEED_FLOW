"""Public live-demo endpoints.

POST /demo/start — no auth. Wipes + re-seeds the demo org from the requested
cast and returns a short-lived session token for the cast's ADMIN. Disabled
unless settings.demo_enabled (404 — the feature simply doesn't exist where it
isn't switched on; production keeps the default False).

POST /demo/exit — demo token required. Wipes the org again (re-seed is
deferred to the next start). Belt-and-braces: an abandoned tab is healed by
the next visitor's start-reset anyway.

No password ever leaves the server: demo profiles carry an unusable random
hash and the token is minted directly. The token is org-pinned to the demo
org, so RLS confines every request it makes exactly like any real tenant.
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import demo_org
from app.config import settings
from app.deps import get_current_user
from app.security import create_access_token

router = APIRouter(prefix="/demo", tags=["demo"])

# Per-IP start throttle: a reset is a heavy DB operation; nobody legitimate
# starts the demo more than a few times in five minutes. In-process, same
# trade-off as auth.py's login limiter (single replica).
_WINDOW_S = 300
_MAX_STARTS_PER_IP = 3
_starts: dict[str, list[float]] = {}


def _throttle(ip: str) -> None:
    now = time.monotonic()
    log = [t for t in _starts.get(ip, []) if now - t < _WINDOW_S]
    if len(log) >= _MAX_STARTS_PER_IP:
        raise HTTPException(429, "Too many demo starts — try again in a few minutes")
    log.append(now)
    _starts[ip] = log
    if len(_starts) > 512:  # bounded memory, same GC style as auth.py
        for k in [k for k, v in _starts.items() if not v or now - v[-1] > _WINDOW_S]:
            _starts.pop(k, None)


class StartIn(BaseModel):
    cast: str | None = None


@router.post("/start")
async def start_demo(body: StartIn, request: Request):
    if not settings.demo_enabled:
        raise HTTPException(404, "Not found")
    _throttle(request.client.host if request.client else "unknown")
    cast = body.cast if body.cast in demo_org.CASTS else demo_org.DEFAULT_CAST
    admin = await demo_org.reset_demo_org(cast)
    pwv = admin["password_set_at"].isoformat() if admin["password_set_at"] else None
    token = create_access_token(
        str(admin["id"]), admin["role"], str(admin["org_id"]),
        password_set_at=pwv, days=1)   # a demo day, not the 15-min default
    return {
        "access_token": token, "token_type": "bearer", "cast": cast,
        "user": {
            "id": str(admin["id"]), "username": admin["username"],
            "full_name": admin["full_name"], "role": admin["role"],
            "department_id": None, "function_role": "System Administrator",
            "must_change_password": False,
        },
    }


@router.post("/exit")
async def exit_demo(user: dict = Depends(get_current_user)):
    if not settings.demo_enabled:
        raise HTTPException(404, "Not found")
    demo_id = await demo_org.get_demo_org_id()
    if demo_id is None or str(user["org_id"]) != str(demo_id):
        raise HTTPException(403, "Not a demo session")
    await demo_org.wipe_demo_org(demo_id)
    return {"ok": True}
