"""
Document Processing Flow - Wrapper for Pipeline Flow.

This module provides backward compatibility by wrapping the new pipeline_flow.
For new development, use pipeline_flow.py directly.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from utilities import logger


def kickoff_flow(
    file_paths: List[str] = None,
    case_id: Optional[str] = None,
    llm = None,
    processing_mode: str = "process",
    **kwargs
) -> Dict[str, Any]:
    """
    Kickoff document processing flow.
    
    This is a compatibility wrapper that delegates to the new pipeline_flow.
    
    Args:
        file_paths: List of file paths to process
        case_id: Optional case ID to associate documents with
        llm: Language model instance (optional, not used in new pipeline)
        processing_mode: Processing mode (default: "process")
        **kwargs: Additional arguments
        
    Returns:
        Processing results dictionary
    """
    from pipeline_flow import run_pipeline_sync
    
    try:
        if not file_paths:
            return {
                "success": False,
                "error": "No file paths provided",
                "status": "failed"
            }
        
        # Use first path (can be file or folder)
        input_path = file_paths[0]
        
        # Run the new pipeline
        result = run_pipeline_sync(input_path)
        
        # Transform result for backward compatibility
        if result.get('success'):
            return {
                "success": True,
                "status": "success",
                "summary": result.get('summary', {}),
                "processed_documents": result.get('processed_documents', []),
                "stage_metadata": {
                    "intake": {"status": "success"},
                    "classification": {"status": "success"},
                    "extraction": {"status": "success"}
                }
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "error": result.get('error', 'Unknown error')
            }
            
    except Exception as e:
        logger.error(f"Flow error: {e}")
        return {
            "success": False,
            "status": "failed",
            "error": str(e)
        }


# Compatibility aliases
def add_directory_to_queue(directory_path: str, priority: int = 1) -> Dict[str, Any]:
    """Add directory to queue - compatibility wrapper."""
    from tools.queue_tools import build_processing_queue, get_queue_status
    
    result = build_processing_queue(directory_path)
    
    if result.get('success'):
        return {
            "status": "success",
            "message": f"Added {result.get('queued_count', 0)} documents to queue",
            "queue_status": get_queue_status()
        }
    else:
        return {
            "status": "failed",
            "message": result.get('error', 'Failed to add directory to queue')
        }


def add_files_to_queue(file_paths: List[str], priority: int = 1) -> Dict[str, Any]:
    """Add files to queue - compatibility wrapper."""
    from tools.queue_tools import build_processing_queue, get_queue_status
    
    total_queued = 0
    for file_path in file_paths:
        result = build_processing_queue(file_path)
        if result.get('success'):
            total_queued += result.get('queued_count', 0)
    
    return {
        "status": "success" if total_queued > 0 else "failed",
        "message": f"Added {total_queued} documents to queue",
        "queue_status": get_queue_status()
    }


def get_queue_status() -> Dict[str, Any]:
    """Get queue status - compatibility wrapper."""
    from tools.queue_tools import get_queue_status as new_get_queue_status
    
    status = new_get_queue_status()
    
    return {
        "status": status,
        "pending": [],  # Legacy format
        "failed": []
    }


def process_next_document_from_queue(
    processing_mode: str = "process",
    case_id: Optional[str] = None,
    llm = None,
    auto_drain: bool = False
) -> Dict[str, Any]:
    """Process next document from queue - compatibility wrapper."""
    from tools.queue_tools import get_next_from_queue, mark_document_processed
    from tools.classification_api_tools import classify_document
    from tools.extraction_api_tools import extract_document_data
    
    try:
        next_doc = get_next_from_queue()
        
        if not next_doc.get('success') or not next_doc.get('document'):
            return {"status": "complete", "message": "Queue is empty"}
        
        doc = next_doc['document']
        doc_id = doc.get('document_id')
        file_path = doc.get('stored_path')
        
        # Classification
        class_result = classify_document(file_path)
        
        if class_result.get('success'):
            doc_type = class_result.get('document_type')
            
            # Extraction
            extract_result = extract_document_data(file_path, doc_type)
            
            if extract_result.get('success'):
                mark_document_processed(doc_id, 'completed')
                return {
                    "status": "success",
                    "document_id": doc_id,
                    "stage_results": {
                        "classification": {"status": "success", "document_type": doc_type},
                        "extraction": {"status": "success"}
                    },
                    "queue_status": {"pending": 0, "failed": 0}
                }
            else:
                mark_document_processed(doc_id, 'failed', extract_result.get('error'))
                return {
                    "status": "failed",
                    "queue_id": doc_id,
                    "error": extract_result.get('error')
                }
        else:
            mark_document_processed(doc_id, 'failed', class_result.get('error'))
            return {
                "status": "failed",
                "queue_id": doc_id,
                "error": class_result.get('error')
            }
            
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
