"""
Document classification tools for agents.

These tools handle document classification using the external classifier API.
"""
from crewai.tools import tool
from typing import Dict, Any, List
from utilities import logger
from agents.classifier_api_client import ClassifierAPIClient


# Initialize API client
_classifier_client = None

def get_classifier_client():
    """Get or create classifier API client."""
    global _classifier_client
    if _classifier_client is None:
        _classifier_client = ClassifierAPIClient()
    return _classifier_client


@tool("Classify Document")
def classify_document_tool(file_path: str) -> Dict[str, Any]:
    """
    Classify a single document using the classifier API.
    
    Args:
        file_path: Path to the document to classify
        
    Returns:
        Dictionary with classification results including:
        - success: Boolean indicating success
        - document_type: Classified document type
        - confidence: Classification confidence score
        - categories: List of possible categories
    """
    logger.info(f"Classifying document: {file_path}")
    
    try:
        client = get_classifier_client()
        result = client.classify_document(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "classification": result
        }
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {
            "success": False,
            "file_path": file_path,
            "error": str(e)
        }


@tool("Batch Classify Documents")
def batch_classify_documents_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Classify multiple documents in batch.
    
    Args:
        file_paths: List of document file paths to classify
        
    Returns:
        Dictionary with batch classification results including:
        - success: Boolean indicating overall success
        - total: Total number of documents
        - successful: Number of successful classifications
        - failed: Number of failed classifications
        - results: List of classification results for each document
    """
    logger.info(f"Batch classifying {len(file_paths)} documents")
    
    results = []
    successful = 0
    failed = 0
    
    client = get_classifier_client()
    
    for file_path in file_paths:
        try:
            result = client.classify_document(file_path)
            results.append({
                "file_path": file_path,
                "success": True,
                "classification": result
            })
            successful += 1
        except Exception as e:
            logger.error(f"Failed to classify {file_path}: {e}")
            results.append({
                "file_path": file_path,
                "success": False,
                "error": str(e)
            })
            failed += 1
    
    return {
        "success": failed == 0,
        "total": len(file_paths),
        "successful": successful,
        "failed": failed,
        "results": results
    }


@tool("Get Classification Summary")
def get_classification_summary_tool(classification_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a summary of classification results.
    
    Args:
        classification_results: List of classification result dictionaries
        
    Returns:
        Dictionary with summary statistics including:
        - total_documents: Total number of documents
        - document_types: Count by document type
        - average_confidence: Average confidence score
        - success_rate: Percentage of successful classifications
    """
    logger.info("Generating classification summary")
    
    if not classification_results:
        return {
            "total_documents": 0,
            "document_types": {},
            "average_confidence": 0.0,
            "success_rate": 0.0
        }
    
    total = len(classification_results)
    successful = sum(1 for r in classification_results if r.get('success', False))
    
    # Count document types
    document_types = {}
    total_confidence = 0.0
    confidence_count = 0
    
    for result in classification_results:
        if result.get('success') and 'classification' in result:
            classification = result['classification']
            
            # Count document type
            doc_type = classification.get('document_type', 'unknown')
            document_types[doc_type] = document_types.get(doc_type, 0) + 1
            
            # Sum confidence
            if 'confidence' in classification:
                total_confidence += classification['confidence']
                confidence_count += 1
    
    avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0.0
    success_rate = (successful / total * 100) if total > 0 else 0.0
    
    return {
        "total_documents": total,
        "successful": successful,
        "failed": total - successful,
        "document_types": document_types,
        "average_confidence": round(avg_confidence, 2),
        "success_rate": round(success_rate, 2)
    }
