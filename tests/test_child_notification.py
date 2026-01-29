"""
Test child document notification after parent processing.
"""

from pathlib import Path
from utilities.queue_manager import DocumentQueue
from utilities import settings


def test_child_notification():
    """Test that child documents trigger notification."""
    print("\n" + "="*70)
    print("TESTING CHILD DOCUMENT NOTIFICATION")
    print("="*70 + "\n")
    
    # Initialize queue
    queue = DocumentQueue()
    
    # Simulate child documents being queued
    print("1. Simulating PDF conversion creating 3 child documents...")
    
    # Create fake child document IDs
    child_ids = ["DOC_CHILD_TEST_001", "DOC_CHILD_TEST_002", "DOC_CHILD_TEST_003"]
    parent_id = "DOC_PARENT_TEST_123"
    
    # We need actual files for the queue to work, so let's check if there are real child docs
    intake_dir = Path(settings.documents_dir) / "intake"
    
    # Find any existing child documents
    existing_children = []
    if intake_dir.exists():
        for metadata_file in intake_dir.glob("*.metadata.json"):
            try:
                import json
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                if metadata.get('generated_from_pdf'):
                    doc_id = metadata['document_id']
                    parent = metadata.get('source_document_id', 'UNKNOWN')
                    existing_children.append({
                        'doc_id': doc_id,
                        'parent': parent,
                        'page': metadata.get('page_number', 1)
                    })
            except Exception as e:
                continue
    
    if existing_children:
        print(f"\n✅ Found {len(existing_children)} real child documents in intake/")
        for child in existing_children[:5]:
            print(f"   • {child['doc_id']} (Page {child['page']} of {child['parent']})")
        
        # Check queue status
        status = queue.get_status()
        print(f"\n📊 Current Queue Status:")
        print(f"   • Pending: {status['pending']}")
        print(f"   • Processing: {status['processing']}")
        print(f"   • Failed: {status['failed']}")
        print(f"   • Total in queue: {status['total_queue']}")
        print(f"   • Total processed: {status['total_processed']}")
        
        if status['pending'] > 0:
            print(f"\n✅ Queue has {status['pending']} pending documents!")
            print("\n💡 To process them:")
            print("   from flows.document_processing_flow import process_next_document_from_queue")
            print("   process_next_document_from_queue()")
        else:
            print("\n⚠️  No pending documents in queue")
            print("   Child documents may have already been processed")
    else:
        print("⚠️  No child documents found in intake/ directory")
        print("   Process a PDF file to create child documents")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    test_child_notification()
