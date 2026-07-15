"""Initial schema for Cannabis EU GMP QMS Creator.

Revision ID: 001
Revises:
Create Date: 2026-01-23 09:40:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create DocumentStatus enum type
    sa.Enum(
        "draft",
        "in_review",
        "approved",
        "planned",
        "completed",
        "archived",
        name="documentstatus",
    ).create(op.get_bind(), checkfirst=True)

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("department", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "in_review",
                "approved",
                "planned",
                "completed",
                "archived",
                name="documentstatus",
            ),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("docx_path", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.String(500), nullable=True),
        sa.Column("effective_date", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_modified", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_documents_code"), "documents", ["code"], unique=False)
    op.create_index(
        op.f("ix_documents_created_at"), "documents", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_documents_department"), "documents", ["department"], unique=False
    )
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    # Create annexes table
    op.create_table(
        "annexes",
        sa.Column("id", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("docx_path", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_annexes_code"), "annexes", ["code"], unique=False)
    op.create_index(
        op.f("ix_annexes_document_id"), "annexes", ["document_id"], unique=False
    )

    # Create chapters table
    op.create_table(
        "chapters",
        sa.Column("id", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("folder", sa.String(100), nullable=True),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_chapters_code"), "chapters", ["code"], unique=False)
    op.create_index(
        op.f("ix_chapters_document_id"), "chapters", ["document_id"], unique=False
    )
    op.create_index(op.f("ix_chapters_name"), "chapters", ["name"], unique=False)

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_document_id"), "audit_logs", ["document_id"], unique=False
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f("ix_audit_logs_document_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_chapters_name"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_document_id"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_code"), table_name="chapters")
    op.drop_table("chapters")

    op.drop_index(op.f("ix_annexes_document_id"), table_name="annexes")
    op.drop_index(op.f("ix_annexes_code"), table_name="annexes")
    op.drop_table("annexes")

    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_department"), table_name="documents")
    op.drop_index(op.f("ix_documents_created_at"), table_name="documents")
    op.drop_index(op.f("ix_documents_code"), table_name="documents")
    op.drop_table("documents")

    sa.Enum(
        "draft",
        "in_review",
        "approved",
        "planned",
        "completed",
        "archived",
        name="documentstatus",
    ).drop(op.get_bind(), checkfirst=True)
