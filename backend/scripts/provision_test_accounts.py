#!/usr/bin/env python3
"""Provision the tt.* test-account matrix on a WWF deployment — API-only.

Creates the 7 canonical departments (idempotently, via the ADMIN-only
POST /departments) and ~25 test accounts covering every role tier:

    tt.owner / tt.ceo / tt.coo      OWNER / CEO / COO   (no department)
    tt.qp                           QP                  (no department)
    tt.<dept>.mgr                   <DEPT>_MGR          (x7)
    tt.<dept>.op1 / tt.<dept>.op2   USER                (x14)

Everything goes through the real HTTP API — never direct SQL — so the
hash-chained audit trail records every provisioning action exactly as it
would a human admin's. Idempotent: reruns skip existing tt.* accounts and
existing departments.

SAFETY: if the live /departments codes DEVIATE from the canonical 7 (any
unknown code present), the script prints the diff and ABORTS instead of
risking semantic duplicates (e.g. a live 'warehouse' next to a canonical
'logistics'). Missing departments are created; extra ones are never touched.

Usage:
    WWF_ADMIN_PASSWORD=... python provision_test_accounts.py \
        [--base-url https://wwf.srv1231216.hstgr.cloud] [--admin-user USERNAME]
        [--set-passwords]   # complete each account's forced first login
        [--cleanup]         # soft-delete every tt.* account (confirm prompt)

Credentials (username / OTP / password) are written to
test_accounts.local.json (mode 0600, gitignored) next to this script's CWD.
The hard DELETE /auth/users/{id}/purge remains a deliberate MANUAL
pre-production step — see docs/TEST-ACCOUNTS.md.
"""
import argparse
import getpass
import json
import os
import secrets
import stat
import sys
import time

DEFAULT_BASE_URL = "https://wwf.srv1231216.hstgr.cloud"
STATE_FILE = "test_accounts.local.json"

# The canonical TOP-LEVEL departments — codes/names as app/demo_org.py's
# _DEPARTMENTS. Cloning and Nursery are sub-departments of Cultivation there
# and have no manager role of their own (the cultivation manager runs them),
# so they get no account trio here.
DEPARTMENTS = [
    {"code": "cultivation",       "name": "Cultivation",       "name_mk": "Одгледување"},
    {"code": "irrigation",        "name": "Irrigation",        "name_mk": "Наводнување"},
    {"code": "production",        "name": "Production",        "name_mk": "Производство"},
    {"code": "qc",                "name": "Quality Control",   "name_mk": "Контрола на квалитет"},
    {"code": "quality_assurance", "name": "Quality Assurance", "name_mk": "Обезбедување квалитет"},
    {"code": "logistics",         "name": "Warehouse",         "name_mk": "Магацин"},
    {"code": "security",          "name": "Security",          "name_mk": "Обезбедување"},
    {"code": "tooling",           "name": "Maintenance",       "name_mk": "Одржување"},
]

# dept code -> (username segment, manager role) — segments match the role
# prefixes (CU/IR/PR/QC/QA/WH/SE/MU) so tt.qc.mgr obviously pairs with QC_MGR.
DEPT_KEY = {
    "cultivation": ("cu", "CU_MGR"),
    "irrigation": ("ir", "IR_MGR"),
    "production": ("pr", "PR_MGR"),
    "qc": ("qc", "QC_MGR"),
    "quality_assurance": ("qa", "QA_MGR"),
    "logistics": ("wh", "WH_MGR"),
    "security": ("se", "SE_MGR"),
    "tooling": ("mu", "MU_MGR"),
}

_CAST = {
    "cu": ("Goran Dimitrov", "Ile Trajkovski", "Sara Petreska"),
    "ir": ("Vlatko Manev", "Ana Izvorska", "Mitko Reskov"),
    "pr": ("Marija Ristova", "Dejan Stankov", "Bojana Miteva"),
    "qc": ("Blagoj Testov", "Kiril Angelov", "Teodora Naumova"),
    "qa": ("Vesna Georgieva", "Filip Karev", "Ivana Zdravkova"),
    "wh": ("Zoran Peev", "Aleksandar Kotev", "Milena Ristovska"),
    "se": ("Stefan Nakov", "Darko Cvetanov", "Igor Pavlov"),
    "mu": ("Nikola Andonov", "Vlado Serafimov", "Petar Josifov"),
}


