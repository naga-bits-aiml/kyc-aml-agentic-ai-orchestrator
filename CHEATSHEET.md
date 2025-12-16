# KYC-AML Orchestrator - Command Cheat Sheet

## 🚀 Quick Commands

### Chat Interfaces (Recommended)
```powershell
# CLI chat interface
python chat_interface.py

# Web chat interface
streamlit run web_chat.py
```

### Setup & Installation
```powershell
# Automated setup
.\setup.ps1

# Manual setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### Configuration
```powershell
# Edit configuration
notepad .env

# Required: Add OPENAI_API_KEY
# Required: Set CLASSIFIER_API_BASE_URL
```

### Testing
```powershell
# Start mock API server
python mock_classifier_api.py

# Health check
python main.py --health-check
```

### Basic Usage
```powershell
# Single document
python main.py --documents document.pdf

# Multiple documents
python main.py --documents doc1.pdf doc2.jpg doc3.docx

# With output file
python main.py --documents doc.pdf --output results.json
```

### Advanced Usage
```powershell
# Batch classification
python main.py --documents doc1.pdf doc2.pdf --batch

# CrewAI workflow
python main.py --documents doc1.pdf doc2.pdf --use-crew

# Different model
python main.py --documents doc.pdf --model gpt-3.5-turbo

# Adjust temperature
python main.py --documents doc.pdf --temperature 0.3
```

### Help
```powershell
# Show all options
python main.py --help

# View examples
python examples.py
```

## 📂 File Locations

| Item | Location |
|------|----------|
| Configuration | `.env` |
| Main script | `main.py` |
| CLI Chat | `chat_interface.py` |
| Web Chat | `web_chat.py` |
| Orchestrator | `orchestrator.py` |
| Agents | `agents/` |
| Examples | `examples.py` |
| Mock API | `mock_classifier_api.py` |
| Documentation | `README.md` |
| Chat Guide | `CHAT_GUIDE.md` |
| Quick Start | `QUICKSTART.md` |
| Logs | `kyc_aml_orchestrator.log` |

## 🔧 Common Tasks

### Change API Endpoint
```env
# In .env file
CLASSIFIER_API_BASE_URL=https://your-api.com/api/v1
```

### Adjust File Size Limit
```env
# In .env file (size in MB)
MAX_DOCUMENT_SIZE_MB=20
```

### Add Allowed Extensions
```env
# In .env file
ALLOWED_EXTENSIONS=.pdf,.jpg,.jpeg,.png,.docx,.doc,.txt
```

### Change Log Level
```env
# In .env file
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## 🐍 Python API Examples

### Basic Processing
```python
from orchestrator import KYCAMLOrchestrator

orch = KYCAMLOrchestrator()
results = orch.process_documents(["doc1.pdf", "doc2.pdf"])
print(orch.get_processing_summary(results))
```

### Batch Mode
```python
orch = KYCAMLOrchestrator(use_batch_classification=True)
results = orch.process_documents(["doc1.pdf", "doc2.pdf"])
```

### CrewAI Workflow
```python
orch = KYCAMLOrchestrator()
results = orch.process_with_crew(
    document_paths=["doc1.pdf"],
    process_type="sequential"
)
```

### Individual Agents
```python
from agents import DocumentIntakeAgent, DocumentClassifierAgent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4-turbo-preview")
intake = DocumentIntakeAgent(llm=llm)
classifier = DocumentClassifierAgent(llm=llm)

# Process
intake_results = intake.process_documents(["doc.pdf"])
validated = intake.get_validated_documents(intake_results)
classified = classifier.classify_documents(validated)
```

## 🔍 Debugging

### Check Logs
```powershell
# View log file
Get-Content kyc_aml_orchestrator.log -Tail 50

# Watch logs in real-time
Get-Content kyc_aml_orchestrator.log -Wait
```

### Test API Connection
```powershell
# Test with curl
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -Method GET

# Or in Python
python -c "from agents import ClassifierAPIClient; print(ClassifierAPIClient().health_check())"
```

### Validate Environment
```python
# Check configuration
python -c "from utilities import config; print(f'Model: {config.openai_model}'); print(f'API URL: {config.classifier_api_url}')"
```

## 📊 Output Interpretation

### Status Codes
- `completed` - All documents processed successfully
- `completed_with_warnings` - Some documents failed validation
- `no_valid_documents` - No documents passed validation
- `error` - Critical error occurred

### Classification Results
```json
{
  "file_path": "passport.pdf",
  "classification": {
    "category": "Identity Proof",
    "type": "Passport",
    "confidence": 0.95
  },
  "status": "classified"
}
```

### Common Document Categories
- **Identity Proof**: Passport, Driver's License, National ID
- **Address Proof**: Utility Bill, Bank Statement, Lease
- **Financial Document**: Tax Return, Income Statement
- **Regulatory Form**: KYC Form, AML Declaration

## 🚨 Troubleshooting

| Error | Solution |
|-------|----------|
| No LLM config found | Set `OPENAI_API_KEY` in `.env` |
| API not responding | Start mock server or check real API |
| File not found | Use absolute paths |
| File too large | Adjust `MAX_DOCUMENT_SIZE_MB` |
| Invalid extension | Check `ALLOWED_EXTENSIONS` |
| Import error | Run `pip install -r requirements.txt` |

## 🎯 Best Practices

1. **Always activate venv**: `.\venv\Scripts\Activate.ps1`
2. **Use absolute paths**: `python main.py --documents C:\path\to\doc.pdf`
3. **Check health first**: `python main.py --health-check`
4. **Save important results**: `--output results.json`
5. **Monitor logs**: Check `kyc_aml_orchestrator.log`
6. **Batch for efficiency**: Use `--batch` for multiple docs
7. **Test with mock API**: Use `mock_classifier_api.py` for development

## 📞 Getting Help

```powershell
# Command help
python main.py --help

# View examples
python examples.py

# Read documentation
# - README.md (full docs)
# - QUICKSTART.md (quick start)
# - PROJECT_SUMMARY.md (overview)
```

## 🔗 Quick Links

- **Setup**: Run `.\setup.ps1`
- **Config**: Edit `.env`
- **Test**: Run `python mock_classifier_api.py`
- **Process**: Run `python main.py --documents file.pdf`
- **Examples**: Run `python examples.py`
- **Docs**: Read `README.md`

---

💡 **Tip**: Keep this cheat sheet handy for quick reference!
