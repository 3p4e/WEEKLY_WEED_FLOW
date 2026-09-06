"""The as-built facility layout register — facility_rooms + api/facility_layout.py.

The owner supplied the Archicad ground-floor sheet on 2026-09-05 and asked that
the app know the real facility. These tests pin what the register is: the
building as drawn (import is faithful and idempotent), what it is not (it does
not invent a cleanliness grade, and it is not the operational `rooms` table),
and who may classify a room.
"""
import json
from pathlib import Path

from tests.conftest import create_user, login_and_set_password
from tests.test_qc import _actor

_REGISTER = json.loads(
    (Path(__file__).resolve().parents[1] / "app" / "data" / "facility_layout.json")
    .read_text(encoding="utf-8"))


async def _import(client, headers, dry_run=False):
    r = await client.post("/facility/layout/import", json={"dry_run": dry_run},
                          headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _by_code(client, headers, code):
    r = await client.get("/facility/layout", headers=headers)
    assert r.status_code == 200, r.text
    rooms = r.json()["rooms"]
    return next(x for x in rooms if x["code"] == code)


async def test_the_packaged_register_is_the_drawing(client, admin_headers):
    """Every room on the sheet arrives, with the stamped area and perimeter and
    an anchor point, and the six flowering rooms carry the net cultivation area
    the plan prints under the gross one."""
    res = await _import(client, admin_headers)
    assert res["total"] == len(_REGISTER) == 191
    assert len(res["created"]) == 191 and res["updated"] == []

    c180 = await _by_code(client, admin_headers, "C180")
    assert c180["name_en"] == "FLOWERING PREMISE 1.1"
    assert c180["name_mk"] == "ПРОСТОРИЈА ЗА ЦВЕТАЊЕ 1.1"
    assert c180["area_m2"] == 501.38 and c180["net_area_m2"] == 416.0
    assert c180["perimeter_m"] == 111.35
    assert c180["wing"] == "cultivation" and c180["zone"] == "cultivation"
    assert 0 <= c180["plan_x"] <= 1 and 0 <= c180["plan_y"] <= 1

    r = await client.get("/facility/layout?zone=cultivation", headers=admin_headers)
    flowering = [x for x in r.json()["rooms"] if x["name_en"].startswith("FLOWERING")]
    assert len(flowering) == 6
    assert {x["net_area_m2"] for x in flowering} == {416.0}


async def test_no_room_is_given_a_cleanliness_grade(client, admin_headers):
    """No grade appears anywhere on the drawing, so the import must not invent
    one — assigning it is QA's decision, not the importer's."""
    await _import(client, admin_headers)
    r = await client.get("/facility/layout", headers=admin_headers)
    assert all(x["grade"] is None for x in r.json()["rooms"])


async def test_the_gacp_to_gmp_handover_is_recorded(client, admin_headers):
    """The owner's rule — harvest, cure and defoliation end GACP and start GMP —
    read onto the building: live plants are GACP, de-bucking onward is GMP, and
    plant rooms and personnel areas sit under neither."""
    await _import(client, admin_headers)
    grow = await _by_code(client, admin_headers, "C182")
    debuck = await _by_code(client, admin_headers, "C153")
    drying = await _by_code(client, admin_headers, "F104")
    ahu = await _by_code(client, admin_headers, "T69")
    assert grow["regime"] == "GACP"
    assert debuck["regime"] == "GMP" and debuck["zone"] == "post_harvest"
    assert drying["regime"] == "GMP"
    assert ahu["regime"] == "SUPPORT" and ahu["zone"] == "technical"


async def test_import_is_idempotent_and_keeps_a_classification(client, admin_headers):
    """Re-importing a corrected register refreshes what the drawing says and
    leaves what a person decided alone."""
    await _import(client, admin_headers)
    room = await _by_code(client, admin_headers, "F104")
    r = await client.patch(f"/facility/layout/{room['id']}",
                           json={"grade": "D", "notes": "classified 2026-09"},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["grade"] == "D"

    again = await _import(client, admin_headers)
    assert again["created"] == [] and len(again["updated"]) == 191
    after = await _by_code(client, admin_headers, "F104")
    assert after["grade"] == "D" and after["notes"] == "classified 2026-09"
    assert after["area_m2"] == 98.27


async def test_a_dry_run_writes_nothing(client, admin_headers):
    res = await _import(client, admin_headers, dry_run=True)
    assert res["dry_run"] is True and len(res["created"]) == 191
    r = await client.get("/facility/layout", headers=admin_headers)
    assert r.json()["rooms"] == []


async def test_the_register_links_to_the_room_the_app_schedules(client, admin_headers):
    """facility_rooms is the building; `rooms` is the short list of places the
    app schedules. The link is what lets a batch on the board be found on the
    plan — and re-linking moves it rather than colliding."""
    await _import(client, admin_headers)
    r = await client.post("/facility/rooms",
                          json={"code": "flower_1_1", "name": "Flowering 1.1", "kind": "flower"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    op_room = r.json()

    c180 = await _by_code(client, admin_headers, "C180")
    r = await client.patch(f"/facility/layout/{c180['id']}",
                           json={"room_id": op_room["id"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["room_id"] == op_room["id"]
    assert r.json()["room_code"] == "flower_1_1"

    # The same operational room moved to a different architectural room.
    c181 = await _by_code(client, admin_headers, "C181")
    r = await client.patch(f"/facility/layout/{c181['id']}",
                           json={"room_id": op_room["id"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert (await _by_code(client, admin_headers, "C180"))["room_id"] is None


async def test_a_linked_room_shows_what_is_growing_in_it(client, admin_headers):
    await _import(client, admin_headers)
    r = await client.post("/facility/rooms",
                          json={"code": "flower_1_2", "name": "Flowering 1.2", "kind": "flower"},
                          headers=admin_headers)
    op_room = r.json()
    cv = await client.post("/cultivation/cultivars",
                           json={"code": "GP", "name": "Grape Pie"}, headers=admin_headers)
    b = await client.post("/cultivation/batches",
                          json={"cultivar_id": cv.json()["id"], "room_id": op_room["id"],
                                "code": "GP092601", "plant_count": 120, "phase": "flower"},
                          headers=admin_headers)
    assert b.status_code == 201, b.text
    c181 = await _by_code(client, admin_headers, "C181")
    await client.patch(f"/facility/layout/{c181['id']}",
                       json={"room_id": op_room["id"]}, headers=admin_headers)
    r = await client.get(f"/facility/layout/{c181['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert [x["code"] for x in r.json()["batches"]] == [b.json()["code"]]


async def test_qa_classifies_and_an_operator_may_not(client, admin_headers):
    await _import(client, admin_headers)
    room = await _by_code(client, admin_headers, "F106")
    _, qa = await _actor(client, admin_headers, "QA_MGR")
    r = await client.patch(f"/facility/layout/{room['id']}",
                           json={"grade": "D", "regime": "GMP"}, headers=qa)
    assert r.status_code == 200, r.text
    assert r.json()["grade"] == "D"

    u, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, u["username"], otp)
    op = {"Authorization": f"Bearer {token}"}
    r = await client.patch(f"/facility/layout/{room['id']}", json={"grade": "C"}, headers=op)
    assert r.status_code == 403
    r = await client.get("/facility/layout", headers=op)
    assert r.status_code == 403


async def test_an_unknown_zone_or_regime_is_refused(client, admin_headers):
    await _import(client, admin_headers)
    room = await _by_code(client, admin_headers, "F106")
    for body in ({"zone": "greenhouse"}, {"regime": "GDP"}):
        r = await client.patch(f"/facility/layout/{room['id']}", json=body,
                               headers=admin_headers)
        assert r.status_code == 422, r.text


async def test_the_board_totals_the_building_by_zone(client, admin_headers):
    await _import(client, admin_headers)
    r = await client.get("/facility/layout", headers=admin_headers)
    totals = r.json()["totals"]
    assert totals["cultivation"]["rooms"] == 13
    # Six flowering rooms, two vegetation, mother, two clone rooms, seeds and
    # the sick-plant quarantine — just under 4 000 m2 as drawn.
    assert 3900 < totals["cultivation"]["area_m2"] < 4000
    assert totals["airlock"]["rooms"] == 17


async def test_every_room_that_can_be_drawn_carries_its_rectangle(client, admin_headers):
    """A room's SIZE comes from its own A:/P: stamp and is exact; its position
    and orientation were fitted to the drawing, and `box_conf` is how well the
    fitted edges landed on wall ink. The app draws the building from these, so
    the frame has to be sound: inside the unit square, and containing the pin."""
    await _import(client, admin_headers)
    r = await client.get("/facility/layout", headers=admin_headers)
    rooms = r.json()["rooms"]
    boxed = [x for x in rooms if x["box_x"] is not None]
    # Only C88 has no stamped area, so only C88 has no rectangle.
    assert len(boxed) == 190
    assert [x["code"] for x in rooms if x["box_x"] is None] == ["C88"]
    for x in boxed:
        assert 0 <= x["box_x"] and 0 <= x["box_y"]
        assert x["box_w"] > 0 and x["box_h"] > 0
        assert x["box_x"] + x["box_w"] <= 1 and x["box_y"] + x["box_h"] <= 1
        assert 0 <= x["box_conf"] <= 1
        # The pin sits in its own room — the two are one coordinate space.
        assert x["box_x"] <= x["plan_x"] <= x["box_x"] + x["box_w"]
        assert x["box_y"] <= x["plan_y"] <= x["box_y"] + x["box_h"]


async def test_the_drawn_rectangle_matches_the_stamped_area(client, admin_headers):
    """The rectangle is not a decoration: scaled back to metres it must return
    the area the drawing stamps. A flowering hall is 44.38 x 11.30 m, and the
    plan frame it is normalised against is 2710 x 1200 points at 14.2 points
    per metre."""
    await _import(client, admin_headers)
    room = await _by_code(client, admin_headers, "C180")
    w_m = room["box_w"] * 2710 / 14.2
    h_m = room["box_h"] * 1200 / 14.2
    # Tall hall: the long side runs down the plan.
    assert 10.5 < w_m < 12.0
    assert 43.0 < h_m < 46.0
    assert abs(w_m * h_m - room["area_m2"]) / room["area_m2"] < 0.06


async def test_a_reimport_does_not_move_a_room(client, admin_headers):
    await _import(client, admin_headers)
    before = await _by_code(client, admin_headers, "F104")
    await _import(client, admin_headers)
    after = await _by_code(client, admin_headers, "F104")
    for k in ("box_x", "box_y", "box_w", "box_h", "box_conf"):
        assert before[k] == after[k]
