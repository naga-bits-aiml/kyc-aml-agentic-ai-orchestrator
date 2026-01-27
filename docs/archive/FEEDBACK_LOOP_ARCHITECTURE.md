# Agentic Feedback Loop Architecture

## The Fundamental Principle

**When agents or orchestrators encounter failures or can't execute actions, they MUST provide feedback to the LLM so it can adapt and try different approaches.**

## Why This Matters

### Without Feedback Loop ❌
```
User: "process KYC-2026-001_DOC_001.pdf"
System: [Detects document ID]
System: [Can't resolve path - case not set]
System: [Silent failure]
Response: "No paths found"
User: ❌ Confused, doesn't know what to do
```

### With Feedback Loop ✅
```
User: "process KYC-2026-001_DOC_001.pdf"
System: [Detects document ID]
System: [Can't resolve path - case not set]
System → LLM: {
  "action_failed": "unresolved_document_ids",
  "reason": "case metadata manager not initialized",
  "suggestion": "use switch_to_case tool first"
}
LLM: [Understands the issue]
LLM: [Calls switch_to_case("KYC-2026-001")]
System: ✅ Case set, metadata manager initialized
LLM: [Retries document processing]
System: ✅ Document processed successfully
```

## Implementation

### 1. Inference Context Structure

The `_create_inference_context()` method builds a structured context that includes:

```python
{
  "user_input": "process KYC-2026-001_DOC_001.pdf",
  "local_inferences": [
    {
      "type": "action_failed",  # Signals failure to LLM
      "inference": "unresolved_document_ids",
      "confidence": "high",
      "action": "Document IDs detected but could not be resolved",
      "details": "Mentioned document IDs: ['KYC-2026-001_DOC_001.pdf']",
      "data": {"document_ids": ["..."]},
      "feedback": "Detailed explanation + suggestions"  # ← Key part
    }
  ],
  "context": {
    "workflow_state": "active",
    "active_case": "KYC-2026-001"
  }
}
```

### 2. Feedback Types

#### Success Feedback
```python
{
  "type": "action",
  "inference": "process_file_paths",
  "confidence": "high",
  "data": {"file_paths": ["/path/to/doc.pdf"]},
  "note": "System will automatically process these documents"
}
```

#### Failure Feedback (NEW)
```python
{
  "type": "action_failed",
  "inference": "unresolved_document_ids",
  "confidence": "high",
  "data": {"document_ids": ["KYC-2026-001_DOC_001.pdf"]},
  "feedback": """Could not resolve document IDs. Possible reasons:
    • Case not set or metadata manager not initialized
    • Active case: None
    • Suggest: Use 'switch_to_case' tool first"""
}
```

#### Partial Success Feedback
```python
{
  "type": "action_partial",
  "inference": "some_documents_processed",
  "confidence": "high",
  "data": {
    "processed": ["doc1.pdf"],
    "failed": ["doc2.pdf"]
  },
  "feedback": "2 documents found, 1 processed, 1 failed: permission denied"
}
```

### 3. LLM Response Flow

The `get_llm_response_with_inference()` method:

1. **Receives inference context** with feedback
2. **Passes to LLM** in structured format
3. **LLM analyzes** the feedback
4. **LLM decides** next action:
   - Call a tool (e.g., `switch_to_case`)
   - Ask user for clarification
   - Try alternative approach
5. **System executes** LLM's decision
6. **Loop continues** until success or max iterations

### 4. Code Locations

#### Inference Creation
**File**: `chat_interface.py`
**Method**: `_create_inference_context()`
**Lines**: ~1784-1900

```python
# Document ID detection with feedback
if file_paths:
    # SUCCESS PATH
    inference["local_inferences"].append({
        "type": "action",
        "inference": "process_file_paths",
        "data": {"file_paths": file_paths}
    })
elif mentioned_doc_ids:
    # FAILURE PATH - Provide feedback
    inference["local_inferences"].append({
        "type": "action_failed",
        "inference": "unresolved_document_ids",
        "data": {"document_ids": mentioned_doc_ids},
        "feedback": "Detailed explanation + suggestions"
    })
```

