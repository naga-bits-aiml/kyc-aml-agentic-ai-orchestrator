"""API client for KYC-AML Document Classifier service."""
import requests
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
from utilities import config, settings, logger


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
        
        API Endpoint: http://35.184.130.36/api/kyc_document_classifier/v1/
        
        Args:
            file_path: Path to the document file
            metadata: Optional document metadata
            
        Returns:
            Classification result from the API
        """
        # API expects files to be posted to the base URL
        url = self.base_url
        
        try:
            with open(file_path, 'rb') as f:
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
