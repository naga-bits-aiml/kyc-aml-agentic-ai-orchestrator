# OCR Agent Quick Start Guide

## Installation & Setup

### 1. Environment Setup
```bash
# Virtual environment already created at .venv
source .venv/bin/activate

# All dependencies installed, verify with:
python -c "from agents import DocumentExtractionAgent, OCRAPIClient; print('✓ Ready')"
```

### 2. Optional: Install Tesseract (Local OCR)
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Verify installation
tesseract --version
```

### 3. Configure LLM (Optional for basic extraction)
```bash
# Set your preferred LLM API key
export OPENAI_API_KEY="sk-..."  # For OpenAI
# OR
export GOOGLE_API_KEY="..."      # For Google Gemini
```

## Basic Usage

### Simple PDF Text Extraction
```python
from agents import DocumentExtractionAgent

# Initialize agent
agent = DocumentExtractionAgent()

# Extract text from PDF
result = agent.extract_from_document(
    file_path="path/to/document.pdf",
    metadata={"user_id": "123", "document_type": "invoice"}
)

# Result contains:
# - extracted_text: The extracted document text
# - quality_score: Quality assessment (0-1.0)
# - method_used: Which extraction method was used
# - processing_time: How long it took
# - stored_path: Where the extraction was saved
```

### Image/Scanned Document OCR
```python
# For images, the agent automatically uses OCR
result = agent.extract_from_document(
    file_path="path/to/scanned_document.jpg"
)

# Supports: PNG, JPG, JPEG, BMP, TIFF, GIF
```

### DOCX or Text Files
```python
# Works with multiple formats
formats_supported = {
    '.pdf': 'PDF (text + OCR for scanned)',
    '.docx': 'Microsoft Word',
    '.doc': 'Microsoft Word (legacy)',
    '.txt': 'Plain text',
    '.jpg': 'Image (OCR)',
    '.png': 'Image (OCR)',
}

for file_format, description in formats_supported.items():
    result = agent.extract_from_document(f"sample{file_format}")
```

## Advanced Usage

### Using OCR API Client Directly
```python
from agents import OCRAPIClient

# Initialize with specific provider
client = OCRAPIClient(provider='azure')  # or 'aws', 'google', 'tesseract'

# Health check
is_healthy = client.health_check()

# Extract from single document
text = client.extract_text(
    file_path="document.jpg",
    language="eng"
)

# Batch extraction
results = client.extract_batch(
    file_paths=["doc1.jpg", "doc2.jpg", "doc3.jpg"]
)
```

### Quality Assessment
```python
from tools.extraction_tools import check_extraction_quality

# Check quality of extracted text
quality = check_extraction_quality(extracted_text)

print(f"Quality Score: {quality['score']}")
print(f"Status: {quality['status']}")  # excellent, good, acceptable, poor
print(f"Issues: {quality['issues']}")

# Quality > 0.7 is generally good
if quality['score'] > 0.7:
    print("High quality extraction!")
else:
    print("Consider re-extracting with different method")
```

### Document Type Analysis
```python
from tools.extraction_tools import analyze_document_type

# Determine best extraction method
analysis = analyze_document_type("document.pdf")
print(analysis)  # "investigation_needed: PDF requires content analysis"

# Based on extension:
# - .jpg, .png, .tiff → "ocr_required"
# - .docx, .doc → "direct_extraction"
# - .txt, .csv, .json → "direct_extraction"
# - .pdf → "investigation_needed"
```

## Configuration

### config/api.json
```json
{
  "ocr": {
    "base_url": "${OCR_API_BASE_URL}",
    "api_key": "${OCR_API_KEY}",
    "timeout": 60,
    "provider": "tesseract",
    "confidence_threshold": 0.7
  }
}
```

### Environment Override
```bash
# Override config values with environment variables
export OCR_API_BASE_URL="https://api.example.com"
export OCR_API_KEY="your-api-key"
export OCR_PROVIDER="azure"
export OCR_TIMEOUT="120"
```

## Output Structure

### Extraction Result
```python
{
    "success": True,
    "extracted_text": "...full document text...",
    "quality_score": 0.92,
    "quality_status": "excellent",
    "method_used": "pdfplumber",  # or "ocr_api", "tesseract"
    "file_path": "path/to/document.pdf",
    "processing_time_seconds": 2.34,
    "stored_path": "/path/to/documents/extracted/...",
    "metadata": {
        "page_count": 5,
        "word_count": 1234,
        "extraction_timestamp": "2024-01-18T22:07:00"
    }
}
```

## Error Handling

```python
from agents import DocumentExtractionAgent

agent = DocumentExtractionAgent()

try:
    result = agent.extract_from_document("document.pdf")
    
    if not result['success']:
        print(f"Extraction failed: {result.get('error')}")
    elif result['quality_score'] < 0.5:
        print("Warning: Low quality extraction detected")
    else:
        print(f"Success! Extracted {result['metadata']['word_count']} words")
        
except FileNotFoundError:
    print("Document file not found")
except Exception as e:
    print(f"Error: {e}")
```

## Integration with Orchestrator

```python
from agents import DocumentIntakeAgent, DocumentClassifierAgent, DocumentExtractionAgent

# Full workflow
intake = DocumentIntakeAgent()
classifier = DocumentClassifierAgent()
extractor = DocumentExtractionAgent()

# 1. Intake
document = intake.validate_document("path/to/file.pdf", "user_provided_name.pdf")

# 2. Classify
classification = classifier.classify_document(document['internal_path'])

# 3. Extract text
extraction = extractor.extract_from_document(document['internal_path'])

# Store results
results = {
    "intake": document,
    "classification": classification,
    "extraction": extraction
}
```

## Performance Tips

1. **PDF Files**: Use pdfplumber for searchable PDFs (fastest)
2. **Scanned Documents**: Use local Tesseract for privacy/speed, API for accuracy
3. **Batch Processing**: Use extract_batch() for multiple files
4. **Quality Assessment**: Check quality_score before further processing
5. **Caching**: Store extraction results to avoid re-processing

## Troubleshooting

### Issue: "Tesseract not found"
```bash
# Install Tesseract
brew install tesseract  # macOS
sudo apt-get install tesseract-ocr  # Linux

# Or configure path in config
export TESSDATA_PREFIX="/usr/local/share/tessdata"
```

### Issue: "API timeout"
```python
# Increase timeout in config
from utilities.config_loader import ConfigLoader
config = ConfigLoader()
config.ocr_timeout = 120  # seconds
```

### Issue: "Low quality extraction"
```python
# Try different provider
agent = DocumentExtractionAgent(
    ocr_api_client=OCRAPIClient(provider='azure')
)
```

---

**For more details, see:**
- OCR_SETUP.md - Detailed configuration and troubleshooting
- OCR_FIXES_SUMMARY.md - What was fixed and validated
- agents/document_extraction_agent.py - Source code
