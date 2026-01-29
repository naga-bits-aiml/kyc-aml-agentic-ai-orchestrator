"""
Classification Agent Tools - REST API calls for document classification.

These tools handle:
- External REST API calls for document classification
- Retry logic for transient failures
- Result parsing and validation
- Metadata updates with classification results

Uses the /predict endpoint for classifying Indian identity documents.
All REST calls are wrapped in tools with proper error handling.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.tools import tool

# Import utilities
try:
    from utilities import logger, settings, config
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    class Settings:
        documents_dir = "./documents"
    settings = Settings()
    class Config:
        classifier_api_url = "http://localhost:8000"
        classifier_timeout = 30
    config = Config()


# ==================== CONFIGURATION ====================

def get_api_config() -> Dict[str, Any]:
    """
    Get classifier API configuration.
    Uses the /predict endpoint for document classification.
    
    Returns:
        Dictionary with API configuration
    """
    api_info = {
        "base_url": config.classifier_api_url.rstrip('/'),
        "endpoint": "/predict",
        "full_url": f"{config.classifier_api_url.rstrip('/')}/predict",
        "method": "POST",
        "content_type": "multipart/form-data",
        "description": "Classify Indian identity documents",
        "supported_classes": ["Aadhar", "Driving License", "PAN Card", "Passport", "Voter ID"],
        "supported_formats": ["image/jpeg", "image/png", "image/bmp", "image/tiff"],
        "timeout": config.classifier_timeout,
        "max_retries": 3,
        "retry_delay": 2
    }
    
    logger.debug(f"Classifier API config: {api_info['full_url']}")
    return api_info


# ==================== HELPER FUNCTIONS ====================

def make_api_request_with_retry(
    url: str,
    method: str = "POST",
    files: Optional[Dict] = None,
    data: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: int = 2
) -> Dict[str, Any]:
    """
    Make HTTP request with retry logic for transient failures.
    
    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, etc.)
        files: Files to upload
        data: Form data or JSON payload
        headers: HTTP headers
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Dictionary with:
        - success: Boolean
        - status_code: HTTP status code
        - response: Parsed JSON response or raw text
        - error: Error message if failed
        - attempts: Number of attempts made
    """
    headers = headers or {}
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"API request attempt {attempt}/{max_retries}: {method} {url}")
            
            if method.upper() == "POST":
                if files:
                    response = requests.post(url, files=files, data=data, headers=headers, timeout=timeout)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == "GET":
                response = requests.get(url, params=data, headers=headers, timeout=timeout)
            else:
                return {
                    "success": False,
                    "status_code": None,
                    "response": None,
                    "error": f"Unsupported HTTP method: {method}",
                    "attempts": attempt
                }
            
            # Check for success
            if response.status_code == 200:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    result = response.text
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": result,
                    "error": None,
                    "attempts": attempt
                }
            
            # Retryable errors (5xx, 429)
            if response.status_code >= 500 or response.status_code == 429:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"Retryable error: {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay * attempt)  # Exponential backoff
                continue
            
            # Non-retryable client errors (4xx except 429)
            return {
                "success": False,
                "status_code": response.status_code,
                "response": response.text,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "attempts": attempt
            }
            
        except requests.exceptions.Timeout:
            last_error = f"Request timeout after {timeout}s"
            logger.warning(f"Timeout on attempt {attempt}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {str(e)}"
            logger.warning(f"Connection error on attempt {attempt}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    return {
        "success": False,
        "status_code": None,
        "response": None,
        "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
        "attempts": max_retries
    }


# ==================== TOOL DEFINITIONS ====================

@tool
def classify_document(document_id: str) -> Dict[str, Any]:
    """
    Call external REST API to classify a document.
    
    Reads the document file from the intake folder and sends it
    to the classification API. Updates the document's metadata
    with the classification result.
    
    Args:
        document_id: Document ID to classify
        
    Returns:
        Dictionary with:
        - success: Boolean
        - document_id: Document ID
        - document_type: Classified document type
        - confidence: Classification confidence score
        - api_response: Full API response
        - error: Error message if failed
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    # Load document metadata
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "document_type": None,
            "confidence": None,
            "error": f"Metadata not found for document: {document_id}"
        }
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Get document file path
    stored_path = metadata.get("stored_path")
    if not stored_path or not Path(stored_path).exists():
        return {
            "success": False,
            "document_id": document_id,
            "document_type": None,
            "confidence": None,
            "error": f"Document file not found: {stored_path}"
        }
    
    # Update metadata: classification started
    metadata["classification"]["status"] = "processing"
    metadata["classification"]["started_at"] = datetime.now().isoformat()
    metadata["updated_at"] = datetime.now().isoformat()
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Get API configuration
    api_config = get_api_config()
    
    # Log the classification request
    logger.info(f"Classifying document {document_id} via {api_config['full_url']}")
    
    # Make API request to /predict endpoint
    try:
        with open(stored_path, 'rb') as f:
            files = {"file": (Path(stored_path).name, f, "application/octet-stream")}
            
            result = make_api_request_with_retry(
                url=api_config["full_url"],
                method="POST",
                files=files,
                headers={},
                timeout=api_config.get("timeout", 30),
                max_retries=api_config.get("max_retries", 3),
                retry_delay=api_config.get("retry_delay", 2)
            )
    except Exception as e:
        result = {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
            "attempts": 0
        }
    
    # Update metadata with result
    metadata["classification"]["completed_at"] = datetime.now().isoformat()
    metadata["classification"]["retry_count"] = result.get("attempts", 0)
    
    if result["success"]:
        api_response = result["response"]
        
        # Extract classification details from /predict API response format
        # Expected: {"predicted_class": "...", "confidence": 0.95, "probabilities": {...}}
        if isinstance(api_response, dict):
            document_type = (
                api_response.get("predicted_class") or 
                api_response.get("document_type") or 
                api_response.get("type") or 
                api_response.get("class")
            )
            confidence = (
                api_response.get("confidence") or 
                api_response.get("score") or 
                api_response.get("probability")
            )
            probabilities = api_response.get("probabilities", {})
        else:
            document_type = str(api_response)
            confidence = None
            probabilities = {}
        
        metadata["classification"]["status"] = "completed"
        metadata["classification"]["result"] = api_response
        metadata["classification"]["document_type"] = document_type
        metadata["classification"]["confidence"] = confidence
        metadata["classification"]["probabilities"] = probabilities
        
        # Log classification result
        logger.info(
            f"Classification successful for {document_id}: "
            f"{document_type} (confidence: {confidence:.2%})" if confidence else f"{document_type}"
        )
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "document_type": document_type,
            "confidence": confidence,
            "probabilities": probabilities,
            "api_response": api_response,
            "error": None
        }
    else:
        metadata["classification"]["status"] = "failed"
        metadata["classification"]["error"] = result["error"]
        metadata["last_error"] = result["error"]
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": False,
            "document_id": document_id,
            "document_type": None,
            "confidence": None,
            "error": result["error"]
        }


