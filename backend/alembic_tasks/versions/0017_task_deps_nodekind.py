"""TMS T1: task dependency graph + node_kind (harvest from qc-lims-ao)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-16

Unification TMS phase T1 — additively fold the qc-lims-ao prototype's richer
task structure into the live model. The delta analysis (WWF already has the
parent_id tree, task_assignees.accepted /ack accept-decline, outcome, and the
handoffs table) showed only two genuine storage gaps:

- `tasks.node_kind` — the tree's node ROLE (task | annex | step), distinct
  from `task_type` (the domain category capa/sop/...). Lets the tree render a
  document→annex→step spine, not just parent/child tasks. Additive column,
  defaulted so every existing row is a plain 'task'.
- `task_dependencies` — a real blocker graph. WWF had only free-text
  `blocker_reason`; this is the first structured "X is blocked by Y" edge set,
  enabling a blocked-by / critical-path view. Same org-isolation RLS +
  hash-chained audit trigger + guarded grants as every other work table
  (0015 pattern). It carries an `id` surrogate PK because the shared audit
  trigger (app.fn_audit_row) records `NEW.id` — a composite-only PK would
  break it; the edge itself is kept unique via task_dependencies_edge_key. A
  self-dependency is rejected; both endpoints FK into tasks with ON DELETE
  CASCADE so deleting a task cannot orphan an edge.

The handoffs table already exists (schema.tasks.sql) with a richer 4-state
lifecycle than the prototype — T1 only surfaces it via new API, no migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- additive: node_kind on tasks ----
    op.execute(
        "ALTER TABLE public.tasks ADD COLUMN node_kind text NOT NULL DEFAULT 'task'"
    )
    op.execute(
        "ALTER TABLE public.tasks ADD CONSTRAINT tasks_node_kind_check "
        "CHECK (node_kind = ANY (ARRAY['task'::text, 'annex'::text, 'step'::text]))"
    )

    # ---- new: task dependency graph ----
    op.execute(
        """
        CREATE TABLE public.task_dependencies (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            task_id uuid NOT NULL,
            depends_on_task_id uuid NOT NULL,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT task_dependencies_pkey PRIMARY KEY (id),
            CONSTRAINT task_dependencies_edge_key UNIQUE (task_id, depends_on_task_id),
            CONSTRAINT task_dependencies_no_self CHECK (task_id <> depends_on_task_id),
            CONSTRAINT task_dependencies_task_fkey FOREIGN KEY (task_id)
                REFERENCES public.tasks(id) ON DELETE CASCADE,
            CONSTRAINT task_dependencies_dep_fkey FOREIGN KEY (depends_on_task_id)
                REFERENCES public.tasks(id) ON DELETE CASCADE
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.task_dependencies FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.task_dependencies ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.task_dependencies"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_task_dependencies AFTER INSERT OR DELETE OR UPDATE"
        " ON public.task_dependencies FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX task_dependencies_dep_idx ON public.task_dependencies"
        " USING btree (org_id, depends_on_task_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.task_dependencies TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.task_dependencies TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.task_dependencies")
    op.execute("ALTER TABLE public.tasks DROP CONSTRAINT tasks_node_kind_check")
    op.execute("ALTER TABLE public.tasks DROP COLUMN node_kind")
