"""Test suite for Flow-based orchestration pattern.

This module tests the new Flow-based workflow implementation,
ensuring proper event-driven execution and state management.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flows import (
    DocumentProcessingFlow,
    DocumentProcessingState,
    kickoff_flow,
    FLOW_AVAILABLE
)
from crew import KYCAMLCrew


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = Mock()
    llm.invoke = Mock(return_value=Mock(content='{"status": "completed"}'))
    return llm


@pytest.fixture
def flow_instance(mock_llm):
    """Create a DocumentProcessingFlow instance for testing."""
    if not FLOW_AVAILABLE:
        pytest.skip("CrewAI Flow not available")
    return DocumentProcessingFlow(llm=mock_llm)


class TestFlowState:
    """Test Flow state management."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = DocumentProcessingState()
        
        assert state.case_id == ""
        assert state.file_paths == []
        assert state.current_stage == "initialized"
        assert state.use_reasoning is True
        assert state.validated_documents == []
        assert state.classifications == []
        assert state.extractions == []
        assert state.total_documents == 0
        assert state.successful_documents == 0
        assert state.failed_documents == 0
        assert state.requires_review == 0
    
    def test_state_updates(self):
        """Test state updates work correctly."""
        state = DocumentProcessingState()
        
        state.case_id = "test_case_123"
        state.file_paths = ["/path/to/doc1.pdf", "/path/to/doc2.pdf"]
        state.current_stage = "intake"
        state.total_documents = 2
        
        assert state.case_id == "test_case_123"
        assert len(state.file_paths) == 2
        assert state.current_stage == "intake"
        assert state.total_documents == 2
    
    def test_state_with_documents(self):
        """Test state with document data."""
        state = DocumentProcessingState()
        
        state.validated_documents = [
            {'document_id': 'doc1', 'file_path': '/path/to/doc1.pdf'},
            {'document_id': 'doc2', 'file_path': '/path/to/doc2.pdf'}
        ]
        
        assert len(state.validated_documents) == 2
        assert state.validated_documents[0]['document_id'] == 'doc1'


class TestFlowInitialization:
    """Test Flow initialization."""
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_flow_initialization(self, mock_llm):
        """Test flow initializes correctly."""
        flow = DocumentProcessingFlow(llm=mock_llm)
        
        assert flow.llm is not None
        assert flow.crew is not None
        assert isinstance(flow.crew, KYCAMLCrew)
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_flow_has_state(self, flow_instance):
        """Test flow has state object."""
        assert hasattr(flow_instance, 'state')
        assert isinstance(flow_instance.state, DocumentProcessingState)


