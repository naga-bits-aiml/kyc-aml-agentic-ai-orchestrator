"""
Queue Agent Tools - Deterministic file operations for document queue management.

These tools handle:
- Path scanning (file or folder)
- Folder expansion (recursive file collection)
- PDF to image conversion
- Queue building and management
- Metadata JSON creation

All operations are deterministic - no LLM reasoning for file operations.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
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

# PDF conversion support
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available. PDF conversion disabled.")


# ==================== HELPER FUNCTIONS ====================

def generate_document_id() -> str:
    """Generate unique document ID with timestamp and random suffix."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = hashlib.md5(os.urandom(8)).hexdigest()[:5].upper()
    return f"DOC_{timestamp}_{random_suffix}"


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file for deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_metadata_schema() -> Dict[str, Any]:
    """
    Return the standard metadata JSON schema for documents.
    
    Schema includes:
    - Document identification
    - File information
    - Processing status for each stage
    - Timestamps and tracking
    """
    return {
        "document_id": "",
        "original_filename": "",
        "stored_filename": "",
        "stored_path": "",
        "extension": "",
        "size_bytes": 0,
        "file_hash": "",
        "created_at": "",
        "updated_at": "",
        
        # Parent/child relationship for PDF pages
        "parent_document_id": None,
        "child_document_ids": [],
        "page_number": None,
        "total_pages": None,
        
        # Processing stages
        "queue": {
            "status": "pending",  # pending, processing, completed, failed, skipped
            "queued_at": None,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "retry_count": 0
        },
        "classification": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "result": None,  # API response
            "document_type": None,
            "confidence": None,
            "error": None,
            "retry_count": 0
        },
        "extraction": {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "result": None,  # API response
            "extracted_fields": {},
            "error": None,
            "retry_count": 0
        },
        
        # Overall status
        "processing_status": "queued",  # queued, processing, completed, failed
        "last_error": None,
        "requires_review": False
    }


