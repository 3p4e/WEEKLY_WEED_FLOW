"""Department scoping for manager roles (workflow scoping at the API layer).

Department managers (DEPT_SCOPED_ROLES = MANAGER_ROLES minus QP) see their own
department's tasks plus tasks they personally own / are assigned, PLUS both
sides of any multi-departmental family (a parent whose subtask is delegated to
their department, and a subtask under a parent in their department). Their
/reports/weekly is forced to their department. Executives, QP and ADMIN stay
org-wide. Enforced in tasks.py / reports.py via app.deps.dept_scope."""
import inspect

import pytest

from tests.conftest import create_user, login_and_set_password


def test_every_task_id_route_calls_the_scope_guard():
    """Structural backstop for the whole class of bug this file exists to pin:
    department scoping is enforced only at the app layer (RLS grants managers
    org-wide access — see roles.DEPT_SCOPED_ROLES), so EVERY endpoint that
    reaches a task by id must call tasks._assert_scope_visible. This test fails
    if a route with {task_id} in its path (or the by-session delete) is added
    without the guard — so a future endpoint can't silently reopen the bypass,
    which is exactly how it reopened for 11+ endpoints before. If a new such
    route legitimately needs no guard, add it to _EXEMPT with a reason."""
    from app.main import app

    # Routes that take a task id but genuinely don't need the guard, with why.
    _EXEMPT: dict[str, str] = {}  # none today: every {task_id} route is by-id task access

    offenders = []
    for route in app.routes:
        path = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        targets_a_task = "{task_id}" in path or path == "/sessions/{session_id}"
        if not targets_a_task or endpoint.__name__ in _EXEMPT:
            continue
        src = inspect.getsource(endpoint)
        if "_assert_scope_visible" not in src:
            methods = ",".join(sorted(getattr(route, "methods", []) or []))
            offenders.append(f"{methods} {path} ({endpoint.__name__})")
    assert not offenders, (
        "these task-id routes don't call _assert_scope_visible — a dept-scoped "
        "manager could reach a foreign task through them:\n  " + "\n  ".join(offenders))


async def _two_departments(org):
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC'),($1,'pr','Production')"
        " RETURNING id", org["org_id"])
    return str(rows[0]["id"]), str(rows[1]["id"])


