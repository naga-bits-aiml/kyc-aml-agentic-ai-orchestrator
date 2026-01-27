# Hybrid Architecture Guide

## Overview

This project now implements a **hybrid architecture** that combines CrewAI's standard patterns with advanced autonomous agent reasoning capabilities. This approach provides the best of both worlds:

- ✅ **CrewAI Standards**: YAML-based configuration, @agent/@task decorators, standard workflows
- ✅ **Advanced Reasoning**: Custom Observe-Reason-Plan-Act-Reflect loop for intelligent decision-making
- ✅ **Flow-Based Orchestration**: Event-driven workflow with proper state management
- ✅ **Backward Compatibility**: Legacy orchestration methods still work

---

## Architecture Components

### 1. **YAML Configuration** (`config/`)

Agent and task definitions are now externalized in YAML files, making them easy to modify without touching code.

#### `config/agents.yaml`
Defines roles, goals, and backstories for all agents:
```yaml
document_intake_agent:
  role: >
    Document Intake and Validation Specialist
  goal: >
    Validate and organize documents for case {case_id}
  backstory: >
    Experienced specialist with 10+ years in KYC/AML...
```

**Parameters** like `{case_id}`, `{document_type}` are automatically injected at runtime.

#### `config/tasks.yaml`
Defines task descriptions, expected outputs, and agent assignments:
```yaml
validate_documents_task:
  description: >
    Validate all documents...
  expected_output: >
    JSON object with validated documents...
  agent: document_intake_agent
```

---

### 2. **CrewAI-Compliant Crew** (`crew.py`)

The `KYCAMLCrew` class follows CrewAI standards with decorators:

```python
@CrewBase
class KYCAMLCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    @agent
    def document_intake_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['document_intake_agent'],
            tools=[...],
            verbose=True,
            llm=self.llm
        )
    
    @task
    def validate_documents_task(self) -> Task:
        return Task(
            config=self.tasks_config['validate_documents_task'],
            agent=self.document_intake_agent()
        )
    
    @crew
    def intake_crew(self) -> Crew:
        return Crew(
            agents=[self.document_intake_agent()],
            tasks=[self.validate_documents_task()],
            process=Process.sequential
        )
```

**Key Features:**
- Automatic agent/task collection via decorators
- Config-driven agent creation
- Multiple crew definitions (intake, classification, extraction, full pipeline)
- Hybrid execution mode supporting both standard and reasoning-enhanced workflows

---

### 3. **Flow-Based Orchestration** (`flows/`)

Event-driven workflow using CrewAI's Flow pattern:

```python
class DocumentProcessingFlow(Flow[DocumentProcessingState]):
    @start()
    def intake_documents(self):
        """Entry point - validates documents"""
        result = self.crew.execute_with_reasoning('intake', {...})
        self.state.validated_documents = result['execution']['validated_documents']
    
    @listen(intake_documents)
    def classify_documents(self):
        """Triggered after intake completes"""
        result = self.crew.execute_with_reasoning('classification', {...})
        self.state.classifications = result['execution']['classifications']
    
    @listen(classify_documents)
    def extract_data(self):
        """Triggered after classification completes"""
        result = self.crew.execute_with_reasoning('extraction', {...})
        self.state.extractions = result['execution']['extractions']
```

**Benefits:**
- Clear stage dependencies via `@listen` decorators
- Type-safe state management with Pydantic
- Automatic flow visualization
- Error handling between stages

---

### 4. **Hybrid Agent Adapters** (`agents/hybrid_adapter.py`)

Bridges CrewAI agents with autonomous reasoning agents:

```python
class ReasoningAgentAdapter:
    """Wraps autonomous agents for use in CrewAI"""
    
    def execute_with_reasoning(self, task_params):
        # Execute using Observe-Reason-Plan-Act-Reflect loop
        result = self.autonomous_agent.execute(task, shared_memory)
        return result
```

**Features:**
- Transparent integration of reasoning capabilities
- Shared memory bridge between systems
- Result format translation
- Optional reasoning callbacks

---

## Usage Guide

### **Option 1: Flow-Based Workflow (Recommended)**

Use the new Flow pattern for complete workflows:

