"""app/automation.py — canned automation rules on task status transitions.

A deliberately small, FIXED rule set — not a user-configurable rule builder
(that's future scope, see docs/MASS-WEED-IMPLEMENTATION-SPEC.md's "automations,
rule-builder" line). Certain task types going 'stuck' are quality-relevant
regardless of who is assigned, so Quality should hear about it even without a
participation stake: CAPA work reaches QA + the Qualified Person; validation
work reaches the Qualified Person.

Recipients from these rules are listed BEFORE participant recipients in the
emit() call (same "first reason wins" dedup pattern @mentions uses in
collab.py) — a quality manager who also happens to be assigned still gets the
more specific reason, not the generic 'status' one.
"""
from app.db import rls_users

# (task_type, new_status) -> (roles to notify, the per-recipient reason string)
_CANNED_RULES = {
    ("capa", "stuck"): (("QA_MGR", "QP"), "capa_stuck"),
    ("validation", "stuck"): (("QP",), "validation_stuck"),
}


async def canned_recipients(user: dict, task_type: str, new_status: str) -> list[tuple[str, str]]:
    """Extra reviewers a canned rule wants pinged for this transition,
    independent of task participation. Empty list when no rule matches."""
    rule = _CANNED_RULES.get((task_type, new_status))
    if not rule:
        return []
    roles, reason = rule
    async with rls_users(user) as uc:
        rows = await uc.fetch(
            "SELECT id FROM profiles WHERE org_id=$1 AND is_deleted=false AND is_active"
            " AND role = ANY($2::text[])",
            user["org_id"], list(roles))
    return [(str(r["id"]), reason) for r in rows]
