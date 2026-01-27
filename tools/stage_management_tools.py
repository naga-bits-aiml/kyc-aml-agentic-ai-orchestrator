"""Stage management tools for CrewAI agents.

These tools allow agents to move documents between workflow stages:
intake → classification → extraction → processed
"""

from crewai.tools import tool
from typing import Dict, Any, Optional
from pathlib import Path
from case_metadata_manager import StagedCaseMetadataManager
from utilities import logger, settings
import json
from datetime import datetime


def _get_stage_manager(case_id: str) -> StagedCaseMetadataManager:
    """Get or create a stage manager for a case."""
    case_dir = Path(settings.documents_dir) / "cases" / case_id
    if not case_dir.exists():
        raise ValueError(f"Case directory does not exist: {case_id}")
    return StagedCaseMetadataManager(case_dir)


@tool("Move Document to Stage")
def move_document_to_stage(case_id: str, document_id: str, stage: str) -> Dict[str, Any]:
    """
    Move a document to a different workflow stage.
    
    Valid stages are:
    - intake: Initial document upload
    - classification: Document has been classified
    - extraction: Data has been extracted
    - processed: Document is fully processed
    
    Args:
        case_id: Case identifier (e.g., "KYC-2026-001")
        document_id: Document identifier (e.g., "KYC-2026-001_DOC_001")
        stage: Target stage name
        
    Returns:
        Status of the move operation
    
    Example:
        move_document_to_stage("KYC-2026-001", "KYC-2026-001_DOC_001", "classification")
    """
    try:
        manager = _get_stage_manager(case_id)
        
        # Validate stage
        valid_stages = ['intake', 'classification', 'extraction', 'processed']
        if stage not in valid_stages:
            return {
                "success": False,
                "error": f"Invalid stage '{stage}'. Must be one of: {', '.join(valid_stages)}"
            }
        
        # Move document
        success = manager.move_to_stage(document_id, stage)
        
        if success:
            logger.info(f"Moved {document_id} to {stage} stage")
            return {
                "success": True,
                "document_id": document_id,
                "new_stage": stage,
                "message": f"Document successfully moved to {stage}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to move document {document_id} to {stage}"
            }
            
    except Exception as e:
        logger.error(f"Error moving document to stage: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Get Documents by Stage")