class TestFlowStages:
    """Test individual flow stages."""
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_intake_stage(self, mock_execute, flow_instance):
        """Test intake stage execution."""
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {
                'validated_documents': [
                    {'document_id': 'doc1', 'file_path': '/path/to/doc1.pdf'}
                ]
            }
        }
        
        flow_instance.state.case_id = "test_case"
        flow_instance.state.file_paths = ["/path/to/doc1.pdf"]
        
        flow_instance.intake_documents()
        
        assert flow_instance.state.current_stage == "intake"
        assert len(flow_instance.state.validated_documents) == 1
        assert flow_instance.state.total_documents == 1
        assert flow_instance.state.start_time is not None
        mock_execute.assert_called_once()
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_intake_stage_handles_failure(self, mock_execute, flow_instance):
        """Test intake stage handles failures."""
        mock_execute.return_value = {
            'status': 'failed',
            'error': 'Intake failed'
        }
        
        flow_instance.state.case_id = "test_case"
        flow_instance.state.file_paths = ["/path/to/doc1.pdf"]
        
        flow_instance.intake_documents()
        
        assert flow_instance.state.current_stage == "failed"
        assert len(flow_instance.state.errors) > 0
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_classification_stage(self, mock_execute, flow_instance):
        """Test classification stage execution."""
        # Setup state with validated documents
        flow_instance.state.case_id = "test_case"
        flow_instance.state.current_stage = "intake"
        flow_instance.state.validated_documents = [
            {'document_id': 'doc1', 'file_path': '/path/to/doc1.pdf'}
        ]
        
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {
                'classifications': [
                    {
                        'document_id': 'doc1',
                        'predicted_class': 'identity_proof',
                        'confidence_score': 0.95,
                        'requires_review': False
                    }
                ]
            }
        }
        
        flow_instance.classify_documents()
        
        assert flow_instance.state.current_stage == "classification"
        assert len(flow_instance.state.classifications) == 1
        assert flow_instance.state.requires_review == 0
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_classification_skips_if_no_documents(self, flow_instance):
        """Test classification skips if no validated documents."""
        flow_instance.state.current_stage = "intake"
        flow_instance.state.validated_documents = []
        
        flow_instance.classify_documents()
        
        # Should not update stage if no documents
        assert flow_instance.state.current_stage == "intake"
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_extraction_stage(self, mock_execute, flow_instance):
        """Test extraction stage execution."""
        # Setup state with classifications
        flow_instance.state.case_id = "test_case"
        flow_instance.state.current_stage = "classification"
        flow_instance.state.classifications = [
            {'document_id': 'doc1', 'predicted_class': 'identity_proof'}
        ]
        
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {
                'extractions': [
                    {
                        'document_id': 'doc1',
                        'extracted_data': {'name': 'John Doe'},
                        'extraction_quality': 0.9
                    }
                ]
            }
        }
        
        flow_instance.extract_data()
        
        assert flow_instance.state.current_stage == "extraction"
        assert len(flow_instance.state.extractions) == 1
        assert flow_instance.state.successful_documents == 1
        assert flow_instance.state.failed_documents == 0
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_extraction_counts_failures(self, mock_execute, flow_instance):
        """Test extraction correctly counts failed extractions."""
        flow_instance.state.current_stage = "classification"
        flow_instance.state.classifications = [
            {'document_id': 'doc1', 'predicted_class': 'identity_proof'},
            {'document_id': 'doc2', 'predicted_class': 'address_proof'}
        ]
        
        mock_execute.return_value = {
            'status': 'completed',
            'execution': {
                'extractions': [
                    {
                        'document_id': 'doc1',
                        'extracted_data': {'name': 'John Doe'},
                        'extraction_quality': 0.9  # Success
                    },
                    {
                        'document_id': 'doc2',
                        'extracted_data': {},
                        'extraction_quality': 0.3  # Failure
                    }
                ]
            }
        }
        
        flow_instance.extract_data()
        
        assert flow_instance.state.successful_documents == 1
        assert flow_instance.state.failed_documents == 1
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_finalize_workflow(self, flow_instance):
        """Test workflow finalization."""
        flow_instance.state.current_stage = "extraction"
        flow_instance.state.start_time = datetime.now()
        flow_instance.state.total_documents = 2
        flow_instance.state.successful_documents = 2
        flow_instance.state.failed_documents = 0
        
        flow_instance.finalize_workflow()
        
        assert flow_instance.state.current_stage == "completed"
        assert flow_instance.state.end_time is not None
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_finalize_with_review_required(self, flow_instance):
        """Test finalization when review is required."""
        flow_instance.state.current_stage = "extraction"
        flow_instance.state.start_time = datetime.now()
        flow_instance.state.requires_review = 1
        
        flow_instance.finalize_workflow()
        
        assert flow_instance.state.current_stage == "requires_review"


