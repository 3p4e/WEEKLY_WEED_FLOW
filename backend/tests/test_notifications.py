"""Phase-1 notifications: events + inbox fan-out + feed.

Pins the design rules from docs/RESEARCH-NOTIFICATIONS-2026-07.md:
participation-based recipients, hard self-notify suppression, coalescing of
repeated identical events, recipient-scoped RLS on the inbox, creation as a
feed-only event (no recipients), and the read/done lifecycle driving the
server-computed unread count.
"""
import logging
from app.worktime import facility_today
import uuid

from tests.conftest import create_user, login_and_set_password
from app.db import rls, tasks_admin_pool
from app.notify import safe_emit


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def test_one_bad_recipient_is_logged_and_skipped_not_fatal(org, caplog):
    """A failing recipient must cost exactly that recipient.

    emit() used to catch only UniqueViolation, so any OTHER per-recipient error
    (here a malformed uuid) propagated out and — through safe_emit's outer
    savepoint — rolled back the EVENT itself along with every recipient already
    inserted. Migration 0032's own comment documents the opposite intention.
    The per-recipient savepoint has already undone just the bad INSERT, so the
    transaction is healthy and the fan-out continues.

    Pins all three properties: the event survives, the good recipient still
    gets their notification, and the failure is logged rather than swallowed."""
    actor = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"}
    good = str(uuid.uuid4())
    caplog.set_level(logging.WARNING, logger="app.notify")
    async with rls(actor) as c:
        ev_id = await safe_emit(
            c, actor, verb="assigned", object_type="task",
            object_id="00000000-0000-0000-0000-000000000000",
            # bad one FIRST: if it aborted the fan-out, `good` would never be
            # reached and the row count below would be 0.
            recipients=[("not-a-uuid", "assigned"), (good, "assigned")],
        )
    assert ev_id is not None, "one bad recipient must not roll back the event"
    delivered = await tasks_admin_pool().fetchval(
        "SELECT count(*) FROM notifications WHERE event_id=$1 AND recipient_id=$2",
        ev_id, good)
    assert delivered == 1, "the good recipient must still be notified"
    assert any("fan-out failed for recipient not-a-uuid" in r.message
               for r in caplog.records), "the skipped recipient must be logged"


async def test_assign_notifies_assignee_not_actor(client, admin_headers):
    target, th = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Notify me"}, headers=admin_headers)
    tid = r.json()["id"]
    assert (await client.post(f"/tasks/{tid}/assignees",
                              json={"user_id": target["id"]}, headers=admin_headers)).status_code == 201
    # assignee sees it, with the reason label
    inbox = (await client.get("/notifications", headers=th)).json()
    assert any(n["reason"] == "assigned" and n["task_id"] == tid for n in inbox)
    # the acting admin was NOT notified about their own action
    mine = (await client.get("/notifications", headers=admin_headers)).json()
    assert not any(n["task_id"] == tid and n["reason"] == "assigned" for n in mine)


async def test_status_change_notifies_participants_and_coalesces(client, admin_headers):
    owner, oh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Status watch"}, headers=admin_headers)
    tid = r.json()["id"]
    # give the task to the user so they're a participant, then admin flaps status twice
    await client.patch(f"/tasks/{tid}", json={"status": "ongoing"}, headers=admin_headers)  # pre-ownership change
    assert (await client.post(f"/tasks/{tid}/assignees",
                              json={"user_id": owner["id"]}, headers=admin_headers)).status_code == 201
    await client.patch(f"/tasks/{tid}", json={"status": "review"}, headers=admin_headers)
    await client.patch(f"/tasks/{tid}", json={"status": "stuck"}, headers=admin_headers)
    inbox = (await client.get("/notifications", headers=oh)).json()
    status_rows = [n for n in inbox if n["task_id"] == tid and n["reason"] == "status"]
    # two changes while unread → coalesced to ONE open row
    assert len(status_rows) == 1, status_rows


async def test_comment_notifies_owner(client, admin_headers):
    owner, oh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Commented"}, headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": owner["id"]}, headers=admin_headers)
    # clear the assignment notification so only the comment remains unread
    await client.post("/notifications/read-all", headers=oh)
    assert (await client.post(f"/tasks/{tid}/comments",
                              json={"content": "please review"}, headers=admin_headers)).status_code == 201
    unread = (await client.get("/notifications?unread=true", headers=oh)).json()
    assert any(n["reason"] == "comment" and n["params"].get("preview") == "please review" for n in unread)


