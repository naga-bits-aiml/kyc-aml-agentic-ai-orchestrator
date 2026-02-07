# Tools Package

This package contains all tools that agents can access and use to perform their tasks.

## 📂 Tool Organization

Tools are organized by **entity** for clear CRUD operations:

| File | Entity | Operations |
|------|--------|------------|
| `document_tools.py` | Document | Create, Read, Update, Delete |
| `case_tools.py` | Case | Create, Read, Update, Delete, Summary |
| `file_tools.py` | File | Read, Write, Check, Info |
| `queue_tools.py` | Queue | Scan, Expand, Split, Build |
| `classification_api_tools.py` | Classification | Classify, Batch |
| `extraction_api_tools.py` | Extraction | Extract, Batch |
| `metadata_tools.py` | Metadata | Status, Errors, Retry |
| `summary_tools.py` | Summary | Report, Export |
| `stage_management_tools.py` | Workflow | Stage transitions |

## 🔧 Tool Categories

```python
from tools import DOCUMENT_TOOLS, CASE_TOOLS, get_tools

# Get specific category
doc_tools = get_tools('document')  # 10 tools
case_tools = get_tools('case')     # 11 tools
all_tools = get_tools('all')       # 56 tools

# Get tools for specific agent
from tools import get_tools_for_agent
intake_tools = get_tools_for_agent('intake')
```

**Features:**
- ✅ Entity-based tool organization (Document, Case)
- ✅ CRUD operations for each entity
- ✅ **API Auto-Discovery** via `/info` or OpenAPI specs
- ✅ Dynamic tool generation from API schemas
- ✅ Tool registry and categorization

## 🔍 API Auto-Discovery

### Discover Tools from APIs

```python
from tools import discover_and_add_api_tools, APIDiscovery
from utilities import config

# Automatically discover and register tools from an API
discovered_tools = discover_and_add_api_tools(
    base_url=config.classifier_api_url,
    api_key=config.classifier_api_key,
    agent_type='classifier'
)

print(f"Discovered {len(discovered_tools)} tools")
```

### Discovery Methods

**1. Via /info Endpoint:**
```python
from tools.api_discovery import APIDiscovery

discovery = APIDiscovery("https://api.example.com", api_key="key")
info = discovery.discover_from_info_endpoint("/info")
tools = discovery.auto_generate_tools()
```

**2. Via OpenAPI/Swagger Spec:**
```python
discovery = APIDiscovery("https://api.example.com")
spec = discovery.discover_from_openapi("/openapi.json")
tools = discovery.auto_generate_tools()
```

**3. Specialized Classifier Discovery:**
```python
from tools.api_discovery import ClassifierAPIDiscovery

classifier_discovery = ClassifierAPIDiscovery()
tools = classifier_discovery.discover_and_generate_tools()
```

### Auto-Generated Tools

Tools are automatically generated with:
- ✅ Proper function names based on endpoint
- ✅ Descriptive docstrings from API specs
- ✅ Parameter handling (path, query, body)
- ✅ Error handling and logging
- ✅ CrewAI `@tool` decorator applied

## 🛠️ Tool Categories

### Document Tools ([document_tools.py](document_tools.py))
Tools for document intake, validation, and management:

- **`validate_document_tool`** - Validate document file format, size, and extension
- **`store_document_tool`** - Store document with unique naming and metadata
- **`get_document_metadata_tool`** - Retrieve document metadata
- **`list_documents_tool`** - List documents in a directory with filtering

### Classifier Tools ([classifier_tools.py](classifier_tools.py))
Tools for document classification:

- **`classify_document_tool`** - Classify single document via API
- **`batch_classify_documents_tool`** - Classify multiple documents in batch
- **`get_classification_summary_tool`** - Generate classification statistics

### File Tools ([file_tools.py](file_tools.py))
Basic file operation tools:

- **`read_file_tool`** - Read text file contents
- **`write_file_tool`** - Write content to file
- **`check_file_exists_tool`** - Check if file/directory exists
- **`get_file_info_tool`** - Get detailed file information

### API Discovery ([api_discovery.py](api_discovery.py))
Tools for discovering and auto-generating tools from APIs:

- **`APIDiscovery`** - Class for discovering API endpoints
- **`ClassifierAPIDiscovery`** - Specialized discovery for classifier API
- **`discover_api_tools()`** - Convenience function to discover and generate tools

## 📋 Tool Registry

### Getting Tools for Agents

```python
from tools import get_tools_for_agent, get_tools

# Get tools for specific agent type
intake_tools = get_tools_for_agent('intake')
classifier_tools = get_tools_for_agent('classifier')
all_tools = get_tools_for_agent('general')

# Get tools by category
document_tools = get_tools('document')
classifier_tools = get_tools('classifier')
file_tools = get_tools('file')
all_tools = get_tools('all')
```

### Tool Assignment by Agent Type

**Intake Agent** gets:
- All document tools (validate, store, metadata, list)
- All file tools (read, write, check, info)

**Classifier Agent** gets:
- All classifier tools (classify, batch, summary)
- All file tools (read, write, check, info)

**General Agent** gets:
- All tools from all categories

## 🎯 Using Tools in Agents

### CrewAI Agent with Tools

