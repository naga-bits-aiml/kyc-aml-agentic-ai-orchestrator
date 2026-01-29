"""
Extraction Agent Tools - REST API calls for document data extraction.

These tools handle:
- External REST API calls for OCR/field extraction
- Retry logic for transient failures
- Result parsing and validation
- Metadata updates with extraction results

Uses the OCR API (Google Vision or compatible) for text extraction.
All REST calls are wrapped in tools with proper error handling.
"""

import json
import time
import base64
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool

# Import utilities
try:
    from utilities import logger, settings, config
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    class Settings:
        documents_dir = "./documents"
    settings = Settings()
    class Config:
        @staticmethod
        def get(key, default=None):
            return default
    config = Config()


# ==================== CONFIGURATION ====================

def get_extraction_api_config() -> Dict[str, Any]:
    """
    Get OCR/extraction API configuration.
    Uses config.get('api.ocr', {}) for API settings.
    
    Configured for Google Vision API TEXT_DETECTION feature.
    
    Returns:
        Dictionary with API configuration
    """
    # Load OCR config from settings
    ocr_config = config.get('api.ocr', {})
    
    # Build API info from config
    base_url = ocr_config.get('base_url', 'https://vision.googleapis.com/v1/images:annotate')
    
    api_info = {
        "base_url": base_url.rstrip('/'),
        "full_url": base_url,
        "method": "POST",
        "content_type": "application/json",
        "description": "Google Vision OCR for Indian identity documents",
        "provider": ocr_config.get('provider', 'google_vision'),
        "api_key": ocr_config.get('api_key'),
        "api_key_header": "X-goog-api-key",  # Google Vision specific header
        "feature_type": "TEXT_DETECTION",  # Vision API feature
        "timeout": ocr_config.get('timeout', 60),
        "max_retries": ocr_config.get('max_retries', 3),
        "retry_delay": ocr_config.get('retry_delay', 2),
        "confidence_threshold": ocr_config.get('confidence_threshold', 0.7),
        "supported_document_types": ["Aadhar", "Driving License", "PAN Card", "Passport", "Voter ID"],
        "supported_formats": ["image/jpeg", "image/png", "image/bmp", "image/tiff", "image/gif"]
    }
    
    logger.debug(f"OCR API config: provider={api_info['provider']}, url={api_info['base_url']}")
    return api_info


# ==================== HELPER FUNCTIONS ====================

