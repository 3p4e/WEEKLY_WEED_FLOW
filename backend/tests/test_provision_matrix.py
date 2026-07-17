"""Offline validation of the tt.* provisioning matrix — pure data, no HTTP.

Pins the invariants docs/TEST-ACCOUNTS.md promises: 7 canonical departments
(codes exactly matching web/gf/demo.js), ~25 unique tt.* accounts, 1 manager
+ 2 operators per department, executives/QP department-less, every role a
valid CREATABLE role (never ADMIN).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from provision_test_accounts import DEPARTMENTS, DEPT_KEY, MATRIX  # noqa: E402

from app.roles import CREATABLE_ROLES, MANAGER_ROLES  # noqa: E402

CANONICAL = ["cultivation", "production", "qc", "quality_assurance", "logistics", "security", "tooling"]


def test_seven_canonical_departments_match_demo_org():
    assert [d["code"] for d in DEPARTMENTS] == CANONICAL
    # The live demo seeds these same canonical departments server-side
    # (app/demo_org.py replaced the old client-side demo.js facility mock).
    from app.demo_org import _DEPARTMENTS
    assert [code for code, _en, _mk in _DEPARTMENTS] == CANONICAL
    # every department carries both language names
    assert all(d["name"] and d["name_mk"] for d in DEPARTMENTS)
    assert all(en and mk for _c, en, mk in _DEPARTMENTS)


def test_matrix_shape():
    usernames = [r["username"] for r in MATRIX]
    assert len(usernames) == len(set(usernames)), "duplicate usernames"
    assert len(MATRIX) == 4 + 7 * 3  # execs+QP + (mgr+2 ops) per dept
    assert all(u.startswith("tt.") for u in usernames)
    assert all(re.fullmatch(r"[a-z0-9.]{3,64}", u) for u in usernames)
    assert all(r["full_name"].startswith("[TEST] ") for r in MATRIX)


def test_roles_and_departments():
    by_role = {}
    for r in MATRIX:
        by_role.setdefault(r["role"], []).append(r)
        assert r["role"] in CREATABLE_ROLES, f"{r['role']} not creatable via the API"
    # executives + QP are department-less
    for u in ("tt.owner", "tt.ceo", "tt.coo", "tt.qp"):
        row = next(r for r in MATRIX if r["username"] == u)
        assert row["dept"] is None
    # exactly one manager of the right role + two USER operators per department
    for code, (seg, mgr_role) in DEPT_KEY.items():
        assert mgr_role in MANAGER_ROLES
        dept_rows = [r for r in MATRIX if r["dept"] == code]
        assert len(dept_rows) == 3
        mgrs = [r for r in dept_rows if r["role"] == mgr_role]
        ops = [r for r in dept_rows if r["role"] == "USER"]
        assert len(mgrs) == 1 and mgrs[0]["username"] == f"tt.{seg}.mgr"
        assert len(ops) == 2
