"""
LLM factory for creating configured language models.
"""
from typing import Optional
from langchain.llms.base import BaseLLM
from langchain_openai import ChatOpenAI
from utilities import config

# Try to import Google Genai if available
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False


def create_llm(provider: Optional[str] = None) -> BaseLLM:
    """
    Create an LLM instance based on the configured provider.
    
    Args:
        provider: LLM provider ('google', 'openai'). If None, uses config.llm_provider
        
    Returns:
        Configured LLM instance
    """
    provider = provider or config.llm_provider
    
    if provider == "google" and HAS_GOOGLE_GENAI:
        # Get timeout and retries from config using get() method
        timeout = config.get('llm.google.timeout', 120)
        max_retries = config.get('llm.google.max_retries', 3)
        
        return ChatGoogleGenerativeAI(
            model=config.google_model,
            temperature=config.google_temperature,
            google_api_key=config.google_api_key,
            timeout=timeout,
            max_retries=max_retries
        )
    else:
        # Default to OpenAI
        if provider == "google" and not HAS_GOOGLE_GENAI:
            print("⚠️  Google Genai not installed, falling back to OpenAI")
        
        timeout = config.get('llm.openai.timeout', 120)
        max_retries = config.get('llm.openai.max_retries', 3)
        
        return ChatOpenAI(
            model=config.openai_model,
            temperature=config.openai_temperature,
            openai_api_key=config.openai_api_key,
            timeout=timeout,
            max_retries=max_retries
        )


def get_model_info() -> tuple[str, str]:
    """
    Get the current model name and provider.
    
    Returns:
        Tuple of (model_name, provider)
    """
    provider = config.llm_provider
    
    if provider == "google":
        return (config.google_model, "google")
    else:
        return (config.openai_model, "openai")
