"""
Case Tools - CRUD operations for case management.

This module consolidates all case-related operations:
- Create: create_case
- Read: get_case, list_cases, list_documents_by_case
- Update: update_case, link_document_to_case, unlink_document_from_case
- Delete: delete_case
- Summary: generate_case_summary, generate_comprehensive_case_summary

Cases are stored in documents/cases/{case_id}/ with case_metadata.json.
Documents are linked to cases via document IDs (many-to-many relationship).
"""
from crewai.tools import tool
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime

from utilities import settings, logger


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _find_document_metadata(doc_id: str) -> Optional[Dict[str, Any]]:
    """Find document metadata - documents are stored in intake folder."""
    metadata_path = Path(settings.documents_dir) / "intake" / f"{doc_id}.metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metadata for {doc_id}: {e}")
    return None


def _map_to_category(categories_list: List[str], doc_type: str) -> str:
    """Map document type/categories to summary categories."""
    if "identity_proof" in categories_list:
        return "id_proof"
    if "address_proof" in categories_list:
        return "address_proof"
    if "financial_statement" in categories_list:
        return "financial_statement"
    
    doc_type_lower = doc_type.lower()
    if any(kw in doc_type_lower for kw in ["passport", "license", "id", "voter", "pan", "aadhar"]):
        return "id_proof"
    elif any(kw in doc_type_lower for kw in ["utility", "bill", "statement", "address"]):
        return "address_proof"
    elif any(kw in doc_type_lower for kw in ["bank", "financial", "account"]):
        return "financial_statement"
    
    return "id_proof"


def _extract_id_proof_data(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fields for identity proof documents."""
    return {
        "name": fields.get("full_name") or fields.get("name") or fields.get("holder_name"),
        "dob": fields.get("date_of_birth") or fields.get("dob") or fields.get("birth_date"),
        "father_name": fields.get("father_name") or fields.get("fathers_name"),
        "document_number": (fields.get("pan_number") or fields.get("document_number") or 
                           fields.get("id_number") or fields.get("passport_number")),
        "expiry_date": fields.get("expiry_date") or fields.get("valid_until"),
        "issuing_authority": fields.get("issuing_authority") or fields.get("issued_by")
    }


def _extract_address_proof_data(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fields for address proof documents."""
    return {
        "name": fields.get("name") or fields.get("customer_name") or fields.get("account_holder"),
        "address": fields.get("address") or fields.get("full_address") or fields.get("service_address"),
        "date": fields.get("date") or fields.get("statement_date") or fields.get("bill_date"),
        "issuing_organization": (fields.get("issuing_organization") or fields.get("provider") or 
                                 fields.get("utility_company"))
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


# =============================================================================
# CREATE OPERATIONS
# =============================================================================

@tool("Create Case")
def create_case_tool(case_id: str, description: str = "", case_type: str = "kyc") -> Dict[str, Any]:
    """
    Create a new case.
    
    Args:
        case_id: Unique case identifier (e.g., KYC_2026_001)
        description: Optional case description
        case_type: Type of case (kyc, aml, etc.)
        
    Returns:
        Dictionary with:
        - success: Boolean
        - case_id: The created case ID
        - case_dir: Path to case directory
    """
    logger.info(f"Creating case: {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        
        if case_dir.exists():
            return {
                "success": False,
                "case_id": case_id,
                "error": f"Case {case_id} already exists"
            }
        
        case_dir.mkdir(parents=True, exist_ok=True)
        
        # Create case metadata
        case_metadata = {
            "case_id": case_id,
            "description": description,
            "case_type": case_type,
            "status": "active",
            "workflow_stage": "intake",
            "documents": [],
            "created_date": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "case_summary": None
        }
        
        metadata_path = case_dir / "case_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(case_metadata, f, indent=2)
        
        logger.info(f"Created case: {case_id}")
        
        return {
            "success": True,
            "case_id": case_id,
            "case_dir": str(case_dir),
            "message": f"Case {case_id} created successfully"
        }
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e)
        }


# =============================================================================
# READ OPERATIONS
# =============================================================================

@tool("Get Case")
def get_case_tool(case_id: str) -> Dict[str, Any]:
    """
    Get case details by case ID.
    
    Args:
        case_id: The case identifier
        
    Returns:
        Dictionary with case metadata
    """
    logger.info(f"Getting case: {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        metadata_path = case_dir / "case_metadata.json"
        
        if not metadata_path.exists():
            return {
                "success": False,
                "case_id": case_id,
                "error": f"Case {case_id} not found"
            }
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        return {
            "success": True,
            "case_id": case_id,
            "metadata": case_metadata
        }
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e)
        }


