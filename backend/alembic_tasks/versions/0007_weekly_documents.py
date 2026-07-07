"""weekly_documents: compiled Plan & Report documents with a lock lifecycle

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06

The weekly Plan/Report stops being a transient screen: compiling one now
produces a stored document (full task snapshot, work-session ribbon,
metrics, and AI-drafted sections) that the user reviews, may edit while
in draft, then LOCKS as the submitted record for that week. Locked
documents are immutable at the application layer and, like every other
work table, covered by the append-only audit trigger — a real submission
trail. One document per (org, kind, week).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.weekly_documents (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            kind text NOT NULL,
            week_start date NOT NULL,
            week_end date NOT NULL,
            content jsonb DEFAULT '{}'::jsonb NOT NULL,
            status text DEFAULT 'draft'::text NOT NULL,
            created_by uuid,
            locked_by uuid,
            locked_at timestamp with time zone,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT weekly_documents_pkey PRIMARY KEY (id),
            CONSTRAINT weekly_documents_kind_check CHECK (kind = ANY (ARRAY['plan'::text, 'report'::text])),
            CONSTRAINT weekly_documents_status_check CHECK (status = ANY (ARRAY['draft'::text, 'locked'::text])),
            CONSTRAINT weekly_documents_org_kind_week_key UNIQUE (org_id, kind, week_start)
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.weekly_documents FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.weekly_documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.weekly_documents"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_weekly_documents AFTER INSERT OR DELETE OR UPDATE"
        " ON public.weekly_documents FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX weekly_documents_org_week_idx ON public.weekly_documents"
        " USING btree (org_id, week_start)"
    )
    # The app_user/app_admin GRANTs are otherwise a one-time bootstrap step
    # (see backend/README.md) that predates this table — without this, every
    # request against a freshly-migrated (not freshly schema.sql-loaded)
    # database hits "permission denied for table weekly_documents". Guarded
    # because those roles don't exist in the CI job that diffs a pure
    # `alembic upgrade head` against schema.tasks.sql.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.weekly_documents TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.weekly_documents TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.weekly_documents")
