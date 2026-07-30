"""Live demo org — a REAL organization the public demo logs into.

The old demo (web/gf/demo.js) was a client-side mock that intercepted the API
layer; it stopped reflecting the app once Facility/QC LIMS/QMS shipped. This
module replaces its data layer server-side: one permanent org (slug "demo"),
isolated from every real tenant by the same org_id RLS that separates real
tenants, wiped and re-seeded on every demo start (and wiped again on exit).

Invariants (from the platform's own rules):
- audit_log is NEVER touched — both DBs carry ONE global hash chain each;
  deleting any org's rows breaks /audit/verify for every org. Demo audit rows
  simply accumulate (append-only by design).
- app_admin's grants are S/I/U/D only — DELETE, never TRUNCATE, and the global
  PP-#### sequences are consumed permanently (unique per org, so harmless).
- The weekly snapshot scheduler must skip this org (scripts/weekly_snapshot.py
  and scripts/scheduler.py filter slug <> DEMO_SLUG) so demo data never flows
  into the shared Letta RAG.
- No ai_agent_bindings are seeded — every AI surface degrades gracefully
  ("no binding"), so anonymous visitors can never invoke real Letta agents.

The demo runs a single narrative — Arrakis / Spice Production ("the spice must
flow"). A random visual skin is still applied on every start (kept as before);
only the cast/narrative is fixed.
"""
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone

from app.db import tasks_admin_pool, users_admin_pool
from app.security import hash_password

DEMO_SLUG = "demo"
DEMO_ORG_NAME = "GrowFlow Demo"

# Serializes concurrent resets (two visitors clicking "Try the demo" at once).
_RESET_LOCK_KEY = 771_2026

# Every org-scoped table in the tasks DB except audit_log, children before
# parents. Several FK edges are RESTRICT and force ordering: qc_certificates →
# qc_specifications; the cultivation chain plant_phase_events/plants → batches →
# cultivars/rooms; and plant_batches → rooms. Everything else either cascades or
# is SET NULL, but explicit order keeps the wipe self-evident.
_TASKS_WIPE_ORDER = (
    "ai_agent_bindings", "ai_pins", "weekly_documents", "handoffs",
    "task_comments", "task_assignees", "task_links", "work_sessions",
    "task_progress", "task_dependencies", "notifications", "events",
    "qc_coa_verifications", "qc_coa_chunks", "qc_coa_extractions",
    "qc_coa_documents", "qc_oos_notifications", "qc_oos_register",
    "qc_oos_records", "qc_results", "qc_certificates",
    "qc_chain_of_custody", "qc_sample_field_records", "qc_sampling_requests",
    "qc_samples", "qc_sampling_plans", "qc_spec_parameters",
    "qc_specifications", "qc_field_placeholders", "qc_water_tests",
    "qc_stability_studies", "qc_sample_transports",
    "plant_phase_events", "plants", "plant_batches", "cultivars", "rooms",
    "tasks", "calendar_weeks", "departments",
)

_DEPARTMENTS = (
    ("cultivation",       "Cultivation",       "Одгледување"),
    ("production",        "Production",        "Производство"),
    ("qc",                "Quality Control",   "Контрола на квалитет"),
    ("quality_assurance", "Quality Assurance", "Обезбедување квалитет"),
    ("logistics",         "Warehouse",         "Магацин"),
    ("security",          "Security",          "Обезбедување"),
    ("tooling",           "Maintenance",       "Одржување"),
)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _username(full_name: str) -> str:
    out, prev_dot = [], True
    for ch in full_name.lower():
        if ch.isalpha():
            out.append(ch); prev_dot = False
        elif not prev_dot:
            out.append("."); prev_dot = True
    return "".join(out).strip(".")


# ── the demo cast (Arrakis / Spice Production) ─────────────────────────────
# people: (key, full_name, role, dept_code|None, function_role)
# tasks:  dicts; owner/helpers reference people keys; dept is a dept code;
#         notes: (person_key, day_label, text); w: prev|cur|next (default cur)