def get_documents_by_stage(stage: str) -> Dict[str, Any]:
    """
    Get all documents in a specific workflow stage.
    
    This tool searches across all document directories to find documents
    at the specified stage, regardless of case association.
    
    Args:
        stage: Stage name (intake/classification/extraction/processed)
        
    Returns:
        List of documents in the specified stage
    
    Example:
        get_documents_by_stage("classification")
    """
    try:
        valid_stages = ['intake', 'classification', 'extraction', 'processed']
        if stage not in valid_stages:
            return {
                "success": False,
                "error": f"Invalid stage '{stage}'. Must be one of: {valid_stages}"
            }
        
        # Search through stage-based directories
        stage_dirs = [
            Path(settings.documents_dir) / "intake",
            Path(settings.documents_dir) / "classification", 
            Path(settings.documents_dir) / "extraction",
            Path(settings.documents_dir) / "processed"
        ]
        
        documents = []
        
        # Scan all metadata files
        for stage_dir in stage_dirs:
            if not stage_dir.exists():
                continue
                
            for metadata_file in stage_dir.glob("*.metadata.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if document is in requested stage
                    if metadata.get('stage') == stage:
                        documents.append({
                            "document_id": metadata.get('document_id'),
                            "original_filename": metadata.get('original_filename'),
                            "stored_path": metadata.get('stored_path'),
                            "stage": metadata.get('stage'),
                            "document_type": metadata.get('classification', {}).get('document_type'),
                            "confidence": metadata.get('classification', {}).get('confidence'),
                            "last_updated": metadata.get('last_updated')
                        })
                except Exception as e:
                    logger.warning(f"Error reading metadata file {metadata_file}: {e}")
                    continue
        
        logger.info(f"Found {len(documents)} documents in stage '{stage}'")
        
        return {
            "success": True,
            "stage": stage,
            "document_count": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error(f"Error getting documents by stage: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Get Stage Summary")
def get_stage_summary(case_id: str) -> Dict[str, Any]:
    """
    Get a summary of documents across all workflow stages.
    
    Args:
        case_id: Case identifier
        
    Returns:
        Count of documents in each stage
    
    Example:
        get_stage_summary("KYC-2026-001")
    """
    try:
        manager = _get_stage_manager(case_id)
        summary = manager.get_stage_summary()
        total = sum(summary.values())
        
        return {
            "success": True,
            "case_id": case_id,
            "total_documents": total,
            "by_stage": summary,
            "stages": {
                "intake": summary.get('intake', 0),
                "classification": summary.get('classification', 0),
                "extraction": summary.get('extraction', 0),
                "processed": summary.get('processed', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting stage summary: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Add Document to Case")
def add_document_to_case(
    case_id: str,
    document_id: str,
    filename: str,
    source_path: str,
    parent_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new document to a case in the intake stage.
    
    Args:
        case_id: Case identifier
        document_id: Unique document identifier
        filename: Document filename
        source_path: Path to source file
        parent_file: Optional parent document ID (for OCR-generated images)
        
    Returns:
        Document entry with stage information
    
    Example:
        add_document_to_case("KYC-2026-001", "KYC-2026-001_DOC_005", "passport.pdf", "/uploads/passport.pdf")
    """
    try:
        manager = _get_stage_manager(case_id)
        
        result = manager.add_document(
            document_id=document_id,
            filename=filename,
            source_path=source_path,
            parent_file=parent_file
        )
        
        logger.info(f"Added document {document_id} to case {case_id}")
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Error adding document to case: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Update Document Metadata in Stage")
def update_document_metadata_in_stage(
    case_id: str,
    document_id: str,
    metadata_updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update metadata for a document without changing its stage.
    DEPRECATED for case-agnostic workflows. Use update_document_metadata_tool instead.
    
    Args:
        case_id: Case identifier
        document_id: Document identifier
        metadata_updates: Dictionary of metadata fields to update
        
    Returns:
        Status of the update operation
    
    Example:
        update_document_metadata_in_stage(
            "KYC-2026-001",
            "KYC-2026-001_DOC_001",
            {"classification": {"type": "Passport", "confidence": 0.95}}
        )
    """
    try:
        manager = _get_stage_manager(case_id)
        
        success = manager.update_document_metadata(document_id, metadata_updates)
        
        if success:
            return {
                "success": True,
                "document_id": document_id,
                "message": "Metadata updated successfully"
            }
        else:
            return {
                "success": False,
                "error": "Failed to update metadata"
            }
            
    except Exception as e:
        logger.error(f"Error updating document metadata: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Update Document Metadata")
def update_document_metadata_tool(
    document_id: str,
    stage_name: str,
    status: str,
    msg: str = "",
    error: Optional[str] = None,
    trace: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update stage-specific metadata block for a document.
    Each processing stage (intake, classification, extraction) updates its own block.
    
    Args:
        document_id: Globally unique document ID (e.g., DOC_20260127_143022_A3F8B)
        stage_name: Stage name to update (intake/classification/extraction)
        status: Status of the stage (success/fail/pending/running)
        msg: Descriptive message about the stage result
        error: Error message if stage failed (optional)
        trace: Stack trace if stage failed (optional)
        additional_data: Any additional stage-specific data (optional)
        
    Returns:
        Status of the update operation
    
    Examples:
        # After successful classification:
        update_document_metadata_tool(
            document_id="DOC_20260127_143022_A3F8B",
            stage_name="classification",
            status="success",
            msg="Document classified as Passport",
            additional_data={
                "document_type": "Passport",
                "confidence": 0.95,
                "categories": ["identity_proof"]
            }
        )
        
        # After failed extraction:
        update_document_metadata_tool(
            document_id="DOC_20260127_143022_A3F8B",
            stage_name="extraction",
            status="fail",
            msg="OCR extraction failed",
            error="API timeout",
            trace="Traceback: ..."
        )
    """
    try:
        # Find document metadata file in intake directory
        intake_dir = Path(settings.documents_dir) / "intake"
        metadata_path = intake_dir / f"{document_id}.metadata.json"
        
        if not metadata_path.exists():
            return {
                "success": False,
                "document_id": document_id,
                "error": f"Document {document_id} not found in intake directory"
            }
        
        # Load existing metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Update the specific stage block
        stage_block = {
            "status": status,
            "msg": msg,
            "error": error,
            "trace": trace,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add any additional data to the stage block
        if additional_data:
            stage_block.update(additional_data)
        
        # Update the stage block in metadata
        metadata[stage_name] = stage_block
        
        # Update the current stage indicator if successful
        if status == "success":
            metadata["stage"] = stage_name
        
        metadata["last_updated"] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Updated {stage_name} metadata for {document_id}: {status}")
        
        return {
            "success": True,
            "document_id": document_id,
            "stage_name": stage_name,
            "status": status,
            "message": f"Metadata block '{stage_name}' updated successfully"
        }
            
    except Exception as e:
        logger.error(f"Error updating document metadata: {str(e)}")
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }
