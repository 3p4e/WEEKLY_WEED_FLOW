"""
SQLAlchemy models for Cannabis EU GMP QMS Creator.
Supports PostgreSQL backend for document and annex storage.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class DocumentStatus(str, enum.Enum):
    """Document status enumeration"""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PLANNED = "planned"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Document(Base):
    """
    Represents a QMS document (SOP, Work Instruction, Form, etc.)
    """

    __tablename__ = "documents"

    id = Column(String(255), primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    department = Column(String(255), nullable=False, index=True)
    status = Column(
        Enum(DocumentStatus), nullable=False, default=DocumentStatus.PLANNED, index=True
    )
    version = Column(String(50), nullable=False)

    # File paths
    pdf_path = Column(String(500), nullable=True)
    docx_path = Column(String(500), nullable=True)

    # Content and metadata
    content = Column(Text, nullable=True)  # Markdown content
    description = Column(Text, nullable=True)
    keywords = Column(String(500), nullable=True)

    # Relationships
    effective_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_modified = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    annexes = relationship(
        "Annex", back_populates="document", cascade="all, delete-orphan"
    )
    chapters = relationship(
        "Chapter", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document(id={self.id}, code={self.code}, title={self.title}, status={self.status})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "department": self.department,
            "status": self.status.value
            if isinstance(self.status, DocumentStatus)
            else self.status,
            "version": self.version,
            "pdf_path": self.pdf_path,
            "docx_path": self.docx_path,
            "effective_date": self.effective_date.isoformat()
            if self.effective_date
            else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "annexes": [a.to_dict() for a in self.annexes] if self.annexes else [],
        }


class Annex(Base):
    """
    Represents an annex or appendix to a document
    """

    __tablename__ = "annexes"

    id = Column(String(255), primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)

    # File paths
    pdf_path = Column(String(500), nullable=True)
    docx_path = Column(String(500), nullable=True)

    # Content
    content = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Relationship to parent document
    document_id = Column(
        String(255),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document = relationship("Document", back_populates="annexes")

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Annex(id={self.id}, code={self.code}, title={self.title})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "pdf_path": self.pdf_path,
            "docx_path": self.docx_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Chapter(Base):
    """
    Represents a chapter or section grouping documents by department
    """

    __tablename__ = "chapters"

    id = Column(String(255), primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    folder = Column(String(100), nullable=True)

    # Relationship to documents
    document_id = Column(
        String(255),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document = relationship("Document", back_populates="chapters")

    # Metadata
    document_count = Column(Integer, default=0)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Chapter(id={self.id}, code={self.code}, name={self.name})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "folder": self.folder,
            "document_count": self.document_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AuditLog(Base):
    """
    Tracks changes to documents for compliance and audit trails
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        String(255),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(100), nullable=False)  # create, update, delete, publish
    old_values = Column(Text, nullable=True)  # JSON string of previous values
    new_values = Column(Text, nullable=True)  # JSON string of new values
    changed_by = Column(String(255), nullable=True)  # User who made the change
    reason = Column(Text, nullable=True)  # Reason for change

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, document_id={self.document_id}, action={self.action})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "action": self.action,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }
