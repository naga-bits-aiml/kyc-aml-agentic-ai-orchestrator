# 🔍 Smart Case Management Guide

**Feature**: Intelligent Case Retrieval and Resume  
**Version**: 1.0.2  
**Date**: January 26, 2026

---

## Overview

Your KYC-AML agents are now **smart enough to retrieve and continue working on existing cases**. The system automatically detects existing cases, loads their history, and allows seamless continuation of work.

---

## Key Capabilities

### ✅ What Your Agents Can Do

1. **Detect Existing Cases**
   - Automatically recognize when a case reference already exists
   - Load case information and document history

2. **Resume Work Seamlessly**
   - Continue adding documents to existing cases
   - Maintain case context across sessions
   - Track all case activities with metadata

3. **Smart Case Listing**
   - View all available cases
   - See document counts and dates
   - Check case status

4. **Automatic Metadata Tracking**
   - Creation date
   - Last updated timestamp
   - Document count
   - Processing status
   - File mappings

---

## How It Works

### Creating a New Case

```
User: KYC-2026-001

Agent Response:
✅ New Case Created: KYC-2026-001

📁 Case directory: documents/cases/KYC-2026-001

You can now:
• Upload individual documents
• Provide a folder path containing multiple documents
• Upload archive files for batch processing
```

### Retrieving an Existing Case

```
User: KYC-2026-001

Agent Response:
🔍 Existing Case Found: KYC-2026-001

📊 Case Summary:
  • Documents: 3
  • Created: 2026-01-26 10:30
  • Last Updated: 2026-01-26 15:45

📄 Existing Documents:
  1. KYC-2026-001_DOC_001.pdf (passport)
  2. KYC-2026-001_DOC_002.jpg (utility bill)
  3. KYC-2026-001_DOC_003.docx (bank statement)

✅ Case loaded successfully!

You can now:
• Add more documents to this case
• Review existing case documents
• Continue processing
```

---

## Usage Examples

### Example 1: Resume an Existing Case

**Scenario**: User needs to add more documents to a case from last week

```bash
# Start chat interface
python chat_interface.py

# User provides existing case reference
You: KYC-2024-0145

# System detects and loads existing case
Agent: 🔍 Existing Case Found: KYC-2024-0145
       📊 Case Summary:
          • Documents: 5
          • Created: 2024-01-15 09:00
          • Last Updated: 2024-01-15 14:30
       
       You can continue working on this case!

# User adds more documents
You: test_documents/additional_proof.pdf

# System adds to existing case
Agent: ✅ Processing complete!
       Document added to case KYC-2024-0145
       Total documents: 6
```

### Example 2: List All Cases

```bash
# In chat interface
You: cases

Agent: 📋 Available Cases:

       📁 KYC-2024-0145
          • Documents: 6
          • Created: 2024-01-15 09:00
          • Status: active

       📁 AML-CASE-789
          • Documents: 3
          • Created: 2024-01-18 11:20
          • Status: active

       📁 CUSTOMER-XYZ
          • Documents: 2
          • Created: 2024-01-20 16:45
          • Status: processing

       To resume a case, simply provide its case reference.
```

### Example 3: Python API

```python
from chat_interface import ChatInterface

# Create interface
chat = ChatInterface()

# Set case reference (will load if exists)
response = chat.set_case_reference("KYC-2024-0145")
print(response)

# Check if case existed
if "Existing Case Found" in response:
    print("Resuming existing case")
else:
    print("Created new case")

# Add documents
chat._process_documents([
    "new_document1.pdf",
    "new_document2.jpg"
])

# List all cases
cases = chat.list_all_cases()
print(cases)
```

---

## Commands

### Chat Interface Commands

| Command | Description |
|---------|-------------|
| `cases`, `/cases` | List all available cases |
| `[case-ref]` | Create or resume a case |
| `help` | Show help information |
| `status` | Show current processing status |

### Case Reference Format

- Use clear, meaningful references
- Examples: `KYC-2026-001`, `AML-CASE-123`, `CUSTOMER-456`
- Case-insensitive (automatically converted to uppercase)

---

## Case Directory Structure