@tool("List Cases")
def list_cases_tool(status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """
    List all cases with optional status filter.
    
    Args:
        status: Optional status filter (active, closed, pending)
        limit: Maximum number of cases to return
        
    Returns:
        Dictionary with list of cases
    """
    logger.info(f"Listing cases (status={status}, limit={limit})")
    
    try:
        cases_dir = Path(settings.documents_dir) / "cases"
        
        if not cases_dir.exists():
            return {
                "success": True,
                "cases": [],
                "total": 0
            }
        
        cases = []
        for case_dir in sorted(cases_dir.iterdir(), reverse=True):
            if not case_dir.is_dir():
                continue
            
            metadata_path = case_dir / "case_metadata.json"
            if not metadata_path.exists():
                continue
            
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    case_metadata = json.load(f)
                
                # Apply status filter
                if status and case_metadata.get('status') != status:
                    continue
                
                cases.append({
                    "case_id": case_metadata.get('case_id'),
                    "description": case_metadata.get('description', ''),
                    "status": case_metadata.get('status', 'unknown'),
                    "workflow_stage": case_metadata.get('workflow_stage', 'unknown'),
                    "document_count": len(case_metadata.get('documents', [])),
                    "created_date": case_metadata.get('created_date'),
                    "last_updated": case_metadata.get('last_updated')
                })
                
                if len(cases) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Error reading case metadata for {case_dir.name}: {e}")
                continue
        
        return {
            "success": True,
            "cases": cases,
            "total": len(cases)
        }
    except Exception as e:
        logger.error(f"Failed to list cases: {e}")
        return {
            "success": False,
            "error": str(e),
            "cases": [],
            "total": 0
        }


@tool("List Documents by Case")
def list_documents_by_case_tool(case_id: str) -> Dict[str, Any]:
    """
    List all documents linked to a specific case.
    
    Args:
        case_id: Case identifier
        
    Returns:
        Dictionary with:
        - success: Boolean
        - case_id: Case ID
        - documents: List of documents linked to this case
        - total: Total count
    """
    logger.info(f"Listing documents for case: {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        metadata_path = case_dir / "case_metadata.json"
        
        if not metadata_path.exists():
            return {
                "success": False,
                "case_id": case_id,
                "error": f"Case {case_id} not found",
                "documents": [],
                "total": 0
            }
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        document_ids = case_metadata.get('documents', [])
        documents = []
        
        for doc_id in document_ids:
            doc_metadata = _find_document_metadata(doc_id)
            if doc_metadata:
                documents.append({
                    "document_id": doc_id,
                    "original_filename": doc_metadata.get('original_filename'),
                    "classification": doc_metadata.get('classification', {}),
                    "extraction": doc_metadata.get('extraction', {}),
                    "stage": doc_metadata.get('stage', 'intake')
                })
            else:
                documents.append({
                    "document_id": doc_id,
                    "original_filename": "unknown",
                    "error": "Metadata not found"
                })
        
        return {
            "success": True,
            "case_id": case_id,
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        logger.error(f"Failed to list documents for case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e),
            "documents": [],
            "total": 0
        }


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

@tool("Update Case")
def update_case_tool(case_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update case metadata.
    
    Args:
        case_id: The case identifier
        updates: Dictionary of fields to update
        
    Returns:
        Dictionary with success status
    """
    logger.info(f"Updating case: {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        metadata_path = case_dir / "case_metadata.json"
        
        if not metadata_path.exists():
            return {
                "success": False,
                "case_id": case_id,
                "error": f"Case {case_id} not found"
            }
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        # Apply updates (don't allow overwriting core fields)
        protected_fields = ['case_id', 'created_date', 'documents']
        for key, value in updates.items():
            if key not in protected_fields:
                case_metadata[key] = value
        
        case_metadata['last_updated'] = datetime.now().isoformat()
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(case_metadata, f, indent=2)
        
        return {
            "success": True,
            "case_id": case_id,
            "message": "Case updated successfully",
            "metadata": case_metadata
        }
    except Exception as e:
        logger.error(f"Failed to update case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e)
        }


@tool("Link Document to Case")
def link_document_to_case_tool(document_id: str, case_id: str) -> Dict[str, Any]:
    """
    Link an existing document to a case.
    
    Supports many-to-many relationships (one document can be linked to multiple cases).
    Only updates case metadata - the case holds document references.
    
    Args:
        document_id: Globally unique document ID (e.g., DOC_20260127_143022_A3F8B)
        case_id: Case identifier (e.g., KYC_2026_001)
        
    Returns:
        Dictionary with:
        - success: Boolean indicating success
        - document_id: Document ID
        - case_id: Case ID
        - message: Status message
    """
    logger.info(f"Linking document {document_id} to case {case_id}")
    
    try:
        # Verify document exists
        stages = ["intake", "classification", "extraction", "processed"]
        document_found = False
        current_stage = None
        
        for stage in stages:
            potential_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
            if potential_path.exists():
                document_found = True
                current_stage = stage
                break
        
        if not document_found:
            return {
                "success": False,
                "document_id": document_id,
                "case_id": case_id,
                "error": f"Document {document_id} not found in any stage"
            }
        
        # Update case metadata
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {
                "success": False,
                "document_id": document_id,
                "case_id": case_id,
                "error": f"Case {case_id} not found"
            }
        
        with open(case_metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        if "documents" not in case_metadata:
            case_metadata["documents"] = []
        
        if document_id not in case_metadata["documents"]:
            case_metadata["documents"].append(document_id)
            case_metadata["last_updated"] = datetime.now().isoformat()
            
            with open(case_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(case_metadata, f, indent=2)
            
            logger.info(f"Linked document {document_id} to case {case_id}")
            
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "stage": current_stage,
                "total_documents": len(case_metadata["documents"]),
                "message": f"Document successfully linked to case {case_id}"
            }
        else:
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "stage": current_stage,
                "total_documents": len(case_metadata["documents"]),
                "message": f"Document already linked to case {case_id}"
            }
    except Exception as e:
        logger.error(f"Failed to link document to case: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "case_id": case_id,
            "error": str(e)
        }


@tool("Unlink Document from Case")
def unlink_document_from_case_tool(document_id: str, case_id: str) -> Dict[str, Any]:
    """
    Unlink a document from a case.
    
    Removes the document reference from the case metadata.
    Does not delete the document itself.
    
    Args:
        document_id: Document ID to unlink
        case_id: Case identifier
        
    Returns:
        Dictionary with success status
    """
    logger.info(f"Unlinking document {document_id} from case {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {
                "success": False,
                "document_id": document_id,
                "case_id": case_id,
                "error": f"Case {case_id} not found"
            }
        
        with open(case_metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        documents = case_metadata.get("documents", [])
        
        if document_id in documents:
            documents.remove(document_id)
            case_metadata["documents"] = documents
            case_metadata["last_updated"] = datetime.now().isoformat()
            
            with open(case_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(case_metadata, f, indent=2)
            
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "message": f"Document unlinked from case {case_id}"
            }
        else:
            return {
                "success": True,
                "document_id": document_id,
                "case_id": case_id,
                "message": f"Document was not linked to case {case_id}"
            }
    except Exception as e:
        logger.error(f"Failed to unlink document from case: {e}")
        return {
            "success": False,
            "document_id": document_id,
            "case_id": case_id,
            "error": str(e)
        }


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

@tool("Delete Case")
def delete_case_tool(case_id: str, force: bool = False) -> Dict[str, Any]:
    """
    Delete a case.
    
    Args:
        case_id: The case identifier
        force: If True, delete even if case has linked documents
        
    Returns:
        Dictionary with success status
    """
    logger.info(f"Deleting case: {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        
        if not case_dir.exists():
            return {
                "success": False,
                "case_id": case_id,
                "error": f"Case {case_id} not found"
            }
        
        # Check for linked documents
        metadata_path = case_dir / "case_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                case_metadata = json.load(f)
            
            documents = case_metadata.get('documents', [])
            if documents and not force:
                return {
                    "success": False,
                    "case_id": case_id,
                    "error": f"Case has {len(documents)} linked documents. Use force=True to delete anyway."
                }
        
        # Delete the case directory
        import shutil
        shutil.rmtree(case_dir)
        
        logger.info(f"Deleted case: {case_id}")
        
        return {
            "success": True,
            "case_id": case_id,
            "message": f"Case {case_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"Failed to delete case: {e}")
        return {
            "success": False,
            "case_id": case_id,
            "error": str(e)
        }


# =============================================================================
# SUMMARY OPERATIONS
# =============================================================================

@tool("Generate Case Summary")
def generate_case_summary_tool(case_id: str) -> Dict[str, Any]:
    """
    Generate comprehensive case summary by aggregating all document metadata.
    
    Groups documents by classification category (id_proof, address_proof, financial_statement)
    and extracts key fields for each category. Performs cross-verification of data consistency.
    
    Args:
        case_id: Case reference ID (e.g., KYC-2026-001)
        
    Returns:
        Dictionary with case_summary structure
    """
    logger.info(f"Generating case summary for {case_id}")
    
    try:
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {
                "success": False,
                "error": f"Case {case_id} not found"
            }
        
        with open(case_metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
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
        
        all_names = []
        all_addresses = []
        
        for doc_id in document_ids:
            doc_metadata = _find_document_metadata(doc_id)
            
            if not doc_metadata:
                continue
            
            # Skip parent PDF containers
            if doc_metadata.get('processing_status') == 'split':
                continue
            
            classification = doc_metadata.get('classification', {})
            doc_type = classification.get('document_type', 'unknown')
            categories_list = classification.get('categories', [])
            
            category_key = _map_to_category(categories_list, doc_type)
            
            if category_key not in categories:
                continue
            
            categories[category_key]["documents"].append(doc_id)
            
            extraction = doc_metadata.get('extraction', {})
            extraction_status = extraction.get('status')
            
            kyc_data = (
                extraction.get('kyc_data') or 
                extraction.get('extracted_fields', {}).get('kyc_data') or
                doc_metadata.get('extraction', {}).get('extracted_fields', {})
            )
            
            categories[category_key]["status"].append(extraction_status)
            
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
            
            _merge_extracted_data(categories[category_key]["extracted_data"], key_data)
        
        # Determine verification status
        for category_key, category_data in categories.items():
            if category_data["documents"]:
                category_data["verified"] = "success" in category_data["status"]
                del category_data["status"]
            else:
                del category_data["status"]
        
        # Cross-verification checks
        consistency_checks = {
            "name_consistency": _check_name_consistency(all_names),
            "address_consistency": _check_address_consistency(all_addresses),
            "cross_document_match": True
        }
        
        # Overall verification status
        id_verified = categories["id_proof"]["verified"]
        address_verified = categories["address_proof"]["verified"]
        
        if id_verified and address_verified:
            verification_status = "complete"
        elif id_verified or address_verified:
            verification_status = "partial"
        else:
            verification_status = "incomplete"
        
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


@tool("Update Case Summary")
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
        
        with open(case_metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        metadata['case_summary'] = case_summary
        metadata['last_updated'] = datetime.now().isoformat()
        
        with open(case_metadata_path, 'w', encoding='utf-8') as f:
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


@tool("Generate Comprehensive Case Summary")
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
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        case_metadata_path = case_dir / "case_metadata.json"
        
        if not case_metadata_path.exists():
            return {"success": False, "error": f"Case {case_id} not found"}
        
        with open(case_metadata_path, 'r', encoding='utf-8') as f:
            case_metadata = json.load(f)
        
        document_ids = case_metadata.get('documents', [])
        
        if not document_ids:
            return {
                "success": False,
                "error": "No documents found in case"
            }
        
        # Collect all document data
        all_documents = []
        for doc_id in document_ids:
            doc_metadata = _find_document_metadata(doc_id)
            if not doc_metadata:
                continue
            if doc_metadata.get('processing_status') == 'split':
                continue
            
            extraction = doc_metadata.get('extraction', {})
            classification = doc_metadata.get('classification', {})
            
            doc_info = {
                "document_id": doc_id,
                "document_type": classification.get('document_type', 'unknown'),
                "kyc_data": extraction.get('kyc_data', {}),
                "raw_text": extraction.get('raw_text', '')[:2000]
            }
            all_documents.append(doc_info)
        
        case_data = {
            "case_id": case_id,
            "case_description": case_metadata.get('description', ''),
            "document_count": len(all_documents),
            "documents": all_documents
        }
        
        # Use LLM to summarize
        try:
            from utilities.llm_factory import create_llm
            llm = create_llm()
            
            doc_summaries = [
                {
                    "document_id": doc.get('document_id'),
                    "document_type": doc.get('document_type'),
                    "kyc_data": doc.get('kyc_data', {})
                }
                for doc in all_documents
            ]
            
            prompt = f"""Analyze the following KYC data and provide a case summary.

CASE ID: {case_id}
DOCUMENT DATA:
{json.dumps(doc_summaries, indent=2)}

Return a JSON object with:
- primary_entity: {{entity_type, name, description}}
- persons: [{{name, role, pan_number, etc.}}]
- companies: [{{name, cin, registered_address, etc.}}]
- kyc_verification: {{identity_verified, address_verified, missing_documents}}
- summary: Brief narrative 
- discrepancies: List any inconsistencies or issues found across documents
- recommendations: Suggested actions based on KYC analysis

JSON OUTPUT:"""
            
            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            llm_summary = json.loads(response_text.strip())
            
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            llm_summary = {
                "primary_entity": {"entity_type": "unknown", "name": "Unknown"},
                "persons": [],
                "companies": [],
                "kyc_verification": {"identity_verified": False, "address_verified": False},
                "summary": "LLM summarization failed",
                "error": str(e)
            }
        
        llm_summary["generated_at"] = datetime.now().isoformat()
        llm_summary["document_count"] = len(all_documents)
        llm_summary["case_id"] = case_id
        
        # Update case metadata
        case_metadata['case_summary'] = llm_summary
        case_metadata['last_updated'] = datetime.now().isoformat()
        
        with open(case_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(case_metadata, f, indent=2)
        
        return {
            "success": True,
            "case_summary": llm_summary
        }
        
    except Exception as e:
        logger.error(f"Error generating comprehensive case summary: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
