"""Agents package - Core API clients for tools.

Legacy agents moved to agents/legacy/ for reference.
Current implementation uses pure CrewAI with tools.
"""
from agents.classifier_api_client import ClassifierAPIClient
from agents.ocr_api_client import OCRAPIClient
from agents.base_agent import BaseAgent
from agents.shared_memory import SharedMemory

__all__ = [
    "ClassifierAPIClient",
    "OCRAPIClient",
    "BaseAgent",
    "SharedMemory"
]
