#!/usr/bin/env python3
"""
Test PDF to image conversion for classification API.
"""

from pathlib import Path
from agents.classifier_api_client import ClassifierAPIClient, PDF2IMAGE_AVAILABLE

def test_pdf_conversion():
    """Test PDF to image conversion functionality."""
    print("\n" + "="*80)
    print("Testing PDF to Image Conversion for Classification")
    print("="*80 + "\n")
    
    # Check if pdf2image is available
    print(f"1. pdf2image available: {PDF2IMAGE_AVAILABLE}")
    
    if not PDF2IMAGE_AVAILABLE:
        print("   ❌ pdf2image not installed. Install with: pip install pdf2image")
        print("   ℹ️  Also need poppler: brew install poppler (macOS)")
        return
    
    # Initialize client
    client = ClassifierAPIClient()
    
    # Test with a PDF file
    pdf_path = "documents/cases/KYC-2026-001/KYC-2026-001_DOC_002.pdf"
    
    if not Path(pdf_path).exists():
        print(f"   ⚠️  Test PDF not found: {pdf_path}")
        print("   Using alternative test file...")
        # Try to find any PDF
        pdf_files = list(Path("documents/cases").rglob("*.pdf"))
        if pdf_files:
            pdf_path = str(pdf_files[0])
            print(f"   Found: {pdf_path}")
        else:
            print("   ❌ No PDF files found for testing")
            return
    
    print(f"\n2. Testing with PDF: {pdf_path}")
    print(f"   File size: {Path(pdf_path).stat().st_size / 1024:.1f} KB")
    
    # Test if it should convert
    should_convert = client._should_convert_to_image(pdf_path)
    print(f"\n3. Should convert to image? {should_convert}")
    
    if should_convert:
        print("\n4. Converting PDF to image...")
        image_path = client._convert_pdf_to_image(pdf_path)
        
        if image_path:
            print(f"   ✅ Conversion successful!")
            print(f"   Image path: {image_path}")
            print(f"   Image size: {Path(image_path).stat().st_size / 1024:.1f} KB")
            
            # Cleanup
            Path(image_path).unlink()
            print(f"   🗑️  Cleaned up temporary image")
        else:
            print(f"   ❌ Conversion failed")
            print(f"   Note: Make sure poppler is installed (brew install poppler)")
    
    print("\n" + "="*80)
    print("Test Complete")
    print("="*80)

if __name__ == "__main__":
    test_pdf_conversion()
