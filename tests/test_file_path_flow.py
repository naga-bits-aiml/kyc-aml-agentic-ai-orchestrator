#!/usr/bin/env python3
"""
Test script to verify file path detection and processing flow.
"""

import logging
from chat_interface import ChatInterface

# Set up logging to see all debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_file_path_flow():
    """Test the file path detection and processing flow."""
    print("\n" + "="*80)
    print("Testing File Path Detection Flow")
    print("="*80 + "\n")
    
    # Initialize chat interface
    chat = ChatInterface()
    
    # Set a case reference first
    print("\n1. Setting case reference...")
    response = chat.handle_user_input("new case")
    print(f"Response: {response}\n")
    
    response = chat.handle_user_input("KYC-TEST-001")
    print(f"Response: {response}\n")
    
    # Now test file path detection
    print("\n2. Testing file path detection with: ~/Downloads/pan-1.pdf")
    print("-" * 80)
    
    response = chat.handle_user_input("~/Downloads/pan-1.pdf")
    print(f"\nResponse: {response}\n")
    
    print("="*80)
    print("Test Complete - Check logs above for debug information")
    print("="*80)

if __name__ == "__main__":
    test_file_path_flow()