```python
from crewai import Agent
from tools import get_tools_for_agent

# Create agent with appropriate tools
intake_agent = Agent(
    role="Document Intake Specialist",
    goal="Validate and store documents securely",
    backstory="Expert in document handling and validation",
    tools=get_tools_for_agent('intake'),  # Auto-assigns document + file tools
    verbose=True
)

classifier_agent = Agent(
    role="Document Classifier",
    goal="Classify documents accurately",
    backstory="Expert in document classification",
    tools=get_tools_for_agent('classifier'),  # Auto-assigns classifier + file tools
    verbose=True
)
```

### Accessing Individual Tools

```python
from tools import (
    validate_document_tool,
    classify_document_tool,
    store_document_tool
)

# Use tools directly
validation_result = validate_document_tool("path/to/document.pdf")
if validation_result['is_valid']:
    storage_result = store_document_tool("path/to/document.pdf")
    classification = classify_document_tool(storage_result['stored_path'])
```

## 🔧 Tool Decorators

All tools use the `@tool` decorator from CrewAI:

```python
from crewai_tools import tool

@tool("Tool Name")
def my_tool(param: str) -> Dict[str, Any]:
    """
    Tool description that helps the agent understand when to use it.
    
    Args:
        param: Parameter description
        
    Returns:
        Dictionary with results
    """
    # Tool implementation
    pass
```

## 📊 Tool Response Format

All tools return standardized dictionary responses:

```python
{
    "success": True,           # Boolean indicating success
    Option 1: Manual Tool Creation

```python
# tools/my_tools.py
from crewai_tools import tool
from utilities import logger

@tool("My Custom Tool")
def my_custom_tool(param: str) -> Dict[str, Any]:
    """
    Description of what the tool does.
    
    Args:
        param: Parameter description
        
    Returns:
        Result dictionary
    """
    logger.info(f"Running custom tool with: {param}")
    try:
        # Tool logic here
        return {"success": True, "result": "done"}
    except Exception as e:
        logger.error(f"Tool failed: {e}")
        return {"success": False, "error": str(e)}
```

### Option 2: Auto-Discovery from API

```python
from tools import discover_and_add_api_tools

# Discover and auto-generate tools
tools = discover_and_add_api_tools(
    base_url="https://api.example.com",
    api_key="your_api_key",
    agent_type='classifier'
)

# Tools are automatically registered and available!
```

### Option 3: Manual Endpoint Definition

```python
from tools.api_discovery import APIDiscovery

discovery = APIDiscovery("https://api.example.com", "api_key")

# Define endpoint manually
discovery.discovered_endpoints["POST /custom"] = {
    "path": "/custom",
    "method": "POST",
    "summary": "Custom Endpoint",
    "description": "My custom endpoint"
}

# Generate tool
tools = discovery.auto_generate_tools()
    logger.info(f"Running custom tool with: {param}")
    try:
        # Tool logic here
        return {"success": True, "result": "done"}
    except Exception as e:
5. **API Auto-Discovery** - Tools automatically generated from API specs

### Discovery Flow

```
1. Check Tool Registry → Manual tools
2. Call discover_and_add_api_tools() → Auto-discover from APIs
3. Generate tools from OpenAPI/info → Create tool functions
4. Register in categories → Add to CLASSIFIER_TOOLS, etc.
5. Assign to agents → get_tools_for_agent('classifier')
```
        logger.error(f"Tool failed: {e}")
        return {"success": False, "error": str(e)}
```

### 2. Register in __init__.py

```python
# tools/__init__.py
from .my_tools import my_custom_tool

# Add to appropriate category
MY_TOOLS = [my_custom_tool]

# Add to registry
TOOL_REGISTRY['my_category'] = MY_TOOLS
```

### 3. Update get_tools_for_agent

```python
def get_tools_for_agent(agent_type: str):
    if agent_type == 'my_agent':
        return MY_TOOLS + FILE_TOOLS
    # ... existing code
```

## 🔍 Tool Discovery

Agents discover tools through:

1. **Tool Registry** - Centralized registry in `tools/__init__.py`
2. **Category-based Access** - Tools grouped by functionality
3. **Agent Type Mapping** - Automatic tool assignment based on agent type
4. **Tool Descriptions** - Docstrings help agents understand tool purpose

## ✅ Best Practices

1. **Single Responsibility** - Each tool should do one thing well
2. **Descriptive Names** - Use clear, action-oriented names ending in `_tool`
3. **Detailed Docstrings** - Help agents understand when to use the tool
4. **Error Handling** - Always wrap in try/except and return standardized responses
5. **Logging** - Log tool usage for debugging and monitoring
6. **Type Hints** - Use type hints for parameters and returns
7. **Validation** - Validate inputs before processing

## 📝 Example: Complete Tool Workflow

```python
from crewai import Agent, Task, Crew
from tools import get_tools_for_agent

# Create agents with tools
intake_agent = Agent(
    role="Document Processor",
    goal="Process incoming documents",
    tools=get_tools_for_agent('intake'),
    verbose=True
)

classifier_agent = Agent(
    role="Document Classifier",
    goal="Classify processed documents",
    tools=get_tools_for_agent('classifier'),
    verbose=True
)

# Create tasks
intake_task = Task(
    description="Validate and store document.pdf",
    agent=intake_agent,
    expected_output="Document stored with metadata"
)

classify_task = Task(
    description="Classify the stored document",
    agent=classifier_agent,
    expected_output="Document classification result"
)

# Execute
crew = Crew(agents=[intake_agent, classifier_agent], tasks=[intake_task, classify_task])
result = crew.kickoff()
```

---

All tools are automatically available to agents through the tool registry!