def build_matrix() -> list[dict]:
    """The full account matrix — pure data, unit-tested offline."""
    rows = [
        {"username": "tt.owner", "full_name": "[TEST] Viktor Petrov", "role": "OWNER", "dept": None},
        {"username": "tt.ceo", "full_name": "[TEST] Elena Stojanova", "role": "CEO", "dept": None},
        {"username": "tt.coo", "full_name": "[TEST] Marko Iliev", "role": "COO", "dept": None},
        {"username": "tt.qp", "full_name": "[TEST] Ana Kostova", "role": "QP", "dept": None},
    ]
    for dept in DEPARTMENTS:
        code = dept["code"]
        seg, mgr_role = DEPT_KEY[code]
        mgr, op1, op2 = _CAST[seg]
        rows.append({"username": f"tt.{seg}.mgr", "full_name": f"[TEST] {mgr}", "role": mgr_role, "dept": code})
        rows.append({"username": f"tt.{seg}.op1", "full_name": f"[TEST] {op1}", "role": "USER", "dept": code})
        rows.append({"username": f"tt.{seg}.op2", "full_name": f"[TEST] {op2}", "role": "USER", "dept": code})
    return rows


MATRIX = build_matrix()


# ── HTTP plumbing (import httpx lazily so the offline matrix test needs nothing) ──

def _client(base_url):
    import httpx
    return httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=False)


def login(c, username, password) -> tuple[str, dict]:
    r = c.post("/auth/login", json={"email": username, "password": password})
    if r.status_code != 200:
        sys.exit(f"login as {username!r} failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def ensure_departments(c, token) -> dict:
    """Verify live codes ⊆ canonical, create the missing ones, return code→id."""
    r = c.get("/departments", headers=_auth(token))
    r.raise_for_status()
    live = {d["code"]: d for d in r.json()}
    canonical = {d["code"] for d in DEPARTMENTS}
    unknown = sorted(set(live) - canonical)
    if unknown:
        print("LIVE DEPARTMENT CODES DEVIATE FROM THE CANONICAL 7 — refusing to continue.")
        print(f"  canonical : {sorted(canonical)}")
        print(f"  live      : {sorted(live)}")
        print(f"  unknown   : {unknown}")
        print("Resolve the deviation manually (rename/retire the unknown codes or update")
        print("this script's DEPARTMENTS constant deliberately), then rerun.")
        sys.exit(2)
    for spec in DEPARTMENTS:
        if spec["code"] in live:
            continue
        r = c.post("/departments", json=spec, headers=_auth(token))
        if r.status_code not in (200, 201):
            sys.exit(f"POST /departments {spec['code']} failed: {r.status_code} {r.text[:200]}")
        live[spec["code"]] = r.json()
        print(f"  + department {spec['code']}")
    return {code: d["id"] for code, d in live.items()}


def load_state(path=STATE_FILE) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"accounts": {}}


