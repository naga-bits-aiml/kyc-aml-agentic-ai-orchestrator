# 🚀 KYC-AML Agentic AI Orchestrator - Usage Guide

**Version**: 1.0.1  
**Status**: ✅ Production Ready  
**Last Updated**: January 26, 2026

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [System Overview](#-system-overview)
- [Usage Methods](#-usage-methods)
- [Document Processing](#-document-processing)
- [Configuration](#-configuration)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Quick Start

### 1. Run the Demo

The fastest way to see the system in action:

```bash
python examples/quick_start_demo.py
```

This demo will:
- Initialize the orchestrator
- Process sample KYC documents
- Show complete workflow results

### 2. Process Your Documents

**CLI Method:**
```bash
# Single document
python main.py --documents path/to/document.pdf

# Multiple documents
python main.py --documents doc1.pdf doc2.jpg doc3.docx

# Batch mode (faster for multiple documents)
python main.py --documents doc1.pdf doc2.pdf --batch
```

**Chat Interface:**
```bash
python chat_interface.py
```

**Web Interface:**
```bash
python web_chat.py
```

---

## 🔍 System Overview

### What It Does

The KYC-AML Orchestrator automates document processing for Know Your Customer (KYC) and Anti-Money Laundering (AML) workflows:

1. **Document Intake**: Validates and stores documents securely
2. **Text Extraction**: Extracts text using intelligent methods (direct extraction or OCR)
3. **Classification**: Categorizes documents (passport, utility bill, ID, etc.)

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Orchestrator                       │
│  (Coordinates all agents and workflow)              │
└───────────┬─────────────┬─────────────┬────────────┘
            │             │             │
    ┌───────▼──────┐ ┌───▼──────┐ ┌───▼──────────┐
    │   Intake     │ │Extraction│ │Classification│
    │    Agent     │ │  Agent   │ │    Agent     │
    └──────────────┘ └──────────┘ └──────────────┘
```

### Supported File Formats

- **Documents**: PDF, DOCX, DOC, TXT
- **Images**: JPG, JPEG, PNG
- **Max Size**: 10MB per file

---

## 🎮 Usage Methods

### Method 1: Command-Line Interface (CLI)

Best for: Batch processing, automation, scripting

```bash
# Basic usage
python main.py --documents file1.pdf file2.jpg

# Batch classification
python main.py --documents *.pdf --batch

# Use CrewAI workflow
python main.py --documents file.pdf --use-crew

# Check system health
python main.py --health-check
```

**CLI Options:**
- `--documents, -d`: Document paths to process
- `--batch`: Use batch classification endpoint
- `--use-crew`: Use CrewAI workflow coordination
- `--health-check`: Check classifier API health

### Method 2: Interactive Chat Interface

Best for: Interactive processing, guided workflow

```bash
python chat_interface.py
```

**Chat Commands:**
- `help` - Show help information
- `status` - Show processing status
- `history` - Show chat history
- `clear` - Clear chat history
- `health` - Check system health
- `exit` - Exit the chat

**Workflow:**
1. Set a case reference (e.g., "KYC-2026-001")
2. Provide document path or describe what you want to process
3. Review results

### Method 3: Web Interface

Best for: Visual interface, non-technical users

```bash
python web_chat.py
```

Then open your browser to the URL shown (typically http://localhost:8501)

**Features:**
- File upload interface
- Visual document preview
- Real-time processing status
- Result visualization

---

## 📄 Document Processing

### Processing Flow

```
Document Input
    ↓
Intake & Validation
    ↓
Text Extraction (Direct or OCR)
    ↓
Classification
    ↓
Results & Storage
```

### Extraction Methods

The system intelligently chooses the best extraction method:

1. **Direct Text Extraction** (Fastest)
   - For PDFs with searchable text
   - DOCX, TXT files
   - Quality score: Usually 1.0

2. **Local OCR (Tesseract)** (Medium)
   - For scanned documents
   - Image files (JPG, PNG)
   - Quality score: 0.5-0.9

3. **API-based OCR** (High quality)
   - For complex documents
   - Fallback when local OCR fails
   - Quality score: 0.7-1.0

### Storage Structure

```
documents/
├── intake/          # Validated documents with unique names
├── extracted/       # Extracted text files
├── processed/       # Classified documents
└── cases/          # Case-specific document folders
    └── KYC-2026-001/
        ├── KYC-2026-001_DOC_001.pdf
        └── KYC-2026-001_DOC_002.jpg
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# LLM Configuration (choose one)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# OCR Configuration (optional)
OCR_PROVIDER=tesseract
TESSERACT_CMD=/usr/local/bin/tesseract

# Classifier API (optional)
CLASSIFIER_API_URL=http://localhost:8000
CLASSIFIER_API_KEY=your-api-key
```

### Configuration Files

Located in `config/`:

- **app.json**: Application settings, file validation
- **llm.json**: LLM provider configuration
- **api.json**: API endpoints and settings
- **paths.json**: Directory paths
- **logging.json**: Logging configuration

### Key Settings

**Document Validation** (`config/app.json`):
```json
{
  "document_validation": {
    "max_size_mb": 10,
    "allowed_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".txt"]
  }
}
```

**LLM Provider** (`config/llm.json`):
```json
{
  "openai": {
    "model": "gpt-4o-mini",
    "temperature": 0.1
  },
  "google": {
    "model": "gemini-2.5-flash",
    "temperature": 0.1
  }
}
```

---

## 💡 Examples

### Example 1: Process Single Document

```bash
python main.py --documents test_documents/passport_sample.txt
```

**Output:**
```
📄 Processing 1 document(s)...
✅ Intake complete: 1/1 documents validated
✅ Extraction: method=direct_text, quality=1.00
✅ Classification: passport
```

### Example 2: Batch Process Multiple Documents

```bash
python main.py --documents \
  test_documents/passport_sample.txt \
  test_documents/utility_bill_sample.txt \
  test_documents/drivers_license_sample.txt \
  --batch
```

### Example 3: Chat Interface Workflow

```
You: Hello
Assistant: Welcome! Please provide your case reference...

You: KYC-2026-001
Assistant: Case reference set to: KYC-2026-001

You: Process test_documents/passport_sample.txt
Assistant: Processing passport_sample.txt...
✅ Document classified as: passport
```

### Example 4: Python Script Integration

```python
from orchestrator import KYCAMLOrchestrator

# Initialize
orchestrator = KYCAMLOrchestrator(
    temperature=0.1,
    use_batch_classification=True
)

# Process documents
results = orchestrator.process_documents([
    "documents/passport.pdf",
    "documents/utility_bill.jpg"
])

# Access results
print(f"Status: {results['status']}")
print(f"Validated: {results['summary']['validated']}")
```

---

## 🔧 Troubleshooting

### Common Issues

**1. Import Errors**

```
Error: ModuleNotFoundError: No module named 'crewai'
```

**Solution:**
```bash
pip install -r requirements.txt
```

**2. LLM Configuration**

```
Error: No valid LLM configuration found
```

**Solution:**
- Create `.env` file
- Add `OPENAI_API_KEY` or `GOOGLE_API_KEY`

**3. File Not Validated**

```
Error: Invalid file extension
```

**Solution:**
- Check `config/app.json` allowed_extensions
- Ensure file format is supported

**4. OCR Not Working**

```
Error: Tesseract not found
```

**Solution:**
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### System Health Check

```bash
python main.py --health-check
```

This checks:
- ✅ Configuration loaded
- ✅ LLM connection
- ✅ Classifier API (if configured)
- ✅ OCR availability

---

## 📚 Additional Resources

- **Quick Start**: `docs/QUICKSTART.md`
- **Implementation Status**: `docs/IMPLEMENTATION_STATUS.md`
- **Chat Guide**: `docs/CHAT_GUIDE.md`
- **Model Configuration**: `docs/MODEL_GUIDE.md`
- **OCR Setup**: `docs/OCR_SETUP.md`

---

## 🆘 Support

For issues or questions:
1. Check the documentation in `docs/`
2. Review test scripts in `tests/`
3. Run the demo: `python examples/quick_start_demo.py`
4. Check logs in `logs/` directory

---

## ✅ Verification Checklist

Before using in production:

- [ ] Environment variables configured
- [ ] LLM API key added to `.env`
- [ ] Test documents processed successfully
- [ ] All tests pass: `python tests/test_complete_workflow.py`
- [ ] Demo runs successfully: `python examples/quick_start_demo.py`
- [ ] System health check passes: `python main.py --health-check`

---

**System Status**: ✅ Production Ready  
**Documentation Version**: 1.0.1  
**Last Tested**: January 26, 2026
