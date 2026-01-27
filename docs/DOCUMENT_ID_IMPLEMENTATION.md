# Document ID Processing - Implementation Summary

## Overview
Implemented hierarchical case metadata with document ID lookup capability, allowing users to reference documents by their IDs instead of full file paths.

## Architecture

### Minimal Case Metadata Structure
```json
{
  "case_reference": "KYC-2026-001",
  "documents": [
    {"document_id": "KYC-2026-001_DOC_001.pdf", "status": "pending_reprocessing"}
  ],
  "document_summary": {
    "total": 4,
    "pending_reprocessing": 4
  }
}
```

### Individual Document Metadata
```json
{
  "document_id": "KYC-2026-001_DOC_001.pdf",
  "stored_path": "/path/to/document.pdf",
  "status": "validated",
  "extraction": {"status": "error", "method": "ocr_local_pdf_unsupported"},
  "classification": {"status": "unknown"}
}
```

## Features Implemented

### 1. CaseMetadataManager
- **Location**: `case_metadata_manager.py`
- **Key Methods**:
  - `sync_documents_from_directory()` - Scans case directory and updates metadata
  - `get_pending_documents()` - Returns documents needing processing
  - `generate_llm_prompt()` - Creates comprehensive prompt for LLM orchestration
  - `_calculate_summary_from_files()` - Reads individual metadata files for statistics

### 2. Document ID Recognition (ChatInterface)
- **Pattern**: `KYC-\d{4}-\d{3}_DOC_\d{3}\.(?:pdf|txt|jpg|jpeg|png)`
- **Examples**:
  - `KYC-2026-001_DOC_001.pdf`
  - `KYC-2026-001_DOC_002.pdf`

### 3. Path Resolution
When a user types a document ID:
1. Regex extracts the document ID pattern
2. System looks up the document in the case directory
3. Resolves to full path from `stored_path` in metadata
4. Processes the document

## Usage Examples

### User Commands
```
👤 You: KYC-2026-001
🤖 Assistant: [Switches to case and shows summary]

👤 You: process KYC-2026-001_DOC_001.pdf
🤖 Assistant: [Processes that specific document]

👤 You: process documents
🤖 Assistant: [Processes all pending documents]

👤 You: reprocess KYC-2026-001_DOC_002.pdf
🤖 Assistant: [Reprocesses that document]
```

### Programmatic Access
```python
from case_metadata_manager import CaseMetadataManager

# Initialize manager
manager = CaseMetadataManager("KYC-2026-001")

# Sync metadata
metadata = manager.sync_documents_from_directory()

# Get pending documents
pending = manager.get_pending_documents()
# Returns: [{"document_id": "...", "status": "pending_reprocessing"}, ...]

# Generate LLM prompt (includes details from individual files)
prompt = manager.generate_llm_prompt()
```

## Benefits

### No Data Duplication
- Case metadata: Only document_id + status (2 fields)
- Document metadata: Full details in separate files
- Single source of truth per document

### Scalable
- Case metadata stays small (~70 lines) regardless of document count
- Adding document fields doesn't bloat case metadata
- Fast parsing for LLM analysis

### User-Friendly
- Users can reference documents by short IDs
- No need to type full file paths
- Autocomplete-friendly naming scheme

## Testing

### Run Tests
```bash
# Test simplified metadata structure
python tests/test_simplified_metadata.py

# Test document ID lookup
python test_document_id_lookup.py
```

### Expected Output
```
✅ Case metadata is minimal (document_id + status)
✅ Summary calculated from individual .metadata.json files
✅ LLM prompt includes details loaded from individual files
✅ No data duplication in case_metadata.json
✅ Document IDs recognized and resolved to paths
```

## Next Steps

### Integration Complete
- ✅ CaseMetadataManager implemented
- ✅ Document ID recognition in chat interface
- ✅ Path resolution from metadata
- ✅ Pending documents retrieval

### Ready for Use
The system now supports:
1. Referencing documents by ID: "process KYC-2026-001_DOC_001.pdf"
2. Processing all pending documents: "process documents"
3. LLM-based orchestration using case metadata
4. Hierarchical tracking with no duplication

## File Locations

- **Case Metadata Manager**: `case_metadata_manager.py`
- **Chat Interface**: `chat_interface.py` (updated with document ID lookup)
- **Case Metadata**: `documents/cases/{case_id}/case_metadata.json`
- **Document Metadata**: `documents/cases/{case_id}/{doc_id}.metadata.json`
- **Tests**: 
  - `tests/test_simplified_metadata.py`
  - `test_document_id_lookup.py`
