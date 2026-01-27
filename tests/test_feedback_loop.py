"""Test feedback loop when document IDs can't be resolved."""
import sys
import json
from pathlib import Path

# This test demonstrates the feedback loop principle:
# When an action fails, the system should provide feedback to the LLM
# so it can try a different approach.

print("=" * 80)
print("FEEDBACK LOOP TEST: Document ID Resolution")
print("=" * 80)

print("""
Principle: When agents/orchestrator can't execute an action, they should 
provide feedback to the LLM explaining why and suggesting alternatives.

Example Flow:
1. User: "process KYC-2026-001_DOC_001.pdf"
2. System: Detects document ID but can't resolve path (case not set)
3. System → LLM: "I found document ID but can't resolve it because case 
                  metadata manager isn't initialized. Suggest using 
                  switch_to_case first."
4. LLM: Tries different approach - calls switch_to_case tool
5. LLM: Then retries with resolved path
""")

# Simulate the inference context that would be passed to LLM
inference_context = {
    "user_input": "process KYC-2026-001_DOC_001.pdf",
    "local_inferences": [
        {
            "type": "action_failed",
            "inference": "unresolved_document_ids",
            "confidence": "high",
            "action": "Document IDs detected but could not be resolved to file paths",
            "details": "Mentioned document IDs: ['KYC-2026-001_DOC_001.pdf']",
            "data": {"document_ids": ["KYC-2026-001_DOC_001.pdf"]},
            "feedback": """Could not resolve document IDs. Possible reasons:
  • Case not set or metadata manager not initialized
  • Active case: None
  • Metadata manager: NOT initialized
  • Suggest: Use 'switch_to_case' tool first, then try 'get_case_details' to see available documents"""
        }
    ]
}

print("\n" + "=" * 80)
print("INFERENCE CONTEXT PASSED TO LLM:")
print("=" * 80)
print(json.dumps(inference_context, indent=2))

print("\n" + "=" * 80)
print("LLM SHOULD NOW:")
print("=" * 80)
print("""
1. ✅ See that document ID was detected but couldn't be resolved
2. ✅ Understand the reason: case metadata manager not initialized  
3. ✅ See the suggestion: use switch_to_case tool first
4. ✅ Call: switch_to_case("KYC-2026-001")
5. ✅ Wait for confirmation
6. ✅ Retry: Now the document ID can be resolved
7. ✅ Success: Process the document

This is the AGENTIC LOOP:
  User Request → Attempt Action → Failure Feedback → LLM Adapts → 
  Try Different Approach → Success
""")

print("\n" + "=" * 80)
print("BENEFITS OF FEEDBACK LOOP:")
print("=" * 80)
print("""
✅ Self-correcting: LLM learns from failures and adapts
✅ Transparent: User sees the system thinking through the problem
✅ Robust: System doesn't give up on first failure
✅ Intelligent: LLM uses reasoning to find alternative paths
✅ Context-aware: Feedback includes specific state information

Without feedback loop:
❌ Silent failure - user sees "No paths found"
❌ No retry mechanism
❌ LLM doesn't know what went wrong
❌ Poor user experience
""")

print("\n" + "=" * 80)
print("Test Complete! This demonstrates the importance of")
print("passing feedback to the LLM when actions fail.")
print("=" * 80)
