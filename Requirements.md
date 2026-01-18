# KYC-AML Agentic AI Orchestrator - Project Summary

## 📌 Overview

This is a multi-agent AI system built with **CrewAI** for processing KYC (Know Your Customer) and AML (Anti-Money Laundering) documents. The system orchestrates two specialized agents that work together to validate and classify compliance documents.

## 🏗️ Architecture

### Core Components

1. **Document Intake Agent**
   - Validates document format and size
   - Creates metadata (hash, size, timestamp)
   - Filters out invalid documents
   - Prepares documents for classification

2. **Document Classifier Agent**
   - Integrates with external classifier API
   - Classifies documents into categories
   - Supports both single and batch classification
   - Returns confidence scores and document types

3. **Orchestrator**
   - Coordinates agent workflows
   - Manages LLM initialization
   - Provides sequential and hierarchical processing
   - Generates comprehensive reports

### Technology Stack

- **Framework**: CrewAI 0.28.8
- **LLM**: OpenAI GPT-4 Turbo (configurable)
- **Alternative LLMs**: Azure OpenAI, Anthropic Claude, Ollama
- **Language**: Python 3.8+
- **HTTP Client**: Requests with retry logic (tenacity)
- **Configuration**: Pydantic Settings

## 📁 Project Structure

```
kyc-aml-agentic-ai-orchestrator/
├── agents/
│   ├── __init__.py                    # Package initialization
│   ├── document_intake_agent.py       # Agent for document validation
│   ├── document_classifier_agent.py   # Agent for document classification
│   └── classifier_api_client.py       # API client with retry logic
├── documents/                          # Document storage (auto-created)
│   └── intake/                        # Validated documents
├── sample_documents/                   # Sample test documents
├── logs/                              # Application logs
├── main.py                            # CLI entry point
├── orchestrator.py                    # Main orchestration logic
├── config.py                          # Configuration management
├── utils.py                           # Utility functions
├── examples.py                        # Usage examples
├── mock_classifier_api.py             # Mock API server for testing
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development dependencies
├── setup.ps1                          # Setup script (PowerShell)
├── .env.example                       # Example environment file
├── .gitignore                        # Git ignore rules
├── README.md                         # Full documentation
├── QUICKSTART.md                     # Quick start guide
└── PROJECT_SUMMARY.md                # This file
```

## 🔑 Key Features

### 1. Multi-Agent Coordination
- Agents work together through CrewAI framework
- Sequential or hierarchical processing modes
- Clear role separation and delegation

### 2. Robust Document Validation
- File format validation (PDF, JPG, PNG, DOCX)
- Size limit enforcement (configurable)
- SHA-256 hash generation for integrity
- Comprehensive metadata extraction

### 3. Flexible Classification
- Single document classification
- Batch processing for efficiency
- Retry logic for API resilience
- Detailed confidence scores

### 4. LLM Flexibility
- OpenAI GPT-4 (default)
- Azure OpenAI support
- Anthropic Claude support
- Local models via Ollama
- Configurable temperature and parameters

### 5. Comprehensive Error Handling
- Graceful failure handling
- Detailed error reporting
- Validation feedback
- API retry mechanism

### 6. Developer-Friendly
- CLI interface
- Python API
- Example scripts
- Mock API server for testing
- Extensive documentation

## 🚀 Usage Modes

### 1. Command Line Interface
```powershell
# Basic usage
python main.py --documents doc1.pdf doc2.jpg

# Batch mode
python main.py --documents doc1.pdf doc2.pdf --batch

# CrewAI workflow
python main.py --documents doc1.pdf --use-crew

# Save results
python main.py --documents doc1.pdf --output results.json

# Health check
python main.py --health-check
```

### 2. Python API
```python
from orchestrator import KYCAMLOrchestrator

orchestrator = KYCAMLOrchestrator()
results = orchestrator.process_documents(["doc1.pdf", "doc2.pdf"])
print(orchestrator.get_processing_summary(results))
```

### 3. Individual Agents
```python
from agents import DocumentIntakeAgent, DocumentClassifierAgent

intake_agent = DocumentIntakeAgent(llm=llm)
classifier_agent = DocumentClassifierAgent(llm=llm)

# Process separately
intake_results = intake_agent.process_documents(docs)
classification_results = classifier_agent.classify_documents(validated_docs)
```

## 📊 Document Types Supported

### Identity Proofs
- Passport
- Driver's License
- National ID Card

