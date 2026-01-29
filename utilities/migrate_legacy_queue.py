"""
Migration utility to move pending child documents from legacy queue
to the new unified queue system.

Run this once to migrate:
    python -m utilities.migrate_legacy_queue
"""

import json
from pathlib import Path
from utilities import settings, logger
from utilities.queue_manager import DocumentQueue


def migrate_legacy_queue() -> dict:
    """
    Migrate pending child documents from legacy queue to unified queue.
    
    Returns:
        Dict with migration results
    """
    # Legacy queue path
    legacy_queue_path = Path(settings.documents_dir) / "intake" / "pending_child_documents.json"
    
    # Check if legacy queue exists
    if not legacy_queue_path.exists():
        return {
            "status": "no_migration_needed",
            "message": "No legacy queue file found",
            "migrated_count": 0
        }
    
    # Load legacy queue
    try:
        with open(legacy_queue_path, 'r') as f:
            legacy_data = json.load(f)
        
        if not isinstance(legacy_data, list):
            logger.warning("Legacy queue is not a list, skipping migration")
            return {
                "status": "invalid_format",
                "message": "Legacy queue has invalid format",
                "migrated_count": 0
            }
        
        child_ids = [doc_id for doc_id in legacy_data if isinstance(doc_id, str)]
        
        if not child_ids:
            logger.info("Legacy queue is empty")
            return {
                "status": "empty",
                "message": "Legacy queue is empty",
                "migrated_count": 0
            }
        
        logger.info(f"Found {len(child_ids)} child documents in legacy queue")
        
        # Initialize unified queue
        queue = DocumentQueue()
        
        # Migrate each child document
        intake_dir = Path(settings.documents_dir) / "intake"
        migrated_count = 0
        failed_migrations = []
        
        for child_id in child_ids:
            # Find child document file
            child_files = list(intake_dir.glob(f"{child_id}.*"))
            child_files = [f for f in child_files if not f.name.endswith('.metadata.json')]
            
            if not child_files:
                logger.warning(f"Child document file not found: {child_id}")
                failed_migrations.append(child_id)
                continue
            
            # Load child metadata to get parent info
            metadata_path = intake_dir / f"{child_id}.metadata.json"
            parent_id = "UNKNOWN"
            child_metadata = {}
            
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        child_metadata = json.load(f)
                    parent_id = child_metadata.get("parent_document_id", "UNKNOWN")
                except Exception as e:
                    logger.warning(f"Failed to load metadata for {child_id}: {e}")
            
            # Add to unified queue
            queue_id = queue.add_file(
                file_path=str(child_files[0]),
                source_type="child_creation",
                priority=2,
                parent_id=parent_id,
                metadata={
                    "page_number": child_metadata.get("page_number", 0),
                    "generated_from_pdf": True,
                    "child_document_id": child_id,
                    "migrated_from_legacy": True
                }
            )
            
            if queue_id:
                migrated_count += 1
                logger.info(f"Migrated {child_id} → {queue_id}")
            else:
                failed_migrations.append(child_id)
        
        # Backup legacy queue before removing
        backup_path = legacy_queue_path.with_suffix('.json.backup')
        legacy_queue_path.rename(backup_path)
        logger.info(f"Backed up legacy queue to: {backup_path}")
        
        result = {
            "status": "success",
            "message": f"Migrated {migrated_count} child documents to unified queue",
            "migrated_count": migrated_count,
            "failed_count": len(failed_migrations),
            "failed_ids": failed_migrations,
            "backup_path": str(backup_path)
        }
        
        logger.info(f"Migration complete: {migrated_count} migrated, {len(failed_migrations)} failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "migrated_count": 0
        }


def main():
    """CLI entry point for migration."""
    print("\n" + "="*70)
    print("LEGACY QUEUE MIGRATION")
    print("="*70 + "\n")
    
    print("Migrating pending child documents from legacy queue to unified queue...")
    print("Legacy: documents/intake/pending_child_documents.json")
    print("Unified: documents/processing_queue.json\n")
    
    result = migrate_legacy_queue()
    
    print("\n" + "="*70)
    print("MIGRATION RESULTS")
    print("="*70 + "\n")
    
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Migrated: {result['migrated_count']} documents")
    
    if result.get('failed_count', 0) > 0:
        print(f"Failed: {result['failed_count']} documents")
        print(f"Failed IDs: {result.get('failed_ids', [])}")
    
    if result.get('backup_path'):
        print(f"\nBackup saved to: {result['backup_path']}")
        print("(You can safely delete this after verifying migration)")
    
    print("\n" + "="*70 + "\n")
    
    return 0 if result['status'] in ['success', 'no_migration_needed', 'empty'] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
