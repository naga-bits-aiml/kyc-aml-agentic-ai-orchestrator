#!/usr/bin/env python3
"""
Quick Start Demo for KYC-AML Agentic AI Orchestrator
This script demonstrates the complete workflow with example documents.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator import KYCAMLOrchestrator
from utilities import logger


def print_banner():
    """Print a welcome banner."""
    print("\n" + "="*70)
    print("🚀 KYC-AML Agentic AI Orchestrator - Quick Start Demo")
    print("="*70)
    print("\nThis demo will:")
    print("  1. Initialize the orchestrator with Google Gemini LLM")
    print("  2. Process sample KYC documents (Passport, Utility Bill, Driver's License)")
    print("  3. Perform document intake, extraction, and classification")
    print("  4. Display comprehensive results")
    print("="*70 + "\n")


def main():
    """Run the quick start demo."""
    print_banner()
    
    # Step 1: Initialize orchestrator
    print("📋 Step 1: Initializing Orchestrator...")
    try:
        orchestrator = KYCAMLOrchestrator(
            temperature=0.1,
            use_batch_classification=True
        )
        print("   ✅ Orchestrator initialized successfully\n")
    except Exception as e:
        print(f"   ❌ Failed to initialize orchestrator: {e}")
        return False
    
    # Step 2: Prepare test documents
    print("📄 Step 2: Loading Test Documents...")
    test_docs = [
        project_root / "test_documents" / "passport_sample.txt",
        project_root / "test_documents" / "utility_bill_sample.txt",
        project_root / "test_documents" / "drivers_license_sample.txt"
    ]
    
    # Check if documents exist
    existing_docs = []
    for doc in test_docs:
        if doc.exists():
            existing_docs.append(str(doc))
            print(f"   ✅ Found: {doc.name}")
        else:
            print(f"   ⚠️  Missing: {doc.name}")
    
    if not existing_docs:
        print("\n   ❌ No test documents found!")
        print("   Run the tests to generate sample documents.")
        return False
    
    print(f"\n   Found {len(existing_docs)} document(s) to process\n")
    
    # Step 3: Process documents
    print("⚙️  Step 3: Processing Documents...")
    print("   This will perform:")
    print("     • Document intake and validation")
    print("     • Text extraction (direct or OCR)")
    print("     • Document classification\n")
    
    try:
        results = orchestrator.process_documents(existing_docs)
        print("   ✅ Processing completed\n")
    except Exception as e:
        print(f"   ❌ Processing failed: {e}")
        logger.error(f"Demo processing failed: {e}", exc_info=True)
        return False
    
    # Step 4: Display results
    print("="*70)
    print("📊 RESULTS SUMMARY")
    print("="*70)
    
    print(f"\n🔹 Status: {results.get('status', 'unknown').upper()}")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"\n🔹 Documents:")
        print(f"   • Total Submitted: {summary.get('total_documents', 0)}")
        print(f"   • Successfully Validated: {summary.get('validated', 0)}")
        
        # Classification summary
        if 'classification_summary' in summary:
            class_summary = summary['classification_summary']
            if isinstance(class_summary, dict):
                print(f"\n🔹 Classification:")
                success_rate = class_summary.get('success_rate', 0)
                print(f"   • Success Rate: {success_rate}%")
                print(f"   • Successfully Classified: {class_summary.get('successfully_classified', 0)}")
                print(f"   • Errors: {class_summary.get('errors', 0)}")
                
                if 'document_types' in class_summary:
                    print(f"\n🔹 Document Types Identified:")
                    for doc_type, count in class_summary['document_types'].items():
                        print(f"   • {doc_type.upper()}: {count} document(s)")
    
    # Extraction summary
    if 'extraction_results' in results and results['extraction_results']:
        print(f"\n🔹 Text Extraction:")
        successful_extractions = 0
        for extraction in results['extraction_results']:
            if isinstance(extraction, dict) and extraction.get('status') == 'success':
                successful_extractions += 1
        
        print(f"   • Successful Extractions: {successful_extractions}/{len(results['extraction_results'])}")
        
        # Show sample extraction
        print(f"\n🔹 Sample Extracted Text:")
        for idx, extraction in enumerate(results['extraction_results'][:1], 1):
            if isinstance(extraction, dict) and 'text' in extraction:
                text = extraction['text']
                method = extraction.get('method', 'unknown')
                quality = extraction.get('quality_score', 'N/A')
                
                print(f"\n   Document {idx}:")
                print(f"   Method: {method}")
                print(f"   Quality Score: {quality}")
                print(f"   Text Preview:")
                preview = text[:200] + "..." if len(text) > 200 else text
                for line in preview.split('\n')[:5]:
                    print(f"     {line}")
    
    print("\n" + "="*70)
    print("✅ DEMO COMPLETED SUCCESSFULLY")
    print("="*70)
    
    print("\n💡 Next Steps:")
    print("   • Try the chat interface: python chat_interface.py")
    print("   • Try the web interface: python web_chat.py")
    print("   • Process your own documents: python main.py --documents <path>")
    print("   • Read the documentation: docs/QUICKSTART.md")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)
