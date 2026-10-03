"""department model: IR_MGR in is_elevated, rooms belong to departments, clone rooms, dept_family()

Revision ID: 0064
Revises: 0063
Create Date: 2026-09-05

The owner's review of who does what (2026-09-05) found the model had no seam
where the floor's work actually changes hands, and one gate a full step
upstream of where it was felt. Three schema changes carry the fix; the role
gates themselves live in app code.

1. app.is_elevated() gains IR_MGR — the tasks-DB twin of users migration 0012.
   This function has fallen out of step with the users DB twice before (0009
   explains how); the two migrations ship together.

2. rooms.department_id (nullable, FK departments ON DELETE SET NULL). Rooms
   had no owner, so opening one was ADMIN-only — and a batch REQUIRES a room
   (plant_batches.room_id NOT NULL). The cultivation manager could create a
   batch and had nowhere to put it: the gate that blocked them was on a
   different table from the one they were looking at. A room now belongs to
   the department that runs it, and app/api/facility.py lets that
   department's manager open and edit it. Nullable because every existing
   room is unassigned, and because ADMIN / the executives may still open a
   room that belongs to no department in particular.

3. rooms.kind admits 'clone'. plant_batches.phase has had 'clone' as a phase
   distinct from 'nursery' since 0045, but a room could only be typed
   'nursery' — so a clone batch had no clone room to sit in.

4. app.dept_family(root uuid) RETURNS uuid[] — root plus every descendant by
   departments.parent_id. Cloning and Nursery are SUB-DEPARTMENTS of
   Cultivation, and a department-scoped manager's scope is their department
   AND its descendants: the cultivation head sees, files and manages Cloning
   and Nursery work as their own. Every scope predicate that used to say
   `t.department_id = $scope` now says `= ANY(app.dept_family($scope))`.
   Plain SQL, STABLE, no SECURITY DEFINER — it runs under the caller's RLS,
   so a foreign org's departments are invisible to it. Depth is capped at 8:
   a parent_id cycle (nothing prevents one at the SQL level) terminates
   instead of recursing forever. An unknown or invisible root yields [root],
   so the predicate degrades to the exact-match it replaced.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ELEVATED_NEW = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','IR_MGR','MU_MGR','QP'")
_ELEVATED_OLD = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")

_KINDS_NEW = ("ARRAY['clone'::text, 'nursery'::text, 'veg'::text, 'flower'::text,"
              " 'mother'::text, 'dry'::text, 'other'::text]")
_KINDS_OLD = ("ARRAY['nursery'::text, 'veg'::text, 'flower'::text,"
              " 'mother'::text, 'dry'::text, 'other'::text]")

_DEPT_FAMILY = """
CREATE FUNCTION app.dept_family(root uuid) RETURNS uuid[]
    LANGUAGE sql STABLE
    AS $$
  WITH RECURSIVE fam(id, depth) AS (
    SELECT d.id, 0 FROM public.departments d WHERE d.id = root
    UNION ALL
    SELECT d.id, fam.depth + 1
      FROM public.departments d JOIN fam ON d.parent_id = fam.id
     WHERE fam.depth < 8
  )
  SELECT coalesce(array_agg(DISTINCT id), ARRAY[root]) FROM fam
$$;
"""


def upgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")

    op.execute("ALTER TABLE public.rooms ADD COLUMN department_id uuid")
    op.execute("ALTER TABLE public.rooms ADD CONSTRAINT rooms_department_id_fkey"
               " FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX rooms_department_id_idx ON public.rooms USING btree (department_id)")

    op.execute("ALTER TABLE public.rooms DROP CONSTRAINT rooms_kind_check")
    op.execute("ALTER TABLE public.rooms ADD CONSTRAINT rooms_kind_check"
               f" CHECK ((kind = ANY ({_KINDS_NEW})))")

    op.execute(_DEPT_FAMILY)


def downgrade() -> None:
    op.execute("DROP FUNCTION app.dept_family(uuid)")

    # A clone room has no pre-0064 kind; nursery is the phase it split from.
    op.execute("UPDATE public.rooms SET kind='nursery' WHERE kind='clone'")
    op.execute("ALTER TABLE public.rooms DROP CONSTRAINT rooms_kind_check")
    op.execute("ALTER TABLE public.rooms ADD CONSTRAINT rooms_kind_check"
               f" CHECK ((kind = ANY ({_KINDS_OLD})))")

    op.execute("DROP INDEX public.rooms_department_id_idx")
    op.execute("ALTER TABLE public.rooms DROP CONSTRAINT rooms_department_id_fkey")
    op.execute("ALTER TABLE public.rooms DROP COLUMN department_id")

    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_OLD}) $$")
