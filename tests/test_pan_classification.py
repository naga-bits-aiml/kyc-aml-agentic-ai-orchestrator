#!/usr/bin/env python3
"""
Test PAN card classification to verify agent behavior.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from flows.document_processing_flow import kickoff_flow
from utilities.llm_factory import create_llm
from utilities import logger

def test_pan_classification():
    """Test PAN card document classification."""
    
    print("="*70)
    print("🧪 Testing PAN Card Classification")
    print("="*70)
    
    # Setup
    pan_file = Path.home() / "Downloads" / "pan-1.pdf"
    
    if not pan_file.exists():
        print(f"❌ File not found: {pan_file}")
        return
    
    print(f"\n📄 Document: {pan_file}")
    print(f"   Size: {pan_file.stat().st_size / 1024:.1f} KB\n")
    
    # Create LLM
    llm = create_llm()
    
    # Test classification
    case_id = "TEST-PAN-CLASSIFICATION"
    
    try:
        print("🚀 Starting classification flow...")
        print(f"   Case: {case_id}\n")
        
        result = kickoff_flow(
            case_id=case_id,
            file_paths=[str(pan_file)],
            llm=llm
        )
        
        print("\n✅ Classification Complete!\n")
        print("="*70)
        print("📊 RESULTS:")
        print("="*70)
        
        if isinstance(result, dict):
            # Print formatted results
            import json
            print(json.dumps(result, indent=2))
        else:
            print(result)
        
        # Check case metadata
        from case_metadata_manager import CaseMetadataManager
        metadata_mgr = CaseMetadataManager(case_id)
        metadata = metadata_mgr.load_metadata()
        
        print("\n" + "="*70)
        print("📋 CASE METADATA:")
        print("="*70)
        
        if metadata.get('documents'):
            for doc in metadata['documents']:
                print(f"\n📄 Document: {doc.get('filename', 'Unknown')}")
                print(f"   Status: {doc.get('status', 'unknown')}")
                
                classification = doc.get('classification', {})
                if classification:
                    doc_type = classification.get('document_type', 'unknown')
                    confidence = classification.get('confidence', 0)
                    print(f"   Classification: {doc_type} ({confidence:.0%} confidence)")
                    print(f"   Reasoning: {classification.get('reasoning', 'N/A')}")
                
                extraction = doc.get('extraction', {})
                if extraction:
                    extracted_data = extraction.get('extracted_data', {})
                    if extracted_data:
                        print(f"   Extracted Fields: {len(extracted_data)}")
                        for field, value in extracted_data.items():
                            if value:
                                print(f"      • {field}: {value}")
        else:
            print("\n⚠️  No documents found in metadata")
        
        # Analysis
        print("\n" + "="*70)
        print("🔍 ANALYSIS:")
        print("="*70)
        
        if metadata.get('documents'):
            doc = metadata['documents'][0]
            classification = doc.get('classification', {})
            
            if classification:
                doc_type = classification.get('document_type', 'unknown')
                confidence = classification.get('confidence', 0)
                
                if doc_type == 'unknown' or confidence < 0.5:
                    print("\n⚠️  CLASSIFICATION ISSUE DETECTED:")
                    print(f"   Type: {doc_type}")
                    print(f"   Confidence: {confidence:.0%}")
                    print("\n💡 RECOMMENDATION:")
                    print("   Agent struggled with classification.")
                    print("   Should implement LLM fallback for:")
                    print("   - Unknown document types")
                    print("   - Low confidence (<50%)")
                    print("   - Non-standard document formats (PAN card)")
                else:
                    print(f"\n✅ Classification successful: {doc_type} ({confidence:.0%})")
            else:
                print("\n❌ No classification performed")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = test_pan_classification()
    sys.exit(0 if success else 1)
