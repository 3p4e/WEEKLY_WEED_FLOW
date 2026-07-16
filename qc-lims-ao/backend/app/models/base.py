"""
Base SQLAlchemy model mixins for GMP-compliant LIMS records.

EU GMP Annex 11 requires:
- Soft delete (is_deleted flag) for all GxP records
- UTC timestamps (created_at, updated_at)
- UUID primary keys for all records
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# Unify on the single declarative base defined in app.core.database so that
# every model registers on the SAME metadata that the lifespan's
# Base.metadata.create_all() uses. Previously this module declared its own
# separate DeclarativeBase, so create_all() on database.Base created zero tables.
from app.core.database import Base as _Base


class TimestampMixin:
    """
    Mixin that adds UTC created_at and updated_at timestamps.

    ALCOA++ 'Contemporaneous' principle: timestamps recorded at time of activity.
    All times stored in UTC per GMP Annex 11 §13 time synchronization requirement.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Record last update timestamp (UTC)",
    )


class SoftDeleteMixin:
    """
    Mixin that adds soft delete support.

    GMP requires records never be hard-deleted. Instead, is_deleted flag
    hides records from normal queries while preserving the audit trail.

    ALCOA++ 'Enduring' principle: records available for full retention period.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Soft delete flag; True = logically deleted, preserved for audit",
    )


class BaseModel(_Base, TimestampMixin, SoftDeleteMixin):
    """
    Base ORM model with UUID primary key, timestamps, and soft delete.

    All GxP-relevant tables MUST inherit from this class.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Universal unique record identifier (UUID v4)",
    )
