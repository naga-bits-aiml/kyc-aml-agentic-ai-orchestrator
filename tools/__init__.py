"""
Tools package for KYC-AML Agentic AI Orchestrator.

This package contains all tools that agents can use to perform tasks.
Tools are registered and made available to agents through the tool registry.
Tools can also be auto-discovered from API specifications.

Pipeline Agent Tools (NEW):
- queue_tools: Scan paths, expand folders, split PDFs, build queue
- classification_api_tools: REST API classification with retry
- extraction_api_tools: REST API extraction with retry
- metadata_tools: Status tracking, error handling, retry management
- summary_tools: Processing summary and reporting
"""
from .document_tools import (
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool
)
from .file_tools import (
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool
)
from .extraction_tools import (
    analyze_document_type,
    check_extraction_quality,
    get_document_info
)
from .stage_management_tools import (
    move_document_to_stage,
    get_documents_by_stage,
    get_stage_summary,
    add_document_to_case,
    update_document_metadata_in_stage
)

# Pipeline Agent Tools - NEW
from .queue_tools import (
    scan_input_path,
    expand_folder,
    split_pdf_to_images,
    build_processing_queue,
    get_next_from_queue,
    get_queue_status,
    mark_document_processed
)
from .classification_api_tools import (
    classify_document,
    get_classification_result,
    batch_classify_documents
)
from .extraction_api_tools import (
    extract_document_data,
    get_extraction_result,
    batch_extract_documents
)
from .metadata_tools import (
    get_document_metadata,
    update_processing_status,
    record_error,
    check_retry_eligible,
    reset_stage_for_retry,
    flag_for_review
)
from .summary_tools import (
    generate_processing_summary,
    generate_report_text,
    get_document_results,
    export_results_json
)

# Lazy imports to avoid circular dependencies
def _get_classifier_tools():
    """Lazy load classifier tools to avoid circular imports."""
    try:
        from .classifier_tools import (
            get_classifier_api_info_tool,
            make_classifier_api_request,
            extract_document_file_path_tool
        )
        return [
            get_classifier_api_info_tool,
            make_classifier_api_request,
            extract_document_file_path_tool,
        ]
    except ImportError:
        return []

def _get_api_discovery():
    """Lazy load API discovery to avoid circular imports."""
    try:
        from .api_discovery import (
            APIDiscovery,
            ClassifierAPIDiscovery,
            discover_api_tools
        )
        return {
            'APIDiscovery': APIDiscovery,
            'ClassifierAPIDiscovery': ClassifierAPIDiscovery,
            'discover_api_tools': discover_api_tools,
        }
    except ImportError:
        return {}

# Tool Registry - All available tools for agents
ALL_TOOLS = [
    # Document processing tools
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool,
    
    # Extraction tools
    analyze_document_type,
    check_extraction_quality,
    get_document_info,
    
    # File operation tools
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
]

# Pipeline Agent Tools (NEW)
PIPELINE_QUEUE_TOOLS = [
    scan_input_path,
    expand_folder,
    split_pdf_to_images,
    build_processing_queue,
    get_next_from_queue,
    get_queue_status,
    mark_document_processed,
]

PIPELINE_CLASSIFICATION_TOOLS = [
    classify_document,
    get_classification_result,
    batch_classify_documents,
]

PIPELINE_EXTRACTION_TOOLS = [
    extract_document_data,
    get_extraction_result,
    batch_extract_documents,
]

PIPELINE_METADATA_TOOLS = [
    get_document_metadata,
    update_processing_status,
    record_error,
    check_retry_eligible,
    reset_stage_for_retry,
    flag_for_review,
]

PIPELINE_SUMMARY_TOOLS = [
    generate_processing_summary,
    generate_report_text,
    get_document_results,
    export_results_json,
]

# Tools grouped by category
DOCUMENT_TOOLS = [
    validate_document_tool,
    store_document_tool,
    get_document_metadata_tool,
    list_documents_tool,
]

# Classifier tools loaded lazily
CLASSIFIER_TOOLS = None

