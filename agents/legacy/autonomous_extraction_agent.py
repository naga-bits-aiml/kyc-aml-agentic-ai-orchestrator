"""Autonomous Extraction Agent with reasoning capabilities."""
import json
from typing import Dict, Any
from pathlib import Path
from agents.base_agent import BaseAgent
from agents.shared_memory import SharedMemory
from agents.document_extraction_agent import DocumentExtractionAgent


class AutonomousExtractionAgent(BaseAgent):
    """
    Autonomous document extraction specialist.
    Extracts data from documents with reasoning and adaptation.
    """
    
    def __init__(self, llm):
        """Initialize autonomous extraction agent."""
        super().__init__(
            name="ExtractionAgent",
            role="Document Extraction Specialist",
            llm=llm
        )
        # Use existing extraction agent as worker
        self.extraction_worker = DocumentExtractionAgent(llm=llm)
    
    def _reason(self, observation: Dict[str, Any], task: Dict[str, Any],
                shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Reason about extraction strategy based on documents.
        """
        validated_docs = shared_memory.get('validated_documents', [])
        
        if not validated_docs:
            return {
                'analysis': 'No validated documents to extract',
                'strategy': 'skip'
            }
        
        prompt = f"""
You are a Document Extraction Specialist.

Documents to extract: {len(validated_docs)}
Sample: {json.dumps(validated_docs[:3], indent=2)}

Analyze:
1. What types of documents are these?
2. What extraction method would work best for each?
3. Are there any documents that don't need extraction?
4. What's the priority order?
5. Any quality concerns?

Return JSON:
{{
    "analysis": "brief assessment",
    "extraction_strategy": {{
        "method": "ocr|text|hybrid",
        "quality_priority": "speed|accuracy|balanced"
    }},
    "document_priorities": [
        {{
            "document_id": "id",
            "priority": "high|normal|low",
            "extraction_needed": true/false,
            "reason": "why"
        }}
    ],
    "concerns": ["any quality or processing concerns"]
}}
"""
        
        response = self._invoke_llm(prompt)
        reasoning = self._parse_llm_response(response)
        
        self.logger.info(f"[ExtractionAgent] Strategy: {reasoning.get('extraction_strategy', {}).get('method', 'standard')}")
        
        return reasoning
    
    def _plan(self, reasoning: Dict[str, Any], observation: Dict[str, Any],
              shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Create extraction plan for documents.
        """
        validated_docs = shared_memory.get('validated_documents', [])
        doc_priorities = reasoning.get('document_priorities', [])
        
        # Match priorities with documents
        plan = {
            'extractions': [],
            'skip': []
        }
        
        for doc in validated_docs:
            doc_id = doc.get('document_id', '')
            priority_info = next(
                (p for p in doc_priorities if p.get('document_id') == doc_id),
                {'extraction_needed': True, 'priority': 'normal'}
            )
            
            if priority_info.get('extraction_needed', True):
                plan['extractions'].append({
                    'document_id': doc_id,
                    'path': doc.get('stored_path'),
                    'priority': priority_info.get('priority', 'normal')
                })
            else:
                plan['skip'].append({
                    'document_id': doc_id,
                    'reason': priority_info.get('reason', 'Not needed')
                })
        
        # Sort by priority
        priority_order = {'high': 0, 'normal': 1, 'low': 2}
        plan['extractions'].sort(key=lambda x: priority_order.get(x['priority'], 1))
        
        return plan
    
    def _act(self, plan: Dict[str, Any], shared_memory: SharedMemory) -> Dict[str, Any]:
        """
        Execute extractions using the worker agent.
        """
        extractions = plan.get('extractions', [])
        results = []
        
        for extraction_task in extractions:
            doc_path = extraction_task.get('path')
            doc_id = extraction_task.get('document_id')
            
            if not doc_path:
                continue
            
            self.logger.info(f"[ExtractionAgent] Extracting: {doc_id}")
            
            try:
                # Use worker to perform extraction
                result = self.extraction_worker.extract_from_document(doc_path)
                
                results.append({
                    'document_id': doc_id,
                    'status': result.get('status', 'completed'),
                    'method': result.get('method', 'unknown'),
                    'quality_score': result.get('quality_score', 0.0),
                    'character_count': result.get('character_count', 0),
                    'extracted_text_path': result.get('extracted_text_path', '')
                })
                
                self.logger.info(f"[ExtractionAgent] ✓ Extracted: {doc_id} - {result.get('method')}")
                
                # Save extraction metadata
                self._save_extraction_metadata(doc_path, result, shared_memory)
                
            except Exception as e:
                self.logger.error(f"[ExtractionAgent] Error extracting {doc_id}: {e}")
                results.append({
                    'document_id': doc_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Update shared memory
        shared_memory.update('extraction_results', results, agent=self.name)
        
        return {
            'status': 'success' if results else 'no_extractions',
            'extracted_count': len([r for r in results if r.get('status') != 'failed']),
            'failed_count': len([r for r in results if r.get('status') == 'failed']),
            'results': results,
            'summary': f"Extracted {len(results)} documents"
        }
    
    def _save_extraction_metadata(self, doc_path: str, extraction_result: Dict[str, Any],
                                  shared_memory: SharedMemory):
        """Save extraction metadata to document metadata file."""
        doc_path_obj = Path(doc_path)
        metadata_file = doc_path_obj.parent / f"{doc_path_obj.name}.metadata.json"
        
        try:
            # Load existing metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            # Add extraction info
            metadata['extraction'] = {
                'status': extraction_result.get('status'),
                'method': extraction_result.get('method'),
                'quality_score': extraction_result.get('quality_score'),
                'character_count': extraction_result.get('character_count'),
                'extracted_text_path': extraction_result.get('extracted_text_path'),
                'timestamp': self._get_timestamp()
            }
            
            # Save updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"[ExtractionAgent] Failed to save metadata: {e}")