async def test_unread_count_and_lifecycle(client, admin_headers):
    u, uh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Lifecycle"}, headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": u["id"]}, headers=admin_headers)
    assert (await client.get("/notifications/unread-count", headers=uh)).json()["unread"] >= 1
    inbox = (await client.get("/notifications", headers=uh)).json()
    nid = inbox[0]["id"]
    assert (await client.post(f"/notifications/{nid}/read", headers=uh)).status_code == 200
    assert (await client.post(f"/notifications/{nid}/done", headers=uh)).status_code == 200
    # done rows leave the inbox
    assert not any(n["id"] == nid for n in (await client.get("/notifications", headers=uh)).json())
    assert (await client.post("/notifications/read-all", headers=uh)).status_code == 200
    assert (await client.get("/notifications/unread-count", headers=uh)).json()["unread"] == 0


async def test_inbox_is_recipient_scoped(client, admin_headers):
    a, ah = await _actor(client, admin_headers)
    b, bh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "A only"}, headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": a["id"]}, headers=admin_headers)
    # B sees nothing of A's inbox (RLS notif_select) and can't mark A's row
    b_inbox = (await client.get("/notifications", headers=bh)).json()
    assert not any(n["task_id"] == tid for n in b_inbox)
    a_row = next(n for n in (await client.get("/notifications", headers=ah)).json() if n["task_id"] == tid)
    assert (await client.post(f"/notifications/{a_row['id']}/read", headers=bh)).status_code == 404


async def test_creation_is_feed_only(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Feed only creature"}, headers=admin_headers)
    tid = r.json()["id"]
    feed = (await client.get("/activity", headers=admin_headers)).json()
    assert any(e["verb"] == "created" and e["task_id"] == tid for e in feed)
    # ...and notified nobody (org has only admin + prior test users; check admin)
    inbox = (await client.get("/notifications", headers=admin_headers)).json()
    assert not any(n["task_id"] == tid for n in inbox)


async def test_unassign_notifies_the_ex_assignee(client, admin_headers):
    target, th = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Take-back"}, headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": target["id"]}, headers=admin_headers)
    await client.post("/notifications/read-all", headers=th)
    assert (await client.delete(f"/tasks/{tid}/assignees/{target['id']}",
                                headers=admin_headers)).status_code == 200
    unread = (await client.get("/notifications?unread=true", headers=th)).json()
    assert any(n["verb"] == "unassigned" and n["task_id"] == tid for n in unread)


async def test_mention_in_comment_notifies_with_mentioned_reason(client, admin_headers):
    """A mention notifies a no-stake bystander only when they can actually see
    the task (same department). A USER in another department must NOT receive
    the notification — its title+preview would leak a task that 404s for them."""
    dept = (await client.post("/departments", json={"code": "mn_home", "name": "Mention Home"},
                              headers=admin_headers)).json()
    other = (await client.post("/departments", json={"code": "mn_away", "name": "Mention Away"},
                               headers=admin_headers)).json()
    bu, botp = await create_user(client, admin_headers, department_id=dept["id"])
    bh = {"Authorization": f"Bearer {await login_and_set_password(client, bu['username'], botp)}"}
    ou, ootp = await create_user(client, admin_headers, department_id=other["id"])
    oh = {"Authorization": f"Bearer {await login_and_set_password(client, ou['username'], ootp)}"}
    r = await client.post("/tasks", json={"title": "Mention target", "department_id": dept["id"]},
                          headers=admin_headers)
    tid = r.json()["id"]
    # neither has a participation stake — only the @mention reaches them
    assert (await client.post(f"/tasks/{tid}/comments",
                              json={"content": f"ping @{bu['username']} and @{ou['username']}"},
                              headers=admin_headers)).status_code == 201
    inbox = (await client.get("/notifications", headers=bh)).json()
    row = next(n for n in inbox if n["task_id"] == tid)
    assert row["reason"] == "mentioned"
    # the cross-department USER gets nothing — the leak is closed
    out_inbox = (await client.get("/notifications", headers=oh)).json()
    assert not any(n["task_id"] == tid for n in out_inbox)