async def _mk_task(client, headers, title, dept_id=None, **kw):
    body = {"title": title, **kw}
    if dept_id is not None:
        body["department_id"] = dept_id
    r = await client.post("/tasks", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _manager(client, admin_headers, dept_id, role="QC_MGR"):
    prof, otp = await create_user(client, admin_headers, role=role,
                                  full_name="Scoped Manager", department_id=dept_id)
    token = await login_and_set_password(client, prof["username"], otp)
    return prof, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_manager_list_scoped_to_own_department(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    mine = await _mk_task(client, admin_headers, "scoped: in my dept", d1)
    other = await _mk_task(client, admin_headers, "scoped: other dept", d2)
    _, mgr = await _manager(client, admin_headers, d1)

    r = await client.get("/tasks", headers=mgr)
    assert r.status_code == 200, r.text
    ids = {t["id"] for t in r.json()}
    assert mine["id"] in ids
    assert other["id"] not in ids


@pytest.mark.asyncio
async def test_manager_sees_cross_dept_task_they_own_or_are_assigned(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    prof, mgr = await _manager(client, admin_headers, d1)
    assigned = await _mk_task(client, admin_headers, "scoped: assigned cross-dept", d2)
    r = await client.post(f"/tasks/{assigned['id']}/assignees",
                          json={"user_id": prof["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.get("/tasks", headers=mgr)
    ids = {t["id"] for t in r.json()}
    assert assigned["id"] in ids


@pytest.mark.asyncio
async def test_multi_departmental_family_visible_to_both_sides(client, admin_headers, org):
    """A parent in dept B with a subtask delegated to dept A is visible IN FULL
    (parent + child) to dept A's manager — and vice versa."""
    d1, d2 = await _two_departments(org)
    parent = await _mk_task(client, admin_headers, "family: parent in d2", d2)
    child = await _mk_task(client, admin_headers, "family: subtask for d1", d1,
                           parent_id=parent["id"])
    _, mgr1 = await _manager(client, admin_headers, d1)   # receiving side
    _, mgr2 = await _manager(client, admin_headers, d2, role="PR_MGR")  # owning side

    ids1 = {t["id"] for t in (await client.get("/tasks", headers=mgr1)).json()}
    assert parent["id"] in ids1 and child["id"] in ids1, \
        "receiving department must see the whole family"
    ids2 = {t["id"] for t in (await client.get("/tasks", headers=mgr2)).json()}
    assert parent["id"] in ids2 and child["id"] in ids2, \
        "owning department must see the whole family"


@pytest.mark.asyncio
async def test_manager_create_guard_and_delegation(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)

    # top-level in another department → 403
    r = await client.post("/tasks", json={"title": "illegal", "department_id": d2}, headers=mgr)
    assert r.status_code == 403
    # top-level with no department → defaults to their own
    t = await _mk_task(client, mgr, "defaulted dept")
    assert str(t["department_id"]) == d1
    # subtask under their own task, delegated to another department → allowed
    sub = await _mk_task(client, mgr, "delegated subtask", d2, parent_id=t["id"])
    assert str(sub["department_id"]) == d2
    # subtask under a foreign parent: the parent is invisible to a d1-scoped
    # manager, so the create is refused as 404 (existence hidden, same as
    # GET /tasks/{id}) — it never reaches the department check
    foreign = await _mk_task(client, admin_headers, "foreign parent", d2)
    r = await client.post("/tasks", json={
        "title": "illegal delegation", "department_id": d2, "parent_id": foreign["id"],
    }, headers=mgr)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_manager_patch_department_guard(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    t = await _mk_task(client, mgr, "patch guard", d1)

    # moving a top-level task out of their department → 403
    r = await client.patch(f"/tasks/{t['id']}", json={"department_id": d2}, headers=mgr)
    assert r.status_code == 403
    # re-targeting a subtask under their own parent → allowed (delegation)
    sub = await _mk_task(client, mgr, "child", d1, parent_id=t["id"])
    r = await client.patch(f"/tasks/{sub['id']}", json={"department_id": d2}, headers=mgr)
    assert r.status_code == 200, r.text
    assert str(r.json()["department_id"]) == d2


@pytest.mark.asyncio
async def test_qp_and_executive_stay_org_wide(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    t1 = await _mk_task(client, admin_headers, "orgwide d1", d1)
    t2 = await _mk_task(client, admin_headers, "orgwide d2", d2)
    for role in ("QP", "COO"):
        prof, otp = await create_user(client, admin_headers, role=role,
                                      full_name=f"{role} OrgWide")
        token = await login_and_set_password(client, prof["username"], otp)
        h = {"Authorization": f"Bearer {token}"}
        ids = {t["id"] for t in (await client.get("/tasks", headers=h)).json()}
        assert t1["id"] in ids and t2["id"] in ids, f"{role} must remain org-wide"


@pytest.mark.asyncio
async def test_manager_cannot_patch_foreign_task_via_non_department_field(client, admin_headers, org):
    """A manager's PATCH scope guard used to fire ONLY when department_id was
    being changed — any other field (status, priority, ...) on a task outside
    their scope sailed through unchecked, relying on RLS's is_elevated() clause
    which grants every manager role org-wide write. This pins the fix: the
    scope guard now runs for every PATCH, not just department moves."""
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    foreign = await _mk_task(client, admin_headers, "foreign task", d2)

    r = await client.patch(f"/tasks/{foreign['id']}", json={"status": "completed"}, headers=mgr)
    assert r.status_code == 404, r.text

    # sanity: the same manager CAN patch a task in their own department
    mine = await _mk_task(client, mgr, "own task")
    r = await client.patch(f"/tasks/{mine['id']}", json={"status": "completed"}, headers=mgr)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_manager_cannot_write_subresources_on_foreign_task(client, admin_headers, org):
    """add_progress / add_session / add_link only checked the task EXISTS, not
    that it's in the manager's scope — same unguarded-write bug as the PATCH
    case, on the sub-resource endpoints."""
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    foreign = await _mk_task(client, admin_headers, "foreign for subresources", d2)
    fid = foreign["id"]

    r = await client.post(f"/tasks/{fid}/progress", json={"day_label": "Mon", "note": "x"}, headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.post(f"/tasks/{fid}/sessions",
                          json={"started_at": "2026-01-05T09:00:00", "hours": 1}, headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.post(f"/tasks/{fid}/links", json={"url": "https://example.com/x"}, headers=mgr)
    assert r.status_code == 404, r.text

    # sanity: all three succeed on a task in the manager's own department
    mine = await _mk_task(client, mgr, "own for subresources")
    mid = mine["id"]
    r = await client.post(f"/tasks/{mid}/progress", json={"day_label": "Mon", "note": "x"}, headers=mgr)
    assert r.status_code == 201, r.text
    r = await client.post(f"/tasks/{mid}/sessions",
                          json={"started_at": "2026-01-05T09:00:00", "hours": 1}, headers=mgr)
    assert r.status_code == 201, r.text
    r = await client.post(f"/tasks/{mid}/links", json={"url": "https://example.com/x"}, headers=mgr)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_manager_cannot_read_or_delete_foreign_task_sessions(client, admin_headers, org):
    """list_sessions (GET) and delete_session (DELETE /sessions/{id}) both
    reached org-wide for managers: list_sessions only checked task existence,
    and delete_session gated on 'author OR elevated' — and every manager role
    IS elevated, so a manager could read or destroy work-session evidence on
    any task in the org. Both now go through the shared scope guard."""
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    foreign = await _mk_task(client, admin_headers, "foreign with a session", d2)
    r = await client.post(f"/tasks/{foreign['id']}/sessions",
                          json={"started_at": "2026-01-05T09:00:00", "hours": 2}, headers=admin_headers)
    assert r.status_code == 201, r.text
    foreign_sid = r.json()["id"]

    # read leak closed
    r = await client.get(f"/tasks/{foreign['id']}/sessions", headers=mgr)
    assert r.status_code == 404, r.text
    # destructive write closed (session must still exist afterwards)
    r = await client.delete(f"/sessions/{foreign_sid}", headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.get(f"/tasks/{foreign['id']}/sessions", headers=admin_headers)
    assert any(s["id"] == foreign_sid for s in r.json()), "manager's blocked DELETE must not have removed it"

    # sanity: the manager CAN list + delete sessions on their own task
    mine = await _mk_task(client, mgr, "own with a session")
    r = await client.post(f"/tasks/{mine['id']}/sessions",
                          json={"started_at": "2026-01-05T09:00:00", "hours": 1}, headers=mgr)
    assert r.status_code == 201, r.text
    mine_sid = r.json()["id"]
    r = await client.get(f"/tasks/{mine['id']}/sessions", headers=mgr)
    assert r.status_code == 200 and any(s["id"] == mine_sid for s in r.json())
    r = await client.delete(f"/sessions/{mine_sid}", headers=mgr)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_noop_patch_on_foreign_task_is_404_not_success(client, admin_headers, org):
    """An empty PATCH used to short-circuit to {ok,noop} before the scope
    guard ran, returning success for a task the manager can't touch. The guard
    now runs even on a no-op, so an out-of-scope task is a clean 404."""
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    foreign = await _mk_task(client, admin_headers, "foreign noop", d2)

    r = await client.patch(f"/tasks/{foreign['id']}", json={}, headers=mgr)
    assert r.status_code == 404, r.text
    # own-dept no-op still returns the noop marker
    mine = await _mk_task(client, mgr, "own noop")
    r = await client.patch(f"/tasks/{mine['id']}", json={}, headers=mgr)
    assert r.status_code == 200 and r.json().get("noop") is True, r.text


@pytest.mark.asyncio
async def test_manager_cannot_assign_or_comment_on_foreign_task(client, admin_headers, org):
    """assign/unassign/comments only checked _can_manage_task (elevated OR
    owner) — since every manager role IS elevated, that check alone granted
    org-wide access. The scope guard must narrow it back to their department.
    Uses a bystander (not the manager) as the assignment target, since being
    assigned to a task is itself a legitimate in-scope condition — assigning
    the manager under test would defeat the negative case being tested."""
    d1, d2 = await _two_departments(org)
    _, mgr = await _manager(client, admin_headers, d1)
    bystander, _ = await create_user(client, admin_headers, role="USER", full_name="Bystander")
    foreign = await _mk_task(client, admin_headers, "foreign for collab", d2)
    fid = foreign["id"]

    r = await client.get(f"/tasks/{fid}/comments", headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.post(f"/tasks/{fid}/comments", json={"content": "hi"}, headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.get(f"/tasks/{fid}/assignees", headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.post(f"/tasks/{fid}/assignees", json={"user_id": bystander["id"]}, headers=mgr)
    assert r.status_code == 404, r.text
    r = await client.delete(f"/tasks/{fid}/assignees/{bystander['id']}", headers=mgr)
    assert r.status_code == 404, r.text

    # sanity: the same manager CAN comment/assign on a task in their own department
    mine = await _mk_task(client, mgr, "own for collab")
    r = await client.post(f"/tasks/{mine['id']}/comments", json={"content": "hi"}, headers=mgr)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_manager_weekly_report_forced_to_own_department(client, admin_headers, org):
    d1, d2 = await _two_departments(org)
    await _mk_task(client, admin_headers, "report mine", d1)
    await _mk_task(client, admin_headers, "report other", d2)
    _, mgr = await _manager(client, admin_headers, d1)

    # even explicitly requesting the other department is overridden
    r = await client.get(f"/reports/weekly?department_id={d2}", headers=mgr)
    assert r.status_code == 200, r.text
    body = r.json()
    titles = {t["title"] for t in body["tasks"]}
    assert "report mine" in titles
    assert "report other" not in titles
