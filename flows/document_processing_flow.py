"""Flow-based document processing orchestration for KYC-AML.

This module implements CrewAI's Flow pattern for event-driven workflow management
using pure CrewAI crews without hybrid/legacy dependencies.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime

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
from utilities import logger


class DocumentProcessingState(BaseModel):
    """
    State management for document processing flow.
    Uses Pydantic for type-safe state transitions.
    """
    # Input parameters
    case_id: str = Field(default="", description="Unique case identifier")
    file_paths: List[str] = Field(default_factory=list, description="List of document file paths")
    
    # Processing state
    current_stage: str = Field(default="initialized", description="Current workflow stage")
    use_reasoning: bool = Field(default=True, description="Whether to use autonomous reasoning")
    
    # Stage results
    validated_documents: List[Dict[str, Any]] = Field(default_factory=list)
    classifications: List[Dict[str, Any]] = Field(default_factory=list)
    extractions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Metadata
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)
    
    # Summary metrics
    total_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0
    requires_review: int = 0


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
        checks file integrity, and prepares them for processing.
        """
        self.state.current_stage = "intake"
        self.state.start_time = datetime.now()
        
        try:
            # Execute intake using crew
            intake_crew = self.crew.intake_crew()
            intake_output = intake_crew.kickoff(inputs={
                'case_id': self.state.case_id,
                'file_paths': self.state.file_paths
            })
            
            # Extract result from CrewOutput and parse JSON
            import json
            intake_result = json.loads(intake_output.raw) if hasattr(intake_output, 'raw') else intake_output
            
            # Update state with results
            self.state.validated_documents = intake_result.get('validated_documents', [])
            self.state.total_documents = len(self.state.validated_documents)
                
        except Exception as e:
            error_msg = f"Intake exception: {str(e)}"
            self.state.errors.append(error_msg)
            self.state.current_stage = "failed"
    
    @listen(intake_documents)
    def classify_documents(self):
        """
        Stage 2: Document classification.
        
        Triggered after intake completes successfully. Classifies each document
        into appropriate categories (identity_proof, address_proof, etc.).
        """
        # Check if intake was successful
        if self.state.current_stage == "failed" or not self.state.validated_documents:
            return
        
        self.state.current_stage = "classification"
        
        try:
            # Execute classification using crew
            classification_crew = self.crew.classification_crew()
            classification_output = classification_crew.kickoff(inputs={
                'case_id': self.state.case_id,
                'documents': self.state.validated_documents
            })
            
            # Extract result from CrewOutput and parse JSON
            import json
            classification_result = json.loads(classification_output.raw) if hasattr(classification_output, 'raw') else classification_output
            
            # Update state with results
            self.state.classifications = classification_result.get('classifications', [])
            self.state.requires_review = sum(
                1 for c in self.state.classifications 
                if c.get('requires_review', False)
            )
                
        except Exception as e:
            error_msg = f"Classification exception: {str(e)}"
            self.state.errors.append(error_msg)
            self.state.current_stage = "partial"
    
    @listen(classify_documents)
    def extract_data(self):
        """
        Stage 3: Data extraction.
        
        Triggered after classification completes. Extracts structured data
        from each classified document using appropriate tools.
        """
        # Check if classification was successful
        if self.state.current_stage == "failed" or not self.state.classifications:
            return
        
        self.state.current_stage = "extraction"
        
        try:
            # Execute extraction using crew
            extraction_crew = self.crew.extraction_crew()
            extraction_output = extraction_crew.kickoff(inputs={
                'case_id': self.state.case_id,
                'classifications': self.state.classifications
            })
            
            # Extract result from CrewOutput and parse JSON
            import json
            extraction_result = json.loads(extraction_output.raw) if hasattr(extraction_output, 'raw') else extraction_output
            
            # Update state with results
            self.state.extractions = extraction_result.get('extractions', [])
            
            # Count successful vs failed extractions
            self.state.successful_documents = sum(
                1 for e in self.state.extractions 
                if e.get('extraction_quality', 0) > 0.5
            )
            self.state.failed_documents = len(self.state.extractions) - self.state.successful_documents
                
        except Exception as e:
            error_msg = f"Extraction exception: {str(e)}"
            self.state.errors.append(error_msg)
            self.state.current_stage = "partial"
    
    @listen(extract_data)
    def finalize_workflow(self):
        """
        Stage 4: Workflow finalization and reporting.
        
        Final stage that generates reports, validates results, and
        prepares the case for review or completion.
        """
        self.state.end_time = datetime.now()
        
        # Determine final status
        if self.state.current_stage == "failed":
            final_status = "failed"
        elif self.state.errors:
            final_status = "partial"
        elif self.state.failed_documents > 0 or self.state.requires_review > 0:
            final_status = "requires_review"
        else:
            final_status = "completed"
        
        self.state.current_stage = final_status
        
        # Calculate processing time
        self.state.current_stage = final_status
    def get_results(self) -> Dict[str, Any]:
        """
        Get comprehensive results from the flow execution.
        
        Returns:
            Dictionary containing all processing results and metadata
        """
        return {
            'case_id': self.state.case_id,
            'status': self.state.current_stage,
            'processing_time': (
                (self.state.end_time - self.state.start_time).total_seconds()
                if self.state.start_time and self.state.end_time else None
            ),
            'documents': {
                'total': self.state.total_documents,
                'successful': self.state.successful_documents,
                'failed': self.state.failed_documents,
                'requires_review': self.state.requires_review
            },
            'validated_documents': self.state.validated_documents,
            'classifications': self.state.classifications,
            'extractions': self.state.extractions,
            'errors': self.state.errors,
            'timestamps': {
                'start': self.state.start_time.isoformat() if self.state.start_time else None,
                'end': self.state.end_time.isoformat() if self.state.end_time else None
            }
        }


def kickoff_flow(
    case_id: str,
    file_paths: List[str],
    llm,
    visualize: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to kickoff a document processing flow.
    
    Args:
        case_id: Unique case identifier
        file_paths: List of document file paths to process
        llm: Language model instance
        visualize: Whether to generate flow visualization (default: False)
        
    Returns:
        Complete processing results
    """
    if not FLOW_AVAILABLE:
        # Fallback to direct crew execution
        return process_documents(case_id, file_paths, llm)
    
    # Initialize flow with state
    flow = DocumentProcessingFlow(llm=llm)
    flow.state.case_id = case_id
    flow.state.file_paths = file_paths
    
    # Optionally visualize the flow
    if visualize:
        try:
            flow.plot(filename=f"flow_{case_id}.html")
        except Exception as e:
            pass
    
    # Execute the flow
    logger.info(f"Kicking off flow for case {case_id} with {len(file_paths)} documents")
    flow.kickoff()
    
    # Return results
    return flow.get_results()
