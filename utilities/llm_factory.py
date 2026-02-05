"""
LLM factory for creating configured language models.
"""
from typing import Optional, List
import os
from langchain.llms.base import BaseLLM
from langchain_openai import ChatOpenAI
from utilities import config, logger

# Try to import Google Genai if available
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from google.ai.generativelanguage_v1beta.types.safety import HarmCategory, SafetySetting
    HarmBlockThreshold = SafetySetting.HarmBlockThreshold
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False
    HarmCategory = None
    HarmBlockThreshold = None


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> BaseLLM:
    """
    Create an LLM instance based on the configured provider.
    
    Args:
        provider: LLM provider ('google', 'openai'). If None, uses config.llm_provider
        model: Optional model override
        temperature: Optional temperature override
        
    Returns:
        Configured LLM instance
    """
    provider = provider or config.llm_provider
    callbacks = _build_callbacks()
    
    if provider == "google" and HAS_GOOGLE_GENAI:
        # Get timeout and retries from config using get() method
        timeout = config.get('llm.google.timeout', 120)
        max_retries = config.get('llm.google.max_retries', 3)
        
        # Disable safety filters for KYC/AML document processing
        # These documents contain regulated PII/financial data that should not be blocked
        safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        resolved_model = model or config.google_model
        resolved_temperature = temperature if temperature is not None else config.google_temperature
        return ChatGoogleGenerativeAI(
            model=resolved_model,
            temperature=resolved_temperature,
            google_api_key=config.google_api_key,
            timeout=timeout,
            max_retries=max_retries,
            safety_settings=safety_settings,
            callbacks=callbacks
        )
    else:
        # Default to OpenAI
        if provider == "google" and not HAS_GOOGLE_GENAI:
            print("⚠️  Google Genai not installed, falling back to OpenAI")
        
        timeout = config.get('llm.openai.timeout', 120)
        max_retries = config.get('llm.openai.max_retries', 3)
        
        resolved_model = model or config.openai_model
        resolved_temperature = temperature if temperature is not None else config.openai_temperature
        return ChatOpenAI(
            model=resolved_model,
            temperature=resolved_temperature,
            openai_api_key=config.openai_api_key,
            timeout=timeout,
            max_retries=max_retries,
            callbacks=callbacks
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


def _build_callbacks() -> List[object]:
    if os.getenv("KYC_LLM_LOG_PROMPTS", "").lower() not in {"1", "true", "yes"}:
        return []
    try:
        from langchain.callbacks.base import BaseCallbackHandler
    except Exception as e:
        logger.warning(f"Prompt logging disabled (langchain callbacks import failed): {e}")
        return []

    class PromptLoggingHandler(BaseCallbackHandler):
        """Log LLM prompts and responses for debugging."""

        def on_llm_start(self, serialized, prompts: List[str], **kwargs):  # type: ignore[override]
            for prompt in prompts:
                logger.info(
                    "\n" + "=" * 80 + "\n" +
                    "LLM PROMPT\n" +
                    "=" * 80 + "\n" +
                    prompt[:8000] + "\n" +
                    "=" * 80
                )

        def on_llm_end(self, response, **kwargs):  # type: ignore[override]
            try:
                text = response.generations[0][0].text
            except Exception:
                text = str(response)
            logger.info(
                "\n" + "=" * 80 + "\n" +
                "LLM RESPONSE\n" +
                "=" * 80 + "\n" +
                text[:8000] + "\n" +
                "=" * 80
            )

        def on_llm_error(self, error, **kwargs):  # type: ignore[override]
            logger.error(f"LLM error: {error}")

    return [PromptLoggingHandler()]
