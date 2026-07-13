"""tasks.attributes — the per-department metadata map (migration 0011).

Pins: round-trip through POST/GET/PATCH, whole-object-replace PATCH
semantics with explicit-null → {} (the column is NOT NULL), the
_check_attributes bounds (key charset/count, scalar values, string and
serialized-size caps), and that a recurring task's next instance inherits
its attributes (room/equipment metadata must survive materialization).
"""
import pytest


async def _create(client, headers, **extra):
    r = await client.post("/tasks", json={"title": "attr task", **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_attributes_roundtrip_and_replace(client, admin_headers, org):
    task = await _create(client, admin_headers,
                         attributes={"room": "GR-2", "plant_count": 120, "handoff_ready": True})
    assert task["attributes"] == {"room": "GR-2", "plant_count": 120, "handoff_ready": True}

    # The list endpoint carries the column (dept home screens group on it).
    r = await client.get("/tasks", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task["id"])
    assert listed["attributes"]["room"] == "GR-2"

    # PATCH is whole-object replace, not merge.
    r = await client.patch(f"/tasks/{task['id']}", json={"attributes": {"room": "GR-5"}},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["attributes"] == {"room": "GR-5"}

    # Explicit null clears to the empty map (NOT NULL column — never SQL NULL).
    r = await client.patch(f"/tasks/{task['id']}", json={"attributes": None},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["attributes"] == {}


@pytest.mark.asyncio
async def test_attributes_default_to_empty_map(client, admin_headers, org):
    task = await _create(client, admin_headers)
    assert task["attributes"] == {}


@pytest.mark.asyncio
async def test_attributes_shape_bounds(client, admin_headers, org):
    async def rejected(attrs):
        r = await client.post("/tasks", json={"title": "bad attrs", "attributes": attrs},
                              headers=admin_headers)
        assert r.status_code == 422, f"expected 422 for {attrs!r}, got {r.status_code}"

    await rejected({"nested": {"a": 1}})            # non-scalar value
    await rejected({"listy": [1, 2]})               # non-scalar value
    await rejected({"nullv": None})                 # null value (clear = omit the key)
    await rejected({"Room": "GR-2"})                # uppercase key
    await rejected({"room-1": "x"})                 # hyphen in key
    await rejected({"k" * 49: "x"})                 # key too long
    await rejected({f"k{i}": i for i in range(25)})  # > 24 keys
    await rejected({"note": "x" * 501})             # string too long
    # > 8 KB serialized (24 valid keys of near-max strings)
    await rejected({f"key_{i:02d}": "y" * 400 for i in range(24)})

    # ...and the same guard runs on PATCH.
    task = await _create(client, admin_headers)
    r = await client.patch(f"/tasks/{task['id']}", json={"attributes": {"BAD": "x"}},
                           headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_attributes_scalars_accepted(client, admin_headers, org):
    task = await _create(client, admin_headers,
                         attributes={"room": "GR-1", "plant_count": 64,
                                     "target_ph": 6.1, "flagged": False})
    a = task["attributes"]
    assert a["plant_count"] == 64 and a["target_ph"] == 6.1 and a["flagged"] is False


@pytest.mark.asyncio
async def test_recurring_next_instance_inherits_attributes(client, admin_headers, org):
    task = await _create(client, admin_headers,
                         recurrence={"freq": "weekly"},
                         attributes={"equipment_ref": "HVAC-03"})
    r = await client.patch(f"/tasks/{task['id']}", json={"status": "completed"},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    nxt = r.json().get("next_instance")
    assert nxt, "completing a recurring task must materialize the next instance"
    assert nxt["attributes"] == {"equipment_ref": "HVAC-03"}
