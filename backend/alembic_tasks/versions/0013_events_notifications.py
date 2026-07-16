"""events + notifications: activity feed and per-user inbox (Phase-1)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-15

Design per docs/RESEARCH-NOTIFICATIONS-2026-07.md (adversarially-verified
vendor evidence: Linear/GitHub/Asana/Jira/Slack + AS2/FCM):

- `events` — append-only actor-verb-object activity stream (AS2-shaped).
  `params` holds STRUCTURED values only (titles, old/new status); the client
  renders the EN/МК sentence at display time. Append-only is enforced by RLS
  policy shape: only SELECT + INSERT policies exist, so the NOBYPASSRLS app
  role cannot update or delete history.
- `notifications` — per-recipient inbox rows fanned out ON WRITE (max fan-out
  ≈ org size at this scale). Recipient-scoped RLS: you can only ever read or
  update (mark read/done) YOUR OWN rows; inserts are org-checked because the
  acting user writes rows for OTHER recipients. Repeated identical events
  coalesce while an unread row is open: partial UNIQUE on
  (recipient_id, coalesce_key) WHERE read_at IS NULL AND done_at IS NULL,
  written with ON CONFLICT DO NOTHING.

Deliberately NO audit triggers on either table: these are high-churn
awareness/UI-state data, not GMP-adjacent work records — auditing every
mark-read would bloat the hash chain (and serialize through its advisory
lock) for zero traceability value. The underlying work writes remain fully
audited on their own tables.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            actor_id uuid NOT NULL,
            verb text NOT NULL,
            object_type text NOT NULL,
            object_id text NOT NULL,
            task_id uuid,
            department_id uuid,
            params jsonb DEFAULT '{}'::jsonb NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT events_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.events FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY events_read ON public.events FOR SELECT"
        " USING ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE POLICY events_insert ON public.events FOR INSERT"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE INDEX events_org_created_idx ON public.events"
        " USING btree (org_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX events_org_dept_created_idx ON public.events"
        " USING btree (org_id, department_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE public.notifications (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            recipient_id uuid NOT NULL,
            event_id uuid NOT NULL,
            reason text NOT NULL,
            coalesce_key text NOT NULL,
            read_at timestamp with time zone,
            done_at timestamp with time zone,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT notifications_pkey PRIMARY KEY (id),
            CONSTRAINT notifications_event_id_fkey FOREIGN KEY (event_id)
                REFERENCES public.events(id) ON DELETE CASCADE,
            CONSTRAINT notifications_reason_check CHECK (reason = ANY (ARRAY['assigned'::text, 'mentioned'::text, 'comment'::text, 'status'::text, 'due'::text, 'report'::text]))
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.notifications FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY notif_select ON public.notifications FOR SELECT"
        " USING (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id())))"
    )
    op.execute(
        "CREATE POLICY notif_insert ON public.notifications FOR INSERT"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE POLICY notif_update ON public.notifications FOR UPDATE"
        " USING (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id())))"
        " WITH CHECK (((org_id = app.current_org_id()) AND (recipient_id = app.current_user_id())))"
    )
    op.execute(
        "CREATE UNIQUE INDEX notifications_coalesce_idx ON public.notifications"
        " USING btree (recipient_id, coalesce_key)"
        " WHERE ((read_at IS NULL) AND (done_at IS NULL))"
    )
    op.execute(
        "CREATE INDEX notifications_recipient_created_idx ON public.notifications"
        " USING btree (recipient_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX notifications_unread_idx ON public.notifications"
        " USING btree (recipient_id)"
        " WHERE ((read_at IS NULL) AND (done_at IS NULL))"
    )

    # Same guarded grant block as 0007/0011 — CI's pure-alembic build has no
    # app roles; live/test databases do and need the grants immediately.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.events, public.notifications TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.events, public.notifications TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.notifications")
    op.execute("DROP TABLE public.events")
