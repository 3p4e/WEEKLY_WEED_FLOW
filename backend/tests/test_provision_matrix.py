"""Offline validation of the tt.* provisioning matrix — pure data, no HTTP.

Pins the invariants docs/TEST-ACCOUNTS.md promises: the canonical TOP-LEVEL
departments (codes exactly matching app/demo_org.py), 1 manager + 2 operators
per department, executives/QP department-less, every role a valid CREATABLE
role (never ADMIN). Sub-departments (Cloning and Nursery under Cultivation)
have no manager role of their own — the cultivation manager runs them — so
they get no account trio.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from provision_test_accounts import DEPARTMENTS, DEPT_KEY, MATRIX  # noqa: E402

from app.roles import CREATABLE_ROLES, MANAGER_ROLES  # noqa: E402

CANONICAL = ["cultivation", "irrigation", "production", "qc", "quality_assurance",
             "logistics", "security", "tooling"]


def test_top_level_departments_match_demo_org():
    assert [d["code"] for d in DEPARTMENTS] == CANONICAL
    # The live demo seeds these same departments server-side (app/demo_org.py),
    # plus the sub-departments, which provisioning deliberately skips.
    from app.demo_org import _DEPARTMENTS
    top = [code for code, _en, _mk, parent in _DEPARTMENTS if parent is None]
    assert top == CANONICAL
    # A sub-department hangs off a TOP-LEVEL parent that precedes it in the
    # tuple — the seeder resolves parent_id from what it has already inserted.
    seen = set()
    for code, en, mk, parent in _DEPARTMENTS:
        assert en and mk, code
        if parent is not None:
            assert parent in seen and parent in CANONICAL, (code, parent)
        seen.add(code)
    assert {c for c, _e, _m, p in _DEPARTMENTS if p == "cultivation"} == {"cloning", "nursery"}
    assert all(d["name"] and d["name_mk"] for d in DEPARTMENTS)


def test_matrix_shape():
    usernames = [r["username"] for r in MATRIX]
    assert len(usernames) == len(set(usernames)), "duplicate usernames"
    assert len(MATRIX) == 4 + 8 * 3  # execs+QP + (mgr+2 ops) per top-level dept
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
