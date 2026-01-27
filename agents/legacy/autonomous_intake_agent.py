"""Autonomous Intake Agent with reasoning capabilities."""
import json
from typing import Dict, Any, List
from pathlib import Path
from agents.base_agent import BaseAgent
from agents.shared_memory import SharedMemory
from utilities import validate_file_extension, validate_file_size, settings


class AutonomousIntakeAgent(BaseAgent):
    """
    Autonomous document intake specialist.
    Validates and prepares documents with reasoning and decision-making.
    """
    
    def __init__(self, llm):
        """Initialize autonomous intake agent."""
        super().__init__(
            name="IntakeAgent",
            role="Document Intake Specialist",
            llm=llm
        )
    
    def _reason(self, observation: Dict[str, Any], task: Dict[str, Any],
                shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Reason about what documents need and how to handle them.
        """
        action = task.get('action', '')
        parameters = task.get('parameters', {})
        documents = parameters.get('documents', shared_memory.get('documents', []))
        
        if not documents:
            return {
                'analysis': 'No documents to process',
                'approach': 'status_check',
                'concerns': []
            }
        
        prompt = f"""
You are a Document Intake Specialist for KYC/AML compliance.

Documents to process: {documents}
Case: {shared_memory.case_reference}
Current workflow phase: {observation['context'].get('workflow_phase')}

As an intake specialist, analyze:
1. Are these document paths valid and accessible?
2. What document types do these appear to be (based on filenames)?
3. Are there any immediate concerns (size, format, naming)?
4. What's the best order to process them?
5. Any special handling needed?

Return JSON:
{{
    "analysis": "brief situation assessment",
    "document_assessment": [
        {{
            "path": "doc path",
            "inferred_type": "identity_proof|address_proof|financial|other",
            "concerns": ["list any concerns"],
            "priority": "high|normal|low"
        }}
    ],
    "processing_order": ["ordered list of document paths"],
    "approach": "standard|careful|expedited",
    "special_handling": []
}}
"""
        
        response = self._invoke_llm(prompt)
        reasoning = self._parse_llm_response(response)
        
        self.logger.info(f"[IntakeAgent] Reasoning: {reasoning.get('approach', 'standard')} approach")
        
        return reasoning
    
    def _plan(self, reasoning: Dict[str, Any], observation: Dict[str, Any],
              shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Create detailed action plan for document intake.
        """
        documents = reasoning.get('processing_order', [])
        
        prompt = f"""
You are planning the intake process for these documents.

Reasoning: {json.dumps(reasoning, indent=2)}

Create a detailed action plan:

Return JSON:
{{
    "validation_steps": [
        {{
            "document": "path",
            "checks": ["file_exists", "valid_extension", "size_check", "readable"],
            "metadata_to_capture": ["hash", "size", "mime_type", "timestamp"]
        }}
    ],
    "storage_strategy": "organize_by_type|chronological|as_is",
    "quality_checks": ["checks to perform"],
    "error_recovery": "how to handle validation failures"
}}
"""
        
        response = self._invoke_llm(prompt)
        plan = self._parse_llm_response(response)
        
        # Ensure we have documents to process
        if 'validation_steps' not in plan or not plan['validation_steps']:
            plan['validation_steps'] = [
                {
                    'document': doc,
                    'checks': ['file_exists', 'valid_extension', 'size_check'],
                    'metadata_to_capture': ['hash', 'size', 'mime_type']
                }
                for doc in documents
            ]
        
        return plan
    
    def _act(self, plan: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Execute the intake plan: validate and store documents.
        """
        validation_steps = plan.get('validation_steps', [])
        validated_documents = []
        failed_documents = []
        
        for step in validation_steps:
            doc_path = step.get('document', '')
            if not doc_path:
                continue
            
            self.logger.info(f"[IntakeAgent] Processing: {doc_path}")
            
            try:
                # Expand tilde and resolve path
                file_path = Path(doc_path).expanduser().resolve()
                
                # Perform validations
                validation_result = self._validate_document(file_path, step.get('checks', []))
                
                if validation_result['valid']:
                    # Store document
                    stored_doc = self._store_document(file_path, shared_memory)
                    validated_documents.append(stored_doc)
                    
                    self.logger.info(f"[IntakeAgent] ✓ Validated: {file_path.name}")
                else:
                    failed_documents.append({
                        'path': str(file_path),
                        'reason': validation_result.get('reason', 'Unknown')
                    })
                    self.logger.warning(f"[IntakeAgent] ✗ Failed: {file_path.name} - {validation_result.get('reason')}")
            
            except Exception as e:
                self.logger.error(f"[IntakeAgent] Error processing {doc_path}: {e}")
                failed_documents.append({
                    'path': doc_path,
                    'reason': str(e)
                })
        
        # Update shared memory with results
        shared_memory.update('validated_documents', validated_documents, agent=self.name)
        shared_memory.update('failed_documents', failed_documents, agent=self.name)
        
        result = {
            'status': 'success' if validated_documents else 'failed',
            'validated_count': len(validated_documents),
            'failed_count': len(failed_documents),
            'validated_documents': validated_documents,
            'failed_documents': failed_documents,
            'summary': f"Validated {len(validated_documents)}/{len(validation_steps)} documents"
        }
        
        return result
    
    def _validate_document(self, file_path: Path, checks: List[str]) -> Dict[str, Any]:
        """
        Perform validation checks on a document.
        """
        if not file_path.exists():
            return {'valid': False, 'reason': 'File does not exist'}
        
        if 'valid_extension' in checks:
            if not validate_file_extension(str(file_path), settings.allowed_extensions):
                return {'valid': False, 'reason': f'Invalid file extension. Allowed: {settings.allowed_extensions}'}
        
        if 'size_check' in checks:
            max_size_bytes = settings.max_document_size_mb * 1024 * 1024
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if not validate_file_size(str(file_path), max_size_bytes):
                return {'valid': False, 'reason': f'File too large: {file_size_mb:.1f}MB (max: {settings.max_document_size_mb}MB)'}
        
        if 'readable' in checks:
            try:
                with open(file_path, 'rb') as f:
                    f.read(1024)  # Try reading first KB
            except Exception as e:
                return {'valid': False, 'reason': f'File not readable: {e}'}
        
        return {'valid': True}
    
    def _store_document(self, source_path: Path, shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Store document in case directory with metadata.
        """
        import shutil
        import hashlib
        from datetime import datetime
        
        case_ref = shared_memory.case_reference
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        case_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        existing_docs = list(case_dir.glob(f"{case_ref}_DOC_*.{source_path.suffix.lstrip('.')}"))
        doc_num = len(existing_docs) + 1
        dest_filename = f"{case_ref}_DOC_{doc_num:03d}{source_path.suffix}"
        dest_path = case_dir / dest_filename
        
        # Copy file
        shutil.copy2(source_path, dest_path)
        
        # Create metadata
        with open(source_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        metadata = {
            'document_id': dest_filename,
            'original_path': str(source_path),
            'stored_path': str(dest_path),
            'filename': dest_filename,
            'size_bytes': dest_path.stat().st_size,
            'hash': file_hash,
            'mime_type': self._get_mime_type(dest_path),
            'intake_timestamp': datetime.now().isoformat(),
            'status': 'validated'
        }
        
        # Save document-specific metadata
        doc_metadata_file = case_dir / f"{dest_filename}.metadata.json"
        with open(doc_metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"[IntakeAgent] Stored: {dest_filename}")
        
        return metadata
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type of file."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
