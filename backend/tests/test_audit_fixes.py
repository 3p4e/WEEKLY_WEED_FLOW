"""Regression tests for the 2026-07 application-wide audit fixes.

Each test pins a specific bug the audit surfaced so it cannot silently return:
  - a department-less manager must NOT inherit org-wide authority over the
    submitted GMP document;
  - a dept-scoped manager must not read a foreign department's task by id
    (IDOR), nor plant a subtask in a foreign department via an omitted
    department_id;
  - a weekly Plan is scoped to its week PLUS carryover (future-week tasks are
    excluded, still-open earlier tasks are kept);
  - PDF export never 500s / never injects on a hostile color or a v1-shape
    metrics bucket missing keys.
"""
from datetime import date, timedelta

import pytest

from tests.conftest import create_user, login_and_set_password


async def _dept(org, code, name):
    from app.db import tasks_admin_pool
    row = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,$2,$3) RETURNING id",
        org["org_id"], code, name)
    return str(row["id"])


async def _manager(client, admin_headers, dept_id, role="QC_MGR"):
    prof, otp = await create_user(client, admin_headers, role=role,
                                  full_name="Mgr", department_id=dept_id)
    token = await login_and_set_password(client, prof["username"], otp)
    return prof, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_department_less_manager_cannot_compile_or_lock_org_wide_document(client, admin_headers, org):
    prof, otp = await create_user(client, admin_headers, role="WH_MGR",
                                  full_name="No Dept Mgr", department_id=None)
    token = await login_and_set_password(client, prof["username"], otp)
    h = {"Authorization": f"Bearer {token}"}
    # cannot compile any document with no department assigned
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=h)
    assert r.status_code == 403, r.text
    # admin compiles the org-wide record; the dept-less manager still cannot lock it
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    doc_id = r.json()["id"]
    r = await client.post(f"/reports/documents/{doc_id}/lock", headers=h)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_manager_cannot_read_foreign_department_task_by_id(client, admin_headers, org):
    d1 = await _dept(org, "qc", "QC")
    d2 = await _dept(org, "pr", "Production")
    _, mgr = await _manager(client, admin_headers, d1)
    r = await client.post("/tasks", json={"title": "secret", "department_id": d2}, headers=admin_headers)
    other = r.json()
    r = await client.get(f"/tasks/{other['id']}", headers=mgr)
    assert r.status_code == 404, r.text  # IDOR closed


@pytest.mark.asyncio
async def test_subtask_under_foreign_parent_never_lands_in_that_department(client, admin_headers, org):
    d1 = await _dept(org, "qc", "QC")
    d2 = await _dept(org, "pr", "Production")
    _, mgr = await _manager(client, admin_headers, d1)
    r = await client.post("/tasks", json={"title": "parent d2", "department_id": d2}, headers=admin_headers)
    parent = r.json()
    # manager posts a subtask with NO department_id under a foreign parent
    r = await client.post("/tasks", json={"title": "child", "parent_id": parent["id"]}, headers=mgr)
    if r.status_code == 201:
        assert r.json()["department_id"] == d1  # forced to own scope, NOT d2
    else:
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_plan_excludes_future_week_tasks_but_keeps_open_carryover(client, admin_headers, org):
    today = date.today()
    future = (today + timedelta(days=60)).isoformat()
    past = (today - timedelta(days=60)).isoformat()
    await client.post("/tasks", json={"title": "future task", "week_start": future,
                                      "due_date": future}, headers=admin_headers)
    await client.post("/tasks", json={"title": "carryover task", "week_start": past},
                      headers=admin_headers)
    r = await client.post("/reports/documents/compile", json={"kind": "plan"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    titles = [t.get("title") for t in r.json()["content"].get("tasks", [])]
    assert "carryover task" in titles
    assert "future task" not in titles


@pytest.mark.asyncio
async def test_pdf_export_survives_hostile_color_and_missing_metric_keys(client, admin_headers, org):
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    doc = r.json()
    c = doc["content"]
    c["ribbon"] = [{"date": date.today().isoformat(), "start_h": 9, "end_h": 11,
                    "color": '"/><script>x</script>', "title": "x", "sop": "PP-01", "hours": 2}]
    # a v1-shape metrics bucket: hostile color + missing hours/prev4/tasks/... keys
    c.setdefault("metrics", {})["per_sop"] = [{"sop": "PP-01", "color": "javascript:alert(1)"}]
    r = await client.patch(f"/reports/documents/{doc['id']}", json={"content": c}, headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.get(f"/reports/documents/{doc['id']}/export.pdf", headers=admin_headers)
    assert r.status_code == 200, r.text  # no KeyError 500
    assert r.headers["content-type"].startswith("application/pdf")
    # the injected markup must not appear verbatim in the PDF byte stream
    assert b"<script>x</script>" not in r.content