### Address Proofs
- Utility Bills
- Bank Statements (as address proof)
- Lease Agreements

### Financial Documents
- Bank Statements
- Income Statements
- Tax Returns

### Regulatory Forms
- KYC Forms
- AML Declarations
- Compliance Documents

## 🔧 Configuration

### Environment Variables
```env
# LLM Configuration
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4-turbo-preview

# Classifier API
CLASSIFIER_API_BASE_URL=http://localhost:8000/api/v1
CLASSIFIER_API_KEY=your_key
CLASSIFIER_TIMEOUT=30

# Application
LOG_LEVEL=INFO
MAX_DOCUMENT_SIZE_MB=10
ALLOWED_EXTENSIONS=.pdf,.jpg,.jpeg,.png,.docx,.doc
```

## 🧪 Testing

### Mock API Server
A Flask-based mock server is included for testing without the real classifier API:

```powershell
python mock_classifier_api.py
```

Provides:
- `/api/v1/health` - Health check
- `/api/v1/classify` - Single document classification
- `/api/v1/batch-classify` - Batch classification
- `/api/v1/classifications/{id}` - Get classification details

### Example Scripts
The `examples.py` file contains 7 comprehensive examples:
1. Basic document processing
2. Batch processing
3. CrewAI workflow orchestration
4. Individual agent usage
5. Health check
6. Error handling
7. Save results to file

## 🔐 Security Considerations

### Best Practices Implemented
- API key management via environment variables
- File size limits to prevent DoS
- File type validation
- Hash-based document integrity
- Secure API communication with retries

### Recommendations for Production
- Use HTTPS for API communication
- Implement rate limiting
- Add authentication/authorization
- Encrypt sensitive documents at rest
- Log audit trails for compliance
- Implement access control
- Use secrets management (e.g., Azure Key Vault)

## 📈 Performance Considerations

### Optimization Strategies
- Batch classification for multiple documents
- Configurable API timeout
- Retry logic with exponential backoff
- Efficient file handling (streaming)
- Minimal memory footprint

### Scalability
- Stateless design for horizontal scaling
- API client connection pooling
- Asynchronous processing capability (future)
- Queue-based architecture (future enhancement)

## 🛠️ Development Setup

### Quick Setup
```powershell
# Run setup script
.\setup.ps1

# Or manual setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your API keys
```

### Running Tests
```powershell
# Start mock server
python mock_classifier_api.py

# In another terminal, test
python main.py --health-check
python main.py --documents sample_documents/test.pdf
```

## 🚦 CI/CD Recommendations

### Suggested Pipeline
1. **Lint**: flake8, black, mypy
2. **Test**: pytest with coverage
3. **Build**: Create distributable package
4. **Deploy**: Docker container or serverless

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🔮 Future Enhancements

### Planned Features
1. **Additional Agents**
   - Document extraction agent (OCR)
   - Verification agent (cross-reference data)
   - Risk assessment agent

2. **Advanced Workflows**
   - Parallel processing
   - Conditional routing
   - Human-in-the-loop approval

3. **Data Storage**
   - Database integration
   - Document versioning
   - Audit trail storage

4. **Monitoring**
   - Prometheus metrics
   - Real-time dashboards
   - Alert system

5. **Web Interface**
   - FastAPI REST API
   - Web dashboard
   - Real-time status updates

## 📝 Maintenance

### Regular Tasks
- Update dependencies monthly
- Review and rotate API keys
- Monitor error logs
- Update document type mappings
- Backup processed documents

### Monitoring Metrics
- Document processing success rate
- Average processing time
- API response times
- Error rates by type
- Agent performance metrics

## 📚 Resources

### Documentation
- `README.md` - Complete documentation
- `QUICKSTART.md` - Quick start guide
- `examples.py` - Code examples
- `.env.example` - Configuration reference

### External Links
- [CrewAI Documentation](https://docs.crewai.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [OpenAI API Reference](https://platform.openai.com/docs)

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Implement changes with tests
4. Submit pull request
5. Code review and merge

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings
- Include unit tests
- Update documentation

## 📄 License

MIT License - See LICENSE file for details

## 👥 Support

For issues, questions, or contributions:
- Create GitHub issue
- Review documentation
- Check example scripts
- Examine logs for errors

---

**Last Updated**: December 11, 2025
**Version**: 1.0.0
**Status**: Production Ready
