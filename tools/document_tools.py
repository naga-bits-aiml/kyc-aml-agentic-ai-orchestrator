"""
Document Tools - CRUD operations for document management.

This module consolidates all document-related operations:
- Create: validate_document, batch_validate_documents, store_document
- Read: get_document_by_id, get_document_metadata, list_documents, list_all_documents
- Update: update_document_metadata
- Delete: delete_document

Documents are stored in a case-agnostic structure (documents/intake/) and can be
linked to multiple cases via the case_tools module.
"""
from crewai.tools import tool
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import shutil
from datetime import datetime

from utilities import (
    settings,
    logger,
    validate_file_extension,
    validate_file_size,
    generate_document_id,
    compute_file_hash,
    create_document_metadata,
    ensure_directory
)


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _validate_and_store_document(file_path: str, intake_dir: Path) -> Dict[str, Any]:
    """
    Internal function to validate document and store it with unique ID.
    
    If the document already exists (based on filename or stored path), 
    returns the existing document ID instead of creating a duplicate.
    
    Args:
        file_path: Path to document file
        intake_dir: Directory to store validated documents
        
    Returns:
        Dictionary with validation results and document metadata
    """
    logger.info(f"Validating and storing document: {file_path}")
    
    issues = []
    path = Path(file_path).resolve()
    intake_dir = Path(intake_dir).resolve()
    
    # Check existence
    if not path.exists():
        logger.error(f"❌ File does not exist: {file_path}")
        return {
            "success": False,
            "file_path": file_path,
            "issues": ["File does not exist"],
            "document_id": None,
            "stored_path": None,
            "metadata": {}
        }
    
    # CHECK IF DOCUMENT ALREADY EXISTS
    # Method 1: Check if this is already a document in intake (by path)
    if path.parent == intake_dir and path.suffix in settings.allowed_extensions:
        stem = path.stem
        if stem.startswith("DOC_") and len(stem.split("_")) >= 4:
            metadata_path = intake_dir / f"{stem}.metadata.json"
            if metadata_path.exists():
                logger.info(f"♻️ Found existing document by filename: {stem}")
                try:
                    with open(metadata_path, 'r') as f:
                        existing_metadata = json.load(f)
                    return {
                        "success": True,
                        "file_path": file_path,
                        "document_id": stem,
                        "stored_path": str(path),
                        "metadata": existing_metadata,
                        "issues": [],
                        "reused_existing": True
                    }
                except Exception as e:
                    logger.warning(f"Could not read existing metadata: {e}")
    
    # Method 2: Check for existing document by stored_path
    for metadata_file in intake_dir.glob("*.metadata.json"):
        try:
            with open(metadata_file, 'r') as f:
                existing_metadata = json.load(f)
            
            stored_path_in_metadata = Path(existing_metadata.get("stored_path", "")).resolve()
            if stored_path_in_metadata == path:
                document_id = existing_metadata.get("document_id")
                logger.info(f"♻️ Found existing document by path: {document_id}")
                return {
                    "success": True,
                    "file_path": file_path,
                    "document_id": document_id,
                    "stored_path": str(path),
                    "metadata": existing_metadata,
                    "issues": [],
                    "reused_existing": True
                }
        except Exception:
            continue
    
    # Method 3: Check for existing document by original filename
    for metadata_file in intake_dir.glob("*.metadata.json"):
        try:
            with open(metadata_file, 'r') as f:
                existing_metadata = json.load(f)
            
            if existing_metadata.get("original_filename") == path.name:
                document_id = existing_metadata.get("document_id")
                stored_path = existing_metadata.get("stored_path")
                if Path(stored_path).exists():
                    logger.info(f"♻️ Found existing document by original filename: {document_id}")
                    return {
                        "success": True,
                        "file_path": file_path,
                        "document_id": document_id,
                        "stored_path": stored_path,
                        "metadata": existing_metadata,
                        "issues": [],
                        "reused_existing": True
                    }
        except Exception:
            continue
    
    # Document doesn't exist - proceed with validation and storage
    
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
            f.read(1024)
    except Exception as e:
        issues.append(f"File is not readable: {str(e)}")
    
    # If validation failed, return early
    if issues:
        return {
            "success": False,
            "file_path": file_path,
            "issues": issues,
            "document_id": None,
            "stored_path": None,
            "metadata": {}
        }
    
    # Generate unique document ID
    document_id = generate_document_id()
    
    # Copy file to intake directory with new name
    file_extension = path.suffix
    new_filename = f"{document_id}{file_extension}"
    stored_path = intake_dir / new_filename
    
    try:
        intake_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, stored_path)
        
        # Compute file hash
        file_hash = compute_file_hash(str(stored_path))
        
        # Build metadata
        metadata = {
            "document_id": document_id,
            "original_filename": path.name,
            "stored_filename": new_filename,
            "stored_path": str(stored_path),
            "size_bytes": file_size,
            "extension": file_extension,
            "file_hash": file_hash,
            "stage": "intake",
            "uploaded_at": datetime.now().isoformat(),
            "linked_cases": [],
            "linked_documents": [],
            
            # Stage-specific information blocks
            "intake": {
                "status": "success",
                "msg": "Document validated and stored successfully",
                "error": None,
                "trace": None,
                "timestamp": datetime.now().isoformat(),
                "validation_status": "valid"
            },
            "classification": {
                "status": "pending",
                "msg": "",
                "error": None,
                "trace": None,
                "timestamp": None
            },
            "extraction": {
                "status": "pending",
                "msg": "",
                "error": None,
                "trace": None,
                "timestamp": None
            }
        }
        
        # Save metadata file
        metadata_path = intake_dir / f"{document_id}.metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Document stored successfully with ID: {document_id}")
        
        return {
            "success": True,
            "file_path": file_path,
            "document_id": document_id,
            "stored_path": str(stored_path),
            "metadata": metadata,
            "issues": []
        }
    except Exception as e:
        logger.error(f"Failed to store document: {e}")
        return {
            "success": False,
            "file_path": file_path,
            "issues": [f"Failed to store document: {str(e)}"],
            "document_id": None,
            "stored_path": None,
            "metadata": {}
        }