def _cast_dune():
    people = [
        ("admin",   "Lady Jessica",        "ADMIN",  None,                "System Administrator"),
        ("owner",   "Duke Leto Atreides",  "OWNER",  None,                "Owner"),
        ("ceo",     "Paul Atreides",       "CEO",    None,                "Chief Executive Officer"),
        ("coo",     "Thufir Hawat",        "COO",    None,                "Chief Operating Officer (Mentat)"),
        ("qp",      "Rev Mother Mohiam",   "QP",     None,                "Qualified Person"),
        ("qa",      "Dr Wellington Yueh",  "QA_MGR", "quality_assurance", "QA Manager"),
        ("qc",      "Dr Liet Kynes",       "QC_MGR", "qc",                "QC Manager"),
        ("pr",      "Gurney Halleck",      "PR_MGR", "production",        "Production Manager"),
        ("cu",      "Stilgar",             "CU_MGR", "cultivation",       "Cultivation Manager"),
        ("wh",      "Esmar Tuek",          "WH_MGR", "logistics",         "Warehouse Manager"),
        ("se",      "Duncan Idaho",        "SE_MGR", "security",          "Security Manager"),
        ("mu",      "Shadout Mapes",       "MU_MGR", "tooling",           "Maintenance Manager"),
        ("op_pr",   "Jamis",               "USER",   "production",        "Production Operator"),
        ("op_wh",   "Harah",               "USER",   "logistics",         "Warehouse Operator"),
        ("op_cu",   "Chani",               "USER",   "cultivation",       "Grow Room Operator"),
        ("op_qc",   "Alia Atreides",       "USER",   "qc",                "Lab Technician"),
    ]
    batch = "SP-042"
    tasks = [
        dict(w="prev", title=f'Harvest spice field, Sector 14 — batch {batch} "Melange Prime" | Жетва на зачин, сектор 14 — серија {batch}',
             dept="cultivation", owner="cu", helpers=["op_cu"], status="completed", priority="high",
             days=["Mon", "Tue"], tags=[batch, "harvest"], ref="SOP-CU-014",
             notes=[("cu", "Tue", "Harvest complete: 42.5 kg raw melange, carryall lifted before wormsign."),
                    ("owner", "Tue", "The Emperor watches our quotas. I want the maturation-loss figure the moment it exists.")]),
        dict(w="prev", title="Load maturation chamber 2 and set climate program | Полнење на комора за зреење 2",
             dept="production", owner="pr", helpers=["op_pr"], status="completed",
             days=["Tue", "Wed"], tags=[batch, "maturation"], ref="SOP-PR-007"),
        dict(w="prev", title="Night-shift wormsign & perimeter watch (weekend) | Ноќна стража на периметарот",
             dept="security", owner="se", status="completed", days=["Sat", "Sun"], tags=["monitoring"],
             sessions=[("se", "prev", 5, 22, 4.5, "Sat night watch"),
                       ("se", "prev", 6, 10, 4.5, "Sun rounds")],
             notes=[("se", "Sun", "Wormsign at 03:00, two klicks out — sentries recalled, thumper decoy deployed.")]),
        dict(w="prev", title="Replace air-filtration pre-filters, corridor B | Замена на предфилтри, коридор Б",
             dept="tooling", owner="mu", status="completed", days=["Fri"],
             type="validation", tags=["HVAC"], ref="PM-10191-31"),
        dict(title=f"Sift & weigh matured batch {batch} | Просејување и мерење на {batch}",
             desc="Sift, record net weight per container, transfer to QC sampling.",
             dept="production", owner="pr", helpers=["op_pr"], status="ongoing", priority="critical",
             days=["Mon", "Tue", "Wed"], tags=[batch, "sift"], ref="SOP-PR-009", est=24,
             sessions=[("op_pr", "cur", 0, 8, 8, "Sift day 1"),
                       ("pr", "cur", 0, 17, 3, "Catch-up after scale drift")],
             notes=[("op_pr", "Mon", "First 12 containers sifted and sealed."),
                    ("pr", "Tue", "Scale #2 drifted 0.3 g — Maintenance notified; using scale #1."),
                    ("ceo", "Tue", "Keep daily net-weight totals in the notes — the Landsraad review wants the trend.")],
             comments=[("qc", "Hand-off window is Wed 09:00 — the lab booth is booked. The desert does not forgive lateness."),
                       ("pr", "We'll be there at 09:00 sharp.")]),
        dict(title=f"QC sampling of batch {batch} per sampling plan | QC узорцирање на {batch}",
             dept="qc", owner="qc", helpers=["op_qc"], status="ongoing", priority="critical",
             days=["Wed", "Thu"], tags=[batch, "sampling"], ref="SOP-QC-003", type="lab", est=8,
             notes=[("qc", "Wed", "Sampling booth calibrated. The spice must flow — but only through the sampling plan.")]),
        dict(title=f"Purity & potency assay {batch} | Чистота и потентност на {batch}",
             dept="qc", owner="op_qc", status="pending", priority="high",
             days=["Thu", "Fri"], tags=[batch, "lab"], type="lab", ref="TM-114"),
        dict(title=f"Batch record review & release dossier {batch} | Преглед на серија и досие за {batch}",
             dept="quality_assurance", owner="qa", status="pending", priority="high",
             days=["Fri"], tags=[batch, "release"], type="document", ref=f"BR-{batch}",
             notes=[("qa", "Mon", "Pre-review checklist ready. My conditioning does not permit an uninitialled entry.")]),
        dict(title=f"QP certification decision — batch {batch} | Одлука за сертификација на {batch}",
             dept="quality_assurance", owner="qp", status="pending", priority="critical",
             days=["Fri"], tags=[batch, "release"], due="cur_end", ref="GOM-CERT-042"),
        dict(title=f"Reserve quarantine bay & Guild shipping manifests {batch} | Карантин и шпедиција за {batch}",
             dept="logistics", owner="wh", helpers=["op_wh"], status="pending",
             days=["Fri"], tags=[batch, "shipping"],
             notes=[("wh", "Mon", "Bay 4 cleared and sealed. The Guild asks no questions when the papers are perfect.")]),
        dict(title="Establish 240 desert-hardened seedlings, Greenhouse 1 | Садење 240 садници во стаклена градина 1",
             dept="cultivation", owner="cu", helpers=["op_cu"], status="ongoing", priority="high",
             days=["Mon", "Tue"], tags=["new-genetics", "propagation"], est=16,
             notes=[("op_cu", "Mon", "Trays 1–8 planted; dew collectors mounted and logged."),
                    ("owner", "Mon", "Those seedlings cost House Atreides a fortune — I expect a 95% take rate.")]),
        dict(title="Repair windtrap condenser valve, Greenhouse 2 | Поправка на вентил на кондензатор, градина 2",
             dept="tooling", owner="mu", status="stuck", priority="critical", days=["Tue"], tags=["irrigation"],
             blocker="Replacement valve held at Guild customs — broker chasing daily; ETA Thursday.",
             notes=[("mu", "Tue", "Water discipline holds — hand-watering rota posted while we wait for the part.")]),
        dict(title="Weekly perimeter & sentry-eye audit | Неделна проверка на периметар и сензори",
             dept="security", owner="se", status="ongoing", days=["Wed"], tags=["audit"]),
        dict(title="Investigate temperature deviation DEV-10191-089 | Истрага за отстапување DEV-10191-089",
             dept="quality_assurance", owner="qa", helpers=["mu"], status="review", priority="high",
             days=["Wed", "Thu"], type="capa", tags=["deviation", "HVAC"], ref="DEV-10191-089",
             notes=[("qa", "Thu", "Root cause: compressor cycling. CAPA drafted, awaiting Maintenance countersign.")]),
        dict(title="Update SOP-PR-007 (maturation process) | Ажурирање на SOP-PR-007 (процес на зреење)",
             dept="production", owner="pr", status="review", type="sop", days=["Thu"], tags=["GMP", "SOP"], ref="SOP-PR-007"),
        dict(title="Cycle count — spice containers & packaging | Попис на амбалажа и контејнери",
             dept="logistics", owner="op_wh", status="postponed", days=["Wed"], tags=["inventory"],
             notes=[("op_wh", "Wed", "Moved to next week — the loader crew was called to the landing field.")]),
        dict(title="Weekly management meeting — production status | Неделен колегиум за производство",
             dept="production", owner="ceo", helpers=["coo", "pr", "cu", "qc"],
             status="completed", type="meeting", days=["Mon"]),
        dict(w="next", title=f"Package certified batch {batch} (400 g + 10 g) | Пакување на {batch}",
             dept="production", owner="pr", helpers=["op_pr"], status="pending", priority="high",
             days=["Mon", "Tue"], tags=[batch, "packaging"]),
        dict(w="next", title=f"Ship {batch} to Guild freighter + certificate pack | Испорака на {batch} со сертификати",
             dept="logistics", owner="wh", status="pending", priority="high", days=["Wed"], tags=[batch, "shipping"]),
        dict(w="next", title="Prepare propagation room for new cultivar | Подготовка на соба за нова генетика",
             dept="cultivation", owner="cu", helpers=["op_cu"], status="pending", priority="critical",
             days=["Mon", "Tue", "Wed"], tags=["new-genetics", "quarantine"]),
        dict(w="next", title="Environmental monitoring re-qualification | Реквалификација на мониторинг на средина",
             dept="qc", owner="qc", status="pending", type="validation", days=["Thu", "Fri"], tags=["GMP", "EM"]),
    ]
    return dict(label="Arrakis spice ops", people=people, tasks=tasks, batch=batch,
                material=("SPC-MP", "Refined Melange — Melange Prime", "Рафиниран меланж — Melange Prime"),
                strains=("Melange Prime", "Arrakeen Dawn", "Sietch Kush"), lab="Guild Reference Lab")


