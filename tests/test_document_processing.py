"""
Test script to verify document processing through chat interface.
"""
import os
from pathlib import Path
from chat_interface import ChatInterface
from utilities import logger

def create_test_document():
    """Create a test document for classification."""
    test_dir = Path("test_documents")
    test_dir.mkdir(exist_ok=True)
    
    test_file = test_dir / "sample_passport.txt"
    with open(test_file, "w") as f:
        f.write("""
PASSPORT
United States of America

Passport No: 123456789
Surname: DOE
Given Names: JOHN MICHAEL
Nationality: USA
Date of Birth: 01 JAN 1990
Sex: M
Place of Birth: NEW YORK, USA
Date of Issue: 01 JAN 2020
Date of Expiry: 01 JAN 2030
        """)
    
    logger.info(f"✓ Created test document: {test_file.absolute()}")
    return str(test_file.absolute())

def test_path_extraction():
    """Test path extraction from user input."""
    chat = ChatInterface()
    
    test_cases = [
        "Please classify this document: C:\\Users\\test\\document.pdf",
        "I want to submit my passport at C:/Documents/passport.jpg",
        "Can you process 'C:\\My Documents\\utility bill.pdf'",
        "Analyze /home/user/doc.pdf",
    ]
    
    print("\n🧪 Testing path extraction:")
    for test_input in test_cases:
        paths = chat._extract_file_paths(test_input)
        print(f"  Input: {test_input}")
        print(f"  Paths: {paths}\n")

def test_document_processing():
    """Test end-to-end document processing."""
    print("\n📄 Testing Document Processing\n")
    
    # Create test document
    test_file = create_test_document()
    
    # Initialize chat interface
    chat = ChatInterface()
    
    # Test different input formats
    test_inputs = [
        f"Please classify {test_file}",
        f"I want to process this document: {test_file}",
        f"/process {test_file}",
    ]
    
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {user_input[:50]}...")
        print('='*60)
        
        response = chat.handle_user_input(user_input)
        print(f"\n📨 Response:\n{response}\n")

if __name__ == "__main__":
    # First test path extraction
    test_path_extraction()
    
    # Then test full processing
    test_document_processing()
