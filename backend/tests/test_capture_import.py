"""POST /capture/import — the capture prompt's delivery end. The properties
that matter: idempotency (same payload twice → second run is a no-op),
forward-only status merges, session/link/subtask dedup, owner gating, and
per-task skip (one bad task never aborts the batch)."""
import os

from tests.conftest import create_user, login_and_set_password


def _payload(ref="pp-qc-sop-099", owner=None, **task_over):
    task = {
        "action": "create",
        "external_ref": ref,
        "title": "PP-QC-SOP-099 Test SOP",
        "description": "Drafting the test SOP",
        "status": "ongoing",
        "priority": "high",
        "task_type": "sop",
        "reference_code": "PP-QC-SOP-099",
        "department": "qc",
        "tags": ["sop", "test"],
        "week_start": "2026-07-03",
        "due_date": "2026-07-16",
        "sessions": [
            {"started_at": "2026-07-04T14:00:00", "hours": 2.0,
             "time_estimated": False, "note": "first sitting"},
        ],
        "links": [{"url": "https://drive.google.com/x", "label": "draft", "kind": "drive"}],
        "subtasks": [{"title": "Annex A01", "status": "pending"}],
    }
    if owner:
        task["owner"] = owner
    task.update(task_over)
    return {"session_meta": {"prompt_version": "wwf-capture/v2.1"}, "tasks": [task]}


