"""
Metadata Agent Tools - Status tracking and error handling.

These tools handle:
- Reading and updating document metadata
- Processing status tracking
- Error recording and retry management
- Metadata validation

All metadata operations are deterministic file operations.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool

# Import utilities
try:
    from utilities import logger, settings
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    class Settings:
        documents_dir = "./documents"
    settings = Settings()


# ==================== TOOL DEFINITIONS ====================

@tool
def get_document_metadata(document_id: str) -> Dict[str, Any]:
    """
    Get the full metadata for a document.
    
    Args:
        document_id: Document ID to retrieve
        
    Returns:
        Dictionary with document metadata or error
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return {
            "success": True,
            "document_id": document_id,
            "metadata": metadata
        }
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to read metadata: {str(e)}"
        }


@tool
def update_processing_status(
    document_id: str,
    stage: str,
    status: str,
    error: Optional[str] = None,
    additional_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Update the processing status for a document stage.
    
    Args:
        document_id: Document ID to update
        stage: Processing stage (queue, classification, extraction)
        status: New status (pending, processing, completed, failed, skipped)
        error: Optional error message
        additional_data: Optional additional data to store
        
    Returns:
        Dictionary with update result
    """
    valid_stages = ["queue", "classification", "extraction"]
    valid_statuses = ["pending", "processing", "completed", "failed", "skipped"]
    
    if stage not in valid_stages:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Invalid stage: {stage}. Valid: {valid_stages}"
        }
    
    if status not in valid_statuses:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Invalid status: {status}. Valid: {valid_statuses}"
        }
    
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Update stage status
        if stage not in metadata:
            metadata[stage] = {}
        
        metadata[stage]["status"] = status
        
        if status == "processing":
            metadata[stage]["started_at"] = datetime.now().isoformat()
        elif status in ["completed", "failed"]:
            metadata[stage]["completed_at"] = datetime.now().isoformat()
        
        if error:
            metadata[stage]["error"] = error
            metadata["last_error"] = error
        
        if additional_data:
            for key, value in additional_data.items():
                metadata[stage][key] = value
        
        # Update overall processing status
        if status == "failed":
            metadata["processing_status"] = "failed"
        elif status == "completed" and stage == "extraction":
            metadata["processing_status"] = "completed"
        
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "stage": stage,
            "status": status,
            "message": f"Updated {stage} status to {status}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to update metadata: {str(e)}"
        }


@tool
def record_error(
    document_id: str,
    stage: str,
    error_message: str,
    increment_retry: bool = True
) -> Dict[str, Any]:
    """
    Record an error for a document and optionally increment retry count.
    
    Args:
        document_id: Document ID
        stage: Stage where error occurred
        error_message: Error description
        increment_retry: Whether to increment retry counter
        
    Returns:
        Dictionary with error recording result
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        if stage not in metadata:
            metadata[stage] = {}
        
        # Record error
        metadata[stage]["status"] = "failed"
        metadata[stage]["error"] = error_message
        metadata[stage]["failed_at"] = datetime.now().isoformat()
        
        # Increment retry count
        if increment_retry:
            current_retries = metadata[stage].get("retry_count", 0)
            metadata[stage]["retry_count"] = current_retries + 1
        
        metadata["last_error"] = error_message
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "stage": stage,
            "error": error_message,
            "retry_count": metadata[stage].get("retry_count", 0),
            "message": f"Recorded error for {stage}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to record error: {str(e)}"
        }