def _find_document_metadata(document_id: str) -> Optional[Dict[str, Any]]:
    """Find document metadata by searching across all stages."""
    stages = ["intake", "classification", "extraction", "processed"]
    
    for stage in stages:
        metadata_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading metadata for {document_id}: {e}")
    
    return None


# =============================================================================
# CREATE OPERATIONS
# =============================================================================

@tool("Validate Document")
def validate_document_tool(file_path: str) -> Dict[str, Any]:
    """
    Validate and store a single document with globally unique ID.
    
    Document is stored in documents/intake/ directory.
    No case association required - document can be linked to cases later.
    
    Checks:
    - File exists
    - Valid extension (PDF, PNG, JPG, JPEG)
    - Valid file size (within limits)
    - File is readable
    
    Args:
        file_path: Path to the document to validate and store
        
    Returns:
        Dictionary with:
        - success: Boolean indicating if document is valid
        - document_id: Globally unique document ID (if successful)
        - stored_path: Path where document is stored
        - metadata: Document metadata
        - issues: List of validation issues (if any)
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    return _validate_and_store_document(file_path, intake_dir)


@tool("Batch Validate Documents")
def batch_validate_documents_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Validate and store multiple documents with globally unique IDs.
    
    Documents are stored in documents/intake/ directory.
    No case association required - documents can be linked to cases later.
    
    Args:
        file_paths: List of document file paths to validate and store
        
    Returns:
        Dictionary with:
        - success: Boolean indicating if all documents are valid
        - total: Total number of documents
        - valid: Number of valid documents
        - invalid: Number of invalid documents
        - validated_documents: List of successfully validated documents
        - failed_documents: List of failed validations
    """
    logger.info(f"Batch validating {len(file_paths)} documents")
    
    intake_dir = Path(settings.documents_dir) / "intake"
    validated_documents = []
    failed_documents = []
    
    for file_path in file_paths:
        result = _validate_and_store_document(file_path, intake_dir)
        
        if result["success"]:
            log_msg = "♻️ REUSED" if result.get("reused_existing") else "📄 CREATED"
            logger.info(f"{log_msg}: {result['document_id']}")
            
            validated_documents.append({
                "document_id": result["document_id"],
                "original_filename": result["metadata"]["original_filename"],
                "stored_path": result["stored_path"],
                "file_size": result["metadata"]["size_bytes"],
                "validation_status": "valid",
                "reused_existing": result.get("reused_existing", False),
                "metadata": result.get("metadata", {})
            })
        else:
            failed_documents.append({
                "file_path": file_path,
                "issues": result["issues"],
                "validation_status": "invalid"
            })
    
    return {
        "success": len(failed_documents) == 0,
        "total": len(file_paths),
        "valid": len(validated_documents),
        "invalid": len(failed_documents),
        "validated_documents": validated_documents,
        "failed_documents": failed_documents
    }


