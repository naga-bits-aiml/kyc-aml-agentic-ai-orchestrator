"""
API Discovery and Auto-Tool Generation Module.

This module can discover API endpoints via /info or OpenAPI specs
and automatically generate CrewAI tools from the discovered schemas.
"""
import requests
from typing import Dict, Any, List, Optional, Callable
from crewai.tools import tool
from utilities import logger, config
import json


class APIDiscovery:
    """Discover and auto-generate tools from API specifications."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize API discovery.
        
        Args:
            base_url: Base URL of the API
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.discovered_endpoints = {}
        self.generated_tools = []
    
    def discover_from_info_endpoint(self, info_path: str = "/info") -> Dict[str, Any]:
        """
        Discover API capabilities from an /info endpoint.
        
        Args:
            info_path: Path to the info endpoint (default: /info)
            
        Returns:
            Dictionary containing API information and available endpoints
        """
        logger.info(f"Discovering API from: {self.base_url}{info_path}")
        
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.get(
                f"{self.base_url}{info_path}",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            api_info = response.json()
            self.discovered_endpoints = api_info.get('endpoints', {})
            
            logger.info(f"Discovered {len(self.discovered_endpoints)} endpoints")
            return api_info
            
        except Exception as e:
            logger.error(f"Failed to discover API: {e}")
            return {"error": str(e)}
    
    def discover_from_openapi(self, openapi_path: str = "/openapi.json") -> Dict[str, Any]:
        """
        Discover API capabilities from OpenAPI/Swagger specification.
        
        Args:
            openapi_path: Path to OpenAPI spec (default: /openapi.json)
            
        Returns:
            Parsed OpenAPI specification
        """
        logger.info(f"Discovering API from OpenAPI spec: {self.base_url}{openapi_path}")
        
        try:
            response = requests.get(
                f"{self.base_url}{openapi_path}",
                timeout=10
            )
            response.raise_for_status()
            
            openapi_spec = response.json()
            self._parse_openapi_spec(openapi_spec)
            
            return openapi_spec
            
        except Exception as e:
            logger.error(f"Failed to load OpenAPI spec: {e}")
            return {"error": str(e)}
    
    def _parse_openapi_spec(self, spec: Dict[str, Any]) -> None:
        """Parse OpenAPI specification and extract endpoints."""
        paths = spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    endpoint_key = f"{method.upper()} {path}"
                    self.discovered_endpoints[endpoint_key] = {
                        'path': path,
                        'method': method.upper(),
                        'summary': details.get('summary', ''),
                        'description': details.get('description', ''),
                        'parameters': details.get('parameters', []),
                        'requestBody': details.get('requestBody', {}),
                        'responses': details.get('responses', {})
                    }
        
        logger.info(f"Parsed {len(self.discovered_endpoints)} endpoints from OpenAPI spec")
    
    def generate_tool_from_endpoint(
        self,
        endpoint_key: str,
        endpoint_info: Dict[str, Any]
    ) -> Optional[Callable]:
        """
        Generate a CrewAI tool from an endpoint specification.
        
        Args:
            endpoint_key: Unique key for the endpoint
            endpoint_info: Endpoint specification
            
        Returns:
            Generated tool function
        """
        path = endpoint_info.get('path', '')
        method = endpoint_info.get('method', 'GET')
        summary = endpoint_info.get('summary', endpoint_key)
        description = endpoint_info.get('description', f'Call {method} {path}')
        
        # Create tool function
        def endpoint_tool(**kwargs) -> Dict[str, Any]:
            """Dynamically generated tool for API endpoint."""
            logger.info(f"Calling {method} {path} with params: {kwargs}")
            
            try:
                headers = {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                
                url = f"{self.base_url}{path}"
                
                # Replace path parameters
                for key, value in kwargs.items():
                    if f"{{{key}}}" in url:
                        url = url.replace(f"{{{key}}}", str(value))
                
                # Make request
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=kwargs, timeout=30)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, json=kwargs, timeout=30)
                elif method == 'PUT':
                    response = requests.put(url, headers=headers, json=kwargs, timeout=30)
                elif method == 'DELETE':
                    response = requests.delete(url, headers=headers, timeout=30)
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}
                
                response.raise_for_status()
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json() if response.text else {}
                }
                
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Set function metadata
        endpoint_tool.__name__ = f"{method.lower()}_{path.replace('/', '_').replace('{', '').replace('}', '').strip('_')}"
        endpoint_tool.__doc__ = f"{summary}\n\n{description}"
        
        # Decorate as CrewAI tool
        tool_name = summary or endpoint_key
        decorated_tool = tool(tool_name)(endpoint_tool)
        
        return decorated_tool
    
    def auto_generate_tools(self) -> List[Callable]:
        """
        Auto-generate tools for all discovered endpoints.
        
        Returns:
            List of generated tool functions
        """
        logger.info(f"Auto-generating tools for {len(self.discovered_endpoints)} endpoints")
        
        self.generated_tools = []
        
        for endpoint_key, endpoint_info in self.discovered_endpoints.items():
            try:
                tool_func = self.generate_tool_from_endpoint(endpoint_key, endpoint_info)
                if tool_func:
                    self.generated_tools.append(tool_func)
                    logger.info(f"Generated tool: {tool_func.__name__}")
            except Exception as e:
                logger.error(f"Failed to generate tool for {endpoint_key}: {e}")
        
        logger.info(f"Successfully generated {len(self.generated_tools)} tools")
        return self.generated_tools
    
    def get_tool_summary(self) -> List[Dict[str, str]]:
        """
        Get summary of all generated tools.
        
        Returns:
            List of tool summaries
        """
        return [
            {
                "name": tool.__name__,
                "description": tool.__doc__ or "No description"
            }
            for tool in self.generated_tools
        ]


class ClassifierAPIDiscovery:
    """Specialized discovery for the KYC document classifier API."""
    
    def __init__(self):
        """Initialize classifier API discovery."""
        self.base_url = config.classifier_api_url
        self.api_key = config.classifier_api_key
        self.discovery = APIDiscovery(self.base_url, self.api_key)
    
    def discover_and_generate_tools(self) -> List[Callable]:
        """
        Discover classifier API and generate tools.
        
        Returns:
            List of generated tools
        """
        logger.info("Discovering KYC classifier API capabilities")
        
        # Try /info endpoint first
        info = self.discovery.discover_from_info_endpoint("/info")
        
        if not info.get('error'):
            logger.info(f"Discovered API info: {info.get('name', 'Unknown API')}")
        else:
            # Try OpenAPI spec
            logger.info("Trying OpenAPI specification...")
            openapi = self.discovery.discover_from_openapi("/openapi.json")
            
            if openapi.get('error'):
                # Fallback to manually defined endpoints
                logger.warning("Could not auto-discover API, using manual definitions")
                self._define_manual_endpoints()
        
        # Generate tools from discovered endpoints
        tools = self.discovery.auto_generate_tools()
        
        logger.info(f"Generated {len(tools)} tools for classifier API")
        return tools
    
    def _define_manual_endpoints(self) -> None:
        """Define endpoints manually if auto-discovery fails."""
        self.discovery.discovered_endpoints = {
            "POST /classify": {
                "path": "/classify",
                "method": "POST",
                "summary": "Classify Single Document",
                "description": "Classify a single document and return its type",
                "parameters": [],
                "requestBody": {
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string", "format": "binary"}
                                }
                            }
                        }
                    }
                }
            },
            "POST /batch_classify": {
                "path": "/batch_classify",
                "method": "POST",
                "summary": "Batch Classify Documents",
                "description": "Classify multiple documents in a single request",
                "parameters": [],
                "requestBody": {
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "files": {
                                        "type": "array",
                                        "items": {"type": "string", "format": "binary"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "GET /health": {
                "path": "/health",
                "method": "GET",
                "summary": "Health Check",
                "description": "Check if the API is healthy and running",
                "parameters": []
            }
        }


# Convenience function to discover and generate tools
def discover_api_tools(base_url: str, api_key: Optional[str] = None) -> List[Callable]:
    """
    Discover API and auto-generate tools.
    
    Args:
        base_url: Base URL of the API
        api_key: Optional API key
        
    Returns:
        List of generated tools
    """
    discovery = APIDiscovery(base_url, api_key)
    
    # Try multiple discovery methods
    info = discovery.discover_from_info_endpoint("/info")
    if info.get('error'):
        discovery.discover_from_openapi("/openapi.json")
    
    return discovery.auto_generate_tools()


__all__ = [
    'APIDiscovery',
    'ClassifierAPIDiscovery',
    'discover_api_tools'
]