@tool
def get_classification_result(document_id: str) -> Dict[str, Any]:
    """
    Get the classification result for a document from its metadata.
    
    Args:
        document_id: Document ID to check
        
    Returns:
        Dictionary with classification status and result
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "status": "not_found",
            "error": f"Metadata not found for document: {document_id}"
        }
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    classification = metadata.get("classification", {})
    
    return {
        "success": True,
        "document_id": document_id,
        "status": classification.get("status", "pending"),
        "document_type": classification.get("document_type"),
        "confidence": classification.get("confidence"),
        "result": classification.get("result"),
        "error": classification.get("error"),
        "started_at": classification.get("started_at"),
        "completed_at": classification.get("completed_at")
    }


@tool
def batch_classify_documents(document_ids: list) -> Dict[str, Any]:
    """
    Classify multiple documents in sequence.
    
    Args:
        document_ids: List of document IDs to classify
        
    Returns:
        Dictionary with batch results
    """
    results = []
    success_count = 0
    failed_count = 0
    
    for doc_id in document_ids:
        result = classify_document.invoke({"document_id": doc_id})
        results.append(result)
        
        if result["success"]:
            success_count += 1
        else:
            failed_count += 1
    
    return {
        "success": failed_count == 0,
        "total": len(document_ids),
        "succeeded": success_count,
        "failed": failed_count,
        "results": results,
        "message": f"Classified {success_count}/{len(document_ids)} documents"
    }
