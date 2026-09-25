"""Trichome maturation checks — the documented record behind a harvest date
(migration 0066 + app/api/trichome.py).

Pins that the record is an OBSERVATION and not a gate (a cut is never refused
for want of one), that the three trichome percentages are read together, that
the cultivation writers — including QA since 2026-09-05 — record it, and that
the harvest clearance reports the latest verdict without counting it.
"""
from tests.conftest import create_user, login_and_set_password
from tests.test_cultivation import _actor, _cultivar, _room
from app.worktime import facility_today


async def _batch(client, headers, room_id, cultivar_id, code="GP092601", phase="flower"):
    r = await client.post("/cultivation/batches", json={
        "room_id": room_id, "cultivar_id": cultivar_id, "code": code,
        "plant_count": 100, "phase": phase}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _check(client, headers, batch_id, **over):
    body = {"batch_id": batch_id, "instrument": "digital", "verdict": "approaching"}
    body.update(over)
    return await client.post("/cultivation/trichome-checks", json=body, headers=headers)


async def test_who_may_look_down_the_microscope(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, user_h = await _actor(client, admin_headers, "USER")
    room = await _room(client, admin_headers, "flower_t", "Flowering T")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _batch(client, cu_h, room["id"], cv["id"])

    assert (await client.get("/cultivation/trichome-checks", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/trichome-checks", headers=qc_h)).status_code == 200
    assert (await _check(client, qc_h, b["id"])).status_code == 403
    assert (await _check(client, user_h, b["id"])).status_code == 403
    assert (await _check(client, cu_h, b["id"])).status_code == 201
    # QA is a cultivation writer since the owner's 2026-09-05 model.
    assert (await _check(client, qa_h, b["id"], verdict="ready")).status_code == 201


async def test_a_check_records_what_was_seen_and_defaults_to_the_facility_day(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_t2", "Flowering T2")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _batch(client, cu_h, room["id"], cv["id"])
    r = await _check(client, cu_h, b["id"], instrument="stereo", magnification="60x",
                     sample_sites=5, pct_clear=15, pct_cloudy=70, pct_amber=15,
                     verdict="ready", note="lower canopy lagging")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["checked_on"] == facility_today().isoformat()
    assert body["instrument"] == "stereo" and body["magnification"] == "60x"
    assert body["pct_amber"] == 15.0 and body["verdict"] == "ready"
    assert body["batch_code"] == "GP092601" and body["room_name"] == "Flowering T2"
    # A qualitative check is allowed: the percentages are optional together.
    r = await _check(client, cu_h, b["id"], checked_on="2026-09-01", verdict="immature")
    assert r.status_code == 201
    assert r.json()["pct_amber"] is None and r.json()["checked_on"] == "2026-09-01"

    lst = (await client.get(f"/cultivation/trichome-checks?batch_id={b['id']}",
                            headers=cu_h)).json()["checks"]
    assert len(lst) == 2
    assert lst[0]["checked_on"] > lst[1]["checked_on"], "newest first — the trend is the point"


async def test_three_states_of_one_field_of_view_must_add_up(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_t3", "Flowering T3")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _batch(client, cu_h, room["id"], cv["id"])
    r = await _check(client, cu_h, b["id"], pct_clear=10, pct_cloudy=10, pct_amber=10)
    assert r.status_code == 422 and "100" in r.text
    # 98–102 is the slack a real reading has.
    assert (await _check(client, cu_h, b["id"], pct_clear=10, pct_cloudy=80,
                         pct_amber=9)).status_code == 201
    # Two of three given is not a sum to check — and a missing percentage is
    # missing, never zero.
    r = await _check(client, cu_h, b["id"], pct_amber=12)
    assert r.status_code == 201 and r.json()["pct_clear"] is None
    assert (await _check(client, cu_h, b["id"], instrument="loupe")).status_code == 422
    assert (await _check(client, cu_h, b["id"], verdict="lovely")).status_code == 422


async def test_a_finished_batch_has_nothing_left_to_look_at(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_t4", "Flowering T4")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _batch(client, cu_h, room["id"], cv["id"])
    r = await client.post(f"/cultivation/batches/{b['id']}/move",
                          json={"to_phase": "destroyed", "reason": "test"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert (await _check(client, cu_h, b["id"])).status_code == 409
    assert (await _check(client, cu_h, "not-a-uuid")).status_code == 404


async def test_the_batch_board_and_the_harvest_clearance_carry_the_latest_verdict(client, admin_headers):
    """The board shows the trend's last word; the cut form shows it too and is
    never blocked by it — a maturation reading is an observation, and the
    pre-harvest interval is the only thing that refuses a harvest."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_t5", "Flowering T5")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _batch(client, cu_h, room["id"], cv["id"])

    board = (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]
    assert next(x for x in board if x["id"] == b["id"])["latest_trichome"] is None
    clear = (await client.get(f"/cultivation/harvest-clearance/{b['id']}", headers=cu_h)).json()
    assert clear["latest_trichome"] is None and clear["clear"] is True

    await _check(client, cu_h, b["id"], checked_on="2026-09-01", verdict="immature")
    await _check(client, cu_h, b["id"], checked_on="2026-09-04", verdict="ready",
                 pct_clear=5, pct_cloudy=75, pct_amber=20)
    board = (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]
    tc = next(x for x in board if x["id"] == b["id"])["latest_trichome"]
    assert tc["verdict"] == "ready" and tc["checked_on"] == "2026-09-04" and tc["pct_amber"] == 20.0
    clear = (await client.get(f"/cultivation/harvest-clearance/{b['id']}", headers=cu_h)).json()
    assert clear["latest_trichome"]["verdict"] == "ready"
    assert clear["clear"] is True, "a verdict never gates the cut"
