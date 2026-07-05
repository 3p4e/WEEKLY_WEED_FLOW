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
from mcp.server.fastmcp import FastMCP
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
mcp.settings.host = "0.0.0.0"
mcp.settings.port = int(os.environ.get("PORT", "8000"))
mcp.settings.streamable_http_path = MCP_PATH

# Tiny in-process rate limit — this tool is called a handful of times a day
# by one person; anything hot is abuse of the (secret) URL.
_WINDOW_S, _MAX_CALLS = 300, 30
_calls: list[float] = []


def _rate_ok() -> bool:
    now = time.monotonic()
    while _calls and now - _calls[0] > _WINDOW_S:
        _calls.pop(0)
    if len(_calls) >= _MAX_CALLS:
        return False
    _calls.append(now)
    return True


@mcp.tool()
async def submit_capture(capture_json: str) -> str:
    """Send a WWF task capture to Weekly Weed Flow.

    Pass the COMPLETE capture object produced by the Master Task-Capture
    Prompt — {"session_meta": {...}, "tasks": [...]} — as a JSON string.
    Returns the import result: how many tasks were created/updated, how many
    work sessions were added, and any skipped entries with reasons.
    Importing the same capture twice is safe (tasks merge by external_ref).
    """
    if not _rate_ok():
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
