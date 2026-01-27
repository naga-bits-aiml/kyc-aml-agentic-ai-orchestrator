"""Autonomous Classification Agent with reasoning capabilities."""
import json
from typing import Dict, Any
from pathlib import Path
from agents.base_agent import BaseAgent
from agents.shared_memory import SharedMemory
from agents.document_classifier_agent import DocumentClassifierAgent


class AutonomousClassificationAgent(BaseAgent):
    """
    Autonomous document classification specialist.
    Classifies documents with reasoning and confidence assessment.
    """
    
    def __init__(self, llm):
        """Initialize autonomous classification agent."""
        super().__init__(
            name="ClassificationAgent",
            role="Document Classification Specialist",
            llm=llm
        )
        # Use existing classifier agent as worker
        self.classifier_worker = DocumentClassifierAgent(llm=llm)
    
    def _reason(self, observation: Dict[str, Any], task: Dict[str, Any],
                shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Reason about classification strategy.
        """
        validated_docs = shared_memory.get('validated_documents', [])
        extraction_results = shared_memory.get('extraction_results', [])
        
        if not validated_docs:
            return {
                'analysis': 'No documents to classify',
                'strategy': 'skip'
            }
        
        prompt = f"""
You are a Document Classification Specialist for KYC/AML.

Documents to classify: {len(validated_docs)}
Extraction completed: {len(extraction_results)} documents

Sample documents: {json.dumps(validated_docs[:3], indent=2)}

Analyze:
1. Based on filenames and metadata, what types might these be?
2. Should we use extracted text or original files for classification?
3. Are there any documents we can classify without API (based on naming)?
4. What's the confidence strategy (strict/lenient)?
5. Any documents that need special handling?

Return JSON:
{{
    "analysis": "brief assessment",
    "classification_strategy": {{
        "use_extracted_text": true/false,
        "confidence_threshold": 0.0-1.0,
        "fallback_strategy": "manual_review|best_guess|skip"
    }},
    "pre_classifications": [
        {{
            "document_id": "id",
            "likely_type": "identity_proof|address_proof|financial|other",
            "confidence": "high|low",
            "reason": "filename pattern|extraction content|metadata"
        }}
    ],
    "special_handling": []
}}
"""
        
        response = self._invoke_llm(prompt)
        reasoning = self._parse_llm_response(response)
        
        strategy = reasoning.get('classification_strategy', {})
        self.logger.info(f"[ClassificationAgent] Strategy: confidence_threshold={strategy.get('confidence_threshold', 0.5)}")
        
        return reasoning
    
    def _plan(self, reasoning: Dict[str, Any], observation: Dict[str, Any],
              shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Create classification plan.
        """
        validated_docs = shared_memory.get('validated_documents', [])
        pre_classifications = reasoning.get('pre_classifications', [])
        strategy = reasoning.get('classification_strategy', {})
        
        plan = {
            'classifications': [],
            'batch_mode': len(validated_docs) > 5,  # Use batch for many documents
            'confidence_threshold': strategy.get('confidence_threshold', 0.5),
            'use_extracted_text': strategy.get('use_extracted_text', False)
        }
        
        for doc in validated_docs:
            doc_id = doc.get('document_id', '')
            pre_class = next(
                (p for p in pre_classifications if p.get('document_id') == doc_id),
                None
            )
            
            plan['classifications'].append({
                'document_id': doc_id,
                'path': doc.get('stored_path'),
                'hint': pre_class.get('likely_type') if pre_class else None,
                'pre_confidence': pre_class.get('confidence') if pre_class else 'low'
            })
        
        return plan
    
    def _act(self, plan: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Execute classifications using the worker agent.
        """
        classifications = plan.get('classifications', [])
        results = []
        
        for class_task in classifications:
            doc_path = class_task.get('path')
            doc_id = class_task.get('document_id')
            
            if not doc_path:
                continue
            
            self.logger.info(f"[ClassificationAgent] Classifying: {doc_id}")
            
            try:
                # Prepare document metadata for classifier
                doc_metadata = {
                    'file_path': doc_path,
                    'document_id': doc_id
                }
                
                # Use worker to perform classification
                result = self.classifier_worker.classify_single_document(
                    file_path=doc_path,
                    metadata=doc_metadata
                )
                
                # Handle case where result is None (API error)
                if result is None:
                    self.logger.warning(f"[ClassificationAgent] Classification returned None for {doc_id}")
                    result = {
                        'status': 'failed',
                        'error': 'Classification API returned no result',
                        'classification': {'category': 'unknown', 'confidence': 0.0}
                    }
                
                classification = result.get('classification', {})
                
                results.append({
                    'document_id': doc_id,
                    'status': result.get('status', 'completed'),
                    'document_type': classification.get('category', 'unknown'),
                    'confidence': classification.get('confidence', 0.0),
                    'sub_type': classification.get('sub_category'),
                    'suggestion': classification.get('suggestion')
                })
                
                doc_type = classification.get('category', 'unknown')
                confidence = classification.get('confidence', 0)
                self.logger.info(f"[ClassificationAgent] ✓ Classified: {doc_id} as {doc_type} ({confidence:.0%})")
                
                # Always save classification metadata (even on errors)
                self._save_classification_metadata(doc_path, result, shared_memory)
                
            except Exception as e:
                self.logger.error(f"[ClassificationAgent] Error classifying {doc_id}: {e}")
                
                # Save error metadata
                error_result = {
                    'status': 'failed',
                    'error': str(e),
                    'classification': {'category': 'unknown', 'confidence': 0.0}
                }
                self._save_classification_metadata(doc_path, error_result, shared_memory)
                
                results.append({
                    'document_id': doc_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Update shared memory
        shared_memory.update('classification_results', results, agent=self.name)
        
        # Analyze results for case completeness
        self._analyze_case_completeness(results, shared_memory)
        
        return {
            'status': 'success' if results else 'no_classifications',
            'classified_count': len([r for r in results if r.get('status') != 'failed']),
            'failed_count': len([r for r in results if r.get('status') == 'failed']),
            'results': results,
            'summary': f"Classified {len(results)} documents"
        }
    
    def _save_classification_metadata(self, doc_path: str, classification_result: Dict[str, Any],
                                     shared_memory: SharedMemory):
        """Save classification metadata to document metadata file."""
        doc_path_obj = Path(doc_path)
        metadata_file = doc_path_obj.parent / f"{doc_path_obj.name}.metadata.json"
        
        try:
            # Load existing metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            # Add classification info
            classification = classification_result.get('classification', {})
            error_msg = classification_result.get('error')
            
            metadata['classification'] = {
                'status': classification_result.get('status', 'unknown'),
                'document_type': classification.get('category', 'unknown'),
                'confidence': classification.get('confidence', 0.0),
                'sub_type': classification.get('sub_category'),
                'suggestion': classification.get('suggestion'),
                'timestamp': self._get_timestamp()
            }
            
            # Add error info if present
            if error_msg:
                metadata['classification']['error'] = error_msg
            
            # Save updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"[ClassificationAgent] Saved classification metadata for {doc_path_obj.name}")
                
        except Exception as e:
            self.logger.error(f"[ClassificationAgent] Failed to save metadata: {e}")
    
    def _analyze_case_completeness(self, classification_results: list, shared_memory: SharedMemory):
        """Analyze if case has all required document types."""
        required_types = ['identity_proof', 'address_proof', 'financial_document']
        
        classified_types = set()
        for result in classification_results:
            if result.get('status') != 'failed':
                doc_type = result.get('document_type', '')
                if doc_type in required_types:
                    classified_types.add(doc_type)
        
        missing_types = set(required_types) - classified_types
        
        completeness = {
            'has_all_required': len(missing_types) == 0,
            'present_types': list(classified_types),
            'missing_types': list(missing_types),
            'completeness_score': len(classified_types) / len(required_types)
        }
        
        shared_memory.update('case_completeness', completeness, agent=self.name)
        
        if missing_types:
            self.logger.info(f"[ClassificationAgent] Case missing: {', '.join(missing_types)}")
        else:
            self.logger.info("[ClassificationAgent] ✓ Case has all required document types")
