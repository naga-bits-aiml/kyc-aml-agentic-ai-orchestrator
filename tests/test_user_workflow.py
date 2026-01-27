#!/usr/bin/env python3
"""
Quick test to verify the actual user workflow that was reported as broken.
"""

import logging
from chat_interface import ChatInterface

# Minimal logging to see key actions
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_user_workflow():
    """Test the exact user workflow that was reported as broken."""
    print("\n" + "="*80)
    print("Testing User Workflow: Create Case + Add Document")
    print("="*80 + "\n")
    
    chat = ChatInterface()
    
    # User creates new case
    print("1. User: new case")
    response = chat.handle_user_input("new case")
    print(f"   Bot: {response[:80]}...")
    
    # User provides case reference  
    print("\n2. User: KYC-2026-001")
    response = chat.handle_user_input("KYC-2026-001")
    print(f"   Bot: {response[:150]}...")
    
    # User provides file path (this was broken)
    print("\n3. User: ~/Downloads/pan-1.pdf")
    response = chat.handle_user_input("~/Downloads/pan-1.pdf")
    
    # Print full response
    print(f"\n   Bot Response:\n{response}\n")
    
    # Check if processing happened
    if "Processing Complete" in response or "Documents Processed" in response:
        print("✅ SUCCESS: Document was processed!")
    elif "not successfully added" in response or "No documents" in response:
        print("❌ FAILED: Document was NOT processed!")
    else:
        print("⚠️  UNCLEAR: Check response above")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    test_user_workflow()
