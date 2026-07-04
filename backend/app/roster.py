"""App-side name resolution across the users↔tasks database boundary.

The tasks database stores bare profile uuids (user_id, created_by, ...) with
no FK — profiles live in the other database. Anywhere the API used to
LEFT JOIN profiles for a display name now fetches the org roster here and
merges in Python. Deliberately NO is_active/is_deleted filter: historical
authors and deactivated accounts must still resolve to their names on old
comments, tasks and audit rows (the /auth/directory endpoint is where the
active-only rule lives)."""
from app.db import rls_users


async def roster(user: dict) -> dict[str, dict]:
    """{profile_id(str): {"username", "full_name"}} for the caller's org.

    Runs on the RLS users pool — the profiles_read policy scopes rows to the
    caller's org, so a cross-org id simply won't resolve (shows as None)."""
    async with rls_users(user) as c:
        rows = await c.fetch(
            "SELECT id, username, full_name FROM profiles WHERE org_id=$1", user["org_id"])
    return {str(r["id"]): {"username": r["username"], "full_name": r["full_name"]} for r in rows}


def display_name(roster_map: dict[str, dict], user_id) -> str:
    p = roster_map.get(str(user_id)) if user_id else None
    if not p:
        return "—"
    return p["full_name"] or p["username"] or "—"
