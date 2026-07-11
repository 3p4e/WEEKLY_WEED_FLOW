"""Weekly Plan & Report documents — compile → review → lock → PDF export."""
from datetime import datetime, timedelta, timezone

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


async def test_documents_operator_denied_all_access(client, admin_headers, org):
    """A base USER must not compile, read, or export a document — it is an
    org-wide snapshot (all tasks' notes + every user's session times) that
    tasks_read RLS and reports.py's per-user filtering deliberately withhold."""
    user, otp = await create_user(client, admin_headers, role="USER")
    tok = await login_and_set_password(client, user["username"], otp)
    h = {"Authorization": f"Bearer {tok}"}
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=h)
    assert r.status_code == 403
    # Manager compiles it; the USER still cannot READ or EXPORT it.
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    doc_id = r.json()["id"]
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=h)
    assert r.status_code == 403
    r = await client.get(f"/reports/documents/{doc_id}/export.pdf", headers=h)
    assert r.status_code == 403
    r = await client.patch(f"/reports/documents/{doc_id}", json={"content": {}}, headers=h)
    assert r.status_code == 403


async def test_documents_malformed_id_is_404_not_500(client, admin_headers, org):
    """A non-uuid path param is a clean 404, not a 500 from asyncpg casting."""
    for method, suffix in (("patch", ""), ("post", "/lock"), ("get", "/export.pdf")):
        call = getattr(client, method)
        kw = {"json": {"content": {}}} if method == "patch" else {}
        r = await call(f"/reports/documents/not-a-uuid{suffix}", headers=admin_headers, **kw)
        assert r.status_code == 404, f"{method} {suffix}: {r.status_code}"


async def test_section_approve_endpoint(client, admin_headers, org):
    """The section-scoped PATCH flips one AI section's approval without sending
    the whole document, and refuses malformed ids / unknown keys / locked docs."""
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    doc = r.json()
    doc_id = doc["id"]
    key = doc["content"]["ai_sections"][0]["key"]
    # malformed id -> 404, unknown section -> 404
    r = await client.patch("/reports/documents/not-a-uuid/sections/x", json={"approved": True}, headers=admin_headers)
    assert r.status_code == 404
    r = await client.patch(f"/reports/documents/{doc_id}/sections/nope", json={"approved": True}, headers=admin_headers)
    assert r.status_code == 404
    # approve just that section
    r = await client.patch(f"/reports/documents/{doc_id}/sections/{key}", json={"approved": True}, headers=admin_headers)
    assert r.status_code == 200
    secs = {s["key"]: s for s in r.json()["content"]["ai_sections"]}
    assert secs[key]["approved"] is True
    # locked doc -> 409
    await client.post(f"/reports/documents/{doc_id}/lock", headers=admin_headers)
    r = await client.patch(f"/reports/documents/{doc_id}/sections/{key}", json={"approved": False}, headers=admin_headers)
    assert r.status_code == 409


async def test_locked_document_immutable_at_db_layer(client, admin_headers, org):
    """A locked document must be immutable at the DB layer, not just via the
    app's WHERE status='draft' guard: a raw UPDATE/DELETE through an app_user
    RLS connection must affect 0 rows (the command-scoped policies only expose
    DRAFT rows to UPDATE/DELETE)."""
    from app.db import rls
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    doc_id = r.json()["id"]
    r = await client.post(f"/reports/documents/{doc_id}/lock", headers=admin_headers)
    assert r.json()["status"] == "locked"

    user = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"}
    async with rls(user) as c:  # app_user pool — RLS-enforced, no status guard in the SQL
        upd = await c.execute("UPDATE weekly_documents SET content='{}'::jsonb WHERE id=$1", doc_id)
        dele = await c.execute("DELETE FROM weekly_documents WHERE id=$1", doc_id)
    assert upd == "UPDATE 0", upd
    assert dele == "DELETE 0", dele
    # untouched + still locked
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "locked"


def test_pdf_html_escapes_days_field():
    """The `days` field is unvalidated user input — it must be HTML-escaped in
    the PDF like every other field, or a crafted task injects markup / makes
    WeasyPrint fetch an attacker URL server-side."""
    from app.api.documents import _pdf_html
    doc = {
        "status": "draft", "kind": "report", "locked_by": None, "locked_at": None,
        "content": {
            "kind": "report", "period": {"label": "W1", "start": "2026-01-02"},
            "tasks": [{"title": "T", "status": "completed", "priority": "high",
                       "days": ["<img src=x onerror=alert(1)>"], "notes": []}],
            "ribbon": [], "metrics": {}, "ai_sections": [],
        },
    }
    out = _pdf_html(doc, {})
    assert "<img src=x" not in out
    assert "&lt;img src=x" in out