#### LLM Processing with Feedback
**File**: `chat_interface.py`
**Method**: `get_llm_response_with_inference()`
**Lines**: ~382-480

```python
inference_msg = f"""[INFERENCE VALIDATION]
User Input: "{user_message}"

Local System Analysis:
{json.dumps(inference_context, indent=2)}

Task: Validate the local inferences and decide the best action.
If local inference failed, analyze the feedback and try alternative approach.
"""
```

## Benefits

### 1. Self-Correcting Behavior
LLM learns from failures and adapts strategy automatically.

### 2. Transparent Problem-Solving
User sees the system reasoning through issues:
```
Assistant: I see you want to process KYC-2026-001_DOC_001.pdf, but 
           the case isn't set yet. Let me switch to that case first...
           [Switches case]
           Now processing the document...
```

### 3. Robust Error Handling
System doesn't give up on first failure - tries multiple approaches:
1. Direct path resolution
2. Document ID lookup
3. Case switching
4. User clarification

### 4. Context-Aware Intelligence
Feedback includes state information so LLM makes informed decisions:
- Active case
- Workflow state
- Available tools
- Recent actions

## Examples

### Example 1: Document ID Without Case

**User Input**: "process KYC-2026-001_DOC_001.pdf"

**Inference Context**:
```json
{
  "local_inferences": [{
    "type": "action_failed",
    "feedback": "Case metadata manager not initialized. Suggest: switch_to_case first"
  }]
}
```

**LLM Response**: Calls `switch_to_case("KYC-2026-001")`, then retries

### Example 2: Ambiguous Document Reference

**User Input**: "process document 1"

**Inference Context**:
```json
{
  "local_inferences": [{
    "type": "action_failed",
    "feedback": "Ambiguous reference. 4 documents in case. Use get_case_details to see list."
  }]
}
```

**LLM Response**: Calls `get_case_details()`, shows list, asks user to clarify

### Example 3: Permission Error

**User Input**: "process /secure/doc.pdf"

**Inference Context**:
```json
{
  "local_inferences": [{
    "type": "action_failed",
    "feedback": "Permission denied: /secure/doc.pdf. Need read access."
  }]
}
```

**LLM Response**: Explains permission issue, suggests alternative path or file

## Testing

Run the feedback loop test:
```bash
python test_feedback_loop.py
```

This demonstrates:
1. How feedback is structured
2. What information is passed to LLM
3. How LLM can adapt based on feedback
4. Complete flow from failure to success

## Future Enhancements

### 1. Feedback History
Track previous feedback and LLM adaptations to learn patterns:
```python
{
  "feedback_history": [
    {"attempt": 1, "action": "direct_path", "result": "failed"},
    {"attempt": 2, "action": "switch_case", "result": "success"}
  ]
}
```

### 2. Confidence Scoring
Adjust confidence based on feedback success rate:
```python
{
  "confidence": "medium",  # Lowered from "high" due to 2 previous failures
  "reason": "Similar pattern failed twice before"
}
```

### 3. Suggestion Ranking
Rank multiple suggestions by likelihood of success:
```python
{
  "suggestions": [
    {"action": "switch_case", "confidence": 0.9},
    {"action": "list_documents", "confidence": 0.7},
    {"action": "ask_user", "confidence": 0.5}
  ]
}
```

### 4. Multi-Agent Feedback
Allow specialized agents to provide feedback to supervisor:
```python
{
  "agent": "DocumentExtractionAgent",
  "feedback": "OCR failed - document is encrypted. Suggest: try classification API."
}
```

## Summary

**The feedback loop is essential for intelligent, adaptive agentic systems.** It transforms brittle, failure-prone automation into robust, self-correcting AI that learns and adapts.

**Key Principle**: Never let an action fail silently. Always provide structured feedback that enables the LLM to understand what happened and why, so it can make informed decisions about next steps.
