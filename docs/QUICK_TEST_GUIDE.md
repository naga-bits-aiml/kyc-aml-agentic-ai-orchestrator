# Quick Test Guide for Agentic AI System

## Testing the Agentic Workflow

### Option 1: Run Comprehensive Tests
```bash
cd /Users/nagaad/Workspace_Project/kyc-aml-agentic-ai-orchestrator
.venv/bin/python test_agentic_workflow.py
```

**Expected Output:**
```
✅ ALL TESTS PASSED!
```

### Option 2: Test via Chat Interface
```bash
.venv/bin/python chat_interface.py
```

**Test Scenario:**
1. When prompted, enter case reference: `KYC-2024-TEST`
2. When prompted, provide a document path (or type 'skip')
3. The system will:
   - Create SharedMemory for the case
   - Supervisor will analyze your request
   - IntakeAgent will validate documents with reasoning
   - ExtractionAgent will extract text with strategy
   - ClassificationAgent will classify with confidence
   - Results will show workflow status and completeness

**Example Interaction:**
```
🔍 Please provide your KYC/AML case reference:
> KYC-2024-TEST

📎 Please provide document path(s):
> /path/to/passport.pdf

[Agentic Processing...]

✅ Agentic Processing Complete for KYC-2024-TEST!

📁 Case Directory: documents/cases/KYC-2024-TEST

🔄 Workflow Status:
  • Phase: execution
  • Completed Steps: 3
  • Pending Steps: 0

📄 Documents Processed: 1
  • KYC-2024-TEST_DOC_001.pdf: validated

🏷️  Classifications:
  • KYC-2024-TEST_DOC_001.pdf: identity_proof (92% confidence)

✓ Case Completeness:
  ⚠️  Missing: address_proof, financial_document
  Score: 33%
```

### Verify State Persistence

**Check Workflow Memory:**
```bash
cat documents/cases/KYC-2024-TEST/workflow_memory.json | jq
```

**Check Document Metadata:**
```bash
cat documents/cases/KYC-2024-TEST/*.metadata.json | jq
```

### What to Look For

✅ **Reasoning Logs**: Agent explains WHY decisions were made
```
[IntakeAgent] Reasoning: careful approach
Analysis: "Document identified as passport, concerns about file format..."
```

✅ **Adaptive Behavior**: Agent adjusts strategy based on context
```
[ExtractionAgent] Strategy: ocr_local_pdf
Document prioritized as 'high' due to identity verification requirement
```

✅ **Quality Reflection**: Agent evaluates its own work
```
Reflection: success=True, quality_score=0.85
Issues: ["Low image quality may affect OCR accuracy"]
Suggestions: ["Consider requesting higher resolution scan"]
```

✅ **State Persistence**: All actions tracked in workflow_memory.json
```json
{
  "execution_history": [
    {"type": "agent_action", "agent": "IntakeAgent", "action": "validate", "status": "success"},
    {"type": "agent_action", "agent": "ExtractionAgent", "action": "extract", "status": "success"}
  ]
}
```

## Troubleshooting

### If Python Can't Find Modules
Make sure to use the venv python:
```bash
.venv/bin/python test_agentic_workflow.py
```

### If CrewAI Import Fails
Install in venv:
```bash
.venv/bin/pip install crewai==1.8.1
```

### View Detailed Logs
Check the logs directory:
```bash
tail -f logs/kyc_aml_orchestrator_*.log
```

## Performance Notes

- **LLM Calls**: Each agent makes 2-3 LLM calls (reason, plan, reflect)
- **Processing Time**: ~7-10 seconds per document (mostly LLM inference)
- **Memory Usage**: Persisted to disk after each step
- **Scalability**: Can process multiple documents in sequence

## Architecture Verification

Run this to confirm all components are working:
```python
from agents import (
    SharedMemory, SupervisorAgent,
    AutonomousIntakeAgent, AutonomousExtractionAgent,
    AutonomousClassificationAgent
)

# Should import without errors
print("✅ All agentic components imported successfully")
```

## Key Differences from Old System

| Aspect | Old System | New Agentic System |
|--------|-----------|-------------------|
| Decision Making | Hardcoded rules | LLM-powered reasoning |
| Workflow | Fixed pipeline | Dynamic adaptation |
| State | No persistence | Full state tracking |
| Traceability | Limited logs | Complete audit trail |
| Error Handling | Basic | Reflective + adaptive |
| Collaboration | None | Agent messaging |

---

**Ready to Test!** 🚀

The system is fully operational and demonstrates true agentic AI behavior with autonomous decision-making, reasoning, and collaborative intelligence.
