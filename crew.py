"""Pure CrewAI implementation for KYC-AML document processing.

This module implements standard CrewAI patterns using @CrewBase, @agent, and @task decorators.
Agents use tools directly without any legacy agent wrappers.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import Optional, List, Dict, Any
from langchain.llms.base import BaseLLM

# Import CrewAI tools
from tools.intake_tools import (
    validate_document_tool,
    batch_validate_documents_tool,
    link_document_to_case_tool,
    get_document_by_id_tool,
    list_documents_by_case_tool,
    list_all_documents_tool
)
from tools.pdf_conversion_tools import (
    convert_pdf_to_images_tool,
    check_pdf_conversion_needed_tool
)
from tools.classifier_tools import (
    get_classifier_api_info_tool,
    make_classifier_api_request,
    extract_document_file_path_tool
)
from tools.extraction_tools import (
    extract_text_from_pdf_tool,
    extract_text_from_image_tool,
    batch_extract_documents_tool
)
from tools.stage_management_tools import (
    move_document_to_stage,
    get_documents_by_stage,
    get_stage_summary,
    update_document_metadata_in_stage,
    update_document_metadata_tool
)
from tools.skip_check_tool import check_if_stage_should_skip_tool
from tools.skip_check_tool import check_if_stage_should_skip_tool


@CrewBase
class KYCAMLCrew:
    """
    Pure CrewAI KYC-AML Document Processing Crew.
    
    This crew orchestrates document intake, classification, and extraction
    using standard CrewAI patterns with tool-based agents.
    """
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self, llm: Optional[BaseLLM] = None):
        """
        Initialize the crew with LLM.
        
        Args:
            llm: Language model instance (optional, defaults to GPT-4)
        """
        self.llm = llm
        if self.llm is None:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model="gpt-4", temperature=0.1)
    
    # ==================== AGENT DEFINITIONS ====================
    
    @agent
    def document_intake_agent(self) -> Agent:
        """
        Document intake and validation agent.
        Uses validation tools to check and organize documents.
        """
        return Agent(
            config=self.agents_config['document_intake_agent'],
            tools=[
                check_if_stage_should_skip_tool,
                validate_document_tool,
                batch_validate_documents_tool,
                convert_pdf_to_images_tool,
                check_pdf_conversion_needed_tool,
                move_document_to_stage,
                get_stage_summary,
                update_document_metadata_tool
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def document_classifier_agent(self) -> Agent:
        """
        Document classification agent.
        Wraps autonomous classifier with CrewAI Agent interface and tools.
        """
        return Agent(
            config=self.agents_config['document_classifier_agent'],
            tools=[
                check_if_stage_should_skip_tool,
                get_classifier_api_info_tool,
                make_classifier_api_request,
                extract_document_file_path_tool,
                get_document_by_id_tool,
                convert_pdf_to_images_tool,
                check_pdf_conversion_needed_tool,
                update_document_metadata_tool
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def document_extraction_agent(self) -> Agent:
        """
        Data extraction agent.
        Uses OCR and extraction tools to extract structured data.
        """
        return Agent(
            config=self.agents_config['document_extraction_agent'],
            tools=[
                check_if_stage_should_skip_tool,
                extract_text_from_pdf_tool,
                extract_text_from_image_tool,
                batch_extract_documents_tool,
                move_document_to_stage,
                get_documents_by_stage,
                update_document_metadata_tool
            ],
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
    
    @agent
    def supervisor_agent(self) -> Agent:
        """
        Workflow supervisor agent.
        Coordinates the overall processing workflow.
        """
        return Agent(
            config=self.agents_config['supervisor_agent'],
            verbose=True,
            llm=self.llm,
            allow_delegation=True
        )
    
    # ==================== TASK DEFINITIONS ====================
    
    @task
    def validate_documents_task(self) -> Task:
        """Task for document validation and intake."""
        return Task(
            config=self.tasks_config['validate_documents_task'],
            agent=self.document_intake_agent()
        )
    
    @task
    def classify_documents_task(self) -> Task:
        """Task for document classification."""
        return Task(
            config=self.tasks_config['classify_documents_task'],
            agent=self.document_classifier_agent()
        )
    
    @task
    def extract_document_data_task(self) -> Task:
        """Task for data extraction from documents."""
        return Task(
            config=self.tasks_config['extract_document_data_task'],
            agent=self.document_extraction_agent()
        )
    
    @task
    def orchestrate_workflow_task(self) -> Task:
        """Task for workflow orchestration."""
        return Task(
            config=self.tasks_config['orchestrate_workflow_task'],
            agent=self.supervisor_agent()
        )
    
    # ==================== CREW DEFINITIONS ====================
    
    @crew
    def intake_crew(self) -> Crew:
        """
        Creates the intake crew for document validation.
        """
        return Crew(
            agents=[self.document_intake_agent()],
            tasks=[self.validate_documents_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def classification_crew(self) -> Crew:
        """
        Creates the classification crew for document categorization.
        """
        return Crew(
            agents=[self.document_classifier_agent()],
            tasks=[self.classify_documents_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def extraction_crew(self) -> Crew:
        """
        Creates the extraction crew for data extraction.
        """
        return Crew(
            agents=[self.document_extraction_agent()],
            tasks=[self.extract_document_data_task()],
            process=Process.sequential,
            verbose=True
        )
    
    @crew
    def full_pipeline_crew(self) -> Crew:
        """
        Creates the complete processing crew with all agents.
        """
        return Crew(
            agents=self.agents,  # Auto-collected from @agent decorators
            tasks=self.tasks,    # Auto-collected from @task decorators
            process=Process.sequential,
            verbose=True
        )
    
    # ==================== CONVENIENCE METHODS ====================
    
    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the full pipeline crew.
        
        Args:
            inputs: Input parameters including:
                - case_id: Case identifier
                - file_paths: List of document file paths
                
        Returns:
            Crew execution results
        """
        crew = self.full_pipeline_crew()
        result = crew.kickoff(inputs=inputs)
        return result


        results = {
            'case_id': case_id,
            'stages': {}
        }
        
