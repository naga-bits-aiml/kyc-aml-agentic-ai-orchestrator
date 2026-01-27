# Production-Grade KYC-AML Document Processing Architecture

**Last Updated**: January 28, 2026  
**Status**: ✅ Production Ready

## Overview

The KYC-AML Agentic AI Orchestrator is a production-grade document processing system with comprehensive logging, clear processing stages, and robust error handling.

## Architecture Principles

### 1. **Clear Processing Stages**
Every document goes through well-defined stages:
- **Intake** → **Classification** → **Extraction** → **Processed**

### 2. **Comprehensive Logging**
All critical operations are logged with full details:
- 🔧 API Client Initialization
- 🌐 API Requests (method, URL, file details)
- 🎯 Classifier Predictions (class, confidence, probabilities)
- 📄 File Generation (PDF → images conversion)
- 🔄 Stage Transitions
- 🚀 Pipeline Start/Complete

### 3. **Simple & Clear**
- No complex API discovery - direct `/predict` endpoint usage
- Existing logger infrastructure - no additional complexity
- Clear error messages and status tracking

## System Components

```
┌──────────────────────────────────────────────────────────────┐
│                    Document Processing Pipeline               │
│                                                                │
│  ┌────────────┐   ┌──────────────┐   ┌─────────────┐        │
│  │   INTAKE   │──▶│CLASSIFICATION│──▶│ EXTRACTION  │──▶Done  │
│  └────────────┘   └──────────────┘   └─────────────┘        │
│        │                  │                   │               │
│        ▼                  ▼                   ▼               │
│   Validate           Classify            Extract Text         │
│   Convert PDF        via /predict        via OCR              │
│   Store Metadata     API                 Store Results        │
└──────────────────────────────────────────────────────────────┘
```

## Critical Logging Points

### 1. API Client Initialization
```
================================================================================
🔧 CLASSIFIER API CLIENT INITIALIZED
================================================================================
Base URL: http://35.184.130.36/api/kyc_document_classifier/v1
Endpoint: /predict
Timeout: 30s
Supported: Aadhar, Driving License, PAN Card, Passport, Voter ID
================================================================================
```

### 2. API Requests
```
================================================================================
🌐 API REQUEST: Document Classification
================================================================================
Method: POST
URL: http://35.184.130.36/api/kyc_document_classifier/v1/predict
File: passport_sample.jpg
Path: /path/to/passport_sample.jpg
Size: 45,678 bytes (44.61 KB)
Extension: .jpg
================================================================================
```

### 3. Classification Predictions
```
================================================================================
🎯 CLASSIFIER PREDICTION RESULT
================================================================================
Document: passport_sample.jpg
Predicted Class: Passport
Confidence: 95.67%
Success: True
Duration: 1.234s
All Probabilities:
  - Passport: 95.67%
  - Voter ID: 2.34%
  - Aadhar: 1.23%
  - Driving License: 0.56%
  - PAN Card: 0.20%
================================================================================
```

### 4. File Generation (PDF → Images)
```
================================================================================
📄 FILES GENERATED: PDF to Image Conversion
================================================================================
Source PDF: multi_page_document.pdf
Source Path: /path/to/multi_page_document.pdf
Source Document ID: DOC_20260128_123456_ABC123
Pages Converted: 3
DPI: 200
Format: JPEG
Child Document IDs:
  - DOC_20260128_123457_DEF456
  - DOC_20260128_123458_GHI789
  - DOC_20260128_123459_JKL012
Generated Files:
  - DOC_20260128_123457_DEF456_page1.jpg
  - DOC_20260128_123458_GHI789_page2.jpg
  - DOC_20260128_123459_JKL012_page3.jpg
================================================================================
```

## Processing Flow

### Stage 1: Document Intake
**Purpose**: Validate and prepare documents for processing

**Operations**:
1. Validate file format, size, and integrity
2. Generate unique document ID
3. Store file in intake directory
4. Create metadata JSON
5. If PDF: Convert to images and create child documents

**Logging**:
- Document validation status
- File storage location
- Metadata creation
- PDF conversion (if applicable)

### Stage 2: Document Classification
**Purpose**: Identify document type using ML classifier

**Operations**:
1. Call `/predict` API endpoint with document
2. Receive prediction with confidence scores
3. Store classification in metadata
4. Move to classification stage directory

**Logging**:
- API request details (URL, file, size)
- Prediction result (class, confidence, all probabilities)
- Performance metrics (duration)
- Error details (if failed)

**API Endpoint**: `/predict`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Request**: `file` (image: JPEG, PNG, BMP, TIFF)
- **Response**:
  ```json
  {
    "predicted_class": "Passport",
    "confidence": 0.9567,
    "probabilities": {
      "Passport": 0.9567,
      "Voter ID": 0.0234,
      "Aadhar": 0.0123,
      "Driving License": 0.0056,
      "PAN Card": 0.0020
    },
    "success": true
  }
  ```