@tool("Store Document")
def store_document_tool(source_path: str, destination_dir: str = None) -> Dict[str, Any]:
    """
    Store a document in the intake directory with proper metadata.
    
    Args:
        source_path: Path to the source document
        destination_dir: Destination directory (defaults to intake directory)
        
    Returns:
        Dictionary with:
        - success: Boolean indicating success
        - stored_path: Path where document was stored
        - metadata: Document metadata
    """
    import uuid
    
    logger.info(f"Storing document: {source_path}")
    
    try:
        dest_dir = destination_dir or str(Path(settings.documents_dir) / "intake")
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


# =============================================================================
# READ OPERATIONS
# =============================================================================

@tool("Get Document By ID")
def get_document_by_id_tool(document_id: str) -> Dict[str, Any]:
    """
    Retrieve document metadata by document ID.
    
    Searches across all stages (intake, classification, extraction, processed)
    to find the document.
    
    Args:
        document_id: The document ID (e.g., 'DOC_20260207_130709_4FA11')
        
    Returns:
        Dictionary with:
        - success: Boolean indicating if document was found
        - document_id: The document ID
        - stage: Current stage of the document
        - original_filename: Original file name
        - classification: Classification results
        - extraction: Extracted data
        - linked_cases: Cases this document is linked to
        - metadata: Full metadata for detailed access
    """
    logger.info(f"Getting document by ID: {document_id}")
    
    try:
        stages = ["intake", "classification", "extraction", "processed"]
        
        for stage in stages:
            metadata_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                return {
                    "success": True,
                    "document_id": document_id,
                    "stage": stage,
                    "original_filename": metadata.get('original_filename', 'unknown'),
                    "source_path": metadata.get('source_path', ''),
                    "status": metadata.get('status', 'unknown'),
                    "linked_cases": metadata.get('linked_cases', []),
                    "classification": metadata.get('classification', {}),
                    "extraction": metadata.get('extraction', {}),
                    "queue": metadata.get('queue', {}),
                    "intake_date": metadata.get('intake_date', ''),
                    "metadata": metadata
                }
        
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Document {document_id} not found in any stage"
        }
    except Exception as e:
        logger.error(f"Failed to get document by ID: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }


@tool("Get Document Metadata")
def get_document_metadata_tool(file_path: str) -> Dict[str, Any]:
    """
    Retrieve metadata for a document by file path.
    
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
        dir_path = Path(directory) if directory else Path(settings.documents_dir) / "intake"
        
        if not dir_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {dir_path}"
            }
        
        # Get all files
        if extension:
            files = list(dir_path.glob(f"*{extension}"))
        else:
            files = [f for f in dir_path.iterdir() if f.is_file() and not f.name.endswith('.metadata.json')]
        
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


@tool("List All Documents")
def list_all_documents_tool(stage: Optional[str] = None, page: int = 1, limit: int = 50) -> Dict[str, Any]:
    """
    List all documents with pagination support.
    
    Optionally filter by stage.
    
    Args:
        stage: Optional stage filter (intake, classification, extraction, processed)
        page: Page number (1-indexed)
        limit: Number of documents per page
        
    Returns:
        Dictionary with:
        - success: Boolean
        - documents: List of documents
        - total: Total count
        - page: Current page
        - pages: Total pages
    """
    logger.info(f"Listing all documents (stage={stage}, page={page}, limit={limit})")
    
    try:
        stages = [stage] if stage else ["intake", "classification", "extraction", "processed"]
        all_documents = []
        
        for s in stages:
            stage_dir = Path(settings.documents_dir) / s
            if not stage_dir.exists():
                continue
            
            for metadata_file in sorted(stage_dir.glob("*.metadata.json"), reverse=True):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                all_documents.append({
                    "document_id": metadata["document_id"],
                    "original_filename": metadata["original_filename"],
                    "stage": s,
                    "uploaded_at": metadata.get("uploaded_at"),
                    "size_bytes": metadata.get("size_bytes"),
                    "linked_cases": metadata.get("linked_cases", []),
                    "classification": metadata.get("classification", {}),
                    "extraction": metadata.get("extraction", {})
                })
        
        # Pagination
        total = len(all_documents)
        total_pages = (total + limit - 1) // limit
        start = (page - 1) * limit
        end = start + limit
        paginated_docs = all_documents[start:end]
        
        return {
            "success": True,
            "documents": paginated_docs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": total_pages
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {
            "success": False,
            "error": str(e),
            "documents": [],
            "total": 0
        }


@tool("Resolve Document Paths")
def resolve_document_paths_tool(paths: List[str], recursive: bool = False) -> Dict[str, Any]:
    """
    Resolve input paths into a list of valid document files.

    Accepts a mix of file and directory paths. Directories are scanned for
    supported file types based on settings.allowed_extensions.

    Args:
        paths: List of file or directory paths
        recursive: Whether to scan directories recursively (default: False)

    Returns:
        Dictionary with resolved files and skipped paths
    """
    logger.info(f"Resolving {len(paths)} input path(s)")

    allowed_extensions = [ext.lower() for ext in settings.allowed_extensions]
    resolved_files: List[str] = []
    skipped_paths: List[Dict[str, str]] = []
    directories_scanned: List[str] = []
    seen_files = set()

    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()

        if not path.exists():
            skipped_paths.append({"path": str(path), "reason": "Path does not exist"})
            continue

        if path.is_dir():
            directories_scanned.append(str(path))
            iterator = path.rglob("*") if recursive else path.iterdir()
            entries = sorted([p for p in iterator if p.is_file()], key=lambda p: p.name)
            for entry in entries:
                if entry.suffix.lower() not in allowed_extensions:
                    skipped_paths.append({
                        "path": str(entry),
                        "reason": "Unsupported extension"
                    })
                    continue
                resolved_path = str(entry.resolve())
                if resolved_path in seen_files:
                    continue
                seen_files.add(resolved_path)
                resolved_files.append(resolved_path)
            continue

        if path.is_file():
            if path.suffix.lower() not in allowed_extensions:
                skipped_paths.append({
                    "path": str(path),
                    "reason": "Unsupported extension"
                })
                continue
            resolved_path = str(path)
            if resolved_path not in seen_files:
                seen_files.add(resolved_path)
                resolved_files.append(resolved_path)
            continue

        skipped_paths.append({"path": str(path), "reason": "Unsupported path type"})

    return {
        "success": True,
        "resolved_files": resolved_files,
        "directories_scanned": directories_scanned,
        "skipped_paths": skipped_paths,
        "allowed_extensions": allowed_extensions,
        "total_resolved": len(resolved_files)
    }


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

@tool("Update Document Metadata")
def update_document_metadata_tool(document_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata for a document.
    
    Args:
        document_id: The document ID
        updates: Dictionary of fields to update
        
    Returns:
        Dictionary with success status and updated metadata
    """
    logger.info(f"Updating metadata for document: {document_id}")
    
    try:
        stages = ["intake", "classification", "extraction", "processed"]
        
        for stage in stages:
            metadata_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Apply updates
                for key, value in updates.items():
                    if isinstance(value, dict) and isinstance(metadata.get(key), dict):
                        metadata[key].update(value)
                    else:
                        metadata[key] = value
                
                metadata['last_updated'] = datetime.now().isoformat()
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                return {
                    "success": True,
                    "document_id": document_id,
                    "stage": stage,
                    "message": "Metadata updated successfully",
                    "metadata": metadata
                }
        
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Document {document_id} not found"
        }
    except Exception as e:
        logger.error(f"Failed to update document metadata: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

@tool("Delete Document")
def delete_document_tool(document_id: str, force: bool = False) -> Dict[str, Any]:
    """
    Delete a document and its metadata.
    
    Args:
        document_id: The document ID to delete
        force: If True, delete even if linked to cases (will unlink first)
        
    Returns:
        Dictionary with success status
    """
    logger.info(f"Deleting document: {document_id}")
    
    try:
        stages = ["intake", "classification", "extraction", "processed"]
        
        for stage in stages:
            stage_dir = Path(settings.documents_dir) / stage
            metadata_path = stage_dir / f"{document_id}.metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Check if linked to cases
                linked_cases = metadata.get('linked_cases', [])
                if linked_cases and not force:
                    return {
                        "success": False,
                        "document_id": document_id,
                        "error": f"Document is linked to cases: {linked_cases}. Use force=True to delete anyway."
                    }
                
                # Delete the document file
                stored_path = metadata.get('stored_path')
                if stored_path and Path(stored_path).exists():
                    Path(stored_path).unlink()
                
                # Delete metadata file
                metadata_path.unlink()
                
                logger.info(f"Deleted document: {document_id}")
                
                return {
                    "success": True,
                    "document_id": document_id,
                    "stage": stage,
                    "message": f"Document {document_id} deleted successfully"
                }
        
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Document {document_id} not found"
        }
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }
