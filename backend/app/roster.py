"""App-side name resolution across the users↔tasks database boundary.

The tasks database stores bare profile uuids (user_id, created_by, ...) with
no FK — profiles live in the other database. Anywhere the API used to
LEFT JOIN profiles for a display name now fetches the org roster here and
merges in Python. Deliberately NO is_active/is_deleted filter: historical
authors and deactivated accounts must still resolve to their names on old
comments, tasks and audit rows (the /auth/directory endpoint is where the
active-only rule lives)."""
import time

from app.db import rls_users

# Wave 3 audit (Low, "scaling watch-point, not a correctness bug"): every
# current call site (comments/assignees in collab.py, hours-by-person in
# reports.py, PDF/HTML export + the AI dependency-advisor context in
# documents.py/ai.py) fetches the roster at most ONCE per request, purely to
# resolve ids to display names — never for an authorization decision. So a
# per-request cache would not help today (nothing to dedupe within one
# request), and a cache with real invalidation (someone adds/removes a person
# and every held copy must know) is real machinery this is not worth for a Low
# finding. What IS a cheap, safe win: a short wall-clock TTL, org-scoped,
# in-process. It needs no invalidation logic at all — entries simply expire —
# and it still pays off the actual growth case (many concurrent requests
# against the same org, e.g. everyone loading their board at shift start) by
# letting them share one DB round trip instead of each doing their own. The
# cost is a few seconds of staleness on a brand-new/renamed/removed person's
# display name, which is invisible for what this is used for (nothing here
# gates access — profiles_read RLS already did that on the row read itself).
_TTL_SECONDS = 15.0
_cache: dict[str, tuple[float, dict[str, dict]]] = {}


async def roster(user: dict) -> dict[str, dict]:
    """{profile_id(str): {"username", "full_name"}} for the caller's org.

    Runs on the RLS users pool — the profiles_read policy scopes rows to the
    caller's org, so a cross-org id simply won't resolve (shows as None).
    Served from a short-TTL org-scoped cache when fresh — see the module
    docstring above for why that is safe here."""
    org_id = str(user["org_id"])
    now = time.monotonic()
    cached = _cache.get(org_id)
    if cached is not None and now - cached[0] < _TTL_SECONDS:
        return cached[1]
    async with rls_users(user) as c:
        rows = await c.fetch(
            "SELECT id, username, full_name FROM profiles WHERE org_id=$1", user["org_id"])
    result = {str(r["id"]): {"username": r["username"], "full_name": r["full_name"]} for r in rows}
    _cache[org_id] = (now, result)
    return result


def display_name(roster_map: dict[str, dict], user_id) -> str:
    p = roster_map.get(str(user_id)) if user_id else None
    if not p:
        return "—"
    return p["full_name"] or p["username"] or "—"
