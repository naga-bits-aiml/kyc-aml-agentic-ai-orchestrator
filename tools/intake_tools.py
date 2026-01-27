"""
Document intake and validation tools for CrewAI agents.

These tools handle file validation and organization with globally unique document IDs.
Documents are stored in a case-agnostic structure and can be linked to multiple cases.
"""
from crewai.tools import tool
from typing import Dict, Any, List, Optional
from pathlib import Path
from utilities import validate_file_extension, validate_file_size, settings, logger, generate_document_id, compute_file_hash
from case_metadata_manager import StagedCaseMetadataManager
import shutil
import json
from datetime import datetime


def _validate_and_store_document(file_path: str, intake_dir: Path) -> Dict[str, Any]:
    """
    Internal function to validate document and store it with unique ID.
    Generates globally unique document ID and stores in intake directory.
    
    Args:
        file_path: Path to document file
        intake_dir: Directory to store validated documents
        
    Returns:
        Dictionary with validation results and document metadata
    """
    logger.info(f"Validating and storing document: {file_path}")
    
    issues = []
    path = Path(file_path)
    
    # Check existence
    if not path.exists():
        return {
            "success": False,
            "file_path": file_path,
            "issues": ["File does not exist"],
            "document_id": None,
            "stored_path": None,
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
            "validation_status": "valid"
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
        Dictionary with validation results:
        - success: Boolean indicating if document is valid
        - document_id: Globally unique document ID (if successful)
        - stored_path: Path where document is stored (if successful)
        - metadata: Document metadata including original filename, size, hash, etc.
        - issues: List of validation issues (if any)
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    return _validate_and_store_document(file_path, intake_dir)


@tool("Batch Validate Documents")
def batch_validate_documents_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Validate and store multiple documents with globally unique IDs.
    Documents are stored in documents/intake/ directory with generated IDs.
    No case association required - documents can be linked to cases later.
    
    Args:
        file_paths: List of document file paths to validate and store
        
    Returns:
        Dictionary with batch validation results:
        - success: Boolean indicating if all documents are valid
        - total: Total number of documents
        - valid: Number of valid documents
        - invalid: Number of invalid documents
        - validated_documents: List of successfully validated documents with IDs
        - failed_documents: List of failed validations
    """
    logger.info(f"Batch validating and storing {len(file_paths)} documents")
    
    # Get intake directory (case-agnostic)
    intake_dir = Path(settings.documents_dir) / "intake"
    
    validated_documents = []
    failed_documents = []
    
    for file_path in file_paths:
        result = _validate_and_store_document(file_path, intake_dir)
        
        if result["success"]:
            validated_documents.append({
                "document_id": result["document_id"],
                "original_filename": result["metadata"]["original_filename"],
                "stored_path": result["stored_path"],
                "file_size": result["metadata"]["size_bytes"],
                "mime_type": f"application/{result['metadata']['extension'][1:]}",
                "validation_status": "valid",
                "validation_timestamp": result["metadata"]["uploaded_at"],
                "stage": "intake"
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


@tool("Organize Case Documents")
def organize_case_documents_tool(case_id: str, file_paths: List[str]) -> Dict[str, Any]:
    """
    DEPRECATED: Use batch_validate_documents_tool followed by link_document_to_case_tool.
    This tool is kept for backward compatibility but will be removed in future versions.
    
    Organize validated documents into case folder structure using stage-based architecture.
    Documents are added to the intake stage.
    
    Args:
        case_id: Case identifier
        file_paths: List of validated document file paths
        
    Returns:
        Dictionary with organization results
    """
    logger.warning("organize_case_documents_tool is deprecated. Use batch_validate_documents_tool + link_document_to_case_tool")
    
    # Process documents first
    validation_result = batch_validate_documents_tool(file_paths)
    
    if not validation_result["success"]:
        return {
            "success": False,
            "case_id": case_id,
            "error": "Document validation failed",
            "details": validation_result
        }
    
    # Link all validated documents to case
    linked_docs = []
    for doc in validation_result["validated_documents"]:
        link_result = link_document_to_case_tool(doc["document_id"], case_id)
        if link_result["success"]:
            linked_docs.append(link_result)
    
    return {
        "success": True,
        "case_id": case_id,
        "organized_files": linked_docs,
        "total_documents": len(linked_docs),
        "stage": "intake"
    }


@tool("Link Document to Case")
def link_document_to_case_tool(document_id: str, case_id: str) -> Dict[str, Any]:
    """
    Link an existing document to a case.
    Supports many-to-many relationships (one document can be linked to multiple cases).
    
    Args:
        document_id: Globally unique document ID (e.g., DOC_20260127_143022_A3F8B)
        case_id: Case identifier (e.g., KYC_2026_001)
        
    Returns:
        Dictionary with linking results:
        - success: Boolean indicating success
        - document_id: Document ID
        - case_id: Case ID
        - message: Status message
    """
    logger.info(f"Linking document {document_id} to case {case_id}")
    
    try:
        # Find document metadata file in intake or other stages
        stages = ["intake", "classification", "extraction", "processed"]
        metadata_path = None
        current_stage = None
        
        for stage in stages:
            potential_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
            if potential_path.exists():
                metadata_path = potential_path
                current_stage = stage
                break
        
        if not metadata_path:
            return {
                "success": False,
                "document_id": document_id,
                "case_id": case_id,
                "error": f"Document {document_id} not found in any stage"
            }
        
        # Load existing metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Add case to linked_cases if not already present
        if "linked_cases" not in metadata:
            metadata["linked_cases"] = []
        
        if case_id not in metadata["linked_cases"]:
            metadata["linked_cases"].append(case_id)
            metadata["last_updated"] = datetime.now().isoformat()
            
            # Save updated metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Document {document_id} linked to case {case_id}")
            
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "stage": current_stage,
                "linked_cases": metadata["linked_cases"],
                "message": f"Document successfully linked to case {case_id}"
            }
        else:
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "stage": current_stage,
                "linked_cases": metadata["linked_cases"],
                "message": f"Document already linked to case {case_id}"
            }
    except Exception as e:
        logger.error(f"Failed to link document to case: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "case_id": case_id,
            "error": str(e)
        }


@tool("Get Document by ID")
def get_document_by_id_tool(document_id: str) -> Dict[str, Any]:
    """
    Retrieve document metadata by document ID.
    Searches across all stages to find the document.
    
    Args:
        document_id: Globally unique document ID
        
    Returns:
        Dictionary with document details:
        - success: Boolean indicating if document was found
        - document_id: Document ID
        - metadata: Full document metadata
        - stage: Current stage of the document
    """
    logger.info(f"Retrieving document: {document_id}")
    
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
                    "metadata": metadata
                }
        
        return {
            "success": False,
            "document_id": document_id,
            "error": "Document not found"
        }
    except Exception as e:
        logger.error(f"Failed to retrieve document: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }


@tool("List Documents by Case")
def list_documents_by_case_tool(case_id: str) -> Dict[str, Any]:
    """
    List all documents linked to a specific case.
    Searches across all stages.
    
    Args:
        case_id: Case identifier
        
    Returns:
        Dictionary with:
        - success: Boolean
        - case_id: Case ID
        - documents: List of documents linked to this case
        - total: Total count
    """
    logger.info(f"Listing documents for case: {case_id}")
    
    try:
        stages = ["intake", "classification", "extraction", "processed"]
        documents = []
        
        for stage in stages:
            stage_dir = Path(settings.documents_dir) / stage
            if not stage_dir.exists():
                continue
            
            for metadata_file in stage_dir.glob("*.metadata.json"):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                if case_id in metadata.get("linked_cases", []):
                    documents.append({
                        "document_id": metadata["document_id"],
                        "original_filename": metadata["original_filename"],
                        "stage": stage,
                        "uploaded_at": metadata.get("uploaded_at"),
                        "size_bytes": metadata.get("size_bytes")
                    })
        
        return {
            "success": True,
            "case_id": case_id,
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        logger.error(f"Failed to list documents for case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e),
            "documents": [],
            "total": 0
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
                    "linked_cases": metadata.get("linked_cases", [])
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