def create_metadata_file(
    file_path: str,
    document_id: str,
    parent_id: Optional[str] = None,
    page_number: Optional[int] = None,
    total_pages: Optional[int] = None,
    original_filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create metadata JSON file for a document.
    
    Args:
        file_path: Path to the document file
        document_id: Unique document identifier
        parent_id: Parent document ID (for PDF pages)
        page_number: Page number (for PDF pages)
        total_pages: Total pages in parent PDF
        original_filename: Original source filename (before renaming to doc ID)
        
    Returns:
        Created metadata dictionary
    """
    path = Path(file_path)
    intake_dir = Path(settings.documents_dir) / "intake"
    intake_dir.mkdir(parents=True, exist_ok=True)
    
    # Build metadata
    metadata = get_metadata_schema()
    metadata["document_id"] = document_id
    # Use original_filename if provided, otherwise fall back to path.name
    metadata["original_filename"] = original_filename if original_filename else path.name
    metadata["stored_filename"] = f"{document_id}{path.suffix}"
    metadata["stored_path"] = str(intake_dir / metadata["stored_filename"])
    metadata["extension"] = path.suffix.lower()
    metadata["size_bytes"] = path.stat().st_size
    metadata["file_hash"] = compute_file_hash(str(path))
    metadata["created_at"] = datetime.now().isoformat()
    metadata["updated_at"] = datetime.now().isoformat()
    
    # Parent/child info
    if parent_id:
        metadata["parent_document_id"] = parent_id
        metadata["page_number"] = page_number
        metadata["total_pages"] = total_pages
    
    # Queue status
    metadata["queue"]["status"] = "pending"
    metadata["queue"]["queued_at"] = datetime.now().isoformat()
    
    # Save metadata file
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Created metadata file: {metadata_path}")
    return metadata


# ==================== TOOL DEFINITIONS ====================

@tool
def scan_input_path(input_path: str) -> Dict[str, Any]:
    """
    Scan an input path to determine if it's a file or folder.
    
    This is the entry point for the queue agent. It determines
    whether the input is a single file or a directory that needs
    to be expanded.
    
    Args:
        input_path: File path or folder path provided by user
        
    Returns:
        Dictionary with:
        - path_type: 'file', 'folder', or 'invalid'
        - path: Resolved absolute path
        - file_count: Number of files (1 for file, count for folder)
        - message: Status message
    """
    path = Path(input_path).expanduser().resolve()
    
    if not path.exists():
        return {
            "path_type": "invalid",
            "path": str(path),
            "file_count": 0,
            "message": f"Path does not exist: {path}"
        }
    
    if path.is_file():
        return {
            "path_type": "file",
            "path": str(path),
            "file_count": 1,
            "message": f"Single file detected: {path.name}"
        }
    
    if path.is_dir():
        # Count supported files recursively
        supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        files = [
            f for f in path.rglob("*")
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]
        return {
            "path_type": "folder",
            "path": str(path),
            "file_count": len(files),
            "message": f"Folder detected with {len(files)} supported files"
        }
    
    return {
        "path_type": "invalid",
        "path": str(path),
        "file_count": 0,
        "message": f"Unknown path type: {path}"
    }


@tool
def expand_folder(folder_path: str, recursive: bool = True) -> Dict[str, Any]:
    """
    Recursively collect all supported files from a folder.
    
    Supported file types: PDF, JPG, JPEG, PNG, TIFF, TIF, BMP
    
    Args:
        folder_path: Path to folder to scan
        recursive: Whether to scan subdirectories (default: True)
        
    Returns:
        Dictionary with:
        - success: Boolean
        - files: List of file paths
        - by_type: Dict grouping files by extension
        - message: Status message
    """
    path = Path(folder_path).expanduser().resolve()
    
    if not path.exists() or not path.is_dir():
        return {
            "success": False,
            "files": [],
            "by_type": {},
            "message": f"Invalid folder path: {path}"
        }
    
    supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
    
    if recursive:
        all_files = list(path.rglob("*"))
    else:
        all_files = list(path.glob("*"))
    
    files = [
        str(f) for f in all_files
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]
    
    # Group by extension
    by_type = {}
    for f in files:
        ext = Path(f).suffix.lower()
        if ext not in by_type:
            by_type[ext] = []
        by_type[ext].append(f)
    
    return {
        "success": True,
        "files": sorted(files),
        "by_type": by_type,
        "message": f"Found {len(files)} files in {path}"
    }


@tool
def split_pdf_to_images(pdf_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """
    Split a PDF document into individual page images.
    
    Each page becomes a child document with its own document ID
    and metadata file. The parent PDF's metadata is updated to
    reference all child documents.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum pages to convert (default: 50)
        
    Returns:
        Dictionary with:
        - success: Boolean
        - parent_document_id: Parent PDF's document ID
        - child_documents: List of child document IDs
        - child_paths: List of child image file paths
        - message: Status message
    """
    if not PDF2IMAGE_AVAILABLE:
        return {
            "success": False,
            "parent_document_id": None,
            "child_documents": [],
            "child_paths": [],
            "message": "pdf2image not installed. Run: pip install pdf2image"
        }
    
    path = Path(pdf_path).expanduser().resolve()
    
    if not path.exists():
        return {
            "success": False,
            "parent_document_id": None,
            "child_documents": [],
            "child_paths": [],
            "message": f"PDF not found: {path}"
        }
    
    if path.suffix.lower() != '.pdf':
        return {
            "success": False,
            "parent_document_id": None,
            "child_documents": [],
            "child_paths": [],
            "message": f"Not a PDF file: {path}"
        }
    
    try:
        # Create parent document
        parent_id = generate_document_id()
        intake_dir = Path(settings.documents_dir) / "intake"
        intake_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy PDF to intake
        import shutil
        stored_pdf_path = intake_dir / f"{parent_id}.pdf"
        shutil.copy2(str(path), str(stored_pdf_path))
        
        # Convert PDF to images
        logger.info(f"Converting PDF: {path} (max {max_pages} pages)")
        images = convert_from_path(
            str(path),
            dpi=200,
            first_page=1,
            last_page=max_pages,
            fmt='jpeg'
        )
        
        total_pages = len(images)
        child_ids = []
        child_paths = []
        
        # Create child documents for each page
        original_pdf_stem = path.stem  # e.g., "my_document" from "my_document.pdf"
        for page_num, image in enumerate(images, start=1):
            child_id = generate_document_id()
            child_filename = f"{child_id}.jpg"
            child_path = intake_dir / child_filename
            
            # Save image
            image.save(str(child_path), 'JPEG', quality=85)
            
            # Create child metadata with original PDF page reference
            create_metadata_file(
                file_path=str(child_path),
                document_id=child_id,
                parent_id=parent_id,
                page_number=page_num,
                total_pages=total_pages,
                original_filename=f"{original_pdf_stem}_page{page_num}.jpg"  # e.g., "my_document_page1.jpg"
            )
            
            child_ids.append(child_id)
            child_paths.append(str(child_path))
            logger.info(f"Created child document: {child_id} (page {page_num}/{total_pages})")
        
        # Create parent metadata with child references
        original_pdf_name = path.name  # Original PDF filename
        parent_metadata = create_metadata_file(
            file_path=str(stored_pdf_path),
            document_id=parent_id,
            original_filename=original_pdf_name  # Preserve original PDF name
        )
        parent_metadata["child_document_ids"] = child_ids
        parent_metadata["total_pages"] = total_pages
        parent_metadata["queue"]["status"] = "completed"
        parent_metadata["queue"]["completed_at"] = datetime.now().isoformat()
        parent_metadata["processing_status"] = "split"
        
        # Mark classification/extraction as skipped for parent PDF
        # Only child documents (page images) get classified/extracted
        parent_metadata["classification"]["status"] = "skipped"
        parent_metadata["classification"]["document_type"] = "pdf_container"
        parent_metadata["extraction"]["status"] = "skipped"
        
        # Save updated parent metadata
        parent_metadata_path = intake_dir / f"{parent_id}.metadata.json"
        with open(parent_metadata_path, 'w') as f:
            json.dump(parent_metadata, f, indent=2)
        
        return {
            "success": True,
            "parent_document_id": parent_id,
            "child_documents": child_ids,
            "child_paths": child_paths,
            "total_pages": total_pages,
            "message": f"Split PDF into {total_pages} page images"
        }
        
    except Exception as e:
        logger.error(f"Failed to split PDF: {e}")
        return {
            "success": False,
            "parent_document_id": None,
            "child_documents": [],
            "child_paths": [],
            "message": f"Error splitting PDF: {str(e)}"
        }


@tool
def build_processing_queue(file_paths: List[str]) -> Dict[str, Any]:
    """
    Build processing queue from a list of file paths.
    
    For each file:
    - If PDF: Split to images and queue child documents
    - If image: Queue directly
    - Create metadata JSON for each document
    
    Args:
        file_paths: List of file paths to queue
        
    Returns:
        Dictionary with:
        - success: Boolean
        - queue: List of document IDs to process
        - pdf_parents: List of parent PDF document IDs
        - total_documents: Total documents queued
        - message: Status message
    """
    queue = []
    pdf_parents = []
    errors = []
    
    intake_dir = Path(settings.documents_dir) / "intake"
    intake_dir.mkdir(parents=True, exist_ok=True)
    
    for file_path in file_paths:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            errors.append(f"File not found: {path}")
            continue
        
        if path.suffix.lower() == '.pdf':
            # Split PDF and queue children
            result = split_pdf_to_images.invoke({"pdf_path": str(path)})
            if result["success"]:
                pdf_parents.append(result["parent_document_id"])
                queue.extend(result["child_documents"])
            else:
                errors.append(result["message"])
        else:
            # Queue image directly
            import shutil
            doc_id = generate_document_id()
            original_name = path.name  # Preserve original filename before renaming
            stored_path = intake_dir / f"{doc_id}{path.suffix}"
            shutil.copy2(str(path), str(stored_path))
            
            create_metadata_file(
                file_path=str(stored_path),
                document_id=doc_id,
                original_filename=original_name  # Pass original filename
            )
            queue.append(doc_id)
    
    # Save queue to disk
    queue_file = Path(settings.documents_dir) / "processing_queue.json"
    queue_data = {
        "created_at": datetime.now().isoformat(),
        "queue": queue,
        "pdf_parents": pdf_parents,
        "processed": [],
        "failed": []
    }
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f, indent=2)
    
    message = f"Queued {len(queue)} documents"
    if pdf_parents:
        message += f" (from {len(pdf_parents)} PDFs)"
    if errors:
        message += f". Errors: {len(errors)}"
    
    return {
        "success": len(queue) > 0,
        "queue": queue,
        "pdf_parents": pdf_parents,
        "total_documents": len(queue),
        "errors": errors,
        "message": message
    }


@tool
def get_next_from_queue() -> Dict[str, Any]:
    """
    Get the next document ID from the processing queue.
    
    Marks the document as 'processing' in the queue.
    
    Returns:
        Dictionary with:
        - has_next: Boolean indicating if there's a document
        - document_id: Next document ID or None
        - remaining: Number of documents remaining
        - message: Status message
    """
    queue_file = Path(settings.documents_dir) / "processing_queue.json"
    
    if not queue_file.exists():
        return {
            "has_next": False,
            "document_id": None,
            "remaining": 0,
            "message": "No queue file found"
        }
    
    with open(queue_file, 'r') as f:
        data = json.load(f)
    
    queue = data.get("queue", [])
    
    if not queue:
        return {
            "has_next": False,
            "document_id": None,
            "remaining": 0,
            "message": "Queue is empty"
        }
    
    # Get next document
    doc_id = queue.pop(0)
    
    # Update metadata to show processing
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{doc_id}.metadata.json"
    
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        metadata["queue"]["status"] = "processing"
        metadata["queue"]["started_at"] = datetime.now().isoformat()
        metadata["processing_status"] = "processing"
        metadata["updated_at"] = datetime.now().isoformat()
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    # Save updated queue
    data["queue"] = queue
    with open(queue_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return {
        "has_next": True,
        "document_id": doc_id,
        "remaining": len(queue),
        "message": f"Processing document: {doc_id}"
    }


@tool
def get_queue_status() -> Dict[str, Any]:
    """
    Get current status of the processing queue.
    
    Returns:
        Dictionary with queue statistics and document lists.
    """
    queue_file = Path(settings.documents_dir) / "processing_queue.json"
    
    if not queue_file.exists():
        return {
            "exists": False,
            "pending": 0,
            "processed": 0,
            "failed": 0,
            "message": "No queue file found"
        }
    
    with open(queue_file, 'r') as f:
        data = json.load(f)
    
    return {
        "exists": True,
        "pending": len(data.get("queue", [])),
        "processed": len(data.get("processed", [])),
        "failed": len(data.get("failed", [])),
        "queue": data.get("queue", []),
        "pdf_parents": data.get("pdf_parents", []),
        "message": f"Queue: {len(data.get('queue', []))} pending, {len(data.get('processed', []))} processed"
    }


@tool
def mark_document_processed(document_id: str, success: bool = True, error: Optional[str] = None) -> Dict[str, Any]:
    """
    Mark a document as processed in the queue.
    
    Updates both the queue file and the document's metadata.
    
    Args:
        document_id: Document ID to mark
        success: Whether processing succeeded
        error: Error message if failed
        
    Returns:
        Dictionary with update status
    """
    queue_file = Path(settings.documents_dir) / "processing_queue.json"
    intake_dir = Path(settings.documents_dir) / "intake"
    
    # Update queue file
    if queue_file.exists():
        with open(queue_file, 'r') as f:
            data = json.load(f)
        
        if success:
            if "processed" not in data:
                data["processed"] = []
            data["processed"].append(document_id)
        else:
            if "failed" not in data:
                data["failed"] = []
            data["failed"].append({"document_id": document_id, "error": error})
        
        with open(queue_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    # Update metadata
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        metadata["queue"]["status"] = "completed" if success else "failed"
        metadata["queue"]["completed_at"] = datetime.now().isoformat()
        if error:
            metadata["queue"]["error"] = error
        metadata["processing_status"] = "completed" if success else "failed"
        metadata["updated_at"] = datetime.now().isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    return {
        "success": True,
        "document_id": document_id,
        "status": "completed" if success else "failed",
        "message": f"Document {document_id} marked as {'completed' if success else 'failed'}"
    }
