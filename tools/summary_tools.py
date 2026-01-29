"""
Summary Agent Tools - Processing summary and reporting.

These tools handle:
- Reading all metadata files
- Aggregating processing results
- Generating summary reports
- Final status reporting

Used by SummaryAgent after queue completion.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from collections import Counter
from langchain_core.tools import tool

# Import utilities
try:
    from utilities import logger, settings
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    class Settings:
        documents_dir = "./documents"
    settings = Settings()


# ==================== TOOL DEFINITIONS ====================

@tool
def generate_processing_summary() -> Dict[str, Any]:
    """
    Generate a comprehensive summary of all document processing.
    
    Reads all metadata files and aggregates statistics about
    processing status, document types, errors, and review flags.
    
    Returns:
        Dictionary with:
        - total_documents: Total number of documents
        - by_status: Counts by processing status
        - by_type: Counts by document type
        - errors: List of documents with errors
        - requires_review: List of flagged documents
        - processing_times: Average processing times
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    
    if not intake_dir.exists():
        return {
            "success": True,
            "total_documents": 0,
            "message": "No documents found in intake folder"
        }
    
    # Collect all metadata
    documents = []
    for metadata_file in intake_dir.glob("*.metadata.json"):
        try:
            with open(metadata_file, 'r') as f:
                documents.append(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to read {metadata_file}: {e}")
    
    if not documents:
        return {
            "success": True,
            "total_documents": 0,
            "message": "No metadata files found"
        }
    
    # Aggregate statistics
    status_counts = Counter()
    type_counts = Counter()
    errors = []
    requires_review = []
    
    classification_times = []
    extraction_times = []
    
    for doc in documents:
        # Skip parent PDFs (only count page images)
        if doc.get("child_document_ids"):
            continue
        
        # Count by status
        status = doc.get("processing_status", "unknown")
        status_counts[status] += 1
        
        # Count by document type
        doc_type = doc.get("classification", {}).get("document_type", "unclassified")
        type_counts[doc_type] += 1
        
        # Collect errors
        if doc.get("last_error"):
            errors.append({
                "document_id": doc.get("document_id"),
                "filename": doc.get("original_filename"),
                "error": doc.get("last_error"),
                "stage": _get_failed_stage(doc)
            })
        
        # Collect review flags
        if doc.get("requires_review"):
            requires_review.append({
                "document_id": doc.get("document_id"),
                "filename": doc.get("original_filename"),
                "reason": doc.get("review_reason", "Unknown")
            })
        
        # Calculate processing times
        class_data = doc.get("classification", {})
        if class_data.get("started_at") and class_data.get("completed_at"):
            try:
                start = datetime.fromisoformat(class_data["started_at"])
                end = datetime.fromisoformat(class_data["completed_at"])
                classification_times.append((end - start).total_seconds())
            except:
                pass
        
        extract_data = doc.get("extraction", {})
        if extract_data.get("started_at") and extract_data.get("completed_at"):
            try:
                start = datetime.fromisoformat(extract_data["started_at"])
                end = datetime.fromisoformat(extract_data["completed_at"])
                extraction_times.append((end - start).total_seconds())
            except:
                pass
    
    # Calculate averages
    avg_classification_time = sum(classification_times) / len(classification_times) if classification_times else 0
    avg_extraction_time = sum(extraction_times) / len(extraction_times) if extraction_times else 0
    
    return {
        "success": True,
        "total_documents": len(documents),
        "by_status": dict(status_counts),
        "by_type": dict(type_counts),
        "completed": status_counts.get("completed", 0),
        "failed": status_counts.get("failed", 0),
        "pending": status_counts.get("pending", 0) + status_counts.get("queued", 0),
        "errors": errors,
        "error_count": len(errors),
        "requires_review": requires_review,
        "review_count": len(requires_review),
        "processing_times": {
            "avg_classification_seconds": round(avg_classification_time, 2),
            "avg_extraction_seconds": round(avg_extraction_time, 2),
            "total_classification_samples": len(classification_times),
            "total_extraction_samples": len(extraction_times)
        },
        "generated_at": datetime.now().isoformat()
    }


def _get_failed_stage(doc: Dict) -> str:
    """Determine which stage failed for a document."""
    for stage in ["extraction", "classification", "queue"]:
        if doc.get(stage, {}).get("status") == "failed":
            return stage
    return "unknown"


@tool
def generate_report_text() -> str:
    """
    Generate a human-readable processing report.
    
    Returns:
        Formatted text report suitable for display or logging.
    """
    summary = generate_processing_summary.invoke({})
    
    if not summary.get("success"):
        return f"Error generating report: {summary.get('error', 'Unknown error')}"
    
    lines = [
        "=" * 60,
        "DOCUMENT PROCESSING SUMMARY REPORT",
        "=" * 60,
        f"Generated: {summary.get('generated_at', 'N/A')}",
        "",
        "OVERVIEW",
        "-" * 40,
        f"  Total Documents: {summary.get('total_documents', 0)}",
        f"  Completed: {summary.get('completed', 0)}",
        f"  Failed: {summary.get('failed', 0)}",
        f"  Pending: {summary.get('pending', 0)}",
        "",
        "BY STATUS",
        "-" * 40,
    ]
    
    for status, count in summary.get("by_status", {}).items():
        lines.append(f"  {status}: {count}")
    
    lines.extend([
        "",
        "BY DOCUMENT TYPE",
        "-" * 40,
    ])
    
    for doc_type, count in summary.get("by_type", {}).items():
        lines.append(f"  {doc_type}: {count}")
    
    # Processing times
    times = summary.get("processing_times", {})
    lines.extend([
        "",
        "PROCESSING TIMES (averages)",
        "-" * 40,
        f"  Classification: {times.get('avg_classification_seconds', 0):.2f}s",
        f"  Extraction: {times.get('avg_extraction_seconds', 0):.2f}s",
    ])
    
    # Errors
    errors = summary.get("errors", [])
    if errors:
        lines.extend([
            "",
            f"ERRORS ({len(errors)})",
            "-" * 40,
        ])
        for err in errors[:10]:  # Show first 10
            lines.append(f"  • {err['document_id']}: {err['error'][:50]}...")
        if len(errors) > 10:
            lines.append(f"  ... and {len(errors) - 10} more")
    
    # Review flags
    reviews = summary.get("requires_review", [])
    if reviews:
        lines.extend([
            "",
            f"REQUIRES REVIEW ({len(reviews)})",
            "-" * 40,
        ])
        for rev in reviews[:10]:
            lines.append(f"  • {rev['document_id']}: {rev['reason']}")
        if len(reviews) > 10:
            lines.append(f"  ... and {len(reviews) - 10} more")
    
    lines.extend([
        "",
        "=" * 60,
        "END OF REPORT",
        "=" * 60,
    ])
    
    return "\n".join(lines)


@tool
def get_document_results(document_ids: List[str]) -> Dict[str, Any]:
    """
    Get processing results for specific documents.
    
    Args:
        document_ids: List of document IDs to retrieve
        
    Returns:
        Dictionary with results for each document
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    results = {}
    
    for doc_id in document_ids:
        metadata_path = intake_dir / f"{doc_id}.metadata.json"
        
        if not metadata_path.exists():
            results[doc_id] = {"error": "Not found"}
            continue
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            results[doc_id] = {
                "filename": metadata.get("original_filename"),
                "status": metadata.get("processing_status"),
                "document_type": metadata.get("classification", {}).get("document_type"),
                "confidence": metadata.get("classification", {}).get("confidence"),
                "extracted_fields": list(metadata.get("extraction", {}).get("extracted_fields", {}).keys()),
                "error": metadata.get("last_error"),
                "requires_review": metadata.get("requires_review", False)
            }
        except Exception as e:
            results[doc_id] = {"error": str(e)}
    
    return {
        "success": True,
        "document_count": len(document_ids),
        "results": results
    }


@tool
def export_results_json(output_path: str = None) -> Dict[str, Any]:
    """
    Export all processing results to a JSON file.
    
    Args:
        output_path: Optional custom output path
        
    Returns:
        Dictionary with export result
    """
    if not output_path:
        output_path = str(Path(settings.documents_dir) / "processing_results.json")
    
    summary = generate_processing_summary.invoke({})
    
    # Get detailed results for all documents
    intake_dir = Path(settings.documents_dir) / "intake"
    all_metadata = []
    
    if intake_dir.exists():
        for metadata_file in intake_dir.glob("*.metadata.json"):
            try:
                with open(metadata_file, 'r') as f:
                    all_metadata.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to read {metadata_file}: {e}")
    
    export_data = {
        "summary": summary,
        "documents": all_metadata,
        "exported_at": datetime.now().isoformat()
    }
    
    try:
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return {
            "success": True,
            "output_path": output_path,
            "document_count": len(all_metadata),
            "message": f"Exported results to {output_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to export: {str(e)}"
        }
