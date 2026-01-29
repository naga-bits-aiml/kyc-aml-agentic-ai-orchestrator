"""
Comprehensive tests for the unified DocumentQueue manager.

Tests cover:
- Queue initialization and file operations
- Adding documents from various sources
- Queue status and retrieval operations
- Processing lifecycle (pending → processing → completed)
- Error handling and failed documents
- Child document queuing
- Directory scanning
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

# Import queue manager
from utilities.queue_manager import DocumentQueue


class TestQueueInitialization:
    """Test queue initialization and file management."""
    
    def test_queue_creation(self, tmp_path):
        """Test queue file is created on initialization."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        assert queue_file.exists()
        
        # Verify structure
        with open(queue_file, 'r') as f:
            data = json.load(f)
        
        assert 'queue' in data
        assert 'processed' in data
        assert isinstance(data['queue'], list)
        assert isinstance(data['processed'], list)
        print("✅ TEST 1 PASSED: Queue file created with correct structure")
    
    def test_existing_queue_loading(self, tmp_path):
        """Test loading existing queue file."""
        queue_file = tmp_path / "test_queue.json"
        
        # Create queue with some data
        initial_data = {
            "queue": [
                {
                    "id": "QUEUE_00001",
                    "status": "pending",
                    "source_path": "/test/file.pdf"
                }
            ],
            "processed": []
        }
        
        with open(queue_file, 'w') as f:
            json.dump(initial_data, f)
        
        # Load queue
        queue = DocumentQueue(queue_file=queue_file)
        data = queue._load_queue()
        
        assert len(data['queue']) == 1
        assert data['queue'][0]['id'] == "QUEUE_00001"
        print("✅ TEST 2 PASSED: Existing queue loaded correctly")


class TestAddingDocuments:
    """Test adding documents from various sources."""
    
    def test_add_single_file(self, tmp_path):
        """Test adding a single file to queue."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Create a test file
        test_file = tmp_path / "test_document.pdf"
        test_file.write_text("test content")
        
        # Add file to queue
        queue_id = queue.add_file(str(test_file), source_type="manual", priority=1)
        
        assert queue_id is not None
        assert queue_id.startswith("QUEUE_")
        
        # Verify in queue
        data = queue._load_queue()
        assert len(data['queue']) == 1
        assert data['queue'][0]['id'] == queue_id
        assert data['queue'][0]['status'] == 'pending'
        assert data['queue'][0]['source_type'] == 'manual'
        print("✅ TEST 3 PASSED: Single file added to queue")
    
    def test_add_multiple_files(self, tmp_path):
        """Test adding multiple files maintains order and priority."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Create test files
        files = []
        for i in range(3):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test content {i}")
            files.append(test_file)
        
        # Add files with different priorities
        queue_ids = []
        queue_ids.append(queue.add_file(str(files[0]), priority=3))
        queue_ids.append(queue.add_file(str(files[1]), priority=1))  # Highest priority
        queue_ids.append(queue.add_file(str(files[2]), priority=2))
        
        # Verify queue order (sorted by priority)
        data = queue._load_queue()
        assert len(data['queue']) == 3
        assert data['queue'][0]['priority'] == 1  # files[1]
        assert data['queue'][1]['priority'] == 2  # files[2]
        assert data['queue'][2]['priority'] == 3  # files[0]
        print("✅ TEST 4 PASSED: Multiple files added with correct priority order")
    
    def test_add_directory(self, tmp_path):
        """Test adding all files from a directory."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Create test directory with files
        test_dir = tmp_path / "documents"
        test_dir.mkdir()
        
        # Create various file types
        (test_dir / "doc1.pdf").write_text("pdf content")
        (test_dir / "doc2.jpg").write_text("jpg content")
        (test_dir / "doc3.png").write_text("png content")
        (test_dir / "readme.txt").write_text("txt content")  # Should be ignored
        
        # Add directory
        queue_ids = queue.add_directory(str(test_dir))
        
        # Should add 3 valid files (pdf, jpg, png), not txt
        assert len(queue_ids) == 3
        
        data = queue._load_queue()
        assert len(data['queue']) == 3
        
        # Verify all are marked as directory_scan
        for entry in data['queue']:
            assert entry['source_type'] == 'directory_scan'
        print("✅ TEST 5 PASSED: Directory scanned and valid files added")
    
    def test_add_nonexistent_file(self, tmp_path):
        """Test adding non-existent file returns None."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        queue_id = queue.add_file("/nonexistent/file.pdf")
        
        assert queue_id is None, "Expected None for nonexistent file"
        
        data = queue._load_queue()
        assert len(data['queue']) == 0, f"Expected empty queue, got {len(data['queue'])}"
        print("✅ TEST 6 PASSED: Non-existent file rejected")


