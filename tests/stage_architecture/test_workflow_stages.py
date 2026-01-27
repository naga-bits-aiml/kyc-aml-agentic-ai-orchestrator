#!/usr/bin/env python3
"""Test the full workflow with stage-based architecture."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from crew import KYCAMLCrew
from utilities.llm_factory import create_llm


def test_full_workflow_with_stages():
    """Test document processing with automatic stage transitions."""
    
    print("=" * 70)
    print("🧪 Testing Full Workflow with Stage Management")
    print("=" * 70)
    
    # Test parameters
    case_id = "TEST-STAGE-WORKFLOW"
    test_file = Path("~/Downloads/pan-1.pdf").expanduser()
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        print("Please ensure the PAN card file exists")
        return False
    
    print(f"\n📂 Test Case: {case_id}")
    print(f"📄 Test File: {test_file.name}\n")
    
    try:
        # Initialize LLM and crew
        print("Initializing crew with Gemini 2.0 Flash...")
        llm = create_llm()
        crew_instance = KYCAMLCrew(llm=llm)
        
        # Step 1: Intake (documents go to intake stage)
        print("\n" + "=" * 70)
        print("STEP 1: Document Intake")
        print("=" * 70)
        
        intake_crew = crew_instance.intake_crew()
        intake_result = intake_crew.kickoff(inputs={
            'case_id': case_id,
            'file_paths': [str(test_file)]
        })
        
        print("\n✅ Intake Complete")
        print(f"Validated Documents: {len(intake_result.get('validated_documents', []))}")
        
        # Check stage
        from tools.stage_management_tools import get_stage_summary
        summary = get_stage_summary(case_id)
        print(f"\nStage Summary:")
        print(f"  Intake: {summary['stages']['intake']}")
        print(f"  Classification: {summary['stages']['classification']}")
        print(f"  Extraction: {summary['stages']['extraction']}")
        print(f"  Processed: {summary['stages']['processed']}")
        
        # Step 2: Classification (documents move to classification stage)
        print("\n" + "=" * 70)
        print("STEP 2: Document Classification")
        print("=" * 70)
        
        classification_crew = crew_instance.classification_crew()
        classification_result = classification_crew.kickoff(inputs={
            'case_id': case_id,
            'documents': intake_result.get('validated_documents', [])
        })
        
        print("\n✅ Classification Complete")
        classifications = classification_result.get('classifications', [])
        print(f"Classified Documents: {len(classifications)}")
        
        if classifications:
            for doc in classifications:
                classification = doc.get('classification', {})
                print(f"\n  Document: {Path(doc.get('file_path', '')).name}")
                print(f"  Type: {classification.get('type', 'unknown')}")
                print(f"  Category: {classification.get('category', 'unknown')}")
                print(f"  Confidence: {classification.get('confidence', 0):.2%}")
        
        # Check stage after classification
        summary = get_stage_summary(case_id)
        print(f"\nStage Summary After Classification:")
        print(f"  Intake: {summary['stages']['intake']}")
        print(f"  Classification: {summary['stages']['classification']}")
        print(f"  Extraction: {summary['stages']['extraction']}")
        print(f"  Processed: {summary['stages']['processed']}")
        
        # Step 3: Extraction (documents move to extraction stage)
        print("\n" + "=" * 70)
        print("STEP 3: Data Extraction")
        print("=" * 70)
        
        extraction_crew = crew_instance.extraction_crew()
        extraction_result = extraction_crew.kickoff(inputs={
            'case_id': case_id,
            'classifications': classifications
        })
        
        print("\n✅ Extraction Complete")
        extractions = extraction_result.get('extractions', [])
        print(f"Extracted Documents: {len(extractions)}")
        
        if extractions:
            for doc in extractions:
                print(f"\n  Document: {Path(doc.get('file_path', '')).name}")
                print(f"  Quality: {doc.get('extraction_quality', 0):.2%}")
                print(f"  Method: {doc.get('extraction_method', 'unknown')}")
        
        # Final stage summary
        summary = get_stage_summary(case_id)
        print(f"\n" + "=" * 70)
        print("FINAL STAGE SUMMARY")
        print("=" * 70)
        print(f"  Intake: {summary['stages']['intake']}")
        print(f"  Classification: {summary['stages']['classification']}")
        print(f"  Extraction: {summary['stages']['extraction']}")
        print(f"  Processed: {summary['stages']['processed']}")
        print(f"\n  Total Documents: {summary['total_documents']}")
        
        print("\n" + "=" * 70)
        print("✅ Full Workflow Test Complete!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_full_workflow_with_stages()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