@tool
def check_retry_eligible(document_id: str, stage: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Check if a document is eligible for retry at a given stage.
    
    Args:
        document_id: Document ID
        stage: Processing stage to check
        max_retries: Maximum allowed retries
        
    Returns:
        Dictionary with retry eligibility
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "eligible": False,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        stage_data = metadata.get(stage, {})
        current_retries = stage_data.get("retry_count", 0)
        status = stage_data.get("status", "pending")
        
        eligible = (status == "failed" and current_retries < max_retries)
        
        return {
            "success": True,
            "document_id": document_id,
            "stage": stage,
            "eligible": eligible,
            "current_retries": current_retries,
            "max_retries": max_retries,
            "status": status,
            "message": f"{'Eligible' if eligible else 'Not eligible'} for retry ({current_retries}/{max_retries})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "eligible": False,
            "error": f"Failed to check retry eligibility: {str(e)}"
        }


@tool
def reset_stage_for_retry(document_id: str, stage: str) -> Dict[str, Any]:
    """
    Reset a stage to pending status for retry.
    
    Args:
        document_id: Document ID
        stage: Stage to reset
        
    Returns:
        Dictionary with reset result
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        if stage not in metadata:
            metadata[stage] = {}
        
        # Keep retry count, reset status
        retry_count = metadata[stage].get("retry_count", 0)
        
        metadata[stage]["status"] = "pending"
        metadata[stage]["error"] = None
        metadata[stage]["retry_count"] = retry_count
        metadata[stage]["reset_at"] = datetime.now().isoformat()
        
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "stage": stage,
            "message": f"Reset {stage} to pending (retry {retry_count + 1})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to reset stage: {str(e)}"
        }


@tool
def flag_for_review(document_id: str, reason: str) -> Dict[str, Any]:
    """
    Flag a document for manual review.
    
    Args:
        document_id: Document ID
        reason: Reason for flagging
        
    Returns:
        Dictionary with flagging result
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        metadata["requires_review"] = True
        metadata["review_reason"] = reason
        metadata["flagged_at"] = datetime.now().isoformat()
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "flagged": True,
            "reason": reason,
            "message": f"Flagged for review: {reason}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to flag document: {str(e)}"
        }


@tool
def get_processing_summary(document_id: str) -> Dict[str, Any]:
    """
    Get a summary of processing status for a document.
    
    Args:
        document_id: Document ID
        
    Returns:
        Dictionary with processing summary
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Metadata not found: {document_id}"
        }
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return {
            "success": True,
            "document_id": document_id,
            "original_filename": metadata.get("original_filename"),
            "processing_status": metadata.get("processing_status"),
            "stages": {
                "queue": {
                    "status": metadata.get("queue", {}).get("status"),
                    "error": metadata.get("queue", {}).get("error")
                },
                "classification": {
                    "status": metadata.get("classification", {}).get("status"),
                    "document_type": metadata.get("classification", {}).get("document_type"),
                    "confidence": metadata.get("classification", {}).get("confidence"),
                    "error": metadata.get("classification", {}).get("error")
                },
                "extraction": {
                    "status": metadata.get("extraction", {}).get("status"),
                    "fields_count": len(metadata.get("extraction", {}).get("extracted_fields", {})),
                    "error": metadata.get("extraction", {}).get("error")
                }
            },
            "requires_review": metadata.get("requires_review", False),
            "last_error": metadata.get("last_error"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at")
        }
        
    except Exception as e:
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Failed to get summary: {str(e)}"
        }


@tool
def list_all_metadata() -> Dict[str, Any]:
    """
    List all document metadata files in the intake folder.
    
    Returns:
        Dictionary with list of documents and their status
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    
    if not intake_dir.exists():
        return {
            "success": True,
            "documents": [],
            "count": 0,
            "message": "No documents found"
        }
    
    documents = []
    for metadata_file in intake_dir.glob("*.metadata.json"):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            documents.append({
                "document_id": metadata.get("document_id"),
                "original_filename": metadata.get("original_filename"),
                "processing_status": metadata.get("processing_status"),
                "classification_status": metadata.get("classification", {}).get("status"),
                "extraction_status": metadata.get("extraction", {}).get("status"),
                "requires_review": metadata.get("requires_review", False)
            })
        except Exception as e:
            logger.warning(f"Failed to read {metadata_file}: {e}")
    
    return {
        "success": True,
        "documents": documents,
        "count": len(documents),
        "message": f"Found {len(documents)} documents"
    }
