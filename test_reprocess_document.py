"""
Test to verify that reprocessing existing documents doesn't create duplicates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.intake_tools import batch_validate_documents_tool
from utilities import logger

def test_reprocess_existing_document():
    """Test that reprocessing an existing document reuses it instead of creating duplicate."""
    
    print("\n" + "="*80)
    print("TEST: Reprocess Existing Document - Should NOT Create Duplicate")
    print("="*80 + "\n")
    
    # Use the document that already exists
    existing_doc_path = "/Users/nagaad/Workspace_Project/kyc-aml-agentic-ai-orchestrator/documents/intake/DOC_20260128_003445_5BA56.jpg"
    
    if not Path(existing_doc_path).exists():
        print("❌ Test document doesn't exist. Using the document from your example:")
        existing_doc_path = "/Users/nagaad/Workspace_Project/kyc-aml-agentic-ai-orchestrator/documents/intake/DOC_20260127_213335_7953F_page1.jpg"
    
    print(f"Testing with document: {existing_doc_path}")
    print("-" * 80)
    
    # Try to validate/store it again
    result = batch_validate_documents_tool([existing_doc_path])
    
    print("\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Total: {result['total']}")
    print(f"  Valid: {result['valid']}")
    
    if result['validated_documents']:
        doc = result['validated_documents'][0]
        print(f"\n  Document ID: {doc['document_id']}")
        print(f"  Reused Existing: {doc.get('reused_existing', False)}")
        print(f"  Stored Path: {doc['stored_path']}")
    
    print("\n" + "="*80)
    
    if result['validated_documents'] and result['validated_documents'][0].get('reused_existing'):
        print("✅ TEST PASSED: Existing document was reused (no duplicate created)")
        print("   Check the logs above - you should see '♻️ EXISTING DOCUMENT REUSED'")
    else:
        print("⚠️  Document was processed as new (check if it truly exists)")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    test_reprocess_existing_document()
