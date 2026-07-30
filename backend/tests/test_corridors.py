"""Corridor cleaning cadence (§25, migration 0049 + app/api/decon.py).

The plan asks for the cultivation corridors to be cleaned after every waste
movement, every 4 hours, and at shift changeover. That is a CADENCE requirement,
and what these tests pin is the difference between a log and a cadence record: a
log answers "was it cleaned", the endpoint has to answer "often enough, and after
the events that demanded it".

So the cases that matter are the negative ones — a corridor never cleaned, a
corridor cleaned longer ago than the interval, and a disposed waste manifest with
no cleaning recorded after it. Each of those is a state the software must SURFACE;
none of them is a state it can prevent, and the report says so rather than showing
a green board it cannot justify.
"""
from datetime import datetime, timedelta, timezone

from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def _room(client, admin_headers, code, name, kind="other", name_mk=None):
    body = {"code": code, "name": name, "kind": kind}
    if name_mk:
        body["name_mk"] = name_mk
    r = await client.post("/facility/rooms", json=body, headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _clean(client, headers, room_id, trigger="four_hourly", **over):
    body = {"room_id": room_id, "trigger": trigger, "campaign": "hlvd-2026-07"}
    body.update(over)
    return await client.post("/decon/corridors/cleanings", json=body, headers=headers)


async def _backdate(cleaning_id, minutes):
    """Push a cleaning into the past. Done with a direct UPDATE rather than an API
    field: `cleaned_at` is deliberately not client-settable — a crew that can
    backdate its own cleaning record can satisfy the cadence on paper."""
    await tasks_admin_pool().execute(
        "UPDATE corridor_cleanings SET cleaned_at = now() - ($1 || ' minutes')::interval"
        " WHERE id = $2", str(minutes), cleaning_id)


async def test_read_gating_and_writer_roles(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    assert (await client.get("/decon/corridors", headers=user_h)).status_code == 403
    assert (await client.get("/decon/corridors", headers=qc_h)).status_code == 200
    # Cleaning is a cultivation-crew action, same as the rest of decon.
    assert (await _clean(client, qc_h, corridor["id"])).status_code == 403
    assert (await _clean(client, cu_h, corridor["id"])).status_code == 201


async def test_corridors_come_from_the_register_not_a_hardcoded_list(client, admin_headers):
    """A hardcoded C146/C152/... list would silently ignore a corridor added
    later, which is the failure mode of every embedded facility list."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    await _room(client, admin_headers, "c146_t", "Corridor · C146")
    await _room(client, admin_headers, "c999_t", "Corridor · C999 (added later)")
    # A non-corridor room must not appear, however it is used.
    await _room(client, admin_headers, "c180_t", "Flowering 1.1 · C180", kind="flower")
    # Nor must a Macedonian-named corridor be missed.
    await _room(client, admin_headers, "c152_t", "Hallway 152", name_mk="Коридор · C152")

    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    codes = {c["code"] for c in r["corridors"]}
    assert codes == {"c146_t", "c999_t", "c152_t"}, codes
    assert r["interval_minutes"] == 240


async def test_a_corridor_never_cleaned_is_overdue_not_unknown(client, admin_headers):
    """During the campaign, no record is the case the requirement is aimed at.
    Reporting it as "unknown" would let it sit unnoticed next to a green row."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    await _room(client, admin_headers, "c146_t", "Corridor · C146")
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    c = r["corridors"][0]
    assert c["last_cleaned"] is None
    assert c["minutes_since"] is None
    assert c["cleanings"] == 0
    assert c["overdue"] is True


async def test_the_cadence_flips_overdue_at_the_interval(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    fresh = await _clean(client, cu_h, corridor["id"])
    assert fresh.status_code == 201
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is False
    assert r["corridors"][0]["minutes_since"] == 0

    # Inside the window: still fine.
    await _backdate(fresh.json()["id"], 239)
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is False
    assert r["corridors"][0]["minutes_since"] == 239

    # AT the interval: due. "Cleaned every 4 hours" makes it due at the four-hour
    # mark, not a minute after — the boundary was undefined behaviour until a
    # mutation flipping > to >= survived this file, so it is pinned here.
    await _backdate(fresh.json()["id"], 240)
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is True
    assert r["corridors"][0]["minutes_since"] == 240

    # Past it: still overdue.
    await _backdate(fresh.json()["id"], 241)
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is True
    assert r["corridors"][0]["minutes_since"] == 241


async def test_the_latest_cleaning_is_what_counts_not_the_first(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    old = await _clean(client, cu_h, corridor["id"])
    await _backdate(old.json()["id"], 900)
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is True

    await _clean(client, cu_h, corridor["id"], trigger="shift_change")
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["corridors"][0]["overdue"] is False
    assert r["corridors"][0]["cleanings"] == 2, "both cleanings stay on the record"


async def test_a_waste_movement_cleaning_must_cite_its_manifest(client, admin_headers):
    """Without the link it cannot discharge "after every waste movement" — there
    is nothing tying it to a movement."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    naked = await _clean(client, cu_h, corridor["id"], trigger="waste_movement")
    assert naked.status_code == 422
    assert "cite the manifest" in naked.json()["detail"]

    m = (await client.post("/waste/manifests", json={
        "manifest_code": "WM-C1", "waste_type": "plant_material",
        "reason": "hlvd_eradication", "campaign": "hlvd-2026-07"},
        headers=cu_h)).json()
    ok = await _clean(client, cu_h, corridor["id"],
                      trigger="waste_movement", manifest_id=m["id"])
    assert ok.status_code == 201

    listed = (await client.get(f"/decon/corridors/{corridor['id']}/cleanings",
                               headers=cu_h)).json()
    assert listed["cleanings"][0]["manifest_code"] == "WM-C1"


async def test_an_unknown_trigger_is_rejected_with_the_named_list(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    bad = await _clean(client, cu_h, corridor["id"], trigger="felt_like_it")
    assert bad.status_code == 422
    assert "four_hourly" in bad.json()["detail"]


async def test_an_unknown_manifest_is_rejected_rather_than_500(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    for ref in ("not-a-uuid", "11111111-1111-4111-8111-111111111111"):
        r = await _clean(client, cu_h, corridor["id"],
                         trigger="waste_movement", manifest_id=ref)
        assert r.status_code == 422, ref


async def _disposed_manifest(client, cu_h, qa_h, code):
    m = (await client.post("/waste/manifests", json={
        "manifest_code": code, "waste_type": "plant_material",
        "reason": "hlvd_eradication", "campaign": "hlvd-2026-07"},
        headers=cu_h)).json()
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 500}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 500}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    r = await client.post(f"/waste/manifests/{m['id']}/dispose",
                          json={"carrier_ref": "C-" + code}, headers=cu_h)
    assert r.status_code == 200, r.text
    return m


async def test_a_disposed_movement_with_no_cleaning_after_it_is_surfaced(client, admin_headers):
    """The join neither table can do alone. A manifest that left the site and a
    corridor register with nothing cleaned since is exactly the breach §25 names,
    and it is invisible in either table on its own."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    m = await _disposed_manifest(client, cu_h, qa_h, "WM-MOVE1")
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    open_moves = {x["manifest_code"] for x in r["movements_without_cleaning"]}
    assert open_moves == {"WM-MOVE1"}

    # A cleaning that cites the manifest clears it.
    assert (await _clean(client, cu_h, corridor["id"],
                         trigger="waste_movement", manifest_id=m["id"])).status_code == 201
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["movements_without_cleaning"] == []


async def test_a_cleaning_BEFORE_the_movement_does_not_clear_it(client, admin_headers):
    """The rule is "after every waste movement". A clean that happened first is
    not the clean the rule asks for, and counting it would let one sweep at the
    start of a shift discharge every movement in it."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    early = await _clean(client, cu_h, corridor["id"], trigger="four_hourly")
    await _backdate(early.json()["id"], 30)
    await _disposed_manifest(client, cu_h, qa_h, "WM-MOVE2")

    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert {x["manifest_code"] for x in r["movements_without_cleaning"]} == {"WM-MOVE2"}, \
        "a cleaning 30 minutes before the movement must not discharge it"


async def test_an_EARLIER_movements_cleaning_does_not_discharge_a_LATER_movement(client, admin_headers):
    """The case a multi-day destruction window produces constantly: movement A is
    disposed, the corridor is swept after A, then movement B is disposed and
    nothing is swept. B is still a breach.

    This is what makes the time comparison load-bearing rather than decorative.
    The cleaning after A carries trigger='waste_movement', so a query that checked
    only the trigger — without `cleaned_at >= disposed_at` — would treat A's sweep
    as discharging B and report a clean board. My first version of this file did
    not cover it: the earlier cleaning it used was a four-hourly one, whose
    trigger fails the condition anyway, so removing the time comparison changed
    nothing and the mutation survived."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    a = await _disposed_manifest(client, cu_h, qa_h, "WM-A")
    swept = await _clean(client, cu_h, corridor["id"],
                         trigger="waste_movement", manifest_id=a["id"])
    assert swept.status_code == 201
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["movements_without_cleaning"] == [], "A is discharged by its own sweep"

    # B leaves the site later, and nothing is swept after it.
    await _disposed_manifest(client, cu_h, qa_h, "WM-B")
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert {x["manifest_code"] for x in r["movements_without_cleaning"]} == {"WM-B"}, \
        "A's sweep happened BEFORE B left — it cannot discharge B"


async def test_a_sweep_citing_ANOTHER_movement_does_not_discharge_this_one(client, admin_headers):
    """"After EVERY waste movement" is per movement. A sweep attesting to movement
    A, even one timed after movement B, does not discharge B — nobody attested to
    B, and treating it as covered is how a movement leaves the site with no
    corridor record behind it.

    This is the strict reading, and it is deliberate. An earlier draft of the query
    also accepted any cleaning with trigger='waste_movement', which both opened
    this hole and made the mandatory manifest citation pointless. That draft
    survived a mutation removing the loose clause — nothing failed, because nothing
    depended on the weaker reading. This test is what that finding produced."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")

    a = await _disposed_manifest(client, cu_h, qa_h, "WM-A")
    b = await _disposed_manifest(client, cu_h, qa_h, "WM-B")
    # One sweep, citing A only, after BOTH movements.
    assert (await _clean(client, cu_h, corridor["id"],
                         trigger="waste_movement", manifest_id=a["id"])).status_code == 201

    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert {x["manifest_code"] for x in r["movements_without_cleaning"]} == {"WM-B"}, \
        "A is discharged by its own citation; B is not discharged by A's"

    # B needs its own record. One physical sweep, two attestations.
    assert (await _clean(client, cu_h, corridor["id"],
                         trigger="waste_movement", manifest_id=b["id"])).status_code == 201
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["movements_without_cleaning"] == []


async def test_an_undisposed_manifest_is_not_yet_a_movement(client, admin_headers):
    """A draft or sealed manifest has not left the building, so there is nothing
    to clean up after. Counting it would produce a permanent false breach for
    every manifest still being filled in."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    await _room(client, admin_headers, "c146_t", "Corridor · C146")
    m = (await client.post("/waste/manifests", json={
        "manifest_code": "WM-DRAFT", "waste_type": "trim",
        "reason": "routine_cull", "campaign": "hlvd-2026-07"}, headers=cu_h)).json()
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 3}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 3}, headers=cu_h)
    r = (await client.get("/decon/corridors", headers=cu_h)).json()
    assert r["movements_without_cleaning"] == []


async def test_the_campaign_filter_scopes_both_halves(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    await _clean(client, cu_h, corridor["id"], campaign="hlvd-2026-07")
    await _disposed_manifest(client, cu_h, qa_h, "WM-CAMP")

    same = (await client.get("/decon/corridors?campaign=hlvd-2026-07", headers=cu_h)).json()
    assert same["corridors"][0]["cleanings"] == 1
    assert len(same["movements_without_cleaning"]) == 1

    other = (await client.get("/decon/corridors?campaign=some-other", headers=cu_h)).json()
    assert other["corridors"][0]["cleanings"] == 0, "a different campaign sees no cleanings"
    assert other["corridors"][0]["overdue"] is True
    assert other["movements_without_cleaning"] == [], "nor its movements"


async def test_a_below_spec_strip_reading_is_recorded_not_refused(client, admin_headers):
    """Same reasoning as the bleach and tool logs: a refused entry means the crew
    does not log it, and an unlogged weak bucket is invisible."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    weak = await _clean(client, cu_h, corridor["id"], ppm_strip_reading=400)
    assert weak.status_code == 201
    listed = (await client.get(f"/decon/corridors/{corridor['id']}/cleanings",
                               headers=cu_h)).json()
    assert listed["cleanings"][0]["ppm_strip_reading"] == 400


async def test_cleaned_at_is_not_client_settable(client, admin_headers):
    """A crew that can backdate its own cleaning satisfies the cadence on paper.
    The field is server-stamped, so an attempt to set it is ignored rather than
    honoured."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    corridor = await _room(client, admin_headers, "c146_t", "Corridor · C146")
    stale = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    r = await _clean(client, cu_h, corridor["id"], cleaned_at=stale)
    assert r.status_code == 201
    got = (await client.get("/decon/corridors", headers=cu_h)).json()["corridors"][0]
    assert got["overdue"] is False, "a client-supplied cleaned_at must not be honoured"
    assert got["minutes_since"] == 0
