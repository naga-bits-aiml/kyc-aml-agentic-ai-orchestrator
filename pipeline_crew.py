"""
Document Processing Pipeline - CrewAI Crew Definition

This module defines the CrewAI crew with 5 specialized agents:
1. QueueAgent - Builds and manages the processing queue
2. ClassificationAgent - Calls external API for document classification
3. ExtractionAgent - Calls external API for data extraction
4. MetadataAgent - Tracks status and handles errors
5. SummaryAgent - Generates final processing summary

Each agent uses deterministic tools for file operations and REST calls.
"""

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from typing import Optional, Dict, Any, Union

# Import tools
from tools.queue_tools import (
    scan_input_path,
    expand_folder,
    split_pdf_to_images,
    build_processing_queue,
    get_next_from_queue,
    get_queue_status,
    mark_document_processed
)

from tools.classification_api_tools import (
    classify_document,
    get_classification_result,
    batch_classify_documents
)

from tools.extraction_api_tools import (
    extract_document_data,
    get_extraction_result,
    batch_extract_documents,
    get_expected_fields_for_type
)

from tools.metadata_tools import (
    get_document_metadata,
    update_processing_status,
    record_error,
    check_retry_eligible,
    reset_stage_for_retry,
    flag_for_review,
    get_processing_summary,
    list_all_metadata
)

from tools.summary_tools import (
    generate_processing_summary,
    generate_report_text,
    get_document_results,
    export_results_json
)


