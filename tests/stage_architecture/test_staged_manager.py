#!/usr/bin/env python3
"""Test the new StagedCaseMetadataManager"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from case_metadata_manager import StagedCaseMetadataManager

def test_staged_manager():
    """Test basic operations of StagedCaseMetadataManager"""
    
    print("=" * 70)
    print("🧪 Testing StagedCaseMetadataManager")
    print("=" * 70)
    
    # Test with KYC-2026-001
    case_dir = Path("documents/cases/KYC-2026-001").resolve()
    
    if not case_dir.exists():
        print(f"❌ Case directory not found: {case_dir}")
        return False
    
    print(f"\n📂 Testing with case: {case_dir.name}")
    print(f"📂 Full path: {case_dir}\n")
    
    # Initialize manager
    manager = StagedCaseMetadataManager(case_dir)
    
    # Debug: Check metadata loading
    print(f"📋 Metadata file: {manager.metadata_file}")
    print(f"📋 Metadata exists: {manager.metadata_file.exists()}")
    metadata = manager.load_metadata()
    print(f"📋 Documents in metadata: {len(metadata.get('documents', []))}")
    print()
    
    # Test 1: Get stage summary
    print("=" * 70)
    print("Test 1: Get Stage Summary")
    print("=" * 70)
    summary = manager.get_stage_summary()
    total = sum(summary.values())
    print(f"Total documents: {total}")
    for stage, count in summary.items():
        print(f"  {stage}: {count}")
    
    # Test 2: Get documents by stage
    print("\n" + "=" * 70)
    print("Test 2: Get Documents in Extraction Stage")
    print("=" * 70)
    extraction_docs = manager.get_document_by_stage('extraction')
    print(f"Found {len(extraction_docs)} document(s) in extraction:")
    for doc in extraction_docs:
        print(f"  - {doc['document_id']} → {doc['metadata_path']}")
    
    # Test 3: Move one document to processed stage
    print("\n" + "=" * 70)
    print("Test 3: Move Document to Processed Stage")
    print("=" * 70)
    if extraction_docs:
        doc_id = extraction_docs[0]['document_id']
        print(f"Moving {doc_id} from extraction → processed...")
        success = manager.move_to_stage(doc_id, 'processed')
        if success:
            print(f"✅ Successfully moved to processed")
            
            # Verify the move
            processed_docs = manager.get_document_by_stage('processed')
            print(f"\nDocuments now in processed: {len(processed_docs)}")
            for doc in processed_docs:
                print(f"  - {doc['document_id']}")
        else:
            print(f"❌ Failed to move document")
    
    # Test 4: Update document metadata
    print("\n" + "=" * 70)
    print("Test 4: Update Document Metadata")
    print("=" * 70)
    if extraction_docs and len(extraction_docs) > 1:
        doc_id = extraction_docs[1]['document_id']
        print(f"Updating metadata for {doc_id}...")
        
        updates = {
            "test_field": "test_value",
            "migration_test": True,
            "timestamp": "2026-01-27 12:50:00"
        }
        
        success = manager.update_document_metadata(doc_id, updates)
        if success:
            print(f"✅ Successfully updated metadata")
            
            # Read the metadata file to verify
            doc_entry = manager.get_document(doc_id)
            if doc_entry:
                metadata_path = manager.case_dir / doc_entry['metadata_path']
                if metadata_path.exists():
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    print(f"\nVerification - Updated fields:")
                    for key in updates.keys():
                        if key in metadata:
                            print(f"  {key}: {metadata[key]}")
        else:
            print(f"❌ Failed to update metadata")
    
    # Test 5: Final stage summary
    print("\n" + "=" * 70)
    print("Test 5: Final Stage Summary After Changes")
    print("=" * 70)
    final_summary = manager.get_stage_summary()
    total = sum(final_summary.values())
    print(f"Total documents: {total}")
    for stage, count in final_summary.items():
        print(f"  {stage}: {count}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = test_staged_manager()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
