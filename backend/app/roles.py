"""The user-role taxonomy — one source of truth.

Purely Plant's org model: a system ADMIN (seeded in the DB, never assignable
through the app), two executives, a rank of department managers plus the
Qualified Person, and base staff.

  ADMIN                                    — system administrator (DB-seeded only)
  CEO, COO                                 — executives
  QA_MGR, QC_MGR, PR_MGR, WH_MGR,          — department managers (one rank)
  SC_MGR, CU_MGR, QP                         (QP = Qualified Person)
  USER                                     — department staff / operators

Everything except USER is "elevated" (org-wide task read via RLS + audit
access) — the same meaning ADMIN/DEP_MGR carried before. This module is the
only place the set is defined; the DB CHECK constraint (schema.users.sql) and
app.is_elevated() (both DBs) are generated from migrations that must stay in
sync with ELEVATED_ROLES below, and CI byte-diffs them.
"""

ADMIN = "ADMIN"

EXECUTIVE_ROLES = ("CEO", "COO")

# Department managers + the Qualified Person, all at manager rank. A manager may
# create only USER staff, and only in their own department.
MANAGER_ROLES = ("QA_MGR", "QC_MGR", "PR_MGR", "WH_MGR", "SC_MGR", "CU_MGR", "QP")

USER = "USER"

# Every valid role, in tier order (matches the DB CHECK's ARRAY order).
ALL_ROLES = (ADMIN, *EXECUTIVE_ROLES, *MANAGER_ROLES, USER)

# Elevated = everything but base staff.
ELEVATED_ROLES = tuple(r for r in ALL_ROLES if r != USER)

# Roles that may be assigned through the API. ADMIN is never among them — it is
# seeded directly in the database, never chosen in a role picker.
CREATABLE_ROLES = tuple(r for r in ALL_ROLES if r != ADMIN)
