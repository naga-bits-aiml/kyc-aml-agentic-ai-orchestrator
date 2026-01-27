"""
Stage-Based Case Metadata Manager - Clean Architecture

Implements your proposed structure:
- Stage-based folders: intake/ classification/ extraction/ processed/
- Simplified metadata with stage references only
- Single file storage (no duplication)
- Parent file tracking for OCR-generated images
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from utilities import logger, settings


class StagedCaseMetadataManager:
    """Manages case metadata with stage-based document tracking."""
    
    STAGES = ['intake', 'classification', 'extraction', 'processed']
    
    def __init__(self, case_reference: str):
        """Initialize staged case metadata manager."""
        self.case_reference = case_reference
        self.case_dir = Path(settings.documents_dir) / "cases" / case_reference
        self.metadata_file = self.case_dir / "case_metadata.json"
        self.logger = logger
        
        # Create stage directories
        self._ensure_stage_directories()
    
    def _ensure_stage_directories(self):
        """Create stage directories if they don't exist."""
        for stage in self.STAGES:
            stage_dir = self.case_dir / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load case metadata from file."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return self._create_empty_metadata()
    
    def save_metadata(self, metadata: Dict[str, Any]):
        """Save case metadata to file."""
        self.case_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _create_empty_metadata(self) -> Dict[str, Any]:
        """Create empty case metadata structure with simplified format."""
        return {
            "case_reference": self.case_reference,
            "created_date": datetime.now().isoformat(),
            "status": "active",
            "workflow_stage": "intake",
            "documents": []  # Simple list with stage references
        }
    
    def add_document(
        self,
        document_id: str,
        filename: str,
        source_path: str,
        parent_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add document to intake stage.
        
        Args:
            document_id: Unique document ID (e.g., KYC-2026-001_DOC_001)
            filename: Original filename
            source_path: Source file path
            parent_file: Parent document ID if this is OCR-generated (optional)
            
        Returns:
            Document entry dictionary
        """
        metadata = self.load_metadata()
        
        # Create intake directory for this document
        intake_stage = self.case_dir / "intake"
        dest_path = intake_stage / filename
        
        # Copy file to intake (single location)
        shutil.copy2(source_path, dest_path)
        
        # Create document metadata file
        doc_metadata_path = intake_stage / f"{filename}.metadata.json"
        doc_metadata = {
            "document_id": document_id,
            "filename": filename,
            "added_date": datetime.now().isoformat(),
            "file_size": dest_path.stat().st_size,
            "source_path": str(source_path)
        }
        
        if parent_file:
            doc_metadata["parent_file"] = parent_file
        
        with open(doc_metadata_path, 'w') as f:
            json.dump(doc_metadata, f, indent=2)
        
        # Add to case metadata (simplified)
        doc_entry = {
            "document_id": document_id,
            "stage": "intake",
            "metadata_path": f"intake/{filename}.metadata.json"
        }
        
        if parent_file:
            doc_entry["parent_file"] = parent_file
        
        metadata["documents"].append(doc_entry)
        self.save_metadata(metadata)
        
        self.logger.info(f"Document added to intake: {document_id}")
        return doc_entry
    
    def move_to_stage(self, document_id: str, new_stage: str) -> bool:
        """
        Move document to a new stage.
        
        Args:
            document_id: Document ID to move
            new_stage: Target stage (classification, extraction, processed)
            
        Returns:
            Boolean indicating success
        """
        if new_stage not in self.STAGES:
            self.logger.error(f"Invalid stage: {new_stage}")
            return False
        
        metadata = self.load_metadata()
        
        # Find document
        doc_entry = next((d for d in metadata["documents"] if d["document_id"] == document_id), None)
        if not doc_entry:
            self.logger.error(f"Document not found: {document_id}")
            return False
        
        current_stage = doc_entry["stage"]
        if current_stage == new_stage:
            self.logger.info(f"Document already in {new_stage} stage")
            return True
        
        # Extract filename from metadata path
        current_metadata_path = self.case_dir / doc_entry["metadata_path"]
        with open(current_metadata_path, 'r') as f:
            doc_metadata = json.load(f)
        
        filename = doc_metadata["filename"]
        
        # Move file
        src_file = self.case_dir / current_stage / filename
        dst_file = self.case_dir / new_stage / filename
        
        if not src_file.exists():
            self.logger.error(f"Source file not found: {src_file}")
            return False
        
        shutil.move(str(src_file), str(dst_file))
        
        # Move metadata file
        src_metadata = self.case_dir / current_stage / f"{filename}.metadata.json"
        dst_metadata = self.case_dir / new_stage / f"{filename}.metadata.json"
        shutil.move(str(src_metadata), str(dst_metadata))
        
        # Update case metadata
        doc_entry["stage"] = new_stage
        doc_entry["metadata_path"] = f"{new_stage}/{filename}.metadata.json"
        doc_entry["moved_date"] = datetime.now().isoformat()
        
        self.save_metadata(metadata)
        
        self.logger.info(f"Moved {document_id} from {current_stage} to {new_stage}")
        return True
    
    def get_document_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        """Get all documents in a specific stage."""
        metadata = self.load_metadata()
        return [d for d in metadata["documents"] if d["stage"] == stage]
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document entry by ID."""
        metadata = self.load_metadata()
        return next((d for d in metadata["documents"] if d["document_id"] == document_id), None)
    
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Load full metadata for a specific document."""
        metadata = self.load_metadata()
        
        doc_entry = next((d for d in metadata["documents"] if d["document_id"] == document_id), None)
        if not doc_entry:
            return None
        
        metadata_path = self.case_dir / doc_entry["metadata_path"]
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)
    
    def update_document_metadata(
        self,
        document_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update document metadata file.
        
        Args:
            document_id: Document ID
            updates: Dictionary of fields to update (classification, extraction, etc.)
            
        Returns:
            Boolean indicating success
        """
        metadata = self.load_metadata()
        
        doc_entry = next((d for d in metadata["documents"] if d["document_id"] == document_id), None)
        if not doc_entry:
            self.logger.error(f"Document not found: {document_id}")
            return False
        
        metadata_path = self.case_dir / doc_entry["metadata_path"]
        
        # Load existing metadata
        with open(metadata_path, 'r') as f:
            doc_metadata = json.load(f)
        
        # Update fields
        doc_metadata.update(updates)
        doc_metadata["last_updated"] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(doc_metadata, f, indent=2)
        
        self.logger.info(f"Updated metadata for {document_id}")
        return True
    
    def get_stage_summary(self) -> Dict[str, int]:
        """Get count of documents in each stage."""
        metadata = self.load_metadata()
        
        summary = {stage: 0 for stage in self.STAGES}
        for doc in metadata["documents"]:
            stage = doc.get("stage", "unknown")
            if stage in summary:
                summary[stage] += 1
        
        return summary
    
    def reprocess_document(self, document_id: str, target_stage: str = "intake") -> bool:
        """
        Move document back to an earlier stage for reprocessing.
        
        Args:
            document_id: Document ID to reprocess
            target_stage: Stage to move back to (default: intake)
            
        Returns:
            Boolean indicating success
        """
        return self.move_to_stage(document_id, target_stage)
