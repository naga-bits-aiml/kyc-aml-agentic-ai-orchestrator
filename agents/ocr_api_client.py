"""API client for OCR extraction service."""
import requests
import base64
from typing import Dict, Any, Optional
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from utilities import config, settings, logger


class OCRAPIClient:
    """Client for interacting with OCR extraction APIs."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        provider: Optional[str] = None
    ):
        """
        Initialize the OCR API client.
        
        Args:
            base_url: Base URL of the OCR API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            provider: OCR provider (tesseract, azure, aws, google)
        """
        # Get OCR config from config system
        ocr_config = config.get('api.ocr', {})
        
        self.base_url = base_url or ocr_config.get('base_url') or settings.ocr_api_base_url
        self.api_key = api_key or ocr_config.get('api_key') or settings.ocr_api_key
        self.timeout = timeout or ocr_config.get('timeout', 60)
        self.provider = provider or ocr_config.get('provider', 'tesseract')
        self.confidence_threshold = ocr_config.get('confidence_threshold', 0.7)
        
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
        
        logger.info(f"OCR API client initialized with provider: {self.provider}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True
    )
    def health_check(self) -> bool:
        """
        Check if the OCR API is available.
        
        Returns:
            True if API is healthy, False otherwise
        """
        if not self.base_url:
            logger.warning("OCR API base URL not configured - using local extraction only")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            is_healthy = response.status_code == 200
            
            if is_healthy:
                logger.info("OCR API health check passed")
            else:
                logger.warning(f"OCR API health check failed: {response.status_code}")
            
            return is_healthy
        except Exception as e:
            logger.error(f"OCR API health check error: {str(e)}")
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True
    )
    def extract_text(
        self,
        file_path: str,
        language: str = "eng",
        extract_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from a document using OCR API.
        
        Args:
            file_path: Path to the document file
            language: Language code (default: eng)
            extract_metadata: Whether to extract additional metadata
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        if not self.base_url:
            raise ValueError("OCR API base URL not configured. Cannot use API extraction.")
        
        try:
            # Read file and encode to base64
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            file_name = Path(file_path).name
            
            # Prepare request payload
            payload = {
                "file_content": file_base64,
                "file_name": file_name,
                "language": language,
                "extract_metadata": extract_metadata,
                "provider": self.provider
            }
            
            logger.info(f"Sending OCR extraction request for: {file_name}")
            
            response = self.session.post(
                f"{self.base_url}/extract",
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(
                f"OCR extraction successful for {file_name}, "
                f"confidence: {result.get('confidence', 0):.2f}"
            )
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR API request failed for {file_path}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"OCR extraction error for {file_path}: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True
    )
    def extract_batch(
        self,
        file_paths: list,
        language: str = "eng"
    ) -> Dict[str, Any]:
        """
        Extract text from multiple documents in batch.
        
        Args:
            file_paths: List of document file paths
            language: Language code (default: eng)
            
        Returns:
            Dictionary containing batch extraction results
        """
        if not self.base_url:
            raise ValueError("OCR API base URL not configured. Cannot use batch extraction.")
        
        try:
            # Prepare batch payload
            documents = []
            for file_path in file_paths:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                documents.append({
                    "file_name": Path(file_path).name,
                    "file_content": base64.b64encode(file_content).decode('utf-8'),
                    "original_path": file_path
                })
            
            payload = {
                "documents": documents,
                "language": language,
                "provider": self.provider
            }
            
            logger.info(f"Sending batch OCR extraction request for {len(file_paths)} documents")
            
            response = self.session.post(
                f"{self.base_url}/batch-extract",
                json=payload,
                timeout=self.timeout * len(file_paths)  # Scale timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Batch OCR extraction successful for {len(file_paths)} documents")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR batch API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"OCR batch extraction error: {str(e)}")
            raise
