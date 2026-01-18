"""Test script for OCR Extraction Agent."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents import DocumentExtractionAgent, OCRAPIClient
from utilities import config, settings, logger


def test_ocr_agent():
    """Test the OCR extraction agent."""
    
    print("=" * 70)
    print("OCR Extraction Agent Test")
    print("=" * 70)
    
    # Test 1: Initialize OCR API Client
    print("\n1. Testing OCR API Client Initialization...")
    try:
        ocr_client = OCRAPIClient()
        print(f"   ✓ OCR Client initialized")
        print(f"   - Provider: {ocr_client.provider}")
        print(f"   - Base URL: {ocr_client.base_url or 'Not configured (local only)'}")
        print(f"   - Timeout: {ocr_client.timeout}s")
        print(f"   - Confidence Threshold: {ocr_client.confidence_threshold}")
    except Exception as e:
        print(f"   ✗ Failed: {str(e)}")
        return
    
    # Test 2: Initialize Extraction Agent
    print("\n2. Testing Document Extraction Agent Initialization...")
    try:
        extraction_agent = DocumentExtractionAgent()
        print(f"   ✓ Extraction Agent initialized")
        print(f"   - Extraction directory: {extraction_agent.extraction_dir}")
    except Exception as e:
        print(f"   ✗ Failed: {str(e)}")
        return
    
    # Test 3: Test document analysis
    print("\n3. Testing Document Analysis...")
    test_files = [
        "test.pdf",
        "test.jpg",
        "test.docx",
        "test.txt"
    ]
    
    for test_file in test_files:
        analysis = extraction_agent._analyze_document(test_file)
        print(f"\n   File: {test_file}")
        print(f"   - Needs OCR: {analysis['needs_ocr']}")
        print(f"   - Use API: {analysis['use_api']}")
        print(f"   - Reason: {analysis['reason']}")
    
    # Test 4: Test with actual file if available
    print("\n4. Testing Actual Document Extraction...")
    test_doc_dir = project_root / "test_documents"
    
    if test_doc_dir.exists():
        test_files = list(test_doc_dir.glob("*"))
        if test_files:
            for test_file in test_files[:3]:  # Test first 3 files
                print(f"\n   Testing: {test_file.name}")
                try:
                    result = extraction_agent.extract_from_document(str(test_file))
                    print(f"   - Status: {result.get('status')}")
                    print(f"   - Method: {result.get('method')}")
                    print(f"   - Confidence: {result.get('confidence', 0):.2f}")
                    print(f"   - Quality Score: {result.get('quality_score', 0):.2f}")
                    
                    text = result.get('text', '')
                    if text:
                        preview = text[:100].replace('\n', ' ')
                        print(f"   - Text Preview: {preview}...")
                    else:
                        print(f"   - Text: (empty)")
                        
                except Exception as e:
                    print(f"   ✗ Error: {str(e)}")
        else:
            print("   No test files found in test_documents/")
    else:
        print(f"   Test documents directory not found: {test_doc_dir}")
        print("   Create test_documents/ and add sample files to test extraction")
    
    # Test 5: Check configuration
    print("\n5. Configuration Check...")
    print(f"   OCR API Base URL: {config.ocr_api_url or 'Not set'}")
    print(f"   OCR Provider: {config.ocr_provider}")
    print(f"   OCR Timeout: {config.ocr_timeout}s")
    print(f"   Documents Directory: {settings.documents_dir}")
    
    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)
    
    # Print next steps
    print("\n📋 Next Steps:")
    print("   1. Set OCR_API_BASE_URL in .env if using external OCR API")
    print("   2. Set OCR_API_KEY in .env if API requires authentication")
    print("   3. Install Tesseract for local OCR: brew install tesseract (macOS)")
    print("   4. Add test documents to test_documents/ folder")
    print("   5. Run: python tests/test_ocr_agent.py")


if __name__ == "__main__":
    test_ocr_agent()