async def test_on_time_excludes_no_deadline_completions(client, admin_headers, org):
    """A completed task without a due date is neither on-time nor late — it must
    not inflate the on-time rate (it counts toward 'completed' but not 'measured')."""
    # one completed task with NO deadline
    r = await client.post("/tasks", json={"title": "Ad-hoc done", "status": "completed"}, headers=admin_headers)
    assert r.status_code == 201
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    ot = r.json()["content"]["metrics"]["on_time"]
    assert ot["completed"] >= 1 and ot["measured"] == 0 and ot["rate"] is None


async def test_preview_custom_range_not_persisted(client, admin_headers, org):
    """A custom-range preview returns compiled content WITHOUT writing a row —
    the stored/lockable record stays the scheduled Fri→Thu week only. The
    period carries the day-span the ribbon renderers use."""
    task = await _seed_task_with_session(client, admin_headers, org)
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=1)).isoformat()
    end = (today + timedelta(days=1)).isoformat()
    r = await client.post("/reports/documents/preview",
                          json={"kind": "report", "start": start, "end": end}, headers=admin_headers)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "preview" and doc["id"] is None
    c = doc["content"]
    assert c["period"]["days"] == 3
    assert c["period"]["start"] == start and c["period"]["end"] == end
    assert any(t["title"] == task["title"] for t in c["tasks"])
    # non-persistence: no compiled document exists for that week
    r = await client.get("/reports/documents", params={"kind": "report", "ref_date": start}, headers=admin_headers)
    assert r.status_code == 404


async def test_preview_validation_errors(client, admin_headers, org):
    bad = [
        {"kind": "report", "start": "2026-02-10", "end": "2026-02-01"},   # end < start
        {"kind": "report", "start": "2026-01-01", "end": "2026-12-31"},   # > 92 days
        {"kind": "report", "start": "nope", "end": "2026-01-02"},         # malformed date
        {"kind": "invoice", "start": "2026-01-01", "end": "2026-01-07"},  # bad kind
    ]
    for payload in bad:
        r = await client.post("/reports/documents/preview", json=payload, headers=admin_headers)
        assert r.status_code == 422, (payload, r.status_code)


async def test_export_range_pdf(client, admin_headers, org):
    """The non-persisted preview exports to PDF by posting its content back."""
    await _seed_task_with_session(client, admin_headers, org)
    today = datetime.now(timezone.utc).date()
    r = await client.post("/reports/documents/preview", json={
        "kind": "report", "start": (today - timedelta(days=1)).isoformat(),
        "end": (today + timedelta(days=1)).isoformat()}, headers=admin_headers)
    content = r.json()["content"]
    r = await client.post("/reports/documents/export-range.pdf",
                          json={"kind": "report", "content": content}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "PREVIEW" in r.headers.get("content-disposition", "")


async def test_preview_and_range_export_operator_denied(client, admin_headers, org):
    """Custom-range preview/export is an org-wide snapshot — base USER denied."""
    user, otp = await create_user(client, admin_headers, role="USER")
    tok = await login_and_set_password(client, user["username"], otp)
    h = {"Authorization": f"Bearer {tok}"}
    r = await client.post("/reports/documents/preview",
                          json={"kind": "report", "start": "2026-01-02", "end": "2026-01-08"}, headers=h)
    assert r.status_code == 403
    r = await client.post("/reports/documents/export-range.pdf",
                          json={"kind": "report", "content": {}}, headers=h)
    assert r.status_code == 403


async def test_documents_rls_org_isolation(client, admin_headers, org):
    await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    # a second org cannot see this org's document
    import uuid
    from app.db import users_admin_pool
    from app.security import hash_password
    from tests.conftest import purge_org
    org2, admin2 = uuid.uuid4(), uuid.uuid4()
    try:
        await users_admin_pool().execute(
            "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
            org2, "Other Org", f"other-{str(org2)[:8]}")
        await users_admin_pool().execute(
            "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role, must_change_password)"
            " VALUES ($1,$2,$3,$4,$5,'Other Admin','ADMIN',false)",
            admin2, org2, f"admin2_{str(org2)[:8]}", f"a2_{str(org2)[:8]}@test.invalid", hash_password("OtherPass123456"))
        r = await client.post("/auth/login", json={"email": f"admin2_{str(org2)[:8]}", "password": "OtherPass123456"})
        h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.get("/reports/documents", params={"kind": "report"}, headers=h2)
        assert r.status_code == 404
    finally:
        await purge_org(org2)


# ═══ Per-department documents (migration 0010 + content v2) ═══════════════════

async def _dept_pair(org):
    from app.db import tasks_admin_pool
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name, name_mk)"
        " VALUES ($1,'cultivation','Cultivation','Одгледување'),($1,'qc','Quality Control','Контрола')"
        " RETURNING id, code", org["org_id"])
    return {r["code"]: str(r["id"]) for r in rows}