```
documents/
└── cases/
    ├── KYC-2026-001/
    │   ├── case_metadata.json          # Case information
    │   ├── file_mapping.json           # Original → Internal name mapping
    │   ├── KYC-2026-001_DOC_001.pdf   # Document 1
    │   ├── KYC-2026-001_DOC_002.jpg   # Document 2
    │   └── KYC-2026-001_DOC_003.docx  # Document 3
    │
    └── AML-CASE-789/
        ├── case_metadata.json
        ├── file_mapping.json
        └── AML-CASE-789_DOC_001.pdf
```

### Case Metadata (case_metadata.json)

```json
{
  "case_reference": "KYC-2026-001",
  "created_date": "2026-01-26 10:30",
  "last_updated": "2026-01-26 15:45",
  "document_count": 3,
  "status": "active",
  "last_processing": "success"
}
```

### File Mapping (file_mapping.json)

```json
{
  "KYC-2026-001_DOC_001.pdf": "passport.pdf",
  "KYC-2026-001_DOC_002.jpg": "utility_bill.jpg",
  "KYC-2026-001_DOC_003.docx": "bank_statement.docx"
}
```

---

## Benefits

### 1. **Seamless Continuation**
   - Pick up where you left off
   - No need to resubmit documents
   - Maintains complete case history

### 2. **Multi-Session Support**
   - Works across different chat sessions
   - Works across application restarts
   - Persistent case storage

### 3. **Audit Trail**
   - Tracks when case was created
   - Records all updates
   - Maintains document history

### 4. **Organized Storage**
   - All case documents in one place
   - Internal document references
   - Original filename mapping preserved

---

## Technical Details

### Case Detection Logic

```python
def set_case_reference(self, case_ref: str):
    """Smart case reference setter with retrieval."""
    case_dir = Path(settings.documents_dir) / "cases" / case_ref
    
    # Check if case exists
    case_exists = case_dir.exists() and any(case_dir.iterdir())
    
    if case_exists:
        # Load existing case
        case_info = self._load_existing_case(case_dir)
        # Show case summary with existing documents
        ...
    else:
        # Create new case
        case_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_case_metadata(case_dir)
        ...
```

### Metadata Updates

The system automatically updates case metadata:
- When a new document is added
- After successful processing
- On status changes

---

## Testing

### Test the Feature

```bash
# Run comprehensive test
python tests/test_case_management.py

# Run interactive demo
python tests/test_case_management.py --demo
```

### Test Scenarios Covered

✅ New case creation  
✅ Document addition to case  
✅ Case retrieval from different session  
✅ Continuing work on existing case  
✅ Case listing  
✅ Metadata tracking  

---

## Best Practices

### 1. **Use Meaningful Case References**
```
✅ Good: KYC-2026-001, CUSTOMER-SMITH-2024
❌ Bad: ABC, TEST, 123
```

### 2. **Check Existing Cases First**
```bash
# List cases before creating new ones
You: cases

# Then decide to resume or create new
You: KYC-2026-001  # Resume if exists
```

### 3. **Add Documents Incrementally**
```python
# Add documents as they arrive
chat.set_case_reference("KYC-2026-001")
chat._process_documents(["new_doc.pdf"])

# Later, add more
chat._process_documents(["another_doc.pdf"])
```

### 4. **Review Case Status**
```bash
# Check case information
You: status

# Shows current case and document count
```

---

## Troubleshooting

### Case Not Found

**Issue**: Case exists but system says it's new

**Solution**: Check case directory exists and has files
```bash
ls documents/cases/YOUR-CASE-REF/
```

### Metadata Not Updating

**Issue**: Case metadata shows old information

**Solution**: Metadata is updated after processing completes
```python
# Ensure processing finished successfully
# Check logs for errors
```

### Can't List Cases

**Issue**: `cases` command returns empty

**Solution**: Cases directory might not exist yet
```bash
mkdir -p documents/cases
```

---

## Future Enhancements

Planned improvements:
- [ ] Case search by document type
- [ ] Case archiving (completed cases)
- [ ] Case export functionality
- [ ] Case sharing between users
- [ ] Advanced filtering and sorting

---

## Summary

Your agents now have **intelligent case management** with:

✅ **Automatic case detection**  
✅ **Seamless case resumption**  
✅ **Complete case history**  
✅ **Metadata tracking**  
✅ **Multi-session support**  

The system is smart enough to:
- Remember previous work
- Continue where you left off
- Track all case activities
- Maintain organized storage

**You can now confidently work on cases across multiple sessions!**

---

**Documentation Version**: 1.0  
**Last Updated**: January 26, 2026  
**Status**: Production Ready ✅
