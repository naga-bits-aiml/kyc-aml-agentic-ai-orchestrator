"""Flow-based document processing orchestration for KYC-AML.

This module implements CrewAI's Flow pattern for event-driven workflow management
using pure CrewAI crews without hybrid/legacy dependencies.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
import json

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
from utilities import logger, settings


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
    
    # Child documents that need processing (e.g., images from PDF conversion)
    child_documents_pending: List[Dict[str, str]] = Field(default_factory=list, description="Child documents awaiting processing")


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
                'stage_status': previous_status  # Pass actual previous status
            }
            if self.state.case_id:
                intake_inputs['case_id'] = self.state.case_id
            
            logger.info(f"Executing intake crew with inputs: {intake_inputs}")
            intake_output = intake_crew.kickoff(inputs=intake_inputs)
            logger.info(f"Intake crew completed. Output type: {type(intake_output)}")
            
            # Extract result from CrewOutput and parse JSON
            import json
            if hasattr(intake_output, 'raw'):
                logger.info(f"Intake raw output: {intake_output.raw[:500]}...")  # Log first 500 chars
                intake_result = json.loads(intake_output.raw)
            else:
                logger.info(f"Intake output (no raw attribute): {str(intake_output)[:500]}...")
                intake_result = intake_output
            
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
            
            # Capture success metadata
            self.state.stage_metadata['intake'] = {
                'status': 'success',
                'msg': f"Successfully validated {self.state.total_documents} documents",
                'error': None,
                'trace': None,
                'data': intake_result
            }
            logger.info(f"Intake complete: {self.state.total_documents} documents validated")
                
        except Exception as e:
            import traceback
            error_msg = f"Intake exception: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full intake error traceback:")
            
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
            # Use documents from intake if available, otherwise use file paths
            documents_to_classify = self.state.validated_documents
            
            if not documents_to_classify:
                logger.warning("No validated documents from intake. Classification may fail.")
            
            # Execute classification using crew - agent decides whether to skip or execute
            classification_crew = self.crew.classification_crew()
            classification_output = classification_crew.kickoff(inputs={
                'case_id': self.state.case_id,
                'documents': documents_to_classify,
                'processing_mode': self.state.processing_mode,
                'stage_status': previous_status  # Pass actual previous status
            })
            
            # Extract result from CrewOutput and parse JSON
            import json
            classification_result = json.loads(classification_output.raw) if hasattr(classification_output, 'raw') else classification_output
            
            # Check if stage was skipped
            if classification_result.get('skipped'):
                logger.info(f"Classification stage skipped: {classification_result.get('message')}")
                return self.state
            
            # Stage was executed, set to running then success
            self.state.stage_metadata['classification']['status'] = 'running'
            
            # Update state with results
            self.state.classifications = classification_result.get('classifications', [])
            self.state.requires_review = sum(
                1 for c in self.state.classifications 
                if c.get('requires_review', False)
            )
            
            # Capture success metadata
            self.state.stage_metadata['classification'] = {
                'status': 'success',
                'msg': f"Successfully classified {len(self.state.classifications)} documents",
                'error': None,
                'trace': None,
                'data': classification_result
            }
            logger.info(f"Classification complete: {len(self.state.classifications)} documents classified")
                
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
            # Use classifications if available, otherwise try with file paths
            classifications_to_extract = self.state.classifications
            
            if not classifications_to_extract:
                logger.warning("No classifications available. Extraction may fail.")
            
            # Execute extraction using crew - agent decides whether to skip or execute
            extraction_crew = self.crew.extraction_crew()
            extraction_output = extraction_crew.kickoff(inputs={
                'case_id': self.state.case_id,
                'classifications': classifications_to_extract,
                'processing_mode': self.state.processing_mode,
                'stage_status': previous_status  # Pass actual previous status
            })
            
            # Extract result from CrewOutput (Vision API returns structured JSON)
            import json
            extraction_result = {}
            
            # Parse CrewOutput - try raw JSON first, then other attributes
            if hasattr(extraction_output, 'raw') and extraction_output.raw:
                raw_str = str(extraction_output.raw).strip()
                if raw_str:  # Only try to parse non-empty strings
                    try:
                        extraction_result = json.loads(raw_str)
                        logger.info(f"Parsed extraction result from raw: {len(extraction_result.get('extractions', []))} extractions")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse raw as JSON (len={len(raw_str)}): {e}")
                        # Try to extract JSON from text if embedded
                        import re
                        json_match = re.search(r'\{.*\}', raw_str, re.DOTALL)
                        if json_match:
                            try:
                                extraction_result = json.loads(json_match.group())
                                logger.info("Extracted JSON from text successfully")
                            except:
                                extraction_result = {"error": "Could not parse output", "raw": raw_str[:500]}
                        else:
                            extraction_result = {"error": "No JSON found in output", "raw": raw_str[:500]}
            elif hasattr(extraction_output, 'json'):
                extraction_result = extraction_output.json
            elif isinstance(extraction_output, dict):
                extraction_result = extraction_output
            else:
                logger.error(f"Unexpected output type: {type(extraction_output)}")
                extraction_result = {"error": "Invalid output format", "output": str(extraction_output)[:500]}
            
            # Check if stage was skipped
            if extraction_result.get('skipped'):
                logger.info(f"Extraction stage skipped: {extraction_result.get('message')}")
                return self.state
            
            # Stage was executed, set to running then success
            self.state.stage_metadata['extraction']['status'] = 'running'
            
            # Update state with results (Vision API provides structured extractions)
            self.state.extractions = extraction_result.get('extractions', [])
            
            # Count successful vs failed extractions (based on fields found)
            self.state.successful_documents = sum(
                1 for e in self.state.extractions 
                if e.get('success', False) and e.get('extraction_quality', 0) > 0.5
            )
            self.state.failed_documents = len(self.state.extractions) - self.state.successful_documents
            
            # Capture success metadata
            self.state.stage_metadata['extraction'] = {
                'status': 'success',
                'msg': f"Successfully extracted data from {self.state.successful_documents}/{len(self.state.extractions)} documents",
                'error': None,
                'trace': None,
                'data': extraction_result
            }
            logger.info(f"Extraction complete: {self.state.successful_documents} successful, {self.state.failed_documents} failed")
                
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
        
        # Check for child documents that need processing
        child_documents = self._find_child_documents()
        if child_documents:
            logger.info(f"Found {len(child_documents)} child documents that need processing")
            self.state.child_documents_pending = child_documents
        
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
        
        logger.info(f"Workflow finalized with status: {final_status}")
        logger.info(f"Stage summary: {stages_summary}")
    
    def _find_child_documents(self) -> List[Dict[str, str]]:
        """
        Find any child documents (e.g., images from PDF conversion) that need processing.
        
        Returns:
            List of child document info dictionaries with document_id and parent_id
        """
        child_docs = []
        
        try:
            intake_dir = Path(settings.documents_dir) / "intake"
            
            # Check all processed documents for child_documents field
            for doc_info in self.state.validated_documents:
                doc_id = doc_info.get('document_id')
                if not doc_id:
                    continue
                
                metadata_path = intake_dir / f"{doc_id}.metadata.json"
                if not metadata_path.exists():
                    continue
                
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Check if this document has child documents
                child_doc_ids = metadata.get('child_documents', [])
                for child_id in child_doc_ids:
                    # Verify child document exists and hasn't been processed yet
                    child_metadata_path = intake_dir / f"{child_id}.metadata.json"
                    if child_metadata_path.exists():
                        with open(child_metadata_path, 'r') as cf:
                            child_meta = json.load(cf)
                        
                        # Check if child needs processing (classification is pending)
                        classification_status = child_meta.get('classification', {}).get('status', 'pending')
                        if classification_status == 'pending':
                            child_docs.append({
                                'document_id': child_id,
                                'parent_id': doc_id,
                                'filename': child_meta.get('original_filename', 'unknown')
                            })
                            logger.info(f"Child document {child_id} needs processing (parent: {doc_id})")
        
        except Exception as e:
            logger.error(f"Error finding child documents: {e}")
            logger.exception("Full traceback:")
        
        return child_docs
    def get_results(self) -> Dict[str, Any]:
        """
        Get comprehensive results from the flow execution.
        
        Returns:
            Dictionary containing all processing results and stage metadata.
            Users can analyze stage_metadata to determine case completion.
        """
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
            
            # Child documents that need processing
            'child_documents_pending': self.state.child_documents_pending,
            
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
    processing_mode: str = 'process'
) -> Dict[str, Any]:
    """
    Convenience function to kickoff a document processing flow.
    
    Args:
        file_paths: List of document file paths to process
        case_id: Optional case identifier for linking documents to a case
        llm: Language model instance
        visualize: Whether to generate flow visualization (default: False)
        processing_mode: Processing mode - 'process' (smart resume, skip successful stages) 
                        or 'reprocess' (force rerun all stages). Default: 'process'
        
    Returns:
        Complete processing results including document IDs
    """
    if not FLOW_AVAILABLE:
        # Fallback to direct crew execution
        return process_documents(case_id or "UNLINKED", file_paths, llm)
    
    # Initialize flow with state
    flow = DocumentProcessingFlow(llm=llm)
    flow.state.case_id = case_id
    flow.state.file_paths = file_paths
    flow.state.processing_mode = processing_mode
    
    # Smart loading: Check if files are already processed documents and load their metadata
    if processing_mode == 'process':
        from utilities import settings
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
                        
                        logger.info(
                            f"Loaded existing metadata for {doc_id}:\n" +
                            f"  • Intake: {flow.state.stage_metadata['intake'].get('status')}\n" +
                            f"  • Classification: {flow.state.stage_metadata['classification'].get('status')}\n" +
                            f"  • Extraction: {flow.state.stage_metadata['extraction'].get('status')}"
                        )
    
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
    flow.kickoff()
    
    # Return results
    return flow.get_results()