```bash
# Process documents with Flow and reasoning
python main.py --documents doc1.pdf doc2.pdf --use-flow

# With custom case ID
python main.py --documents doc1.pdf --use-flow --case-id CASE_001

# Disable reasoning (standard CrewAI only)
python main.py --documents doc1.pdf --use-flow --no-reasoning

# Generate flow visualization
python main.py --documents doc1.pdf --use-flow --visualize-flow
```

**Python API:**
```python
from flows import kickoff_flow
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", temperature=0.1)

results = kickoff_flow(
    case_id="CASE_001",
    file_paths=["path/to/doc1.pdf", "path/to/doc2.pdf"],
    llm=llm,
    use_reasoning=True,
    visualize=True  # Creates flow_CASE_001.html
)

print(results['status'])  # 'completed', 'requires_review', etc.
print(results['documents'])  # Document counts
print(results['extractions'])  # Extracted data
```

---

### **Option 2: Direct Crew Usage**

Use crews directly for specific tasks:

```python
from crew import KYCAMLCrew, KYCAMLCrewFactory
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", temperature=0.1)

# Create full crew
crew = KYCAMLCrew(llm=llm)

# Option A: Use hybrid approach with reasoning
results = crew.kickoff_with_reasoning(
    case_id="CASE_001",
    file_paths=["doc1.pdf"],
    use_reasoning=True
)

# Option B: Use standard CrewAI approach
inputs = {'case_id': 'CASE_001', 'file_paths': ['doc1.pdf']}
results = crew.full_pipeline_crew().kickoff(inputs=inputs)

# Or use specialized crews
intake_crew = KYCAMLCrewFactory.create_intake_only_crew(llm)
classification_crew = KYCAMLCrewFactory.create_classification_only_crew(llm)
```

---

### **Option 3: Legacy Orchestrator (Backward Compatible)**

The original orchestrator still works:

```bash
# Legacy direct processing
python main.py --documents doc1.pdf doc2.pdf

# Legacy CrewAI mode
python main.py --documents doc1.pdf --use-crew
```

```python
from orchestrator import KYCAMLOrchestrator

orchestrator = KYCAMLOrchestrator(model_name="gpt-4")
results = orchestrator.process_documents(["doc1.pdf"])
```

---

## Configuration Guide

### **Modifying Agent Behavior**

Edit `config/agents.yaml` to change agent characteristics:

```yaml
document_classifier_agent:
  role: >
    Senior Document Classification Expert  # Change role
  goal: >
    Achieve 99% classification accuracy  # Update goal
  backstory: >
    With 15 years of experience...  # Modify backstory
```

No code changes required! Agents will use the new configuration on next run.

### **Modifying Tasks**

Edit `config/tasks.yaml` to change task requirements:

```yaml
classify_documents_task:
  description: >
    Classify documents with extra validation steps...
  expected_output: >
    JSON with additional confidence metrics...
  agent: document_classifier_agent
```

### **Using Parameters**

Both configs support parameter injection:

```yaml
agent:
  goal: >
    Process documents for case {case_id} with {priority} priority
```

Pass parameters via inputs:
```python
inputs = {
    'case_id': 'CASE_001',
    'priority': 'high',
    'document_type': 'passport'
}
crew.kickoff(inputs=inputs)
```

---

## Architecture Comparison

### **Before (Legacy)**
```
main.py → orchestrator.py → agents/* (hardcoded roles)
```
- Roles/tasks in Python code
- Imperative orchestration
- Manual state management

### **After (Hybrid)**
```
main.py → flows/ → crew.py → agents/* (reasoning) + config/*.yaml
```
- Roles/tasks in YAML
- Event-driven orchestration
- Type-safe state management
- Reasoning capabilities preserved

---

## Advanced Features

### **1. Reasoning vs Standard Mode**

```python
# With reasoning (Observe-Reason-Plan-Act-Reflect)
results = crew.kickoff_with_reasoning(
    case_id="CASE_001",
    file_paths=files,
    use_reasoning=True  # Default
)

# Standard CrewAI (no reasoning overhead)
results = crew.kickoff_with_reasoning(
    case_id="CASE_001",
    file_paths=files,
    use_reasoning=False
)
```

### **2. Shared Memory Access**

Agents share state through SharedMemory:

