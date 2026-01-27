"""Test suite for CrewAI integration with hybrid architecture.

This module tests the new CrewAI-compliant crew implementation,
ensuring that the hybrid approach works correctly.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from crew import KYCAMLCrew, KYCAMLCrewFactory
from agents.shared_memory import SharedMemory
from agents.autonomous_intake_agent import AutonomousIntakeAgent
from agents.autonomous_classification_agent import AutonomousClassificationAgent
from agents.autonomous_extraction_agent import AutonomousExtractionAgent


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = Mock()
    llm.model_name = "gpt-4-test"
    llm.model = "gpt-4-test"
    llm.invoke = Mock(return_value=Mock(content='{"status": "completed"}'))
    llm.temperature = 0.1
    return llm


@pytest.fixture
def shared_memory():
    """Create a shared memory instance for testing."""
    return SharedMemory()


@pytest.fixture
def kyc_crew(mock_llm, shared_memory):
    """Create a KYCAMLCrew instance for testing."""
    return KYCAMLCrew(llm=mock_llm, shared_memory=shared_memory)


class TestCrewConfiguration:
    """Test crew configuration and initialization."""
    
    def test_crew_initialization(self, mock_llm):
        """Test that crew initializes correctly."""
        crew = KYCAMLCrew(llm=mock_llm)
        
        assert crew.llm is not None
        assert crew.shared_memory is not None
        assert crew.autonomous_intake is not None
        assert crew.autonomous_classifier is not None
        assert crew.autonomous_extractor is not None
    
    def test_agents_config_loaded(self, kyc_crew):
        """Test that agents configuration is loaded."""
        config_path = Path('config/agents.yaml')
        assert config_path.exists(), "agents.yaml should exist"
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Check key agents exist in config
        assert 'document_intake_agent' in config
        assert 'document_classifier_agent' in config
        assert 'document_extraction_agent' in config
        assert 'autonomous_intake_agent' in config
        assert 'autonomous_classification_agent' in config
        assert 'autonomous_extraction_agent' in config
    
    def test_tasks_config_loaded(self, kyc_crew):
        """Test that tasks configuration is loaded."""
        config_path = Path('config/tasks.yaml')
        assert config_path.exists(), "tasks.yaml should exist"
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Check key tasks exist in config
        assert 'validate_documents_task' in config
        assert 'classify_documents_task' in config
        assert 'extract_document_data_task' in config
        assert 'orchestrate_workflow_task' in config


class TestAgentCreation:
    """Test agent creation using decorators."""
    
    def test_intake_agent_creation(self, kyc_crew):
        """Test intake agent is created correctly."""
        agent = kyc_crew.document_intake_agent()
        
        assert agent is not None
        assert agent.llm is not None
        assert agent.verbose is True
    
    def test_classifier_agent_creation(self, kyc_crew):
        """Test classifier agent is created with tools."""
        agent = kyc_crew.document_classifier_agent()
        
        assert agent is not None
        assert agent.llm is not None
        assert hasattr(agent, 'tools')
    
    def test_extraction_agent_creation(self, kyc_crew):
        """Test extraction agent is created with tools."""
        agent = kyc_crew.document_extraction_agent()
        
        assert agent is not None
        assert agent.llm is not None
        assert hasattr(agent, 'tools')
    
    def test_supervisor_agent_creation(self, kyc_crew):
        """Test supervisor agent allows delegation."""
        agent = kyc_crew.supervisor_agent()
        
        assert agent is not None
        assert agent.llm is not None


class TestTaskCreation:
    """Test task creation using decorators."""
    
    def test_validate_documents_task_creation(self, kyc_crew):
        """Test validate documents task is created."""
        task = kyc_crew.validate_documents_task()
        
        assert task is not None
        assert task.agent is not None
    
    def test_classify_documents_task_creation(self, kyc_crew):
        """Test classify documents task is created."""
        task = kyc_crew.classify_documents_task()
        
        assert task is not None
        assert task.agent is not None
    
    def test_extract_document_data_task_creation(self, kyc_crew):
        """Test extract document data task is created."""
        task = kyc_crew.extract_document_data_task()
        
        assert task is not None
        assert task.agent is not None


class TestCrewExecution:
    """Test crew execution methods."""
    
    @patch.object(AutonomousIntakeAgent, 'execute')
    def test_execute_with_reasoning_intake(self, mock_execute, kyc_crew):
        """Test executing intake with reasoning."""
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {'validated_documents': []}
        }
        
        result = kyc_crew.execute_with_reasoning(
            'intake',
            {'case_id': 'test_case', 'file_paths': []}
        )
        
        assert result['status'] == 'completed'
        mock_execute.assert_called_once()
    
    @patch.object(AutonomousClassificationAgent, 'execute')
    def test_execute_with_reasoning_classification(self, mock_execute, kyc_crew):
        """Test executing classification with reasoning."""
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {'classifications': []}
        }
        
        result = kyc_crew.execute_with_reasoning(
            'classification',
            {'case_id': 'test_case', 'documents': []}
        )
        
        assert result['status'] == 'completed'
        mock_execute.assert_called_once()
    
    @patch.object(AutonomousExtractionAgent, 'execute')
    def test_execute_with_reasoning_extraction(self, mock_execute, kyc_crew):
        """Test executing extraction with reasoning."""
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {'extractions': []}
        }
        
        result = kyc_crew.execute_with_reasoning(
            'extraction',
            {'case_id': 'test_case', 'classifications': []}
        )
        
        assert result['status'] == 'completed'
        mock_execute.assert_called_once()
    
    def test_execute_with_invalid_task_type(self, kyc_crew):
        """Test error handling for invalid task type."""
        with pytest.raises(ValueError, match="Unknown task type"):
            kyc_crew.execute_with_reasoning(
                'invalid_type',
                {'case_id': 'test_case'}
            )


class TestHybridWorkflow:
    """Test hybrid workflow execution."""
    
    @patch.object(AutonomousIntakeAgent, 'execute')
    @patch.object(AutonomousClassificationAgent, 'execute')
    @patch.object(AutonomousExtractionAgent, 'execute')
    def test_kickoff_with_reasoning_full_pipeline(
        self, mock_extraction, mock_classification, mock_intake, kyc_crew
    ):
        """Test full pipeline with reasoning."""
        # Mock intake
        mock_intake.return_value = {
            'status': 'completed',
            'execution': {
                'validated_documents': [
                    {'document_id': 'doc1', 'file_path': '/path/to/doc1.pdf'}
                ]
            }
        }
        
        # Mock classification
        mock_classification.return_value = {
            'status': 'completed',
            'execution': {
                'classifications': [
                    {'document_id': 'doc1', 'predicted_class': 'identity_proof'}
                ]
            }
        }
        
        # Mock extraction
        mock_extraction.return_value = {
            'status': 'completed',
            'execution': {
                'extractions': [
                    {'document_id': 'doc1', 'extracted_data': {}}
                ]
            }
        }
        
        # Store data in shared memory for flow
        kyc_crew.shared_memory.store('validated_documents', [
            {'document_id': 'doc1', 'file_path': '/path/to/doc1.pdf'}
        ])
        
        result = kyc_crew.kickoff_with_reasoning(
            case_id='test_case',
            file_paths=['/path/to/doc1.pdf'],
            use_reasoning=True
        )
        
        assert result['case_id'] == 'test_case'
        assert 'stages' in result
        assert 'intake' in result['stages']
        
        # Verify all agents were called
        assert mock_intake.called
        assert mock_classification.called
        assert mock_extraction.called
    
    @patch.object(AutonomousIntakeAgent, 'execute')
    def test_kickoff_handles_intake_failure(self, mock_intake, kyc_crew):
        """Test workflow handles intake failure gracefully."""
        mock_intake.return_value = {
            'status': 'failed',
            'error': 'Intake failed'
        }
        
        result = kyc_crew.kickoff_with_reasoning(
            case_id='test_case',
            file_paths=['/path/to/doc1.pdf'],
            use_reasoning=True
        )
        
        # Should stop after intake failure
        assert 'stages' in result
        assert 'intake' in result['stages']
        assert result['stages']['intake']['status'] == 'failed'


class TestCrewFactory:
    """Test crew factory methods."""
    
    def test_create_standard_crew(self, mock_llm):
        """Test creating standard crew."""
        crew = KYCAMLCrewFactory.create_standard_crew(mock_llm)
        
        assert isinstance(crew, KYCAMLCrew)
        assert crew.llm is not None
    
    def test_create_intake_only_crew(self, mock_llm):
        """Test creating intake-only crew."""
        crew = KYCAMLCrewFactory.create_intake_only_crew(mock_llm)
        
        assert crew is not None
        # Crew should have intake agent
    
    def test_create_classification_only_crew(self, mock_llm):
        """Test creating classification-only crew."""
        crew = KYCAMLCrewFactory.create_classification_only_crew(mock_llm)
        
        assert crew is not None
    
    def test_create_extraction_only_crew(self, mock_llm):
        """Test creating extraction-only crew."""
        crew = KYCAMLCrewFactory.create_extraction_only_crew(mock_llm)
        
        assert crew is not None


class TestSharedMemoryIntegration:
    """Test shared memory integration with crew."""
    
    def test_shared_memory_accessible_to_agents(self, kyc_crew):
        """Test that shared memory is accessible to all agents."""
        # Store data
        kyc_crew.shared_memory.store('test_key', 'test_value')
        
        # All autonomous agents should have access
        assert kyc_crew.autonomous_intake.shared_memory is not None
        assert kyc_crew.autonomous_classifier.shared_memory is not None
        assert kyc_crew.autonomous_extractor.shared_memory is not None
    
    @patch.object(AutonomousIntakeAgent, 'execute')
    def test_data_flows_through_shared_memory(self, mock_execute, kyc_crew):
        """Test that data flows between stages via shared memory."""
        # Mock intake stores validated documents
        def side_effect(task, shared_memory):
            shared_memory.store('validated_documents', [
                {'document_id': 'doc1'}
            ])
            return {
                'status': 'completed',
                'execution': {'validated_documents': [{'document_id': 'doc1'}]}
            }
        
        mock_execute.side_effect = side_effect
        
        kyc_crew.execute_with_reasoning(
            'intake',
            {'case_id': 'test_case', 'file_paths': []}
        )
        
        # Check data is in shared memory
        validated_docs = kyc_crew.shared_memory.get('validated_documents')
        assert validated_docs is not None
        assert len(validated_docs) == 1
        assert validated_docs[0]['document_id'] == 'doc1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
