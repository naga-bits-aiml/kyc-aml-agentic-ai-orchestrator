"""
Document processing tools for agents.

These tools handle document intake, validation, storage, and metadata management.
"""
from crewai.tools import tool
from typing import Dict, Any, List
from pathlib import Path
import json
from utilities import (
    config,
    logger,
    validate_file_extension,
    validate_file_size,
    create_document_metadata,
    ensure_directory
)


@tool("Validate Document")
def validate_document_tool(file_path: str) -> Dict[str, Any]:
    """
    Validate a document file for processing.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Dictionary with validation results including:
        - is_valid: Boolean indicating if document is valid
        - errors: List of validation errors
        - file_info: Basic file information
    """
    logger.info(f"Validating document: {file_path}")
    
    errors = []
    file_path_obj = Path(file_path)
    
    # Check if file exists
    if not file_path_obj.exists():
        return {
            "is_valid": False,
            "errors": [f"File not found: {file_path}"],
            "file_info": None
        }
    
    # Validate extension
    if not validate_file_extension(file_path, config.allowed_extensions):
        errors.append(f"Invalid file extension. Allowed: {config.allowed_extensions}")
    
    # Validate file size
    if not validate_file_size(file_path, config.max_document_size_bytes):
        errors.append(f"File exceeds maximum size of {config.max_document_size_mb}MB")
    
    file_info = {
        "name": file_path_obj.name,
        "size": file_path_obj.stat().st_size,
        "extension": file_path_obj.suffix
    }
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "file_info": file_info
    }


@tool("Store Document")
def store_document_tool(source_path: str, destination_dir: str = None) -> Dict[str, Any]:
    """
    Store a document in the intake directory with proper metadata.
    
    Args:
        source_path: Path to the source document
        destination_dir: Destination directory (defaults to intake directory)
        
    Returns:
        Dictionary with storage results including:
        - success: Boolean indicating success
        - stored_path: Path where document was stored
        - metadata: Document metadata
    """
    import shutil
    from datetime import datetime
    import uuid
    
    logger.info(f"Storing document: {source_path}")
    
    try:
        dest_dir = destination_dir or str(config.intake_dir)
        ensure_directory(dest_dir)
        
        # Generate unique filename
        source_file = Path(source_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        new_filename = f"{timestamp}_{unique_id}_{source_file.name}"
        dest_path = Path(dest_dir) / new_filename
        
        # Copy file
        shutil.copy2(source_path, dest_path)
        
        # Create metadata
        metadata = create_document_metadata(str(dest_path))
        metadata['original_filename'] = source_file.name
        metadata['stored_filename'] = new_filename
        metadata['timestamp'] = timestamp
        
        return {
            "success": True,
            "stored_path": str(dest_path),
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Failed to store document: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Get Document Metadata")
def get_document_metadata_tool(file_path: str) -> Dict[str, Any]:
    """
    Retrieve metadata for a document.
    
    Args:
        file_path: Path to the document
        
    Returns:
        Document metadata dictionary
    """
    logger.info(f"Getting metadata for: {file_path}")
    
    try:
        metadata = create_document_metadata(file_path)
        return {
            "success": True,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Failed to get metadata: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("Get Document By ID")
def get_document_by_id_tool(document_id: str) -> Dict[str, Any]:
    """
    Retrieve document metadata by document ID.
    
    This tool looks up a document using its unique ID (e.g., DOC_20260207_130709_4FA11)
    and returns all stored metadata including classification and extraction results.
    
    Args:
        document_id: The document ID (e.g., 'DOC_20260207_130709_4FA11')
        
    Returns:
        Dictionary with document metadata including:
        - success: Boolean indicating if document was found
        - document_id: The document ID
        - original_filename: Original file name
        - classification: Classification results (type, confidence)
        - extraction: Extracted data (entities, persons, etc.)
        - linked_cases: Cases this document is linked to
        - status: Processing status
    """
    logger.info(f"Getting document by ID: {document_id}")
    
    try:
        # Documents are stored in intake folder with {doc_id}.metadata.json
        intake_dir = Path(config.documents_dir) / "intake"
        metadata_file = intake_dir / f"{document_id}.metadata.json"
        
        if not metadata_file.exists():
            return {
                "success": False,
                "error": f"Document {document_id} not found in intake folder"
            }
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        return {
            "success": True,
            "document_id": document_id,
            "original_filename": metadata.get('original_filename', 'unknown'),
            "source_path": metadata.get('source_path', ''),
            "status": metadata.get('status', 'unknown'),
            "linked_cases": metadata.get('linked_cases', []),
            "classification": metadata.get('classification', {}),
            "extraction": metadata.get('extraction', {}),
            "queue": metadata.get('queue', {}),
            "intake_date": metadata.get('intake_date', ''),
            "metadata": metadata  # Full metadata for detailed access
        }
    except Exception as e:
        logger.error(f"Failed to get document by ID: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool("List Documents")
def list_documents_tool(directory: str = None, extension: str = None) -> Dict[str, Any]:
    """
    List documents in a directory.
    
    Args:
        directory: Directory to list (defaults to intake directory)
        extension: Filter by file extension (e.g., '.pdf')
        
    Returns:
        Dictionary with list of documents and their details
    """
    logger.info(f"Listing documents in: {directory or 'intake directory'}")
    
    try:
        dir_path = Path(directory) if directory else config.intake_dir
        
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {dir_path}"
            }
        
        # Get all files
        if extension:
            files = list(dir_path.glob(f"*{extension}"))
        else:
            files = [f for f in dir_path.iterdir() if f.is_file()]
        
        documents = []
        for file in files:
            documents.append({
                "name": file.name,
                "path": str(file),
                "size": file.stat().st_size,
                "extension": file.suffix,
                "modified": file.stat().st_mtime
            })
        
        return {
            "success": True,
            "count": len(documents),
            "documents": documents
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {
            "success": False,
            "error": str(e)
        }
