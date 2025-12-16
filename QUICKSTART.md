# Quick Start Guide

Follow these steps to get the KYC-AML Agentic AI Orchestrator up and running.

## Step 1: Install Dependencies

```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install main dependencies
pip install -r requirements.txt

# (Optional) Install development dependencies for mock server
pip install -r requirements-dev.txt
```

## Step 2: Configure Environment

```powershell
# Copy example environment file
Copy-Item .env.example .env

# Edit the .env file and add your API keys
notepad .env
```

Update the following in `.env`:
```env
OPENAI_API_KEY=your_actual_openai_api_key
CLASSIFIER_API_BASE_URL=http://localhost:8000/api/v1
CLASSIFIER_API_KEY=your_classifier_api_key
```

## Step 3: Start the Mock Classifier API (Optional)

If you don't have access to the real classifier API, start the mock server:

```powershell
# In a separate terminal
python mock_classifier_api.py
```

The mock server will start on `http://localhost:8000`

## Step 4: Prepare Sample Documents

Create a `sample_documents` directory and add some test files:

```powershell
New-Item -ItemType Directory -Path sample_documents -Force

# Add your test documents (PDF, JPG, DOCX, etc.)
# Or use the provided samples
```

## Step 5: Run Your First Document Processing

```powershell
# Check if everything is configured correctly
python main.py --health-check

# Process a single document
python main.py --documents sample_documents/passport.pdf

# Process multiple documents
python main.py --documents sample_documents/passport.pdf sample_documents/utility_bill.jpg
```

## Step 6: Try Different Modes

### Basic Processing
```powershell
python main.py --documents doc1.pdf doc2.pdf
```

### Batch Mode
```powershell
python main.py --documents doc1.pdf doc2.pdf doc3.pdf --batch
```

### CrewAI Workflow
```powershell
python main.py --documents doc1.pdf doc2.pdf --use-crew
```

### Save Results to File
```powershell
python main.py --documents doc1.pdf --output results.json
```

## Step 7: Explore Examples

Run the examples script to see different usage patterns:

```powershell
python examples.py
```

Edit `examples.py` to uncomment specific examples you want to run.

## Troubleshooting

### Issue: "No valid LLM configuration found"
✅ **Solution**: Make sure `OPENAI_API_KEY` is set in your `.env` file

### Issue: "Classifier API is not responding"
✅ **Solution**: 
- Check if the mock server is running: `python mock_classifier_api.py`
- Verify the URL in `.env` matches: `http://localhost:8000/api/v1`

### Issue: "ModuleNotFoundError"
✅ **Solution**: Install dependencies: `pip install -r requirements.txt`

### Issue: "File not found"
✅ **Solution**: Use absolute paths or ensure files exist in the specified location

## Next Steps

1. **Customize Agents**: Modify agent behaviors in `agents/` directory
2. **Add New Document Types**: Extend classification categories
3. **Integrate Real API**: Connect to your actual classifier service
4. **Add Monitoring**: Implement logging and metrics collection
5. **Deploy**: Set up production environment with proper security

## Architecture Overview

```
User Input (Documents)
        ↓
Document Intake Agent
    • Validates files
    • Checks formats
    • Creates metadata
        ↓
Document Classifier Agent
    • Calls API
    • Classifies documents
    • Returns results
        ↓
Results & Summary
```

## Supported Models

- **GPT-4 Turbo** (default, recommended)
- **GPT-3.5 Turbo** (faster, cheaper)
- **Claude 3** (via Anthropic)
- **Local Models** (via Ollama)

Change model:
```powershell
python main.py --documents doc.pdf --model gpt-3.5-turbo
```

## File Size Limits

Default: 10MB per document

Adjust in `.env`:
```env
MAX_DOCUMENT_SIZE_MB=20
```

## Allowed File Types

Default: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.docx`, `.doc`

Adjust in `.env`:
```env
ALLOWED_EXTENSIONS=.pdf,.jpg,.jpeg,.png,.docx,.doc,.txt
```

---

🎉 **You're all set!** Start processing KYC-AML documents with AI agents.

For detailed documentation, see [README.md](README.md)