class TestQueueOperations:
    """Test queue retrieval and status operations."""
    
    def test_get_next_pending(self, tmp_path):
        """Test getting next pending document."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Create test files
        test_file1 = tmp_path / "test1.pdf"
        test_file1.write_text("test 1")
        test_file2 = tmp_path / "test2.pdf"
        test_file2.write_text("test 2")
        
        # Add files
        queue_id1 = queue.add_file(str(test_file1), priority=2)
        queue_id2 = queue.add_file(str(test_file2), priority=1)  # Higher priority
        
        # Get next - should be queue_id2 (priority 1)
        next_entry = queue.get_next()
        
        assert next_entry is not None
        assert next_entry['id'] == queue_id2
        assert next_entry['priority'] == 1
        print("✅ TEST 7 PASSED: Get next returns highest priority pending")
    
    def test_get_queue_status(self, tmp_path):
        """Test queue status summary."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Create and add files
        files = []
        for i in range(5):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test {i}")
            queue.add_file(str(test_file))
            files.append(test_file)
        
        status = queue.get_status()
        
        assert status['pending'] == 5
        assert status['processing'] == 0
        assert status['failed'] == 0
        assert status['total_queue'] == 5
        assert status['total_processed'] == 0
        print("✅ TEST 8 PASSED: Queue status summary correct")
    
    def test_get_all_pending(self, tmp_path):
        """Test retrieving all pending entries."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add files
        for i in range(3):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test {i}")
            queue.add_file(str(test_file))
        
        pending = queue.get_all_pending()
        
        assert len(pending) == 3
        assert all(entry['status'] == 'pending' for entry in pending)
        print("✅ TEST 9 PASSED: All pending entries retrieved")


class TestProcessingLifecycle:
    """Test document processing lifecycle."""
    
    def test_mark_processing(self, tmp_path):
        """Test marking document as processing."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test")
        queue_id = queue.add_file(str(test_file))
        
        # Mark as processing
        queue.mark_processing(queue_id)
        
        # Verify status changed
        data = queue._load_queue()
        entry = next(e for e in data['queue'] if e['id'] == queue_id)
        
        assert entry['status'] == 'processing'
        assert 'processing_started_at' in entry
        print("✅ TEST 10 PASSED: Document marked as processing")
    
    def test_mark_completed(self, tmp_path):
        """Test marking document as completed."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add and process file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test")
        queue_id = queue.add_file(str(test_file))
        
        queue.mark_processing(queue_id)
        queue.mark_completed(queue_id, "DOC_20260129_100000_ABC")
        
        # Verify moved to processed
        data = queue._load_queue()
        
        assert len(data['queue']) == 0  # Removed from queue
        assert len(data['processed']) == 1  # Added to processed
        
        processed_entry = data['processed'][0]
        assert processed_entry['id'] == queue_id
        assert processed_entry['status'] == 'completed'
        assert processed_entry['document_id'] == "DOC_20260129_100000_ABC"
        assert 'completed_at' in processed_entry
        print("✅ TEST 11 PASSED: Document marked as completed and moved to processed")
    
    def test_mark_failed(self, tmp_path):
        """Test marking document as failed."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test")
        queue_id = queue.add_file(str(test_file))
        
        # Mark as failed
        error_msg = "Processing failed due to invalid format"
        queue.mark_failed(queue_id, error_msg)
        
        # Verify status
        data = queue._load_queue()
        entry = next(e for e in data['queue'] if e['id'] == queue_id)
        
        assert entry['status'] == 'failed'
        assert entry['error'] == error_msg
        assert 'failed_at' in entry
        print("✅ TEST 12 PASSED: Document marked as failed with error")
    
    def test_mark_skipped(self, tmp_path):
        """Test marking document as skipped."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test")
        queue_id = queue.add_file(str(test_file))
        
        # Mark as skipped
        queue.mark_skipped(queue_id)
        
        # Verify moved to processed with skipped status
        data = queue._load_queue()
        
        assert len(data['queue']) == 0
        assert len(data['processed']) == 1
        
        processed_entry = data['processed'][0]
        assert processed_entry['status'] == 'skipped'
        assert 'skipped_at' in processed_entry
        print("✅ TEST 13 PASSED: Document marked as skipped")


class TestChildDocuments:
    """Test child document queuing (from PDF conversion)."""
    
    def test_add_child_documents(self, tmp_path):
        """Test adding child documents with parent reference."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Mock intake directory structure
        intake_dir = tmp_path / "documents" / "intake"
        intake_dir.mkdir(parents=True)
        
        # Create child document files and metadata
        child_ids = ["DOC_CHILD_001", "DOC_CHILD_002", "DOC_CHILD_003"]
        
        for idx, child_id in enumerate(child_ids, 1):
            # Create child file
            child_file = intake_dir / f"{child_id}.jpg"
            child_file.write_text(f"child {idx}")
            
            # Create metadata
            metadata = {
                "document_id": child_id,
                "page_number": idx,
                "generated_from_pdf": True
            }
            metadata_file = intake_dir / f"{child_id}.metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
        
        # Mock settings
        import utilities.queue_manager as qm
        original_settings = qm.settings.documents_dir
        qm.settings.documents_dir = str(tmp_path / "documents")
        
        try:
            # Add child documents
            parent_id = "DOC_20260129_100000_ABC"
            queue_ids = queue.add_child_documents(child_ids, parent_id=parent_id, priority=2)
            
            assert len(queue_ids) == 3
            
            # Verify queue entries
            data = queue._load_queue()
            assert len(data['queue']) == 3
            
            for entry in data['queue']:
                assert entry['source_type'] == 'child_creation'
                assert entry['parent_id'] == parent_id
                assert entry['priority'] == 2
                assert entry['metadata']['generated_from_pdf'] is True
                assert 'page_number' in entry['metadata']
            
            print("✅ TEST 14 PASSED: Child documents queued with parent reference")
        finally:
            qm.settings.documents_dir = original_settings


