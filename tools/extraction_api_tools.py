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
from crewai.tools import tool

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

def _get_kyc_extraction_prompt(raw_text: str, document_type: str) -> str:
    """
    Build the LLM prompt for KYC data extraction.
    
    Supports extraction of:
    - Multiple persons (directors, account holders, etc.)
    - Companies/Organizations
    - Financial details
    """
    prompt = f"""You are a KYC document data extraction specialist. Extract ALL entities and their details from the following OCR text.

OCR TEXT:
---
{raw_text}
---

DOCUMENT TYPE: {document_type}

INSTRUCTIONS:
1. Extract ALL persons mentioned (directors, account holders, signatories, etc.)
2. Extract ALL companies/organizations mentioned
3. Extract financial details if present (bank accounts, balances, etc.)
4. Return a JSON array of entities

ENTITY TYPES:
- "person": Individual with name, DOB, ID numbers, address
- "company": Business entity with name, CIN, address, incorporation date
- "financial": Bank/financial account details

REQUIRED OUTPUT FORMAT - Return ONLY a valid JSON array (no markdown, no explanation):

[
  {{
    "entity_type": "person",
    "role": "director/account_holder/signatory/etc",
    "full_name": "Name as in document",
    "father_name": "Father's name or null",
    "date_of_birth": "DD/MM/YYYY or null",
    "pan_reference": "10 char PAN or null",
    "aadhar_reference": "12 digit Aadhaar or null",
    "passport_reference": "Passport number or null",
    "voter_reference": "Voter ID or null",
    "driving_reference": "DL number or null",
    "other_id_reference": "Other ID number or null",
    "address": "Full address or null",
    "mobile": "Phone number or null",
    "email": "Email or null"
  }},
  {{
    "entity_type": "company",
    "company_name": "Full legal name",
    "cin_reference": "Corporate Identification Number or null",
    "other_id_reference": "Other ID number or null",
    "date_of_incorporation": "DD/MM/YYYY or null",
    "registered_address": "Registered office address or null",
    "paid_up_capital": "Amount or null",
    "gstin": "GST number or null",
    "business_type": "Type of business or null"
  }},
  {{
    "entity_type": "financial",
    "account_holder": "Name of account holder (person or company)",
    "bank_name": "Bank name or null",
    "account_number": "Account number or null",
    "ifsc_code": "IFSC code or null",
    "account_type": "savings/current/etc or null",
    "balance": "Balance amount if shown or null",
    "statement_date": "Date of statement or null"
  }}
]

RULES:
1. Extract exact values as they appear
2. Use DD/MM/YYYY for dates
3. Use Title Case for names
4. Remove spaces from ID numbers (PAN, Aadhaar)
5. Use null for missing fields (not empty string)
6. Include ALL persons found, even if same details repeat
7. Return ONLY the JSON array, nothing else


JSON OUTPUT:"""
    
    return prompt


