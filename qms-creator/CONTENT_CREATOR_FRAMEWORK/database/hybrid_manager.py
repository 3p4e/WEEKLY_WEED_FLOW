"""
Hybrid database manager for Cannabis EU GMP QMS Creator.

Provides a unified interface for accessing documents from either JSON or PostgreSQL backend.
Supports seamless migration between backends without changing application code.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import Annex, AuditLog, Document, DocumentChapter, DocumentStatus
from .session import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseBackend(ABC):
    """Abstract base class for database backends."""

    @abstractmethod
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        pass

    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        pass

    @abstractmethod
    def upsert_document(self, doc_data: Dict[str, Any]) -> None:
        """Insert or update a document."""
        pass

    @abstractmethod
    def update_status(self, doc_id: str, status: str) -> None:
        """Update document status."""
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        pass

    @abstractmethod
    def initialize_registry(self, sop_list: List[Dict[str, Any]]) -> None:
        """Initialize database with list of SOPs."""
        pass


class JSONBackend(DatabaseBackend):
    """JSON file-based backend for backward compatibility."""

    def __init__(self, db_path: str):
        """Initialize JSON backend."""
        self.db_path = Path(db_path)
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Create initial database if it doesn't exist."""
        if not self.db_path.exists():
            initial_data = {
                "documents": [],
                "last_updated": datetime.now().isoformat(),
                "registry_version": "1.0",
            }
            self._save(initial_data)
            logger.info(f"Created JSON database at {self.db_path}")

    def _load(self) -> Dict[str, Any]:
        """Load data from JSON file."""
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]) -> None:
        """Save data to JSON file."""
        data["last_updated"] = datetime.now().isoformat()
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        return self._load().get("documents", [])

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        docs = self.get_all_documents()
        for doc in docs:
            if doc["id"] == doc_id:
                return doc
        return None

    def upsert_document(self, doc_data: Dict[str, Any]) -> None:
        """Insert or update a document."""
        data = self._load()
        docs = data.get("documents", [])

        found = False
        for i, doc in enumerate(docs):
            if doc["id"] == doc_data["id"]:
                docs[i].update(doc_data)
                found = True
                break

        if not found:
            docs.append(doc_data)

        data["documents"] = docs
        self._save(data)
        logger.debug(f"Upserted document {doc_data['id']} to JSON backend")

    def update_status(self, doc_id: str, status: str) -> None:
        """Update document status."""
        doc = self.get_document(doc_id)
        if doc:
            doc["status"] = status
            doc["last_modified"] = datetime.now().isoformat()
            self.upsert_document(doc)
            logger.debug(f"Updated status for document {doc_id} to {status}")

    def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        data = self._load()
        docs = data.get("documents", [])
        data["documents"] = [doc for doc in docs if doc["id"] != doc_id]
        self._save(data)
        logger.info(f"Deleted document {doc_id} from JSON backend")

    def initialize_registry(self, sop_list: List[Dict[str, Any]]) -> None:
        """Initialize database with list of SOPs."""
        data = self._load()
        if not data.get("documents"):
            data["documents"] = sop_list
            self._save(data)
            logger.info(f"Initialized JSON database with {len(sop_list)} documents")


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL backend for production use."""

    def __init__(self, session: Optional[Session] = None):
        """Initialize PostgreSQL backend."""
        self.session = session
        if self.session is None:
            DatabaseManager.initialize()
            self.session = DatabaseManager.create_session()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        docs = self.session.query(Document).all()
        return [self._document_to_dict(doc) for doc in docs]

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        doc = self.session.query(Document).filter(Document.id == doc_id).first()
        if doc:
            return self._document_to_dict(doc)
        return None

    def upsert_document(self, doc_data: Dict[str, Any]) -> None:
        """Insert or update a document."""
        doc = self.session.query(Document).filter(Document.id == doc_data["id"]).first()

        if doc:
            # Update existing
            for key, value in doc_data.items():
                if hasattr(doc, key) and key not in ["annexes", "chapters"]:
                    setattr(doc, key, value)
        else:
            # Create new
            doc = Document(**doc_data)
            self.session.add(doc)

        self.session.commit()
        logger.debug(f"Upserted document {doc_data['id']} to PostgreSQL backend")

    def update_status(self, doc_id: str, status: str) -> None:
        """Update document status."""
        doc = self.session.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = DocumentStatus(status)
            self.session.commit()
            logger.debug(f"Updated status for document {doc_id} to {status}")

    def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        doc = self.session.query(Document).filter(Document.id == doc_id).first()
        if doc:
            self.session.delete(doc)
            self.session.commit()
            logger.info(f"Deleted document {doc_id} from PostgreSQL backend")

    def initialize_registry(self, sop_list: List[Dict[str, Any]]) -> None:
        """Initialize database with list of SOPs."""
        existing_count = self.session.query(Document).count()
        if existing_count == 0:
            for doc_data in sop_list:
                doc = Document(**doc_data)
                self.session.add(doc)
            self.session.commit()
            logger.info(
                f"Initialized PostgreSQL database with {len(sop_list)} documents"
            )

    @staticmethod
    def _document_to_dict(doc: Document) -> Dict[str, Any]:
        """Convert Document model to dictionary."""
        return {
            "id": doc.id,
            "code": doc.code,
            "title": doc.title,
            "department": doc.department,
            "version": doc.version,
            "status": doc.status.value if doc.status else "pending",
            "description": doc.description,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "pdf_path": doc.pdf_path,
            "docx_path": doc.docx_path,
            "annexes": [
                {
                    "id": annex.id,
                    "title": annex.title,
                    "file_path": annex.file_path,
                    "file_type": annex.file_type,
                }
                for annex in doc.annexes
            ],
            "chapters": [
                {
                    "id": chapter.id,
                    "number": chapter.number,
                    "title": chapter.title,
                    "level": chapter.level,
                    "order": chapter.order,
                }
                for chapter in doc.chapters
            ],
        }


class HybridDatabaseManager:
    """Manages database backend selection and provides unified interface."""

    def __init__(
        self, use_postgresql: bool = True, json_path: str = "data/document_status.json"
    ):
        """
        Initialize hybrid database manager.

        Args:
            use_postgresql: Whether to use PostgreSQL (True) or JSON (False)
            json_path: Path to JSON file for fallback
        """
        self.use_postgresql = (
            use_postgresql or os.getenv("USE_POSTGRESQL", "true").lower() == "true"
        )

        if self.use_postgresql:
            try:
                self.backend = PostgreSQLBackend()
                logger.info("Using PostgreSQL backend")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize PostgreSQL backend: {e}, falling back to JSON"
                )
                self.use_postgresql = False
                self.backend = JSONBackend(json_path)
        else:
            self.backend = JSONBackend(json_path)
            logger.info("Using JSON backend")

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents."""
        return self.backend.get_all_documents()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        return self.backend.get_document(doc_id)

    def upsert_document(self, doc_data: Dict[str, Any]) -> None:
        """Insert or update a document."""
        return self.backend.upsert_document(doc_data)

    def update_status(self, doc_id: str, status: str) -> None:
        """Update document status."""
        return self.backend.update_status(doc_id, status)

    def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        return self.backend.delete_document(doc_id)

    def initialize_registry(self, sop_list: List[Dict[str, Any]]) -> None:
        """Initialize database with list of SOPs."""
        return self.backend.initialize_registry(sop_list)

    def get_backend_type(self) -> str:
        """Get current backend type."""
        return "PostgreSQL" if self.use_postgresql else "JSON"