async def _dept_manager(client, admin_headers, dept_id, role="CU_MGR"):
    prof, otp = await create_user(client, admin_headers, role=role,
                                  full_name="Doc Manager", department_id=dept_id)
    token = await login_and_set_password(client, prof["username"], otp)
    return prof, {"Authorization": f"Bearer {token}"}


async def _task_in(client, headers, title, dept_id):
    r = await client.post("/tasks", json={"title": title, "department_id": dept_id,
                                          "department": "x"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_manager_compile_is_forced_to_their_department(client, admin_headers, org):
    depts = await _dept_pair(org)
    await _task_in(client, admin_headers, "cu doc task", depts["cultivation"])
    await _task_in(client, admin_headers, "qc doc task", depts["qc"])
    _, mgr = await _dept_manager(client, admin_headers, depts["cultivation"])

    # even explicitly requesting the OTHER department is overridden
    r = await client.post("/reports/documents/compile",
                          json={"kind": "report", "department_id": depts["qc"]}, headers=mgr)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["department_id"] == depts["cultivation"]
    assert doc["content"]["department"]["code"] == "cultivation"
    titles = [t["title"] for t in doc["content"]["tasks"]]
    assert "cu doc task" in titles and "qc doc task" not in titles


async def test_orgwide_and_department_documents_coexist(client, admin_headers, org):
    depts = await _dept_pair(org)
    await _task_in(client, admin_headers, "coexist task", depts["cultivation"])
    _, mgr = await _dept_manager(client, admin_headers, depts["cultivation"])

    org_doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                                 headers=admin_headers)).json()
    exec_dept_doc = (await client.post("/reports/documents/compile",
                                       json={"kind": "report", "department_id": depts["qc"]},
                                       headers=admin_headers)).json()
    mgr_doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                                 headers=mgr)).json()
    ids = {org_doc["id"], exec_dept_doc["id"], mgr_doc["id"]}
    assert len(ids) == 3, "three documents (org-wide + 2 departments) must coexist for the same week"
    assert org_doc["department_id"] is None
    assert exec_dept_doc["department_id"] == depts["qc"]
    assert mgr_doc["department_id"] == depts["cultivation"]

    # GET picks the right one per scope
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=admin_headers)
    assert r.json()["id"] == org_doc["id"]
    r = await client.get("/reports/documents",
                         params={"kind": "report", "department_id": depts["qc"]}, headers=admin_headers)
    assert r.json()["id"] == exec_dept_doc["id"]
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=mgr)
    assert r.json()["id"] == mgr_doc["id"], "manager GET lands on their department document"

    # recompile per scope keeps the row identity (UPSERT hits the partial index)
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=admin_headers)
    assert r.json()["id"] == org_doc["id"]
    r = await client.post("/reports/documents/compile", json={"kind": "report"}, headers=mgr)
    assert r.json()["id"] == mgr_doc["id"]


