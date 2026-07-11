"""weekly_documents: per-department documents (nullable department_id)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-11

The Document Engine stored ONE document per (org, kind, week) — org-wide by
definition. With department managers now scoped to their own department, a
manager's compile must produce a DEPARTMENT document without overwriting the
org-wide weekly record (the submitted GMP record).

department_id NULL = the org-wide document (every pre-existing row). The old
UNIQUE (org_id, kind, week_start) is replaced by two partial unique indexes so
the org-wide document and each department's document coexist for the same week:

  - (org_id, kind, week_start)                WHERE department_id IS NULL
  - (org_id, kind, week_start, department_id) WHERE department_id IS NOT NULL

The compile UPSERT must target these via the inference form WITH the matching
WHERE predicate (a plain ON CONFLICT (org_id, kind, week_start) no longer
matches any constraint). No RLS change: 0008's wd_* policies reference only
org_id + status. No GRANT change: 0007's table-level grants cover new columns.

DOWNGRADE IS DESTRUCTIVE for per-department rows: restoring the old UNIQUE
constraint requires deleting every department document first (they would
collide with the org-wide row's uniqueness domain). Acceptable — downgrade is
a CI probe, not an operational path.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.weekly_documents ADD COLUMN department_id uuid")
    op.execute("ALTER TABLE public.weekly_documents"
               " DROP CONSTRAINT weekly_documents_org_kind_week_key")
    op.execute("CREATE UNIQUE INDEX weekly_documents_org_kind_week_dept_key"
               " ON public.weekly_documents USING btree (org_id, kind, week_start, department_id)"
               " WHERE (department_id IS NOT NULL)")
    op.execute("CREATE UNIQUE INDEX weekly_documents_org_kind_week_orgwide_key"
               " ON public.weekly_documents USING btree (org_id, kind, week_start)"
               " WHERE (department_id IS NULL)")


def downgrade() -> None:
    op.execute("DELETE FROM public.weekly_documents WHERE department_id IS NOT NULL")
    op.execute("DROP INDEX public.weekly_documents_org_kind_week_dept_key")
    op.execute("DROP INDEX public.weekly_documents_org_kind_week_orgwide_key")
    op.execute("ALTER TABLE public.weekly_documents"
               " ADD CONSTRAINT weekly_documents_org_kind_week_key"
               " UNIQUE (org_id, kind, week_start)")
    op.execute("ALTER TABLE public.weekly_documents DROP COLUMN department_id")
