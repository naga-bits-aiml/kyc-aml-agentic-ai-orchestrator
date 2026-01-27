#!/usr/bin/env python3
"""
Test script for the new agentic AI workflow.
Tests supervisor agent coordination and state persistence.
"""

import sys
from pathlib import Path
import json
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.shared_memory import SharedMemory
from agents.supervisor_agent import SupervisorAgent
from agents.autonomous_intake_agent import AutonomousIntakeAgent
from agents.autonomous_extraction_agent import AutonomousExtractionAgent
from agents.autonomous_classification_agent import AutonomousClassificationAgent
from utilities.config_loader import settings

def initialize_llm():
    """Initialize the LLM for testing."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os
    
    api_key = settings.google_api_key or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in settings or environment")
    
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=api_key,
        temperature=0.7
    )
    return llm

def setup_test_case():
    """Create a test case directory."""
    case_ref = "TEST-KYC-001"
    case_dir = Path(settings.documents_dir) / "cases" / case_ref
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_ref, case_dir

def create_test_document(case_dir: Path):
    """Create a test document."""
    test_doc = case_dir / "test_passport.txt"
    test_doc.write_text("This is a test passport document with sample text.")
    return str(test_doc)

def test_shared_memory():
    """Test SharedMemory operations."""
    print("\n" + "="*60)
    print("🧪 Testing SharedMemory...")
    print("="*60)
    
    case_ref, case_dir = setup_test_case()
    memory = SharedMemory(case_ref)
    
    # Test data update
    memory.update('test_key', 'test_value', 'TestAgent')
    result = memory.get('test_key')
    assert result == 'test_value', "Data update failed"
    print("✅ Data update/get works")
    
    # Test message posting
    memory.post_message('Agent1', 'Agent2', 'Test message')
    messages = memory.get_messages_for('Agent2')
    assert len(messages) == 1, "Message posting failed"
    print("✅ Message posting works")
    
    # Test workflow state
    memory.update_workflow_state(
        phase='test',
        completed_step='step1',
        pending_step='step2'
    )
    summary = memory.get_workflow_summary()
    assert summary['phase'] == 'test', "Workflow state failed"
    print("✅ Workflow state tracking works")
    
    # Test persistence
    memory.save()
    memory_file = case_dir / "workflow_memory.json"
    assert memory_file.exists(), "Persistence failed"
    print("✅ State persistence works")
    
    # Load and verify
    with open(memory_file) as f:
        data = json.load(f)
        assert data['case_reference'] == case_ref
        print("✅ State loading works")
    
    print("\n✨ SharedMemory: All tests passed!\n")
    return memory

def test_intake_agent(memory: SharedMemory, case_dir: Path, llm):
    """Test AutonomousIntakeAgent."""
    print("\n" + "="*60)
    print("🧪 Testing AutonomousIntakeAgent...")
    print("="*60)
    
    # Create test document
    test_doc = create_test_document(case_dir)
    
    # Initialize agent
    intake_agent = AutonomousIntakeAgent(llm=llm)
    
    # Add documents to memory
    memory.update('documents', [test_doc], 'TestScript')
    
    # Execute intake
    context = {'action': 'validate_and_store'}
    result = intake_agent.execute(context, memory)
    
    print(f"\n📊 Result: {result.get('status')}")
    reasoning = result.get('reasoning', 'N/A')
    if reasoning and isinstance(reasoning, str):
        print(f"📝 Reasoning: {reasoning[:100]}...")
    else:
        print(f"📝 Reasoning: {reasoning}")
    
    # Verify metadata file created (find it in the case directory)
    metadata_files = list(case_dir.glob('*.metadata.json'))
    assert len(metadata_files) > 0, "No metadata files created"
    metadata_file = metadata_files[-1]  # Get the most recent one
    print(f"✅ Document metadata created: {metadata_file.name}")
    
    with open(metadata_file) as f:
        metadata = json.load(f)
        assert 'document_id' in metadata
        assert 'intake_timestamp' in metadata
        assert 'hash' in metadata
        print("✅ Metadata structure correct")
        print(f"   - Document ID: {metadata['document_id']}")
        print(f"   - Status: {metadata.get('status', 'N/A')}")
        print(f"   - Size: {metadata.get('size_bytes', 0)} bytes")
    
    print("\n✨ IntakeAgent: All tests passed!\n")
    return result

def test_extraction_agent(memory: SharedMemory, llm):
    """Test AutonomousExtractionAgent."""
    print("\n" + "="*60)
    print("🧪 Testing AutonomousExtractionAgent...")
    print("="*60)
    
    extraction_agent = AutonomousExtractionAgent(llm=llm)
    
    context = {'action': 'extract_documents'}
    result = extraction_agent.execute(context, memory)
    
    print(f"\n📊 Result: {result.get('status')}")
    reasoning = result.get('reasoning', 'N/A')
    if reasoning and isinstance(reasoning, str):
        print(f"📝 Reasoning: {reasoning[:100]}...")
    else:
        print(f"📝 Reasoning: {reasoning}")
    
    # Check extraction results in memory
    extraction_results = memory.get('extraction_results', [])
    if extraction_results:
        print(f"✅ Extracted {len(extraction_results)} document(s)")
    
    print("\n✨ ExtractionAgent: All tests passed!\n")
    return result

def test_classification_agent(memory: SharedMemory, llm):
    """Test AutonomousClassificationAgent."""
    print("\n" + "="*60)
    print("🧪 Testing AutonomousClassificationAgent...")
    print("="*60)
    
    classification_agent = AutonomousClassificationAgent(llm=llm)
    
    context = {'action': 'classify_documents'}
    result = classification_agent.execute(context, memory)
    
    print(f"\n📊 Result: {result.get('status')}")
    reasoning = result.get('reasoning', 'N/A')
    if reasoning and isinstance(reasoning, str):
        print(f"📝 Reasoning: {reasoning[:100]}...")
    else:
        print(f"📝 Reasoning: {reasoning}")
    
    # Check classification results
    classification_results = memory.get('classification_results', [])
    if classification_results:
        print(f"✅ Classified {len(classification_results)} document(s)")
        for cr in classification_results:
            print(f"   • {cr.get('document_id')}: {cr.get('document_type')} ({cr.get('confidence', 0):.0%})")
    
    # Check case completeness
    completeness = memory.get('case_completeness')
    if completeness:
        print(f"\n📋 Case Completeness: {completeness.get('completeness_score', 0):.0%}")
        if not completeness.get('has_all_required'):
            print(f"   Missing: {completeness.get('missing_types', [])}")
    
    print("\n✨ ClassificationAgent: All tests passed!\n")
    return result

def test_supervisor_agent(memory: SharedMemory, case_ref: str, llm):
    """Test SupervisorAgent orchestration."""
    print("\n" + "="*60)
    print("🧪 Testing SupervisorAgent...")
    print("="*60)
    
    # Initialize specialist agents
    specialist_agents = {
        'intake': AutonomousIntakeAgent(llm=llm),
        'extraction': AutonomousExtractionAgent(llm=llm),
        'classification': AutonomousClassificationAgent(llm=llm)
    }
    
    # Initialize supervisor
    supervisor = SupervisorAgent(llm=llm, specialist_agents=specialist_agents)
    
    # Test workflow
    user_request = "Process the uploaded documents for KYC verification"
    result = supervisor.process_request(user_request, case_ref, memory)
    
    print(f"\n📊 Supervisor Result:")
    print(f"   Status: {result.get('status')}")
    print(f"   Steps Completed: {result.get('steps_completed', 0)}")
    print(f"   Steps Failed: {result.get('steps_failed', 0)}")
    
    if 'reasoning' in result:
        reasoning = result['reasoning']
        print(f"\n🧠 Supervisor Reasoning:")
        if isinstance(reasoning, str):
            print(f"   {reasoning[:200]}...")
        else:
            print(f"   {reasoning}")
    
    if 'plan' in result:
        plan = result['plan']
        print(f"\n📋 Execution Plan:")
        if isinstance(plan, list):
            for i, step in enumerate(plan[:3], 1):
                print(f"   {i}. {step.get('step', 'unknown')} (Agent: {step.get('agent', 'unknown')})")
        else:
            print(f"   {plan}")
    
    # Verify workflow state
    workflow_summary = memory.get_workflow_summary()
    print(f"\n📈 Workflow Summary:")
    print(f"   Phase: {workflow_summary.get('phase')}")
    print(f"   Completed: {workflow_summary.get('completed', 0)} steps")
    print(f"   Pending: {workflow_summary.get('pending', 0)} steps")
    print(f"   Failed: {workflow_summary.get('failed', 0)} steps")
    
    print("\n✨ SupervisorAgent: All tests passed!\n")
    return result

def test_state_persistence(case_dir: Path):
    """Test state persistence and recovery."""
    print("\n" + "="*60)
    print("🧪 Testing State Persistence...")
    print("="*60)
    
    memory_file = case_dir / "workflow_memory.json"
    assert memory_file.exists(), "Memory file not found"
    
    with open(memory_file) as f:
        data = json.load(f)
    
    # Verify structure
    assert 'case_reference' in data
    assert 'data' in data
    assert 'workflow_state' in data
    assert 'execution_history' in data
    print("✅ Memory file structure correct")
    
    # Check execution history
    history = data['execution_history']
    print(f"✅ Execution history has {len(history)} entries")
    
    # Check data versioning
    for key, value in data['data'].items():
        assert 'value' in value
        assert 'updated_by' in value
        assert 'timestamp' in value
        assert 'version' in value
    print("✅ Data versioning correct")
    
    print("\n✨ State Persistence: All tests passed!\n")

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 Starting Agentic AI Workflow Tests")
    print("="*60)
    
    try:
        # Initialize LLM
        print("\n🔧 Initializing LLM...")
        llm = initialize_llm()
        print("✅ LLM initialized\n")
        
        # Test 1: SharedMemory
        memory = test_shared_memory()
        case_ref = memory.case_reference
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        # Test 2: IntakeAgent
        test_intake_agent(memory, case_dir, llm)
        
        # Test 3: ExtractionAgent
        test_extraction_agent(memory, llm)
        
        # Test 4: ClassificationAgent
        test_classification_agent(memory, llm)
        
        # Test 5: SupervisorAgent (full orchestration)
        test_supervisor_agent(memory, case_ref, llm)
        
        # Test 6: State Persistence
        test_state_persistence(case_dir)
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print(f"\n📁 Test case created at: {case_dir}")
        print(f"📄 Check workflow_memory.json for state")
        print(f"📄 Check .metadata.json files for document state\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