def save_state(state, path=STATE_FILE):
    with open(path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 — credentials live here
    print(f"credentials written to {path} (0600)")


def _post_with_429_retry(c, path, payload, headers, what):
    """The API throttles auth mutations (20 per 5-minute window per actor) —
    wait the window out instead of dying mid-run."""
    while True:
        r = c.post(path, json=payload, headers=headers)
        if r.status_code != 429:
            return r
        print(f"  … throttled on {what} — waiting 75s for the window")
        time.sleep(75)


def provision(c, token, dept_ids, state):
    r = c.get("/auth/users", headers=_auth(token))
    r.raise_for_status()
    server_users = {u["username"]: u for u in r.json()}
    created = recovered = 0
    for row in MATRIX:
        u = row["username"]
        if u in server_users:
            rec = state["accounts"].get(u)
            if rec and (rec.get("otp") or rec.get("password")):
                print(f"  = {u} exists — skipped")
                continue
            # Account exists but this state file has no credential for it (a
            # previous run died before saving) — mint a fresh OTP.
            r = _post_with_429_retry(c, f"/auth/users/{server_users[u]['id']}/reset-password",
                                     None, _auth(token), f"reset {u}")
            if r.status_code != 200:
                sys.exit(f"reset-password {u} failed: {r.status_code} {r.text[:200]}")
            state["accounts"][u] = {"full_name": row["full_name"], "role": row["role"],
                                    "department": row["dept"], "otp": r.json()["otp"], "password": None}
            save_state(state)
            recovered += 1
            print(f"  ~ {u} existed without saved credentials — new OTP captured")
            continue
        payload = {"username": u, "full_name": row["full_name"], "role": row["role"],
                   "department_id": dept_ids[row["dept"]] if row["dept"] else None}
        r = _post_with_429_retry(c, "/auth/users", payload, _auth(token), f"create {u}")
        if r.status_code != 201:
            sys.exit(f"POST /auth/users {u} failed: {r.status_code} {r.text[:200]}")
        state["accounts"][u] = {"full_name": row["full_name"], "role": row["role"],
                                "department": row["dept"], "otp": r.json()["otp"], "password": None}
        save_state(state)   # incremental — a mid-run death never loses OTPs again
        created += 1
        print(f"  + {u} ({row['role']}) otp captured")
    print(f"{created} created, {recovered} recovered, {len(MATRIX) - created - recovered} already provisioned")


def set_passwords(c, state):
    """Complete each account's forced first login (conftest.login_and_set_password
    pattern): OTP login → change-password → verify real login."""
    done = 0
    for username, rec in state["accounts"].items():
        if rec.get("password") or not rec.get("otp"):
            continue
        new_pw = "Tt-" + secrets.token_urlsafe(12)
        r = c.post("/auth/login", json={"email": username, "password": rec["otp"]})
        if r.status_code != 200:
            print(f"  ! {username}: OTP login failed ({r.status_code}) — OTP used already? skipped")
            continue
        tmp = r.json()["access_token"]
        r = c.post("/auth/change-password", json={"new_password": new_pw}, headers=_auth(tmp))
        if r.status_code != 200:
            print(f"  ! {username}: change-password failed ({r.status_code}) — skipped")
            continue
        r = c.post("/auth/login", json={"email": username, "password": new_pw})
        if r.status_code != 200:
            print(f"  ! {username}: verification login failed ({r.status_code})")
            continue
        rec["password"] = new_pw
        rec["otp"] = None  # consumed
        done += 1
        print(f"  ✓ {username} password set")
    print(f"{done} account(s) completed first login")


def cleanup(c, token):
    r = c.get("/auth/users", headers=_auth(token))
    r.raise_for_status()
    targets = [u for u in r.json() if u["username"].startswith("tt.")]
    if not targets:
        print("no tt.* accounts found — nothing to clean up")
        return
    print("About to SOFT-DELETE these accounts (audit rows persist; hard purge stays manual):")
    for u in targets:
        print(f"  - {u['username']} ({u['role']})")
    if input("type 'yes' to confirm: ").strip().lower() != "yes":
        sys.exit("aborted")
    for u in targets:
        r = c.delete(f"/auth/users/{u['id']}", headers=_auth(token))
        print(f"  {'✓' if r.status_code in (200, 204) else '!'} {u['username']} ({r.status_code})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.environ.get("WWF_BASE_URL", DEFAULT_BASE_URL))
    ap.add_argument("--admin-user", default=os.environ.get("WWF_ADMIN_USER"))
    ap.add_argument("--set-passwords", action="store_true")
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    admin_user = args.admin_user or input("admin username: ").strip()
    # Password via env or prompt — NEVER argv (visible in `ps`/shell history).
    admin_pw = os.environ.get("WWF_ADMIN_PASSWORD") or getpass.getpass(f"password for {admin_user}: ")

    c = _client(args.base_url)
    token, me = login(c, admin_user, admin_pw)
    if me.get("role") != "ADMIN":
        sys.exit(f"{admin_user!r} is {me.get('role')!r} — department creation requires ADMIN")
    print(f"signed in as {admin_user} on {args.base_url}")

    if args.cleanup:
        cleanup(c, token)
        return

    state = load_state()
    dept_ids = ensure_departments(c, token)
    provision(c, token, dept_ids, state)
    save_state(state)
    if args.set_passwords:
        set_passwords(c, state)
        save_state(state)


if __name__ == "__main__":
    main()
