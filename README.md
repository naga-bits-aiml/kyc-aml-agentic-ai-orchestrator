# KYC-AML Agentic AI Orchestrator

An intelligent multi-agent system for processing KYC (Know Your Customer) and AML (Anti-Money Laundering) documents using CrewAI and Large Language Models.

## 🌟 Features

- **Multi-Agent Architecture**: Coordinated agents working together for document processing
- **Document Intake Agent**: Validates and prepares documents for processing
- **Document Classifier Agent**: Classifies documents using an external classifier API
- **Interactive Chat Interfaces**: CLI and Web-based chat for user interaction
- **Flexible LLM Support**: Works with OpenAI GPT-4, Azure OpenAI, Anthropic Claude, or local models
- **Batch Processing**: Efficient processing of multiple documents
- **CrewAI Orchestration**: Advanced agent coordination and workflow management
- **Robust Error Handling**: Retry logic and comprehensive error reporting

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  KYC-AML Orchestrator                        │
│                                                               │
│  ┌────────────────────┐      ┌────────────────────┐        │
│  │ Document Intake    │──────▶│ Document Classifier│        │
│  │ Agent              │      │ Agent              │        │
│  │                    │      │                    │        │
│  │ • Validates files  │      │ • Calls API        │        │
│  │ • Checks format    │      │ • Classifies docs  │        │
│  │ • Creates metadata │      │ • Returns results  │        │
│  └────────────────────┘      └────────────────────┘        │
│                                        │                     │
│                                        ▼                     │
│                          ┌──────────────────────┐           │
│                          │ Classifier API       │           │
│                          │ (External Service)   │           │
│                          └──────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.8 or higher
- OpenAI API key (or other supported LLM provider)
- Access to KYC-AML Document Classifier API

## 🚀 Quick Start

### 1. Installation

```powershell
# Clone the repository
cd "c:\Users\Lenovo\OneDrive - wilp.bits-pilani.ac.in\Documents\AIML\kyc-aml-agentic-ai-orchestrator"

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Edit .env and add your API keys
notepad .env
```

Required configuration in `.env`:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview
CLASSIFIER_API_BASE_URL=http://localhost:8000/api/v1
CLASSIFIER_API_KEY=your_classifier_api_key_here
```

### 3. Usage

#### Interactive Chat Interface (Recommended)

**CLI Chat**:
```powershell
python chat_interface.py
```

**Web Chat**:
```powershell
streamlit run web_chat.py
```

Then open your browser at `http://localhost:8501`

#### Command Line Usage

Process a single document:
```powershell
python main.py --documents document.pdf
```

Process multiple documents:
```powershell
python main.py --documents doc1.pdf doc2.jpg doc3.docx
```

#### Advanced Usage

Use batch classification:
```powershell
python main.py --documents doc1.pdf doc2.pdf --batch
```

Use CrewAI workflow orchestration:
```powershell
python main.py --documents doc1.pdf doc2.pdf --use-crew
```

Save results to file:
```powershell
python main.py --documents doc1.pdf --output results.json
```

Check classifier API health:
```powershell
python main.py --health-check
```

#### Using Different Models

Use a different OpenAI model:
```powershell
python main.py --documents doc.pdf --model gpt-3.5-turbo
```

Adjust temperature (creativity):
```powershell
python main.py --documents doc.pdf --temperature 0.3
```

## 🧪 Example Code

### Python API Usage

```python
from orchestrator import KYCAMLOrchestrator

# Initialize orchestrator
orchestrator = KYCAMLOrchestrator(
    model_name="gpt-4-turbo-preview",
    temperature=0.1
)

# Process documents
document_paths = ["passport.pdf", "utility_bill.jpg", "bank_statement.pdf"]
results = orchestrator.process_documents(document_paths)

# Print summary
print(orchestrator.get_processing_summary(results))

# Access detailed results
for doc in results["classification_results"]:
    print(f"Document: {doc['file_path']}")
    print(f"Type: {doc['classification']['category']}")
    print(f"Confidence: {doc['classification']['confidence']}")
```

### Using CrewAI Workflow

```python
from orchestrator import KYCAMLOrchestrator

orchestrator = KYCAMLOrchestrator()

# Use CrewAI for coordinated agent workflow
results = orchestrator.process_with_crew(
    document_paths=["doc1.pdf", "doc2.pdf"],
    process_type="sequential"  # or "hierarchical"
)

print(results["crew_output"])
```

### Individual Agent Usage

```python
from agents import DocumentIntakeAgent, DocumentClassifierAgent
from langchain_openai import ChatOpenAI

# Initialize LLM
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)

# Create agents
intake_agent = DocumentIntakeAgent(llm=llm)
classifier_agent = DocumentClassifierAgent(llm=llm)

# Process with intake agent
intake_results = intake_agent.process_documents(["doc.pdf"])
validated_docs = intake_agent.get_validated_documents(intake_results)

# Classify documents
classification_results = classifier_agent.classify_documents(validated_docs)
summary = classifier_agent.get_classification_summary(classification_results)

print(summary)
```

