"""
PostgreSQL backend for QMS database.
Provides SQLAlchemy-based access to the QMS document database.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from CONTENT_CREATOR_FRAMEWORK.database.models import (
    Annex,
    Document,
    DocumentStatus,
)
from CONTENT_CREATOR_FRAMEWORK.database.session import DatabaseManager

logger = logging.getLogger(__name__)


class QMSDatabasePostgres:
    """
    PostgreSQL-backed QMS database implementation.
    Provides the same interface as QMSDatabase but uses PostgreSQL backend.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize PostgreSQL database.

        Args:
            database_url: PostgreSQL connection URL or None to use environment variable
        """
        logger.info("Initializing PostgreSQL QMS Database")
        from CONTENT_CREATOR_FRAMEWORK.database.session import DatabaseConfig

        config = DatabaseConfig(database_url)
        DatabaseManager.initialize(config)
        DatabaseManager.create_all()

    def get_session(self) -> Session:
        """Get a new database session."""
        return DatabaseManager.create_session()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        session = self.get_session()
        try:
            documents = session.query(Document).all()
            return [doc.to_dict() for doc in documents]
        finally:
            session.close()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a single document by ID."""
        session = self.get_session()
        try:
            document = session.query(Document).filter(Document.id == doc_id).first()
            return document.to_dict() if document else None
        finally:
            session.close()

    def get_documents_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get all documents in a specific department."""
        session = self.get_session()
        try:
            documents = (
                session.query(Document).filter(Document.department == department).all()
            )
            return [doc.to_dict() for doc in documents]
        finally:
            session.close()

    def get_documents_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all documents with a specific status."""
        session = self.get_session()
        try:
            status_enum = DocumentStatus[status.upper()]
            documents = (
                session.query(Document).filter(Document.status == status_enum).all()
            )
            return [doc.to_dict() for doc in documents]
        finally:
            session.close()

    def upsert_document(self, doc_data: Dict[str, Any]) -> None:
        """Create or update a document."""
        session = self.get_session()
        try:
            doc_id = doc_data.get("id")
            existing = session.query(Document).filter(Document.id == doc_id).first()

            if existing:
                # Update existing
                for key, value in doc_data.items():
                    if key != "id" and key != "annexes":
                        if key == "status" and isinstance(value, str):
                            setattr(existing, key, DocumentStatus[value.upper()])
                        else:
                            setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                doc_data_copy = doc_data.copy()
                annexes_data = doc_data_copy.pop("annexes", [])

                if "status" in doc_data_copy and isinstance(
                    doc_data_copy["status"], str
                ):
                    doc_data_copy["status"] = DocumentStatus[
                        doc_data_copy["status"].upper()
                    ]

                document = Document(**doc_data_copy)
                session.add(document)
                session.flush()  # Ensure ID is generated

                # Add annexes
                for annex_data in annexes_data:
                    annex_data["document_id"] = doc_data.get("id")
                    annex = Annex(**annex_data)
                    session.add(annex)

            session.commit()
            logger.info(f"Upserted document: {doc_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting document: {str(e)}")
            raise
        finally:
            session.close()

    def update_status(self, doc_id: str, status: str) -> None:
        """Update document status."""
        session = self.get_session()
        try:
            document = session.query(Document).filter(Document.id == doc_id).first()
            if document:
                document.status = DocumentStatus[status.upper()]
                document.last_modified = datetime.utcnow()
                session.commit()
                logger.info(f"Updated document {doc_id} status to {status}")
            else:
                logger.warning(f"Document not found: {doc_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating document status: {str(e)}")
            raise
        finally:
            session.close()

    def delete_document(self, doc_id: str) -> None:
        """Delete a document and its annexes."""
        session = self.get_session()
        try:
            document = session.query(Document).filter(Document.id == doc_id).first()
            if document:
                session.delete(document)  # Cascades to annexes
                session.commit()
                logger.info(f"Deleted document: {doc_id}")
            else:
                logger.warning(f"Document not found: {doc_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting document: {str(e)}")
            raise
        finally:
            session.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        session = self.get_session()
        try:
            total_docs = session.query(Document).count()
            total_annexes = session.query(Annex).count()

            status_counts = {}
            for status in DocumentStatus:
                count = (
                    session.query(Document).filter(Document.status == status).count()
                )
                if count > 0:
                    status_counts[status.value] = count

            dept_counts = {}
            departments = session.query(Document.department).distinct().all()
            for (dept,) in departments:
                count = (
                    session.query(Document).filter(Document.department == dept).count()
                )
                dept_counts[dept] = count

            return {
                "total_documents": total_docs,
                "total_annexes": total_annexes,
                "by_status": status_counts,
                "by_department": dept_counts,
            }
        finally:
            session.close()

    def initialize_registry_from_list(self, sop_list: List[Dict[str, Any]]) -> None:
        """Populate the database with a list of planned SOPs if empty."""
        session = self.get_session()
        try:
            if session.query(Document).count() == 0:
                for sop_data in sop_list:
                    document = Document(**sop_data)
                    session.add(document)
                session.commit()
                logger.info(f"Initialized registry with {len(sop_list)} SOPs")
            else:
                logger.info("Registry already populated, skipping initialization")
        except Exception as e:
            session.rollback()
            logger.error(f"Error initializing registry: {str(e)}")
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connection."""
        DatabaseManager.close()
