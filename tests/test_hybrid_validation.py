"""Quick validation test for hybrid architecture.

This test validates the basic structure and configuration of the new hybrid architecture
without needing full LLM initialization.
"""

import sys
from pathlib import Path
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_yaml_configs_exist():
    """Test that YAML configuration files exist."""
    print("✓ Checking YAML configuration files...")
    
    agents_config = Path('config/agents.yaml')
    tasks_config = Path('config/tasks.yaml')
    
    assert agents_config.exists(), "config/agents.yaml must exist"
    assert tasks_config.exists(), "config/tasks.yaml must exist"
    
    print("  ✓ agents.yaml exists")
    print("  ✓ tasks.yaml exists")


def test_agents_yaml_structure():
    """Test agents.yaml has correct structure."""
    print("\n✓ Validating agents.yaml structure...")
    
    with open('config/agents.yaml') as f:
        agents = yaml.safe_load(f)
    
    # Only need the basic CrewAI agents - autonomous agents are Python classes
    required_agents = [
        'document_intake_agent',
        'document_classifier_agent',
        'document_extraction_agent',
        'supervisor_agent'
    ]
    
    for agent_name in required_agents:
        assert agent_name in agents, f"{agent_name} must be in agents.yaml"
        agent_config = agents[agent_name]
        assert 'role' in agent_config, f"{agent_name} must have 'role'"
        assert 'goal' in agent_config, f"{agent_name} must have 'goal'"
        assert 'backstory' in agent_config, f"{agent_name} must have 'backstory'"
        print(f"  ✓ {agent_name} configured correctly")


def test_tasks_yaml_structure():
    """Test tasks.yaml has correct structure."""
    print("\n✓ Validating tasks.yaml structure...")
    
    with open('config/tasks.yaml') as f:
        tasks = yaml.safe_load(f)
    
    required_tasks = [
        'validate_documents_task',
        'classify_documents_task',
        'extract_document_data_task',
        'orchestrate_workflow_task'
    ]
    
    for task_name in required_tasks:
        assert task_name in tasks, f"{task_name} must be in tasks.yaml"
        task_config = tasks[task_name]
        assert 'description' in task_config, f"{task_name} must have 'description'"
        assert 'expected_output' in task_config, f"{task_name} must have 'expected_output'"
        assert 'agent' in task_config, f"{task_name} must have 'agent'"
        print(f"  ✓ {task_name} configured correctly")


def test_crew_file_exists():
    """Test crew.py exists and can be imported."""
    print("\n✓ Validating crew.py...")
    
    crew_file = Path('crew.py')
    assert crew_file.exists(), "crew.py must exist"
    print("  ✓ crew.py exists")
    
    # Try to import (without initializing which requires LLM)
    try:
        import crew
        assert hasattr(crew, 'KYCAMLCrew'), "KYCAMLCrew class must exist"
        assert hasattr(crew, 'KYCAMLCrewFactory'), "KYCAMLCrewFactory class must exist"
        print("  ✓ KYCAMLCrew class exists")
        print("  ✓ KYCAMLCrewFactory class exists")
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        raise


def test_flow_files_exist():
    """Test flow files exist."""
    print("\n✓ Validating flow files...")
    
    flow_dir = Path('flows')
    assert flow_dir.exists(), "flows/ directory must exist"
    print("  ✓ flows/ directory exists")
    
    flow_file = flow_dir / 'document_processing_flow.py'
    assert flow_file.exists(), "document_processing_flow.py must exist"
    print("  ✓ document_processing_flow.py exists")
    
    init_file = flow_dir / '__init__.py'
    assert init_file.exists(), "flows/__init__.py must exist"
    print("  ✓ flows/__init__.py exists")
    
    # Try to import
    try:
        from flows import DocumentProcessingFlow, DocumentProcessingState, kickoff_flow
        print("  ✓ Flow classes imported successfully")
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        raise


def test_hybrid_adapter_exists():
    """Test hybrid adapter exists."""
    print("\n✓ Validating hybrid adapter...")
    
    adapter_file = Path('agents/hybrid_adapter.py')
    assert adapter_file.exists(), "agents/hybrid_adapter.py must exist"
    print("  ✓ hybrid_adapter.py exists")
    
    try:
        from agents.hybrid_adapter import ReasoningAgentAdapter, HybridAgentFactory
        print("  ✓ Adapter classes imported successfully")
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        raise


def test_main_updated():
    """Test main.py has been updated with flow support."""
    print("\n✓ Validating main.py updates...")
    
    main_file = Path('main.py')
    assert main_file.exists(), "main.py must exist"
    
    with open(main_file) as f:
        content = f.read()
    
    # Check for key additions
    assert 'from flows import' in content, "main.py must import flows"
    assert 'process_with_flow' in content, "main.py must have process_with_flow function"
    assert '--use-flow' in content, "main.py must support --use-flow argument"
    assert 'kickoff_flow' in content, "main.py must use kickoff_flow"
    
    print("  ✓ Flow imports present")
    print("  ✓ process_with_flow function present")
    print("  ✓ --use-flow argument present")
    print("  ✓ kickoff_flow call present")


def run_all_tests():
    """Run all validation tests."""
    print("="*60)
    print("HYBRID ARCHITECTURE VALIDATION")
    print("="*60)
    
    tests = [
        test_yaml_configs_exist,
        test_agents_yaml_structure,
        test_tasks_yaml_structure,
        test_crew_file_exists,
        test_flow_files_exist,
        test_hybrid_adapter_exists,
        test_main_updated
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAILED: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
