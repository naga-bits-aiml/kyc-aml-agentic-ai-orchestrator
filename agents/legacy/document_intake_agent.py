"""Document Intake Agent for KYC-AML processing."""
from crewai import Agent, Task
from typing import List, Dict, Any
import os
import shutil
import json
from pathlib import Path
from datetime import datetime
import uuid
from utilities import (
    validate_file_extension,
    validate_file_size,
    create_document_metadata,
    ensure_directory,
    config,
    settings,
    logger
)
from tools import get_tools_for_agent


class DocumentIntakeAgent:
    """Agent responsible for document intake and initial validation."""
    
    def __init__(self, llm=None):
        """Initialize the Document Intake Agent."""
        self.llm = llm
        # Use configurable paths from JSON config
        self.documents_dir = str(config.intake_dir)
        self.metadata_file = str(config.metadata_file)
        ensure_directory(self.documents_dir)
        self.agent = self._create_agent()
        self._load_metadata()
    
    def _load_metadata(self):
        """Load existing file metadata from JSON file."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.file_mapping = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load metadata file: {str(e)}")
                self.file_mapping = {}
        else:
            self.file_mapping = {}
    
    def _save_metadata(self):
        """Save file metadata to JSON file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.file_mapping, f, indent=2)
            logger.info("File metadata saved successfully")
        except Exception as e:
            logger.error(f"Error saving metadata: {str(e)}")
    
    def _generate_unique_filename(self, original_filename: str) -> str:
        """Generate a unique filename to avoid conflicts in multi-user environment.
        
        Args:
            original_filename: The original filename provided by user
            
        Returns:
            Unique filename with timestamp and UUID
        """
        # Extract extension
        file_path = Path(original_filename)
        extension = file_path.suffix
        
        # Generate unique name: timestamp_uuid_originalname
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_name = file_path.stem.replace(" ", "_")[:50]  # Limit length
        
        unique_filename = f"{timestamp}_{unique_id}_{safe_name}{extension}"
        return unique_filename
    
    def _store_document(self, source_path: str, original_filename: str) -> Dict[str, str]:
        """Store document in filesystem with unique name and track mapping.
        
        Args:
            source_path: Path to the source document
            original_filename: Original filename provided by user
            
        Returns:
            Dictionary with user_filename and internal_filename
        """
        # Generate unique internal filename
        unique_filename = self._generate_unique_filename(original_filename)
        internal_path = os.path.join(self.documents_dir, unique_filename)
        
        # Copy file to storage directory
        try:
            shutil.copy2(source_path, internal_path)
            logger.info(f"Document stored: {original_filename} -> {unique_filename}")
            
            # Update metadata mapping
            self.file_mapping[unique_filename] = {
                "user_filename": original_filename,
                "internal_filename": unique_filename,
                "internal_path": internal_path,
                "original_path": source_path,
                "stored_at": datetime.now().isoformat(),
                "size_bytes": os.path.getsize(internal_path)
            }
            
            # Save metadata
            self._save_metadata()
            
            return {
                "user_filename": original_filename,
                "internal_filename": unique_filename,
                "internal_path": internal_path
            }
            
        except Exception as e:
            logger.error(f"Error storing document: {str(e)}")
            raise
    
    def _create_agent(self) -> Agent:
        """Create the CrewAI agent."""
        return Agent(
            role="Document Intake Specialist",
            goal="Receive, validate, and prepare KYC-AML documents for processing",
            backstory="""You are an expert document intake specialist with years of 
            experience in KYC (Know Your Customer) and AML (Anti-Money Laundering) compliance. 
            Your primary responsibility is to ensure that all incoming documents are properly 
            received, validated for format and size, and prepared for classification. You have 
            a keen eye for detail and understand the importance of document integrity in 
            financial compliance processes.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def validate_document(self, file_path: str, user_filename: str = None) -> Dict[str, Any]:
        """
        Validate a document for intake and store it with unique naming.
        
        Args:
            file_path: Path to the document file
            user_filename: Original filename provided by user (defaults to basename of file_path)
            
        Returns:
            Validation result with status and metadata including user and internal filenames
        """
        # Use basename if user_filename not provided
        if user_filename is None:
            user_filename = os.path.basename(file_path)
        
        result = {
            "valid": False,
            "errors": [],
            "metadata": None,
            "user_filename": user_filename,
            "internal_filename": None,
            "internal_path": None
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            result["errors"].append(f"File not found: {user_filename}")
            logger.error(f"File not found: {file_path}")
            return result
        
        # Validate file extension
        if not validate_file_extension(file_path, settings.allowed_extensions):
            result["errors"].append(
                f"Invalid file extension for '{user_filename}'. Allowed: {', '.join(settings.allowed_extensions)}"
            )
            logger.error(f"Invalid file extension for: {user_filename}")
            return result
        
        # Validate file size
        if not validate_file_size(file_path, settings.max_document_size_bytes):
            result["errors"].append(
                f"File '{user_filename}' exceeds maximum allowed size of {settings.max_document_size_mb} MB"
            )
            logger.error(f"File size exceeded for: {user_filename}")
            return result
        
        # Store document with unique name
        try:
            storage_info = self._store_document(file_path, user_filename)
            
            # Create metadata for the stored document
            metadata = create_document_metadata(storage_info["internal_path"])
            
            # Add user-facing information to metadata
            metadata["user_filename"] = user_filename
            metadata["internal_filename"] = storage_info["internal_filename"]
            metadata["internal_path"] = storage_info["internal_path"]
            
            result["metadata"] = metadata
            result["internal_filename"] = storage_info["internal_filename"]
            result["internal_path"] = storage_info["internal_path"]
            result["valid"] = True
            
            logger.info(f"Document validated and stored successfully: {user_filename}")
            
        except Exception as e:
            result["errors"].append(f"Error processing '{user_filename}': {str(e)}")
            logger.error(f"Error processing {user_filename}: {str(e)}")
        
        return result
    
    def process_documents(self, file_paths: List[str], user_filenames: List[str] = None) -> List[Dict[str, Any]]:
        """
        Process multiple documents for intake with multi-user support.
        
        Args:
            file_paths: List of file paths to process
            user_filenames: Optional list of user-provided filenames (for display purposes)
            
        Returns:
            List of processed documents with validation results
        """
        processed_documents = []
        
        # If user_filenames not provided, use basenames
        if user_filenames is None:
            user_filenames = [os.path.basename(fp) for fp in file_paths]
        
        for idx, file_path in enumerate(file_paths):
            user_filename = user_filenames[idx] if idx < len(user_filenames) else os.path.basename(file_path)
            
            logger.info(f"Processing document: {user_filename}")
            validation_result = self.validate_document(file_path, user_filename)
            
            processed_doc = {
                "file_path": validation_result.get("internal_path", file_path),  # Use stored path
                "user_filename": user_filename,  # User-facing filename
                "internal_filename": validation_result.get("internal_filename"),  # Internal unique filename
                "validation": validation_result,
                "status": "validated" if validation_result["valid"] else "rejected"
            }
            
            processed_documents.append(processed_doc)
        
        return processed_documents
    
    def create_intake_task(self, documents: List[str]) -> Task:
        """
        Create a CrewAI task for document intake.
        
        Args:
            documents: List of document paths to process
            
        Returns:
            CrewAI Task object
        """
        document_list = "\n".join([f"- {doc}" for doc in documents])
        
        return Task(
            description=f"""Process and validate the following documents for KYC-AML compliance:
            
{document_list}

For each document:
1. Verify the file exists and is accessible
2. Check file extension is allowed ({', '.join(settings.allowed_extensions)})
3. Validate file size is within limit ({settings.max_document_size_mb} MB)
4. Generate document metadata including hash, size, and upload timestamp
5. Mark document as 'validated' or 'rejected' based on checks

Provide a summary of all processed documents with their validation status.""",
            agent=self.agent,
            expected_output="""A structured report containing:
- Total number of documents processed
- List of validated documents with metadata
- List of rejected documents with rejection reasons
- Overall intake status (success/partial/failure)"""
        )
    
    def get_validated_documents(
        self, 
        processed_documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract only validated documents from processed results.
        
        Args:
            processed_documents: List of processed document results
            
        Returns:
            List of validated documents
        """
        return [
            doc for doc in processed_documents 
            if doc["validation"]["valid"]
        ]
    
    def get_user_filename(self, internal_filename: str) -> str:
        """
        Get the user-provided filename from internal unique filename.
        
        Args:
            internal_filename: Internal unique filename
            
        Returns:
            User-provided original filename
        """
        if internal_filename in self.file_mapping:
            return self.file_mapping[internal_filename]["user_filename"]
        return internal_filename
    
    def get_internal_path(self, internal_filename: str) -> str:
        """
        Get the internal storage path for a document.
        
        Args:
            internal_filename: Internal unique filename
            
        Returns:
            Full path to stored document
        """
        if internal_filename in self.file_mapping:
            return self.file_mapping[internal_filename]["internal_path"]
        return None
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Get metadata for all stored documents.
        
        Returns:
            List of all document metadata
        """
        return list(self.file_mapping.values())
