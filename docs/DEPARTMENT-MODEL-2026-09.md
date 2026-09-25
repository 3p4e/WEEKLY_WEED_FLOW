# Department model — who does what, and what the system lets them do

**Date:** 2026-09-05 · **Status:** decided by the owner, implemented on
`claude/weekly-read-flow-setup-yft7if` (PR #52) · **Ships as:** users migration
`0012`, tasks migration `0064`, backend `app/`, frontend `web/gf/`.

## Why

An audit of who can do what (2026-09-05) found the permission model did not
describe the facility. The owner's summary was "it's all a mess": the
cultivation manager could not open a room or place a batch, features that
belong to departments lived behind the admin account, and the production
manager had nothing to do. Three of the four audits agreed on the shape of
the problem:

| Finding | Where | Effect |
|---|---|---|
| No cultivation → production boundary. `PR_MGR` appeared in **zero** permission gates; `CU_MGR` owned clone → cut → dry → close end to end. | `harvest.py` `_RECORDERS` | A role with a name and no powers. |
| Rooms were `ADMIN`-only to create or edit — not even the owner. A batch **requires** a room (`plant_batches.room_id NOT NULL`). | `facility.py`, `schema.tasks.sql` | The cultivation manager could create a batch and had nowhere to put it — the gate was one table upstream of where it was felt. |
| Views appear only when their **module** is active; a cultivation manager landing in Tasks saw no cultivation navigation. Admin bypasses modules. | `modules.js` | Department features looked like admin features. |
| `QA_MGR` could not reach the harvest view — yet it is the **only** role that can release a pre-harvest-interval block. | `modules.js` vs `harvest.py` | A power the backend grants and the UI hides. |
| Irrigation existed as a backend record (`irrigation_events`, EC/pH/runoff) gated to cultivation, surfaced only as a tab inside the harvest view. No department, no role, no navigation. | `irrigation.py`, `harvest-view.js` | A record with no owner. |
| Cloning and nursery existed only as batch phases; rooms could be `nursery` but not `clone`; neither phase generated tasks. | `cultivation.py`, `rooms_kind_check` | A clone batch had no clone room to sit in. |
| Departments (a runtime table) and manager roles (a hardcoded tuple) were two unlinked systems. | `roles.py`, `departments` | Adding a department did not create a role — exactly how irrigation ended up ownerless. |

## The model (owner's decisions)

Four points where the description left a genuine choice were put to the
owner; the answers are the model.

**Cultivation (`CU_MGR`)** runs the plant from seed, import or clone up to and
including the **harvest cut**. Cultivars, batches, plants, phase moves, IPM
applications, the cut itself (with `QA_MGR` able to record a cut *only* to
release a PHI block — unchanged).

**Production (`PR_MGR`)** takes the lot **from the cut onward**: the dry
weights, closing the lot, and whatever follows (curing, packaging — not yet
modelled). *Decision: cultivation records the cut, then hands over.* The
post-harvest gate is deliberately **not** a superset of the cut gate: the crew
that cut the plant does not also dry and close it.

**Irrigation (`IR_MGR`, department `irrigation`)** is a department of its own
— the fertigation plant and its distribution to every room. *Decision: only
`IR_MGR` (plus ADMIN and the executives) writes the feed record.* Cultivation
reads it. The routes stay under `/cultivation` because a feed is a record
*about* a cultivation room; who writes it changed, what it is did not.

**Rooms** are opened and edited by **whoever runs them**. *Decision: the
department manager, for their own rooms.* ADMIN and the executives may create
or edit any room, assigned to a department or not. A department manager may
act only on rooms of the kinds their department operates, within their own
department or one of its sub-departments:

| Role | Room kinds |
|---|---|
| `CU_MGR` | `clone`, `nursery`, `veg`, `flower`, `mother` |
| `PR_MGR` | `dry` |
| ADMIN, OWNER, CEO, COO | any (and `other`) |

A room a manager opens is their department's. A legacy room (every room
created before `0064` has no department) stays editable by the manager whose
kind it is, and editing it does **not** claim it; a manager cannot retype a
room into another department's kind, move it to another department, or
unassign it. Only an administrator unassigns.

**Cloning and Nursery are sub-departments of Cultivation.** *Decision: real
child departments* (`departments.parent_id`, which the table already had),
run by the cultivation manager. A department-scoped manager's scope is their
department **and its descendants** — in the task list, the by-id guard every
task route calls, approvals, the audit trail, notifications, AI context,
handoffs, room ownership, and staffing. Scope flows down the tree only: a
manager assigned to `cloning` sees Cloning, not Cultivation.

## What changed

### Schema

- **users `0012`** — `IR_MGR` added to `profiles_role_check` and
  `app.is_elevated()`.
- **tasks `0064`** —
  - `app.is_elevated()` gains `IR_MGR` (the tasks DB keeps its own copy; it
    has fallen out of step with users twice before — see tasks `0009`).
  - `rooms.department_id uuid NULL` → `departments(id) ON DELETE SET NULL`,
    indexed.
  - `rooms_kind_check` admits `clone`.
  - `app.dept_family(root uuid) RETURNS uuid[]` — root plus every descendant
    by `parent_id`, depth-capped at 8 so a cycle terminates; plain SQL,
    STABLE, no SECURITY DEFINER, so it runs under the caller's RLS. Every
    scope predicate that read `t.department_id = $scope` now reads
    `= ANY(app.dept_family($scope))`. An unknown root yields `[root]`, so
    the predicate degrades to the exact match it replaced.
