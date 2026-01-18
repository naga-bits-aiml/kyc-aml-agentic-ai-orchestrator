"""CrewAI tools for document text extraction."""
from pathlib import Path
import mimetypes
from typing import Dict, Any


def analyze_document_type(file_path: str) -> str:
    """
    Analyze document type to determine if OCR or direct extraction is needed.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Analysis result: "ocr_required", "direct_extraction", or "unsupported"
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(str(file_path))
    
    # Image formats always need OCR
    image_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
    if extension in image_formats:
        return f"ocr_required: Image file ({extension})"
    
    # Text formats - direct extraction
    text_formats = {'.txt', '.csv', '.json'}
    if extension in text_formats:
        return f"direct_extraction: Plain text file ({extension})"
    
    # DOCX - direct extraction
    if extension in {'.docx', '.doc'}:
        return f"direct_extraction: Microsoft Word document"
    
    # PDF - needs investigation (could be scanned or have text layer)
    if extension == '.pdf':
        return "investigation_needed: PDF requires content analysis"
    
    return f"unsupported: Unknown format {extension} (MIME: {mime_type})"


def check_extraction_quality(text: str) -> Dict[str, Any]:
    """
    Assess the quality of extracted text.
    
    Args:
        text: The extracted text to assess
        
    Returns:
        Quality assessment with score and issues
    """
    if not text or len(text.strip()) == 0:
        return {
            "score": 0.0,
            "status": "empty",
            "issues": ["No text extracted"]
        }
    
    issues = []
    score = 1.0
    
    # Check length
    if len(text) < 10:
        issues.append("Text too short")
        score *= 0.3
    
    # Check for reasonable character distribution
    alpha_count = sum(c.isalpha() for c in text)
    if len(text) > 0:
        alpha_ratio = alpha_count / len(text)
        if alpha_ratio < 0.3:
            issues.append("Too few alphabetic characters")
            score *= 0.5
    
    # Check for excessive special characters (OCR artifacts)
    special_count = sum(not c.isalnum() and not c.isspace() for c in text)
    if len(text) > 0:
        special_ratio = special_count / len(text)
        if special_ratio > 0.3:
            issues.append("Too many special characters (possible OCR artifacts)")
            score *= 0.6
    
    status = "excellent" if score > 0.9 else "good" if score > 0.7 else "acceptable" if score > 0.5 else "poor"
    
    return {
        "score": round(score, 2),
        "status": status,
        "length": len(text),
        "alpha_ratio": round(alpha_ratio, 2) if len(text) > 0 else 0,
        "issues": issues if issues else ["No issues detected"]
    }


def get_document_info(file_path: str) -> Dict[str, Any]:
    """
    Get basic information about a document file.
    
    Args:
        file_path: Path to the document
        
    Returns:
        Document information dictionary
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {
            "error": "File does not exist",
            "path": str(file_path)
        }
    
    mime_type, _ = mimetypes.guess_type(str(file_path))
    
    return {
        "name": file_path.name,
        "extension": file_path.suffix.lower(),
        "size_bytes": file_path.stat().st_size,
        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "mime_type": mime_type or "unknown",
        "exists": True
    }
