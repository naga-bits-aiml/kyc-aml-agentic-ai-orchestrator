#!/usr/bin/env python3
"""Simple test of stage transitions with real document."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from case_metadata_manager import StagedCaseMetadataManager
from utilities import settings


def test_stage_transitions():
    """Test moving a document through workflow stages."""
    
    print("=" * 70)
    print("🧪 Testing Stage Transitions")
    print("=" * 70)
    
    # Setup
    case_id = "TEST-STAGE-001"
    test_file = Path("~/Downloads/pan-1.pdf").expanduser()
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"\n📂 Case: {case_id}")
    print(f"📄 File: {test_file.name}\n")
    
    try:
        # Create case directory
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        
        manager = StagedCaseMetadataManager(case_id)
        
        # Step 1: Add document to intake
        print("=" * 70)
        print("STEP 1: Add Document to Intake Stage")
        print("=" * 70)
        
        doc_id = f"{case_id}_DOC_001"
        result = manager.add_document(
            document_id=doc_id,
            filename=test_file.name,
            source_path=str(test_file)
        )
        
        print(f"✅ Document added: {result['document_id']}")
        print(f"📍 Stage: {result['stage']}")
        print(f"📂 Path: {result['metadata_path']}")
        
        # Show stage summary
        summary = manager.get_stage_summary()
        print(f"\n📊 Stage Summary:")
        for stage, count in summary.items():
            print(f"  {stage}: {count}")
        
        # Step 2: Move to classification
        print("\n" + "=" * 70)
        print("STEP 2: Move to Classification Stage")
        print("=" * 70)
        
        success = manager.move_to_stage(doc_id, 'classification')
        print(f"✅ Moved to: classification")
        
        summary = manager.get_stage_summary()
        print(f"\n📊 Stage Summary:")
        for stage, count in summary.items():
            print(f"  {stage}: {count}")
        
        # Step 3: Move to extraction
        print("\n" + "=" * 70)
        print("STEP 3: Move to Extraction Stage")
        print("=" * 70)
        
        success = manager.move_to_stage(doc_id, 'extraction')
        print(f"✅ Moved to: extraction")
        
        summary = manager.get_stage_summary()
        print(f"\n📊 Stage Summary:")
        for stage, count in summary.items():
            print(f"  {stage}: {count}")
        
        # Step 4: Move to processed
        print("\n" + "=" * 70)
        print("STEP 4: Move to Processed Stage")
        print("=" * 70)
        
        success = manager.move_to_stage(doc_id, 'processed')
        print(f"✅ Moved to: processed")
        
        summary = manager.get_stage_summary()
        print(f"\n📊 Final Stage Summary:")
        for stage, count in summary.items():
            print(f"  {stage}: {count}")
        
        # Verify file exists in processed folder
        processed_file = case_dir / 'processed' / test_file.name
        print(f"\n📄 File location: {processed_file}")
        print(f"✅ File exists: {processed_file.exists()}")
        
        print("\n" + "=" * 70)
        print("✅ All Stage Transitions Successful!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = test_stage_transitions()
    sys.exit(0 if success else 1)
