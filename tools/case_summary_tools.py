"""
Case Summary Tools - Aggregate document data into case-level summaries.

These tools collect document metadata, group by category, extract key fields,
and generate structured case summaries for policy application and reporting.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from crewai.tools import tool
from utilities import settings, logger


@tool("generate_case_summary")
def generate_case_summary_tool(case_id: str) -> Dict[str, Any]:
    """
    Generate comprehensive case summary by aggregating all document metadata.
    
    Groups documents by classification category (id_proof, address_proof, financial_statement)
    and extracts key fields for each category. Performs cross-verification of data consistency.
    
    Args:
        case_id: Case reference ID (e.g., KYC-2026-001)
        
    Returns:
        Dictionary with case_summary structure:
        {
            "id_proof": {
                "documents": ["DOC_123"],
                "verified": true/false,
                "extracted_data": {...}
            },
            "address_proof": {...},
            "financial_statement": {...},
            "verification_status": "complete/incomplete/failed",
            "consistency_checks": {...},
            "generated_at": "timestamp"
        }
    """
    logger.info(f"Generating case summary for {case_id}")
    
    try:
        # Load case metadata
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {
                "success": False,
                "error": f"Case {case_id} not found"
            }
        
        with open(case_metadata_path, 'r') as f:
            case_metadata = json.load(f)
        
        # Get list of document IDs
        document_ids = case_metadata.get('documents', [])
        
        if not document_ids:
            return {
                "success": True,
                "case_summary": {
                    "id_proof": {"documents": [], "verified": False, "extracted_data": {}},
                    "address_proof": {"documents": [], "verified": False, "extracted_data": {}},
                    "financial_statement": {"documents": [], "verified": False, "extracted_data": {}},
                    "verification_status": "incomplete",
                    "message": "No documents in case",
                    "generated_at": datetime.now().isoformat()
                }
            }
        
        # Initialize category structure
        categories = {
            "id_proof": {"documents": [], "verified": False, "extracted_data": {}, "status": []},
            "address_proof": {"documents": [], "verified": False, "extracted_data": {}, "status": []},
            "financial_statement": {"documents": [], "verified": False, "extracted_data": {}, "status": []}
        }
        
        # Collect all document metadata
        all_names = []  # For consistency checking
        all_addresses = []
        
        for doc_id in document_ids:
            # Find document metadata
            doc_metadata = _find_document_metadata(doc_id)
            
            if not doc_metadata:
                logger.warning(f"Metadata not found for document {doc_id}")
                continue
            
            # Skip parent PDF containers
            if doc_metadata.get('processing_status') == 'split':
                continue
            
            # Get classification category
            classification = doc_metadata.get('classification', {})
            doc_type = classification.get('document_type', 'unknown')
            categories_list = classification.get('categories', [])
            
            # Map to our category structure
            category_key = _map_to_category(categories_list, doc_type)
            
            if category_key not in categories:
                logger.warning(f"Unknown category for document {doc_id}: {category_key}")
                continue
            
            # Add document to category
            categories[category_key]["documents"].append(doc_id)
            
            # Get extraction data - check multiple locations
            extraction = doc_metadata.get('extraction', {})
            extraction_status = extraction.get('status')
            
            # KYC data can be in multiple places
            kyc_data = (
                extraction.get('kyc_data') or 
                extraction.get('extracted_fields', {}).get('kyc_data') or
                doc_metadata.get('extraction', {}).get('extracted_fields', {})
            )
            
            categories[category_key]["status"].append(extraction_status)
            
            # Extract key fields based on category
            if category_key == "id_proof":
                key_data = _extract_id_proof_data(kyc_data)
                if key_data.get('name'):
                    all_names.append(key_data['name'])
            elif category_key == "address_proof":
                key_data = _extract_address_proof_data(kyc_data)
                if key_data.get('name'):
                    all_names.append(key_data['name'])
                if key_data.get('address'):
                    all_addresses.append(key_data['address'])
            elif category_key == "financial_statement":
                key_data = _extract_financial_data(kyc_data)
                if key_data.get('name'):
                    all_names.append(key_data['name'])
            
            # Merge extracted data (prefer higher confidence/more complete data)
            _merge_extracted_data(categories[category_key]["extracted_data"], key_data)
        
        # Determine verification status for each category
        for category_key, category_data in categories.items():
            if category_data["documents"]:
                # Verified if at least one document succeeded extraction
                category_data["verified"] = "success" in category_data["status"]
                # Remove status list from final output
                del category_data["status"]
            else:
                del category_data["status"]
        
        # Cross-verification checks
        consistency_checks = {
            "name_consistency": _check_name_consistency(all_names),
            "address_consistency": _check_address_consistency(all_addresses),
            "cross_document_match": True  # Placeholder for more advanced checks
        }
        
        # Overall verification status
        id_verified = categories["id_proof"]["verified"]
        address_verified = categories["address_proof"]["verified"]
        financial_verified = categories["financial_statement"]["verified"]
        
        if id_verified and address_verified:
            verification_status = "complete"
        elif id_verified or address_verified:
            verification_status = "partial"
        else:
            verification_status = "incomplete"
        
        # Build final summary
        case_summary = {
            "id_proof": categories["id_proof"],
            "address_proof": categories["address_proof"],
            "financial_statement": categories["financial_statement"],
            "verification_status": verification_status,
            "consistency_checks": consistency_checks,
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"Case summary generated: {verification_status}, {len(document_ids)} documents")
        
        return {
            "success": True,
            "case_summary": case_summary
        }
        
    except Exception as e:
        logger.error(f"Error generating case summary: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def _find_document_metadata(doc_id: str) -> Optional[Dict[str, Any]]:
    """Find document metadata - documents are stored in intake folder."""
    metadata_path = Path(settings.documents_dir) / "intake" / f"{doc_id}.metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metadata for {doc_id}: {e}")
    
    return None


def _map_to_category(categories_list: List[str], doc_type: str) -> str:
    """Map document type/categories to our summary categories."""
    # Check category list first
    if "identity_proof" in categories_list:
        return "id_proof"
    if "address_proof" in categories_list:
        return "address_proof"
    if "financial_statement" in categories_list:
        return "financial_statement"
    
    # Fallback to doc_type matching
    doc_type_lower = doc_type.lower()
    if any(keyword in doc_type_lower for keyword in ["passport", "license", "id", "voter", "pan", "aadhar"]):
        return "id_proof"
    elif any(keyword in doc_type_lower for keyword in ["utility", "bill", "statement", "address"]):
        return "address_proof"
    elif any(keyword in doc_type_lower for keyword in ["bank", "financial", "account"]):
        return "financial_statement"
    
    return "id_proof"  # Default fallback


def _extract_id_proof_data(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fields for identity proof documents."""
    return {
        "name": fields.get("full_name") or fields.get("name") or fields.get("holder_name"),
        "dob": fields.get("date_of_birth") or fields.get("dob") or fields.get("birth_date"),
        "father_name": fields.get("father_name") or fields.get("fathers_name"),
        "document_number": fields.get("pan_number") or fields.get("document_number") or fields.get("id_number") or fields.get("passport_number"),
        "expiry_date": fields.get("expiry_date") or fields.get("valid_until"),
        "issuing_authority": fields.get("issuing_authority") or fields.get("issued_by")
    }


