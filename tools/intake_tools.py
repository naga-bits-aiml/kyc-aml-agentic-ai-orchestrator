"""
Document intake and validation tools for CrewAI agents.

These tools handle file validation and organization without requiring agent classes.
"""
from crewai.tools import tool
from typing import Dict, Any, List
from pathlib import Path
from utilities import validate_file_extension, validate_file_size, settings, logger
from case_metadata_manager import StagedCaseMetadataManager
import shutil


def _validate_single_document(file_path: str) -> Dict[str, Any]:
    """
    Internal validation function (not a tool).
    Validates a single document without tool decorator.
    """
    logger.info(f"Validating document: {file_path}")
    
    issues = []
    path = Path(file_path)
    
    # Check existence
    if not path.exists():
        return {
            "success": False,
            "file_path": file_path,
            "issues": ["File does not exist"],
            "metadata": {}
        }
    
    # Validate extension
    if not validate_file_extension(file_path, settings.allowed_extensions):
        issues.append(f"Invalid file extension. Allowed: {', '.join(settings.allowed_extensions)}")
    
    # Validate size
    file_size = path.stat().st_size
    if file_size == 0:
        issues.append("File is empty")
    elif not validate_file_size(file_path, settings.max_document_size_bytes):
        issues.append(f"File size exceeds limit ({settings.max_document_size_mb}MB)")
    
    # Check readability
    try:
        with open(file_path, 'rb') as f:
            f.read(1024)  # Try reading first 1KB
    except Exception as e:
        issues.append(f"File is not readable: {str(e)}")
    
    # Build metadata
    metadata = {
        "size_bytes": file_size,
        "extension": path.suffix,
        "filename": path.name
    }
    
    return {
        "success": len(issues) == 0,
        "file_path": file_path,
        "issues": issues,
        "metadata": metadata
    }


@tool("Validate Document")
def validate_document_tool(file_path: str) -> Dict[str, Any]:
    """
    Validate a single document for intake.
    
    Checks:
    - File exists
    - Valid extension (PDF, PNG, JPG, JPEG)
    - Valid file size (within limits)
    - File is readable
    
    Args:
        file_path: Path to the document to validate
        
    Returns:
        Dictionary with validation results:
        - success: Boolean indicating if document is valid
        - file_path: Original file path
        - issues: List of validation issues (if any)
        - metadata: File metadata (size, extension, etc.)
    """
    return _validate_single_document(file_path)


@tool("Batch Validate Documents")
def batch_validate_documents_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Validate multiple documents in batch.
    
    Args:
        file_paths: List of document file paths to validate
        
    Returns:
        Dictionary with batch validation results:
        - success: Boolean indicating if all documents are valid
        - total: Total number of documents
        - valid: Number of valid documents
        - invalid: Number of invalid documents
        - results: List of validation results for each document
    """
    logger.info(f"Batch validating {len(file_paths)} documents")
    
    results = []
    valid_count = 0
    invalid_count = 0
    
    for file_path in file_paths:
        # Call internal validation function, not the tool
        result = _validate_single_document(file_path)
        results.append(result)
        
        if result["success"]:
            valid_count += 1
        else:
            invalid_count += 1
    
    return {
        "success": invalid_count == 0,
        "total": len(file_paths),
        "valid": valid_count,
        "invalid": invalid_count,
        "results": results
    }


@tool("Organize Case Documents")
def organize_case_documents_tool(case_id: str, file_paths: List[str]) -> Dict[str, Any]:
    """
    Organize validated documents into case folder structure using stage-based architecture.
    Documents are added to the intake stage.
    
    Args:
        case_id: Case identifier
        file_paths: List of validated document file paths
        
    Returns:
        Dictionary with organization results:
        - success: Boolean indicating success
        - case_id: Case identifier
        - case_path: Path to case folder
        - organized_files: List of document entries with stage info
    """
    logger.info(f"Organizing documents for case: {case_id}")
    
    try:
        # Get or create case directory
        case_path = Path(settings.documents_dir) / "cases" / case_id
        case_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize stage manager
        manager = StagedCaseMetadataManager(case_path)
        
        organized_files = []
        
        for idx, file_path in enumerate(file_paths, 1):
            src = Path(file_path)
            
            # Generate document ID
            doc_id = f"{case_id}_DOC_{idx:03d}"
            
            # Add document to intake stage
            doc_entry = manager.add_document(
                document_id=doc_id,
                filename=src.name,
                source_path=str(src)
            )
            
            organized_files.append(doc_entry)
            logger.info(f"Added {doc_id} to intake stage")
        
        return {
            "success": True,
            "case_id": case_id,
            "case_path": str(case_path),
            "organized_files": organized_files,
            "total_documents": len(organized_files),
            "stage": "intake"
        }
    except Exception as e:
        logger.error(f"Organization failed: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e)
        }