async def test_due_scan_notifies_assignee_and_manager(client, admin_headers):
    from datetime import date, timedelta

    from app.duescan import run_for_org

    from app.db import users_admin_pool

    me = (await client.get("/auth/me", headers=admin_headers)).json()
    org_id = await users_admin_pool().fetchval(
        "SELECT org_id FROM profiles WHERE id=$1::uuid", me["id"])
    admin = {"id": me["id"], "org_id": org_id, "role": me["role"]}
    dept = (await client.post("/departments", json={"code": "due_d1", "name": "Due D1"},
                              headers=admin_headers)).json()
    worker, wh = await _actor(client, admin_headers)
    mgr, mh = await _actor(client, admin_headers, role="QC_MGR")
    await client.patch(f"/auth/users/{mgr['id']}", json={"department_id": dept["id"]},
                       headers=admin_headers)
    today = facility_today()
    r1 = await client.post("/tasks", json={"title": "Due today", "department_id": dept["id"],
                                           "due_date": today.isoformat()}, headers=admin_headers)
    r2 = await client.post("/tasks", json={"title": "Late", "department_id": dept["id"],
                                           "due_date": (today - timedelta(days=3)).isoformat()},
                           headers=admin_headers)
    for tid in (r1.json()["id"], r2.json()["id"]):
        await client.post(f"/tasks/{tid}/assignees", json={"user_id": worker["id"]},
                          headers=admin_headers)
    counts = await run_for_org(admin, today)
    assert counts["due_soon"] >= 1 and counts["overdue"] >= 1
    inbox = (await client.get("/notifications", headers=wh)).json()
    due_rows = [n for n in inbox if n["reason"] == "due"]
    verbs = {n["verb"] for n in due_rows if n["task_id"] in (r1.json()["id"], r2.json()["id"])}
    assert verbs == {"due_soon", "overdue"}
    # the dept manager hears about the OVERDUE one only
    m_inbox = (await client.get("/notifications", headers=mh)).json()
    m_verbs = {n["verb"] for n in m_inbox if n["reason"] == "due"
               and n["task_id"] in (r1.json()["id"], r2.json()["id"])}
    assert m_verbs == {"overdue"}
    # idempotent within the day: a second run emits nothing new
    again = await run_for_org(admin, today)
    assert again == {"due_soon": 0, "overdue": 0}


# ── TMS T2: reason-filter regex kept in lockstep with the DB CHECK ──────────
async def test_inbox_reason_filter_accepts_capa_and_validation_stuck(client, admin_headers):
    """Regression: migration 0016 widened notifications.reason's CHECK to
    include capa_stuck/validation_stuck for the canned automation rules, but
    the /notifications query-param validator's regex was never updated —
    filtering by either value 422'd even though the DB (and automation.py)
    both accept them."""
    for reason in ("capa_stuck", "validation_stuck", "assigned", "due", "report"):
        r = await client.get(f"/notifications?reason={reason}", headers=admin_headers)
        assert r.status_code == 200, (reason, r.text)
    r = await client.get("/notifications?reason=not_a_real_reason", headers=admin_headers)
    assert r.status_code == 422


# ── TMS T2: in-app team digest ──────────────────────────────────────────────
async def test_digest_counts_recent_events_by_verb(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Digest smoke task"}, headers=admin_headers)
    assert r.status_code == 201
    task_id = r.json()["id"]
    await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=admin_headers)

    daily = (await client.get("/notifications/digest?window=daily", headers=admin_headers)).json()
    assert daily["window"] == "daily"
    verbs = {v["verb"] for v in daily["by_verb"]}
    assert "created" in verbs and "status_changed" in verbs
    assert daily["total"] >= 2
    assert any(e["task_id"] == task_id for e in daily["recent"])

    weekly = (await client.get("/notifications/digest?window=weekly", headers=admin_headers)).json()
    assert weekly["window"] == "weekly"
    assert weekly["total"] >= daily["total"]  # weekly window is a superset

    r = await client.get("/notifications/digest?window=monthly", headers=admin_headers)
    assert r.status_code == 422