def make_vision_api_request(
    file_path: str,
    api_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Make Google Vision API request with base64 encoded image.
    
    Uses TEXT_DETECTION feature for OCR extraction.
    Includes retry logic for transient failures.
    
    Args:
        file_path: Path to the image file
        api_config: API configuration dictionary
        
    Returns:
        Dictionary with:
        - success: Boolean
        - text: Extracted text
        - confidence: Confidence score
        - word_count: Number of words
        - char_count: Number of characters
        - error: Error message if failed
    """
    url = api_config["full_url"]
    api_key = api_config.get("api_key")
    timeout = api_config.get("timeout", 60)
    max_retries = api_config.get("max_retries", 3)
    retry_delay = api_config.get("retry_delay", 2)
    
    if not api_key:
        return {
            "success": False,
            "error": "Google Vision API key not configured. Set OCR_API_KEY.",
            "attempts": 0
        }
    
    # Read and encode file to base64
    file_path = Path(file_path)
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        content_base64 = base64.b64encode(file_content).decode('utf-8')
        file_size = len(file_content)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
            "attempts": 0
        }
    
    # Prepare Vision API payload
    payload = {
        "requests": [
            {
                "image": {"content": content_base64},
                "features": [{"type": api_config.get("feature_type", "TEXT_DETECTION")}]
            }
        ]
    }
    
    # Headers for Google Vision API
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }
    
    last_error = None
    start_time = time.time()
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"Vision API request attempt {attempt}/{max_retries}: "
                f"{file_path.name} ({file_size:,} bytes)"
            )
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                duration = time.time() - start_time
                
                # Parse Vision API response
                text = ""
                confidence = 0.0
                
                if "responses" in result and len(result["responses"]) > 0:
                    response_data = result["responses"][0]
                    
                    # Check for API errors in response
                    if "error" in response_data:
                        error_msg = response_data["error"].get("message", "Unknown Vision API error")
                        return {
                            "success": False,
                            "error": f"Vision API error: {error_msg}",
                            "attempts": attempt
                        }
                    
                    # Get full text annotation
                    if "fullTextAnnotation" in response_data:
                        text = response_data["fullTextAnnotation"].get("text", "")
                        
                        # Calculate average confidence from pages
                        pages = response_data["fullTextAnnotation"].get("pages", [])
                        if pages:
                            confidences = [p.get("confidence", 0) for p in pages if "confidence" in p]
                            confidence = sum(confidences) / len(confidences) if confidences else 0.0
                    
                    # Fallback to textAnnotations if fullTextAnnotation not available
                    elif "textAnnotations" in response_data:
                        annotations = response_data["textAnnotations"]
                        if annotations:
                            text = annotations[0].get("description", "")
                            confidence = 0.85  # Default confidence for text annotations
                
                word_count = len(text.split()) if text else 0
                char_count = len(text) if text else 0
                
                logger.info(
                    f"Vision API extraction successful: {word_count} words, "
                    f"{char_count} chars, confidence: {confidence:.2%}"
                )
                
                return {
                    "success": True,
                    "text": text,
                    "confidence": confidence,
                    "word_count": word_count,
                    "char_count": char_count,
                    "duration_seconds": duration,
                    "file_size_bytes": file_size,
                    "raw_response": result,
                    "error": None,
                    "attempts": attempt
                }
            
            # Retryable errors (5xx, 429)
            if response.status_code >= 500 or response.status_code == 429:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"Retryable error: {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay * attempt)
                continue
            
            # Non-retryable client errors
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "attempts": attempt
            }
            
        except requests.exceptions.Timeout:
            last_error = f"Request timeout after {timeout}s"
            logger.warning(f"Timeout on attempt {attempt}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {str(e)}"
            logger.warning(f"Connection error on attempt {attempt}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    return {
        "success": False,
        "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
        "attempts": max_retries
    }


# ==================== LLM-BASED EXTRACTION ====================

def _get_kyc_field_schema(document_type: str) -> Dict[str, Any]:
    """
    Get the expected KYC field schema for a document type.
    
    Returns a JSON schema that the LLM should fill with extracted data.
    """
    schemas = {
        "aadhar": {
            "full_name": "string - Full name as printed on card",
            "date_of_birth": "string - Date of birth in DD/MM/YYYY format",
            "gender": "string - Male/Female",
            "aadhar_number": "string - 12 digit Aadhar number (XXXX XXXX XXXX)",
            "address": "string - Complete address if visible",
            "vid_number": "string - Virtual ID if present"
        },
        "pan": {
            "full_name": "string - Full name as printed on card",
            "date_of_birth": "string - Date of birth in DD/MM/YYYY format",
            "pan_number": "string - 10 character PAN (e.g., ABCDE1234F)",
            "father_name": "string - Father's name if present"
        },
        "driving": {
            "full_name": "string - Full name as printed on license",
            "date_of_birth": "string - Date of birth in DD/MM/YYYY format",
            "license_number": "string - Driving license number",
            "issue_date": "string - Date of issue in DD/MM/YYYY format",
            "expiry_date": "string - Validity/expiry date in DD/MM/YYYY format",
            "address": "string - Address if visible",
            "blood_group": "string - Blood group if present",
            "vehicle_class": "string - Class of vehicle (LMV, MCWG, etc.)"
        },
        "passport": {
            "full_name": "string - Full name as in passport",
            "date_of_birth": "string - Date of birth in DD/MM/YYYY format",
            "passport_number": "string - Passport number (letter + 7 digits)",
            "nationality": "string - Nationality",
            "place_of_birth": "string - Place of birth",
            "issue_date": "string - Date of issue",
            "expiry_date": "string - Date of expiry",
            "place_of_issue": "string - Place of issue",
            "gender": "string - Male/Female",
            "address": "string - Address if present"
        },
        "voter": {
            "full_name": "string - Full name (elector's name)",
            "date_of_birth": "string - Date of birth or age",
            "voter_id_number": "string - EPIC number (3 letters + 7 digits)",
            "father_name": "string - Father's/Husband's name",
            "gender": "string - Male/Female",
            "address": "string - Address",
            "constituency": "string - Assembly/Parliamentary constituency"
        }
    }
    
    # Normalize document type
    doc_type_lower = document_type.lower().replace(" ", "_").replace("-", "_")
    
    # Find matching schema
    for key in schemas:
        if key in doc_type_lower or doc_type_lower in key:
            return schemas[key]
    
    # Default generic schema
    return {
        "full_name": "string - Full name",
        "date_of_birth": "string - Date of birth",
        "document_number": "string - Primary document ID/number",
        "address": "string - Address if present"
    }


def _extract_with_llm(raw_text: str, document_type: str) -> Dict[str, Any]:
    """
    Use LLM to extract structured KYC data from OCR text.
    
    Passes the OCR text to an LLM with a specific JSON schema
    to extract and normalize KYC-relevant fields.
    
    Args:
        raw_text: Raw OCR text from Vision API
        document_type: Classified document type
        
    Returns:
        Dictionary with extracted KYC fields
    """
    try:
        from utilities.llm_factory import create_llm
    except ImportError:
        logger.warning("LLM factory not available, falling back to regex extraction")
        return _parse_fields_from_text(raw_text, document_type)
    
    # Get expected schema for this document type
    field_schema = _get_kyc_field_schema(document_type)
    
    # Build the extraction prompt
    prompt = f"""You are a KYC document data extraction specialist. Extract structured information from the following OCR text of a {document_type} document.

OCR TEXT:
---
{raw_text}
---

REQUIRED OUTPUT FORMAT:
Extract the following fields and return ONLY a valid JSON object (no markdown, no explanation):

{json.dumps(field_schema, indent=2)}

INSTRUCTIONS:
1. Extract exact values as they appear in the document
2. For dates, use DD/MM/YYYY format
3. For names, use proper capitalization (Title Case)
4. If a field is not found or unclear, use null
5. For document numbers, remove spaces and normalize format
6. Return ONLY the JSON object, nothing else

JSON OUTPUT:"""

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        
        # Extract content from response
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        # Clean up response - remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        extracted_data = json.loads(response_text)
        
        # Clean null values and empty strings
        cleaned_data = {k: v for k, v in extracted_data.items() if v is not None and v != "" and v != "null"}
        
        logger.info(f"LLM extracted {len(cleaned_data)} fields from {document_type}")
        
        return cleaned_data
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw LLM response: {response_text[:500]}")
        # Fall back to regex extraction
        return _parse_fields_from_text(raw_text, document_type)
        
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        # Fall back to regex extraction
        return _parse_fields_from_text(raw_text, document_type)


def _parse_fields_from_text(raw_text: str, document_type: str) -> Dict[str, Any]:
    """
    Parse document-specific fields from OCR raw text using regex.
    
    This is a fallback when LLM extraction is not available.
    
    Uses regex patterns to extract structured data from
    the raw text based on document type.
    
    Args:
        raw_text: Raw OCR text from Vision API
        document_type: Document type (Aadhar, PAN Card, etc.)
        
    Returns:
        Dictionary of extracted field values
    """
    import re
    
    fields = {}
    doc_type_lower = document_type.lower().replace(" ", "_").replace("-", "_")
    
    # Normalize text for pattern matching
    text = raw_text.replace("\n", " ").strip()
    
    if doc_type_lower == "aadhar" or "aadhar" in doc_type_lower:
        # Aadhar number: 12 digits in groups of 4
        aadhar_pattern = r'\b(\d{4}\s*\d{4}\s*\d{4})\b'
        match = re.search(aadhar_pattern, text)
        if match:
            fields["aadhar_number"] = match.group(1).replace(" ", "")
        
        # DOB patterns
        dob_pattern = r'\b(DOB|Date of Birth|जन्म तिथि)[:\s]*(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(dob_pattern, text, re.IGNORECASE)
        if match:
            fields["date_of_birth"] = match.group(2)
        
        # Gender
        if re.search(r'\b(Male|पुरुष)\b', text, re.IGNORECASE):
            fields["gender"] = "Male"
        elif re.search(r'\b(Female|महिला)\b', text, re.IGNORECASE):
            fields["gender"] = "Female"
    
    elif doc_type_lower == "pan_card" or "pan" in doc_type_lower:
        # PAN number: 5 letters + 4 digits + 1 letter
        pan_pattern = r'\b([A-Z]{5}[0-9]{4}[A-Z])\b'
        match = re.search(pan_pattern, text.upper())
        if match:
            fields["pan_number"] = match.group(1)
        
        # DOB
        dob_pattern = r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b'
        match = re.search(dob_pattern, text)
        if match:
            fields["date_of_birth"] = match.group(1)
    
    elif doc_type_lower == "driving_license" or "driving" in doc_type_lower or "license" in doc_type_lower:
        # License number patterns vary by state
        license_pattern = r'\b([A-Z]{2}[0-9]{2}\s*[0-9]{4}\s*[0-9]{7})\b'
        match = re.search(license_pattern, text.upper())
        if match:
            fields["license_number"] = match.group(1).replace(" ", "")
        
        # DOB
        dob_pattern = r'\b(DOB|Date of Birth)[:\s]*(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(dob_pattern, text, re.IGNORECASE)
        if match:
            fields["date_of_birth"] = match.group(2)
        
        # Validity/Expiry
        expiry_pattern = r'\b(Valid Till|Validity|Expiry)[:\s]*(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(expiry_pattern, text, re.IGNORECASE)
        if match:
            fields["expiry_date"] = match.group(2)
    
    elif doc_type_lower == "passport":
        # Passport number: 1 letter + 7 digits (Indian passport)
        passport_pattern = r'\b([A-Z][0-9]{7})\b'
        match = re.search(passport_pattern, text.upper())
        if match:
            fields["passport_number"] = match.group(1)
        
        # MRZ lines (if present)
        mrz_pattern = r'([A-Z<]{44})'
        matches = re.findall(mrz_pattern, text.upper())
        if len(matches) >= 2:
            fields["mrz_line1"] = matches[0]
            fields["mrz_line2"] = matches[1]
    
    elif doc_type_lower == "voter_id" or "voter" in doc_type_lower:
        # Voter ID: 3 letters + 7 digits
        voter_pattern = r'\b([A-Z]{3}[0-9]{7})\b'
        match = re.search(voter_pattern, text.upper())
        if match:
            fields["voter_id_number"] = match.group(1)
    
    # Try to extract name (common across all documents)
    # Look for "Name:" pattern
    name_pattern = r'\b(Name|नाम)[:\s]*([A-Za-z\s]+?)(?=\s*(?:DOB|Date|Father|S/O|D/O|W/O|$|\n))'
    match = re.search(name_pattern, text, re.IGNORECASE)
    if match:
        name = match.group(2).strip()
        if len(name) > 2:
            fields["full_name"] = name
    
    return fields


# ==================== TOOL DEFINITIONS ====================

@tool
def extract_document_data(document_id: str, document_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Call external REST API to extract data from a document.
    
    Sends the document to the extraction API along with its
    classification type (if available) to guide extraction.
    Updates the document's metadata with extracted fields.
    
    Args:
        document_id: Document ID to extract data from
        document_type: Optional document type from classification
        
    Returns:
        Dictionary with:
        - success: Boolean
        - document_id: Document ID
        - extracted_fields: Dictionary of extracted field values
        - api_response: Full API response
        - error: Error message if failed
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    # Load document metadata
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "extracted_fields": {},
            "error": f"Metadata not found for document: {document_id}"
        }
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Get document file path
    stored_path = metadata.get("stored_path")
    if not stored_path or not Path(stored_path).exists():
        return {
            "success": False,
            "document_id": document_id,
            "extracted_fields": {},
            "error": f"Document file not found: {stored_path}"
        }
    
    # Use document type from classification if not provided
    if not document_type:
        document_type = metadata.get("classification", {}).get("document_type")
    
    # Update metadata: extraction started
    metadata["extraction"]["status"] = "processing"
    metadata["extraction"]["started_at"] = datetime.now().isoformat()
    metadata["updated_at"] = datetime.now().isoformat()
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Get API configuration
    api_config = get_extraction_api_config()
    
    # Log the extraction request
    logger.info(
        f"Extracting document {document_id} via {api_config['provider']} OCR: "
        f"{Path(stored_path).name}"
    )
    
    # Make Vision API request (base64 encoded image)
    result = make_vision_api_request(stored_path, api_config)
    
    # Update metadata with result
    metadata["extraction"]["completed_at"] = datetime.now().isoformat()
    metadata["extraction"]["retry_count"] = result.get("attempts", 0)
    
    if result["success"]:
        # Extract data from Vision API response
        raw_text = result.get("text", "")
        confidence = result.get("confidence", 0.0)
        word_count = result.get("word_count", 0)
        char_count = result.get("char_count", 0)
        
        # Build base extracted fields
        extracted_fields = {
            "raw_text": raw_text,
            "word_count": word_count,
            "char_count": char_count
        }
        
        # Use LLM to extract structured KYC fields from OCR text
        if document_type and raw_text:
            logger.info(f"Extracting KYC fields using LLM for {document_type}...")
            llm_fields = _extract_with_llm(raw_text, document_type)
            extracted_fields["kyc_data"] = llm_fields
            # Also merge key fields to top level for easy access
            extracted_fields.update(llm_fields)
        
        # Log extraction result
        kyc_field_count = len(extracted_fields.get("kyc_data", {}))
        logger.info(
            f"Extraction successful for {document_id}: "
            f"{word_count} words, {kyc_field_count} KYC fields extracted"
        )
        
        metadata["extraction"]["status"] = "completed"
        metadata["extraction"]["result"] = result.get("raw_response", {})
        metadata["extraction"]["extracted_fields"] = extracted_fields
        metadata["extraction"]["kyc_data"] = extracted_fields.get("kyc_data", {})
        metadata["extraction"]["confidence"] = confidence
        metadata["extraction"]["raw_text"] = raw_text
        metadata["extraction"]["word_count"] = word_count
        metadata["extraction"]["char_count"] = char_count
        metadata["extraction"]["provider"] = api_config.get("provider", "google_vision")
        metadata["extraction"]["duration_seconds"] = result.get("duration_seconds")
        metadata["processing_status"] = "completed"
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "document_id": document_id,
            "document_type": document_type,
            "kyc_data": extracted_fields.get("kyc_data", {}),
            "extracted_fields": extracted_fields,
            "confidence": confidence,
            "raw_text": raw_text,
            "word_count": word_count,
            "char_count": char_count,
            "provider": api_config.get("provider", "google_vision"),
            "error": None
        }
    else:
        metadata["extraction"]["status"] = "failed"
        metadata["extraction"]["error"] = result["error"]
        metadata["last_error"] = result["error"]
        metadata["processing_status"] = "failed"
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": False,
            "document_id": document_id,
            "extracted_fields": {},
            "error": result["error"]
        }


@tool
def get_extraction_result(document_id: str) -> Dict[str, Any]:
    """
    Get the extraction result for a document from its metadata.
    
    Args:
        document_id: Document ID to check
        
    Returns:
        Dictionary with extraction status and result
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    metadata_path = intake_dir / f"{document_id}.metadata.json"
    
    if not metadata_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "status": "not_found",
            "error": f"Metadata not found for document: {document_id}"
        }
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    extraction = metadata.get("extraction", {})
    
    return {
        "success": True,
        "document_id": document_id,
        "status": extraction.get("status", "pending"),
        "extracted_fields": extraction.get("extracted_fields", {}),
        "result": extraction.get("result"),
        "error": extraction.get("error"),
        "started_at": extraction.get("started_at"),
        "completed_at": extraction.get("completed_at")
    }


