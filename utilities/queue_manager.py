"""
Unified Document Queue Manager

Manages a persistent queue for all document processing sources:
- Directory scanning
- Multiple file inputs
- Child document creation (PDF conversion)
- Manual document additions

All documents flow through the same queue for consistent processing.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# Import utilities
try:
    from utilities import logger, settings
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    
    # Fallback settings
    class Settings:
        documents_dir = "./documents"
    settings = Settings()


class DocumentQueue:
    """Unified queue for all document processing."""
    
    def __init__(self, queue_file: Optional[Path] = None):
        """
        Initialize document queue.
        
        Args:
            queue_file: Optional custom queue file path
        """
        if queue_file:
            self.queue_file = Path(queue_file)
        else:
            self.queue_file = Path(settings.documents_dir) / "processing_queue.json"
        
        self._ensure_queue_file()
    
    def _ensure_queue_file(self):
        """Create queue file if it doesn't exist."""
        if not self.queue_file.exists():
            # Ensure parent directory exists
            self.queue_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create empty queue
            self._save_queue({
                "queue": [],
                "processed": []
            })
            logger.info(f"Created new queue file: {self.queue_file}")
    
    def _load_queue(self) -> Dict[str, Any]:
        """
        Load queue from disk.
        
        Returns:
            Queue data with 'queue' and 'processed' lists
        """
        try:
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
            
            # Ensure required keys exist
            if 'queue' not in data:
                data['queue'] = []
            if 'processed' not in data:
                data['processed'] = []
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse queue file: {e}")
            return {"queue": [], "processed": []}
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            return {"queue": [], "processed": []}
    
    def _save_queue(self, data: Dict[str, Any]):
        """
        Save queue to disk.
        
        Args:
            data: Queue data to save
        """
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")
            raise
    
    def add_directory(self, directory_path: str, priority: int = 1) -> List[str]:
        """
        Scan directory and add all valid files to queue.
        
        Args:
            directory_path: Path to directory to scan
            priority: Queue priority (lower = higher priority)
        
        Returns:
            List of queue IDs for added documents
        """
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return []
        
        if not directory.is_dir():
            logger.error(f"Path is not a directory: {directory_path}")
            return []
        
        # Valid document extensions
        valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff']
        
        # Find all valid files
        files = [
            f for f in directory.iterdir() 
            if f.is_file() and f.suffix.lower() in valid_extensions
        ]
        
        logger.info(f"Found {len(files)} valid documents in {directory_path}")
        
        # Add each file to queue
        queue_ids = []
        for file_path in sorted(files):  # Sort for consistent ordering
            queue_id = self.add_file(
                file_path=str(file_path),
                source_type="directory_scan",
                priority=priority
            )
            if queue_id:
                queue_ids.append(queue_id)
        
        logger.info(f"Added {len(queue_ids)} documents to queue from directory")
        return queue_ids
    
    def add_file(self, file_path: str, source_type: str = "manual", 
                 priority: int = 1, parent_id: Optional[str] = None,
                 metadata: Optional[Dict] = None) -> Optional[str]:
        """
        Add single file to queue.
        
        Args:
            file_path: Path to file
            source_type: Source of file (manual, directory_scan, child_creation)
            priority: Queue priority (lower = higher priority)
            parent_id: Optional parent document ID (for child documents)
            metadata: Optional metadata dict
        
        Returns:
            Queue ID if successful, None otherwise
        """
        # Validate file exists
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        data = self._load_queue()
        
        # Generate unique queue ID
        existing_ids = [item['id'] for item in data['queue']]
        queue_id = self._generate_queue_id(existing_ids)
        
        # Create queue entry
        entry = {
            "id": queue_id,
            "document_id": None,  # Will be set after intake
            "source_type": source_type,
            "source_path": file_path,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "priority": priority,
            "metadata": metadata or {}
        }
        
        # Add parent_id if provided
        if parent_id:
            entry["parent_id"] = parent_id
        
        # Add to queue
        data['queue'].append(entry)
        
        # Sort by priority (lower first), then creation time
        # Use .get() to handle legacy entries without priority
        data['queue'].sort(key=lambda x: (x.get('priority', 999), x.get('created_at', '')))
        
        # Save queue
        self._save_queue(data)
        
        file_name = Path(file_path).name
        logger.info(f"Added to queue: {queue_id} - {file_name} (priority={priority}, source={source_type})")
        
        return queue_id
    
    def add_child_documents(self, child_ids: List[str], parent_id: str, 
                           priority: int = 2) -> List[str]:
        """
        Add child documents (from PDF conversion) to queue.
        
        Args:
            child_ids: List of child document IDs
            parent_id: Parent document ID
            priority: Queue priority (default 2 = after initial files)
        
        Returns:
            List of queue IDs for added children
        """
        intake_dir = Path(settings.documents_dir) / "intake"
        queue_ids = []
        
        for idx, child_id in enumerate(child_ids, 1):
            # Find child document file (not metadata.json)
            child_files = list(intake_dir.glob(f"{child_id}.*"))
            child_files = [f for f in child_files if not f.name.endswith('.metadata.json')]
            
            if not child_files:
                logger.warning(f"Child document file not found: {child_id}")
                continue
            
            # Load child metadata for page number
            metadata_path = intake_dir / f"{child_id}.metadata.json"
            child_metadata = {}
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        child_metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load child metadata: {e}")
            
            # Add child to queue
            queue_id = self.add_file(
                file_path=str(child_files[0]),
                source_type="child_creation",
                priority=priority,
                parent_id=parent_id,
                metadata={
                    "page_number": child_metadata.get("page_number", idx),
                    "generated_from_pdf": True,
                    "child_document_id": child_id
                }
            )
            
            if queue_id:
                queue_ids.append(queue_id)
        
        logger.info(f"Added {len(queue_ids)} child documents to queue for parent {parent_id}")
        return queue_ids
    
    def get_next(self) -> Optional[Dict[str, Any]]:
        """
        Get next pending document from queue.
        
        Returns:
            Next queue entry dict, or None if queue is empty
        """
        data = self._load_queue()
        
        # Find first pending entry (queue is already sorted by priority)
        for entry in data['queue']:
            if entry['status'] == 'pending':
                return entry
        
        return None
    
    def mark_processing(self, queue_id: str):
        """
        Mark queue entry as currently processing.
        
        Args:
            queue_id: Queue entry ID
        """
        data = self._load_queue()
        
        for entry in data['queue']:
            if entry['id'] == queue_id:
                entry['status'] = 'processing'
                entry['processing_started_at'] = datetime.now().isoformat()
                break
        
        self._save_queue(data)
        logger.info(f"Marked queue entry as processing: {queue_id}")
    
    def mark_completed(self, queue_id: str, document_id: str):
        """
        Mark queue entry as completed and move to processed list.
        
        Args:
            queue_id: Queue entry ID
            document_id: Generated document ID
        """
        data = self._load_queue()
        
        # Find and remove from queue
        entry = None
        for i, item in enumerate(data['queue']):
            if item['id'] == queue_id:
                entry = data['queue'].pop(i)
                break
        
        if entry:
            # Update entry with completion info
            entry['status'] = 'completed'
            entry['document_id'] = document_id
            entry['completed_at'] = datetime.now().isoformat()
            
            # Add to processed list
            data['processed'].append(entry)
            
            # Save queue
            self._save_queue(data)
            logger.info(f"Completed queue entry: {queue_id} → {document_id}")
        else:
            logger.warning(f"Queue entry not found: {queue_id}")
    
    def mark_failed(self, queue_id: str, error: str):
        """
        Mark queue entry as failed.
        
        Args:
            queue_id: Queue entry ID
            error: Error message
        """
        data = self._load_queue()
        
        for entry in data['queue']:
            if entry['id'] == queue_id:
                entry['status'] = 'failed'
                entry['error'] = error
                entry['failed_at'] = datetime.now().isoformat()
                break
        
        self._save_queue(data)
        logger.error(f"Failed queue entry: {queue_id} - {error}")
    
    def mark_skipped(self, queue_id: str):
        """
        Mark queue entry as skipped and move to processed list.
        
        Args:
            queue_id: Queue entry ID
        """
        data = self._load_queue()
        
        # Find and remove from queue
        entry = None
        for i, item in enumerate(data['queue']):
            if item['id'] == queue_id:
                entry = data['queue'].pop(i)
                break
        
        if entry:
            # Update entry with skip info
            entry['status'] = 'skipped'
            entry['skipped_at'] = datetime.now().isoformat()
            
            # Add to processed list
            data['processed'].append(entry)
            
            # Save queue
            self._save_queue(data)
            logger.info(f"Skipped queue entry: {queue_id}")
        else:
            logger.warning(f"Queue entry not found: {queue_id}")
    
    def get_status(self) -> Dict[str, int]:
        """
        Get queue status summary.
        
        Returns:
            Dict with status counts
        """
        data = self._load_queue()
        
        status_counts = {
            'pending': 0,
            'processing': 0,
            'failed': 0,
            'total_queue': len(data['queue']),
            'total_processed': len(data['processed'])
        }
        
        for entry in data['queue']:
            status = entry['status']
            if status in ['pending', 'processing', 'failed']:
                status_counts[status] += 1
        
        return status_counts
    
    def get_all_pending(self) -> List[Dict[str, Any]]:
        """
        Get all pending queue entries.
        
        Returns:
            List of pending queue entries
        """
        data = self._load_queue()
        return [entry for entry in data['queue'] if entry['status'] == 'pending']
    
    def get_all_failed(self) -> List[Dict[str, Any]]:
        """
        Get all failed queue entries.
        
        Returns:
            List of failed queue entries
        """
        data = self._load_queue()
        return [entry for entry in data['queue'] if entry['status'] == 'failed']
    
    def clear_processed(self, older_than_days: int = 7):
        """
        Clear processed entries older than specified days.
        
        Args:
            older_than_days: Days threshold
        """
        data = self._load_queue()
        cutoff = datetime.now().timestamp() - (older_than_days * 86400)
        
        original_count = len(data['processed'])
        
        # Filter processed entries
        data['processed'] = [
            entry for entry in data['processed']
            if self._parse_timestamp(entry.get('completed_at', entry.get('skipped_at', ''))) > cutoff
        ]
        
        removed_count = original_count - len(data['processed'])
        
        if removed_count > 0:
            self._save_queue(data)
            logger.info(f"Cleared {removed_count} processed entries older than {older_than_days} days")
    
    def retry_failed(self, queue_id: Optional[str] = None) -> int:
        """
        Retry failed queue entries.
        
        Args:
            queue_id: Optional specific queue ID to retry, or None to retry all
        
        Returns:
            Number of entries retried
        """
        data = self._load_queue()
        retry_count = 0
        
        for entry in data['queue']:
            if entry['status'] == 'failed':
                if queue_id is None or entry['id'] == queue_id:
                    # Reset to pending
                    entry['status'] = 'pending'
                    entry.pop('error', None)
                    entry.pop('failed_at', None)
                    entry['retried_at'] = datetime.now().isoformat()
                    retry_count += 1
                    
                    if queue_id:
                        break  # Only retry specific one
        
        if retry_count > 0:
            self._save_queue(data)
            logger.info(f"Retried {retry_count} failed queue entries")
        
        return retry_count
    
    def clear_queue(self, confirm: bool = False):
        """
        Clear all pending queue entries (dangerous!).
        
        Args:
            confirm: Must be True to actually clear
        """
        if not confirm:
            logger.warning("clear_queue called without confirmation")
            return
        
        data = self._load_queue()
        original_count = len(data['queue'])
        
        # Keep only processed entries
        data['queue'] = []
        
        self._save_queue(data)
        logger.info(f"Cleared {original_count} queue entries")
    
    def _generate_queue_id(self, existing_ids: List[str]) -> str:
        """
        Generate unique queue ID.
        
        Args:
            existing_ids: List of existing queue IDs
        
        Returns:
            New unique queue ID
        """
        max_num = 0
        for queue_id in existing_ids:
            if queue_id.startswith('QUEUE_'):
                try:
                    num = int(queue_id.split('_')[1])
                    max_num = max(max_num, num)
                except (IndexError, ValueError):
                    pass
        
        return f"QUEUE_{max_num + 1:05d}"
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """
        Parse ISO timestamp to Unix timestamp.
        
        Args:
            timestamp_str: ISO format timestamp string
        
        Returns:
            Unix timestamp
        """
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.timestamp()
        except:
            return 0.0
