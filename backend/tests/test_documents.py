"""Weekly Plan & Report documents — compile → review → lock → PDF export."""
from datetime import datetime, timedelta, timezone

from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


async def _seed_task_with_session(client, admin_headers, org, title="Ribbon task"):
    r = await client.post("/tasks", json={
        "title": title, "status": "ongoing", "priority": "high",
        "reference_code": "PP-QC-012", "task_type": "validation",
        "description": "System suitability plus linearity per protocol.",
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    task = r.json()
    # progress note (lands in the document's task content)
    r = await client.post(f"/tasks/{task['id']}/progress",
                          json={"day_label": "Mon", "note": "Column equilibrated."},
                          headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    # a real work session today 09:00-11:30 facility time -> ribbon segment
    start = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
    r = await client.post(f"/tasks/{task['id']}/sessions", json={
        "started_at": start.isoformat(),
        "ended_at": (start + timedelta(hours=2, minutes=30)).isoformat(),
        "note": "morning run",
    }, headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    return task


async def test_compile_review_lock_export_lifecycle(client, admin_headers, org):
    task = await _seed_task_with_session(client, admin_headers, org)

    # Compile the report document
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "draft" and doc["kind"] == "report"
    c = doc["content"]
    titles = [t["title"] for t in c["tasks"]]
    assert task["title"] in titles
    # expanded content: notes attached to the task
    mine = next(t for t in c["tasks"] if t["id"] == task["id"])
    assert any("Column equilibrated" in n["note"] for n in mine["notes"])
    # ribbon carries the session as a local-time segment keyed by SOP
    assert any(s["task_id"] == task["id"] and s["sop"] == "PP-QC-012" for s in c["ribbon"])
    seg = next(s for s in c["ribbon"] if s["task_id"] == task["id"])
    assert 0 <= seg["start_h"] < seg["end_h"] <= 24
    # metrics: per-SOP hours + trend fields exist
    sop = next(b for b in c["metrics"]["per_sop"] if b["sop"] == "PP-QC-012")
    assert sop["hours"] > 0 and "prev4_avg_hours" in sop
    # AI sections exist but are not_configured (no Letta binding in tests)
    assert all(s["status"] in ("not_configured", "unavailable", "draft") for s in c["ai_sections"])

    # Re-compile while draft: allowed (refreshes content, same row)
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["id"] == doc["id"]

    # GET by week
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["id"] == doc["id"]

    # PATCH the draft: approve a section / add edited content
    c["ai_sections"] = [{**s, "approved": True, "body": s["body"] or "Edited narrative."}
                        for s in c["ai_sections"]]
    r = await client.patch(f"/reports/documents/{doc['id']}", json={"content": c}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["content"]["ai_sections"][0]["approved"] is True

    # PDF export of the draft
    r = await client.get(f"/reports/documents/{doc['id']}/export.pdf", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "DRAFT" in r.headers.get("content-disposition", "")

    # LOCK -> immutable
    r = await client.post(f"/reports/documents/{doc['id']}/lock", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "locked"
    r = await client.patch(f"/reports/documents/{doc['id']}", json={"content": c}, headers=admin_headers)
    assert r.status_code == 409
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 409
    r = await client.post(f"/reports/documents/{doc['id']}/lock", headers=admin_headers)
    assert r.status_code == 409
    # locked PDF has no DRAFT suffix
    r = await client.get(f"/reports/documents/{doc['id']}/export.pdf", headers=admin_headers)
    assert r.status_code == 200 and "DRAFT" not in r.headers.get("content-disposition", "")


async def test_plan_document_compiles_without_sessions(client, admin_headers, org):
    r = await client.post("/tasks", json={"title": "Carries into next week", "status": "pending"},
                          headers=admin_headers)
    assert r.status_code == 201
    r = await client.post("/reports/documents/compile", json={"kind": "plan"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    c = r.json()["content"]
    assert c["kind"] == "plan" and c["ribbon"] == []
    assert any(t["title"] == "Carries into next week" for t in c["tasks"])


async def test_documents_operator_cannot_compile_or_lock(client, admin_headers, org):
    user, otp = await create_user(client, admin_headers, role="USER")
    tok = await login_and_set_password(client, user["username"], otp)
    h = {"Authorization": f"Bearer {tok}"}
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=h)
    assert r.status_code == 403
    # but reading the week's document (once compiled by a manager) is allowed
    await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=h)
    assert r.status_code == 200


async def test_documents_rls_org_isolation(client, admin_headers, org):
    await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    # a second org cannot see this org's document
    import uuid
    from app.db import users_admin_pool
    from app.security import hash_password
    org2, admin2 = str(uuid.uuid4()), str(uuid.uuid4())
    await users_admin_pool().execute(
        "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
        org2, "Other Org", f"other-{org2[:8]}")
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'Other Admin','ADMIN',false)",
        admin2, org2, f"admin2_{org2[:8]}", f"a2_{org2[:8]}@test.invalid", hash_password("OtherPass123456"))
    r = await client.post("/auth/login", json={"email": f"admin2_{org2[:8]}", "password": "OtherPass123456"})
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=h2)
    assert r.status_code == 404
    await users_admin_pool().execute("DELETE FROM organizations WHERE id=$1", org2)
    await tasks_admin_pool().execute("DELETE FROM weekly_documents WHERE org_id=$1", org2)
