"""
Production-Grade API client for Google Vision OCR extraction service.

Uses Google Vision API for text detection with comprehensive logging.
"""
import requests
import base64
import time
from typing import Dict, Any, Optional
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from utilities import config, settings, logger


class OCRAPIClient:
    """
    Production-Grade Google Vision API Client for OCR/Text Extraction.
    
    Uses Google Vision API TEXT_DETECTION feature for extracting text from images.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize the Google Vision OCR API client.
        
        Args:
            api_key: Google Vision API key
            timeout: Request timeout in seconds
        """
        # Get OCR config from config system
        ocr_config = config.get('api.ocr', {})
        
        self.api_key = api_key or ocr_config.get('api_key') or settings.ocr_api_key
        self.timeout = timeout or ocr_config.get('timeout', 60)
        self.base_url = ocr_config.get('base_url', 'https://vision.googleapis.com/v1/images:annotate')
        self.provider = ocr_config.get('provider', 'google_vision')
        self.url = self.base_url
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        })
        
        # Log initialization
        logger.critical(
            "="*80 + "\n" +
            "🔧 GOOGLE VISION OCR CLIENT INITIALIZED\n" +
            "="*80 + "\n" +
            f"Base URL: {self.base_url}\n" +
            f"Provider: {self.provider}\n" +
            f"API Key: {'Configured' if self.api_key else 'NOT CONFIGURED'}\n" +
            f"Timeout: {self.timeout}s\n" +
            f"Feature: TEXT_DETECTION\n" +
            "="*80
        )
    
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
        Extract text from a document using Google Vision API TEXT_DETECTION.
        
        Args:
            file_path: Path to the image file (JPEG, PNG, BMP, TIFF, etc.)
            language: Language code (not used by Vision API, kept for compatibility)
            extract_metadata: Whether to extract additional metadata
            
        Returns:
            Dictionary containing:
            - text: Extracted text content
            - confidence: Overall confidence (from Vision API)
            - word_count: Number of words extracted
            - char_count: Number of characters
            - metadata: Additional extraction metadata
        """
        if not self.api_key:
            raise ValueError("Google Vision API key not configured. Set OCR_API_KEY environment variable.")
        
        file_path = Path(file_path)
        start_time = time.time()
        file_size = file_path.stat().st_size
        
        # Log API request
        logger.critical(
            "\n" + "="*80 + "\n" +
            "🌐 GOOGLE VISION API REQUEST: Text Extraction\n" +
            "="*80 + "\n" +
            f"Method: POST\n" +
            f"URL: {self.url}\n" +
            f"File: {file_path.name}\n" +
            f"Path: {file_path}\n" +
            f"Size: {file_size:,} bytes ({file_size/1024:.2f} KB)\n" +
            f"Feature: TEXT_DETECTION\n" +
            "="*80
        )
        
        try:
            # Read file and encode to base64
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            content_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Prepare Vision API payload
            payload = {
                "requests": [
                    {
                        "image": {"content": content_base64},
                        "features": [{"type": "TEXT_DETECTION"}]
                    }
                ]
            }
            
            # Send request to Google Vision API
            response = self.session.post(
                self.url,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            duration = time.time() - start_time
            
            # Extract text from response
            text = ""
            confidence = 0.0
            
            if "responses" in result and len(result["responses"]) > 0:
                response_data = result["responses"][0]
                
                # Get full text annotation
                if "fullTextAnnotation" in response_data:
                    text = response_data["fullTextAnnotation"].get("text", "")
                    
                    # Calculate average confidence from pages
                    if "pages" in response_data["fullTextAnnotation"]:
                        pages = response_data["fullTextAnnotation"]["pages"]
                        if pages:
                            confidences = []
                            for page in pages:
                                if "confidence" in page:
                                    confidences.append(page["confidence"])
                            confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                # Check for errors
                if "error" in response_data:
                    error_msg = response_data["error"].get("message", "Unknown error")
                    logger.error(f"Google Vision API error: {error_msg}")
                    raise Exception(f"Vision API error: {error_msg}")
            
            word_count = len(text.split()) if text else 0
            char_count = len(text) if text else 0
            
            # Log extraction result with ALL details
            logger.critical(
                "\n" + "="*80 + "\n" +
                "📝 TEXT EXTRACTION RESULT\n" +
                "="*80 + "\n" +
                f"Document: {file_path.name}\n" +
                f"Text Extracted: {'Yes' if text else 'No'}\n" +
                f"Characters: {char_count:,}\n" +
                f"Words: {word_count:,}\n" +
                f"Confidence: {confidence:.2%}\n" +
                f"Duration: {duration:.3f}s\n" +
                f"Preview: {text[:200]}{'...' if len(text) > 200 else ''}\n" +
                "="*80
            )
            
            extraction_result = {
                "text": text,
                "confidence": confidence,
                "word_count": word_count,
                "char_count": char_count,
                "duration_seconds": duration,
                "file_name": file_path.name,
                "file_size_bytes": file_size
            }
            
            if extract_metadata:
                extraction_result["metadata"] = {
                    "api": "google_vision",
                    "feature": "TEXT_DETECTION",
                    "response_pages": len(result.get("responses", [])),
                    "has_full_text": "fullTextAnnotation" in result.get("responses", [{}])[0]
                }
            
            return extraction_result
            
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            logger.error(
                f"\n" + "="*80 + "\n" +
                f"❌ TEXT EXTRACTION FAILED\n" +
                "="*80 + "\n" +
                f"File: {file_path.name}\n" +
                f"URL: {self.url}\n" +
                f"Duration: {duration:.3f}s\n" +
                f"Error Type: {type(e).__name__}\n" +
                f"Error: {str(e)}\n" +
                "="*80
            )
            raise
        except Exception as e:
            logger.error(f"Text extraction error for {file_path}: {str(e)}")
            raise
    
    def process_document(self, file_path: str, language: str = "eng") -> Dict[str, Any]:
        """
        Process a document for text extraction (wrapper for extract_text).
        
        Args:
            file_path: Path to the document file
            language: Language code (not used by Vision API)
            
        Returns:
            Dictionary with extraction results
        """
        return self.extract_text(file_path, language=language, extract_metadata=True)
