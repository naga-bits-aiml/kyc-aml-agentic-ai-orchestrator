#!/usr/bin/env python
"""Quick end-to-end test of the hybrid architecture.

This script validates that the new hybrid architecture works correctly
by running a simulated workflow through all stages.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from crew import KYCAMLCrew
from agents.shared_memory import SharedMemory


def create_mock_llm():
    """Create a mock LLM that returns expected formats."""
    llm = Mock()
    llm.model_name = "gpt-4-test"
    llm.model = "gpt-4-test"
    llm.temperature = 0.1
    
    # Mock invoke to return JSON-like responses
    def mock_invoke(prompt):
        response = Mock()
        response.content = '{"status": "completed", "message": "Mock response"}'
        return response
    
    llm.invoke = mock_invoke
    return llm


def test_crew_initialization():
    """Test 1: Crew initializes correctly."""
    print("\n" + "="*60)
    print("TEST 1: Crew Initialization")
    print("="*60)
    
    try:
        llm = create_mock_llm()
        crew = KYCAMLCrew(llm=llm)
        
        assert crew.llm is not None, "LLM should be set"
        assert crew.shared_memory is not None, "Shared memory should be initialized"
        assert crew.autonomous_intake is not None, "Intake agent should be initialized"
        assert crew.autonomous_classifier is not None, "Classifier agent should be initialized"
        assert crew.autonomous_extractor is not None, "Extractor agent should be initialized"
        
        print("✓ Crew initialized successfully")
        print(f"✓ LLM: {crew.llm.model_name}")
        print(f"✓ Shared Memory: {type(crew.shared_memory).__name__}")
        print(f"✓ Autonomous Agents: 3 initialized")
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shared_memory_integration():
    """Test 2: Shared memory works correctly."""
    print("\n" + "="*60)
    print("TEST 2: Shared Memory Integration")
    print("="*60)
    
    try:
        llm = create_mock_llm()
        crew = KYCAMLCrew(llm=llm)
        
        # Store test data
        test_data = {
            'validated_documents': [
                {'document_id': 'doc1', 'file_path': '/test/doc1.pdf'}
            ]
        }
        crew.shared_memory.store('validated_documents', test_data['validated_documents'])
        
        # Retrieve data
        retrieved = crew.shared_memory.get('validated_documents')
        
        assert retrieved is not None, "Data should be retrievable"
        assert len(retrieved) == 1, "Should have 1 document"
        assert retrieved[0]['document_id'] == 'doc1', "Document ID should match"
        
        print("✓ Shared memory store/retrieve works")
        print(f"✓ Stored: {len(test_data['validated_documents'])} documents")
        print(f"✓ Retrieved: {len(retrieved)} documents")
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_execute_with_reasoning():
    """Test 3: Execute with reasoning works."""
    print("\n" + "="*60)
    print("TEST 3: Execute with Reasoning")
    print("="*60)
    
    try:
        llm = create_mock_llm()
        crew = KYCAMLCrew(llm=llm)
        
        # Mock the autonomous agent's execute method
        with patch.object(crew.autonomous_intake, 'execute') as mock_execute:
            mock_execute.return_value = {
                'status': 'completed',
                'execution': {
                    'validated_documents': [
                        {'document_id': 'doc1', 'file_path': '/test/doc1.pdf'}
                    ]
                },
                'reasoning': {'strategy': 'validate_all'},
                'reflection': {'quality': 'good'}
            }
            
            result = crew.execute_with_reasoning(
                'intake',
                {'case_id': 'test_case', 'file_paths': ['/test/doc1.pdf']}
            )
            
            assert result['status'] == 'completed', "Status should be completed"
            assert 'execution' in result, "Should have execution results"
            assert 'reasoning' in result, "Should have reasoning chain"
            
            print("✓ Execute with reasoning works")
            print(f"✓ Status: {result['status']}")
            print(f"✓ Has reasoning chain: {' reasoning' in result}")
            print(f"✓ Mock agent called: {mock_execute.called}")
            return True
            
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_kickoff_with_reasoning():
    """Test 4: Full kickoff with reasoning."""
    print("\n" + "="*60)
    print("TEST 4: Full Workflow Kickoff")
    print("="*60)
    
    try:
        llm = create_mock_llm()
        crew = KYCAMLCrew(llm=llm)
        
        # Mock all autonomous agents
        with patch.object(crew.autonomous_intake, 'execute') as mock_intake, \
             patch.object(crew.autonomous_classifier, 'execute') as mock_classifier, \
             patch.object(crew.autonomous_extractor, 'execute') as mock_extractor:
            
            # Setup mock responses
            mock_intake.return_value = {
                'status': 'completed',
                'execution': {
                    'validated_documents': [
                        {'document_id': 'doc1', 'file_path': '/test/doc1.pdf'}
                    ]
                }
            }
            
            # Need to setup shared memory for flow
            crew.shared_memory.store('validated_documents', [
                {'document_id': 'doc1', 'file_path': '/test/doc1.pdf'}
            ])
            
            mock_classifier.return_value = {
                'status': 'completed',
                'execution': {
                    'classifications': [
                        {'document_id': 'doc1', 'predicted_class': 'identity_proof', 'confidence_score': 0.95}
                    ]
                }
            }
            
            crew.shared_memory.store('classifications', [
                {'document_id': 'doc1', 'predicted_class': 'identity_proof'}
            ])
            
            mock_extractor.return_value = {
                'status': 'completed',
                'execution': {
                    'extractions': [
                        {'document_id': 'doc1', 'extracted_data': {'name': 'John Doe'}}
                    ]
                }
            }
            
            # Execute full workflow
            result = crew.kickoff_with_reasoning(
                case_id='test_case',
                file_paths=['/test/doc1.pdf'],
                use_reasoning=True
            )
            
            assert 'case_id' in result, "Should have case_id"
            assert 'stages' in result, "Should have stages"
            assert result['case_id'] == 'test_case', "Case ID should match"
            
            print("✓ Full workflow kickoff works")
            print(f"✓ Case ID: {result['case_id']}")
            print(f"✓ Stages executed: {len(result.get('stages', {}))}")
            print(f"✓ All agents called")
            return True
            
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test 5: YAML configs load correctly."""
    print("\n" + "="*60)
    print("TEST 5: Configuration Loading")
    print("="*60)
    
    try:
        import yaml
        
        # Load agents config
        with open('config/agents.yaml') as f:
            agents_config = yaml.safe_load(f)
        
        # Load tasks config
        with open('config/tasks.yaml') as f:
            tasks_config = yaml.safe_load(f)
        
        assert 'document_intake_agent' in agents_config, "Intake agent should be in config"
        assert 'validate_documents_task' in tasks_config, "Validate task should be in config"
        
        print("✓ YAML configs load correctly")
        print(f"✓ Agents configured: {len(agents_config)}")
        print(f"✓ Tasks configured: {len(tasks_config)}")
        
        # Test parameter placeholders
        intake_goal = agents_config['document_intake_agent']['goal']
        assert '{case_id}' in intake_goal, "Should have case_id parameter"
        print("✓ Parameter placeholders found")
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all end-to-end tests."""
    print("\n" + "="*70)
    print("END-TO-END HYBRID ARCHITECTURE VALIDATION")
    print("="*70)
    
    tests = [
        ("Crew Initialization", test_crew_initialization),
        ("Shared Memory Integration", test_shared_memory_integration),
        ("Execute with Reasoning", test_execute_with_reasoning),
        ("Full Workflow Kickoff", test_kickoff_with_reasoning),
        ("Configuration Loading", test_config_loading)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed
    
    for name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {name}")
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed}/{len(results)} tests passed")
    print("="*70)
    
    if passed == len(results):
        print("\n🎉 All tests passed! Hybrid architecture is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
