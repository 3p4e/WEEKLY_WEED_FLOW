#!/usr/bin/env python3
"""
Database seeding script for Cannabis EU GMP QMS Creator.

This script creates sample documents, annexes, and chapters for testing
and demonstration purposes.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from CONTENT_CREATOR_FRAMEWORK.database.models import (
    Annex,
    AuditLog,
    Base,
    Document,
    DocumentChapter,
)
from CONTENT_CREATOR_FRAMEWORK.database.session import DatabaseManager


def seed_documents(db: Session) -> list[str]:
    """Create sample documents."""
    documents_data = [
        {
            "id": "doc-001",
            "code": "SOP-001",
            "title": "Standard Operating Procedure - Cultivation",
            "department": "Cultivation",
            "version": "1.0",
            "status": "approved",
            "description": "Main SOP for cannabis cultivation operations",
        },
        {
            "id": "doc-002",
            "code": "SOP-002",
            "title": "Standard Operating Procedure - Quality Assurance",
            "department": "Quality Assurance",
            "version": "1.0",
            "status": "approved",
            "description": "Quality assurance procedures for all operations",
        },
        {
            "id": "doc-003",
            "code": "SOP-003",
            "title": "Standard Operating Procedure - Safety",
            "department": "Safety",
            "version": "2.0",
            "status": "approved",
            "description": "Safety procedures and hazard management",
        },
        {
            "id": "doc-004",
            "code": "SOP-004",
            "title": "Standard Operating Procedure - Personnel",
            "department": "Human Resources",
            "version": "1.0",
            "status": "approved",
            "description": "Personnel management and training procedures",
        },
        {
            "id": "doc-005",
            "code": "POL-001",
            "title": "Company Policy - Document Control",
            "department": "Quality Assurance",
            "version": "1.5",
            "status": "approved",
            "description": "Policy for document creation, review, and approval",
        },
        {
            "id": "doc-006",
            "code": "FORM-001",
            "title": "Inspection Checklist Form",
            "department": "Quality Assurance",
            "version": "1.0",
            "status": "active",
            "description": "Form for conducting facility inspections",
        },
    ]

    document_ids = []
    for doc_data in documents_data:
        doc = Document(**doc_data)
        db.add(doc)
        document_ids.append(doc.id)

    db.commit()
    print(f"✓ Created {len(documents_data)} sample documents")
    return document_ids


def seed_annexes(db: Session, document_ids: list[str]) -> None:
    """Create sample annexes for documents."""
    annexes_data = [
        {
            "id": "annex-001",
            "document_id": document_ids[0],
            "code": "ANNEX-A",
            "title": "Cultivation Standards Reference",
            "file_path": "/documents/annexes/cultivation-standards.pdf",
        },
        {
            "id": "annex-002",
            "document_id": document_ids[0],
            "code": "ANNEX-B",
            "title": "Equipment Specifications",
            "file_path": "/documents/annexes/equipment-specs.pdf",
        },
        {
            "id": "annex-003",
            "document_id": document_ids[1],
            "code": "ANNEX-A",
            "title": "QA Test Methods",
            "file_path": "/documents/annexes/qa-test-methods.pdf",
        },
        {
            "id": "annex-004",
            "document_id": document_ids[2],
            "code": "ANNEX-A",
            "title": "Safety Hazard Matrix",
            "file_path": "/documents/annexes/hazard-matrix.pdf",
        },
    ]

    for annex_data in annexes_data:
        annex = Annex(**annex_data)
        db.add(annex)

    db.commit()
    print(f"✓ Created {len(annexes_data)} sample annexes")


def seed_chapters(db: Session, document_ids: list[str]) -> None:
    """Create sample chapters for documents."""
    chapters_data = [
        {
            "id": "chap-001",
            "document_id": document_ids[0],
            "chapter_number": 1,
            "number": "1",
            "title": "Introduction",
            "section": "General",
        },
        {
            "id": "chap-002",
            "document_id": document_ids[0],
            "chapter_number": 2,
            "number": "2",
            "title": "Scope and Applicability",
            "section": "General",
        },
        {
            "id": "chap-003",
            "document_id": document_ids[0],
            "chapter_number": 3,
            "number": "3",
            "title": "Pre-Cultivation Requirements",
            "section": "Preparation",
        },
        {
            "id": "chap-004",
            "document_id": document_ids[0],
            "chapter_number": 4,
            "number": "4",
            "title": "Cultivation Process",
            "section": "Operations",
        },
        {
            "id": "chap-005",
            "document_id": document_ids[1],
            "chapter_number": 1,
            "number": "1",
            "title": "Quality Standards",
            "section": "General",
        },
        {
            "id": "chap-006",
            "document_id": document_ids[1],
            "chapter_number": 2,
            "number": "2",
            "title": "Testing Procedures",
            "section": "Operations",
        },
    ]

    for chapter_data in chapters_data:
        chapter = DocumentChapter(**chapter_data)
        db.add(chapter)

    db.commit()
    print(f"✓ Created {len(chapters_data)} sample chapters")


def seed_audit_logs(db: Session, document_ids: list[str]) -> None:
    """Create sample audit log entries."""
    base_time = datetime.utcnow()
    logs_data = []

    actions = ["CREATE", "UPDATE", "REVIEW", "APPROVE", "ARCHIVE"]
    users = ["user-001", "user-002", "user-003"]

    for i, doc_id in enumerate(document_ids):
        action = actions[i % len(actions)]
        user = users[i % len(users)]
        timestamp = base_time - timedelta(days=i)

        log = AuditLog(
            id=f"log-{i + 1:03d}",
            document_id=doc_id,
            action=action,
            user_id=user,
            details=json.dumps(
                {
                    "action": action,
                    "reason": f"Sample {action} action",
                    "version_before": "1.0",
                    "version_after": "1.1",
                }
            ),
            created_at=timestamp,
        )
        db.add(log)
        logs_data.append(log)

    db.commit()
    print(f"✓ Created {len(logs_data)} sample audit log entries")


def seed_database() -> None:
    """Seed the database with sample data."""
    print("\n" + "=" * 60)
    print("Cannabis EU GMP QMS Creator - Database Seeding Script")
    print("=" * 60 + "\n")

    try:
        # Initialize database
        print("Initializing database...")
        DatabaseManager.initialize()
        db = DatabaseManager.get_session()

        # Check if database already has data
        doc_count = db.query(Document).count()
        if doc_count > 0:
            print(f"\n⚠ Database already contains {doc_count} documents.")
            response = input("Do you want to clear and reseed? (y/n): ")
            if response.lower() != "y":
                print("Seeding cancelled.")
                return

            # Clear existing data
            print("Clearing existing data...")
            db.query(AuditLog).delete()
            db.query(DocumentChapter).delete()
            db.query(Annex).delete()
            db.query(Document).delete()
            db.commit()
            print("✓ Cleared existing data\n")

        # Seed data
        print("Seeding sample data...\n")
        document_ids = seed_documents(db)
        seed_annexes(db, document_ids)
        seed_chapters(db, document_ids)
        seed_audit_logs(db, document_ids)

        print("\n" + "=" * 60)
        print("Database seeding completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n✗ Error during seeding: {e}")
        raise
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    seed_database()
