"""Department scoping for manager roles (workflow scoping at the API layer).

Department managers (DEPT_SCOPED_ROLES = MANAGER_ROLES minus QP) see their own
department's tasks plus tasks they personally own / are assigned, PLUS both
sides of any multi-departmental family (a parent whose subtask is delegated to
their department, and a subtask under a parent in their department). Their
/reports/weekly is forced to their department. Executives, QP and ADMIN stay
org-wide. Enforced in tasks.py / reports.py via app.deps.dept_scope."""
import pytest

from tests.conftest import create_user, login_and_set_password


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
    # subtask under a foreign parent, targeting a foreign department → 403
    foreign = await _mk_task(client, admin_headers, "foreign parent", d2)
    r = await client.post("/tasks", json={
        "title": "illegal delegation", "department_id": d2, "parent_id": foreign["id"],
    }, headers=mgr)
    assert r.status_code == 403


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