### Stage 3: Data Extraction
**Purpose**: Extract text and structured data from documents

**Operations**:
1. Apply OCR (if image)
2. Extract text (if PDF)
3. Parse structured data
4. Store extraction results in metadata
5. Move to extraction/processed stage

**Logging**:
- Extraction method used
- Text length extracted
- Structured data found
- Final status

## Error Handling

### Retry Logic
- API requests: 3 attempts with exponential backoff
- Timeouts: Configurable per operation
- Graceful degradation: Continue with partial results

### Error Logging
```
================================================================================
❌ CLASSIFICATION FAILED
================================================================================
File: document.jpg
URL: http://api.example.com/predict
Duration: 2.345s
Error Type: ConnectionError
Error: Connection timeout after 30s
================================================================================
```

## Configuration

### API Settings (`config/api.json`)
```json
{
  "classifier_api": {
    "base_url": "http://35.184.130.36/api/kyc_document_classifier/v1",
    "endpoint": "/predict",
    "timeout": 30,
    "max_retries": 3
  }
}
```

### Logging Settings (`config/logging.json`)
- **Level**: DEBUG (development), INFO (production)
- **Handlers**: Console, File, Error File
- **Format**: Structured with timestamps
- **Rotation**: 10MB per file, 5 backups

## Document Metadata Structure

Each document has a metadata JSON file tracking its journey:

```json
{
  "document_id": "DOC_20260128_123456_ABC123",
  "original_filename": "passport.jpg",
  "stored_path": "/documents/intake/DOC_20260128_123456_ABC123.jpg",
  "stage": "classification",
  "uploaded_at": "2026-01-28T12:34:56",
  
  "intake": {
    "status": "success",
    "msg": "Document validated successfully",
    "timestamp": "2026-01-28T12:34:56"
  },
  
  "classification": {
    "status": "success",
    "predicted_class": "Passport",
    "confidence": 0.9567,
    "probabilities": {...},
    "timestamp": "2026-01-28T12:35:23"
  },
  
  "extraction": {
    "status": "pending"
  }
}
```

## Best Practices

### 1. Always Check Logs
- Use `logger.critical()` for important events
- Use `logger.error()` for failures
- Use `logger.info()` for progress updates

### 2. Handle PDFs Properly
- Always convert PDFs to images before classification
- Track child documents in parent metadata
- Process child documents after parent completes

### 3. Monitor API Health
- Check API availability before batch processing
- Handle rate limits and timeouts
- Log all API interactions for debugging

### 4. Validate at Each Stage
- Check file exists before processing
- Validate API responses
- Verify metadata consistency

## Troubleshooting

### Common Issues

1. **Classification API Not Responding**
   - Check: `logger.critical()` logs for API initialization
   - Check: API URL configuration in `config/api.json`
   - Check: Network connectivity

2. **No Classification Results**
   - Check: File format (must be image for /predict)
   - Check: File size (not too large)
   - Check: API response in logs

3. **PDF Conversion Fails**
   - Check: `pdf2image` is installed
   - Check: Poppler is installed (system dependency)
   - Check: Source PDF is valid

4. **Missing Logs**
   - Check: Logging configuration in `config/logging.json`
   - Check: Log directory exists and is writable
   - Check: Log level is appropriate (DEBUG vs INFO)

## Monitoring

### Key Metrics to Track
- API response time (logged per request)
- Classification confidence scores
- Success/failure rates per stage
- Processing time per document
- Queue depth at each stage

### Log Analysis
```bash
# Find all API requests
grep "🌐 API REQUEST" logs/kyc_aml_orchestrator.log

# Find all predictions
grep "🎯 CLASSIFIER PREDICTION" logs/kyc_aml_orchestrator.log

# Find all file generations
grep "📄 FILES GENERATED" logs/kyc_aml_orchestrator.log

# Find all errors
grep "❌" logs/errors.log
```

## Future Enhancements

1. **Real-time Monitoring Dashboard**
   - Live view of processing pipeline
   - API health status
   - Performance metrics

2. **Automated Testing**
   - Unit tests for each component
   - Integration tests for full pipeline
   - Performance benchmarks

3. **Advanced Error Recovery**
   - Automatic retry with backoff
   - Circuit breaker for failing APIs
   - Dead letter queue for failed documents

4. **Scalability**
   - Parallel processing of documents
   - Load balancing across API instances
   - Distributed queue management

---

## Quick Reference

### Start Processing
```bash
python chat_interface.py
```

### Check Logs
```bash
tail -f logs/kyc_aml_orchestrator.log
```

### View Errors
```bash
tail -f logs/errors.log
```

### API Health Check
```python
from agents.classifier_api_client import ClassifierAPIClient

client = ClassifierAPIClient()
is_healthy = client.health_check()
print(f"API Health: {'✅ OK' if is_healthy else '❌ FAILED'}")
```

---

**Remember**: Every critical operation is logged. Check the logs first when troubleshooting!
