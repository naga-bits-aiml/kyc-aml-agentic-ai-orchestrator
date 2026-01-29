"""Flow-based document processing orchestration for KYC-AML.

This module implements CrewAI's Flow pattern for event-driven workflow management
using pure CrewAI crews without hybrid/legacy dependencies.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from crewai.flow.flow import Flow, listen, start
    FLOW_AVAILABLE = True
except ImportError:
    # Fallback if Flow is not available in current CrewAI version
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

from crew import KYCAMLCrew, process_documents
from tools.intake_tools import get_document_by_id_tool
from tools.stage_management_tools import update_document_metadata_tool
from utilities import logger, settings, config


class DocumentProcessingState(BaseModel):
    """
    State management for document processing flow.
    Uses Pydantic for type-safe state transitions.
    """
    # Input parameters
    case_id: Optional[str] = Field(default=None, description="Optional case identifier for linking documents")
    file_paths: List[str] = Field(default_factory=list, description="List of document file paths")
    processing_mode: str = Field(default="process", description="Processing mode: 'process' (skip successful stages) or 'reprocess' (rerun all stages)")
    
    # Processing state
    current_stage: str = Field(default="initialized", description="Current workflow stage")
    use_reasoning: bool = Field(default=True, description="Whether to use autonomous reasoning")
    require_queue_confirmation: bool = Field(
        default=False,
        description="Prompt before queueing intake results for classification"
    )
    auto_drain_queue: bool = Field(
        default=True,
        description="Whether to auto-drain queued documents before finalizing"
    )
    
    # Stage results (legacy - kept for backward compatibility)
    validated_documents: List[Dict[str, Any]] = Field(default_factory=list)
    classifications: List[Dict[str, Any]] = Field(default_factory=list)
    extractions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Stage metadata - captures success/failure for each stage
    stage_metadata: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            'intake': {'status': 'pending', 'msg': '', 'error': None, 'trace': None, 'data': None},
            'classification': {'status': 'pending', 'msg': '', 'error': None, 'trace': None, 'data': None},
            'extraction': {'status': 'pending', 'msg': '', 'error': None, 'trace': None, 'data': None}
        },
        description="Metadata for each processing stage"
    )
    
    # Metadata
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)
    
    # Summary metrics
    total_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0
    requires_review: int = 0
    
    # Documents processed in this run (including auto-drained queue)
    processed_document_ids: List[str] = Field(default_factory=list, description="Processed document IDs")


class DocumentProcessingFlow(Flow[DocumentProcessingState] if FLOW_AVAILABLE else object):
    """
    Event-driven document processing flow.
    
    This flow orchestrates the complete KYC-AML document processing pipeline:
    1. Document intake and validation
    2. Document classification
    3. Data extraction
    4. Quality validation and reporting
    
    Each stage triggers the next upon completion, with proper error handling
    and state management throughout.
    """
    
    def __init__(self, llm, *args, **kwargs):
        """
        Initialize the flow with LLM.
        
        Args:
            llm: Language model instance for crew
        """
        if FLOW_AVAILABLE:
            super().__init__(*args, **kwargs)
        self.llm = llm
        self.crew = KYCAMLCrew(llm=llm)

    def _parse_crew_output(self, output: Any) -> Dict[str, Any]:
        """Parse CrewOutput into a dictionary, tolerating non-JSON output."""
        if hasattr(output, 'raw') and output.raw:
            raw_str = str(output.raw).strip()
            if raw_str:
                try:
                    return json.loads(raw_str)
                except json.JSONDecodeError:
                    import re
                    json_match = re.search(r'\{.*\}', raw_str, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            return {"error": "Could not parse output", "raw": raw_str[:500]}
                    return {"error": "No JSON found in output", "raw": raw_str[:500]}
        if hasattr(output, 'json'):
            return output.json
        if isinstance(output, dict):
            return output
        return {"error": "Invalid output format", "output": str(output)[:500]}

    # Legacy queue methods removed - now using unified DocumentQueue in utilities/queue_manager.py

    def _run_tool(self, tool_obj, **kwargs) -> Dict[str, Any]:
        """Run a CrewAI tool regardless of decorator wrapping."""
        if hasattr(tool_obj, "run"):
            return tool_obj.run(**kwargs)
        if callable(tool_obj):
            return tool_obj(**kwargs)
        return {"error": "Tool is not callable", "tool": str(tool_obj)}

    def _ensure_intake_queue(self, validated_documents: List[Dict[str, Any]], prompt: bool) -> Dict[str, Any]:
        """
        Ensure intake results (including PDF child docs) are queued for classification.
        """
        from tools.pdf_conversion_tools import convert_pdf_to_images_tool
        from tools.intake_tools import queue_documents_for_classification_tool

        child_documents = []
        pdf_conversions = []

        for doc in validated_documents:
            metadata = doc.get("metadata") or {}
            document_id = doc.get("document_id")
            extension = (metadata.get("extension") or "").lower()
            if extension != ".pdf" or not document_id:
                continue

            metadata = self._refresh_document_metadata(document_id) or metadata
            existing_children = metadata.get("child_documents", [])
            if existing_children:
                for child_id in existing_children:
                    child_documents.append({"child_id": child_id, "parent_id": document_id})
                continue

            conversion_result = self._run_tool(
                convert_pdf_to_images_tool,
                document_id=document_id
            )
            if conversion_result.get("success"):
                pdf_conversions.append({
                    "document_id": conversion_result.get("source_document_id"),
                    "child_documents": conversion_result.get("child_documents", []),
                    "total_pages": conversion_result.get("total_pages")
                })
                for child_id in conversion_result.get("child_documents", []):
                    child_documents.append({"child_id": child_id, "parent_id": document_id})

        queue_result = self._run_tool(
            queue_documents_for_classification_tool,
            document_paths=[doc.get("stored_path") for doc in validated_documents if doc.get("stored_path")],
            child_documents=child_documents,
            require_confirmation=prompt
        )

        return {
            "queue_result": queue_result,
            "pdf_conversions": pdf_conversions
        }

    def _run_intake_fallback(self, previous_status: str) -> Optional[Dict[str, Any]]:
        """
        Run intake steps without LLM when the agent returns an empty response.
        """
        try:
            from tools.skip_check_tool import check_if_stage_should_skip_tool
            from tools.intake_tools import (
                resolve_document_paths_tool,
                batch_validate_documents_tool,
                queue_documents_for_classification_tool,
                link_document_to_case_tool
            )
            from tools.pdf_conversion_tools import convert_pdf_to_images_tool
        except Exception as e:
            logger.error(f"Failed to load intake tools for fallback: {e}")
            return None

        skip_check = self._run_tool(
            check_if_stage_should_skip_tool,
            processing_mode=self.state.processing_mode,
            stage_status=previous_status,
            stage_name="intake"
        )

        if skip_check.get("should_skip"):
            return {
                "skipped": True,
                "message": skip_check.get("reason", "Intake skipped"),
                "skip_check_result": skip_check
            }

        resolved_paths = self._run_tool(
            resolve_document_paths_tool,
            paths=self.state.file_paths,
            recursive=False
        )

        resolved_files = resolved_paths.get("resolved_files", [])
        validation_result = self._run_tool(
            batch_validate_documents_tool,
            file_paths=resolved_files
        )

        validated_documents = validation_result.get("validated_documents", [])
        failed_documents = validation_result.get("failed_documents", [])

        queue_info = self._ensure_intake_queue(
            validated_documents,
            prompt=self.state.require_queue_confirmation
        )
        queue_result = queue_info.get("queue_result", {})
        pdf_conversions = queue_info.get("pdf_conversions", [])

        if self.state.case_id:
            for doc in validated_documents:
                doc_id = doc.get("document_id")
                if not doc_id:
                    continue
                self._run_tool(
                    link_document_to_case_tool,
                    document_id=doc_id,
                    case_id=self.state.case_id
                )

        return {
            "skip_check_result": skip_check,
            "resolved_paths": resolved_paths,
            "validated_documents": validated_documents,
            "failed_documents": failed_documents,
            "pdf_conversions": pdf_conversions,
            "queue_summary": queue_result.get("summary", {}),
            "summary": {
                "total": validation_result.get("total", len(resolved_files)),
                "valid": validation_result.get("valid", len(validated_documents)),
                "invalid": validation_result.get("invalid", len(failed_documents))
            }
        }

    def _auto_drain_queue(self, max_docs: int) -> List[str]:
        """
        Drain pending queue entries up to max_docs and return processed document IDs.
        """
        from utilities.queue_manager import DocumentQueue
        from flows.document_processing_flow import process_next_document_from_queue

        processed_ids: List[str] = []
        queue = DocumentQueue()

        while len(processed_ids) < max_docs:
            status = queue.get_status()
            if status.get("pending", 0) == 0:
                break

            result = process_next_document_from_queue(
                processing_mode=self.state.processing_mode,
                case_id=self.state.case_id,
                llm=self.llm,
                auto_drain=False
            )

            if result.get("status") == "success":
                doc_id = result.get("document_id")
                if doc_id:
                    processed_ids.append(doc_id)
            elif result.get("status") in {"failed", "skipped"}:
                continue
            else:
                break

        return processed_ids

    def _run_flow_kickoff(self) -> None:
        """
        Run flow.kickoff safely, even if an event loop is already running.
        """
        try:
            asyncio.get_running_loop()
            loop_running = True
        except RuntimeError:
            loop_running = False

        if loop_running:
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self.kickoff).result()
        else:
            self.kickoff()

    def _refresh_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Refresh document metadata from disk.
        Use this after crew execution to get latest updates.
        
        Args:
            document_id: Document ID to refresh
            
        Returns:
            Fresh metadata dict or None if failed
        """
        result = self._run_tool(get_document_by_id_tool, document_id=document_id)
        if result.get('success'):
            return result['metadata']
        logger.error(f"Failed to refresh metadata for {document_id}")
        return None

    def _update_validated_document_metadata(self, index: int, document_id: str) -> bool:
        """
        Update metadata for a validated document in state.
        
        Args:
            index: Index in validated_documents list
            document_id: Document ID to refresh
            
        Returns:
            True if successful
        """
        fresh_metadata = self._refresh_document_metadata(document_id)
        if fresh_metadata:
            self.state.validated_documents[index]['metadata'] = fresh_metadata
            return True
        return False

    def _hydrate_validated_documents_with_metadata(self) -> None:
        """Ensure each validated document includes its current metadata."""
        for doc in self.state.validated_documents:
            if doc.get("metadata"):
                continue
            document_id = doc.get("document_id")
            if not document_id:
                continue
            result = self._run_tool(get_document_by_id_tool, document_id=document_id)
            if result.get("metadata"):
                doc["metadata"] = result["metadata"]

    def _load_validated_documents_from_intake(self) -> None:
        """Load validated_documents from intake metadata based on file_paths."""
        if self.state.validated_documents:
            return
        intake_dir = Path(settings.documents_dir) / "intake"

        for file_path in self.state.file_paths:
            path = Path(file_path).resolve()
            metadata = None
            document_id = None

            if path.parent.resolve() == intake_dir.resolve() and path.stem.startswith("DOC_"):
                document_id = path.stem
                metadata_path = intake_dir / f"{document_id}.metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
            else:
                for metadata_file in intake_dir.glob("*.metadata.json"):
                    try:
                        with open(metadata_file, 'r') as f:
                            candidate = json.load(f)
                        stored_path = Path(candidate.get("stored_path", "")).resolve()
                        if stored_path == path:
                            metadata = candidate
                            document_id = candidate.get("document_id")
                            break
                    except Exception as e:
                        logger.debug(f"Error reading metadata file {metadata_file}: {e}")

            if metadata and document_id:
                self.state.validated_documents.append({
                    "document_id": document_id,
                    "original_filename": metadata.get("original_filename"),
                    "stored_path": metadata.get("stored_path"),
                    "file_size": metadata.get("size_bytes"),
                    "mime_type": f"application/{metadata.get('extension', '').lstrip('.')}",
                    "validation_status": metadata.get("intake", {}).get("validation_status", "valid"),
                    "stage": "intake",
                    "metadata": metadata
                })

    def _convert_pdfs_and_queue_children(self) -> None:
        """
        Convert any PDF documents to images during intake and queue the children.
        This runs after intake validation to prepare PDFs for classification.
        """
        from tools.pdf_conversion_tools import convert_pdf_to_images_tool
        from utilities.queue_manager import DocumentQueue
        
        intake_dir = Path(settings.documents_dir) / "intake"
        
        # Find all PDF metadata files in intake
        for metadata_file in intake_dir.glob("*.metadata.json"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Skip if not a PDF or already has children
                if metadata.get('extension', '').lower() != '.pdf':
                    continue
                    
                if metadata.get('child_documents'):
                    continue  # Already converted
                
                document_id = metadata.get('document_id')
                if not document_id:
                    continue
                
                logger.info(f"Converting PDF {document_id} to images during intake")
                
                # Convert PDF to images
                result = convert_pdf_to_images_tool(document_id)
                
                if result.get('success'):
                    child_ids = result.get('child_documents', [])
                    if child_ids:
                        # Queue children immediately
                        queue = DocumentQueue()
                        queue_ids = queue.add_child_documents(child_ids, parent_id=document_id, priority=2)
                        logger.info(f"Queued {len(queue_ids)} child documents for PDF {document_id}")
                else:
                    logger.warning(f"Failed to convert PDF {document_id}: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"Error processing PDF {metadata_file}: {e}")
    
    def _enqueue_child_documents(self, child_ids: List[str], parent_id: Optional[str] = None) -> None:
        """
        Queue child documents for processing using unified DocumentQueue.
        
        Args:
            child_ids: List of child document IDs to queue
            parent_id: Parent document ID
        """
        if not child_ids:
            return
        
        # Use unified queue manager
        from utilities.queue_manager import DocumentQueue
        queue = DocumentQueue()
        
        # Queue child documents with priority 2 (after initial files)
        queue_ids = queue.add_child_documents(child_ids, parent_id=parent_id or "UNKNOWN", priority=2)
        
        logger.info(f"Queued {len(queue_ids)} child documents for parent {parent_id}")
    
    @start()
    def intake_documents(self):
        """
        Stage 1: Document intake and validation.
        
        This is the entry point of the flow. It validates all incoming documents,
        generates globally unique IDs, and stores them in documents/intake/ directory.
        Documents can be linked to cases later if case_id is provided.
        
        Note: This stage always progresses to next stage regardless of success/failure.
        Results are captured in stage_metadata['intake'].
        """
        self.state.current_stage = "intake"
        self.state.start_time = datetime.now()
        
        # Get the ACTUAL previous status before changing it
        previous_status = self.state.stage_metadata['intake'].get('status', 'pending')
        
        try:
            # Execute intake using crew - agent decides whether to skip or execute
            intake_crew = self.crew.intake_crew()
            intake_inputs = {
                'file_paths': self.state.file_paths,
                'processing_mode': self.state.processing_mode,
                'stage_status': previous_status,  # Pass actual previous status
                'require_queue_confirmation': self.state.require_queue_confirmation
            }
            if self.state.case_id:
                intake_inputs['case_id'] = self.state.case_id
            
            logger.info(f"Executing intake crew with inputs: {intake_inputs}")
            intake_output = intake_crew.kickoff(inputs=intake_inputs)
            logger.info(f"Intake crew completed. Output type: {type(intake_output)}")
            
            # Extract result from CrewOutput with tolerant parsing
            if hasattr(intake_output, 'raw') and intake_output.raw:
                logger.info(f"Intake raw output: {str(intake_output.raw)[:500]}...")  # Log first 500 chars
            else:
                logger.info(f"Intake output (no raw attribute or empty raw): {str(intake_output)[:500]}...")
            intake_result = self._parse_crew_output(intake_output)

            if intake_result.get("error"):
                raise ValueError(f"Invalid response from intake LLM output: {intake_result.get('error')}")
            
            # Check if stage was skipped
            if intake_result.get('skipped'):
                logger.info(f"Intake stage skipped: {intake_result.get('message')}")
                # Keep existing status, don't update to success
                return self.state
            
            # Stage was executed, set to running then success
            self.state.stage_metadata['intake']['status'] = 'running'
            
            # Update state with results
            self.state.validated_documents = intake_result.get('validated_documents', [])
            self.state.total_documents = len(self.state.validated_documents)
            self._hydrate_validated_documents_with_metadata()

            # Ensure PDFs create child documents and all docs are queued
            prompt_for_queue = self.state.require_queue_confirmation and not intake_result.get("queue_summary")
            queue_info = self._ensure_intake_queue(self.state.validated_documents, prompt=prompt_for_queue)
            if queue_info.get("pdf_conversions") and not intake_result.get("pdf_conversions"):
                intake_result["pdf_conversions"] = queue_info["pdf_conversions"]
            if queue_info.get("queue_result") and not intake_result.get("queue_summary"):
                intake_result["queue_summary"] = queue_info["queue_result"].get("summary", {})
            
            # Capture success metadata
            self.state.stage_metadata['intake'] = {
                'status': 'success',
                'msg': f"Successfully validated {self.state.total_documents} documents",
                'error': None,
                'trace': None,
                'data': intake_result
            }
            logger.info(f"Intake complete: {self.state.total_documents} documents validated")
            
            # Convert PDFs to images and queue children
            self._convert_pdfs_and_queue_children()
                
        except Exception as e:
            import traceback
            error_msg = f"Intake exception: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full intake error traceback:")

            fallback_error_signals = [
                "Invalid response from LLM call - None or empty",
                "Invalid response from intake LLM output"
            ]
            if any(signal in str(e) for signal in fallback_error_signals):
                logger.warning("Attempting intake fallback without LLM response")
                fallback_result = self._run_intake_fallback(previous_status)
                if fallback_result:
                    if fallback_result.get("skipped"):
                        logger.info(f"Intake fallback skipped: {fallback_result.get('message')}")
                        return self.state

                    self.state.validated_documents = fallback_result.get('validated_documents', [])
                    self.state.total_documents = len(self.state.validated_documents)
                    self._hydrate_validated_documents_with_metadata()

                    self.state.stage_metadata['intake'] = {
                        'status': 'success',
                        'msg': f"Successfully validated {self.state.total_documents} documents (fallback)",
                        'error': None,
                        'trace': None,
                        'data': fallback_result
                    }
                    logger.info(f"Intake fallback complete: {self.state.total_documents} documents validated")
                    return self.state

            # Capture failure metadata
            self.state.stage_metadata['intake'] = {
                'status': 'fail',
                'msg': error_msg,
                'error': str(e),
                'trace': traceback.format_exc(),
                'data': None
            }
            self.state.errors.append(error_msg)
            
            # Continue to next stage anyway
    
    @listen(intake_documents)
    def classify_documents(self):
        """
        Stage 2: Document classification.
        
        Triggered after intake completes. Classifies each document
        into appropriate categories (identity_proof, address_proof, etc.).
        
        Note: Progresses to next stage regardless of success/failure.
        Results are captured in stage_metadata['classification'].
        """
        self.state.current_stage = "classification"
        
        # Get the ACTUAL previous status before changing it
        previous_status = self.state.stage_metadata['classification'].get('status', 'pending')
        
        try:
            self._load_validated_documents_from_intake()
            self._hydrate_validated_documents_with_metadata()

            if not self.state.validated_documents:
                logger.warning("No validated documents available for classification")
                return self.state

            classification_crew = self.crew.classification_crew()
            classified_documents = []
            failed_documents = []
            skipped_documents = 0

            for doc in self.state.validated_documents:
                document_id = doc.get('document_id')
                if not document_id:
                    continue

                document_metadata = doc.get('metadata', {})
                stage_status = document_metadata.get('classification', {}).get('status', 'pending')

                classification_output = classification_crew.kickoff(inputs={
                    'document_id': document_id,
                    'document_metadata': document_metadata,
                    'case_id': self.state.case_id,
                    'processing_mode': self.state.processing_mode,
                    'stage_status': stage_status or previous_status
                })

                classification_result = self._parse_crew_output(classification_output)

                if classification_result.get('skipped'):
                    skipped_documents += 1
                    continue

                classified_documents.extend(
                    classification_result.get('classified_documents')
                    or classification_result.get('classifications', [])
                )
                failed_documents.extend(classification_result.get('failed_documents', []))

                # Refresh metadata to get latest classification results
                refreshed = self._run_tool(get_document_by_id_tool, document_id=document_id)
                if refreshed.get("metadata"):
                    doc["metadata"] = refreshed["metadata"]
                    # Children already queued in intake stage - no need to queue here

            self.state.stage_metadata['classification']['status'] = 'running'

            self.state.classifications = classified_documents
            self.state.requires_review = sum(
                1 for c in self.state.classifications
                if c.get('requires_review', False)
            )

            success_count = len(classified_documents)
            failure_count = len(failed_documents)
            if success_count and failure_count:
                status = "partial"
            elif success_count:
                status = "success"
            elif failure_count:
                status = "fail"
            elif skipped_documents:
                status = "skipped"
            else:
                status = "pending"

            self.state.stage_metadata['classification'] = {
                'status': status,
                'msg': f"Classification: {success_count} success, {failure_count} failed, {skipped_documents} skipped",
                'error': None,
                'trace': None,
                'data': {
                    "classified_documents": classified_documents,
                    "failed_documents": failed_documents,
                    "skipped_documents": skipped_documents
                }
            }
            logger.info(f"Classification complete: {success_count} success, {failure_count} failed, {skipped_documents} skipped")
                
        except Exception as e:
            import traceback
            error_msg = f"Classification exception: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full classification error traceback:")
            
            # Capture failure metadata
            self.state.stage_metadata['classification'] = {
                'status': 'fail',
                'msg': error_msg,
                'error': str(e),
                'trace': traceback.format_exc(),
                'data': None
            }
            self.state.errors.append(error_msg)
            
            # Continue to next stage anyway
    
    @listen(classify_documents)
    def extract_data(self):
        """
        Stage 3: Data extraction.
        
        Triggered after classification completes. Extracts structured data
        from each classified document using appropriate tools.
        
        Note: Progresses to next stage regardless of success/failure.
        Results are captured in stage_metadata['extraction'].
        """
        self.state.current_stage = "extraction"
        
        # Get the ACTUAL previous status before changing it
        previous_status = self.state.stage_metadata['extraction'].get('status', 'pending')
        
        try:
            self._load_validated_documents_from_intake()
            self._hydrate_validated_documents_with_metadata()

            if not self.state.validated_documents:
                logger.warning("No validated documents available for extraction")
                return self.state

            extraction_crew = self.crew.extraction_crew()
            extracted_documents = []
            failed_documents = []
            skipped_documents = 0

            for doc in self.state.validated_documents:
                document_id = doc.get('document_id')
                if not document_id:
                    continue

                document_metadata = doc.get('metadata', {})
                stage_status = document_metadata.get('extraction', {}).get('status', 'pending')

                child_documents = document_metadata.get('child_documents', [])
                if child_documents and not document_metadata.get("generated_from_pdf", False):
                    skipped_documents += 1
                    self._run_tool(
                        update_document_metadata_tool,
                        document_id=document_id,
                        stage_name="extraction",
                        status="skipped",
                        msg="Extraction skipped for parent PDF; process child documents instead"
                    )
                    # Children already queued in classification stage - don't duplicate
                    continue

                extraction_output = extraction_crew.kickoff(inputs={
                    'document_id': document_id,
                    'document_metadata': document_metadata,
                    'case_id': self.state.case_id,
                    'processing_mode': self.state.processing_mode,
                    'stage_status': stage_status or previous_status
                })

                extraction_result = self._parse_crew_output(extraction_output)

                if extraction_result.get('skipped'):
                    skipped_documents += 1
                    continue

                extracted_documents.extend(
                    extraction_result.get('extracted_documents')
                    or extraction_result.get('extractions', [])
                )
                failed_documents.extend(extraction_result.get('failed_documents', []))

                refreshed = self._run_tool(get_document_by_id_tool, document_id=document_id)
                if refreshed.get("metadata"):
                    doc["metadata"] = refreshed["metadata"]

            self.state.stage_metadata['extraction']['status'] = 'running'

            self.state.extractions = extracted_documents

            self.state.successful_documents = sum(
                1 for e in self.state.extractions
                if e.get('success', True) and e.get('extraction_quality', 0) > 0.5
            )
            self.state.failed_documents = len(failed_documents)

            if self.state.successful_documents and self.state.failed_documents:
                status = "partial"
            elif self.state.successful_documents:
                status = "success"
            elif self.state.failed_documents:
                status = "fail"
            elif skipped_documents:
                status = "skipped"
            else:
                status = "pending"

            self.state.stage_metadata['extraction'] = {
                'status': status,
                'msg': f"Extraction: {self.state.successful_documents} success, {self.state.failed_documents} failed, {skipped_documents} skipped",
                'error': None,
                'trace': None,
                'data': {
                    "extracted_documents": extracted_documents,
                    "failed_documents": failed_documents,
                    "skipped_documents": skipped_documents
                }
            }
            logger.info(f"Extraction complete: {self.state.successful_documents} successful, {self.state.failed_documents} failed, {skipped_documents} skipped")
                
        except Exception as e:
            import traceback
            error_msg = f"Extraction exception: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full extraction error traceback:")
            
            # Capture failure metadata
            self.state.stage_metadata['extraction'] = {
                'status': 'fail',
                'msg': error_msg,
                'error': str(e),
                'trace': traceback.format_exc(),
                'data': None
            }
            self.state.errors.append(error_msg)
            
            # Continue to next stage anyway
    
    @listen(extract_data)
    def finalize_workflow(self):
        """
        Stage 4: Workflow finalization and reporting.
        
        Final stage that generates reports, validates results, and
        prepares the case for review or completion.
        
        This stage analyzes stage_metadata to determine overall case status.
        Business logic can determine case completion based on available data.
        
        Also checks for child documents (e.g., images from PDF conversion) that need processing.
        """
        self.state.end_time = datetime.now()
        self.state.current_stage = "finalized"
        
        processed_ids = [doc.get("document_id") for doc in self.state.validated_documents if doc.get("document_id")]

        # Auto-drain queue for additional documents (e.g., child docs)
        if self.state.auto_drain_queue:
            max_docs = config.get("processing.max_auto_drain_docs", 5)
            drained_ids = self._auto_drain_queue(max_docs=max_docs)
            processed_ids.extend(drained_ids)

        # Analyze stage results to determine case readiness
        stages_summary = {
            'intake': self.state.stage_metadata['intake']['status'],
            'classification': self.state.stage_metadata['classification']['status'],
            'extraction': self.state.stage_metadata['extraction']['status']
        }
        
        # Count successful stages
        successful_stages = sum(1 for status in stages_summary.values() if status == 'success')
        
        # Determine final status based on stage outcomes
        if successful_stages == 3:
            final_status = "completed"
        elif successful_stages == 0:
            final_status = "failed"
        else:
            # Partial success - user can decide case completion
            final_status = "partial"
        
        # Additional checks for review requirements
        if self.state.failed_documents > 0 or self.state.requires_review > 0:
            if final_status == "completed":
                final_status = "requires_review"
        
        self.state.current_stage = final_status
        self.state.processed_document_ids = list(dict.fromkeys(processed_ids))
        
        logger.info(f"Workflow finalized with status: {final_status}")
        logger.info(f"Stage summary: {stages_summary}")
    
    def get_results(self) -> Dict[str, Any]:
        """
        Get comprehensive results from the flow execution.
        
        Returns:
            Dictionary containing all processing results and stage metadata.
            Users can analyze stage_metadata to determine case completion.
        """
        # Get queue status
        queue_info = {}
        try:
            from utilities.queue_manager import DocumentQueue
            queue = DocumentQueue()
            queue_status = queue.get_status()
            queue_info = {
                'pending': queue_status['pending'],
                'processing': queue_status['processing'],
                'failed': queue_status['failed'],
                'has_pending': queue_status['pending'] > 0
            }
        except Exception as e:
            logger.warning(f"Could not retrieve queue status: {e}")
        
        return {
            'case_id': self.state.case_id,
            'status': self.state.current_stage,
            'processing_time': (
                (self.state.end_time - self.state.start_time).total_seconds()
                if self.state.start_time and self.state.end_time else None
            ),
            
            # Stage-by-stage metadata with success/failure details
            'stage_metadata': self.state.stage_metadata,
            
            # Document summary
            'documents': {
                'total': self.state.total_documents,
                'successful': self.state.successful_documents,
                'failed': self.state.failed_documents,
                'requires_review': self.state.requires_review
            },
            
            # Queue information
            'queue': queue_info,
            
            # Raw stage data (for backward compatibility)
            'validated_documents': self.state.validated_documents,
            'classifications': self.state.classifications,
            'extractions': self.state.extractions,
            
            # Errors list (deprecated - use stage_metadata instead)
            'errors': self.state.errors,
            
            # Timestamps
            'timestamps': {
                'start': self.state.start_time.isoformat() if self.state.start_time else None,
                'end': self.state.end_time.isoformat() if self.state.end_time else None
            },
            
            # Documents processed in this run (including auto-drained queue)
            'processed_document_ids': self.state.processed_document_ids,
            
            # Case completion hints
            'case_readiness': self._assess_case_readiness()
        }
    
    def _assess_case_readiness(self) -> Dict[str, Any]:
        """
        Assess whether the case has sufficient information for completion.
        
        Returns:
            Dictionary with readiness assessment and recommendations
        """
        # Check which stages succeeded
        intake_ok = self.state.stage_metadata['intake']['status'] == 'success'
        classification_ok = self.state.stage_metadata['classification']['status'] == 'success'
        extraction_ok = self.state.stage_metadata['extraction']['status'] == 'success'
        
        # Determine minimum requirements
        has_documents = len(self.state.validated_documents) > 0
        has_classifications = len(self.state.classifications) > 0
        has_extractions = len(self.state.extractions) > 0
        
        # Business logic for case completion
        is_complete = intake_ok and has_documents and (has_classifications or has_extractions)
        
        return {
            'is_complete': is_complete,
            'has_documents': has_documents,
            'has_classifications': has_classifications,
            'has_extractions': has_extractions,
            'stages_succeeded': {
                'intake': intake_ok,
                'classification': classification_ok,
                'extraction': extraction_ok
            },
            'recommendations': self._generate_recommendations(intake_ok, classification_ok, extraction_ok)
        }
    
    def _generate_recommendations(self, intake_ok: bool, classification_ok: bool, extraction_ok: bool) -> List[str]:
        """
        Generate recommendations based on stage outcomes.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if not intake_ok:
            recommendations.append("Re-upload documents with correct format")
        
        if not classification_ok:
            recommendations.append("Manual classification may be required")
        
        if not extraction_ok:
            recommendations.append("Manual data entry may be required")
        
        if intake_ok and classification_ok and extraction_ok:
            recommendations.append("Case ready for review and completion")
        
        return recommendations


def kickoff_flow(
    file_paths: List[str],
    case_id: Optional[str] = None,
    llm = None,
    visualize: bool = False,
    processing_mode: str = 'process',
    require_queue_confirmation: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to kickoff a document processing flow.
    
    Args:
        file_paths: List of document file paths to process (can be empty to process queued child docs)
        case_id: Optional case identifier for linking documents to a case
        llm: Language model instance
        visualize: Whether to generate flow visualization (default: False)
        processing_mode: Processing mode - 'process' (smart resume, skip successful stages) 
                        or 'reprocess' (force rerun all stages). Default: 'process'
        
    Returns:
        Complete processing results including document IDs
    """
    from utilities import settings

    if not FLOW_AVAILABLE:
        # Fallback to direct crew execution
        return process_documents(case_id or "UNLINKED", file_paths, llm)
    
    # Initialize flow with state
    flow = DocumentProcessingFlow(llm=llm)
    flow.state.case_id = case_id
    flow.state.file_paths = file_paths
    flow.state.processing_mode = processing_mode
    flow.state.require_queue_confirmation = require_queue_confirmation
    flow.state.auto_drain_queue = config.get("processing.auto_drain_queue", True)

    # NOTE: Child documents are now processed via the unified queue system
    # Use process_next_document_from_queue() instead of this function for queue-based processing
    # This function processes only the provided file_paths

    if not flow.state.file_paths:
        return {
            "status": "failed",
            "errors": ["No documents provided. Use process_next_document_from_queue() for queue-based processing."],
            "documents": {"total": 0, "successful": 0, "failed": 0, "requires_review": 0}
        }
    
    # Smart loading: Check if files are already processed documents and load their metadata
    if processing_mode == 'process':
        intake_dir = Path(settings.documents_dir) / "intake"
        
        for file_path in file_paths:
            file_path_obj = Path(file_path)
            
            # Check if file is in intake directory and matches DOC_* pattern
            if file_path_obj.parent.resolve() == intake_dir.resolve():
                doc_id = file_path_obj.stem  # DOC_20260127_213328_95D48
                if doc_id.startswith('DOC_'):
                    metadata_path = intake_dir / f"{doc_id}.metadata.json"
                    if metadata_path.exists():
                        # Load existing stage metadata
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        
                        for stage_name in ['intake', 'classification', 'extraction']:
                            if stage_name in metadata:
                                flow.state.stage_metadata[stage_name] = metadata[stage_name]

                        flow.state.validated_documents.append({
                            "document_id": doc_id,
                            "original_filename": metadata.get("original_filename"),
                            "stored_path": metadata.get("stored_path"),
                            "file_size": metadata.get("size_bytes"),
                            "mime_type": f"application/{metadata.get('extension', '').lstrip('.')}",
                            "validation_status": metadata.get("intake", {}).get("validation_status", "valid"),
                            "stage": "intake",
                            "metadata": metadata
                        })
                        
                        logger.info(
                            f"Loaded existing metadata for {doc_id}:\n" +
                            f"  • Intake: {flow.state.stage_metadata['intake'].get('status')}\n" +
                            f"  • Classification: {flow.state.stage_metadata['classification'].get('status')}\n" +
                            f"  • Extraction: {flow.state.stage_metadata['extraction'].get('status')}"
                        )
        flow.state.total_documents = len(flow.state.validated_documents)
    
    logger.info(
        f"Starting document processing flow\n" +
        f"Mode: {processing_mode.upper()}\n" +
        f"Files: {len(file_paths)}\n" +
        f"Case: {case_id or 'None'}\n" +
        f"Behavior: {'Skip successful stages' if processing_mode == 'process' else 'Rerun all stages'}"
    )
    
    # Optionally visualize the flow
    if visualize:
        try:
            flow_name = f"flow_{case_id}" if case_id else "flow_unlinked"
            flow.plot(filename=f"{flow_name}.html")
        except Exception as e:
            pass
    
    # Execute the flow
    logger.info(f"Kicking off flow with {len(file_paths)} documents" + (f" for case {case_id}" if case_id else ""))
    flow._run_flow_kickoff()
    
    # Return results
    return flow.get_results()


