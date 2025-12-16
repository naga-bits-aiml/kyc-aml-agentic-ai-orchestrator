"""
Example script demonstrating API auto-discovery and tool generation.

This script shows how to discover APIs and automatically generate tools.
"""
from tools.api_discovery import APIDiscovery, ClassifierAPIDiscovery, discover_api_tools
from utilities import logger


def example_basic_discovery():
    """Example: Basic API discovery from /info endpoint."""
    print("\n" + "="*80)
    print("Example 1: Basic API Discovery from /info endpoint")
    print("="*80)
    
    # Discover API
    discovery = APIDiscovery("https://api.example.com", api_key="your_key")
    
    # Try /info endpoint
    info = discovery.discover_from_info_endpoint("/info")
    print(f"\nAPI Info: {info}")
    
    # Generate tools
    tools = discovery.auto_generate_tools()
    print(f"\nGenerated {len(tools)} tools:")
    for tool_info in discovery.get_tool_summary():
        print(f"  - {tool_info['name']}: {tool_info['description']}")


def example_openapi_discovery():
    """Example: API discovery from OpenAPI/Swagger specification."""
    print("\n" + "="*80)
    print("Example 2: API Discovery from OpenAPI Specification")
    print("="*80)
    
    # Discover API using OpenAPI spec
    discovery = APIDiscovery("https://api.example.com")
    
    # Load OpenAPI spec
    spec = discovery.discover_from_openapi("/openapi.json")
    print(f"\nDiscovered {len(discovery.discovered_endpoints)} endpoints")
    
    # Generate tools
    tools = discovery.auto_generate_tools()
    print(f"\nGenerated {len(tools)} tools")


def example_classifier_api_discovery():
    """Example: Discover KYC classifier API."""
    print("\n" + "="*80)
    print("Example 3: Discover KYC Document Classifier API")
    print("="*80)
    
    # Use specialized classifier discovery
    classifier_discovery = ClassifierAPIDiscovery()
    
    # Discover and generate tools
    tools = classifier_discovery.discover_and_generate_tools()
    
    print(f"\nGenerated {len(tools)} tools for classifier API:")
    for tool_info in classifier_discovery.discovery.get_tool_summary():
        print(f"  - {tool_info['name']}")
        print(f"    Description: {tool_info['description']}")


def example_use_discovered_tools():
    """Example: Use auto-discovered tools with agents."""
    print("\n" + "="*80)
    print("Example 4: Use Discovered Tools with Agents")
    print("="*80)
    
    from crewai import Agent
    from tools import get_tools_for_agent, discover_and_add_api_tools
    from utilities import config
    
    # Discover API tools and add them automatically
    discovered_tools = discover_and_add_api_tools(
        base_url=config.classifier_api_url,
        api_key=config.classifier_api_key,
        agent_type='classifier'
    )
    
    print(f"\nDiscovered and registered {len(discovered_tools)} tools")
    
    # Create agent with discovered tools included
    classifier_agent = Agent(
        role="Document Classifier",
        goal="Classify documents using auto-discovered API tools",
        backstory="Expert classifier with access to dynamically discovered tools",
        tools=get_tools_for_agent('classifier'),  # Now includes discovered tools!
        verbose=True
    )
    
    print(f"\nAgent has access to {len(classifier_agent.tools)} tools")


def example_manual_tool_generation():
    """Example: Manually generate tools for specific endpoints."""
    print("\n" + "="*80)
    print("Example 5: Manually Generate Tools for Specific Endpoints")
    print("="*80)
    
    discovery = APIDiscovery("https://api.example.com", api_key="key")
    
    # Manually define endpoint
    endpoint_info = {
        "path": "/users/{user_id}",
        "method": "GET",
        "summary": "Get User Info",
        "description": "Retrieve user information by ID",
        "parameters": [
            {"name": "user_id", "in": "path", "required": True, "type": "string"}
        ]
    }
    
    # Generate tool for this endpoint
    tool = discovery.generate_tool_from_endpoint("GET /users/{user_id}", endpoint_info)
    
    print(f"\nGenerated tool: {tool.__name__}")
    print(f"Description: {tool.__doc__}")
    
    # Use the tool
    # result = tool(user_id="123")
    # print(f"Result: {result}")


def example_discover_multiple_apis():
    """Example: Discover tools from multiple APIs."""
    print("\n" + "="*80)
    print("Example 6: Discover Tools from Multiple APIs")
    print("="*80)
    
    # List of APIs to discover
    apis = [
        {"url": "https://api1.example.com", "key": "key1"},
        {"url": "https://api2.example.com", "key": "key2"},
        {"url": "https://api3.example.com", "key": None},
    ]
    
    all_tools = []
    
    for api in apis:
        print(f"\nDiscovering: {api['url']}")
        tools = discover_api_tools(api['url'], api['key'])
        all_tools.extend(tools)
        print(f"  Found {len(tools)} tools")
    
    print(f"\nTotal discovered tools: {len(all_tools)}")


if __name__ == "__main__":
    print("\n🔍 API Auto-Discovery Examples")
    print("="*80)
    
    # Run examples
    try:
        example_basic_discovery()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    try:
        example_openapi_discovery()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    
    try:
        example_classifier_api_discovery()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    
    try:
        example_use_discovered_tools()
    except Exception as e:
        print(f"Example 4 failed: {e}")
    
    try:
        example_manual_tool_generation()
    except Exception as e:
        print(f"Example 5 failed: {e}")
    
    try:
        example_discover_multiple_apis()
    except Exception as e:
        print(f"Example 6 failed: {e}")
    
    print("\n" + "="*80)
    print("✅ Examples complete!")
    print("="*80 + "\n")
