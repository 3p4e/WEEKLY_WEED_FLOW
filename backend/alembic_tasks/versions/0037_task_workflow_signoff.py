"""SUMA v2 assimilation: task workflow sign-off (submit→approve/reject + QP block).

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-21

The last un-incorporated delta from the SUMA ISO17025 corpus: its v2
workflow_state / task_remarks / QP-block layer was provisioned-but-unwired even
in SUMA, and the WWF `tasks.workflow_state` column has sat inert (default
'draft', raw passthrough) since the v2 baseline. This activates it:

  draft → submitted → approved | rejected (rejected → resubmittable)
  qp_blocked: a QP/ADMIN quality hold from any state; lifting returns to draft
  (rework + resubmission after a quality block — the conservative reading).

`task_workflow_events` is the append-only sign-off record: one row per
transition carrying the action, the from/to states, the actor (plain uuid —
users live in the separate users DB — plus a role snapshot), and the remark
(mandatory on reject/block). It doubles as the SUMA task_remarks log, kept
separate from free-form task_comments so the sign-off record stays a record.

No CHECK constraint is added to tasks.workflow_state itself: the column was a
free-text passthrough, so live rows may hold arbitrary historical strings and a
constraint could fail the migration; the lifecycle is enforced in the app (the
passthrough is removed in the same increment) and every transition is evidenced
here. Additive + reversible.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIONS = ("SUBMIT", "APPROVE", "REJECT", "BLOCK", "UNBLOCK")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.task_workflow_events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            task_id uuid NOT NULL,
            action text NOT NULL,
            from_state text NOT NULL,
            to_state text NOT NULL,
            actor_id uuid NOT NULL,
            actor_role text,
            remark text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT task_workflow_events_pkey PRIMARY KEY (id),
            CONSTRAINT task_workflow_events_action_check CHECK ((action = ANY (ARRAY[%s])))
        )
        """
        % ",".join(f"'{a}'::text" for a in _ACTIONS)
    )
    op.execute(
        "ALTER TABLE ONLY public.task_workflow_events ADD CONSTRAINT task_workflow_events_task_fkey"
        " FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE"
    )
    op.execute("ALTER TABLE ONLY public.task_workflow_events FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.task_workflow_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.task_workflow_events"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_task_workflow_events AFTER INSERT OR DELETE OR UPDATE"
        " ON public.task_workflow_events FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX task_workflow_events_task_idx ON public.task_workflow_events"
        " USING btree (org_id, task_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.task_workflow_events TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.task_workflow_events TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.task_workflow_events")
