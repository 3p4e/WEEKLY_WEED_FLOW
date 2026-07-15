"""Phase-1 notifications: events + inbox fan-out + feed.

Pins the design rules from docs/RESEARCH-NOTIFICATIONS-2026-07.md:
participation-based recipients, hard self-notify suppression, coalescing of
repeated identical events, recipient-scoped RLS on the inbox, creation as a
feed-only event (no recipients), and the read/done lifecycle driving the
server-computed unread count.
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


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
