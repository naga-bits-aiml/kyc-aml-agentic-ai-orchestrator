"""Test document ID lookup in chat interface."""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import but don't run main
from case_metadata_manager import CaseMetadataManager
from utilities import settings

def test_document_id_extraction():
    """Test document ID pattern matching."""
    import re
    
    print("=" * 80)
    print("Testing Document ID Pattern Matching")
    print("=" * 80)
    
    doc_id_pattern = r'(KYC-\d{4}-\d{3}_DOC_\d{3}\.(?:pdf|txt|jpg|jpeg|png))'
    
    test_inputs = [
        "process KYC-2026-001_DOC_001.pdf",
        "Can you process KYC-2026-001_DOC_002.pdf and KYC-2026-001_DOC_003.pdf?",
        "reprocess KYC-2026-001_DOC_001.pdf",
        "process documents",  # Should not match
        "KYC-2026-001_DOC_004.pdf needs reprocessing",
    ]
    
    for test_input in test_inputs:
        print(f"\nInput: \"{test_input}\"")
        matches = re.findall(doc_id_pattern, test_input, re.IGNORECASE)
        if matches:
            print(f"  ✅ Found {len(matches)} document ID(s): {matches}")
            
            # Try to resolve paths
            case_dir = Path(settings.documents_dir) / "cases" / "KYC-2026-001"
            for doc_id in matches:
                doc_path = case_dir / doc_id
                if doc_path.exists():
                    print(f"     → Resolved to: {doc_path}")
                else:
                    print(f"     → File not found: {doc_path}")
        else:
            print("  ℹ️  No document IDs found")
    
    print("\n" + "=" * 80)
    print("Testing Case Metadata Manager Integration")
    print("=" * 80)
    
    # Test case metadata manager
    case_id = "KYC-2026-001"
    manager = CaseMetadataManager(case_id)
    
    print(f"\n1. Syncing case metadata...")
    metadata = manager.sync_documents_from_directory()
    print(f"   ✅ Case: {metadata['case_reference']}")
    print(f"   ✅ Documents: {metadata['document_count']}")
    
    print(f"\n2. Getting pending documents...")
    pending = manager.get_pending_documents()
    print(f"   Found {len(pending)} pending document(s):")
    for doc in pending:
        print(f"      - {doc['document_id']} (status: {doc['status']})")
    
    print(f"\n3. Looking up specific document...")
    if pending:
        doc_id = pending[0]['document_id']
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        doc_path = case_dir / doc_id
        print(f"   Document ID: {doc_id}")
        print(f"   Path: {doc_path}")
        print(f"   Exists: {doc_path.exists()}")
        
        # Check metadata
        metadata_file = case_dir / f"{doc_id}.metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                doc_metadata = json.load(f)
            print(f"   Stored path: {doc_metadata.get('stored_path')}")
            print(f"   Status: {doc_metadata.get('status')}")
            print(f"   Extraction: {doc_metadata.get('extraction', {}).get('status')}")
            print(f"   Classification: {doc_metadata.get('classification', {}).get('status')}")
    
    print("\n" + "=" * 80)
    print("Test Complete! ✅")
    print("=" * 80)

if __name__ == "__main__":
    test_document_id_extraction()
