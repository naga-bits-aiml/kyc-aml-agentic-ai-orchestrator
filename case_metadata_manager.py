"""
Case Metadata Manager - Clean Architecture

Cases are lightweight containers that:
- Hold case metadata (customer info, status, etc.)
- Maintain references to document IDs
- Documents are processed and stored independently in documents/intake/

A document can belong to multiple cases (many-to-many relationship).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from utilities import logger, settings


class CaseMetadataManager:
    """
    Manages case metadata with document ID references.
    
    Cases only store:
    - Case metadata (reference, status, description, dates)
    - List of document IDs that are linked to this case
    
    Documents are stored independently in documents/intake/ and can
    belong to multiple cases.
    """
    
    def __init__(self, case_reference: str):
        """Initialize case metadata manager."""
        self.case_reference = case_reference
        self.case_dir = Path(settings.documents_dir) / "cases" / case_reference
        self.metadata_file = self.case_dir / "case_metadata.json"
        self.logger = logger
    
    def ensure_exists(self) -> None:
        """Ensure case directory exists."""
        self.case_dir.mkdir(parents=True, exist_ok=True)
    
    def exists(self) -> bool:
        """Check if case exists."""
        return self.metadata_file.exists()
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load case metadata from file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_empty_metadata()
    
    def save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save case metadata to file."""
        self.ensure_exists()
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
    
    def _create_empty_metadata(self) -> Dict[str, Any]:
        """Create empty case metadata structure."""
        return {
            "case_reference": self.case_reference,
            "created_date": datetime.now().isoformat(),
            "status": "active",
            "description": "",
            "documents": [],  # List of document IDs linked to this case
            "last_updated": datetime.now().isoformat()
        }
    
    def create(self, description: str = "") -> Dict[str, Any]:
        """
        Create a new case with metadata.
        
        Args:
            description: Optional case description
            
        Returns:
            Created case metadata
        """
        self.ensure_exists()
        metadata = self._create_empty_metadata()
        metadata["description"] = description
        self.save_metadata(metadata)
        self.logger.info(f"Created case: {self.case_reference}")
        return metadata
    
    def add_document(self, document_id: str) -> bool:
        """
        Link a document to this case.
        
        Args:
            document_id: Unique document ID (e.g., DOC_20260129_231812_A734B)
            
        Returns:
            True if added, False if already linked
        """
        metadata = self.load_metadata()
        
        if document_id not in metadata.get("documents", []):
            if "documents" not in metadata:
                metadata["documents"] = []
            metadata["documents"].append(document_id)
            metadata["last_updated"] = datetime.now().isoformat()
            self.save_metadata(metadata)
            self.logger.info(f"Linked document {document_id} to case {self.case_reference}")
            return True
        return False
    
    def remove_document(self, document_id: str) -> bool:
        """
        Unlink a document from this case.
        
        Args:
            document_id: Document ID to remove
            
        Returns:
            True if removed, False if not found
        """
        metadata = self.load_metadata()
        
        if document_id in metadata.get("documents", []):
            metadata["documents"].remove(document_id)
            metadata["last_updated"] = datetime.now().isoformat()
            self.save_metadata(metadata)
            self.logger.info(f"Unlinked document {document_id} from case {self.case_reference}")
            return True
        return False
    
    def get_documents(self) -> List[str]:
        """Get list of document IDs linked to this case."""
        metadata = self.load_metadata()
        return metadata.get("documents", [])
    
    def get_document_count(self) -> int:
        """Get count of documents linked to this case."""
        return len(self.get_documents())
    
    def update_status(self, status: str) -> None:
        """Update case status."""
        metadata = self.load_metadata()
        metadata["status"] = status
        metadata["last_updated"] = datetime.now().isoformat()
        self.save_metadata(metadata)
    
    def update_description(self, description: str) -> None:
        """Update case description."""
        metadata = self.load_metadata()
        metadata["description"] = description
        metadata["last_updated"] = datetime.now().isoformat()
        self.save_metadata(metadata)
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple case metadata fields.
        
        Args:
            updates: Dictionary of fields to update
        """
        metadata = self.load_metadata()
        
        allowed_fields = ["status", "description", "notes", "assigned_to", "customer_name"]
        for field, value in updates.items():
            if field in allowed_fields:
                metadata[field] = value
        
        metadata["last_updated"] = datetime.now().isoformat()
        self.save_metadata(metadata)


# Backwards compatibility alias
StagedCaseMetadataManager = CaseMetadataManager