@CrewBase
class DocumentProcessingCrew:
    """
    CrewAI Crew for document processing pipeline.
    
    This crew orchestrates document intake, classification, and extraction
    using specialized agents with deterministic tools.
    """
    
    agents_config = 'config/pipeline_agents.yaml'
    tasks_config = 'config/pipeline_tasks.yaml'
    
    def __init__(self, llm: Optional[Union[LLM, str]] = None):
        """
        Initialize the crew with LLM.
        
        Args:
            llm: CrewAI LLM instance or model string (optional, defaults to configured model)
        """
        if llm is None:
            # Create CrewAI LLM from config
            from utilities import config
            llm_config = config.get("llm", {})
            provider = llm_config.get("provider", "google")
            model_name = llm_config.get("model_name", "gemini-2.5-flash")
            
            # CrewAI uses format like "gemini/gemini-2.5-flash" or "openai/gpt-4"
            if provider == "google":
                model_str = f"gemini/{model_name}"
            elif provider == "openai":
                model_str = f"openai/{model_name}"
            else:
                model_str = f"{provider}/{model_name}"
            
            self.llm = LLM(model=model_str)
        elif isinstance(llm, str):
            self.llm = LLM(model=llm)
        else:
            self.llm = llm
    
    # ==================== AGENT DEFINITIONS ====================
    
    @agent
    def queue_agent(self) -> Agent:
        """
        Queue Agent - Builds and manages the processing queue.
        
        Tools:
        - scan_input_path: Determine if input is file or folder
        - expand_folder: Recursively collect files from folder
        - split_pdf_to_images: Convert PDF pages to images
        - build_processing_queue: Create queue with metadata
        - get_next_from_queue: Get next document to process
        - get_queue_status: Check queue statistics
        """
        return Agent(
            config=self.agents_config['queue_agent'],
            tools=[
                scan_input_path,
                expand_folder,
                split_pdf_to_images,
                build_processing_queue,
                get_next_from_queue,
                get_queue_status,
                mark_document_processed
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def classification_agent(self) -> Agent:
        """
        Classification Agent - Calls external API for document classification.
        
        Tools:
        - classify_document: Send document to classification API
        - get_classification_result: Get classification from metadata
        - batch_classify_documents: Classify multiple documents
        """
        return Agent(
            config=self.agents_config['classification_agent'],
            tools=[
                classify_document,
                get_classification_result,
                batch_classify_documents
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def extraction_agent(self) -> Agent:
        """
        Extraction Agent - Calls external API for data extraction.
        
        Tools:
        - extract_document_data: Send document to extraction API
        - get_extraction_result: Get extraction from metadata
        - batch_extract_documents: Extract from multiple documents
        - get_expected_fields_for_type: Get expected field schema
        """
        return Agent(
            config=self.agents_config['extraction_agent'],
            tools=[
                extract_document_data,
                get_extraction_result,
                batch_extract_documents,
                get_expected_fields_for_type
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def metadata_agent(self) -> Agent:
        """
        Metadata Agent - Tracks status and handles errors.
        
        Tools:
        - get_document_metadata: Read document metadata
        - update_processing_status: Update stage status
        - record_error: Record error with retry count
        - check_retry_eligible: Check if document can be retried
        - reset_stage_for_retry: Reset stage for retry
        - flag_for_review: Flag document for manual review
        - get_processing_summary: Get summary for a document
        - list_all_metadata: List all documents
        """
        return Agent(
            config=self.agents_config['metadata_agent'],
            tools=[
                get_document_metadata,
                update_processing_status,
                record_error,
                check_retry_eligible,
                reset_stage_for_retry,
                flag_for_review,
                get_processing_summary,
                list_all_metadata
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def summary_agent(self) -> Agent:
        """
        Summary Agent - Generates final processing summary.
        
        Tools:
        - generate_processing_summary: Aggregate all results
        - generate_report_text: Create human-readable report
        - get_document_results: Get results for specific docs
        - export_results_json: Export full results to file
        """
        return Agent(
            config=self.agents_config['summary_agent'],
            tools=[
                generate_processing_summary,
                generate_report_text,
                get_document_results,
                export_results_json
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    # ==================== TASK DEFINITIONS ====================
    
    @task
    def build_queue_task(self) -> Task:
        """Task: Build the processing queue from input path."""
        return Task(
            config=self.tasks_config['build_queue_task'],
            agent=self.queue_agent()
        )
    
    @task
    def classify_document_task(self) -> Task:
        """Task: Classify a single document."""
        return Task(
            config=self.tasks_config['classify_document_task'],
            agent=self.classification_agent()
        )
    
    @task
    def extract_document_task(self) -> Task:
        """Task: Extract data from a document."""
        return Task(
            config=self.tasks_config['extract_document_task'],
            agent=self.extraction_agent()
        )
    
    @task
    def handle_error_task(self) -> Task:
        """Task: Handle processing error with retry logic."""
        return Task(
            config=self.tasks_config['handle_error_task'],
            agent=self.metadata_agent()
        )
    
    @task
    def generate_summary_task(self) -> Task:
        """Task: Generate final processing summary."""
        return Task(
            config=self.tasks_config['generate_summary_task'],
            agent=self.summary_agent()
        )
    
    # ==================== CREW DEFINITIONS ====================
    
    @crew
    def queue_crew(self) -> Crew:
        """Crew for building the initial queue."""
        return Crew(
            agents=[self.queue_agent()],
            tasks=[self.build_queue_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def classification_crew(self) -> Crew:
        """Crew for document classification."""
        return Crew(
            agents=[self.classification_agent(), self.metadata_agent()],
            tasks=[self.classify_document_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def extraction_crew(self) -> Crew:
        """Crew for data extraction."""
        return Crew(
            agents=[self.extraction_agent(), self.metadata_agent()],
            tasks=[self.extract_document_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def summary_crew(self) -> Crew:
        """Crew for generating final summary."""
        return Crew(
            agents=[self.summary_agent()],
            tasks=[self.generate_summary_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def full_pipeline_crew(self) -> Crew:
        """
        Full pipeline crew with all agents.
        
        Note: For step-by-step execution per document,
        use the Flow class instead.
        """
        return Crew(
            agents=[
                self.queue_agent(),
                self.classification_agent(),
                self.extraction_agent(),
                self.metadata_agent(),
                self.summary_agent()
            ],
            tasks=[
                self.build_queue_task(),
                self.classify_document_task(),
                self.extract_document_task(),
                self.generate_summary_task()
            ],
            process=Process.sequential,
            verbose=True
        )


# ==================== CONVENIENCE FUNCTIONS ====================

def create_pipeline_crew(llm: Optional[Union[LLM, str]] = None) -> DocumentProcessingCrew:
    """
    Create a new document processing crew.
    
    Args:
        llm: Optional CrewAI LLM instance or model string
        
    Returns:
        Configured DocumentProcessingCrew instance
    """
    return DocumentProcessingCrew(llm=llm)


def run_queue_build(input_path: str, llm: Optional[Union[LLM, str]] = None) -> Dict[str, Any]:
    """
    Run queue building for an input path.
    
    Args:
        input_path: File or folder path
        llm: Optional CrewAI LLM instance or model string
        
    Returns:
        Queue building result
    """
    crew = create_pipeline_crew(llm)
    result = crew.queue_crew().kickoff(inputs={"input_path": input_path})
    return result


def run_classification(document_id: str, llm: Optional[Union[LLM, str]] = None) -> Dict[str, Any]:
    """
    Run classification for a document.
    
    Args:
        document_id: Document ID to classify
        llm: Optional CrewAI LLM instance or model string
        
    Returns:
        Classification result
    """
    crew = create_pipeline_crew(llm)
    result = crew.classification_crew().kickoff(inputs={"document_id": document_id})
    return result


def run_extraction(document_id: str, document_type: str = None, llm: Optional[Union[LLM, str]] = None) -> Dict[str, Any]:
    """
    Run extraction for a document.
    
    Args:
        document_id: Document ID to extract
        document_type: Optional document type from classification
        llm: Optional CrewAI LLM instance or model string
        
    Returns:
        Extraction result
    """
    crew = create_pipeline_crew(llm)
    result = crew.extraction_crew().kickoff(inputs={
        "document_id": document_id,
        "document_type": document_type or ""
    })
    return result


def run_summary(llm: Optional[Union[LLM, str]] = None) -> Dict[str, Any]:
    """
    Run summary generation.
    
    Args:
        llm: Optional CrewAI LLM instance or model string
        
    Returns:
        Processing summary
    """
    crew = create_pipeline_crew(llm)
    result = crew.summary_crew().kickoff(inputs={})
    return result
