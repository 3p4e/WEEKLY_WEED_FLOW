"""notify.py — activity events + inbox fan-out.

Design per docs/RESEARCH-NOTIFICATIONS-2026-07.md. emit() appends ONE
actor-verb-object event row and fans out per-recipient inbox notifications in
the same transaction/connection the caller is already using, so awareness
data commits (or rolls back) atomically with the work write it describes.

Rules enforced HERE (not left to callers):
  - never notify the actor about their own action (hard guard);
  - recipients are de-duplicated;
  - repeated identical events coalesce onto the open unread row via the
    partial unique index + ON CONFLICT DO NOTHING;
  - params carries STRUCTURED values only — the client renders the EN/МК
    sentence at display time (AS2 language-map / FCM key+params pattern).

Every call site wraps emit() in try/except: a notification failure must
never break the work operation it rides on. An event with NO recipients is
valid and common — it feeds the shared activity stream without pinging
anyone (e.g. task creation: feed-only by design, per Slack/Linear defaults).
"""


async def participants(c, task_id: str) -> set:
    """Everyone with a participation stake in a task: creator, owner,
    assignees, prior commenters. (The convergent Linear/GitHub/Jira default
    recipient rule.)"""
    rows = await c.fetch(
        "SELECT created_by AS u FROM tasks WHERE id=$1"
        " UNION SELECT user_id FROM tasks WHERE id=$1"
        " UNION SELECT user_id FROM task_assignees WHERE task_id=$1"
        " UNION SELECT user_id FROM task_comments WHERE task_id=$1",
        task_id)
    return {str(r["u"]) for r in rows if r["u"]}


async def emit(c, user: dict, *, verb: str, object_type: str, object_id,
               recipients=(), task_id=None, department_id=None, params=None):
    """Append an event; fan out notifications. recipients = iterable of
    (user_id, reason). Returns the event id."""
    ev_id = await c.fetchval(
        "INSERT INTO events(org_id, actor_id, verb, object_type, object_id,"
        " task_id, department_id, params) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)"
        " RETURNING id",
        user["org_id"], user["id"], verb, object_type, str(object_id),
        task_id, department_id, params or {})
    seen = set()
    me = str(user["id"])
    for uid, reason in recipients:
        uid = str(uid) if uid else ""
        if not uid or uid == me or uid in seen:
            continue
        seen.add(uid)
        # Plain INSERT + savepoint, NOT ON CONFLICT: with an ON CONFLICT
        # arbiter Postgres additionally enforces the table's SELECT policy
        # against the row, and notif_select is recipient-only — the acting
        # user inserting a row for SOMEONE ELSE would always violate it.
        # The partial unique index still enforces coalescing; a duplicate
        # while an unread row is open just rolls back this savepoint.
        try:
            async with c.transaction():
                await c.execute(
                    "INSERT INTO notifications(org_id, recipient_id, event_id, reason, coalesce_key)"
                    " VALUES ($1,$2,$3,$4,$5)",
                    user["org_id"], uid, ev_id, reason, f"{verb}:{object_type}:{object_id}")
        except Exception:  # unique_violation → already an open identical row
            pass
    return ev_id