class KYCAMLCrewFactory:
    """Factory for creating specialized KYC-AML crews."""
    
    @staticmethod
    def create_intake_only_crew(llm: Optional[BaseLLM] = None) -> Crew:
        """Create a crew that only handles document intake."""
        crew_instance = KYCAMLCrew(llm=llm)
        return crew_instance.intake_crew()
    
    @staticmethod
    def create_classification_only_crew(llm: Optional[BaseLLM] = None) -> Crew:
        """
        Docstring for create_classification_only_crew
        
        :param llm: Description
        :type llm: Optional[BaseLLM]
        :return: Description
        :rtype: Crew
        """
        """Create a crew that only handles document classification."""
        crew_instance = KYCAMLCrew(llm=llm)
        return crew_instance.classification_crew()
    
    @staticmethod
    def create_extraction_only_crew(llm: Optional[BaseLLM] = None) -> Crew:
        """Create a crew that only handles data extraction."""
        crew_instance = KYCAMLCrew(llm=llm)
        return crew_instance.extraction_crew()
    
    @staticmethod
    def create_full_pipeline_crew(llm: Optional[BaseLLM] = None) -> Crew:
        """Create a crew for the complete document processing pipeline."""
        crew_instance = KYCAMLCrew(llm=llm)
        return crew_instance.full_pipeline_crew()


# Convenience function for direct usage
def process_documents(case_id: str, file_paths: List[str], 
                     llm: Optional[BaseLLM] = None) -> Dict[str, Any]:
    """
    Process documents through the complete KYC-AML pipeline.
    
    Args:
        case_id: Case identifier
        file_paths: List of document file paths to process
        llm: Language model to use (optional)
        
    Returns:
        Processing results from the crew
    
    """
    
    crew = KYCAMLCrew(llm=llm)
    return crew.kickoff({
        'case_id': case_id,
        'file_paths': file_paths
    })
