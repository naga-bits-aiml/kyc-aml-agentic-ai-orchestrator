"""
Tools package for KYC-AML Agentic AI Orchestrator.

This package contains all tools that agents can use to perform tasks.
Tools are registered and made available to agents through the tool registry.
Tools can also be auto-discovered from API specifications.
"""
from .document_tools import (
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool
)
from .classifier_tools import (
    classify_document_tool,
    batch_classify_documents_tool,
    get_classification_summary_tool
)
from .file_tools import (
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool
)
from .api_discovery import (
    APIDiscovery,
    ClassifierAPIDiscovery,
    discover_api_tools
)

# Tool Registry - All available tools for agents
ALL_TOOLS = [
    # Document processing tools
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool,
    
    # Classification tools
    classify_document_tool,
    batch_classify_documents_tool,
    get_classification_summary_tool,
    
    # File operation tools
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
]

# Tools grouped by category
DOCUMENT_TOOLS = [
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool,
]

CLASSIFIER_TOOLS = [
    classify_document_tool,
    batch_classify_documents_tool,
    get_classification_summary_tool,
]

FILE_TOOLS = [
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
]

# Tool registry for dynamic access
TOOL_REGISTRY = {
    'all': ALL_TOOLS,
    'document': DOCUMENT_TOOLS,
    'classifier': CLASSIFIER_TOOLS,
    'file': FILE_TOOLS,
}


def get_tools(category: str = 'all'):
    """
    Get tools by category.
    
    Args:
        category: Tool category ('all', 'document', 'classifier', 'file')
        
    Returns:
        List of tools in the specified category
    """
    return TOOL_REGISTRY.get(category, ALL_TOOLS)


def get_tools_for_agent(agent_type: str):
    """
    Get appropriate tools for a specific agent type.
    
    Args:
        agent_type: Type of agent ('intake', 'classifier', 'general')
        
    Returns:
        List of tools appropriate for the agent
    """
    if agent_type == 'intake':
        return DOCUMENT_TOOLS + FILE_TOOLS
    elif agent_type == 'classifier':
        return CLASSIFIER_TOOLS + FILE_TOOLS
    elif agent_type == 'general':
        return ALL_TOOLS
    else:
        return ALL_TOOLS


def discover_and_add_api_tools(base_url: str, api_key: str = None, agent_type: str = 'classifier'):
    """
    Discover API tools and add them to the appropriate category.
    
    Args:
        base_url: Base URL of the API to discover
        api_key: Optional API key for authentication
        agent_type: Agent type to add discovered tools to
        
    Returns:
        List of discovered tools
    """
    from .api_discovery import discover_api_tools
    from utilities import logger
    
    logger.info(f"Discovering tools from API: {base_url}")
    discovered_tools = discover_api_tools(base_url, api_key)
    
    # Add to classifier tools by default
    if discovered_tools:
        CLASSIFIER_TOOLS.extend(discovered_tools)
        ALL_TOOLS.extend(discovered_tools)
        logger.info(f"Added {len(discovered_tools)} discovered tools to {agent_type} category")
    'discover_and_add_api_tools',
    
    # API Discovery
    'APIDiscovery',
    'ClassifierAPIDiscovery',
    'discover_api_tools',
    
    return discovered_tools


__all__ = [
    # Individual tools
    'validate_document_tool',
    'store_document_tool',
    'get_document_metadata_tool',
    'list_documents_tool',
    'classify_document_tool',
    'batch_classify_documents_tool',
    'get_classification_summary_tool',
    'read_file_tool',
    'write_file_tool',
    'check_file_exists_tool',
    'get_file_info_tool',
    
    # Tool collections
    'ALL_TOOLS',
    'DOCUMENT_TOOLS',
    'CLASSIFIER_TOOLS',
    'FILE_TOOLS',
    
    # Helper functions
    'get_tools',
    'get_tools_for_agent',
]