@tool
def batch_extract_documents(document_ids: list) -> Dict[str, Any]:
    """
    Extract data from multiple documents in sequence.
    
    Args:
        document_ids: List of document IDs to extract
        
    Returns:
        Dictionary with batch results
    """
    results = []
    success_count = 0
    failed_count = 0
    
    for doc_id in document_ids:
        result = extract_document_data.invoke({"document_id": doc_id})
        results.append(result)
        
        if result["success"]:
            success_count += 1
        else:
            failed_count += 1
    
    return {
        "success": failed_count == 0,
        "total": len(document_ids),
        "succeeded": success_count,
        "failed": failed_count,
        "results": results,
        "message": f"Extracted {success_count}/{len(document_ids)} documents"
    }


@tool
def get_expected_fields_for_type(document_type: str) -> Dict[str, Any]:
    """
    Get the expected extraction fields for a document type.
    
    Useful for validation and ensuring all required fields
    are extracted.
    
    Args:
        document_type: Document type (e.g., 'passport', 'drivers_license')
        
    Returns:
        Dictionary with expected fields and their descriptions
    """
    # Define expected fields per document type (Indian ID documents)
    field_schemas = {
        "aadhar": {
            "required": ["full_name", "aadhar_number", "date_of_birth"],
            "optional": ["address", "gender", "vid_number", "issue_date"]
        },
        "driving_license": {
            "required": ["full_name", "date_of_birth", "license_number", "expiry_date"],
            "optional": ["address", "issue_date", "class_of_vehicle", "blood_group", "rto_code"]
        },
        "pan_card": {
            "required": ["full_name", "pan_number", "date_of_birth"],
            "optional": ["father_name"]
        },
        "passport": {
            "required": ["full_name", "date_of_birth", "passport_number", "nationality", "expiry_date"],
            "optional": ["place_of_birth", "issue_date", "issuing_authority", "address", "mrz_line1", "mrz_line2"]
        },
        "voter_id": {
            "required": ["full_name", "voter_id_number", "date_of_birth"],
            "optional": ["father_name", "address", "gender", "constituency"]
        }
    }
    
    doc_type_lower = document_type.lower().replace(" ", "_").replace("-", "_")
    
    if doc_type_lower in field_schemas:
        return {
            "success": True,
            "document_type": document_type,
            "fields": field_schemas[doc_type_lower]
        }
    
    return {
        "success": False,
        "document_type": document_type,
        "error": f"Unknown document type: {document_type}",
        "available_types": list(field_schemas.keys())
    }