class TestFlowResults:
    """Test flow results generation."""
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_get_results_structure(self, flow_instance):
        """Test results have correct structure."""
        flow_instance.state.case_id = "test_case"
        flow_instance.state.start_time = datetime.now()
        flow_instance.state.end_time = datetime.now()
        flow_instance.state.current_stage = "completed"
        
        results = flow_instance.get_results()
        
        assert 'case_id' in results
        assert 'status' in results
        assert 'processing_time' in results
        assert 'documents' in results
        assert 'validated_documents' in results
        assert 'classifications' in results
        assert 'extractions' in results
        assert 'errors' in results
        assert 'timestamps' in results
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    def test_get_results_with_data(self, flow_instance):
        """Test results contain actual data."""
        flow_instance.state.case_id = "test_case"
        flow_instance.state.total_documents = 2
        flow_instance.state.successful_documents = 2
        flow_instance.state.validated_documents = [
            {'document_id': 'doc1'},
            {'document_id': 'doc2'}
        ]
        flow_instance.state.start_time = datetime.now()
        flow_instance.state.end_time = datetime.now()
        
        results = flow_instance.get_results()
        
        assert results['case_id'] == "test_case"
        assert results['documents']['total'] == 2
        assert results['documents']['successful'] == 2
        assert len(results['validated_documents']) == 2


class TestKickoffFlow:
    """Test the kickoff_flow convenience function."""
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(DocumentProcessingFlow, 'kickoff')
    def test_kickoff_flow_basic(self, mock_kickoff, mock_llm):
        """Test basic kickoff_flow execution."""
        result = kickoff_flow(
            case_id="test_case",
            file_paths=["/path/to/doc1.pdf"],
            llm=mock_llm,
            use_reasoning=True,
            visualize=False
        )
        
        mock_kickoff.assert_called_once()
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(DocumentProcessingFlow, 'plot')
    @patch.object(DocumentProcessingFlow, 'kickoff')
    def test_kickoff_flow_with_visualization(self, mock_kickoff, mock_plot, mock_llm):
        """Test kickoff_flow with visualization."""
        result = kickoff_flow(
            case_id="test_case",
            file_paths=["/path/to/doc1.pdf"],
            llm=mock_llm,
            use_reasoning=True,
            visualize=True
        )
        
        mock_plot.assert_called_once()
        mock_kickoff.assert_called_once()
    
    def test_kickoff_flow_fallback_when_not_available(self, mock_llm):
        """Test fallback when Flow is not available."""
        if FLOW_AVAILABLE:
            pytest.skip("Flow is available, can't test fallback")
        
        with patch.object(KYCAMLCrew, 'kickoff_with_reasoning') as mock_kickoff:
            mock_kickoff.return_value = {'status': 'completed'}
            
            result = kickoff_flow(
                case_id="test_case",
                file_paths=["/path/to/doc1.pdf"],
                llm=mock_llm,
                use_reasoning=True
            )
            
            mock_kickoff.assert_called_once()


class TestFlowEventDriven:
    """Test event-driven flow behavior."""
    
    @pytest.mark.skipif(not FLOW_AVAILABLE, reason="CrewAI Flow not available")
    @patch.object(KYCAMLCrew, 'execute_with_reasoning')
    def test_stages_execute_in_sequence(self, mock_execute, flow_instance):
        """Test that stages execute in proper sequence."""
        call_order = []
        
        def track_calls(task_type, params):
            call_order.append(task_type)
            if task_type == 'intake':
                flow_instance.state.validated_documents = [{'document_id': 'doc1'}]
                return {'status': 'completed', 'execution': {'validated_documents': [{'document_id': 'doc1'}]}}
            elif task_type == 'classification':
                flow_instance.state.classifications = [{'document_id': 'doc1'}]
                return {'status': 'completed', 'execution': {'classifications': [{'document_id': 'doc1'}]}}
            elif task_type == 'extraction':
                return {'status': 'completed', 'execution': {'extractions': [{'document_id': 'doc1'}]}}
        
        mock_execute.side_effect = track_calls
        
        flow_instance.state.case_id = "test_case"
        flow_instance.state.file_paths = ["/path/to/doc1.pdf"]
        
        # Execute stages manually (in real flow, @listen handles this)
        flow_instance.intake_documents()
        flow_instance.classify_documents()
        flow_instance.extract_data()
        
        assert call_order == ['intake', 'classification', 'extraction']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