```python
crew = KYCAMLCrew(llm=llm)

# Access shared memory
validated_docs = crew.shared_memory.get('validated_documents')
classifications = crew.shared_memory.get('classifications')

# Store custom data
crew.shared_memory.store('custom_key', custom_value)
```

### **3. Flow Visualization**

Generate HTML visualization of your workflow:

```python
flow = DocumentProcessingFlow(llm=llm)
flow.plot(filename="my_workflow.html")
```

Opens a browser with interactive flow diagram showing stages and dependencies.

### **4. Custom Crews**

Create specialized crews for specific needs:

```python
@CrewBase
class CustomCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    @agent
    def custom_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['my_custom_agent'],
            tools=[MyCustomTool()],
            llm=self.llm
        )
    
    @task
    def custom_task(self) -> Task:
        return Task(
            config=self.tasks_config['my_custom_task'],
            agent=self.custom_agent()
        )
```

---

## Testing

### **Validation Tests**

Run structural validation:
```bash
python tests/test_hybrid_validation.py
```

Checks:
- YAML configs exist and are valid
- All required agents/tasks defined
- Code structure correct
- Imports work

### **Integration Tests**

Full integration testing (requires mocking):
```bash
pytest tests/test_crew_integration.py -v
pytest tests/test_flow_pattern.py -v
```

---

## Migration Guide

### **For Existing Code**

1. **No changes required** - legacy code still works
2. **Optional**: Gradually adopt new patterns
3. **Benefit**: New features available alongside old code

### **To Adopt Hybrid Architecture**

1. **Start using `--use-flow` flag** in CLI
2. **Import from `flows`** in Python code
3. **Customize** agents/tasks via YAML
4. **Visualize** your workflows

### **To Customize Agents**

1. Edit `config/agents.yaml`
2. Modify roles, goals, backstories
3. Add parameters with `{param_name}`
4. No code restart needed for config changes

---

## Best Practices

### **1. Use Flow for Complex Workflows**
- Multiple stages with dependencies
- Need state management
- Want visualization

### **2. Use Direct Crew for Simple Tasks**
- Single-stage operations
- Quick one-off tasks
- Testing individual agents

### **3. Configure via YAML**
- Roles and goals → YAML
- Logic and tools → Python code
- Experiment with prompts easily

### **4. Leverage Reasoning When Needed**
- Complex decision-making
- Adaptive strategies
- Quality assessment
- Turn off for simple tasks

### **5. Monitor Shared Memory**
- Check what data flows between stages
- Debug issues by inspecting state
- Use for custom coordination

---

## Troubleshooting

### **Import Errors**
```python
# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

### **Config Not Loading**
- Check YAML syntax (use YAML validator)
- Verify file paths are correct
- Look for typos in agent/task names

### **Flow Not Available**
```python
from flows import FLOW_AVAILABLE

if not FLOW_AVAILABLE:
    # Falls back to crew-based execution
    crew.kickoff_with_reasoning(...)
```

### **LLM Issues**
- Verify API keys in `.env`
- Check model names in `config/llm.json`
- Ensure provider is configured correctly

---

## Performance Considerations

### **Reasoning Overhead**
- Reasoning adds ~20-30% processing time
- Use `use_reasoning=False` for simple tasks
- Worth it for complex decision-making

### **Batch Processing**
- Use batch classification for multiple documents
- Flow handles parallelization automatically
- Consider memory limits with large batches

### **Caching**
- Shared memory caches results between stages
- Avoid re-processing same documents
- Clear cache between cases if needed

---

## Future Enhancements

- [ ] Multi-agent collaboration within stages
- [ ] Hierarchical crew support
- [ ] Advanced error recovery strategies
- [ ] Real-time progress tracking
- [ ] Workflow templates library
- [ ] Custom reasoning strategies
- [ ] Performance profiling tools

---

## Summary

The hybrid architecture provides:

✅ **Flexibility**: Choose between standard, reasoning, or hybrid modes  
✅ **Configurability**: YAML-based agent/task definitions  
✅ **Maintainability**: Standard patterns + custom capabilities  
✅ **Scalability**: Flow-based orchestration for complex workflows  
✅ **Compatibility**: Legacy code still works  

Start with `--use-flow` flag and explore the new capabilities!
