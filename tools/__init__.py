"""
Tools package for KYC-AML Agentic AI Orchestrator.

This package contains all tools that agents can use to perform tasks.
Tools are organized by entity:
- document_tools: CRUD operations for documents
- case_tools: CRUD operations for cases
- queue_tools: Document queue management
- classification_api_tools: Document classification
- extraction_api_tools: Data extraction
- metadata_tools: Status tracking and error handling
- summary_tools: Processing summary and reporting
- file_tools: Basic file operations
- stage_management_tools: Workflow stage management
"""

# =============================================================================
# DOCUMENT TOOLS - CRUD operations for documents
# =============================================================================
from .document_tools import (
    # Create
    validate_document_tool,
    batch_validate_documents_tool,
    store_document_tool,
    # Read
    get_document_by_id_tool,
    get_document_metadata_tool,
    list_documents_tool,
    list_all_documents_tool,
    resolve_document_paths_tool,
    # Update
    update_document_metadata_tool,
    # Delete
    delete_document_tool,
)

# =============================================================================
# CASE TOOLS - CRUD operations for cases
# =============================================================================
from .case_tools import (
    # Create
    create_case_tool,
    # Read
    get_case_tool,
    list_cases_tool,
    list_documents_by_case_tool,
    # Update
    update_case_tool,
    link_document_to_case_tool,
    unlink_document_from_case_tool,
    # Delete
    delete_case_tool,
    # Summary
    generate_case_summary_tool,
    update_case_summary_tool,
    generate_comprehensive_case_summary_tool,
)

# =============================================================================
# FILE TOOLS - Basic file operations
# =============================================================================
from .file_tools import (
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
)

# =============================================================================
# EXTRACTION TOOLS - Document analysis
# =============================================================================
from .extraction_tools import (
    analyze_document_type,
    check_extraction_quality,
    get_document_info,
)

# =============================================================================
# STAGE MANAGEMENT TOOLS - Workflow stages
# =============================================================================
from .stage_management_tools import (
    move_document_to_stage,
    get_documents_by_stage,
    get_stage_summary,
    add_document_to_case,
    update_document_metadata_in_stage,
)

# =============================================================================
# PIPELINE TOOLS - Queue, Classification, Extraction, Metadata, Summary
# =============================================================================
from .queue_tools import (
    scan_input_path,
    expand_folder,
    split_pdf_to_images,
    build_processing_queue,
    get_next_from_queue,
    get_queue_status,
    mark_document_processed,
)

from .classification_api_tools import (
    classify_document,
    get_classification_result,
    batch_classify_documents,
)

from .extraction_api_tools import (
    extract_document_data,
    get_extraction_result,
    batch_extract_documents,
)

from .metadata_tools import (
    get_document_metadata,
    update_processing_status,
    record_error,
    check_retry_eligible,
    reset_stage_for_retry,
    flag_for_review,
)

from .summary_tools import (
    generate_processing_summary,
    generate_report_text,
    get_document_results,
    export_results_json,
)


# =============================================================================
# LAZY IMPORTS - Avoid circular dependencies
# =============================================================================

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


# =============================================================================
# TOOL COLLECTIONS
# =============================================================================

# Document CRUD tools
DOCUMENT_TOOLS = [
    validate_document_tool,
    batch_validate_documents_tool,
    store_document_tool,
    get_document_by_id_tool,
    get_document_metadata_tool,
    list_documents_tool,
    list_all_documents_tool,
    resolve_document_paths_tool,
    update_document_metadata_tool,
    delete_document_tool,
]

# Case CRUD tools
CASE_TOOLS = [
    create_case_tool,
    get_case_tool,
    list_cases_tool,
    list_documents_by_case_tool,
    update_case_tool,
    link_document_to_case_tool,
    unlink_document_from_case_tool,
    delete_case_tool,
    generate_case_summary_tool,
    update_case_summary_tool,
    generate_comprehensive_case_summary_tool,
]

# File operation tools
FILE_TOOLS = [
    read_file_tool,
    write_file_tool,
    check_file_exists_tool,
    get_file_info_tool,
]

# Extraction tools
EXTRACTION_TOOLS = [
    analyze_document_type,
    check_extraction_quality,
    get_document_info,
]

# Stage management tools
STAGE_TOOLS = [
    move_document_to_stage,
    get_documents_by_stage,
    get_stage_summary,
    add_document_to_case,
    update_document_metadata_in_stage,
]

# Pipeline tools
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

# All tools combined
ALL_TOOLS = (
    DOCUMENT_TOOLS + 
    CASE_TOOLS + 
    FILE_TOOLS + 
    EXTRACTION_TOOLS + 
    STAGE_TOOLS +
    PIPELINE_QUEUE_TOOLS +
    PIPELINE_CLASSIFICATION_TOOLS +
    PIPELINE_EXTRACTION_TOOLS +
    PIPELINE_METADATA_TOOLS +
    PIPELINE_SUMMARY_TOOLS
)

# Classifier tools loaded lazily
CLASSIFIER_TOOLS = None


