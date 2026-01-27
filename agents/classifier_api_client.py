"""
Production-Grade REST API Client for KYC-AML Document Classifier Service.

This module provides comprehensive logging for all API interactions including:
- Request/response logging with full details
- Classification predictions with confidence scores
- Performance metrics
- Error handling and retry logic
"""
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from utilities import config, logger


class ClassifierAPIClient:
    """
    Production-Grade REST API Client for KYC-AML Document Classifier.
    
    Uses the /predict endpoint for document classification with comprehensive logging.
    
    Features:
    - Direct /predict endpoint usage
    - Comprehensive request/response logging
    - Detailed classification prediction logging
    - Retry logic with exponential backoff
    - Performance metrics tracking
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize the classifier API client.
        
        Args:
            base_url: Base URL of the classifier API
            api_key: API key for authentication (if required)
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or config.classifier_api_url).rstrip('/')
        self.api_key = api_key or config.classifier_api_key
        self.timeout = timeout or config.classifier_timeout
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}"
            })
        
        # Log initialization with critical details
        logger.critical(
            "="*80 + "\n" +
            "🔧 CLASSIFIER API CLIENT INITIALIZED\n" +
            "="*80 + "\n" +
            f"Base URL: {self.base_url}\n" +
            f"Endpoint: {self.base_url}/predict\n" +
            f"Timeout: {self.timeout}s\n" +
            f"API Key: {'Configured' if self.api_key else 'Not configured'}\n" +
            "Supported: Aadhar, Driving License, PAN Card, Passport, Voter ID\n" +
            "="*80
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def classify_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify a single document using the KYC document classifier /predict API.
        
        This method includes comprehensive logging of:
        - API request details (method, URL, file info)
        - Classification predictions with confidence scores
        - All class probabilities
        - Performance metrics (duration, file size)
        - Error conditions with full context
        
        API Endpoint: {base_url}/predict
        Method: POST
        Content-Type: multipart/form-data
        
        Args:
            file_path: Path to the document file (image: JPEG, PNG, BMP, TIFF)
            metadata: Optional document metadata
            
        Returns:
            Classification result from the API containing:
            - predicted_class: Document type (Aadhar, Driving License, PAN Card, Passport, Voter ID)
            - confidence: Confidence score (0.0-1.0)
            - probabilities: Dict of all class probabilities
            - success: Whether prediction succeeded
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            requests.exceptions.RequestException: If API call fails
        """
        file_path = Path(file_path)
        start_time = time.time()
        
        # Validate file exists
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Prepare API request to /predict endpoint
        url = f"{self.base_url}/predict"
        file_size = file_path.stat().st_size
        
        # Log API request with full details
        logger.critical(
            "\n" + "="*80 + "\n" +
            "🌐 API REQUEST: Document Classification\n" +
            "="*80 + "\n" +
            f"Method: POST\n" +
            f"URL: {url}\n" +
            f"File: {file_path.name}\n" +
            f"Path: {file_path}\n" +
            f"Size: {file_size:,} bytes ({file_size/1024:.2f} KB)\n" +
            f"Extension: {file_path.suffix}\n" +
            "="*80
        )
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                
                response = self.session.post(
                    url,
                    files=files,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                duration = time.time() - start_time
                
                # Extract prediction details
                predicted_class = result.get('predicted_class', 'unknown')
                confidence = result.get('confidence', 0.0)
                probabilities = result.get('probabilities', {})
                success = result.get('success', True)
                
                # Log the classification prediction with ALL details
                logger.critical(
                    "\n" + "="*80 + "\n" +
                    "🎯 CLASSIFIER PREDICTION RESULT\n" +
                    "="*80 + "\n" +
                    f"Document: {file_path.name}\n" +
                    f"Predicted Class: {predicted_class}\n" +
                    f"Confidence: {confidence:.2%}\n" +
                    f"Success: {success}\n" +
                    f"Duration: {duration:.3f}s\n" +
                    "All Probabilities:\n" +
                    "\n".join([f"  - {cls}: {prob:.2%}" for cls, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True)]) + "\n" +
                    "="*80
                )
                
                return result
                
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            logger.error(
                f"\n" + "="*80 + "\n" +
                f"❌ CLASSIFICATION FAILED\n" +
                "="*80 + "\n" +
                f"File: {file_path.name}\n" +
                f"URL: {url}\n" +
                f"Duration: {duration:.3f}s\n" +
                f"Error Type: {type(e).__name__}\n" +
                f"Error: {str(e)}\n" +
                "="*80
            )
            raise
    
    def health_check(self) -> bool:
        """
        Check if the classifier API is healthy.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            logger.info(f"🏥 Performing API health check: {self.base_url}/predict")
            response = self.session.get(f"{self.base_url}/predict", timeout=5)
            is_healthy = response.status_code in [200, 405]  # 405 = Method Not Allowed (GET on POST endpoint is OK)
            
            if is_healthy:
                logger.info(f"✅ API health check passed (status: {response.status_code})")
            else:
                logger.warning(f"⚠️ API health check failed (status: {response.status_code})")
            
            return is_healthy
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API health check failed: {str(e)}")
            return False
    
    def get_api_info(self) -> Dict[str, Any]:
        """
        Get API information for external tools.
        
        Returns:
            Dictionary with API configuration and capabilities
        """
        return {
            "base_url": self.base_url,
            "endpoint": "/predict",
            "full_url": f"{self.base_url}/predict",
            "method": "POST",
            "timeout": self.timeout,
            "description": "Classify Indian identity documents",
            "supported_classes": ["Aadhar", "Driving License", "PAN Card", "Passport", "Voter ID"],
            "supported_formats": ["image/jpeg", "image/png", "image/bmp", "image/tiff"],
            "content_type": "multipart/form-data"
        }