# A single narrative — Arrakis / Spice Production. Kept as a dict (not a bare
# function) so the router's `cast in CASTS` guard and the frontend's cast key
# keep working unchanged if another narrative is ever added back.
CASTS = {"dune": _cast_dune}
DEFAULT_CAST = "dune"


# ── org lifecycle ───────────────────────────────────────────────────────────

async def get_demo_org_id() -> uuid.UUID | None:
    row = await users_admin_pool().fetchrow(
        "SELECT id FROM organizations WHERE slug=$1", DEMO_SLUG)
    return row["id"] if row else None


async def _ensure_org() -> uuid.UUID:
    org_id = await get_demo_org_id()
    if org_id is None:
        org_id = uuid.uuid4()
        await users_admin_pool().execute(
            "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)"
            " ON CONFLICT DO NOTHING", org_id, DEMO_ORG_NAME, DEMO_SLUG)
        org_id = await get_demo_org_id()
    return org_id


@asynccontextmanager
async def demo_mutex():
    """Serialize EVERY demo-org mutation (reset AND exit-wipe). A session-level
    advisory lock held on a dedicated connection for the whole wipe+seed span —
    the old design locked only the wipe transaction, so two concurrent
    /demo/start calls could interleave their seeds (one wiping the other's
    half-seeded rows mid-insert → FK violations / UNIQUE collisions → a
    corrupt half-seeded demo org, externally triggerable since /demo/start is
    public when demo_enabled)."""
    async with tasks_admin_pool().acquire() as lock_conn:
        await lock_conn.execute("SELECT pg_advisory_lock($1)", _RESET_LOCK_KEY)
        try:
            yield
        finally:
            await lock_conn.execute("SELECT pg_advisory_unlock($1)", _RESET_LOCK_KEY)