class TestQueueManagement:
    """Test queue management operations."""
    
    def test_retry_failed(self, tmp_path):
        """Test retrying failed documents."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add and fail some documents
        files = []
        queue_ids = []
        for i in range(3):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test {i}")
            files.append(test_file)
            queue_id = queue.add_file(str(test_file))
            queue_ids.append(queue_id)
            queue.mark_failed(queue_id, "Test failure")
        
        # Retry all failed
        retry_count = queue.retry_failed()
        
        assert retry_count == 3
        
        # Verify all back to pending
        data = queue._load_queue()
        for entry in data['queue']:
            assert entry['status'] == 'pending'
            assert 'error' not in entry
            assert 'retried_at' in entry
        print("✅ TEST 15 PASSED: Failed documents retried")
    
    def test_clear_processed(self, tmp_path):
        """Test clearing old processed entries."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add and complete documents
        for i in range(5):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test {i}")
            queue_id = queue.add_file(str(test_file))
            queue.mark_completed(queue_id, f"DOC_{i}")
        
        # Verify processed count
        status = queue.get_status()
        assert status['total_processed'] == 5
        
        # Clear processed (older than 0 days - clears all)
        queue.clear_processed(older_than_days=0)
        
        # Verify cleared
        status = queue.get_status()
        assert status['total_processed'] == 0
        print("✅ TEST 16 PASSED: Old processed entries cleared")


class TestQueueIDGeneration:
    """Test queue ID generation."""
    
    def test_sequential_ids(self, tmp_path):
        """Test queue IDs are generated sequentially."""
        queue_file = tmp_path / "test_queue.json"
        queue = DocumentQueue(queue_file=queue_file)
        
        # Add files
        queue_ids = []
        for i in range(5):
            test_file = tmp_path / f"test_{i}.pdf"
            test_file.write_text(f"test {i}")
            queue_id = queue.add_file(str(test_file))
            queue_ids.append(queue_id)
        
        # Verify sequential
        assert queue_ids == ["QUEUE_00001", "QUEUE_00002", "QUEUE_00003", "QUEUE_00004", "QUEUE_00005"]
        print("✅ TEST 17 PASSED: Queue IDs generated sequentially")


def run_all_tests():
    """Run all queue manager tests."""
    import tempfile
    import traceback
    
    print("\n" + "="*70)
    print("QUEUE MANAGER TESTS")
    print("="*70 + "\n")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Run all test classes
        test_classes = [
            TestQueueInitialization(),
            TestAddingDocuments(),
            TestQueueOperations(),
            TestProcessingLifecycle(),
            TestChildDocuments(),
            TestQueueManagement(),
            TestQueueIDGeneration()
        ]
        
        total_tests = 0
        passed_tests = 0
        
        for test_class in test_classes:
            for method_name in dir(test_class):
                if method_name.startswith('test_'):
                    total_tests += 1
                    try:
                        method = getattr(test_class, method_name)
                        method(tmp_path)
                        passed_tests += 1
                    except AssertionError as e:
                        print(f"❌ TEST FAILED: {method_name}")
                        print(f"   Assertion: {e}")
                        if '--verbose' in str(e):
                            traceback.print_exc()
                    except Exception as e:
                        print(f"❌ TEST ERROR: {method_name}")
                        print(f"   Error: {e}")
                        print(f"   Type: {type(e).__name__}")
                        traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total_tests - passed_tests} tests failed")
    print("="*70 + "\n")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
