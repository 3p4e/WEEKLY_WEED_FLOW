"""
User model for LIMS authentication and role-based access control.

EU GMP Annex 11 requires:
- Unique user identification
- Role-based access with documented training
- Password complexity and periodic expiry
- Two-component electronic signatures for approval actions
"""

from enum import StrEnum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class UserRole(StrEnum):
    """Defined user roles per QCSOP 001."""

    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    QC_ANALYST = "QC_ANALYST"
    QC_REVIEWER = "QC_REVIEWER"
    QC_MANAGER = "QC_MANAGER"
    QP = "QP"
    QA_AUDITOR = "QA_AUDITOR"


class User(BaseModel):
    """
    LIMS user account.

    Passwords hashed with bcrypt. Role determines permissions.
    Inactive users cannot authenticate.
    Soft-deleted users are preserved for audit trail.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        doc="Unique login username"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Bcrypt-hashed password"
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="User's full name for audit trail attribution"
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default=UserRole.QC_ANALYST.value,
        doc="Role-based access control role"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True,
        doc="Email for notifications and password reset"
    )
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True,
        doc="Google OAuth subject identifier (sub claim)"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        doc="URL to user's avatar image from identity provider"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        doc="False = account deactivated (preserved for audit)"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"
