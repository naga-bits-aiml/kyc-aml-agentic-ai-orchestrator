# Stage-Based Architecture Tests

This directory contains tests for the stage-based document workflow architecture.

## Architecture Overview

Documents flow through four distinct stages:
1. **intake** - Initial document upload and validation
2. **classification** - Document type classification
3. **extraction** - Data extraction from documents
4. **processed** - Completed processing

## Test Files

### `test_staged_manager.py`
Tests the core `StagedCaseMetadataManager` functionality:
- Adding documents to intake stage
- Moving documents between stages
- Updating document metadata
- Getting stage summaries
- Verifying file movements

**Run:**
```bash
python tests/stage_architecture/test_staged_manager.py
```

### `test_stage_transitions.py`
Tests document movement through all workflow stages:
- Add document to intake
- Move through classification → extraction → processed
- Verify file locations at each stage
- Validate metadata updates

**Run:**
```bash
python tests/stage_architecture/test_stage_transitions.py
```

### `test_workflow_stages.py`
Full integration test with CrewAI agents:
- Intake crew processing
- Classification crew processing
- Extraction crew processing
- Stage transitions after each step
- Complete workflow validation

**Run:**
```bash
python tests/stage_architecture/test_workflow_stages.py
```

## Key Features Tested

✅ **Single File Storage** - Documents stored once, moved between stages  
✅ **Atomic Operations** - File + metadata move together  
✅ **Stage Summary** - Document counts per stage  
✅ **Metadata Updates** - Updates preserved during transitions  
✅ **Parent File Tracking** - Ready for OCR-generated images  

## Migration

To migrate existing cases to the new architecture:
```bash
python migrate_to_staged_architecture.py
```

This will:
- Create stage directories
- Move documents to appropriate stages based on status
- Create simplified metadata structure
- Backup old metadata files
