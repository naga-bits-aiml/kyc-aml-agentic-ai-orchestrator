"""API client for KYC-AML Document Classifier service."""
import requests
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
from utilities import config, settings, logger

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available. PDF conversion will be skipped.")


class ClassifierAPIClient:
    """Client for interacting with the KYC-AML Document Classifier API."""
    
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
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or config.classifier_api_url
        self.api_key = api_key or config.classifier_api_key
        self.timeout = timeout or config.classifier_timeout
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
    
    def _convert_pdf_to_image(self, pdf_path: str) -> Optional[str]:
        """
        Convert PDF to image (first page) for classification.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Path to the temporary image file, or None if conversion fails
        """
        if not PDF2IMAGE_AVAILABLE:
            logger.warning("pdf2image not available. Cannot convert PDF to image.")
            return None
        
        try:
            logger.info(f"Converting PDF to image for classification: {pdf_path}")
            
            # Convert first page to image
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
            
            if not images:
                logger.error(f"No images extracted from PDF: {pdf_path}")
                return None
            
            # Save to temporary file
            temp_dir = Path(tempfile.gettempdir()) / "kyc_classifier_temp"
            temp_dir.mkdir(exist_ok=True)
            
            temp_image_path = temp_dir / f"{Path(pdf_path).stem}_page1.jpg"
            images[0].save(str(temp_image_path), 'JPEG', quality=85)
            
            logger.info(f"PDF converted to image: {temp_image_path}")
            return str(temp_image_path)
            
        except Exception as e:
            logger.error(f"Error converting PDF to image: {str(e)}")
            return None
    
    def _should_convert_to_image(self, file_path: str) -> bool:
        """Check if file should be converted to image before classification."""
        return Path(file_path).suffix.lower() == '.pdf'
    
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
        Classify a single document using the KYC document classifier API.
        
        Automatically converts PDFs to images before sending to the API.
        
        API Endpoint: http://35.184.130.36/api/kyc_document_classifier/v1/
        
        Args:
            file_path: Path to the document file
            metadata: Optional document metadata
            
        Returns:
            Classification result from the API
        """
        # API expects files to be posted to the base URL
        url = self.base_url
        
        # Convert PDF to image if needed
        classification_file = file_path
        temp_image = None
        
        if self._should_convert_to_image(file_path):
            logger.info(f"PDF detected, converting to image for classification: {file_path}")
            temp_image = self._convert_pdf_to_image(file_path)
            if temp_image:
                classification_file = temp_image
                logger.info(f"Using converted image for classification: {classification_file}")
            else:
                logger.warning(f"PDF conversion failed, attempting with original file: {file_path}")
        
        try:
            with open(classification_file, 'rb') as f:
                files = {'file': f}
                data = {'metadata': str(metadata)} if metadata else {}
                
                response = self.session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Document classified successfully: {file_path}")
                return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error classifying document {file_path}: {str(e)}")
            raise
        
        finally:
            # Clean up temporary image file
            if temp_image and Path(temp_image).exists():
                try:
                    Path(temp_image).unlink()
                    logger.debug(f"Cleaned up temporary image: {temp_image}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary image {temp_image}: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def batch_classify(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Classify multiple documents in a batch.
        
        Args:
            documents: List of documents with file paths and metadata
            
        Returns:
            Batch classification results
        """
        # For batch processing, may need adjustment based on API specification
        url = self.base_url
        
        try:
            files = []
            for idx, doc in enumerate(documents):
                files.append(
                    (f'file_{idx}', open(doc['file_path'], 'rb'))
                )
            
            response = self.session.post(
                url,
                files=files,
                timeout=self.timeout * len(documents)  # Adjust timeout for batch
            )
            response.raise_for_status()
            
            # Close all file handles
            for _, file_handle in files:
                file_handle.close()
            
            result = response.json()
            logger.info(f"Batch classification completed for {len(documents)} documents")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in batch classification: {str(e)}")
            # Ensure files are closed even on error
            for _, file_handle in files:
                if not file_handle.closed:
                    file_handle.close()
            raise
    
    def get_classification_info(self, classification_id: str) -> Dict[str, Any]:
        """
        Get information about a previous classification.
        
        Args:
            classification_id: ID of the classification
            
        Returns:
            Classification information
        """
        url = f"{self.base_url}/classifications/{classification_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting classification info: {str(e)}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if the classifier API is healthy.
        
        Returns:
            True if API is healthy, False otherwise
        """
        # Try base URL for health check
        url = self.base_url
        
        try:
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
