# Context Management Techniques for LLM-Based Chat Interfaces

## Problem
LLMs are **stateless** - they don't remember previous interactions unless you explicitly provide the context. This causes:
- ❌ Asking for case reference when it's already set
- ❌ Not knowing work is incomplete
- ❌ Repeating explanations
- ❌ Losing track of conversation flow

## Solution: 5 Techniques for Context Management

### 1. **System Prompt with Context Awareness** ✅
**What:** Include context-aware instructions in the system prompt

**Implementation:**
```python
system_prompt = """
⚡ CRITICAL CONTEXT AWARENESS:
1. ALWAYS check the CURRENT_STATE context before responding
2. If a case is active, NEVER ask "which case?" - use the active case
3. If processing failed, PROACTIVELY suggest resuming
"""
```

**Why it works:** Sets expectations for LLM behavior at the foundation level

---

### 2. **Conversation Context Array** ✅ (Already implemented)
**What:** Maintain full conversation history and send it with each request

**Implementation:**
```python
self.conversation_context = [
    SystemMessage(system_prompt),
    HumanMessage("Set case to KYC-001"),
    AIMessage("Case KYC-001 created"),
    HumanMessage("Show docs"),  # ← LLM sees previous messages
]
```

**Why it works:** LLM can reference what was said earlier in the conversation

**Limitation:** Context window limit (~8K-100K tokens depending on model)

---

### 3. **Dynamic Context Injection** ✅ (Just implemented!)
**What:** Inject current state as a hidden message before each user query

**Implementation:**
```python
def get_llm_response(self, user_message):
    # Inject current context
    context = f"[CURRENT_STATE: Active Case: {self.case_reference} | Documents: {doc_count} | Workflow: {stage}]"
    self.conversation_context.append(HumanMessage(content=context))
    
    # Then process user message
    self.add_message("user", user_message)
    response = self.llm.invoke(self.conversation_context)
```

**Why it works:** LLM always has up-to-date state information, even if conversation history is long

**Example:**
```
User: "show docs"
Hidden context: [CURRENT_STATE: Active Case: KYC-2026-001 | Documents: 3]
LLM sees both → Knows which case without asking!
```

---

### 4. **State Variables in Class** ✅ (Already implemented)
**What:** Store session state in instance variables

**Implementation:**
```python
class ChatInterface:
    def __init__(self):
        self.case_reference = None  # ← State persistence
        self.workflow_state = "initial"
        self.processed_documents = []
        self.case_documents = {}
```

**Why it works:** Your code can check state and provide it to LLM

**Usage:**
```python
if self.case_reference:
    # We know the active case, inject into context
    context_info = f"Active case: {self.case_reference}"
```

---

### 5. **Smart Command Detection** ✅ (Already implemented)
**What:** Handle common commands programmatically before LLM

**Implementation:**
```python
def handle_user_input(self, user_input):
    # Check for commands first - no LLM needed!
    if user_input.lower() in ['status', 'show docs']:
        return self._show_status()  # Direct action
    
    # Extract file paths - no LLM confirmation needed
    file_paths = self._extract_file_paths(user_input)
    if file_paths:
        return self._process_documents(file_paths)  # Direct action
    
    # Only use LLM for ambiguous queries
    return self.get_llm_response(user_input)
```

**Why it works:** Reduces LLM involvement in deterministic tasks

---

## Advanced Techniques (Not Yet Implemented)

### 6. **Context Summarization**
**Problem:** Long conversations exceed context window

**Solution:** Periodically summarize old messages
```python
if len(self.conversation_context) > 50:
    summary = self.llm.invoke("Summarize this conversation in 3 sentences")
    self.conversation_context = [
        SystemMessage(system_prompt),
        AIMessage(f"Previous conversation summary: {summary}"),
        *self.conversation_context[-20:]  # Keep last 20 messages
    ]
```

---

### 7. **Explicit State Tracking Commands**
**Add commands that update LLM context:**
```python
def set_case_reference(self, case_ref):
    self.case_reference = case_ref
    # Explicitly tell LLM about state change
    self.conversation_context.append(
        AIMessage(f"[SYSTEM: Active case set to {case_ref}]")
    )
```

---

### 8. **Persistent Memory (Database/File)**
**Store conversation state externally:**
```python
# Save to file
with open(f"sessions/{session_id}.json", 'w') as f:
    json.dump({
        'case_reference': self.case_reference,
        'history': self.chat_history,
        'processed_docs': self.processed_documents
    }, f)

# Reload in new session
def load_session(session_id):
    with open(f"sessions/{session_id}.json", 'r') as f:
        data = json.load(f)
    self.case_reference = data['case_reference']
    # Reconstruct conversation_context from history
```

---

### 9. **Retrieval-Augmented Generation (RAG)**
**For very long histories, use vector DB:**
```python
# Store messages in vector database
vector_db.add(message, embedding)

# Retrieve relevant past messages
relevant_history = vector_db.search(user_query, k=5)
self.conversation_context = [
    SystemMessage(system_prompt),
    *relevant_history,  # Only relevant past messages
    HumanMessage(user_query)
]
```

---

### 10. **Token Budget Management**
**Monitor and optimize context size:**
```python
def get_token_count(messages):
    # Estimate: ~4 chars per token
    return sum(len(m.content) for m in messages) // 4

def trim_context(self):
    current_tokens = get_token_count(self.conversation_context)
    if current_tokens > 6000:  # Leave room for response
        # Keep system prompt + last 30 messages
        self.conversation_context = [
            self.conversation_context[0],  # System prompt
            *self.conversation_context[-30:]
        ]
```

---

## Your Current Implementation: Excellent! ✅

You're using:
1. ✅ System prompt with instructions
2. ✅ Conversation context array
3. ✅ **NEW:** Dynamic context injection
4. ✅ State variables (case_reference, workflow_state)
5. ✅ Smart command detection (file paths, commands)

**Result:** LLM now knows:
- Which case is active
- How many documents are in the case
- Current workflow stage
- What was just processed

## Testing the Improvements

```python
# Test 1: LLM should remember case
chat.handle_user_input("KYC-2026-001")  # Set case
chat.handle_user_input("show docs")     # Should NOT ask "which case?"

# Test 2: LLM should know processing failed
chat.handle_user_input("~/document.pdf")  # Process (fails)
chat.handle_user_input("what happened?")  # Should explain failure

# Test 3: Context injection
response = chat.get_llm_response("status")
# LLM receives: [CURRENT_STATE: Active Case: KYC-2026-001 | Documents: 3]
```

---

## Best Practices

1. **Keep system prompt concise but specific** (~500-800 tokens)
2. **Inject context dynamically** for current state
3. **Handle deterministic tasks programmatically** (don't ask LLM for obvious actions)
4. **Trim conversation history** when approaching token limits
5. **Test context retention** regularly

---

## Summary

**Problem:** LLM forgets context → asks redundant questions

**Solution:** 
- System prompt teaches behavior
- Conversation history provides past context
- **Dynamic context injection** provides current state
- State variables enable programmatic decisions

**Your system now has all 5 core techniques implemented!** 🎯