def _extract_address_proof_data(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fields for address proof documents."""
    return {
        "name": fields.get("name") or fields.get("customer_name") or fields.get("account_holder"),
        "address": fields.get("address") or fields.get("full_address") or fields.get("service_address"),
        "date": fields.get("date") or fields.get("statement_date") or fields.get("bill_date"),
        "issuing_organization": fields.get("issuing_organization") or fields.get("provider") or fields.get("utility_company")
    }


def _extract_financial_data(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fields for financial documents."""
    return {
        "name": fields.get("name") or fields.get("account_holder") or fields.get("customer_name"),
        "account_number": fields.get("account_number") or fields.get("account_no"),
        "statement_date": fields.get("statement_date") or fields.get("date"),
        "balance": fields.get("balance") or fields.get("closing_balance")
    }


def _merge_extracted_data(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """Merge source data into target, preferring non-empty values."""
    for key, value in source.items():
        if value and (not target.get(key) or str(value).strip()):
            target[key] = value


def _check_name_consistency(names: List[str]) -> Dict[str, Any]:
    """Check if names are consistent across documents."""
    if not names:
        return {"status": "no_data", "message": "No names extracted"}
    
    # Simple check: all names should be similar (case-insensitive)
    unique_names = list(set(n.lower().strip() for n in names if n))
    
    if len(unique_names) == 1:
        return {"status": "consistent", "name": names[0]}
    elif len(unique_names) <= 2:
        return {"status": "minor_variance", "names": unique_names, "message": "Minor spelling differences"}
    else:
        return {"status": "inconsistent", "names": unique_names, "message": "Multiple different names found"}


def _check_address_consistency(addresses: List[str]) -> Dict[str, Any]:
    """Check if addresses are consistent across documents."""
    if not addresses:
        return {"status": "no_data", "message": "No addresses extracted"}
    
    unique_addresses = list(set(a.lower().strip() for a in addresses if a))
    
    if len(unique_addresses) == 1:
        return {"status": "consistent", "address": addresses[0]}
    else:
        return {"status": "variance", "addresses": unique_addresses, "message": "Multiple addresses found"}


@tool("update_case_summary")
def update_case_summary_tool(case_id: str, case_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update case metadata with generated summary.
    
    Args:
        case_id: Case reference ID
        case_summary: Generated case summary structure
        
    Returns:
        Success status and message
    """
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {"success": False, "error": f"Case {case_id} not found"}
        
        # Load current metadata
        with open(case_metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Update case_summary
        metadata['case_summary'] = case_summary
        metadata['last_updated'] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(case_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Updated case summary for {case_id}")
        
        return {
            "success": True,
            "message": f"Case summary updated for {case_id}",
            "verification_status": case_summary.get('verification_status')
        }
        
    except Exception as e:
        logger.error(f"Error updating case summary: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ==================== LLM-BASED CASE SUMMARY ====================

def _collect_all_kyc_data(case_id: str) -> Dict[str, Any]:
    """
    Collect all KYC data from documents linked to a case.
    
    Returns aggregated data from all documents for LLM summarization.
    """
    case_dir = Path(settings.documents_dir) / "cases" / case_id
    case_metadata_path = case_dir / "case_metadata.json"
    
    if not case_metadata_path.exists():
        return {"error": f"Case {case_id} not found"}
    
    with open(case_metadata_path, 'r') as f:
        case_metadata = json.load(f)
    
    document_ids = case_metadata.get('documents', [])
    
    all_documents = []
    
    for doc_id in document_ids:
        doc_metadata = _find_document_metadata(doc_id)
        
        if not doc_metadata:
            continue
        
        # Skip parent PDF containers
        if doc_metadata.get('processing_status') == 'split':
            continue
        
        extraction = doc_metadata.get('extraction', {})
        classification = doc_metadata.get('classification', {})
        
        # Get KYC data
        kyc_data = extraction.get('kyc_data', {})
        raw_text = extraction.get('raw_text', '')
        
        doc_info = {
            "document_id": doc_id,
            "document_type": classification.get('document_type', 'unknown'),
            "kyc_data": kyc_data,
            "raw_text": raw_text[:2000] if raw_text else ""  # Limit raw text
        }
        
        all_documents.append(doc_info)
    
    return {
        "case_id": case_id,
        "case_description": case_metadata.get('description', ''),
        "document_count": len(all_documents),
        "documents": all_documents
    }


def _summarize_case_with_llm(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use LLM to generate comprehensive case-level KYC summary.
    
    Identifies:
    - Primary entity (company or person)
    - All persons and companies involved
    - Entity relationships
    - KYC verification status
    """
    try:
        from utilities.llm_factory import create_llm
    except ImportError:
        logger.warning("LLM factory not available")
        return {"error": "LLM not available"}
    
    # Build document summaries for the prompt
    doc_summaries = []
    for doc in case_data.get('documents', []):
        doc_summary = {
            "document_id": doc.get('document_id'),
            "document_type": doc.get('document_type'),
            "kyc_data": doc.get('kyc_data', {})
        }
        doc_summaries.append(doc_summary)
    
    prompt = f"""You are a KYC analyst. Analyze the following extracted KYC data from multiple documents and provide a comprehensive case-level summary.

CASE ID: {case_data.get('case_id')}
CASE DESCRIPTION: {case_data.get('case_description', 'Not provided')}

DOCUMENT DATA:
{json.dumps(doc_summaries, indent=2)}

INSTRUCTIONS:
1. Identify the PRIMARY ENTITY for which KYC is being performed:
   - This is the main company or person whose identity is being verified
   - Look for company names in bank KYC forms, director details, etc.
   - If no company is mentioned, the primary entity is a person

2. DISTINGUISH between PRIMARY ENTITY and KYC AGENCIES:
   - PRIMARY ENTITY: The company/person being verified (e.g., "ABC Pvt Ltd")
   - KYC AGENCIES: Organizations that ISSUE identity documents, NOT the subject of KYC:
     * Government bodies: Income Tax Department, UIDAI, Passport Office, RTO, Election Commission, Govt of India, Republic of India, etc.
     * Banks: Any bank issuing statements (XYZ Bank, SBI, HDFC, etc.)
     * Utility companies: Electricity boards, telecom companies (Reliance Electric, Airtel, etc.)
     * Other issuers: Amazon, Flipkart (for delivery address proofs), etc.
   - Do NOT list KYC agencies as "companies" - put them in "kyc_agencies" array

3. List ALL PERSONS found with their roles

4. Identify RELATIONSHIPS between entities

5. Consolidate KYC data for each entity

6. Identify any MISSING or INCOMPLETE information

Return ONLY a valid JSON object (no markdown):

{{
  "primary_entity": {{
    "entity_type": "company" or "person",
    "name": "Name of primary entity being KYC'd",
    "description": "Brief description"
  }},
  "companies": [
    {{
      "name": "Company name (ONLY include primary entity and associated companies, NOT document issuers)",
      "cin": "CIN if available",
      "registered_address": "Address",
      "date_of_incorporation": "Date",
      "paid_up_capital": "Amount",
      "gstin": "GST if available",
      "business_type": "Type of business"
    }}
  ],
  "kyc_agencies": [
    {{
      "name": "Agency name (government departments, banks, utilities that ISSUE documents)",
      "agency_type": "government/bank/utility/other",
      "documents_issued": ["PAN Card", "Aadhaar", "Bank Statement", "Utility Bill", etc.]
    }}
  ],
  "persons": [
    {{
      "name": "Person name",
      "role": "director/shareholder/account_holder/etc",
      "associated_company": "Company name if applicable",
      "pan_number": "PAN",
      "aadhar_number": "Aadhaar",
      "date_of_birth": "DOB",
      "address": "Address",
      "mobile": "Phone",
      "email": "Email"
    }}
  ],
  "relationships": [
    {{
      "person": "Person name",
      "relationship": "is Director of / is Shareholder of / is Account Holder of",
      "entity": "Company or Account name"
    }}
  ],
  "kyc_verification": {{
    "identity_verified": true/false,
    "address_verified": true/false,
    "company_verified": true/false,
    "missing_documents": ["List of missing document types"],
    "missing_information": ["List of missing data points"]
  }},
  "summary": "Brief narrative summary of the KYC case"
}}

JSON OUTPUT:"""

    try:
        llm = create_llm()
        response = llm.invoke(prompt)
        
        # Extract content
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        # Clean up response
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        result = json.loads(response_text)
        
        logger.info(
            f"LLM case summary: primary={result.get('primary_entity', {}).get('entity_type')}, "
            f"persons={len(result.get('persons', []))}, companies={len(result.get('companies', []))}"
        )
        
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM case summary: {e}")
        return {"error": f"JSON parse error: {str(e)}"}
        
    except Exception as e:
        logger.error(f"LLM case summary failed: {e}")
        return {"error": str(e)}


@tool("generate_comprehensive_case_summary")
def generate_comprehensive_case_summary_tool(case_id: str) -> Dict[str, Any]:
    """
    Generate a comprehensive KYC case summary using LLM.
    
    Collects all KYC data from case documents and uses LLM to:
    - Identify primary entity (company or person)
    - List all persons and companies
    - Map entity relationships
    - Assess KYC verification completeness
    
    Args:
        case_id: Case reference ID (e.g., KYC_2026_001)
        
    Returns:
        Comprehensive case summary with entities and relationships
    """
    logger.info(f"Generating comprehensive case summary for {case_id}")
    
    try:
        # Collect all KYC data from documents
        case_data = _collect_all_kyc_data(case_id)
        
        if "error" in case_data:
            return {"success": False, "error": case_data["error"]}
        
        if case_data.get('document_count', 0) == 0:
            return {
                "success": False,
                "error": "No documents found in case"
            }
        
        # Use LLM to summarize
        llm_summary = _summarize_case_with_llm(case_data)
        
        if "error" in llm_summary:
            return {"success": False, "error": llm_summary["error"]}
        
        # Add metadata
        llm_summary["generated_at"] = datetime.now().isoformat()
        llm_summary["document_count"] = case_data.get('document_count', 0)
        llm_summary["case_id"] = case_id
        
        # Update case metadata with new summary
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        with open(case_metadata_path, 'r') as f:
            metadata = json.load(f)
        
        metadata['case_summary'] = llm_summary
        metadata['last_updated'] = datetime.now().isoformat()
        
        with open(case_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Comprehensive case summary saved for {case_id}")
        
        return {
            "success": True,
            "case_summary": llm_summary
        }
        
    except Exception as e:
        logger.error(f"Error generating comprehensive case summary: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