## 📁 Project Structure

```
kyc-aml-agentic-ai-orchestrator/
├── agents/
│   ├── __init__.py
│   ├── document_intake_agent.py      # Document intake and validation
│   ├── document_classifier_agent.py  # Document classification
│   └── classifier_api_client.py      # API client for classifier service
├── documents/                         # Document storage (auto-created)
├── main.py                           # CLI entry point
├── chat_interface.py                 # Interactive CLI chat
├── web_chat.py                       # Web-based chat interface
├── orchestrator.py                   # Main orchestration logic
├── config.py                         # Configuration management
├── utils.py                          # Utility functions
├── examples.py                       # Usage examples
├── mock_classifier_api.py            # Mock API server
├── requirements.txt                  # Python dependencies
├── .env.example                      # Example environment file
├── .gitignore                       # Git ignore rules
├── README.md                        # This file
├── QUICKSTART.md                    # Quick start guide
├── CHAT_GUIDE.md                    # Chat interface guide
└── CHEATSHEET.md                    # Command reference
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4-turbo-preview` |
| `CLASSIFIER_API_BASE_URL` | Classifier API base URL | `http://localhost:8000/api/v1` |
| `CLASSIFIER_API_KEY` | Classifier API key | Required |
| `CLASSIFIER_TIMEOUT` | API timeout (seconds) | `30` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_DOCUMENT_SIZE_MB` | Max document size | `10` |
| `ALLOWED_EXTENSIONS` | Allowed file extensions | `.pdf,.jpg,.jpeg,.png,.docx,.doc` |

### Supported Document Types

- **Identity Proof**: Passport, Driver's License, National ID
- **Address Proof**: Utility Bills, Bank Statements, Lease Agreements
- **Financial Documents**: Income Statements, Tax Returns
- **Regulatory Forms**: KYC Forms, AML Declarations

## 🤖 Supported LLM Providers

### OpenAI (Default)
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

### Azure OpenAI
```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_DEPLOYMENT_NAME=...
```

### Anthropic Claude
```env
ANTHROPIC_API_KEY=...
MODEL_NAME=claude-3-sonnet-20240229
```

### Local Models (Ollama)
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

## 📊 Output Format

The orchestrator returns results in the following format:

```json
{
  "status": "completed",
  "intake_results": [
    {
      "file_path": "document.pdf",
      "validation": {
        "valid": true,
        "metadata": {
          "filename": "document.pdf",
          "size_bytes": 245632,
          "hash": "abc123..."
        }
      },
      "status": "validated"
    }
  ],
  "classification_results": [
    {
      "file_path": "document.pdf",
      "classification": {
        "category": "Identity Proof",
        "type": "Passport",
        "confidence": 0.95
      },
      "status": "classified"
    }
  ],
  "summary": {
    "total_documents": 1,
    "validated": 1,
    "classification_summary": {
      "successfully_classified": 1,
      "success_rate": 100.0,
      "document_types": {
        "Identity Proof": 1
      }
    }
  }
}
```

## 🧩 API Endpoints Expected

The orchestrator expects the classifier API to provide:

- `POST /api/v1/classify` - Classify single document
- `POST /api/v1/batch-classify` - Classify multiple documents
- `GET /api/v1/classifications/{id}` - Get classification details
- `GET /api/v1/health` - Health check

## 🛠️ Development

### Adding New Agents

1. Create a new agent class in `agents/`
2. Inherit from CrewAI's `Agent`
3. Define role, goal, and backstory
4. Implement processing logic
5. Add to orchestrator workflow

### Running Tests

```powershell
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

## 🐛 Troubleshooting

### Common Issues

**Issue**: `No valid LLM configuration found`
- **Solution**: Ensure `OPENAI_API_KEY` is set in `.env`

**Issue**: `Classifier API is not responding`
- **Solution**: Check that the classifier service is running and accessible

**Issue**: `File size exceeds maximum`
- **Solution**: Adjust `MAX_DOCUMENT_SIZE_MB` in `.env` or compress the file

**Issue**: `Invalid file extension`
- **Solution**: Check `ALLOWED_EXTENSIONS` configuration or convert the file

## 📝 Logging

Logs are written to:
- Console (stdout)
- `kyc_aml_orchestrator.log` file

Adjust log level in `.env`:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 👥 Authors

KYC-AML Agentic AI Orchestrator Team

## 🙏 Acknowledgments

- Built with [CrewAI](https://github.com/joaomdmoura/crewAI)
- Powered by [LangChain](https://github.com/langchain-ai/langchain)
- LLM support via OpenAI, Anthropic, and others

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review the logs for error details

---

**Note**: Ensure you comply with all relevant data protection and privacy regulations when processing KYC/AML documents.
