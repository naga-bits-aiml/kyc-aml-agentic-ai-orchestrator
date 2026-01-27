"""
Production-Grade Document Classification Tools for Agents.

These tools provide REST API capabilities for document classification using the /predict endpoint
with detailed logging of all operations including API requests and predictions.
"""
from crewai.tools import tool
from typing import Dict, Any, Optional
from pathlib import Path
from utilities import logger, config
import requests
import json
import time


def get_classifier_api_info() -> Dict[str, Any]:
    """
    Get classifier API information.
    Logs API configuration for transparency.
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
        "timeout": config.classifier_timeout
    }
    
    # Log API info
    logger.critical(
        "\n" + "="*80 + "\n" +
        "🔍 CLASSIFIER API INFORMATION\n" +
        "="*80 + "\n" +
        f"Base URL: {api_info['base_url']}\n" +
        f"Endpoint: {api_info['endpoint']}\n" +
        f"Full URL: {api_info['full_url']}\n" +
        f"Method: {api_info['method']}\n" +
        f"Supported Classes: {', '.join(api_info['supported_classes'])}\n" +
        f"Timeout: {api_info['timeout']}s\n" +
        "="*80
    )
    
    return api_info


@tool("Get Classifier API Info")
def get_classifier_api_info_tool() -> Dict[str, Any]:
    """
    Get information about the classifier API /predict endpoint.
    Use this to discover API capabilities and configuration.
    
    This tool logs API configuration for system transparency.
    
    Returns:
        Dictionary with API information including:
        - base_url: Base URL of the API
        - endpoint: API endpoint path (/predict)
        - full_url: Complete URL for requests
        - method: HTTP method (POST)
        - supported_classes: List of document types
        - timeout: Request timeout in seconds
    """
    logger.info("🔧 Tool: Getting classifier API information")
    return get_classifier_api_info()


@tool("Make Classifier API Request")
def make_classifier_api_request(
    file_path: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Make classification request to the /predict API endpoint.
    
    This tool provides comprehensive logging of:
    - API requests (method, URL, file details)
    - Classification predictions with confidence
    - All class probabilities
    - Performance metrics
    - Error conditions
    
    Args:
        file_path: Full path to the document file to classify
        additional_data: Optional additional metadata (not used by /predict)
        
    Returns:
        Dictionary with:
        - success: Boolean
        - response: API response with predicted_class, confidence, probabilities (if successful)
        - error: Error message (if failed)
        
    Example:
        make_classifier_api_request(
            file_path="/path/to/document.jpg"
        )
    """
    start_time = time.time()
    api_info = get_classifier_api_info()
    url = api_info["full_url"]
    timeout = api_info["timeout"]
    
    file_path_obj = Path(file_path)
    file_size = file_path_obj.stat().st_size if file_path_obj.exists() else 0
    
    # Log API request with full details
    logger.critical(
        "\n" + "="*80 + "\n" +
        "🔧 TOOL: Classifier API Request\n" +
        "="*80 + "\n" +
        f"Method: POST\n" +
        f"URL: {url}\n" +
        f"File: {file_path_obj.name}\n" +
        f"Path: {file_path}\n" +
        f"Size: {file_size:,} bytes ({file_size/1024:.2f} KB)\n" +
        "="*80
    )
    
    # Validate file exists
    if not file_path_obj.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }
    
    try:
        with open(file_path_obj, 'rb') as f:
            files = {'file': (file_path_obj.name, f, 'application/octet-stream')}
            
            response = requests.post(
                url,
                files=files,
                timeout=timeout
            )
            response.raise_for_status()
            
            result = response.json()
            duration = time.time() - start_time
            
            # Extract prediction details
            predicted_class = result.get('predicted_class', 'unknown')
            confidence = result.get('confidence', 0.0)
            probabilities = result.get('probabilities', {})
            
            # Log classification prediction with ALL details
            logger.critical(
                "\n" + "="*80 + "\n" +
                "🎯 CLASSIFICATION RESULT (via Tool)\n" +
                "="*80 + "\n" +
                f"Document: {file_path_obj.name}\n" +
                f"Predicted Class: {predicted_class}\n" +
                f"Confidence: {confidence:.2%}\n" +
                f"Duration: {duration:.3f}s\n" +
                "All Probabilities:\n" +
                "\n".join([f"  - {cls}: {prob:.2%}" for cls, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True)]) + "\n" +
                "="*80
            )
            
            return {
                "success": True,
                "response": result
            }
            
    except requests.exceptions.RequestException as e:
        duration = time.time() - start_time
        logger.error(
            f"\n" + "="*80 + "\n" +
            f"❌ CLASSIFICATION FAILED (via Tool)\n" +
            "="*80 + "\n" +
            f"File: {file_path_obj.name}\n" +
            f"URL: {url}\n" +
            f"Duration: {duration:.3f}s\n" +
            f"Error: {str(e)}\n" +
            "="*80
        )
        return {
            "success": False,
            "error": str(e)
        }
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse API response: {str(e)}")
        return {
            "success": False,
            "error": f"Invalid JSON response: {str(e)}"
        }


@tool("Extract Document File Path")
def extract_document_file_path_tool(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the file path from a document metadata object.
    Use this to get the stored_path needed for API requests.
    
    Args:
        document: Document metadata object
        
    Returns:
        Dictionary with:
        - success: Boolean
        - document_id: Document identifier
        - file_path: Full path to the document file
        - filename: Original filename
        - error: Error message if stored_path missing
    """
    document_id = document.get('document_id', 'unknown')
    stored_path = document.get('stored_path')
    original_filename = document.get('original_filename', 'unknown')
    
    logger.info(f"Extracting file path for document: {document_id}")
    
    if not stored_path:
        error_msg = f"Document {document_id} missing 'stored_path' attribute"
        logger.error(error_msg)
        return {
            "success": False,
            "document_id": document_id,
            "error": error_msg
        }
    
    logger.info(f"Found stored_path: {stored_path}")
    
    return {
        "success": True,
        "document_id": document_id,
        "file_path": stored_path,
        "filename": original_filename
    }
