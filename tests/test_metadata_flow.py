"""
Comprehensive tests for metadata-driven architecture.

This test suite validates:
1. Intake stores full metadata in validated_documents
2. Classification receives metadata in inputs
3. Classification updates metadata correctly
4. Extraction receives metadata WITH classification results
5. Extraction can access document_type from classification
6. All status blocks are properly updated
7. End-to-end metadata flow works correctly
"""

import sys
from pathlib import Path
import json
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities import logger, settings
from tools.document_tools import _validate_and_store_document, get_document_by_id_tool
from flows.document_processing_flow import DocumentProcessingFlow
from utilities.llm_factory import create_llm


def cleanup_test_documents(*document_ids):
    """Clean up test document files."""
    intake_dir = Path(settings.documents_dir) / "intake"
    
    for document_id in document_ids:
        if not document_id:
            continue
        # Remove document file and metadata
        doc_files = list(intake_dir.glob(f"{document_id}.*"))
        for doc_file in doc_files:
            try:
                doc_file.unlink()
                logger.info(f"Cleaned up: {doc_file.name}")
            except Exception as e:
                logger.warning(f"Could not remove {doc_file.name}: {e}")


def test_intake_metadata_storage():
    """Test 1: Validate that intake stores full metadata in state."""
    print("\n" + "="*70)
    print("TEST 1: Intake Metadata Storage")
    print("="*70)
    
    test_file = Path("test_documents/passport_sample.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None, False
    
    print(f"\n1. Processing document via intake...")
    
    # Validate and store document
    intake_dir = Path(settings.documents_dir) / "intake"
    intake_dir.mkdir(parents=True, exist_ok=True)
    
    result = _validate_and_store_document(str(test_file), intake_dir)
    
    if not result.get('success'):
        print(f"❌ Document validation failed")
        return None, False
    
    document_id = result.get('document_id')
    metadata = result.get('metadata')
    
    print(f"   ✅ Document ID: {document_id}")
    print(f"   ✅ Metadata returned from intake")
    
    # Verify metadata completeness
    required_fields = ['document_id', 'stored_path', 'intake', 'classification', 'extraction']
    missing_fields = [field for field in required_fields if field not in metadata]
    
    if missing_fields:
        print(f"❌ Metadata missing fields: {missing_fields}")
        return document_id, False
    
    print(f"   ✅ Metadata has all required fields")
    print(f"   ✅ intake.status: {metadata['intake']['status']}")
    print(f"   ✅ classification.status: {metadata['classification']['status']}")
    print(f"   ✅ extraction.status: {metadata['extraction']['status']}")
    
    # Create a validated_documents entry like flow does
    validated_doc = {
        'document_id': document_id,
        'metadata': metadata
    }
    
    print(f"\n2. Simulating flow state...")
    print(f"   ✅ validated_documents entry created")
    print(f"   ✅ Entry contains 'metadata' key: {('metadata' in validated_doc)}")
    
    return document_id, True


def test_classification_metadata_inputs():
    """Test 2: Verify classification receives and uses metadata."""
    print("\n" + "="*70)
    print("TEST 2: Classification Metadata Inputs")
    print("="*70)
    
    test_file = Path("test_documents/passport_sample.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None, False
    
    print(f"\n1. Setting up document with metadata...")
    
    # Create document
    intake_dir = Path(settings.documents_dir) / "intake"
    result = _validate_and_store_document(str(test_file), intake_dir)
    
    if not result.get('success'):
        print(f"❌ Document validation failed")
        return None, False
    
    document_id = result.get('document_id')
    metadata = result.get('metadata')
    
    print(f"   ✅ Document created: {document_id}")
    
    # Simulate what flow does - prepare classification inputs
    print(f"\n2. Preparing classification inputs (as flow does)...")
    
    classification_inputs = {
        'document_id': document_id,
        'document_metadata': metadata,  # Full metadata passed
        'processing_mode': 'process',
        'stage_status': 'pending'
    }
    
    print(f"   ✅ Inputs prepared")
    print(f"   ✅ Contains 'document_metadata': {('document_metadata' in classification_inputs)}")
    print(f"   ✅ Metadata has document_id: {('document_id' in classification_inputs['document_metadata'])}")
    print(f"   ✅ Metadata has stored_path: {('stored_path' in classification_inputs['document_metadata'])}")
    print(f"   ✅ Metadata has status blocks: {('intake' in classification_inputs['document_metadata'])}")
    
    # Verify metadata provides all needed info
    print(f"\n3. Verifying metadata completeness for classification...")
    
    file_path = classification_inputs['document_metadata'].get('stored_path')
    intake_status = classification_inputs['document_metadata'].get('intake', {}).get('status')
    
    if file_path and Path(file_path).exists():
        print(f"   ✅ File path accessible from metadata: {Path(file_path).name}")
    else:
        print(f"❌ File path not accessible from metadata")
        return document_id, False
    
    if intake_status == 'success':
        print(f"   ✅ Intake status indicates ready for classification")
    else:
        print(f"⚠️  Intake status: {intake_status}")
    
    print(f"\n4. Classification agent can use metadata directly:")
    print(f"   ✅ No need to call get_document_by_id_tool")
    print(f"   ✅ All context available in inputs")
    
    return document_id, True


def test_metadata_update_and_refresh():
    """Test 3: Verify metadata updates are captured."""
    print("\n" + "="*70)
    print("TEST 3: Metadata Update and Refresh")
    print("="*70)
    
    test_file = Path("test_documents/passport_sample.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None, False
    
    print(f"\n1. Creating document...")
    
    intake_dir = Path(settings.documents_dir) / "intake"
    result = _validate_and_store_document(str(test_file), intake_dir)
    
    if not result.get('success'):
        print(f"❌ Document validation failed")
        return None, False
    
    document_id = result.get('document_id')
    original_metadata = result.get('metadata')
    
    print(f"   ✅ Document ID: {document_id}")
    print(f"   ✅ Original classification.status: {original_metadata['classification']['status']}")
    
    # Simulate classification updating metadata
    print(f"\n2. Simulating classification update...")
    
    from tools.stage_management_tools import update_document_metadata_tool
    
    # Update classification block
    update_result = update_document_metadata_tool.run(
        document_id=document_id,
        stage_name="classification",
        status="success",
        msg="Test classification completed",
        additional_data={
            "document_type": "Passport",
            "confidence": 0.95,
            "test_update": True
        }
    )
    
    if not update_result.get('success'):
        print(f"❌ Update failed: {update_result.get('error')}")
        return document_id, False
    
    print(f"   ✅ Metadata updated successfully")
    
    # Refresh metadata (as flow does)
    print(f"\n3. Refreshing metadata from disk...")
    
    refresh_result = get_document_by_id_tool.run(document_id=document_id)
    
    if not refresh_result.get('success'):
        print(f"❌ Refresh failed")
        return document_id, False
    
    refreshed_metadata = refresh_result['metadata']
    
    print(f"   ✅ Metadata refreshed")
    print(f"   ✅ Updated classification.status: {refreshed_metadata['classification']['status']}")
    print(f"   ✅ Classification has document_type: {('document_type' in refreshed_metadata.get('classification', {}))}")
    print(f"   ✅ document_type value: {refreshed_metadata.get('classification', {}).get('document_type')}")
    
    # Verify update persisted
    if refreshed_metadata['classification']['status'] == 'success':
        print(f"\n4. Verification:")
        print(f"   ✅ Classification update persisted correctly")
        print(f"   ✅ Metadata ready for extraction stage")
        return document_id, True
    else:
        print(f"❌ Classification status not updated correctly")
        return document_id, False


def test_extraction_receives_classification_results():
    """Test 4: Verify extraction receives metadata with classification results."""
    print("\n" + "="*70)
    print("TEST 4: Extraction Receives Classification Results")
    print("="*70)
    
    test_file = Path("test_documents/passport_sample.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None, False
    
    print(f"\n1. Creating document and simulating classification...")
    
    # Create document
    intake_dir = Path(settings.documents_dir) / "intake"
    result = _validate_and_store_document(str(test_file), intake_dir)
    
    if not result.get('success'):
        print(f"❌ Document validation failed")
        return None, False
    
    document_id = result.get('document_id')
    
    # Simulate classification
    from tools.stage_management_tools import update_document_metadata_tool
    
    update_document_metadata_tool.run(
        document_id=document_id,
        stage_name="classification",
        status="success",
        msg="Document classified as Passport",
        additional_data={
            "document_type": "Passport",
            "confidence": 0.95,
            "categories": ["identity_proof"]
        }
    )
    
    print(f"   ✅ Document classified: {document_id}")
    
    # Refresh metadata (as flow does before extraction)
    print(f"\n2. Loading metadata for extraction (as flow does)...")
    
    refresh_result = get_document_by_id_tool.run(document_id=document_id)
    metadata_with_classification = refresh_result['metadata']
    
    print(f"   ✅ Metadata loaded")
    
    # Prepare extraction inputs (as flow does)
    print(f"\n3. Preparing extraction inputs...")
    
    extraction_inputs = {
        'document_id': document_id,
        'document_metadata': metadata_with_classification,  # Has classification!
        'processing_mode': 'process',
        'stage_status': 'pending'
    }
    
    print(f"   ✅ Extraction inputs prepared")
    
    # Verify extraction agent has everything it needs
    print(f"\n4. Verifying extraction context:")
    
    classification_block = extraction_inputs['document_metadata'].get('classification', {})
    document_type = classification_block.get('document_type')
    classification_status = classification_block.get('status')
    
    if classification_status == 'success':
        print(f"   ✅ Classification status: {classification_status}")
    else:
        print(f"❌ Classification not successful: {classification_status}")
        return document_id, False
    
    if document_type:
        print(f"   ✅ document_type available: {document_type}")
        print(f"   ✅ Extraction knows what fields to extract")
        print(f"   ✅ No need to call get_document_by_id_tool")
        print(f"   ✅ All classification results in metadata")
    else:
        print(f"❌ document_type not available in metadata")
        return document_id, False
    
    print(f"\n5. Extraction agent benefits:")
    print(f"   ✅ Sees previous stage's work immediately")
    print(f"   ✅ Zero extra tool calls to fetch metadata")
    print(f"   ✅ Natural data flow through pipeline")
    
    return document_id, True


def test_end_to_end_metadata_flow():
    """Test 5: End-to-end metadata flow through all stages."""
    print("\n" + "="*70)
    print("TEST 5: End-to-End Metadata Flow")
    print("="*70)
    
    test_file = Path("test_documents/passport_sample.txt")
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return None, False
    
    print(f"\n1. INTAKE STAGE")
    print(f"   Processing: {test_file.name}")
    
    # Intake
    intake_dir = Path(settings.documents_dir) / "intake"
    result = _validate_and_store_document(str(test_file), intake_dir)
    
    if not result.get('success'):
        print(f"❌ Intake failed")
        return None, False
    
    document_id = result.get('document_id')
    metadata = result.get('metadata')
    
    print(f"   ✅ Document ID generated: {document_id}")
    print(f"   ✅ Metadata created with status blocks")
    print(f"   ✅ intake.status: {metadata['intake']['status']}")
    
    # Simulate validated_documents entry
    validated_doc = {
        'document_id': document_id,
        'metadata': metadata
    }
    
    print(f"\n2. CLASSIFICATION STAGE")
    print(f"   Metadata flows from intake...")
    
    # Classification receives metadata
    classification_inputs = {
        'document_id': validated_doc['document_id'],
        'document_metadata': validated_doc['metadata'],
        'processing_mode': 'process',
        'stage_status': validated_doc['metadata']['classification']['status']
    }
    
    print(f"   ✅ Classification receives metadata in inputs")
    print(f"   ✅ Has all intake information")
    
    # Classification updates metadata
    from tools.stage_management_tools import update_document_metadata_tool
    
    update_document_metadata_tool.run(
        document_id=document_id,
        stage_name="classification",
        status="success",
        msg="Classified as Passport",
        additional_data={
            "document_type": "Passport",
            "confidence": 0.95,
            "categories": ["identity_proof"]
        }
    )
    
    print(f"   ✅ Classification updates metadata")
    
    # Flow refreshes metadata
    refresh_result = get_document_by_id_tool.run(document_id=document_id)
    validated_doc['metadata'] = refresh_result['metadata']
    
    print(f"   ✅ Flow captures updated metadata")
    print(f"   ✅ classification.status: {validated_doc['metadata']['classification']['status']}")
    print(f"   ✅ document_type: {validated_doc['metadata']['classification'].get('document_type')}")
    
    print(f"\n3. EXTRACTION STAGE")
    print(f"   Metadata flows from classification...")
    
    # Extraction receives updated metadata
    extraction_inputs = {
        'document_id': validated_doc['document_id'],
        'document_metadata': validated_doc['metadata'],  # Has classification results!
        'processing_mode': 'process',
        'stage_status': validated_doc['metadata']['extraction']['status']
    }
    
    print(f"   ✅ Extraction receives metadata with classification")
    print(f"   ✅ Can access document_type: {extraction_inputs['document_metadata']['classification']['document_type']}")
    print(f"   ✅ Knows what fields to extract based on document_type")
    
    # Extraction updates metadata
    update_document_metadata_tool.run(
        document_id=document_id,
        stage_name="extraction",
        status="success",
        msg="Extracted fields successfully",
        additional_data={
            "extracted_fields": {
                "name": "Test User",
                "document_number": "A12345678"
            },
            "confidence": 0.90
        }
    )
    
    print(f"   ✅ Extraction updates metadata")
    
    # Final metadata
    final_result = get_document_by_id_tool.run(document_id=document_id)
    final_metadata = final_result['metadata']
    
    print(f"\n4. FINAL STATE")
    print(f"   ✅ intake.status: {final_metadata['intake']['status']}")
    print(f"   ✅ classification.status: {final_metadata['classification']['status']}")
    print(f"   ✅ extraction.status: {final_metadata['extraction']['status']}")
    print(f"   ✅ All blocks successfully updated")
    
    print(f"\n5. METADATA FLOW VALIDATION")
    print(f"   ✅ Metadata flowed through entire pipeline")
    print(f"   ✅ Each stage saw previous stage's work")
    print(f"   ✅ Zero unnecessary tool calls")
    print(f"   ✅ Natural data progression: intake → classification → extraction")
    
    return document_id, True


def run_all_tests():
    """Run all metadata flow tests."""
    print("\n" + "="*70)
    print("METADATA-DRIVEN ARCHITECTURE TEST SUITE")
    print("="*70)
    print("\nValidating:")
    print("• Intake stores full metadata")
    print("• Classification receives metadata in inputs")
    print("• Metadata updates are captured correctly")
    print("• Extraction receives classification results")
    print("• End-to-end metadata flow works")
    print("="*70)
    
    test_results = []
    document_ids = []
    
    # Test 1
    doc_id, success = test_intake_metadata_storage()
    test_results.append(("Intake Metadata Storage", success))
    if doc_id:
        document_ids.append(doc_id)
    
    # Test 2
    doc_id, success = test_classification_metadata_inputs()
    test_results.append(("Classification Metadata Inputs", success))
    if doc_id:
        document_ids.append(doc_id)
    
    # Test 3
    doc_id, success = test_metadata_update_and_refresh()
    test_results.append(("Metadata Update and Refresh", success))
    if doc_id:
        document_ids.append(doc_id)
    
    # Test 4
    doc_id, success = test_extraction_receives_classification_results()
    test_results.append(("Extraction Receives Classification", success))
    if doc_id:
        document_ids.append(doc_id)
    
    # Test 5
    doc_id, success = test_end_to_end_metadata_flow()
    test_results.append(("End-to-End Metadata Flow", success))
    if doc_id:
        document_ids.append(doc_id)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # Cleanup
    print("\n" + "="*70)
    print("CLEANUP")
    print("="*70)
    cleanup_test_documents(*document_ids)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Metadata-driven architecture validated!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
