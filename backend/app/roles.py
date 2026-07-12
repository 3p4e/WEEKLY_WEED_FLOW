"""The user-role taxonomy — one source of truth.

Purely Plant's org model: a system ADMIN (seeded in the DB, never assignable
through the app), the business OWNER plus two executives, a rank of
department managers plus the Qualified Person, and base staff.

  ADMIN                                    — system administrator (DB-seeded only)
  OWNER, CEO, COO                          — executives (OWNER = the business owner)
  QA_MGR, QC_MGR, PR_MGR, WH_MGR,          — department managers (one rank)
  SE_MGR, CU_MGR, MU_MGR, QP                (QP = Qualified Person)
  USER                                     — department staff / operators

Everything except USER is "elevated" (org-wide task read via RLS + audit
access) — the same meaning ADMIN/DEP_MGR carried before. This module is the
only place the set is defined; the DB CHECK constraint (schema.users.sql) and
app.is_elevated() (both DBs) are generated from migrations that must stay in
sync with ELEVATED_ROLES below, and CI byte-diffs them.
"""

ADMIN = "ADMIN"

# OWNER is a cross-org executive like CEO/COO — no department, elevated read,
# but (like CEO/COO today) not a provisioning role: only ADMIN and the
# department managers may create/edit/delete accounts (see auth.py's
# require_role(ADMIN, *MANAGER_ROLES) gates).
EXECUTIVE_ROLES = ("OWNER", "CEO", "COO")

# Department managers + the Qualified Person, all at manager rank. A manager may
# create only USER staff, and only in their own department.
MANAGER_ROLES = ("QA_MGR", "QC_MGR", "PR_MGR", "WH_MGR", "SE_MGR", "CU_MGR", "MU_MGR", "QP")

# Department managers whose task access is scoped to their own department (plus
# tasks they personally own or are assigned): GET /tasks and /reports/weekly
# force department_id = the manager's department. QP is manager rank but
# certifies batches across every department, so it stays org-wide; executives
# and ADMIN are org-wide by definition.
#
# ⚠️ CRITICAL: department scoping for these roles is enforced ENTIRELY at the
# application layer, NOT by RLS. app.is_elevated() (the tasks_read/tasks_write
# policies) treats every manager role as org-wide, so the database grants a
# dept-scoped manager org-wide read AND write on tasks/task_*. That org-wide DB
# grant is intentional (audit, documents, collaboration need it) — but it means
# EVERY endpoint that touches a task by id, on BOTH the read and the write side,
# MUST call tasks._assert_scope_visible(c, task_id, user) to re-impose the
# department boundary. Forgetting it silently reopens a cross-department
# read/write bypass (this has already happened twice). test_dept_scope.py's
# test_every_task_id_route_calls_the_scope_guard enforces this structurally.
DEPT_SCOPED_ROLES = tuple(r for r in MANAGER_ROLES if r != "QP")

USER = "USER"

# Every valid role, in tier order (matches the DB CHECK's ARRAY order).
ALL_ROLES = (ADMIN, *EXECUTIVE_ROLES, *MANAGER_ROLES, USER)

# Elevated = everything but base staff.
ELEVATED_ROLES = tuple(r for r in ALL_ROLES if r != USER)

# Roles that may be assigned through the API. ADMIN is never among them — it is
# seeded directly in the database, never chosen in a role picker.
CREATABLE_ROLES = tuple(r for r in ALL_ROLES if r != ADMIN)