async def test_import_create_then_idempotent_reimport(client, admin_headers, org):
    r = await client.post("/capture/import", json=_payload(), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and body["updated"] == 0
    assert body["sessions_added"] == 1 and body["skipped"] == []

    # Same payload again: updates the row (forward merge) but adds nothing.
    r = await client.post("/capture/import", json=_payload(), headers=admin_headers)
    body = r.json()
    assert body["created"] == 0 and body["updated"] == 1
    assert body["sessions_added"] == 0

    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    matches = [t for t in r.json() if t.get("external_ref") == "pp-qc-sop-099"]
    assert len(matches) == 1
    t = matches[0]
    assert t["task_type"] == "sop" and t["due_date"] == "2026-07-16"
    assert float(t["session_hours"]) == 2.0
    assert t["subtask_count"] == 1

    # The imported weekend session must be classification-ready.
    r = await client.get(f"/tasks/{t['id']}/sessions", headers=admin_headers)
    s = r.json()[0]
    assert s["classification"] == "weekend" and s["source"] == "capture"


async def test_import_date_only_session(client, admin_headers, org):
    """A session with only started_at — duration genuinely unknown, per the
    capture contract — is legal: it contributes 0 hours but is still recorded
    and classified from its start time."""
    r = await client.post("/capture/import", json=_payload(
        ref="date-only-1",
        sessions=[{"started_at": "2026-07-04T14:00:00", "hours": None,
                   "ended_at": None, "time_estimated": True, "note": "unknown duration"}],
    ), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1 and body["skipped"] == []
    assert body["sessions_added"] == 1

    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    t = next(x for x in r.json() if x.get("external_ref") == "date-only-1")
    assert float(t["session_hours"]) == 0.0

    r = await client.get(f"/tasks/{t['id']}/sessions", headers=admin_headers)
    s = r.json()[0]
    assert s["hours"] == 0.0 and s["classification"] == "weekend"


async def test_import_status_never_regresses(client, admin_headers, org):
    await client.post("/capture/import",
                      json=_payload(ref="reg-1", status="completed", completed_date="2026-07-01"),
                      headers=admin_headers)
    r = await client.post("/capture/import", json=_payload(ref="reg-1", status="ongoing"),
                          headers=admin_headers)
    assert r.json()["updated"] == 1
    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    t = next(x for x in r.json() if x.get("external_ref") == "reg-1")
    assert t["status"] == "completed"


async def test_import_reimport_omitting_priority_type_preserves_them(client, admin_headers, org):
    """H9: priority/task_type used to default to 'medium'/'other' on every
    import, silently downgrading a classification a re-import simply didn't
    mention. A re-import that omits them must merge like every sibling
    field (COALESCE onto the existing row), not stomp it."""
    r = await client.post("/capture/import",
                          json=_payload(ref="preserve-1", priority="critical", task_type="capa"),
                          headers=admin_headers)
    assert r.json()["created"] == 1

    r = await client.post("/capture/import",
                          json=_payload(ref="preserve-1", priority=None, task_type=None),
                          headers=admin_headers)
    assert r.json()["updated"] == 1

    r = await client.get("/tasks?include_archived=true", headers=admin_headers)
    t = next(x for x in r.json() if x.get("external_ref") == "preserve-1")
    assert t["priority"] == "critical" and t["task_type"] == "capa"


async def test_import_owner_gating(client, admin_headers, org):
    """A non-admin can import their own work but not someone else's."""
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/capture/import", json=_payload(ref="own-1", owner=user["username"]),
                          headers=headers)
    assert r.json()["created"] == 1

    r = await client.post("/capture/import", json=_payload(ref="theft-1", owner=org["username"]),
                          headers=headers)
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"][0]["reason"] == "not allowed to import for another owner"

    # ADMIN importing for another owner is allowed.
    r = await client.post("/capture/import", json=_payload(ref="admin-for-user", owner=user["username"]),
                          headers=admin_headers)
    assert r.json()["created"] == 1


async def test_import_bad_task_skipped_batch_continues(client, admin_headers, org):
    payload = _payload(ref="good-1")
    bad = _payload(ref="bad-1", status="working")["tasks"][0]          # invalid enum
    bad2 = _payload(ref="bad-2", owner="nobody_here")["tasks"][0]      # unknown owner
    payload["tasks"] += [bad, bad2]
    r = await client.post("/capture/import", json=payload, headers=admin_headers)
    body = r.json()
    assert body["created"] == 1
    reasons = {s["external_ref"]: s["reason"] for s in body["skipped"]}
    assert "invalid status" in reasons["bad-1"]
    assert "unknown owner" in reasons["bad-2"]


async def test_import_provisions_calendar_week(client, admin_headers, org):
    await client.post("/capture/import", json=_payload(ref="week-1", week_start="2026-06-26"),
                      headers=admin_headers)
    r = await client.get("/weeks", headers=admin_headers)
    assert any(w["starts_on"] <= "2026-06-26" <= w["ends_on"] for w in r.json())


async def test_static_capture_token_acts_as_configured_user(client, admin_headers, org, monkeypatch):
    """The connector path: CAPTURE_IMPORT_TOKEN (only on this route) acts as
    CAPTURE_IMPORT_USER. Wrong token → 401; right token → import lands on
    the configured user; the token opens no other route."""
    user, otp = await create_user(client, admin_headers, full_name="Capture Bot Target")
    token = await login_and_set_password(client, user["username"], otp)
    monkeypatch.setenv("CAPTURE_IMPORT_TOKEN", "test-capture-token-123")
    monkeypatch.setenv("CAPTURE_IMPORT_USER", user["username"])

    r = await client.post("/capture/import", json=_payload(ref="conn-1"),
                          headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401

    r = await client.post("/capture/import", json=_payload(ref="conn-1"),
                          headers={"Authorization": "Bearer test-capture-token-123"})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    # Owner defaulted to the configured capture user, not anyone else.
    hdrs = {"Authorization": f"Bearer {token}"}
    r = await client.get("/tasks?include_archived=true", headers=hdrs)
    assert any(t.get("external_ref") == "conn-1" for t in r.json())

    # The static token is NOT a general credential.
    r = await client.get("/tasks", headers={"Authorization": "Bearer test-capture-token-123"})
    assert r.status_code == 401


async def _two_departments(org):
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC'),($1,'pr','Production')"
        " RETURNING id", org["org_id"])
    return str(rows[0]["id"]), str(rows[1]["id"])


async def test_import_respects_manager_department_scope(client, admin_headers, org):
    """H2 — a dept-scoped manager may import only into their OWN department.

    The endpoint used to resolve the capture's department code and use it
    verbatim, with no scope check at all, so a scoped manager could file work
    into any department just by naming it in the payload — the restriction
    create_task has enforced all along (tasks.py:379-390). Refusal is per task
    (the endpoint's established idiom) so one out-of-scope entry never aborts
    the batch."""
    _qc, pr = await _two_departments(org)
    user, otp = await create_user(client, admin_headers, role="CU_MGR",
                                  full_name="Cultivation Manager", department_id=pr)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    # naming another department is refused …
    r = await client.post("/capture/import", json=_payload(ref="x-dept", department="qc"),
                          headers=headers)
    body = r.json()
    assert body["created"] == 0, body
    assert "outside your department scope" in body["skipped"][0]["reason"], body

    # … an unresolvable code cannot be shown to be theirs, so it is refused too
    r = await client.post("/capture/import", json=_payload(ref="x-unknown", department="nosuchdept"),
                          headers=headers)
    assert r.json()["created"] == 0
    assert "outside your department scope" in r.json()["skipped"][0]["reason"]

    # … their own department is accepted …
    r = await client.post("/capture/import", json=_payload(ref="own-dept", department="pr"),
                          headers=headers)
    assert r.json()["created"] == 1, r.text

    # … and an omitted department defaults to theirs rather than landing
    # unassigned, where their own scoped list could never surface it again.
    r = await client.post("/capture/import", json=_payload(ref="no-dept", department=None),
                          headers=headers)
    assert r.json()["created"] == 1, r.text
    tasks = (await client.get("/tasks?include_archived=true", headers=headers)).json()
    landed = next(t for t in tasks if t.get("external_ref") == "no-dept")
    assert str(landed["department_id"]) == pr
    assert landed["department"] == "pr"          # display column agrees with the id


async def test_import_batch_continues_past_out_of_scope_task(client, admin_headers, org):
    """H2 — the scope refusal is per task, like every other skip reason here."""
    _qc, pr = await _two_departments(org)
    user, otp = await create_user(client, admin_headers, role="CU_MGR", department_id=pr)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    payload = _payload(ref="in-scope", department="pr")
    payload["tasks"].append(_payload(ref="out-of-scope", department="qc")["tasks"][0])
    body = (await client.post("/capture/import", json=payload, headers=headers)).json()
    assert body["created"] == 1
    assert [s["external_ref"] for s in body["skipped"]] == ["out-of-scope"]


async def test_import_update_reauthorizes_against_real_row_not_payload_owner(client, admin_headers, org):
    """IDOR regression — the update-merge branch used to trust the PAYLOAD's
    declared `owner` field and never re-checked the actor against the
    EXISTING row's real user_id/department_id. A dept-scoped manager who
    knew (or could guess) a target task's external_ref could claim
    ownership of it in the payload — passing the naive owner check
    trivially — and silently rewrite a task that belonged to a different
    department and a different real owner.

    The victim task is created by ADMIN (real owner = admin, real
    department = qc). The attacker is a CU_MGR scoped to a DIFFERENT
    department (pr) who is neither the row's owner nor an assignee. Their
    import declares owner=themselves (so the old owner check passed) and
    department=their own scope (so the old payload-department check also
    passed) — only a re-check against the row's REAL data can catch this."""
    qc, pr = await _two_departments(org)
    attacker, otp = await create_user(client, admin_headers, role="CU_MGR",
                                      full_name="Cultivation Manager", department_id=pr)
    attacker_token = await login_and_set_password(client, attacker["username"], otp)
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    # Victim task: real owner = admin, real department = qc.
    r = await client.post("/capture/import", json=_payload(
        ref="victim-1", department="qc", title="Original Title", status="ongoing",
        priority="medium"), headers=admin_headers)
    assert r.json()["created"] == 1, r.text

    # Attack: same external_ref, payload claims the attacker as owner and
    # the attacker's OWN department — both checks that existed before this
    # fix would have let this through.
    r = await client.post("/capture/import", json=_payload(
        ref="victim-1", owner=attacker["username"], department="pr",
        title="HACKED TITLE", status="stuck", priority="critical",
        blocker_reason="pwned"), headers=attacker_headers)
    body = r.json()
    assert body["created"] == 0 and body["updated"] == 0, body
    assert len(body["skipped"]) == 1, body
    assert "not allowed" in body["skipped"][0]["reason"], body

    # The row's real fields are untouched.
    tasks = (await client.get("/tasks?include_archived=true", headers=admin_headers)).json()
    victim = next(t for t in tasks if t.get("external_ref") == "victim-1")
    assert victim["title"] == "Original Title"
    assert victim["status"] == "ongoing"
    assert victim["priority"] == "medium"
    assert victim["department"] == "qc"
    assert victim.get("blocker_reason") is None


async def test_import_unscoped_user_unaffected_by_scope_guard(client, admin_headers, org):
    """H2 hazard check — dept_scope() is None for a plain USER (and for any
    manager with no department assigned), so the guard must not touch them."""
    await _two_departments(org)
    user, otp = await create_user(client, admin_headers)          # plain USER
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.post("/capture/import", json=_payload(ref="plain-user", department="qc"),
                          headers=headers)
    assert r.json()["created"] == 1, r.text
