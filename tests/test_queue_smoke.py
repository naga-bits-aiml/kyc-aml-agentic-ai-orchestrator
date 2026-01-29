"""
Quick smoke tests for DocumentQueue to verify basic functionality.
"""

import json
import tempfile
from pathlib import Path
from utilities.queue_manager import DocumentQueue


def test_basic_operations():
    """Test basic queue operations."""
    print("\n🧪 Testing basic queue operations...")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        queue_file = tmp_path / "queue.json"
        
        # Test 1: Initialize queue
        queue = DocumentQueue(queue_file=queue_file)
        assert queue_file.exists(), "Queue file should be created"
        print("✅ Queue initialized")
        
        # Test 2: Add a file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")
        
        queue_id = queue.add_file(str(test_file), source_type="manual", priority=1)
        assert queue_id is not None, "Should return queue ID"
        assert queue_id.startswith("QUEUE_"), f"Queue ID should start with QUEUE_, got {queue_id}"
        print(f"✅ File added with ID: {queue_id}")
        
        # Test 3: Get next from queue
        next_entry = queue.get_next()
        assert next_entry is not None, "Should have next entry"
        assert next_entry['id'] == queue_id, f"Expected {queue_id}, got {next_entry['id']}"
        assert next_entry['status'] == 'pending', f"Expected pending, got {next_entry['status']}"
        print(f"✅ Next entry retrieved: {next_entry['id']}")
        
        # Test 4: Mark as processing
        queue.mark_processing(queue_id)
        status = queue.get_status()
        assert status['processing'] == 1, f"Expected 1 processing, got {status['processing']}"
        print("✅ Marked as processing")
        
        # Test 5: Mark as completed
        queue.mark_completed(queue_id, "DOC_TEST_123")
        status = queue.get_status()
        assert status['total_queue'] == 0, f"Expected 0 in queue, got {status['total_queue']}"
        assert status['total_processed'] == 1, f"Expected 1 processed, got {status['total_processed']}"
        print("✅ Marked as completed")
        
        # Test 6: Directory scanning
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        (test_dir / "doc1.pdf").write_text("doc1")
        (test_dir / "doc2.jpg").write_text("doc2")
        (test_dir / "doc3.txt").write_text("doc3")  # Should be ignored
        
        queue_ids = queue.add_directory(str(test_dir))
        assert len(queue_ids) == 2, f"Expected 2 files, got {len(queue_ids)}"
        print(f"✅ Directory scanned: {len(queue_ids)} files added")
        
        # Clean up queue for next test
        for qid in queue_ids:
            queue.mark_skipped(qid)
        
        # Test 7: Priority ordering
        file1 = tmp_path / "file1.pdf"
        file2 = tmp_path / "file2.pdf"
        file1.write_text("file1")
        file2.write_text("file2")
        
        id1 = queue.add_file(str(file1), priority=3)
        id2 = queue.add_file(str(file2), priority=1)  # Higher priority
        
        next_entry = queue.get_next()
        assert next_entry['id'] == id2, f"Expected {id2} (priority 1) first, got {next_entry['id']}"
        print("✅ Priority ordering works")
        
        # Test 8: Failed and retry
        test_fail = tmp_path / "fail.pdf"
        test_fail.write_text("fail")
        fail_id = queue.add_file(str(test_fail))
        
        queue.mark_failed(fail_id, "Test error")
        status = queue.get_status()
        assert status['failed'] == 1, f"Expected 1 failed, got {status['failed']}"
        
        retry_count = queue.retry_failed(fail_id)
        assert retry_count == 1, f"Expected 1 retried, got {retry_count}"
        print("✅ Failed and retry works")
        
        print("\n🎉 All basic tests passed!\n")
        return True


if __name__ == "__main__":
    try:
        success = test_basic_operations()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
