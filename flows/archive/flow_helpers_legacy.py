"""Helper functions for document processing flows."""

from pathlib import Path
from typing import Dict, Any
import json
from utilities import settings, logger
from flows.document_processing_flow import DocumentProcessingFlow


def process_document(document_id: str, llm=None, processing_mode: str = 'process') -> Dict[str, Any]:
    """
    Process a single document by document ID using smart resume.
    
    Loads existing metadata and resumes from the last successful stage.
    Use processing_mode='reprocess' to force rerun all stages.
    
    Args:
        document_id: Document ID to process (e.g., DOC_20260127_143022_A3F8B)
        llm: Language model instance
        processing_mode: 'process' (smart resume) or 'reprocess' (rerun all)
        
    Returns:
        Processing results
        
    Example:
        # Smart resume - skip successful stages
        process_document("DOC_20260127_143022_A3F8B", llm, processing_mode='process')
        
        # Force reprocess all stages
        process_document("DOC_20260127_143022_A3F8B", llm, processing_mode='reprocess')
    """
    # Find document metadata
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "error": f"Document {document_id} not found in intake directory"
        }
    
    # Load existing metadata to populate stage_metadata
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Get stored path
    stored_path = metadata.get('stored_path')
    if not stored_path:
        return {
            "success": False,
            "error": f"Document {document_id} has no stored_path"
        }
    
    # Initialize flow
    flow = DocumentProcessingFlow(llm=llm)
    flow.state.file_paths = [stored_path]
    flow.state.processing_mode = processing_mode
    
    # Load existing stage status into state
    for stage_name in ['intake', 'classification', 'extraction']:
        if stage_name in metadata:
            flow.state.stage_metadata[stage_name] = metadata[stage_name]
    
    logger.critical(
        "\n" + "="*80 + "\n" +
        f"📋 DOCUMENT PROCESSING: {document_id}\n" +
        "="*80 + "\n" +
        f"Mode: {processing_mode.upper()}\n" +
        f"File: {Path(stored_path).name}\n" +
        f"Current Stage Status:\n" +
        f"  • Intake: {flow.state.stage_metadata['intake'].get('status', 'pending')}\n" +
        f"  • Classification: {flow.state.stage_metadata['classification'].get('status', 'pending')}\n" +
        f"  • Extraction: {flow.state.stage_metadata['extraction'].get('status', 'pending')}\n" +
        f"Behavior: {'Skip successful stages (smart resume)' if processing_mode == 'process' else 'Rerun all stages (full reprocess)'}\n" +
        "="*80
    )
    
    # Execute flow
    flow.kickoff()
    
    results = flow.get_results()
    
    # Log completion
    logger.critical(
        "\n" + "="*80 + "\n" +
        f"✅ PROCESSING COMPLETE: {document_id}\n" +
        "="*80 + "\n" +
        f"Final Stage Status:\n" +
        f"  • Intake: {results['stage_metadata']['intake'].get('status')}\n" +
        f"  • Classification: {results['stage_metadata']['classification'].get('status')}\n" +
        f"  • Extraction: {results['stage_metadata']['extraction'].get('status')}\n" +
        f"Overall Status: {results['status']}\n" +
        "="*80
    )
    
    return results


def reprocess_document(document_id: str, llm=None) -> Dict[str, Any]:
    """
    Reprocess a document from scratch, rerunning all stages.
    
    Convenience wrapper for process_document with processing_mode='reprocess'.
    
    Args:
        document_id: Document ID to reprocess
        llm: Language model instance
        
    Returns:
        Processing results
        
    Example:
        reprocess_document("DOC_20260127_143022_A3F8B", llm)
    """
    return process_document(document_id, llm, processing_mode='reprocess')