async def test_manager_denied_orgwide_document_by_id(client, admin_headers, org):
    depts = await _dept_pair(org)
    _, mgr = await _dept_manager(client, admin_headers, depts["cultivation"])
    org_doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                                 headers=admin_headers)).json()

    for method, path, body in [
        ("patch", f"/reports/documents/{org_doc['id']}", {"content": {}}),
        ("patch", f"/reports/documents/{org_doc['id']}/sections/weekly_summary", {"approved": True}),
        ("post", f"/reports/documents/{org_doc['id']}/lock", None),
    ]:
        r = await getattr(client, method)(path, json=body, headers=mgr) if body is not None \
            else await client.post(path, headers=mgr)
        assert r.status_code == 403, f"{path} → {r.status_code}"
    r = await client.get(f"/reports/documents/{org_doc['id']}/export.pdf", headers=mgr)
    assert r.status_code == 403

    # an executive CAN lock a department document
    dept_doc = (await client.post("/reports/documents/compile",
                                  json={"kind": "report", "department_id": depts["qc"]},
                                  headers=admin_headers)).json()
    r = await client.post(f"/reports/documents/{dept_doc['id']}/lock", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "locked"


async def test_template_sections_shape(client, admin_headers, org):
    depts = await _dept_pair(org)
    await _task_in(client, admin_headers, "shape task", depts["cultivation"])

    # per-department doc: exactly the department's template
    _, mgr = await _dept_manager(client, admin_headers, depts["cultivation"])
    doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                             headers=mgr)).json()
    keys = [s["key"] for s in doc["content"]["template_sections"]]
    assert keys == ["cultivation_status"]
    sec = doc["content"]["template_sections"][0]
    assert sec["title_mk"] and sec["approved"] is False
    assert all(f["value"] == "" for f in sec["fields"]), "physical metrics start empty (manual entry)"
    assert sec["narrative"] == {"en": "", "mk": ""}
    assert doc["content"]["content_version"] == 2

    # org-wide doc: per-active-department sections + the org-wide two
    org_doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                                 headers=admin_headers)).json()
    org_keys = [s["key"] for s in org_doc["content"]["template_sections"]]
    assert "cultivation_status" in org_keys and "quality_gmp" in org_keys
    assert org_keys[-2:] == ["transition_plan", "production_forecast"]


