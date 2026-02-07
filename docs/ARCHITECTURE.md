# Pure CrewAI Architecture

**Last Updated**: January 27, 2026  
**Status**: ✅ Production Ready

## Overview

The KYC-AML Agentic AI Orchestrator uses **pure CrewAI** framework for multi-agent coordination. This architecture provides clean separation of concerns with agents using tools for specialized operations.

## Architecture Components

```
┌──────────────────────────────────────────────────────────────┐
│                    CrewAI Flow Orchestration                  │
│                                                                │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │ Document Intake  │───▶│   Classifier     │               │
│  │ Agent            │    │   Agent          │               │
│  │                  │    │                  │               │
│  │ Tools:           │    │ Tools:           │               │
│  │ • Validate       │    │ • Classify       │               │
│  │ • Organize       │    │ • PDF→Image      │               │
│  └──────────────────┘    └──────────────────┘               │
│           │                        │                         │
│           └────────────┬───────────┘                        │
│                        ▼                                     │
│              ┌──────────────────┐                           │
│              │  Extraction      │                           │
│              │  Agent           │                           │
│              │                  │                           │
│              │  Tools:          │                           │
│              │  • OCR Extract   │                           │
│              │  • Batch Process │                           │
│              └──────────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CrewAI Agents (crew.py)

**KYCAMLCrew** class with four specialized agents:

- **document_intake_agent**: Validates and organizes documents
- **document_classifier_agent**: Classifies documents via API
- **document_extraction_agent**: Extracts text using OCR
- **supervisor_agent**: Coordinates workflow and provides oversight

Each agent uses CrewAI's `@agent` decorator and leverages tools directly.

### 2. CrewAI Tools

**tools/intake_tools.py**:
- `validate_document_tool`: Validates file format, size, and metadata
- `batch_validate_documents_tool`: Batch validation
- `organize_case_documents_tool`: Organizes files by case reference

**tools/classifier_tools.py**:
- `classify_document_tool`: Classifies documents via external API
- `convert_pdf_to_image_tool`: Converts PDFs to images for API compatibility
- `batch_classify_documents_tool`: Batch classification

**tools/extraction_tools.py**:
- `extract_text_from_pdf_tool`: Extracts text from PDFs
- `extract_text_from_image_tool`: OCR for images
- `batch_extract_documents_tool`: Batch extraction

### 3. Flow Orchestration (flows/document_processing_flow.py)

Uses CrewAI's Flow pattern with:
- `@start` decorator for initial intake
- `@listen` decorators for state transitions
- Event-driven workflow progression

### 4. API Clients

**agents/classifier_api_client.py**:
- Handles external classifier API communication
- Automatic PDF-to-image conversion
- Retry logic and error handling

**agents/ocr_api_client.py**:
- Text extraction from documents
- Support for PDFs and images

## Workflow

1. **Intake**: Document validated and organized by intake agent
2. **Classification**: Document classified (with auto PDF→image conversion if needed)
3. **Extraction**: Text extracted using OCR tools
4. **Completion**: Results stored in case directory with metadata

## Key Features

### Pure CrewAI Benefits
- ✅ **Simplified**: No hybrid architecture complexity
- ✅ **Native Tools**: Direct CrewAI tool integration
- ✅ **Reasoning Built-in**: LLMs in agents provide natural reasoning
- ✅ **Maintainable**: Clear separation of concerns
- ✅ **Scalable**: Easy to add new agents/tools

### Smart PDF Handling
The system automatically converts PDFs to images when needed:
- Classification API requires images (JPG/PNG)
- Extraction can handle both PDFs and images
- Conversion happens transparently via `convert_pdf_to_image_tool`

### Case Management
Each case gets:
- Unique case directory: `documents/cases/{case_reference}/`
- Subdirectories: intake/, processed/, extracted/
- Metadata tracking in JSON format

## Configuration

**config/agents.yaml**: Defines 4 agents (intake, classifier, extraction, supervisor)  
**config/tasks.yaml**: Defines 8 tasks for document workflow  
**config/llm.json**: LLM provider settings (OpenAI/Azure/Anthropic/Local)  
**config/api.json**: External API configuration  
**config/paths.json**: Document storage paths

## Running the System

### Via Flow (Recommended)
```bash
.venv/bin/python main.py --case-ref KYC-2024-001 documents/intake/passport.pdf
```

### Via Chat Interface
```bash
.venv/bin/python chat_interface.py
```

### Via Web Interface
```bash
streamlit run web_chat.py
```

## Testing

```bash
# Run all tests
.venv/bin/python test_agentic_workflow.py

# Test document processing
.venv/bin/python test_document_processing.py

# Test file path handling
.venv/bin/python test_file_path_flow.py
```

## Legacy Code

Previous hybrid implementation archived in:
- `agents/legacy/`: Old autonomous agent implementations
- `orchestrator_legacy.py`: Previous orchestration logic
- `docs/archive/`: Historical documentation

## Next Steps

- [ ] Add more document types to classification
- [ ] Implement advanced validation rules
- [ ] Add multi-language OCR support
- [ ] Enhance supervisor agent decision-making
- [ ] Add performance monitoring and metrics