EXTRACTION_TOOLS = [
    analyze_document_type,
    check_extraction_quality,
    get_document_info,
]

FILE_TOOLS = [
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
]


def _initialize_all_tools():
    """Initialize ALL_TOOLS with classifier tools once available."""
    global CLASSIFIER_TOOLS, ALL_TOOLS
    if CLASSIFIER_TOOLS is None:
        CLASSIFIER_TOOLS = _get_classifier_tools()
        ALL_TOOLS.extend(CLASSIFIER_TOOLS)
        # Also add pipeline tools
        ALL_TOOLS.extend(PIPELINE_QUEUE_TOOLS)
        ALL_TOOLS.extend(PIPELINE_CLASSIFICATION_TOOLS)
        ALL_TOOLS.extend(PIPELINE_EXTRACTION_TOOLS)
        ALL_TOOLS.extend(PIPELINE_METADATA_TOOLS)
        ALL_TOOLS.extend(PIPELINE_SUMMARY_TOOLS)


def _get_tool_registry():
    """Get tool registry with lazy initialization."""
    _initialize_all_tools()
    return {
        'all': ALL_TOOLS,
        'document': DOCUMENT_TOOLS,
        'classifier': CLASSIFIER_TOOLS or [],
        'extraction': EXTRACTION_TOOLS,
        'file': FILE_TOOLS,
        # Pipeline tool categories
        'pipeline_queue': PIPELINE_QUEUE_TOOLS,
        'pipeline_classification': PIPELINE_CLASSIFICATION_TOOLS,
        'pipeline_extraction': PIPELINE_EXTRACTION_TOOLS,
        'pipeline_metadata': PIPELINE_METADATA_TOOLS,
        'pipeline_summary': PIPELINE_SUMMARY_TOOLS,
    }


def get_tools(category: str = 'all'):
    """
    Get tools by category.
    
    Args:
        category: Tool category ('all', 'document', 'classifier', 'extraction', 'file',
                  'pipeline_queue', 'pipeline_classification', 'pipeline_extraction',
                  'pipeline_metadata', 'pipeline_summary')
        
    Returns:
        List of tools in the specified category
    """
    registry = _get_tool_registry()
    return registry.get(category, registry['all'])


def get_tools_for_agent(agent_type: str):
    """
    Get appropriate tools for a specific agent type.
    
    Args:
        agent_type: Type of agent ('intake', 'classifier', 'extraction', 'general',
                    'queue', 'metadata', 'summary')
        
    Returns:
        List of tools appropriate for the agent
    """
    _initialize_all_tools()
    
    if agent_type == 'intake':
        return DOCUMENT_TOOLS + FILE_TOOLS
    elif agent_type == 'classifier':
        return (CLASSIFIER_TOOLS or []) + FILE_TOOLS
    elif agent_type == 'extraction':
        return EXTRACTION_TOOLS + FILE_TOOLS
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
    
    # Add to classifier tools
    if discovered_tools:
        global CLASSIFIER_TOOLS, ALL_TOOLS
        _initialize_all_tools()
        if CLASSIFIER_TOOLS:
            CLASSIFIER_TOOLS.extend(discovered_tools)
        ALL_TOOLS.extend(discovered_tools)
        logger.info(f"Added {len(discovered_tools)} discovered tools to {agent_type} category")
    
    return discovered_tools


__all__ = [
    # Individual tools
    'validate_document_tool',
    'store_document_tool',
    'get_document_metadata_tool',
    'list_documents_tool',
    'analyze_document_type',
    'check_extraction_quality',
    'get_document_info',
    'read_file_tool',
    'write_file_tool',
    'check_file_exists_tool',
    'get_file_info_tool',
    
    # Tool collections
    'ALL_TOOLS',
    'DOCUMENT_TOOLS',
    'EXTRACTION_TOOLS',
    'FILE_TOOLS',
    
    # Helper functions
    'get_tools',
    'get_tools_for_agent',
    'discover_and_add_api_tools',
]
