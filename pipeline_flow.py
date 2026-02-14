"""
Document Processing Pipeline - CrewAI Flow Orchestration

This module implements the CrewAI Flow pattern for step-by-step
document processing. Each document goes through:

1. Queue Building (once at start)
2. Classification (per document)
3. Extraction (per document)
4. Error Handling (on failures)
5. Summary (once at end)

The Flow ensures proper ordering and state management.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
import json

# CrewAI Flow imports
try:
    from crewai.flow.flow import Flow, listen, start
    FLOW_AVAILABLE = True
except ImportError:
    FLOW_AVAILABLE = False
    Flow = object
    def start():
        def decorator(func):
            return func
        return decorator
    def listen(*args):
        def decorator(func):
            return func
        return decorator

# Import tools directly (deterministic operations)
from tools.queue_tools import (
    scan_input_path,
    expand_folder,
    build_processing_queue,
    get_next_from_queue,
    get_queue_status,
    mark_document_processed
)

from tools.classification_api_tools import classify_document
from tools.extraction_api_tools import extract_document_data
from tools.metadata_tools import (
    update_processing_status,
    record_error,
    check_retry_eligible,
    reset_stage_for_retry,
    flag_for_review,
    get_document_metadata
)
from tools.summary_tools import (
    generate_processing_summary,
    generate_report_text,
    export_results_json
)

from utilities import logger, settings


# ==================== STATE MODEL ====================

class PipelineState(BaseModel):
    """State management for the document processing pipeline."""
    
    # Input
    input_path: str = Field(default="", description="Input file or folder path")
    
    # Queue state
    queue_built: bool = Field(default=False)
    total_documents: int = Field(default=0)
    pdf_parents: List[str] = Field(default_factory=list)
    
    # Current processing
    current_document_id: Optional[str] = Field(default=None)
    current_stage: str = Field(default="initialized")
    
    # Results tracking
    processed_count: int = Field(default=0)
    success_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    retry_count: int = Field(default=0)
    
    # Document results
    classification_results: Dict[str, Any] = Field(default_factory=dict)
    extraction_results: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Final summary
    summary: Optional[Dict[str, Any]] = None


# ==================== FLOW DEFINITION ====================

class DocumentProcessingPipeline(Flow[PipelineState] if FLOW_AVAILABLE else object):
    """
    CrewAI Flow for step-by-step document processing.
    
    This flow orchestrates the complete pipeline:
    1. Build queue from input path
    2. Process each document through classification and extraction
    3. Handle errors with retry logic
    4. Generate final summary
    """
    
    def __init__(self, *args, **kwargs):
        if FLOW_AVAILABLE:
            super().__init__(*args, **kwargs)
        self.max_retries = 3
    
    # ==================== STAGE 1: BUILD QUEUE ====================
    
    @start()
    def build_queue(self):
        """
        Stage 1: Build the processing queue from input path.
        
        Scans the input path, expands folders, splits PDFs,
        and creates the processing queue with metadata.
        """
        self.state.start_time = datetime.now()
        self.state.current_stage = "building_queue"
        
        input_path = self.state.input_path
        logger.info(f"Building queue from: {input_path}")
        
        # Scan input path
        scan_result = scan_input_path.run(input_path=input_path)
        
        if scan_result["path_type"] == "invalid":
            logger.error(f"Invalid input path: {scan_result['message']}")
            self.state.errors.append({
                "stage": "queue",
                "error": scan_result["message"]
            })
            return
        
        # Get file list
        if scan_result["path_type"] == "folder":
            expand_result = expand_folder.run(folder_path=input_path)
            file_paths = expand_result["files"]
        else:
            file_paths = [scan_result["path"]]
        
        logger.info(f"Found {len(file_paths)} files to process")
        
        # Build queue (splits PDFs, creates metadata)
        queue_result = build_processing_queue.run(file_paths=file_paths)
        
        if queue_result["success"]:
            self.state.queue_built = True
            self.state.total_documents = queue_result["total_documents"]
            self.state.pdf_parents = queue_result["pdf_parents"]
            logger.info(f"Queue built: {queue_result['message']}")
        else:
            logger.error(f"Failed to build queue: {queue_result.get('errors', [])}")
            self.state.errors.extend([
                {"stage": "queue", "error": e} for e in queue_result.get("errors", [])
            ])
    
    # ==================== STAGE 2: PROCESS LOOP ====================
    
    @listen(build_queue)
    def process_documents(self):
        """
        Stage 2: Process each document through classification and extraction.
        
        Loops through the queue, processing one document at a time.
        """
        if not self.state.queue_built:
            logger.warning("Queue not built, skipping document processing")
            return
        
        self.state.current_stage = "processing"
        
        while True:
            # Get next document
            next_result = get_next_from_queue.run()
            
            if not next_result["has_next"]:
                logger.info("Queue processing complete")
                break
            
            document_id = next_result["document_id"]
            self.state.current_document_id = document_id
            remaining = next_result["remaining"]
            
            logger.info(f"Processing: {document_id} ({remaining} remaining)")
            
            # Process this document
            success = self._process_single_document(document_id)
            
            self.state.processed_count += 1
            if success:
                self.state.success_count += 1
            else:
                self.state.failed_count += 1
            
            # Mark as processed in queue
            mark_document_processed.run(
                document_id=document_id,
                success=success
            )
    
    def _process_single_document(self, document_id: str) -> bool:
        """
        Process a single document through classification and extraction.
        
        Returns True if successful, False if failed.
        """
        # ---- CLASSIFICATION ----
        logger.info(f"Classifying: {document_id}")
        
        class_result = classify_document.run(document_id=document_id)
        
        if not class_result["success"]:
            # Handle classification error
            error_handled = self._handle_error(
                document_id, 
                "classification", 
                class_result["error"]
            )
            if not error_handled:
                return False
            
            # Retry classification
            class_result = classify_document.run(document_id=document_id)
            if not class_result["success"]:
                return False
        
        # Store classification result
        self.state.classification_results[document_id] = {
            "document_type": class_result["document_type"],
            "confidence": class_result["confidence"]
        }
        
        logger.info(f"Classified as: {class_result['document_type']} "
                   f"(confidence: {class_result['confidence']})")
        
        # ---- EXTRACTION ----
        logger.info(f"Extracting: {document_id}")
        
        extract_result = extract_document_data.run(
            document_id=document_id,
            document_type=class_result["document_type"]
        )
        
        if not extract_result["success"]:
            # Handle extraction error
            error_handled = self._handle_error(
                document_id,
                "extraction",
                extract_result["error"]
            )
            if not error_handled:
                return False
            
            # Retry extraction
            extract_result = extract_document_data.run(
                document_id=document_id,
                document_type=class_result["document_type"]
            )
            if not extract_result["success"]:
                return False
        
        # Store extraction result
        self.state.extraction_results[document_id] = {
            "fields": list(extract_result["extracted_fields"].keys()),
            "field_count": len(extract_result["extracted_fields"])
        }
        
        logger.info(f"Extracted {len(extract_result['extracted_fields'])} fields")
        
        return True
    
    def _handle_error(self, document_id: str, stage: str, error: str) -> bool:
        """
        Handle processing error with retry logic.
        
        Returns True if document should be retried, False if permanently failed.
        """
        self.state.errors.append({
            "document_id": document_id,
            "stage": stage,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        
        # Record error
        record_error.run(
            document_id=document_id,
            stage=stage,
            error_message=error
        )
        
        # Check retry eligibility
        retry_check = check_retry_eligible.run(
            document_id=document_id,
            stage=stage,
            max_retries=self.max_retries
        )
        
        if retry_check["eligible"]:
            logger.info(f"Retrying {stage} for {document_id} "
                       f"(attempt {retry_check['current_retries'] + 1})")
            self.state.retry_count += 1
            
            # Reset stage for retry
            reset_stage_for_retry.run(
                document_id=document_id,
                stage=stage
            )
            return True
        else:
            # Flag for review
            logger.warning(f"Max retries exceeded for {document_id}, flagging for review")
            flag_for_review.run(
                document_id=document_id,
                reason=f"Max retries exceeded at {stage}: {error}"
            )
            return False
    
    # ==================== STAGE 3: GENERATE SUMMARY ====================
    
    @listen(process_documents)
    def generate_summary(self):
        """
        Stage 3: Generate final processing summary.
        
        Aggregates all results and creates a comprehensive report.
        """
        self.state.current_stage = "generating_summary"
        self.state.end_time = datetime.now()
        
        logger.info("Generating processing summary...")
        
        # Generate summary
        summary_result = generate_processing_summary.run()
        
        # Generate text report
        report_text = generate_report_text.run()
        
        # Export results
        export_result = export_results_json.run()
        
        # Store summary
        self.state.summary = {
            "statistics": summary_result,
            "report": report_text,
            "export_path": export_result.get("output_path"),
            "pipeline_stats": {
                "total_documents": self.state.total_documents,
                "processed": self.state.processed_count,
                "succeeded": self.state.success_count,
                "failed": self.state.failed_count,
                "retries": self.state.retry_count,
                "pdf_parents": len(self.state.pdf_parents),
                "duration_seconds": (
                    (self.state.end_time - self.state.start_time).total_seconds()
                    if self.state.start_time and self.state.end_time else 0
                )
            }
        }
        
        self.state.current_stage = "completed"
        logger.info("Pipeline complete!")
        
        # Print report
        print(report_text)


# ==================== RUNNER FUNCTIONS ====================

def run_pipeline(input_path: str) -> Dict[str, Any]:
    """
    Run the complete document processing pipeline.
    
    Args:
        input_path: File or folder path to process
        
    Returns:
        Pipeline results including summary
    """
    if not FLOW_AVAILABLE:
        logger.error("CrewAI Flow not available")
        return {"error": "CrewAI Flow not available"}
    
    # Create and run pipeline
    pipeline = DocumentProcessingPipeline()
    pipeline.state.input_path = input_path
    
    # Kick off the flow
    result = pipeline.kickoff()
    
    return {
        "success": pipeline.state.failed_count == 0,
        "summary": pipeline.state.summary,
        "processed": pipeline.state.processed_count,
        "succeeded": pipeline.state.success_count,
        "failed": pipeline.state.failed_count,
        "errors": pipeline.state.errors
    }


def run_pipeline_sync(input_path: str, case_reference: str = None) -> Dict[str, Any]:
    """
    Run the pipeline synchronously without Flow (fallback).
    
    Args:
        input_path: File or folder path to process
        case_reference: Optional case to link documents to
        
    Returns:
        Pipeline results with success status, summary, and processed documents
    """
    logger.info(f"Running pipeline for: {input_path}" + (f" (case: {case_reference})" if case_reference else ""))
    
    results = {
        "success": False,
        "input_path": input_path,
        "documents": [],
        "processed_documents": [],
        "errors": [],
        "summary": {
            "statistics": {
                "total_documents": 0,
                "completed": 0,
                "failed": 0
            },
            "by_document_type": {}
        }
    }
    
    # 1. Scan input
    scan_result = scan_input_path.run(input_path=input_path)
    if scan_result["path_type"] == "invalid":
        results["errors"].append(scan_result["message"])
        results["error"] = scan_result["message"]
        return results
    
    # 2. Expand folder if needed
    if scan_result["path_type"] == "folder":
        expand_result = expand_folder.run(folder_path=input_path)
        file_paths = expand_result["files"]
    else:
        file_paths = [scan_result["path"]]
    
    # 3. Build queue
    queue_result = build_processing_queue.run(file_paths=file_paths)
    
    if not queue_result["success"]:
        results["errors"].extend(queue_result.get("errors", []))
        results["error"] = "Failed to build processing queue"
        return results
    
    # Track document types
    doc_type_counts = {}
    completed_count = 0
    failed_count = 0
    all_document_ids = []  # Track ALL documents, not just successful ones
    
    # 4. Process each document
    while True:
        next_result = get_next_from_queue.run()
        
        if not next_result["has_next"]:
            break
        
        document_id = next_result["document_id"]
        all_document_ids.append(document_id)  # Track every document
        doc_result = {"document_id": document_id}
        
        # Classify
        class_result = classify_document.run(document_id=document_id)
        doc_result["classification"] = class_result
        
        if class_result["success"]:
            doc_type = class_result.get("document_type", "unknown")
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1
            
            # Extract
            extract_result = extract_document_data.run(
                document_id=document_id,
                document_type=doc_type
            )
            doc_result["extraction"] = extract_result
            
            if extract_result.get("success"):
                completed_count += 1
                results["processed_documents"].append(document_id)
            else:
                failed_count += 1
        else:
            failed_count += 1
        
        results["documents"].append(doc_result)
        
        # Mark processed
        mark_document_processed.run(
            document_id=document_id,
            success=class_result["success"]
        )
    
    # 5. Generate summary
    summary_result = generate_processing_summary.run()
    
    total_docs = completed_count + failed_count
    results["success"] = failed_count == 0 and completed_count > 0
    results["summary"] = {
        "statistics": {
            "total_documents": total_docs,
            "completed": completed_count,
            "failed": failed_count
        },
        "by_document_type": doc_type_counts,
        "detailed_summary": summary_result
    }
    
    # Link ALL documents to case if provided (regardless of processing status)
    if case_reference and all_document_ids:
        from tools.case_tools import link_document_to_case_tool
        
        # Ensure case exists (create if needed)
        case_dir = Path(settings.documents_dir) / "cases" / case_reference
        case_metadata_path = case_dir / "case_metadata.json"
        if not case_metadata_path.exists():
            case_dir.mkdir(parents=True, exist_ok=True)
            case_metadata = {
                "case_reference": case_reference,
                "created_date": datetime.now().isoformat(),
                "status": "active",
                "documents": []
            }
            with open(case_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(case_metadata, f, indent=2)
            logger.info(f"Auto-created case {case_reference} for document linking")
        
        results["case_reference"] = case_reference
        results["linked_documents"] = []
        for doc_id in all_document_ids:
            try:
                link_result = link_document_to_case_tool.run(document_id=doc_id, case_id=case_reference)
                if link_result.get("success"):
                    results["linked_documents"].append(doc_id)
                else:
                    logger.warning(f"Failed to link {doc_id} to {case_reference}: {link_result.get('error')}")
            except Exception as e:
                logger.warning(f"Failed to link {doc_id} to {case_reference}: {e}")
    
    # Include all document IDs in results (for reference)
    results["all_documents"] = all_document_ids
    
    if failed_count > 0:
        results["error"] = f"{failed_count} document(s) failed processing"
    
    logger.info(f"Pipeline complete: {completed_count}/{total_docs} succeeded")
    
    return results


# ==================== CLI INTERFACE ====================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pipeline_flow.py <input_path>")
        print("  input_path: File or folder path to process")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if FLOW_AVAILABLE:
        result = run_pipeline(input_path)
    else:
        print("Warning: CrewAI Flow not available, using sync mode")
        result = run_pipeline_sync(input_path)
    
    print(json.dumps(result, indent=2, default=str))