async def wipe_demo_org(org_id: uuid.UUID) -> None:
    """Delete every demo-org row in both DBs EXCEPT audit_log (global hash
    chain) and the organizations row itself (stable identity). Callers must
    hold demo_mutex() — the wipe itself stays transactional, but serialization
    against a concurrent reset's SEED phase lives in the mutex."""
    t = tasks_admin_pool()
    async with t.acquire() as c:
        async with c.transaction():
            for table in _TASKS_WIPE_ORDER:
                # `table` is only ever a value from the hardcoded module
                # constant _TASKS_WIPE_ORDER — never user input; the org_id
                # filter is a bound parameter. Safe by construction.
                await c.execute(f"DELETE FROM {table} WHERE org_id=$1", org_id)  # nosec B608
    # Users DB: profiles. Org row stays.
    await users_admin_pool().execute("DELETE FROM profiles WHERE org_id=$1", org_id)


async def reset_demo_org(cast: str = DEFAULT_CAST) -> dict:
    """Wipe + re-seed the demo org from the named cast. Returns the demo
    ADMIN profile identity {id, org_id, role, username, full_name,
    password_set_at} — the caller mints the session token from it (demo
    profiles carry an unusable random password; no password ever leaves
    the server)."""
    data = CASTS.get(cast, _cast_dune)()
    org_id = await _ensure_org()
    async with demo_mutex():
        return await _reset_locked(org_id, data)


