# Workflow Enhancement Implementation Guide

## Overview
The chat interface has been enhanced to support a guided workflow for KYC/AML case processing with the following features:

## Key Enhancements

### 1. Case Reference Management
- **Workflow State Tracking**: Added `workflow_state` to track user progress
  - States: `awaiting_case_reference`, `active`, `awaiting_confirmation`
- **Case Reference Prompt**: Users are asked for case reference on startup
- **Case-Based Storage**: Documents are organized in `documents/cases/{CASE_REFERENCE}/` folders
  
### 2. Document Storage with Internal References
- Files are copied to case-specific folders with internal references
- Format: `{CASE_REF}_DOC_{001}{.ext}`
- File mapping preserved in `file_mapping.json` (internal_ref → original_path)

### 3. Multiple Input Types Support

#### Individual Files
- Auto-detected from file paths in user input
- Processed immediately with case reference

#### Folder Processing
- Detects folder paths in input
- Lists all supported files in folder
- Requests confirmation before processing
- Batch processes all confirmed files

#### Archive Processing  
- Supports: `.zip`, `.tar`, `.gz`, `.tgz`, `.rar`, `.7z`
- Automatically extracts to temp directory
- Lists extracted files for confirmation
- Processes all documents and cleans up temp files

### 4. Enhanced Help and Status Commands
- Help shows current case reference and workflow steps
- Status displays active case and document counts
- Workflow guidance integrated into UI

## Implementation Status

### Completed ✅
1. Added workflow state management to ChatInterface
2. Created `set_case_reference()` method
3. Implemented `confirm_pending_action()` for user confirmations
4. Added input handlers:
   - `_handle_case_reference_input()`
   - `_handle_confirmation_input()`
   - `_handle_folder_input()`
   - `_handle_archive_input()`
5. Created path extraction methods:
   - `_extract_folder_path()`
   - `_extract_archive_path()`
6. Updated `_process_documents()` to:
   - Check for case reference
   - Copy files with internal references
   - Save file mapping
   - Process through orchestrator
7. Enhanced `start()` method with workflow prompts
8. Updated help and status displays

### Syntax Issues to Resolve ⚠️

The implementation has some multiline string syntax issues in `chat_interface.py`:
- Line 509-512: Multiline string return needs proper escaping
- Line 567-572: F-string multiline needs fixing

**Recommended Fix**:
Replace problematic multiline returns with concatenated strings:

```python
# Instead of:
return """Multi
line
string"""

# Use:
return ("Multi\\n"
        "line\\n"
        "string")
```

## Testing

Create test scripts in `tests/` folder:

### Test 1: Case Reference Flow
```python
# Test case reference setting
chat = ChatInterface()
assert chat.workflow_state == "awaiting_case_reference"
chat.set_case_reference("KYC-2024-001")
assert chat.case_reference == "KYC-2024-001"
assert chat.workflow_state == "active"
```

### Test 2: Folder Processing
```python
# Create test folder with documents
test_folder = Path("test_documents")
test_folder.mkdir(exist_ok=True)
(test_folder / "doc1.pdf").touch()
(test_folder / "doc2.jpg").touch()

# Process folder
response = chat.handle_user_input(str(test_folder))
assert "Found 2 document(s)" in response
assert "Do you want to process" in response
```

### Test 3: Archive Processing
```python
# Create test archive
import zipfile
with zipfile.ZipFile("test.zip", "w") as zf:
    zf.writestr("doc1.pdf", b"test content")
    
response = chat.handle_user_input("test.zip")
assert "Archive file detected" in response
```

## Usage Examples

### Example 1: Complete Workflow
```
User: KYC-2024-001
Bot: ✅ Case Reference Set: KYC-2024-001
     You can now upload documents...

User: C:\\Documents\\passport.pdf
Bot: 🔄 Processing 1 document(s) for case KYC-2024-001...
     ✅ Processing complete!
     📁 Documents stored in: documents/cases/KYC-2024-001
```

### Example 2: Folder Processing
```
User: C:\\Documents\\kyc_docs\\
Bot: 📁 Found 5 document(s) in folder: kyc_docs
     • passport.pdf
     • utility_bill.pdf
     ...
     ❓ Do you want to process all these documents?

User: yes
Bot: 🔄 Processing 5 document(s)...
     ✅ Processing complete!
```

### Example 3: Archive Processing
```
User: C:\\Downloads\\documents.zip
Bot: 📦 Archive file detected: documents.zip
     ❓ Do you want to extract and process all documents?

User: yes
Bot: 🔄 Extracting archive...
     Found 3 documents
     ✅ Processing complete!
```

## File Structure

```
documents/
  cases/
    KYC-2024-001/
      KYC-2024-001_DOC_001.pdf  (passport.pdf)
      KYC-2024-001_DOC_002.jpg  (utility_bill.jpg)
      file_mapping.json
    AML-CASE-123/
      AML-CASE-123_DOC_001.pdf
      file_mapping.json
  temp_extract/  (temporary extraction folder)
```

## Configuration Updates Needed

### config/paths.json
```json
{
  "paths": {
    "cases_dir": "documents/cases",
    "temp_extract_dir": "documents/temp_extract"
  }
}
```

## Next Steps

1. Fix multiline string syntax in chat_interface.py (lines 509-512, 567-572)
2. Add unit tests for all new methods
3. Test end-to-end workflow with real documents
4. Add error handling for edge cases:
   - Invalid case references
   - Corrupted archives
   - Permission errors
5. Implement progress indicators for large batches
6. Add case management commands:
   - `/switch-case <ref>` - Switch active case
   - `/list-cases` - Show all cases
   - `/case-info` - Show current case details
7. Document intake agent enhancements (next phase)

## Benefits

1. **Organized Storage**: All documents for a case in one folder
2. **Audit Trail**: File mapping preserves original filenames
3. **User Guidance**: Step-by-step workflow prevents errors
4. **Batch Processing**: Handle multiple documents efficiently
5. **Flexible Input**: Supports files, folders, and archives
6. **Confirmation Prompts**: Prevents accidental batch processing
