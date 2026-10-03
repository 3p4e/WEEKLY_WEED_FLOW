"""WWF capture connector — a minimal remote MCP server for claude.ai/Cowork.

Exposes ONE tool, submit_capture: it takes the wwf-capture JSON a Master
Capture Prompt session produced and forwards it to WWF's /capture/import
with a server-side credential (CAPTURE_IMPORT_TOKEN — valid only on that
route, acting as the configured capture user). The chat side never sees or
holds any WWF credential.

Security model (documented trade-off, see docs/DEPLOY.md): claude.ai custom
connectors speak streamable HTTP to a URL; this server is reachable only at
a secret path (MCP_PATH) behind Traefik TLS, holds a single narrowly-scoped
token, applies a small in-process rate limit, and can only ever do one
thing: import capture-shaped task data for one user. WWF is a non-GMP
planning tool (docs/SCOPE.md).
"""
import json
import os
import time

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

IMPORT_URL = os.environ.get(
    "WWF_IMPORT_URL", "http://weekly_weed_flow-backend-1:8000/capture/import")
TOKEN = os.environ.get("CAPTURE_IMPORT_TOKEN", "")
MCP_PATH = os.environ.get("MCP_PATH", "/mcp")
# The SDK's DNS-rebinding protection rejects any Host header it wasn't told
# about; behind Traefik the Host is the public app hostname.
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "wwf.srv1231216.hstgr.cloud")

mcp = FastMCP(
    "WWF Capture", stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=[PUBLIC_HOST, f"{PUBLIC_HOST}:443", "localhost", "127.0.0.1"],
        allowed_origins=[f"https://{PUBLIC_HOST}"],
    ),
)
# B104 suppressed below: binding all interfaces is correct and required
# INSIDE a container — the process must accept traffic on the container's own
# network namespace, and real exposure is controlled by compose/Traefik, not
# by this bind.
mcp.settings.host = "0.0.0.0"  # nosec B104
mcp.settings.port = int(os.environ.get("PORT", "8000"))
mcp.settings.streamable_http_path = MCP_PATH

# Tiny in-process rate limit — this tool is called a handful of times a day
# by one person; anything hot is abuse of the (secret) URL.
#
# Keyed PER CLIENT ADDRESS, not one global bucket: with one bucket, anyone
# who learned the secret path could burn the whole window and lock the owner
# out for five minutes (review 2026-09-27, DI-22). The address is the first
# X-Forwarded-For hop, which Traefik sets from the real peer; the connector
# is reachable only through Traefik, so the header is trustworthy here. A
# request with no address (a health probe, a unit test) shares one bucket.
_WINDOW_S, _MAX_CALLS = 300, 30
_MAX_BUCKETS = 1024
_calls: dict[str, list[float]] = {}


def _client_key(ctx: Context | None) -> str:
    try:
        req = ctx.request_context.request if ctx is not None else None
    except (AttributeError, ValueError):
        req = None
    if req is None:
        return "-"
    fwd = (req.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if fwd:
        return fwd
    return req.client.host if req.client else "-"


def _rate_ok(key: str = "-") -> bool:
    now = time.monotonic()
    log = _calls.setdefault(key, [])
    while log and now - log[0] > _WINDOW_S:
        log.pop(0)
    if len(log) >= _MAX_CALLS:
        return False
    log.append(now)
    if len(_calls) > _MAX_BUCKETS:  # bounded memory: drop idle buckets
        for k in [k for k, v in _calls.items() if not v or now - v[-1] > _WINDOW_S]:
            _calls.pop(k, None)
    return True


@mcp.tool()
async def submit_capture(capture_json: str, ctx: Context | None = None) -> str:
    """Send a WWF task capture to Weekly Weed Flow.

    Pass the COMPLETE capture object produced by the Master Task-Capture
    Prompt — {"session_meta": {...}, "tasks": [...]} — as a JSON string.
    Returns the import result: how many tasks were created/updated, how many
    work sessions were added, and any skipped entries with reasons.
    Importing the same capture twice is safe (tasks merge by external_ref).
    """
    if not _rate_ok(_client_key(ctx)):
        return "Rate limit exceeded — try again in a few minutes."
    try:
        payload = json.loads(capture_json)
    except json.JSONDecodeError as e:
        return f"capture_json is not valid JSON: {e}"
    if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
        return 'Expected an object with a "tasks" array (the full capture contract).'
    if not TOKEN:
        return "Connector is not configured (missing import token) — use the manual Import box in WWF."
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(IMPORT_URL, json=payload,
                                  headers={"Authorization": f"Bearer {TOKEN}"})
    except Exception as e:
        return f"WWF is unreachable ({type(e).__name__}) — output the capture JSON for manual import instead."
    if r.status_code != 200:
        return f"WWF import failed (HTTP {r.status_code}): {r.text[:300]}"
    d = r.json()
    lines = [f"Imported into WWF: {d.get('created', 0)} created, {d.get('updated', 0)} updated, "
             f"{d.get('sessions_added', 0)} work sessions added."]
    for s in d.get("skipped", []):
        lines.append(f"  skipped {s.get('external_ref')}: {s.get('reason')}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
