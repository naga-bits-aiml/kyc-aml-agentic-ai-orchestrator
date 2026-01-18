# OCR Extraction Agent - Setup Guide

## Overview

The OCR Extraction Agent intelligently extracts text from documents using the most appropriate method:
- **Direct Extraction**: For PDFs with text layers, DOCX, TXT files
- **OCR API**: External OCR services (AWS Textract, Azure Vision, Google Vision)
- **Local OCR**: Tesseract for offline processing

## Configuration

### 1. Environment Variables (.env)

```env
# OCR API Configuration (Optional)
OCR_API_BASE_URL=https://your-ocr-api.com/api/v1
OCR_API_KEY=your_ocr_api_key_here
```

### 2. Config File (config/api.json)

The OCR configuration is already added:

```json
{
  "api": {
    "ocr": {
      "base_url": "${OCR_API_BASE_URL}",
      "api_key": "${OCR_API_KEY}",
      "timeout": 60,
      "max_retries": 3,
      "retry_delay": 2,
      "provider": "tesseract",
      "confidence_threshold": 0.7
    }
  }
}
```

**Configuration Options**:
- `base_url`: OCR API endpoint (leave empty for local-only)
- `api_key`: API authentication key
- `timeout`: Request timeout in seconds (60s for OCR is recommended)
- `max_retries`: Number of retry attempts on failure
- `provider`: OCR provider (`tesseract`, `azure`, `aws`, `google`)
- `confidence_threshold`: Minimum confidence score (0.0-1.0)

## Installation

### Prerequisites

**1. Python Dependencies** (already in requirements.txt):
```bash
pip install pdfplumber pytesseract pdf2image pillow PyPDF2 python-docx
```

**2. Tesseract OCR (for local OCR)**:

**macOS**:
```bash
brew install tesseract
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows**:
- Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH: `C:\Program Files\Tesseract-OCR`

**Verify Installation**:
```bash
tesseract --version
```

## Usage

### Basic Usage

```python
from agents import DocumentExtractionAgent

# Initialize agent
extraction_agent = DocumentExtractionAgent()

# Extract from a document
result = extraction_agent.extract_from_document("document.pdf")

print(f"Method: {result['method']}")
print(f"Confidence: {result['confidence']}")
print(f"Quality Score: {result['quality_score']}")
print(f"Text: {result['text'][:100]}...")
```

### Batch Processing

```python
# Extract from multiple documents
file_paths = ["doc1.pdf", "doc2.jpg", "doc3.docx"]
results = extraction_agent.extract_batch(file_paths)

for result in results:
    print(f"{result['file_path']}: {result['status']}")
```

### With CrewAI Task

```python
from crewai import Crew, Process

# Create extraction task
extraction_task = extraction_agent.create_extraction_task(file_paths)

# Create crew
crew = Crew(
    agents=[extraction_agent.agent],
    tasks=[extraction_task],
    process=Process.sequential
)

# Execute
result = crew.kickoff()
```

## Extraction Methods

The agent intelligently chooses the best method:

| File Type | Condition | Method | Speed | Accuracy |
|-----------|-----------|--------|-------|----------|
| **TXT, CSV** | Always | Direct read | ⚡ Instant | ✅ Perfect |
| **DOCX** | Always | python-docx | ⚡ Fast | ✅ Excellent |
| **PDF** | Has text layer | pdfplumber/PyPDF2 | ⚡ Fast | ✅ Excellent |
| **PDF** | Scanned (no text) | OCR API/Local | 🐌 Slow | ⚠️ Good |
| **Images** | JPG, PNG, etc. | OCR API/Local | 🐌 Slow | ⚠️ Good |

## Quality Assessment

Extracted text is automatically scored (0.0-1.0) based on:
- **Length**: Minimum meaningful content
- **Character distribution**: Reasonable alpha-numeric ratio
- **Special characters**: Not excessive (OCR artifacts)

```python
result = extraction_agent.extract_from_document("scan.pdf")

if result['quality_score'] > 0.8:
    print("✅ High quality extraction")
elif result['quality_score'] > 0.5:
    print("⚠️  Acceptable quality - review recommended")
else:
    print("❌ Low quality - manual review required")
```

## Storage

Extracted text is automatically stored:

```
documents/extracted/
├── document_name.txt              # Extracted text
└── document_name_metadata.json    # Extraction metadata
```

**Metadata includes**:
- Extraction method used
- Confidence score
- Quality score
- Timestamp
- Original file path

## Testing

Run the test script:

```bash
python tests/test_ocr_agent.py
```

The test will:
1. Initialize OCR client and extraction agent
2. Analyze document types
3. Test extraction on sample documents
4. Display configuration status

## OCR Provider Options

### 1. Local Tesseract (Free, Offline)

**Pros**: Free, no API calls, works offline  
**Cons**: Slower, lower accuracy than cloud APIs

**Setup**: Just install Tesseract (see above)

### 2. AWS Textract (Best for Forms/Tables)

**Pros**: Excellent for structured documents, tables, forms  
**Cons**: Requires AWS account, costs money

**Setup**:
```env
OCR_API_BASE_URL=https://your-textract-api.com/extract
OCR_API_KEY=your_aws_api_key
```

### 3. Azure Computer Vision (General Purpose)

**Pros**: Good general accuracy, reasonable pricing  
**Cons**: Requires Azure account

**Setup**:
```env
OCR_API_BASE_URL=https://your-region.api.cognitive.microsoft.com/vision/v3.2/ocr
OCR_API_KEY=your_azure_key
```

### 4. Google Cloud Vision (High Accuracy)

**Pros**: Excellent accuracy, multiple languages  
**Cons**: Requires Google Cloud account

**Setup**:
```env
OCR_API_BASE_URL=https://vision.googleapis.com/v1/images:annotate
OCR_API_KEY=your_google_api_key
```

## Troubleshooting

### "Tesseract not found"
```bash
# Verify installation
which tesseract  # macOS/Linux
where tesseract  # Windows

# If not found, reinstall Tesseract
```

### "OCR API timeout"
- Increase `timeout` in config/api.json to 120 for large files
- Check network connectivity
- Verify API key is valid

### "Low quality score"
- For scanned documents, try higher DPI scanning (300+ DPI)
- Use OCR API instead of local Tesseract
- Clean/enhance image before OCR (contrast, rotation)

### "PDF extraction empty"
- PDF might be scanned - agent will auto-fallback to OCR
- Check if PDF has security restrictions
- Try opening PDF in a viewer first

## Next Steps

1. **Test with your documents**: Place samples in `test_documents/`
2. **Configure OCR API**: If using cloud OCR, set environment variables
3. **Integrate with orchestrator**: Add extraction step to workflow
4. **Monitor quality**: Review extraction quality scores regularly

## API Integration Example

If you're building an OCR API to use with this agent:

**Expected Request Format**:
```json
{
  "file_content": "base64_encoded_content",
  "file_name": "document.pdf",
  "language": "eng",
  "extract_metadata": true,
  "provider": "tesseract"
}
```

**Expected Response Format**:
```json
{
  "text": "Extracted text content...",
  "confidence": 0.95,
  "metadata": {
    "pages": 2,
    "language": "eng",
    "processing_time": 2.3
  }
}
```

## Support

For issues or questions:
- Check logs in `logs/kyc_aml_orchestrator.log`
- Run test script: `python tests/test_ocr_agent.py`
- Review extracted files in `documents/extracted/`
