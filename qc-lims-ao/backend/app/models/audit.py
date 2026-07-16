"""
Audit Trail model for GMP-compliant immutable audit logging.

Per EU GMP Annex 11 §12 — Audit Trail requirements:
- Every GxP-relevant action MUST be logged immutably.
- No UPDATE or DELETE operations on audit records.
- Records retained for full data retention period (10+ years).

ALCOA++ 'Attributable' and 'Contemporaneous' principles:
- Every entry includes user_id, timestamp, and action type.
- Hash chain links each entry to previous for tamper evidence.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AuditAction(StrEnum):
    """Actions logged in the audit trail per Annex 11."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SIGN = "SIGN"
    EXPORT = "EXPORT"
    PRINT = "PRINT"


class AuditEntry(BaseModel):
    """
    Immutable audit log entry for every GxP-relevant action.

    WORM (Write Once Read Many) storage — no UPDATE or DELETE allowed.
    Hash chain provides tamper evidence for regulatory inspection.

    Per 21 CFR Part 11 §11.10(e): audit trail must be secure, computer-generated,
    and time-stamped independently of the operator.
    """

    __tablename__ = "audit_entries"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="UTC timestamp when the action occurred (server-generated)",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="User who performed the action (FK to users.id)",
    )
    user_full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Denormalized user full name for audit readability",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Action type: CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, PRINT",
    )
    record_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Type of record acted upon (e.g., 'coa', 'test_result', 'specification')",
    )
    record_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="ID of the record acted upon (UUID or string identifier)",
    )
    record_identifier: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable record identifier (e.g., PP-COA-2025-0001)",
    )
    field_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Field that was changed (null for CREATE/DELETE/VIEW actions)",
    )
    old_value: Mapped[str | None] = mapped_column(
        String(None),
        nullable=True,
        doc="Previous value before change (encrypted at rest per Annex 11)",
    )
    new_value: Mapped[str | None] = mapped_column(
        String(None),
        nullable=True,
        doc="New value after change",
    )
    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Reason for the change (required for critical changes per Annex 11 §12.4)",
    )
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        doc="Client IP address at time of action",
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Session identifier for correlating actions within a user session",
    )
    digital_signature_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA-256 hash linking this entry to the previous for tamper evidence",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEntry {self.action} on {self.record_type} "
            f"({self.record_identifier}) by user {self.user_id}>"
        )
