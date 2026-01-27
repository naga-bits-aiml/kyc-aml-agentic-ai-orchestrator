"""
Quick test to verify production-grade logging is working correctly.

This script tests:
1. API client initialization logging
2. API info logging
3. Simulated classification logging (without actual API call)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.classifier_api_client import ClassifierAPIClient
from tools.classifier_tools import get_classifier_api_info_tool
from utilities import logger

def test_logging():
    """Test that all critical logging points are working."""
    
    print("\n" + "="*80)
    print("TESTING PRODUCTION-GRADE LOGGING")
    print("="*80 + "\n")
    
    # Test 1: API Client Initialization
    print("Test 1: API Client Initialization Logging")
    print("-" * 80)
    client = ClassifierAPIClient()
    print("✅ API Client initialized (check logs above)")
    print()
    
    # Test 2: API Info Logging
    print("Test 2: API Info Logging")
    print("-" * 80)
    api_info = get_classifier_api_info_tool()
    print("✅ API Info retrieved (check logs above)")
    print(f"   Full URL: {api_info['full_url']}")
    print(f"   Supported Classes: {len(api_info['supported_classes'])}")
    print()
    
    # Test 3: API Health Check
    print("Test 3: API Health Check Logging")
    print("-" * 80)
    is_healthy = client.health_check()
    print(f"✅ Health check completed: {'Healthy' if is_healthy else 'Failed'}")
    print()
    
    # Test 4: Get API Info from Client
    print("Test 4: Client API Info")
    print("-" * 80)
    client_info = client.get_api_info()
    print(f"✅ Client API Info retrieved")
    print(f"   Endpoint: {client_info['endpoint']}")
    print(f"   Method: {client_info['method']}")
    print()
    
    print("="*80)
    print("LOGGING TEST COMPLETE")
    print("="*80)
    print()
    print("📝 Review the logs above to verify:")
    print("   ✅ API Client initialization with full details")
    print("   ✅ API info with endpoint and supported classes")
    print("   ✅ Health check status")
    print("   ✅ All logs use existing logger (no errors)")
    print()
    print("💡 To test full classification logging:")
    print("   1. Ensure the classifier API is running")
    print("   2. Run: python chat_interface.py")
    print("   3. Upload a document and see comprehensive logs")
    print()

if __name__ == "__main__":
    test_logging()
