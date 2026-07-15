
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

class QMSDatabase:
    """
    Manages the persistent state of all QMS documents (SOPs and Annexes).
    Storage: data/document_status.json
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.db_path = self.project_root / "data" / "document_status.json"
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Create initial database if it doesn't exist"""
        if not self.db_path.exists():
            initial_data = {
                "documents": [],
                "last_updated": datetime.now().isoformat(),
                "registry_version": "1.0"
            }
            self._save(initial_data)
            
    def _load(self) -> Dict[str, Any]:
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def _save(self, data: Dict[str, Any]):
        data["last_updated"] = datetime.now().isoformat()
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
    def get_all_documents(self) -> List[Dict[str, Any]]:
        return self._load().get("documents", [])
        
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        docs = self.get_all_documents()
        for doc in docs:
            if doc["id"] == doc_id:
                return doc
        return None
        
    def upsert_document(self, doc_data: Dict[str, Any]):
        """Update existing or add new document"""
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
        
    def update_status(self, doc_id: str, status: str):
        doc = self.get_document(doc_id)
        if doc:
            doc["status"] = status
            doc["last_modified"] = datetime.now().isoformat()
            self.upsert_document(doc)

    def initialize_registry_from_list(self, sop_list: List[Dict[str, Any]]):
        """
        Populate the database with a list of planned SOPs if empty.
        Each item should have: id, code, title, department, status, version.
        """
        data = self._load()
        if not data.get("documents"):
            data["documents"] = sop_list
            self._save(data)