async def _reset_locked(org_id: uuid.UUID, data: dict) -> dict:
    await wipe_demo_org(org_id)

    today = date.today()
    mon = {"prev": _monday(today) - timedelta(days=7),
           "cur": _monday(today),
           "next": _monday(today) + timedelta(days=7)}

    # Seed writes span both DBs and dozens of statements — a failure partway
    # through (a bad row, a lost connection) must not leave a half-seeded demo
    # org for the next visitor to land on. One transaction per DB, held on a
    # single acquired connection each, so either the whole seed lands or none
    # of it does (wipe_demo_org above already does the same for its deletes).
    upool, tpool = users_admin_pool(), tasks_admin_pool()
    async with upool.acquire() as u, tpool.acquire() as t:
        async with u.transaction(), t.transaction():
            # departments
            dept_ids: dict[str, uuid.UUID] = {}
            for code, name, name_mk in _DEPARTMENTS:
                dept_ids[code] = await t.fetchval(
                    "INSERT INTO departments(org_id, code, name, name_mk) VALUES ($1,$2,$3,$4) RETURNING id",
                    org_id, code, name, name_mk)

            # calendar weeks (prev / cur / next)
            week_ids: dict[str, uuid.UUID] = {}
            for key, m in mon.items():
                iso = m.isocalendar()
                week_ids[key] = await t.fetchval(
                    "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on)"
                    " VALUES ($1,$2,$3,$4,$5) RETURNING id",
                    org_id, iso[0], iso[1], m, m + timedelta(days=6))

            # people — unusable password (login is token-minted server-side only)
            unusable = hash_password(secrets.token_urlsafe(32))
            person_ids: dict[str, uuid.UUID] = {}
            for key, full_name, role, dept_code, function_role in data["people"]:
                pid = uuid.uuid4()
                person_ids[key] = pid
                await u.execute(
                    "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role,"
                    " department_id, function_role, must_change_password)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,false)",
                    pid, org_id, f"demo.{_username(full_name)}", unusable, full_name, role,
                    dept_ids.get(dept_code) if dept_code else None, function_role)
            admin_id = person_ids["admin"]

            # tasks + progress + comments + assignees + sessions
            for spec in data["tasks"]:
                wk = spec.get("w", "cur")
                due = (mon["cur"] + timedelta(days=6)) if spec.get("due") == "cur_end" else None
                task_id = await t.fetchval(
                    "INSERT INTO tasks(org_id, user_id, title, description, status, priority, task_type,"
                    " reference_code, blocker_reason, department_id, week_id, week_start, days, tags,"
                    " due_date, estimated_hours, created_by, updated_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$2,$2) RETURNING id",
                    org_id, person_ids[spec["owner"]], spec["title"], spec.get("desc"),
                    spec.get("status", "pending"), spec.get("priority", "normal"),
                    spec.get("type", "other"), spec.get("ref"), spec.get("blocker"),
                    dept_ids[spec["dept"]], week_ids[wk], mon[wk],
                    spec.get("days", []), spec.get("tags", []), due, spec.get("est"))
                for helper in spec.get("helpers", []):
                    await t.execute(
                        "INSERT INTO task_assignees(org_id, task_id, user_id, role, assigned_by)"
                        " VALUES ($1,$2,$3,'assignee',$4)", org_id, task_id, person_ids[helper], admin_id)
                for who, day, text in spec.get("notes", []):
                    await t.execute(
                        "INSERT INTO task_progress(org_id, task_id, user_id, day_label, note)"
                        " VALUES ($1,$2,$3,$4,$5)", org_id, task_id, person_ids[who], day, text)
                for who, text in spec.get("comments", []):
                    await t.execute(
                        "INSERT INTO task_comments(org_id, task_id, user_id, content)"
                        " VALUES ($1,$2,$3,$4)", org_id, task_id, person_ids[who], text)
                for who, wkey, dow, hour, hours, note in spec.get("sessions", []):
                    start = datetime.combine(mon[wkey] + timedelta(days=dow), time(hour=hour), tzinfo=timezone.utc)
                    await t.execute(
                        "INSERT INTO work_sessions(org_id, task_id, user_id, started_at, ended_at, hours, note)"
                        " VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        org_id, task_id, person_ids[who], start,
                        start + timedelta(hours=hours), hours, note)

            # facility: rooms + plant batches
            s1, s2, s3 = data["strains"]
            rooms = (("nursery_1", "Nursery 1", "Расадник 1", "nursery"),
                     ("veg_1", "Veg Room 1", "Вегетативна соба 1", "veg"),
                     ("veg_2", "Veg Room 2", "Вегетативна соба 2", "veg"),
                     ("flower_3", "Flower Room 3", "Соба за цветање 3", "flower"),
                     ("mother_1", "Mother Room", "Соба за мајки", "mother"),
                     ("dry_2", "Drying Room 2", "Сушара 2", "dry"))
            room_ids: dict[str, uuid.UUID] = {}
            for i, (code, name, name_mk, kind) in enumerate(rooms):
                room_ids[code] = await t.fetchval(
                    "INSERT INTO rooms(org_id, code, name, name_mk, kind, sort)"
                    " VALUES ($1,$2,$3,$4,$5,$6) RETURNING id", org_id, code, name, name_mk, kind, i)
            for room, strain, count, phase, since_days in (
                    ("nursery_1", s2, 240, "clone", 4), ("veg_1", s2, 180, "veg", 16),
                    ("veg_2", s3, 120, "veg", 22), ("flower_3", s1, 96, "flower", 48),
                    ("mother_1", s3, 12, "mother", 120), ("dry_2", s1, 0, "drying", 6)):
                await t.execute(
                    "INSERT INTO plant_batches(org_id, room_id, strain, plant_count, phase, phase_since,"
                    " created_by, updated_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$7)",
                    org_id, room_ids[room], strain, count, phase,
                    today - timedelta(days=since_days), admin_id)

            # QC chain: ACTIVE spec (2 params) → sample → DRAFT CoA with a passing and
            # a FAILING result → sample quarantined → OOS in Phase I. Values are typed
            # by the seed, complies computed the same way add_result would.
            batch = data["batch"]
            mcode, men, mmk = data["material"]
            qc_mgr, lab_tech, qp = person_ids["qc"], person_ids["op_qc"], person_ids["qp"]
            # Demo PP-#### document codes come from a dedicated reserved range
            # (…-9001), generated in Python — NEVER from nextval() — so starting or
            # resetting the demo does not advance the shared production qc_*_id_seq
            # counters. Each seed inserts exactly one of each entity and the wipe
            # first clears the prior demo row, so a fixed number in the reserved
            # range is collision-free (uniqueness is per (org_id, code)).
            yr = today.strftime("%Y")

            def dcode(kind: str) -> str:
                return f"PP-{kind}-{yr}-9001"

            spec_id = await t.fetchval(
                "INSERT INTO qc_specifications(org_id, spec_id, material_code, material_name_en,"
                " material_name_mk, version, effective_date, status, thc_grade, thc_acceptance_min,"
                " thc_acceptance_max, created_by, updated_by)"
                " VALUES ($1, $7,"
                "         $2,$3,$4,1,$5,'ACTIVE','GRADE_I',18,30,$6,$6) RETURNING id",
                org_id, mcode, men, mmk, today, qc_mgr, dcode('SPEC'))
            p_thc = await t.fetchval(
                "INSERT INTO qc_spec_parameters(org_id, spec_id, test_name_en, test_name_mk, test_method,"
                " spec_type, lower_limit, upper_limit, unit, sorting_order, created_by)"
                " VALUES ($1,$2,'Total THC','Вкупен THC','HPLC','assay',18,30,'%',1,$3) RETURNING id",
                org_id, spec_id, qc_mgr)
            p_moist = await t.fetchval(
                "INSERT INTO qc_spec_parameters(org_id, spec_id, test_name_en, test_name_mk, test_method,"
                " spec_type, lower_limit, upper_limit, unit, sorting_order, created_by)"
                " VALUES ($1,$2,'Moisture','Влага','Loss on drying','physical',NULL,12,'%',2,$3) RETURNING id",
                org_id, spec_id, qc_mgr)
            sample_id = await t.fetchval(
                "INSERT INTO qc_samples(org_id, sample_id, batch_id, material_code, sample_type,"
                " material_name_en, sampling_date, status, location, quantity, quantity_unit,"
                " created_by, updated_by)"
                " VALUES ($1, $7,"
                "         $2,$3,'batch',$4,$5,'QUARANTINE','QC intake fridge 1',25,'g',$6,$6) RETURNING id",
                org_id, batch, mcode, men, today - timedelta(days=1), qc_mgr, dcode('SMP'))
            coa_id = await t.fetchval(
                "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
                " cert_type, report_date, source_lab, analyst_id, created_by, updated_by)"
                " VALUES ($1, $8,"
                "         $2,$3,$4,'ICOA',$5,$6,$7,$7,$7) RETURNING id",
                org_id, batch, spec_id, sample_id, today, data["lab"], lab_tech, dcode('COA'))
            await t.execute(
                "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value, result_numeric,"
                " unit, lower_limit, upper_limit, complies, status, analyst_id, result_date, created_by)"
                " VALUES ($1,$2,$3,'Total THC','24.2',24.2,'%',18,30,true,'pass',$4,$5,$4)",
                org_id, coa_id, p_thc, lab_tech, today)
            fail_result = await t.fetchval(
                "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value, result_numeric,"
                " unit, lower_limit, upper_limit, complies, status, analyst_id, result_date, created_by)"
                " VALUES ($1,$2,$3,'Moisture','13.4',13.4,'%',NULL,12,false,'fail',$4,$5,$4) RETURNING id",
                org_id, coa_id, p_moist, lab_tech, today)
            oos_id = await t.fetchval(
                "INSERT INTO qc_oos_records(org_id, oos_number, result_id, sample_id, batch_id, material_code,"
                " test_name, specification_value, obtained_value, oos_type, risk_level, phase, status,"
                " detection_date, detected_by_id, created_by, updated_by)"
                " VALUES ($1, $8,"
                "         $2,$3,$4,$5,'Moisture','<= 12 %','13.4 %','OOS','MEDIUM','I','PHASE_I',$6,$7,$7,$7) RETURNING id",
                org_id, fail_result, sample_id, batch, mcode, today, qc_mgr, dcode('OOS'))
            for action, details in (("opened", f"OOS opened for batch {batch} (Moisture 13.4 %)"),
                                    ("status:OPEN->PHASE_I", "Phase I laboratory investigation started")):
                await t.execute(
                    "INSERT INTO qc_oos_register(org_id, oos_id, action, actor_id, details)"
                    " VALUES ($1,$2,$3,$4,$5)", org_id, oos_id, action, qc_mgr, details)

            # custody chain: sampling request → field record → chain-of-custody entry
            rqs_id = await t.fetchval(
                "INSERT INTO qc_sampling_requests(org_id, rqs_number, material_code, material_name_en,"
                " batch_id, originating_department, status, requested_by_id, registered_by_id, registered_at,"
                " registration_deadline, registration_window_met, sample_id, created_by, updated_by)"
                " VALUES ($1, $8,"
                "         $2,$3,$4,'cultivation','REGISTERED',$5,$6, now() - interval '20 hours',"
                "         now() + interval '4 hours', true, $7, $5,$5) RETURNING id",
                org_id, mcode, men, batch, person_ids["cu"], qc_mgr, sample_id, dcode('RQS'))
            sfr_id = await t.fetchval(
                "INSERT INTO qc_sample_field_records(org_id, sfr_number, rqs_id, sampling_location,"
                " barrel_numbers, num_containers, destination_facility, status, sampled_by_id, sample_id,"
                " created_by, updated_by)"
                " VALUES ($1, $6,"
                "         $2,'Flower Room 3',$3,2,'QC laboratory','COMPLETED',$4,$5,$4,$4) RETURNING id",
                org_id, rqs_id, ["B-101", "B-102"], person_ids["op_qc"], sample_id, dcode('SFR'))
            await t.execute(
                "INSERT INTO qc_chain_of_custody(org_id, sample_id, from_user_id, to_user_id, from_location,"
                " to_location, transfer_reason, transfer_type, sfr_id, created_by)"
                " VALUES ($1,$2,$3,$4,'Flower Room 3','QC laboratory','Routine batch testing','FIELD_TO_LAB',$5,$3)",
                org_id, sample_id, lab_tech, qc_mgr, sfr_id)

            # one water test (leaf module coverage)
            await t.execute(
                "INSERT INTO qc_water_tests(org_id, water_test_id, result_date, location, grade, parameters,"
                " passed, created_by, updated_by)"
                " VALUES ($1, $5,"
                "         $2,'Irrigation main, Veg Room 1','TW',$3,true,$4,$4)",
                org_id, today - timedelta(days=2),
                {"pH": 7.1, "conductivity_uScm": 480, "TOC_mgL": 0.4}, qc_mgr, dcode('WT'))

            row = await u.fetchrow(
                "SELECT id, org_id, role, username, full_name, password_set_at FROM profiles WHERE id=$1",
                admin_id)
    return dict(row)
