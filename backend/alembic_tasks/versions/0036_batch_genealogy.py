"""URS alignment: batch genealogy chain (Phase-2 item 5, decision D2 = blending).

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-21

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 5 — the batch lineage
variety → cultivation (AB…) → processing (P…) → packaging batch, with
CoQ-level inheritance of ancestor-batch results (QCSOP 012 D3: a finished-
product CoQ inherits the intermediate/bulk batch results).

Decision D2 (blending): SUPPORTED as an **m:n** graph — a batch may have
multiple parents (a blended packaging lot drawn from several processing lots)
and multiple children. A 1:n tree is just the special case. `qc_batch_genealogy`
holds directed parent→child edges between batch codes (the domain already keys
work by the free-text `batch_id`, so an edge references codes, not a new batch
entity). The application guards against cycles before inserting an edge. Edges
are relationship metadata (not immutable certificates), so they are editable/
deletable by a writer and fully audited by the shared trigger.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RELATIONS = ("CULTIVATION", "PROCESSING", "PACKAGING", "BLEND", "GENERIC")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_batch_genealogy (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            parent_batch_id text NOT NULL,
            child_batch_id text NOT NULL,
            relation text DEFAULT 'GENERIC'::text NOT NULL,
            quantity numeric,
            unit text,
            notes text,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_batch_genealogy_pkey PRIMARY KEY (id),
            CONSTRAINT qc_batch_genealogy_edge_key UNIQUE (org_id, parent_batch_id, child_batch_id),
            CONSTRAINT qc_batch_genealogy_no_self CHECK ((parent_batch_id <> child_batch_id)),
            CONSTRAINT qc_batch_genealogy_relation_check CHECK ((relation = ANY (ARRAY[%s])))
        )
        """
        % ",".join(f"'{r}'::text" for r in _RELATIONS)
    )
    op.execute("ALTER TABLE ONLY public.qc_batch_genealogy FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_batch_genealogy ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_batch_genealogy"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_batch_genealogy AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_batch_genealogy FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX qc_batch_genealogy_child_idx ON public.qc_batch_genealogy"
        " USING btree (org_id, child_batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_batch_genealogy_parent_idx ON public.qc_batch_genealogy"
        " USING btree (org_id, parent_batch_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_batch_genealogy TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_batch_genealogy TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_batch_genealogy")
