"""CrewAI tools for document text extraction."""
from crewai.tools import tool
from pathlib import Path
import mimetypes
from typing import Dict, Any, List
from agents.ocr_api_client import OCRAPIClient
from utilities import logger


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


# Initialize OCR client
_ocr_client = None

def get_ocr_client():
    """Get or create OCR API client."""
    global _ocr_client
    if _ocr_client is None:
        _ocr_client = OCRAPIClient()
    return _ocr_client


@tool("Extract Text from PDF")
def extract_text_from_pdf_tool(file_path: str) -> Dict[str, Any]:
    """
    Extract text from a PDF document using OCR.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Dictionary with extraction results including:
        - success: Boolean indicating success
        - text: Extracted text content
        - confidence: OCR confidence score
    """
    logger.info(f"Extracting text from PDF: {file_path}")
    
    try:
        client = get_ocr_client()
        result = client.process_document(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "extraction": result
        }
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return {
            "success": False,
            "file_path": file_path,
            "error": str(e)
        }


@tool("Extract Text from Image")
def extract_text_from_image_tool(file_path: str) -> Dict[str, Any]:
    """
    Extract text from an image document using OCR.
    
    Args:
        file_path: Path to the image file
        
    Returns:
        Dictionary with extraction results including:
        - success: Boolean indicating success
        - text: Extracted text content
        - confidence: OCR confidence score
    """
    logger.info(f"Extracting text from image: {file_path}")
    
    try:
        client = get_ocr_client()
        result = client.process_document(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "extraction": result
        }
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {
            "success": False,
            "file_path": file_path,
            "error": str(e)
        }


@tool("Batch Extract Documents")
def batch_extract_documents_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Extract text from multiple documents in batch.
    
    Args:
        file_paths: List of document file paths to extract from
        
    Returns:
        Dictionary with batch extraction results including:
        - success: Boolean indicating overall success
        - total: Total number of documents
        - successful: Number of successful extractions
        - failed: Number of failed extractions
        - results: List of extraction results for each document
    """
    logger.info(f"Batch extracting {len(file_paths)} documents")
    
    results = []
    successful = 0
    failed = 0
    
    client = get_ocr_client()
    
    for file_path in file_paths:
        try:
            result = client.process_document(file_path)
            results.append({
                "success": True,
                "file_path": file_path,
                "extraction": result
            })
            successful += 1
        except Exception as e:
            results.append({
                "success": False,
                "file_path": file_path,
                "error": str(e)
            })
            failed += 1
            logger.error(f"Extraction failed for {file_path}: {e}")
    
    return {
        "success": failed == 0,
        "total": len(file_paths),
        "successful": successful,
        "failed": failed,
        "results": results
    }
