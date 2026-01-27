#!/usr/bin/env python3
"""
Migrate existing cases to stage-based architecture.

This script:
1. Creates stage folders (intake/classification/extraction/processed)
2. Moves documents to appropriate stages based on their status
3. Simplifies case_metadata.json structure
4. Preserves all document metadata
"""

import sys
import json
from pathlib import Path
from case_metadata_manager import StagedCaseMetadataManager
from utilities import settings, logger


def migrate_case(case_dir: Path) -> bool:
    """Migrate a single case to stage-based structure."""
    case_reference = case_dir.name
    
    print(f"\n{'='*70}")
    print(f"Migrating Case: {case_reference}")
    print(f"{'='*70}")
    
    # Load old metadata
    old_metadata_file = case_dir / "case_metadata.json"
    if not old_metadata_file.exists():
        print(f"⚠️  No metadata file found, skipping")
        return False
    
    with open(old_metadata_file, 'r') as f:
        old_metadata = json.load(f)
    
    # Create new staged manager
    staged_mgr = StagedCaseMetadataManager(case_reference)
    
    # Find all documents currently in case directory
    pdf_files = list(case_dir.glob("*.pdf"))
    jpg_files = list(case_dir.glob("*.jpg"))
    png_files = list(case_dir.glob("*.png"))
    
    all_files = pdf_files + jpg_files + png_files
    
    print(f"\n📄 Found {len(all_files)} document(s)")
    
    if not all_files:
        print("✅ No documents to migrate")
        return True
    
    # Migrate each document
    migrated_docs = []
    
    for idx, doc_file in enumerate(all_files, 1):
        print(f"\n  {idx}. {doc_file.name}")
        
        # Generate document ID if not exists
        doc_id = f"{case_reference}_DOC_{idx:03d}"
        
        # Check if metadata exists (with or without leading dot)
        metadata_file = case_dir / f"{doc_file.name}.metadata.json"
        if not metadata_file.exists():
            metadata_file = case_dir / f".{doc_file.name}.metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                doc_metadata = json.load(f)
            
            # Determine stage based on status
            status = doc_metadata.get('status', 'pending_processing')
            
            if status == 'fully_completed':
                stage = 'processed'
            elif 'extraction' in doc_metadata:
                stage = 'extraction'
            elif 'classification' in doc_metadata:
                stage = 'classification'
            else:
                stage = 'intake'
            
            print(f"     Status: {status} → Stage: {stage}")
        else:
            stage = 'intake'
            print(f"     No metadata → Stage: {stage}")
        
        # Move to appropriate stage directory
        stage_dir = case_dir / stage
        stage_dir.mkdir(exist_ok=True)
        
        dest_file = stage_dir / doc_file.name
        
        # Move file (if not already in stage dir)
        if doc_file.parent.name not in ['intake', 'classification', 'extraction', 'processed']:
            doc_file.rename(dest_file)
            print(f"     Moved to {stage}/")
        
        # Move metadata if exists
        if metadata_file.exists():
            dest_metadata = stage_dir / f"{doc_file.name}.metadata.json"
            metadata_file.rename(dest_metadata)
        
        # Add to new metadata structure
        migrated_docs.append({
            "document_id": doc_id,
            "stage": stage,
            "metadata_path": f"{stage}/{doc_file.name}.metadata.json"
        })
    
    # Create new metadata structure
    new_metadata = {
        "case_reference": case_reference,
        "created_date": old_metadata.get('created_date', ''),
        "status": old_metadata.get('status', 'active'),
        "workflow_stage": old_metadata.get('workflow_stage', 'intake'),
        "documents": migrated_docs
    }
    
    # Backup old metadata
    backup_file = case_dir / "case_metadata.json.backup"
    old_metadata_file.rename(backup_file)
    print(f"\n💾 Backed up old metadata to: {backup_file.name}")
    
    # Save new metadata
    staged_mgr.save_metadata(new_metadata)
    print(f"✅ Saved new metadata structure")
    
    # Show stage summary
    summary = staged_mgr.get_stage_summary()
    print(f"\n📊 Stage Summary:")
    for stage, count in summary.items():
        if count > 0:
            print(f"   {stage}: {count} document(s)")
    
    return True


def migrate_all_cases():
    """Migrate all cases in the documents/cases directory."""
    cases_dir = Path(settings.documents_dir) / "cases"
    
    if not cases_dir.exists():
        print("❌ No cases directory found")
        return
    
    case_dirs = [d for d in cases_dir.iterdir() if d.is_dir()]
    
    if not case_dirs:
        print("📋 No cases to migrate")
        return
    
    print("\n" + "="*70)
    print(f"🔄 STAGE-BASED ARCHITECTURE MIGRATION")
    print("="*70)
    print(f"\nFound {len(case_dirs)} case(s) to migrate")
    
    success_count = 0
    failed_count = 0
    
    for case_dir in sorted(case_dirs):
        try:
            if migrate_case(case_dir):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Migration failed for {case_dir.name}: {e}")
            print(f"\n❌ Error migrating {case_dir.name}: {e}")
            failed_count += 1
    
    # Final summary
    print("\n" + "="*70)
    print("📊 MIGRATION SUMMARY")
    print("="*70)
    print(f"✅ Successfully migrated: {success_count}")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")
    
    print("\n💡 Next Steps:")
    print("   1. Test the migrated cases")
    print("   2. Update code to use StagedCaseMetadataManager")
    print("   3. Remove backup files when confident")
    print()


if __name__ == "__main__":
    print("\n⚠️  This will restructure your case directories!")
    print("   Backups will be created automatically.")
    
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    
    if response == 'yes':
        migrate_all_cases()
    else:
        print("\n❌ Migration cancelled")
        sys.exit(0)
