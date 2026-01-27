"""Utility functions for the KYC-AML Agentic AI Orchestrator."""
import os
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
from datetime import datetime
import uuid


def generate_document_id() -> str:
    """
    Generate a globally unique document ID.
    Format: DOC_YYYYMMDD_HHMMSS_XXXXX
    Example: DOC_20260127_143022_A3F8B
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:5].upper()
    return f"DOC_{timestamp}_{unique_suffix}"


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """Validate if file has an allowed extension."""
    ext = Path(filename).suffix.lower()
    return ext in [e.lower() for e in allowed_extensions]


def validate_file_size(file_path: str, max_size_bytes: int) -> bool:
    """Validate if file size is within limits."""
    if not os.path.exists(file_path):
        return False
    return os.path.getsize(file_path) <= max_size_bytes


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def create_document_metadata(file_path: str) -> Dict[str, Any]:
    """Create metadata for a document."""
    file_path_obj = Path(file_path)
    return {
        "filename": file_path_obj.name,
        "extension": file_path_obj.suffix,
        "size_bytes": os.path.getsize(file_path),
        "hash": compute_file_hash(file_path),
        "uploaded_at": datetime.now().isoformat(),
        "absolute_path": str(file_path_obj.absolute())
    }


def ensure_directory(directory: str) -> None:
    """Ensure a directory exists."""
    Path(directory).mkdir(parents=True, exist_ok=True)
