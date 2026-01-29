"""Flow module initialization.

This module provides compatibility wrappers that delegate to the new pipeline_flow.
For new development, use pipeline_flow.py and pipeline_crew.py directly.
"""

from .document_processing_flow import (
    kickoff_flow,
    add_directory_to_queue,
    add_files_to_queue,
    get_queue_status,
    process_next_document_from_queue
)

__all__ = [
    'kickoff_flow',
    'add_directory_to_queue',
    'add_files_to_queue',
    'get_queue_status',
    'process_next_document_from_queue'
]