def _extract_with_llm(raw_text: str, document_type: str) -> Dict[str, Any]:
    """
    Use LLM to extract structured KYC data from OCR text.
    
    Extracts multiple entities (persons, companies, financial accounts)
    and returns them as a structured array.
    
    Args:
        raw_text: Raw OCR text from Vision API
        document_type: Classified document type
        
    Returns:
        Dictionary with:
        - entities: List of extracted entities
        - persons: List of person entities (convenience)
        - companies: List of company entities (convenience)
        - financial: List of financial entities (convenience)
        - primary_entity: First/main entity for backward compatibility
    """
    try:
        from utilities.llm_factory import create_llm
    except ImportError:
        logger.warning("LLM factory not available, falling back to regex extraction")
        return _parse_fields_from_text(raw_text, document_type)
    
    # Build the extraction prompt
    prompt = _get_kyc_extraction_prompt(raw_text, document_type)

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
        
        # Parse JSON array
        entities = json.loads(response_text)
        
        # Ensure it's a list
        if not isinstance(entities, list):
            entities = [entities]
        
        # Clean null values from each entity
        cleaned_entities = []
        for entity in entities:
            cleaned = {k: v for k, v in entity.items() if v is not None and v != "" and v != "null"}
            if cleaned.get('entity_type'):  # Only include if has entity type
                cleaned_entities.append(cleaned)
        
        # Categorize entities for convenience
        persons = [e for e in cleaned_entities if e.get('entity_type') == 'person']
        companies = [e for e in cleaned_entities if e.get('entity_type') == 'company']
        financial = [e for e in cleaned_entities if e.get('entity_type') == 'financial']
        
        # Create primary entity for backward compatibility
        primary_entity = {}
        if persons:
            p = persons[0]
            primary_entity = {
                "full_name": p.get("full_name"),
                "date_of_birth": p.get("date_of_birth"),
                "pan_number": p.get("pan_number"),
                "aadhar_number": p.get("aadhar_number"),
                "address": p.get("address")
            }
            primary_entity = {k: v for k, v in primary_entity.items() if v}
        elif companies:
            c = companies[0]
            primary_entity = {
                "company_name": c.get("company_name"),
                "cin": c.get("cin"),
                "registered_address": c.get("registered_address")
            }
            primary_entity = {k: v for k, v in primary_entity.items() if v}
        
        logger.info(
            f"LLM extracted {len(cleaned_entities)} entities: "
            f"{len(persons)} persons, {len(companies)} companies, {len(financial)} financial"
        )
        
        return {
            "entities": cleaned_entities,
            "persons": persons,
            "companies": companies,
            "financial": financial,
            "entity_count": len(cleaned_entities),
            **primary_entity  # Backward compatibility - flatten primary entity
        }
        
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
        
        # Use LLM to extract structured KYC fields from OCR text
        kyc_data = {}
        if document_type and raw_text:
            logger.info(f"Extracting KYC fields using LLM for {document_type}...")
            kyc_data = _extract_with_llm(raw_text, document_type)
        
        # Log extraction result
        entity_count = kyc_data.get("entity_count", 0)
        logger.info(
            f"Extraction successful for {document_id}: "
            f"{word_count} words, {entity_count} entities extracted"
        )
        
        # Store raw Vision API response in separate file to keep metadata lean
        raw_response = result.get("raw_response", {})
        if raw_response:
            raw_response_path = intake_dir / f"{document_id}.vision_response.json"
            with open(raw_response_path, 'w') as f:
                json.dump(raw_response, f, indent=2)
            logger.debug(f"Stored Vision API response: {raw_response_path}")
        
        # Update metadata with essential data only (no raw API response, no duplication)
        metadata["extraction"]["status"] = "completed"
        metadata["extraction"]["vision_response_file"] = f"{document_id}.vision_response.json"
        metadata["extraction"]["kyc_data"] = kyc_data
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
            "kyc_data": kyc_data,
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
        "kyc_data": extraction.get("kyc_data", {}),
        "vision_response_file": extraction.get("vision_response_file"),
        "error": extraction.get("error"),
        "started_at": extraction.get("started_at"),
        "completed_at": extraction.get("completed_at")
    }


@tool
def get_vision_api_response(document_id: str) -> Dict[str, Any]:
    """
    Get the raw Vision API response for a document.
    
    The raw response is stored separately to keep metadata files small.
    Use this tool when you need bounding boxes or character-level details.
    
    Args:
        document_id: Document ID to get Vision response for
        
    Returns:
        Dictionary with Vision API response or error
    """
    intake_dir = Path(settings.documents_dir) / "intake"
    response_path = intake_dir / f"{document_id}.vision_response.json"
    
    if not response_path.exists():
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Vision response not found: {response_path.name}"
        }
    
    with open(response_path, 'r') as f:
        response = json.load(f)
    
    return {
        "success": True,
        "document_id": document_id,
        "response": response
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
        result = extract_document_data.run(document_id=doc_id)
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