def process_next_document_from_queue(
    processing_mode: str = 'process',
    use_reasoning: bool = True,
    case_id: Optional[str] = None,
    llm = None,
    auto_drain: bool = False
) -> Dict[str, Any]:
    """
    Process next document from queue.
    
    This is the core queue-based processing function that:
    1. Gets next document from queue
    2. Processes the document through the full pipeline
    3. Updates queue status
    
    Args:
        processing_mode: 'process' or 'reprocess'
        use_reasoning: Enable agent reasoning
        case_id: Optional case to link document
        llm: Language model instance (required)
        
    Returns:
        Dict with processing result and queue status
    """
    from utilities.queue_manager import DocumentQueue
    from utilities.llm_factory import create_llm
    
    if llm is None:
        llm = create_llm()
    
    queue = DocumentQueue()
    
    # Get next document from queue
    next_entry = queue.get_next()
    
    if not next_entry:
        return {
            "status": "complete",
            "message": "No more documents in queue",
            "queue_status": queue.get_status()
        }
    
    queue_id = next_entry['id']
    file_path = next_entry['source_path']
    
    # Mark as processing
    queue.mark_processing(queue_id)
    logger.info(f"Processing queue entry: {queue_id}")
    
    try:
        # Process single document through flow
        flow = DocumentProcessingFlow(llm=llm)
        flow.state.case_id = case_id
        flow.state.file_paths = [file_path]  # Single file
        flow.state.processing_mode = processing_mode
        flow.state.auto_drain_queue = auto_drain
        
        # Run flow
        flow._run_flow_kickoff()
        
        # Get document ID from result
        document_id = None
        if flow.state.validated_documents:
            document_id = flow.state.validated_documents[0].get('document_id')
        
        # Mark completed
        queue.mark_completed(queue_id, document_id or "UNKNOWN")
        
        return {
            "status": "success",
            "queue_id": queue_id,
            "document_id": document_id,
            "result": flow.get_results(),
            "queue_status": queue.get_status()
        }
        
    except Exception as e:
        logger.error(f"Failed to process document from queue: {e}")
        queue.mark_failed(queue_id, str(e))
        
        return {
            "status": "failed",
            "queue_id": queue_id,
            "error": str(e),
            "queue_status": queue.get_status()
        }