async def test_section_editing_bilingual_fields_and_narrative(client, admin_headers, org):
    depts = await _dept_pair(org)
    await _task_in(client, admin_headers, "edit task", depts["cultivation"])
    doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                             headers=admin_headers)).json()

    # AI section: bilingual bodies + legacy mirror
    r = await client.patch(f"/reports/documents/{doc['id']}/sections/weekly_summary",
                           json={"body_en": "EN text", "body_mk": "МК текст"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    sec = next(s for s in r.json()["content"]["ai_sections"] if s["key"] == "weekly_summary")
    assert sec["body_en"] == "EN text" and sec["body_mk"] == "МК текст" and sec["body"] == "EN text"

    # legacy {body} alias still works and mirrors
    r = await client.patch(f"/reports/documents/{doc['id']}/sections/weekly_summary",
                           json={"body": "legacy"}, headers=admin_headers)
    sec = next(s for s in r.json()["content"]["ai_sections"] if s["key"] == "weekly_summary")
    assert sec["body_en"] == "legacy" and sec["body"] == "legacy"

    # template section: fields + bilingual narrative
    r = await client.patch(f"/reports/documents/{doc['id']}/sections/cultivation_status",
                           json={"fields": {"mother_plants": "12 GC"},
                                 "narrative_en": "Good week", "narrative_mk": "Добра недела",
                                 "approved": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    t = next(s for s in r.json()["content"]["template_sections"] if s["key"] == "cultivation_status")
    assert next(f for f in t["fields"] if f["key"] == "mother_plants")["value"] == "12 GC"
    assert t["narrative"] == {"en": "Good week", "mk": "Добра недела"} and t["approved"] is True

    # unknown field key → 422
    r = await client.patch(f"/reports/documents/{doc['id']}/sections/cultivation_status",
                           json={"fields": {"nonexistent_metric": "x"}}, headers=admin_headers)
    assert r.status_code == 422

    # locked → 409
    await client.post(f"/reports/documents/{doc['id']}/lock", headers=admin_headers)
    r = await client.patch(f"/reports/documents/{doc['id']}/sections/cultivation_status",
                           json={"fields": {"mother_plants": "13"}}, headers=admin_headers)
    assert r.status_code == 409


async def test_department_locked_document_immutable_at_db_layer(client, admin_headers, org):
    from app.db import rls
    depts = await _dept_pair(org)
    doc = (await client.post("/reports/documents/compile",
                             json={"kind": "report", "department_id": depts["qc"]},
                             headers=admin_headers)).json()
    await client.post(f"/reports/documents/{doc['id']}/lock", headers=admin_headers)
    admin = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"} \
        if "admin_id" in org else None
    # reuse the app-user RLS path: UPDATE/DELETE must match nothing on a locked row
    user = {"id": doc["created_by"], "org_id": org["org_id"], "role": "ADMIN",
            "username": "admin", "department_id": None}
    async with rls(user) as c:
        upd = await c.execute("UPDATE weekly_documents SET content='{}'::jsonb WHERE id=$1", doc["id"])
        dele = await c.execute("DELETE FROM weekly_documents WHERE id=$1", doc["id"])
    assert upd == "UPDATE 0" and dele == "DELETE 0"


async def test_v1_content_document_renders_without_500(client, admin_headers, org):
    """A pre-v2 document (no content_version / template_sections / department,
    ai body only) must GET and export cleanly — locked v1 docs are the record."""
    await _seed_task_with_session(client, admin_headers, org, title="v1 compat task")
    doc = (await client.post("/reports/documents/compile", json={"kind": "report"},
                             headers=admin_headers)).json()
    v1_content = {
        "kind": "report",
        "period": doc["content"]["period"],
        "tasks": doc["content"]["tasks"],
        "ribbon": doc["content"]["ribbon"],
        "metrics": doc["content"]["metrics"],
        "ai_sections": [{"key": "weekly_summary", "title": "Executive summary",
                         "body": "v1 legacy body", "approved": True, "status": "draft"}],
    }
    r = await client.patch(f"/reports/documents/{doc['id']}", json={"content": v1_content},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.get("/reports/documents", params={"kind": "report"}, headers=admin_headers)
    assert r.status_code == 200 and "content_version" not in r.json()["content"]
    r = await client.get(f"/reports/documents/{doc['id']}/export.pdf", headers=admin_headers)
    assert r.status_code in (200, 501), r.text   # 501 only if WeasyPrint missing
    if r.status_code == 200:
        assert r.content[:5] == b"%PDF-"


async def test_pdf_html_bilingual_and_locked_rules(client, admin_headers, org):
    from app.api.documents import _pdf_html
    content = {
        "content_version": 2, "kind": "report",
        "period": {"label": "W28 2026", "start": "2026-07-10", "days": 7},
        "department": {"id": "x", "code": "qc", "name": "Quality Control", "name_mk": "Контрола на квалитет"},
        "tasks": [{"title": "Esc <img src=x>", "department": "QC", "status": "completed",
                   "priority": "high", "reference_code": "PP-QC-1", "estimated_hours": 1,
                   "actual_hours": 1, "due_date": None, "description": "", "notes": []}],
        "ribbon": [], "metrics": {"per_sop": [], "on_time": {}},
        "template_sections": [{"key": "quality_gmp", "title_en": "Quality & GMP",
            "title_mk": "Квалитет и GMP",
            "fields": [{"key": "capas_open", "label_en": "Open CAPAs", "label_mk": "Отворени CAPA",
                        "value": "<svg onload=x>", "unit": ""}],
            "narrative": {"en": "Narr EN", "mk": "Нар МК"}, "approved": False}],
        "ai_sections": [{"key": "weekly_summary", "title": "Executive summary",
                         "body_en": "Sum EN", "body_mk": "Сум МК", "body": "Sum EN",
                         "approved": False, "status": "draft"}],
    }
    draft = {"content": content, "status": "draft", "kind": "report", "week_start": "2026-07-10",
             "created_by": None, "locked_by": None, "locked_at": None}
    h = _pdf_html(draft, {})
    assert "Неделен извештај" in h                      # bilingual title
    assert "Контрола на квалитет" in h                  # department name_mk
    assert "counter(pages)" in h                        # page counters
    assert "DRAFT · НАЦРТ" in h                         # watermark on drafts
    assert "Отворени CAPA" in h and "Нар МК" in h and "Сум МК" in h
    assert "<img" not in h and "<svg onload" not in h   # escaping holds
    locked = dict(draft, status="locked")
    h2 = _pdf_html(locked, {})
    assert "DRAFT · НАЦРТ" not in h2                    # no watermark when locked
    assert "Narr EN" not in h2, "unapproved narrative dropped from locked export"
    assert "Отворени CAPA" in h2, "metric grid always kept in the record"
    assert "Sum EN" not in h2, "unapproved AI section dropped from locked export"