- Both `schema.*.sql` regenerated from `alembic upgrade head` with pg_dump
  16.13; the CI-style normalised diff is clean and `downgrade base` leaves
  zero tables. `alembic_version` is no longer in `schema.tasks.sql` (CI's
  dump excludes it on both sides; it was a leftover of an earlier regen).

### Backend

| File | Change |
|---|---|
| `roles.py` | `IR_MGR` in `MANAGER_ROLES` (so also dept-scoped, elevated, creatable). |
| `deps.py` | `dept_family(c, root)` — the Python-side reading of the SQL function, for places that compare in Python. |
| `harvest.py` | `_POST_HARVEST = (ADMIN, execs, PR_MGR)` gates `/dry` and `/close`. The cut stays `_CUTTERS`; IPM stays `_RECORDERS`. |
| `irrigation.py` | `_RECORDERS = (ADMIN, execs, IR_MGR)`. |
| `facility.py` | `_ROOM_WRITERS`, `_KINDS_BY_ROLE`, `_assert_room_authority`; `department_id` on `RoomIn`/`RoomPatch`/the board; `clone` kind. |
| `tasks.py` | `_assert_scope_visible`, the list filter and `_scope_clause` use `dept_family`; the create guard compares against the family; `POST /departments` accepts `parent_id`. |
| `approvals.py`, `audit.py`, `notifications.py`, `ai.py`, `collab.py` | Scope predicates / comparisons use the family. |
| `auth.py` | `_can_manage` takes the actor's family: a manager staffs their sub-departments too. |
| `demo_org.py` | Departments carry a parent; `cloning`, `nursery` under `cultivation`; `irrigation`; an `IR_MGR` in the cast. |
| `scripts/provision_test_accounts.py` | `irrigation` trio (`tt.ir.*`). Sub-departments get no accounts — they have no manager role of their own. |

**Deliberately unchanged:** the weekly GMP document (`documents.py`) stays
per-department, exact match — a cultivation head compiling Cloning's weekly
record is a new capability nobody asked for. `capture.py` imports into the
actor's own department. Executives, QP and ADMIN are org-wide as before.

### Frontend

| File | Change |
|---|---|
| `modules.js` | Cultivation module admits `QA_MGR` (PHI override) and `IR_MGR`; gains the `irrigation` key. |
| `irrigation-view.js` | **New.** The feeding record, extracted from the harvest view's tab; recorder gate mirrors `IR_MGR`. |
| `harvest-view.js` | Feeding tab removed; dry/close affordances gated on `canPostHarvest` (`PR_MGR`), the cut on `canCut` as before. |
| `facility-view.js` | Rooms writable by `ROOM_WRITERS` within their kinds; `clone` kind; department chooser for ADMIN/execs, implicit for managers; edit button only on rooms the caller may touch. |
| `integrate.js` | Role maps carry `IR_MGR`; `DEPT_STYLE`/`DEPT_ABBR` carry `irrigation` (IR), `cloning` (CL), `nursery` (NU); `GF.DEPTS` rows carry `parent_id`; `GF.WWF.deptFamily`. |
| `dept-templates.js` | `irrigation` template; a sub-department without a template inherits its parent's. |
| `core.js`, `data.js` | Role label and permission row for `ir_mgr`; nav labels for the irrigation view (EN/MK). |

## The matrix after this change

| Capability | ADMIN | OWNER/CEO/COO | CU_MGR | PR_MGR | IR_MGR | QA_MGR | others |
|---|---|---|---|---|---|---|---|
| Create cultivar / batch / plants, move phase | ✅ | ✅ | ✅ | — | — | — | — |
| Record IPM application | ✅ | ✅ | ✅ | — | — | — | — |
| Record the harvest **cut** | ✅ | ✅ | ✅ | — | — | ✅ (PHI release) | — |
| Record **dry weights**, **close** the lot | ✅ | ✅ | — | ✅ | — | — | — |
| Record irrigation / feed | ✅ | ✅ | — | — | ✅ | — | — |
| Open / edit a room | any | any | own kinds, own dept + sub-depts | `dry`, own dept | — | — | — |
| See harvest view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | WH/MU read |
| See a sub-department's tasks | ✅ | ✅ | ✅ (own tree) | — | — | — | — |
| Read all of the above | every role above USER | | | | | | |

## Rollout notes

- **Two migrations, one deploy.** `0012` (users) and `0064` (tasks) go
  together — the same is_elevated drift tasks `0009` describes would
  otherwise reopen for `IR_MGR`.
- **Existing rooms are unassigned.** After deploy, either an administrator
  assigns each room's department on the facility board, or the manager whose
  kind it is edits it (which does not claim it). New rooms a manager opens are
  theirs automatically.
- **Create the departments.** `irrigation`, and `cloning` / `nursery` under
  `cultivation`, via `POST /departments` (ADMIN) — the demo seeder does this
  for the demo org only. Then provision an `IR_MGR` with `department_id` =
  irrigation, or the role has nothing to own.
- **Any existing `CU_MGR` staff who dried and closed lots** lose that on
  deploy by design; give production its manager first.

## Still open (not decided here)

- **Security manager** has the biosecurity module but no write role in
  `decon.py` or `waste.py` — read-only by accident. Grant writes, or drop the
  module: the owner's call.
- **Post-harvest beyond the close** (curing, trimming, packaging) is not
  modelled; `production`'s task template lists those steps as attributes only.
- **Room ↔ phase coupling.** Nothing stops a `flower` batch being created in a
  `dry` room. Worth a validation once rooms carry departments everywhere.
- **Sub-department task templates** inherit Cultivation's; Cloning may want
  its own fields (cutting count, mother batch) once someone runs it.
