"""Document Classifier Agent for KYC-AML processing."""
from crewai import Agent, Task
from typing import List, Dict, Any, Optional
from utilities import config, settings, logger
from agents.classifier_api_client import ClassifierAPIClient
from tools import get_tools_for_agent


class DocumentClassifierAgent:
    """Agent responsible for classifying KYC-AML documents using the classifier API."""
    
    def __init__(self, llm=None, api_client: Optional[ClassifierAPIClient] = None):
        """
        Initialize the Document Classifier Agent.
        
        Args:
            llm: Language model for the agent
            api_client: Optional classifier API client (creates default if not provided)
        """
        self.llm = llm
        self.api_client = api_client or ClassifierAPIClient()
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the CrewAI agent."""
        return Agent(
            role="Document Classification Specialist",
            goal="Accurately classify KYC-AML documents using the document classifier service",
            backstory="""You are a highly skilled document classification specialist with 
            expertise in KYC (Know Your Customer) and AML (Anti-Money Laundering) documentation. 
            You work with an advanced AI-powered document classifier system to categorize various 
            types of financial compliance documents including identity proofs, address proofs, 
            financial statements, and regulatory forms. Your classifications help streamline the 
            compliance workflow and ensure documents are routed to the appropriate processing teams. 
            You understand the critical importance of accurate classification in preventing fraud 
            and ensuring regulatory compliance.""",
            tools=get_tools_for_agent('classifier'),  # Automatically get classifier + file tools
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def classify_single_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify a single document.
        
        Args:
            file_path: Path to the document file
            metadata: Optional document metadata
            
        Returns:
            Classification result
        """
        try:
            logger.info(f"Classifying document: {file_path}")
            
            # Call the classifier API
            classification_result = self.api_client.classify_document(
                file_path=file_path,
                metadata=metadata
            )
            
            result = {
                "file_path": file_path,
                "classification": classification_result,
                "status": "classified",
                "metadata": metadata
            }
            
            logger.info(f"Document classified: {file_path} -> {classification_result.get('category', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying document {file_path}: {str(e)}")
            return {
                "file_path": file_path,
                "classification": None,
                "status": "error",
                "error": str(e),
                "metadata": metadata
            }
    
    def classify_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Classify multiple documents.
        
        Args:
            documents: List of documents with file_path and metadata
            
        Returns:
            List of classification results
        """
        classified_documents = []
        
        for doc in documents:
            file_path = doc.get("file_path")
            metadata = doc.get("metadata") or doc.get("validation", {}).get("metadata")
            
            if not file_path:
                logger.warning("Document missing file_path, skipping")
                continue
            
            result = self.classify_single_document(file_path, metadata)
            classified_documents.append(result)
        
        return classified_documents
    
    def classify_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Classify multiple documents using batch API endpoint.
        
        Args:
            documents: List of documents with file_path and metadata
            
        Returns:
            Batch classification results
        """
        try:
            logger.info(f"Batch classifying {len(documents)} documents")
            
            # Call the batch classifier API
            batch_result = self.api_client.batch_classify(documents)
            
            logger.info(f"Batch classification completed for {len(documents)} documents")
            return {
                "status": "classified",
                "results": batch_result,
                "total_documents": len(documents)
            }
            
        except Exception as e:
            logger.error(f"Error in batch classification: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "total_documents": len(documents)
            }
    
    def create_classification_task(
        self,
        documents: List[Dict[str, Any]]
    ) -> Task:
        """
        Create a CrewAI task for document classification.
        
        Args:
            documents: List of validated documents to classify
            
        Returns:
            CrewAI Task object
        """
        document_list = "\n".join([
            f"- {doc.get('file_path', 'unknown')}" 
            for doc in documents
        ])
        
        return Task(
            description=f"""Classify the following validated KYC-AML documents using the 
document classifier service:

{document_list}

For each document:
1. Send the document to the classifier API endpoint
2. Retrieve the classification result including document type/category
3. Record confidence scores and any relevant metadata
4. Handle any classification errors gracefully
5. Compile a comprehensive classification report

The classifier service analyzes documents and categorizes them into types such as:
- Identity Proof (Passport, Driver's License, National ID)
- Address Proof (Utility Bill, Bank Statement, Lease Agreement)
- Financial Documents (Income Statements, Tax Returns, Bank Statements)
- Regulatory Forms (KYC Forms, AML Declarations, Compliance Documents)
- Other supporting documents

Ensure all classifications are accurately recorded with their confidence scores.""",
            agent=self.agent,
            expected_output="""A comprehensive classification report containing:
- Total number of documents classified
- Classification results for each document (type, category, confidence score)
- Any documents that failed classification with error details
- Summary statistics of document types identified
- Overall classification status (success/partial/failure)"""
        )
    
    def get_classification_summary(
        self,
        classified_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a summary of classification results.
        
        Args:
            classified_documents: List of classified documents
            
        Returns:
            Summary statistics
        """
        total = len(classified_documents)
        successful = sum(1 for doc in classified_documents if doc["status"] == "classified")
        errors = sum(1 for doc in classified_documents if doc["status"] == "error")
        
        # Count document types
        document_types = {}
        for doc in classified_documents:
            if doc["status"] == "classified" and doc.get("classification"):
                doc_type = doc["classification"].get("category") or doc["classification"].get("type", "unknown")
                document_types[doc_type] = document_types.get(doc_type, 0) + 1
        
        return {
            "total_documents": total,
            "successfully_classified": successful,
            "errors": errors,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "document_types": document_types
        }