def _initialize_all_tools():
    """Initialize ALL_TOOLS with classifier tools once available."""
    global CLASSIFIER_TOOLS, ALL_TOOLS
    if CLASSIFIER_TOOLS is None:
        CLASSIFIER_TOOLS = _get_classifier_tools()
        if CLASSIFIER_TOOLS:
            ALL_TOOLS.extend(CLASSIFIER_TOOLS)


def _get_tool_registry():
    """Get tool registry with lazy initialization."""
    _initialize_all_tools()
    return {
        'all': ALL_TOOLS,
        'document': DOCUMENT_TOOLS,
        'case': CASE_TOOLS,
        'classifier': CLASSIFIER_TOOLS or [],
        'extraction': EXTRACTION_TOOLS,
        'file': FILE_TOOLS,
        'stage': STAGE_TOOLS,
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
        category: Tool category:
            - 'all': All tools
            - 'document': Document CRUD tools
            - 'case': Case CRUD tools
            - 'file': File operation tools
            - 'extraction': Document analysis tools
            - 'stage': Workflow stage tools
            - 'classifier': Classification tools
            - 'pipeline_queue': Queue management tools
            - 'pipeline_classification': Classification API tools
            - 'pipeline_extraction': Extraction API tools
            - 'pipeline_metadata': Metadata tools
            - 'pipeline_summary': Summary tools
        
    Returns:
        List of tools in the specified category
    """
    registry = _get_tool_registry()
    return registry.get(category, registry['all'])


def get_tools_for_agent(agent_type: str):
    """
    Get appropriate tools for a specific agent type.
    
    Args:
        agent_type: Type of agent:
            - 'intake': Document intake tools
            - 'classifier': Classification tools
            - 'extraction': Extraction tools
            - 'case': Case management tools
            - 'queue': Queue management tools
            - 'metadata': Metadata tools
            - 'summary': Summary tools
            - 'general': All tools
        
    Returns:
        List of tools appropriate for the agent
    """
    _initialize_all_tools()
    
    if agent_type == 'intake':
        return DOCUMENT_TOOLS + FILE_TOOLS
    elif agent_type == 'classifier':
        return (CLASSIFIER_TOOLS or []) + PIPELINE_CLASSIFICATION_TOOLS + FILE_TOOLS
    elif agent_type == 'extraction':
        return EXTRACTION_TOOLS + PIPELINE_EXTRACTION_TOOLS + FILE_TOOLS
    elif agent_type == 'case':
        return CASE_TOOLS + DOCUMENT_TOOLS
    elif agent_type == 'queue':
        return PIPELINE_QUEUE_TOOLS + DOCUMENT_TOOLS
    elif agent_type == 'metadata':
        return PIPELINE_METADATA_TOOLS
    elif agent_type == 'summary':
        return PIPELINE_SUMMARY_TOOLS + CASE_TOOLS
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
    
    if discovered_tools:
        global CLASSIFIER_TOOLS, ALL_TOOLS
        _initialize_all_tools()
        if CLASSIFIER_TOOLS:
            CLASSIFIER_TOOLS.extend(discovered_tools)
        ALL_TOOLS.extend(discovered_tools)
        logger.info(f"Added {len(discovered_tools)} discovered tools to {agent_type} category")
    
    return discovered_tools


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Document tools
    'validate_document_tool',
    'batch_validate_documents_tool',
    'store_document_tool',
    'get_document_by_id_tool',
    'get_document_metadata_tool',
    'list_documents_tool',
    'list_all_documents_tool',
    'resolve_document_paths_tool',
    'update_document_metadata_tool',
    'delete_document_tool',
    
    # Case tools
    'create_case_tool',
    'get_case_tool',
    'list_cases_tool',
    'list_documents_by_case_tool',
    'update_case_tool',
    'link_document_to_case_tool',
    'unlink_document_from_case_tool',
    'delete_case_tool',
    'generate_case_summary_tool',
    'update_case_summary_tool',
    'generate_comprehensive_case_summary_tool',
    
    # File tools
    'read_file_tool',
    'write_file_tool',
    'check_file_exists_tool',
    'get_file_info_tool',
    
    # Extraction tools
    'analyze_document_type',
    'check_extraction_quality',
    'get_document_info',
    
    # Stage tools
    'move_document_to_stage',
    'get_documents_by_stage',
    'get_stage_summary',
    'add_document_to_case',
    'update_document_metadata_in_stage',
    
    # Tool collections
    'ALL_TOOLS',
    'DOCUMENT_TOOLS',
    'CASE_TOOLS',
    'FILE_TOOLS',
    'EXTRACTION_TOOLS',
    'STAGE_TOOLS',
    'PIPELINE_QUEUE_TOOLS',
    'PIPELINE_CLASSIFICATION_TOOLS',
    'PIPELINE_EXTRACTION_TOOLS',
    'PIPELINE_METADATA_TOOLS',
    'PIPELINE_SUMMARY_TOOLS',
    
    # Helper functions
    'get_tools',
    'get_tools_for_agent',
    'discover_and_add_api_tools',
]
