"""
Chat interface tools for LLM tool calling.
These tools enable the LLM to interact with the KYC-AML system via pipeline agents.

NOTE: These tools use LangChain's @tool decorator (not CrewAI's) because they are
used with LangChain's .bind_tools() in the chat interface, not with CrewAI agents.
"""
from pathlib import Path
from typing import Optional, Dict, Any
import json
import shutil
from datetime import datetime
from langchain_core.tools import tool  # LangChain tool for bind_tools() compatibility
from utilities import settings, logger
from case_metadata_manager import StagedCaseMetadataManager


def fmt_id(doc_id: str) -> str:
    """Format document/case ID for Markdown display using backticks to prevent underscore escaping."""
    return f"`{doc_id}`" if doc_id else "unknown"


def create_chat_tools(chat_interface):
    """
    Create chat tools with access to the chat interface instance.
    
    Args:
        chat_interface: The ChatInterface instance that provides context
        
    Returns:
        List of LangChain tools
    """
    
    @tool
    def list_all_cases() -> str:
        """List all available KYC/AML cases in the system.
        
        Returns:
            A formatted string with all cases and their document counts.
        """
        cases_dir = Path(settings.documents_dir) / "cases"
        
        if not cases_dir.exists():
            return "📋 No cases found. Create a new case by providing a case reference (e.g., KYC-2024-001)"
        
        case_dirs = sorted([d for d in cases_dir.iterdir() if d.is_dir()])
        
        if not case_dirs:
            return "📋 No cases found. Create a new case by providing a case reference (e.g., KYC-2024-001)"
        
        msg = f"\n📋 Available Cases ({len(case_dirs)}):\n\n"
        
        for case_dir in case_dirs:
            doc_count = len(list(case_dir.glob("*.pdf"))) + len(list(case_dir.glob("*.jpg")))
            current = "← Current" if case_dir.name == chat_interface.case_reference else ""
            msg += f"  • {case_dir.name}: {doc_count} document(s) {current}\n"
        
        return msg
    
    @tool
    def list_all_documents(limit: int = 10, filter_by: Optional[str] = None) -> str:
        """List all documents in the system from the intake folder.
        
        Shows recent documents with their classification and processing status.
        Documents are sorted by most recent first.
        
        Args:
            limit: Maximum number of documents to show (default: 10)
            filter_by: Optional filter - 'completed', 'pending', 'failed', or document type like 'pan', 'passport'
            
        Returns:
            Formatted list of documents with status and metadata.
        """
        intake_dir = Path(settings.documents_dir) / "intake"
        
        if not intake_dir.exists():
            return "📄 No documents found. Process some documents first."
        
        # Get all metadata files
        metadata_files = sorted(
            intake_dir.glob("*.metadata.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not metadata_files:
            return "📄 No documents found in intake."
        
        # Load and filter documents
        documents = []
        for meta_file in metadata_files:
            try:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                
                # Apply filter if specified
                if filter_by:
                    filter_lower = filter_by.lower()
                    queue_status = metadata.get('queue', {}).get('status', '')
                    doc_type = metadata.get('classification', {}).get('document_type', '')
                    
                    # Check if filter matches status or document type
                    if filter_lower not in [queue_status.lower(), doc_type.lower()]:
                        continue
                
                documents.append(metadata)
                
                if len(documents) >= limit:
                    break
            except:
                continue
        
        if not documents:
            filter_msg = f" matching '{filter_by}'" if filter_by else ""
            return f"📄 No documents found{filter_msg}."
        
        msg = f"\n📄 Documents ({len(documents)} of {len(metadata_files)}):\n"
        msg += "=" * 60 + "\n\n"
        
        for doc in documents:
            doc_id = doc.get('document_id', 'unknown')
            doc_type = doc.get('classification', {}).get('document_type', 'unclassified')
            queue_status = doc.get('queue', {}).get('status', 'unknown')
            class_status = doc.get('classification', {}).get('status', 'pending')
            extract_status = doc.get('extraction', {}).get('status', 'pending')
            linked_cases = doc.get('linked_cases', [])
            confidence = doc.get('classification', {}).get('confidence')
            
            # Status emoji
            if queue_status == "completed":
                status_emoji = "✅"
            elif queue_status == "pending":
                status_emoji = "⏳"
            elif queue_status == "failed":
                status_emoji = "❌"
            else:
                status_emoji = "❓"
            
            msg += f"  {status_emoji} {doc_id}\n"
            msg += f"     📋 Type: {doc_type}"
            if confidence:
                msg += f" ({confidence:.0%})"
            msg += "\n"
            msg += f"     ⚙️  Class: {class_status} | Extract: {extract_status}\n"
            
            if linked_cases:
                msg += f"     📁 Linked to: {', '.join(linked_cases)}\n"
            msg += "\n"
        
        msg += f"💡 Use 'link_document_to_case' to link a document to a case\n"
        return msg
    
    @tool
    def get_current_status() -> str:
        """Get the current system status including active case and document counts.
        
        Returns:
            A formatted string with system status information.
        """
        msg = "\n📊 Status:\n\n"
        msg += f"  • Case: {chat_interface.case_reference or 'Not set'}\n"
        msg += f"  • CrewAI: {'✅ Ready' if chat_interface.crew else '❌ Not initialized'}\n"
        msg += f"  • LLM: {'✅ Connected' if chat_interface.llm else '❌ Not connected'}\n"
        
        if chat_interface.case_reference:
            case_dir = Path(settings.documents_dir) / "cases" / chat_interface.case_reference
            if case_dir.exists():
                doc_count = len(list(case_dir.glob("*.*")))
                msg += f"  • Documents: {doc_count}\n"
        
        return msg
    
    @tool
    def switch_case(case_reference: str) -> str:
        """Switch to a different case or create a new one.
        
        Args:
            case_reference: The case reference ID (e.g., KYC-2024-001)
            
        Returns:
            Confirmation message with case details.
        """
        return chat_interface.set_case_reference(case_reference)
    
    @tool
    def get_case_details(case_reference: str) -> str:
        """Get detailed information about a specific case including linked documents.
        
        Args:
            case_reference: The case reference ID (e.g., KYC-2024-001)
            
        Returns:
            Detailed case information including linked documents with their types.
        """
        case_dir = Path(settings.documents_dir) / "cases" / case_reference
        
        if not case_dir.exists():
            return f"❌ Case {case_reference} not found."
        
        # Load case metadata to get linked documents
        metadata_file = case_dir / "case_metadata.json"
        if not metadata_file.exists():
            return f"❌ Case metadata not found for {case_reference}."
        
        with open(metadata_file, 'r') as f:
            case_meta = json.load(f)
        
        document_ids = case_meta.get('documents', [])
        created = case_meta.get('created_date', 'N/A')[:10]
        status = case_meta.get('status', 'unknown')
        workflow = case_meta.get('workflow_stage', 'unknown')
        
        msg = f"\n📁 Case: {fmt_id(case_reference)}\n\n"
        msg += f"  📅 Created: {created}\n"
        msg += f"  🏷️  Status: {status}\n"
        msg += f"  🔄 Workflow: {workflow.replace('_', ' ').title()}\n"
        msg += f"  📄 Documents: {len(document_ids)}\n\n"
        
        if document_ids:
            msg += "  **Linked Documents:**\n"
            intake_dir = Path(settings.documents_dir) / "intake"
            
            for doc_id in document_ids:
                # Get document metadata from intake
                doc_meta_file = intake_dir / f"{doc_id}.metadata.json"
                if doc_meta_file.exists():
                    try:
                        with open(doc_meta_file, 'r') as f:
                            doc_meta = json.load(f)
                        doc_type = doc_meta.get('classification', {}).get('document_type', 'unclassified')
                        conf = doc_meta.get('classification', {}).get('confidence', 0)
                        msg += f"    - {fmt_id(doc_id)}: {doc_type.upper()} ({conf:.0%})\n"
                    except:
                        msg += f"    - {fmt_id(doc_id)}: (metadata error)\n"
                else:
                    msg += f"    - {fmt_id(doc_id)}: (no metadata)\n"
        else:
            msg += "  No documents linked to this case yet.\n"
        
        # Show case summary if available
        case_summary = case_meta.get('case_summary', {})
        if case_summary:
            primary = case_summary.get('primary_entity', {})
            if primary:
                msg += f"\n  **Primary Entity:** {primary.get('name', 'Unknown')} ({primary.get('entity_type', 'unknown')})\n"
            
            persons = case_summary.get('persons', [])
            if persons:
                msg += f"\n  **Identified Persons:** {len(persons)}\n"
                for person in persons[:3]:
                    msg += f"    - {person.get('name', 'Unknown')}\n"
                if len(persons) > 3:
                    msg += f"    ... and {len(persons) - 3} more\n"
        
        return msg
    
    @tool
    def get_case_status_with_metadata(case_reference: Optional[str] = None) -> str:
        """Get comprehensive case status including processing results and metadata.
        
        This tool reads case_metadata.json and individual document metadata to provide
        a complete view of case processing status, classification results, and extraction data.
        
        Args:
            case_reference: Case ID (optional, uses current case if not provided)
            
        Returns:
            Rich formatted status with workflow stage, document processing details,
            classification results, and extraction summaries.
        """
        # Use current case if not specified
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference or switch to a case first."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        if not case_dir.exists():
            return f"❌ Case {case_ref} not found."
        
        # Load case metadata
        metadata_manager = StagedCaseMetadataManager(case_ref)
        case_metadata = metadata_manager.load_metadata()
        
        # Build comprehensive status report
        msg = f"\n📊 **Case Summary: {fmt_id(case_ref)}**\n"
        msg += "=" * 60 + "\n\n"
        
        # Workflow stage
        workflow_stage = case_metadata.get('workflow_stage', 'unknown')
        status = case_metadata.get('status', 'unknown')
        created = case_metadata.get('created_date', 'N/A')[:10] if case_metadata.get('created_date') else 'N/A'
        
        msg += f"🔄 Workflow Stage: {workflow_stage.replace('_', ' ').title()}\n"
        msg += f"📅 Created: {created}\n"
        msg += f"🏷️  Status: {status.upper()}\n\n"
        
        # Document count
        documents = case_metadata.get('documents', [])
        total = len(documents)
        
        msg += f"📄 **Documents:** {total}\n\n"
        
        # Get detailed info for each document from intake
        intake_dir = Path(settings.documents_dir) / "intake"
        doc_types = {}
        all_persons = []
        all_id_numbers = {}
        
        if documents:
            msg += "📋 **Document Details:**\n"
            msg += "-" * 60 + "\n"
            
            for idx, doc_id in enumerate(documents, 1):
                doc_meta_file = intake_dir / f"{doc_id}.metadata.json"
                if doc_meta_file.exists():
                    try:
                        with open(doc_meta_file, 'r') as f:
                            doc_meta = json.load(f)
                        
                        doc_type = doc_meta.get('classification', {}).get('document_type', 'unknown')
                        conf = doc_meta.get('classification', {}).get('confidence', 0)
                        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                        
                        msg += f"{idx}. {fmt_id(doc_id)}\n"
                        msg += f"   Type: {doc_type.upper()} ({conf:.0%})\n"
                        
                        # Get person info
                        entities = doc_meta.get('extraction', {}).get('entities', {})
                        persons = entities.get('persons', [])
                        for person in persons:
                            name = person.get('name', '')
                            if name and name not in [p.get('name') for p in all_persons]:
                                all_persons.append(person)
                            # Collect ID numbers
                            for key in ['pan_number', 'aadhaar_number', 'passport_number', 'dl_number']:
                                if person.get(key):
                                    all_id_numbers[key.replace('_', ' ').title()] = person.get(key)
                        
                    except Exception as e:
                        msg += f"{idx}. {fmt_id(doc_id)}: Error - {e}\n"
                else:
                    msg += f"{idx}. {fmt_id(doc_id)}: Metadata not found\n"
            
            msg += "\n"
        
        # Document type summary
        if doc_types:
            msg += "📊 **Document Types:**\n"
            for dtype, count in sorted(doc_types.items(), key=lambda x: -x[1]):
                msg += f"   • {dtype.upper()}: {count}\n"
            msg += "\n"
        
        # Person summary
        if all_persons:
            msg += f"👥 **Identified Persons:** {len(all_persons)}\n"
            for person in all_persons[:5]:
                name = person.get('name', 'Unknown')
                dob = person.get('date_of_birth', '')
                msg += f"   • {name}"
                if dob:
                    msg += f" (DOB: {dob})"
                msg += "\n"
            if len(all_persons) > 5:
                msg += f"   ... and {len(all_persons) - 5} more\n"
            msg += "\n"
        
        # ID numbers summary
        if all_id_numbers:
            msg += "🆔 **ID Numbers Found:**\n"
            for id_type, id_val in all_id_numbers.items():
                msg += f"   • {id_type}: {id_val}\n"
            msg += "\n"
        
        # Case summary if exists
        case_summary = case_metadata.get('case_summary', {})
        if case_summary:
            primary = case_summary.get('primary_entity', {})
            if primary:
                msg += f"🏢 **Primary Entity:** {primary.get('name', 'Unknown')} ({primary.get('entity_type', 'unknown')})\n\n"
            
            kyc = case_summary.get('kyc_verification', {})
            if kyc:
                identity = "✅" if kyc.get('identity_verified') else "❌"
                address = "✅" if kyc.get('address_verified') else "❌"
                msg += f"✅ **KYC Status:** Identity {identity} | Address {address}\n"
                
                missing = kyc.get('missing_documents', [])
                if missing:
                    msg += f"⚠️  Missing: {', '.join(missing[:3])}\n"
        
        return msg
    
    @tool
    def get_document_details(document_id: str, case_reference: Optional[str] = None) -> str:
        """Get detailed metadata and processing results for a specific document.
        
        This tool retrieves comprehensive information about a document including:
        - Classification results (document type, confidence, reasoning)
        - All extracted fields and values
        - OCR quality and text content
        - Processing timestamps and status
        - File information and location
        
        Args:
            document_id: Document ID (e.g., 'DOC_20260207_130709_4FA11') or filename
            case_reference: Case ID (optional, only needed if using filename)
            
        Returns:
            Detailed document information with all metadata and processing results.
        """
        intake_dir = Path(settings.documents_dir) / "intake"
        metadata = None
        doc_display_name = document_id
        
        # Check if this is a document ID (starts with DOC_)
        if document_id.startswith("DOC_"):
            # Look up directly in intake folder
            metadata_file = intake_dir / f"{document_id}.metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    doc_display_name = document_id
                except Exception as e:
                    return f"❌ Error reading metadata for {fmt_id(document_id)}: {str(e)}"
            else:
                return f"❌ Document {fmt_id(document_id)} not found in intake folder."
        else:
            # Treat as filename - need case reference
            case_ref = case_reference or chat_interface.case_reference
            
            if not case_ref:
                return "⚠️  No case selected. For filename lookup, please specify a case reference or switch to a case first.\n\n💡 Tip: Use document ID (DOC_...) for direct lookup without a case."
            
            case_dir = Path(settings.documents_dir) / "cases" / case_ref
            
            if not case_dir.exists():
                return f"❌ Case {case_ref} not found."
            
            # Find the document file
            doc_path = case_dir / document_id
            if not doc_path.exists():
                # Try to find similar files
                similar_files = [f.name for f in case_dir.glob("*") if document_id.lower() in f.name.lower()]
                if similar_files:
                    return f"❌ Document '{document_id}' not found. Did you mean one of these?\n" + "\n".join(f"  • {f}" for f in similar_files)
                return f"❌ Document '{document_id}' not found in case {case_ref}."
            
            # Load document metadata from case folder
            metadata_file = case_dir / f".{document_id}.metadata.json"
            
            if not metadata_file.exists():
                return f"📄 Document: {document_id}\n⚠️  No metadata found - document may not have been processed yet."
            
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except Exception as e:
                return f"❌ Error reading metadata: {str(e)}"
        
        # Build detailed report
        msg = f"\n📄 Document Details: {fmt_id(doc_display_name)}\n"
        msg += "=" * 70 + "\n\n"
        
        # Basic info
        doc_id = metadata.get('document_id', 'unknown')
        status = metadata.get('status', 'unknown')
        original_filename = metadata.get('original_filename', 'unknown')
        source_path = metadata.get('source_path', '')
        linked_cases = metadata.get('linked_cases', [])
        
        msg += "📋 Basic Information:\n"
        msg += f"  • Document ID: {fmt_id(doc_id)}\n"
        msg += f"  • Original Filename: {original_filename}\n"
        if source_path:
            msg += f"  • Source Path: {source_path}\n"
        msg += f"  • Status: {status.upper()}\n"
        if linked_cases:
            msg += f"  • Linked Cases: {', '.join(f'`{c}`' for c in linked_cases)}\n"
        msg += "\n"
        
        # Classification results
        classification = metadata.get('classification', {})
        if classification:
            msg += "🔍 Classification Results:\n"
            doc_type = classification.get('document_type', 'unknown')
            confidence = classification.get('confidence', 0)
            reasoning = classification.get('reasoning', 'N/A')
            
            confidence_emoji = "✅" if confidence >= 0.8 else "⚠️" if confidence >= 0.5 else "❌"
            msg += f"  • Document Type: {doc_type} {confidence_emoji}\n"
            msg += f"  • Confidence: {confidence:.1%}\n"
            msg += f"  • Reasoning: {reasoning}\n\n"
        
        # Extraction results
        extraction = metadata.get('extraction', {})
        if extraction:
            # Check for entities structure (persons, companies, etc.)
            entities = extraction.get('entities', {})
            
            # Show persons
            persons = entities.get('persons', [])
            if persons:
                msg += "👤 **Persons Found:**\n"
                for person in persons:
                    name = person.get('name', 'Unknown')
                    msg += f"  • {name}\n"
                    for key in ['date_of_birth', 'father_name', 'address', 'pan_number', 'aadhaar_number', 'passport_number', 'dl_number', 'gender', 'mobile', 'email']:
                        if person.get(key):
                            field_name = key.replace('_', ' ').title()
                            msg += f"      {field_name}: {person.get(key)}\n"
                msg += "\n"
            
            # Show companies
            companies = entities.get('companies', [])
            if companies:
                msg += "🏢 **Companies Found:**\n"
                for company in companies:
                    name = company.get('name', 'Unknown')
                    msg += f"  • {name}\n"
                    for key in ['cin', 'registered_address', 'date_of_incorporation', 'gstin']:
                        if company.get(key):
                            field_name = key.replace('_', ' ').title()
                            msg += f"      {field_name}: {company.get(key)}\n"
                msg += "\n"
            
            # Show financial info
            financial = entities.get('financial', [])
            if financial:
                msg += "💰 **Financial Info:**\n"
                for fin in financial:
                    for key, val in fin.items():
                        if val and key not in ['source', 'type']:
                            msg += f"  • {key.replace('_', ' ').title()}: {val}\n"
                msg += "\n"
            
            # Legacy: extracted_data for backward compatibility
            extracted_data = extraction.get('extracted_data', {})
            if extracted_data and not entities:
                msg += "📊 Extracted Data:\n"
                for field, value in extracted_data.items():
                    if value and str(value).strip():
                        field_name = field.replace('_', ' ').title()
                        msg += f"  • {field_name}: {value}\n"
                msg += "\n"
            
            # OCR information
            ocr_text = extraction.get('ocr_text', '')
            if ocr_text:
                text_preview = ocr_text[:200].replace('\n', ' ')
                msg += f"📝 OCR Text Preview:\n"
                msg += f"  {text_preview}{'...' if len(ocr_text) > 200 else ''}\n"
                msg += f"  (Total: {len(ocr_text)} characters)\n\n"
        
        # Processing timestamps
        intake_date = metadata.get('intake_date')
        classification_date = classification.get('classified_at') if classification else None
        extraction_date = extraction.get('extracted_at') if extraction else None
        
        msg += "⏰ Processing Timeline:\n"
        if intake_date:
            msg += f"  • Intake: {intake_date}\n"
        if classification_date:
            msg += f"  • Classification: {classification_date}\n"
        if extraction_date:
            msg += f"  • Extraction: {extraction_date}\n"
        
        if not any([intake_date, classification_date, extraction_date]):
            msg += "  • No timestamps recorded\n"
        
        msg += "\n"
        
        # Errors and warnings
        errors = metadata.get('errors', [])
        warnings = metadata.get('warnings', [])
        
        if errors or warnings:
            if errors:
                msg += "❌ Errors:\n"
                for error in errors:
                    msg += f"  • {error}\n"
            if warnings:
                msg += "⚠️  Warnings:\n"
                for warning in warnings:
                    msg += f"  • {warning}\n"
            msg += "\n"
        
        # Additional metadata
        additional_fields = ['extracted_by', 'classified_by', 'processing_notes']
        additional_info = {k: metadata.get(k) for k in additional_fields if metadata.get(k)}
        
        if additional_info:
            msg += "ℹ️  Additional Information:\n"
            for key, value in additional_info.items():
                field_name = key.replace('_', ' ').title()
                msg += f"  • {field_name}: {value}\n"
        
        return msg
    
    @tool
    def find_document_by_id(document_id: str) -> str:
        """Find a document by its ID across all cases.
        
        This tool searches for a document using its document ID (e.g., DOC_20260206_233526_AD733)
        and returns the case it belongs to along with its details.
        
        Args:
            document_id: The document ID to search for (e.g., DOC_20260206_233526_AD733)
            
        Returns:
            Document location and details, or not found message.
        """
        cases_dir = Path(settings.documents_dir) / "cases"
        
        if not cases_dir.exists():
            return "❌ No cases directory found."
        
        # Search through all cases
        for case_dir in cases_dir.iterdir():
            if not case_dir.is_dir():
                continue
            
            case_ref = case_dir.name
            
            # Check metadata files for matching document ID
            for metadata_file in case_dir.glob(".*metadata.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    doc_id = metadata.get('document_id', '')
                    if doc_id == document_id or document_id in doc_id:
                        # Found the document
                        filename = metadata_file.name.replace('.metadata.json', '').lstrip('.')
                        doc_type = metadata.get('classification', {}).get('document_type', 'unclassified')
                        status = metadata.get('status', 'unknown')
                        
                        msg = f"\n🔍 Document Found!\n"
                        msg += "=" * 60 + "\n\n"
                        msg += f"📄 Document ID: {fmt_id(doc_id)}\n"
                        msg += f"📁 Case: {fmt_id(case_ref)}\n"
                        msg += f"📋 Filename: {filename}\n"
                        msg += f"🏷️  Type: {doc_type}\n"
                        msg += f"📊 Status: {status}\n\n"
                        
                        # Get extraction summary if available
                        extraction = metadata.get('extraction', {})
                        if extraction:
                            fields = extraction.get('fields', {})
                            if fields:
                                msg += f"📝 Extracted Fields: {len(fields)}\n"
                                for key, val in list(fields.items())[:5]:
                                    msg += f"  • {key}: {val}\n"
                                if len(fields) > 5:
                                    msg += f"  ... and {len(fields) - 5} more fields\n"
                        
                        return msg
                        
                except Exception:
                    continue
            
            # Also check case metadata for document list
            case_metadata_file = case_dir / "case_metadata.json"
            if case_metadata_file.exists():
                try:
                    with open(case_metadata_file, 'r') as f:
                        case_meta = json.load(f)
                    
                    documents = case_meta.get('documents', [])
                    if document_id in documents:
                        msg = f"\n🔍 Document Found in Case!\n"
                        msg += "=" * 60 + "\n\n"
                        msg += f"📄 Document ID: {fmt_id(document_id)}\n"
                        msg += f"📁 Case: {fmt_id(case_ref)}\n"
                        msg += f"ℹ️  Document is registered in case metadata.\n"
                        return msg
                except Exception:
                    continue
        
        return f"❌ Document {fmt_id(document_id)} not found in any case."
    
    @tool
    def get_case_documents_with_extracted_data(case_reference: Optional[str] = None) -> str:
        """Get all documents in a case with their extracted data for comparison and analysis.
        
        This tool retrieves comprehensive extracted data from all documents linked to a case,
        including person names, addresses, dates of birth, ID numbers, and other key fields.
        This is useful for:
        - Checking for discrepancies between documents
        - Verifying identity information across multiple documents
        - KYC/AML compliance analysis
        
        Args:
            case_reference: Case ID (optional, uses current case if not provided)
            
        Returns:
            All documents with their extracted data for comparison.
        """
        # Use current case if not specified
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference or switch to a case first."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        if not case_dir.exists():
            return f"❌ Case {case_ref} not found."
        
        # Load case metadata to get linked documents
        case_metadata_file = case_dir / "case_metadata.json"
        if not case_metadata_file.exists():
            return f"❌ Case metadata not found for {case_ref}."
        
        with open(case_metadata_file, 'r') as f:
            case_meta = json.load(f)
        
        document_ids = case_meta.get('documents', [])
        
        if not document_ids:
            return f"📋 No documents linked to case {fmt_id(case_ref)} yet."
        
        # Collect data from each document
        intake_dir = Path(settings.documents_dir) / "intake"
        documents_data = []
        
        msg = f"\n📊 Case {fmt_id(case_ref)} - Document Analysis\n"
        msg += "=" * 70 + "\n\n"
        
        for doc_id in document_ids:
            # Find metadata file in intake
            doc_metadata_file = intake_dir / f"{doc_id}.metadata.json"
            
            if not doc_metadata_file.exists():
                msg += f"⚠️  {fmt_id(doc_id)}: Metadata not found\n\n"
                continue
            
            try:
                with open(doc_metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                doc_type = metadata.get('classification', {}).get('document_type', 'unknown')
                confidence = metadata.get('classification', {}).get('confidence', 0)
                extraction = metadata.get('extraction', {})
                entities = extraction.get('entities', {})
                
                msg += f"📄 **{fmt_id(doc_id)}** - {doc_type.upper()} ({confidence:.0%} conf)\n"
                msg += "-" * 60 + "\n"
                
                # Persons
                persons = entities.get('persons', [])
                if persons:
                    msg += "👤 **Persons:**\n"
                    for person in persons:
                        name = person.get('name', 'Unknown')
                        dob = person.get('date_of_birth', '')
                        gender = person.get('gender', '')
                        father = person.get('father_name', '')
                        
                        msg += f"   - Name: {name}\n"
                        if dob:
                            msg += f"     DOB: {dob}\n"
                        if gender:
                            msg += f"     Gender: {gender}\n"
                        if father:
                            msg += f"     Father: {father}\n"
                
                # Addresses
                addresses = []
                for person in persons:
                    addr = person.get('address', '')
                    if addr and addr not in addresses:
                        addresses.append(addr)
                
                # Also check companies for addresses
                companies = entities.get('companies', [])
                for company in companies:
                    addr = company.get('address', '') or company.get('registered_address', '')
                    if addr and addr not in addresses:
                        addresses.append(addr)
                
                if addresses:
                    msg += "📍 **Addresses:**\n"
                    for addr in addresses:
                        msg += f"   - {addr}\n"
                
                # ID Numbers (PAN, Aadhaar, Passport, DL, etc.)
                id_fields = {}
                for person in persons:
                    for key in ['pan_number', 'aadhaar_number', 'passport_number', 'dl_number', 'license_number', 'id_number']:
                        if person.get(key):
                            id_fields[key.replace('_', ' ').title()] = person.get(key)
                
                if id_fields:
                    msg += "🆔 **ID Numbers:**\n"
                    for key, val in id_fields.items():
                        msg += f"   - {key}: {val}\n"
                
                # Financial info
                financials = entities.get('financial', [])
                if financials:
                    msg += "💰 **Financial:**\n"
                    for fin in financials:
                        for key, val in fin.items():
                            if val and key not in ['source', 'type']:
                                msg += f"   - {key.replace('_', ' ').title()}: {val}\n"
                
                msg += "\n"
                
                # Store for discrepancy analysis
                documents_data.append({
                    'doc_id': doc_id,
                    'doc_type': doc_type,
                    'persons': persons,
                    'addresses': addresses,
                    'id_fields': id_fields
                })
                
            except Exception as e:
                msg += f"❌ {fmt_id(doc_id)}: Error reading - {str(e)}\n\n"
        
        # Add summary and discrepancy hints
        msg += "=" * 70 + "\n"
        msg += f"📊 **Summary:** {len(documents_data)} documents analyzed\n\n"
        
        # Collect all unique names and addresses for quick comparison
        all_names = []
        all_addresses = []
        for doc in documents_data:
            for person in doc.get('persons', []):
                name = person.get('name', '')
                if name and name not in all_names:
                    all_names.append(name)
            for addr in doc.get('addresses', []):
                if addr not in all_addresses:
                    all_addresses.append(addr)
        
        if all_names:
            msg += f"👥 **Unique Names Found:** {len(all_names)}\n"
            for name in all_names[:10]:
                msg += f"   - {name}\n"
            if len(all_names) > 10:
                msg += f"   ... and {len(all_names) - 10} more\n"
        
        if all_addresses:
            msg += f"\n📍 **Unique Addresses Found:** {len(all_addresses)}\n"
            for addr in all_addresses[:5]:
                msg += f"   - {addr[:80]}...\n" if len(addr) > 80 else f"   - {addr}\n"
        
        msg += "\n💡 **Tip:** Look for name spelling variations, address mismatches, or inconsistent dates across documents."
        
        return msg
    
    @tool
    def summarize_case(case_reference: Optional[str] = None, focus: Optional[str] = None) -> str:
        """Generate an intelligent LLM-powered summary of a case with all its documents.
        
        This tool gathers all case data and document extractions, then uses the LLM
        to generate a comprehensive, intelligent summary. The LLM analyzes:
        - All extracted person information across documents
        - Document types and their verification status
        - Potential discrepancies or inconsistencies
        - KYC/AML compliance status
        - Missing documents or information
        
        Args:
            case_reference: Case ID (optional, uses current case if not provided)
            focus: Optional focus area - 'discrepancies', 'persons', 'verification', 'summary'
            
        Returns:
            LLM-generated intelligent summary of the case.
        """
        from langchain_core.messages import HumanMessage
        
        # Use current case if not specified
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference or switch to a case first."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        if not case_dir.exists():
            return f"❌ Case {case_ref} not found."
        
        # Load case metadata
        case_metadata_file = case_dir / "case_metadata.json"
        if not case_metadata_file.exists():
            return f"❌ Case metadata not found for {case_ref}."
        
        with open(case_metadata_file, 'r') as f:
            case_meta = json.load(f)
        
        document_ids = case_meta.get('documents', [])
        
        if not document_ids:
            return f"📋 No documents linked to case {fmt_id(case_ref)} yet. Add documents first."
        
        # Collect all document data
        intake_dir = Path(settings.documents_dir) / "intake"
        documents_data = []
        
        for doc_id in document_ids:
            doc_metadata_file = intake_dir / f"{doc_id}.metadata.json"
            
            if doc_metadata_file.exists():
                try:
                    with open(doc_metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    doc_type = metadata.get('classification', {}).get('document_type', 'unknown')
                    confidence = metadata.get('classification', {}).get('confidence', 0)
                    extraction = metadata.get('extraction', {})
                    entities = extraction.get('entities', {})
                    ocr_text = extraction.get('ocr_text', '')[:500]  # First 500 chars
                    
                    documents_data.append({
                        'document_id': doc_id,
                        'document_type': doc_type,
                        'confidence': f"{confidence:.0%}",
                        'persons': entities.get('persons', []),
                        'companies': entities.get('companies', []),
                        'financial': entities.get('financial', []),
                        'ocr_preview': ocr_text[:200] if ocr_text else ''
                    })
                except Exception as e:
                    documents_data.append({
                        'document_id': doc_id,
                        'error': str(e)
                    })
        
        # Build context for LLM
        case_context = {
            'case_reference': case_ref,
            'created_date': case_meta.get('created_date', 'unknown'),
            'status': case_meta.get('status', 'unknown'),
            'workflow_stage': case_meta.get('workflow_stage', 'unknown'),
            'total_documents': len(document_ids),
            'documents': documents_data,
            'existing_summary': case_meta.get('case_summary', {})
        }
        
        # Build summarization prompt based on focus
        focus_instructions = ""
        if focus == 'discrepancies':
            focus_instructions = """
Focus specifically on finding DISCREPANCIES and INCONSISTENCIES:
- Compare names across all documents - look for spelling variations
- Compare dates of birth - are they consistent?
- Compare addresses - do they match?
- Look for any mismatched ID numbers
- Flag any suspicious patterns"""
        elif focus == 'persons':
            focus_instructions = """
Focus specifically on PERSON IDENTIFICATION:
- List all unique individuals identified
- Their relationship to the case (applicant, director, etc.)
- All ID documents provided for each person
- Verification status for each person"""
        elif focus == 'verification':
            focus_instructions = """
Focus specifically on KYC VERIFICATION STATUS:
- Which identity documents are verified?
- Which address proofs are verified?
- What documents are still missing?
- Overall compliance readiness"""
        else:
            focus_instructions = """
Provide a comprehensive executive summary covering:
- Primary entity and key persons
- Document verification status
- Notable findings or concerns
- Recommended next steps"""
        
        summarization_prompt = f"""You are a KYC/AML compliance analyst. Analyze the following case data and provide an intelligent summary.

CASE DATA:
```json
{json.dumps(case_context, indent=2, default=str)}
```

{focus_instructions}

Provide your analysis in a clear, professional format with:
1. **Case Overview** - Brief description of the case
2. **Key Findings** - Important information discovered
3. **Document Analysis** - Summary of each document type
4. **Identified Persons** - All persons found with their details
5. **Discrepancies/Concerns** - Any issues or inconsistencies found
6. **Verification Status** - What's verified vs pending
7. **Recommendations** - Next steps or missing items

Be specific and reference document IDs when mentioning findings. Use the extracted data to draw meaningful conclusions."""

        # Check if we have access to LLM through chat_interface
        if hasattr(chat_interface, 'llm') and chat_interface.llm:
            try:
                # Use the LLM to generate summary
                response = chat_interface.llm.invoke([HumanMessage(content=summarization_prompt)])
                
                # Extract text from response
                if hasattr(response, 'content'):
                    if isinstance(response.content, list):
                        text_parts = []
                        for block in response.content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text_parts.append(block.get('text', ''))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        return '\n'.join(text_parts)
                    return response.content
                return str(response)
                
            except Exception as e:
                logger.error(f"LLM summarization error: {e}")
                return f"❌ Error generating LLM summary: {str(e)}\n\nFalling back to data dump:\n{json.dumps(case_context, indent=2, default=str)[:2000]}"
        else:
            # Fallback: return structured data for the outer LLM to summarize
            return f"""📊 **Case Data for Analysis: {fmt_id(case_ref)}**

Please summarize the following case data:

```json
{json.dumps(case_context, indent=2, default=str)[:4000]}
```

{focus_instructions}"""
    
    @tool
    def analyze_case_discrepancies(case_reference: Optional[str] = None) -> str:
        """Analyze a case for discrepancies and inconsistencies across documents.
        
        This tool specifically looks for:
        - Name spelling variations across documents
        - Mismatched dates of birth
        - Address inconsistencies
        - Different ID numbers for same person
        - Suspicious patterns
        
        Args:
            case_reference: Case ID (optional, uses current case if not provided)
            
        Returns:
            Detailed discrepancy analysis with specific findings.
        """
        # Delegate to summarize_case with discrepancies focus
        return summarize_case.invoke({'case_reference': case_reference, 'focus': 'discrepancies'})
    
    @tool
    def create_new_case(case_reference: str, description: Optional[str] = None) -> str:
        """Create a new KYC/AML case with optional description.
        
        Args:
            case_reference: Case ID (e.g., KYC-2026-002)
            description: Optional case description (customer name, purpose, etc.)
            
        Returns:
            Confirmation message with case details.
        """
        case_ref = case_reference.strip().upper()
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        if case_dir.exists():
            return f"⚠️  Case {case_ref} already exists. Use update_case to modify it."
        
        try:
            # Create case directory
            case_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize metadata
            metadata_manager = StagedCaseMetadataManager(case_ref)
            metadata = {
                'case_reference': case_ref,
                'created_date': datetime.now().isoformat(),
                'status': 'active',
                'workflow_stage': 'document_intake',
                'description': description or '',
                'documents': [],
                'case_summary': {
                    'id_proof': {
                        'documents': [],
                        'verified': False,
                        'extracted_data': {}
                    },
                    'address_proof': {
                        'documents': [],
                        'verified': False,
                        'extracted_data': {}
                    },
                    'financial_statement': {
                        'documents': [],
                        'verified': False,
                        'extracted_data': {}
                    },
                    'verification_status': 'pending',
                    'generated_at': None
                }
            }
            metadata_manager.save_metadata(metadata)
            
            msg = f"✅ Created new case: {case_ref}\n"
            msg += f"   📁 Location: {case_dir}\n"
            if description:
                msg += f"   📝 Description: {description}\n"
            msg += f"\n💡 Next: Add documents to this case for processing"
            
            # Auto-switch to new case
            chat_interface.case_reference = case_ref
            
            return msg
            
        except Exception as e:
            return f"❌ Error creating case: {str(e)}"
    
    @tool
    def update_case_metadata(case_reference: str, updates: Dict[str, Any]) -> str:
        """Update metadata for an existing case.
        
        Args:
            case_reference: Case ID to update
            updates: Dictionary of fields to update (e.g., {'status': 'completed', 'description': 'Updated'})
            
        Returns:
            Confirmation message with updated fields.
        """
        case_dir = Path(settings.documents_dir) / "cases" / case_reference
        
        if not case_dir.exists():
            return f"❌ Case {case_reference} not found."
        
        try:
            metadata_manager = StagedCaseMetadataManager(case_reference)
            metadata = metadata_manager.load_metadata()
            
            # Track what was updated
            updated_fields = []
            
            # Only allow safe fields to be updated
            allowed_fields = ['status', 'description', 'workflow_stage', 'notes', 'assigned_to']
            
            for field, value in updates.items():
                if field in allowed_fields:
                    old_value = metadata.get(field)
                    metadata[field] = value
                    updated_fields.append(f"{field}: {old_value} → {value}")
                else:
                    return f"⚠️  Cannot update field '{field}'. Allowed fields: {', '.join(allowed_fields)}"
            
            # Add update timestamp
            metadata['last_updated'] = datetime.now().isoformat()
            
            metadata_manager.save_metadata(metadata)
            
            msg = f"✅ Updated case: {case_reference}\n"
            msg += "   📝 Changes:\n"
            for update in updated_fields:
                msg += f"      • {update}\n"
            
            return msg
            
        except Exception as e:
            return f"❌ Error updating case: {str(e)}"
    
    @tool
    def delete_case(case_reference: str, confirm: bool = False) -> str:
        """Delete a case and all its documents (requires confirmation).
        
        Args:
            case_reference: Case ID to delete
            confirm: Must be True to actually delete (safety check)
            
        Returns:
            Confirmation or warning message.
        """
        case_dir = Path(settings.documents_dir) / "cases" / case_reference
        
        if not case_dir.exists():
            return f"❌ Case {case_reference} not found."
        
        if not confirm:
            # Count all items in case directory
            documents = list(case_dir.glob("*.pdf")) + list(case_dir.glob("*.jpg")) + list(case_dir.glob("*.png"))
            metadata_files = list(case_dir.glob(".*.metadata.json"))
            all_files = list(case_dir.glob("*.*"))
            
            msg = f"⚠️  WARNING: This will archive case {case_reference} and ALL its contents:\n"
            msg += f"   📄 {len(documents)} document(s)\n"
            msg += f"   📊 {len(metadata_files)} metadata file(s)\n"
            msg += f"   📁 {len(all_files)} total file(s)\n\n"
            msg += f"To confirm archival, call this tool with confirm=True"
            return msg
        
        try:
            # Count items for confirmation message
            documents = list(case_dir.glob("*.pdf")) + list(case_dir.glob("*.jpg")) + list(case_dir.glob("*.png"))
            all_files = list(case_dir.glob("*.*"))
            
            # Archive instead of delete (safer)
            archive_dir = Path(settings.documents_dir) / "archive" / case_reference
            archive_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Move entire case directory with all contents
            shutil.move(str(case_dir), str(archive_dir))
            
            msg = f"✅ Case {case_reference} archived successfully\n"
            msg += f"   📦 Moved: {len(documents)} documents + {len(all_files)} total files\n"
            msg += f"   📁 Archive location: {archive_dir}\n"
            msg += f"   🔒 All documents and metadata preserved in archive\n"
            msg += f"   💡 To restore, manually move from archive back to cases folder"
            
            # Clear case reference if this was the active case
            if chat_interface.case_reference == case_reference:
                chat_interface.case_reference = None
            
            return msg
            
        except Exception as e:
            return f"❌ Error archiving case: {str(e)}"
    
    @tool
    def delete_document(filename: str, case_reference: Optional[str] = None, confirm: bool = False) -> str:
        """Delete a document from a case (requires confirmation).
        
        Args:
            filename: Name of document to delete
            case_reference: Case ID (optional, uses current case)
            confirm: Must be True to actually delete (safety check)
            
        Returns:
            Confirmation or warning message.
        """
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        doc_path = case_dir / filename
        
        if not doc_path.exists():
            return f"❌ Document '{filename}' not found in case {case_ref}."
        
        if not confirm:
            return f"⚠️  WARNING: This will permanently delete '{filename}' from case {case_ref}.\n" \
                   f"To confirm deletion, call this tool with confirm=True"
        
        try:
            # Delete document file
            doc_path.unlink()
            
            # Delete metadata file if exists
            metadata_file = case_dir / f".{filename}.metadata.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            # Update case metadata - remove document ID from list
            metadata_manager = StagedCaseMetadataManager(case_ref)
            case_metadata = metadata_manager.load_metadata()
            
            # Find document ID by filename (need to search metadata files)
            # For now, remove by filename match - this is a simplified approach
            # In production, you'd look up the doc_id from metadata files
            case_metadata['documents'] = [
                doc_id for doc_id in case_metadata.get('documents', [])
                if doc_id != filename  # Assumes filename might be doc_id
            ]
            
            metadata_manager.save_metadata(case_metadata)
            
            return f"✅ Deleted document '{filename}' from case {case_ref}"
            
        except Exception as e:
            return f"❌ Error deleting document: {str(e)}"
    
    @tool
    def update_document_metadata(filename: str, updates: Dict[str, Any], case_reference: Optional[str] = None) -> str:
        """Update metadata for a specific document.
        
        Args:
            filename: Name of document to update
            updates: Dictionary of fields to update
            case_reference: Case ID (optional, uses current case)
            
        Returns:
            Confirmation message with updated fields.
        """
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        doc_path = case_dir / filename
        
        if not doc_path.exists():
            return f"❌ Document '{filename}' not found in case {case_ref}."
        
        metadata_file = case_dir / f".{filename}.metadata.json"
        
        if not metadata_file.exists():
            return f"⚠️  No metadata file found for '{filename}'. Document may not have been processed yet."
        
        try:
            # Load existing metadata
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Track updates
            updated_fields = []
            
            # Allow updating specific fields
            allowed_fields = ['status', 'notes', 'tags', 'processing_notes']
            
            for field, value in updates.items():
                if field in allowed_fields:
                    old_value = metadata.get(field)
                    metadata[field] = value
                    updated_fields.append(f"{field}: {old_value} → {value}")
                elif field in ['classification', 'extraction']:
                    # Allow nested updates for classification/extraction
                    if field not in metadata:
                        metadata[field] = {}
                    metadata[field].update(value)
                    updated_fields.append(f"{field}: updated with {len(value)} fields")
                else:
                    return f"⚠️  Cannot update field '{field}'. Allowed fields: {', '.join(allowed_fields)} or classification/extraction (nested)"
            
            # Add update timestamp
            metadata['last_updated'] = datetime.now().isoformat()
            
            # Save updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            msg = f"✅ Updated metadata for '{filename}'\n"
            msg += "   📝 Changes:\n"
            for update in updated_fields:
                msg += f"      • {update}\n"
            
            return msg
            
        except Exception as e:
            return f"❌ Error updating document metadata: {str(e)}"
    
    @tool
    def submit_documents_for_processing(file_paths: str, case_reference: Optional[str] = None) -> str:
        """Submit documents for processing using pipeline agents - NO CASE REQUIRED.
        
        Documents can be processed independently and linked to cases later if needed.
        Each document gets a globally unique ID (e.g., DOC_20260127_143022_A3F8B).
        
        This tool processes documents through the CrewAI pipeline agents:
        - QueueAgent: Scans paths and builds processing queue
        - ClassificationAgent: Classifies documents via REST API
        - ExtractionAgent: Extracts data via REST API
        - MetadataAgent: Tracks status and handles errors
        - SummaryAgent: Generates processing report
        
        Args:
            file_paths: Document path(s). Can be:
                - Single path: "~/Downloads/passport.pdf"
                - Multiple paths (comma-separated): "~/Downloads/passport.pdf, ~/Documents/bill.pdf"
                - Folder path: "~/Documents/kyc_docs"
                - With spaces: "~/My Documents/file.pdf"
            case_reference: OPTIONAL case ID. If not provided, documents are processed independently.
                           Use link_document_to_case later to associate with cases.
            
        Returns:
            Processing results with document IDs and extracted information.
            
        Examples:
            submit_documents_for_processing("~/Downloads/passport.pdf")  # No case needed
            submit_documents_for_processing("~/Documents/kyc_docs")  # Process entire folder
            submit_documents_for_processing("~/Downloads/policy.pdf", case_reference="KYC-2026-001")
        """
        from pipeline_flow import run_pipeline_sync
        import re
        
        case_ref = case_reference or chat_interface.case_reference
        
        # Parse file paths (handle comma-separated, quoted paths, tilde)
        paths = []
        
        # Split by comma first
        raw_paths = [p.strip() for p in file_paths.split(',')]
        
        for raw_path in raw_paths:
            # Remove quotes if present
            raw_path = raw_path.strip('"').strip("'")
            
            # Expand tilde and resolve
            try:
                path = Path(raw_path).expanduser().resolve()
                if path.exists():
                    paths.append(str(path))
                else:
                    return f"❌ Path not found: {raw_path}\n   (Expanded to: {path})"
            except Exception as e:
                return f"❌ Invalid path '{raw_path}': {str(e)}"
        
        if not paths:
            return "❌ No valid file paths provided"
        
        try:
            msg = f"🚀 Processing {len(paths)} path(s) through Pipeline Agents...\n"
            if case_ref:
                msg += f"   📁 Case: {case_ref}\n"
            else:
                msg += f"   📁 No case set - documents will get unique IDs\n"
            
            for i, p in enumerate(paths, 1):
                msg += f"   {i}. {Path(p).name}\n"
            
            # Use the new pipeline (process first path - can be file or folder)
            result = run_pipeline_sync(paths[0])
            
            # Format results
            msg += f"\n✅ Processing Complete!\n\n"
            
            if isinstance(result, dict):
                # Check for success
                if result.get('success'):
                    summary = result.get('summary', {})
                    stats = summary.get('statistics', {})
                    
                    msg += f"📊 Results:\n"
                    msg += f"   • Total: {stats.get('total_documents', 0)}\n"
                    msg += f"   • Completed: {stats.get('completed', 0)}\n"
                    msg += f"   • Failed: {stats.get('failed', 0)}\n"
                    
                    # Show document types
                    by_type = summary.get('by_document_type', {})
                    if by_type:
                        msg += f"\n📋 Document Types:\n"
                        for doc_type, count in by_type.items():
                            msg += f"   • {doc_type}: {count}\n"
                    
                    # Show processed document IDs
                    processed = result.get('processed_documents', [])
                    if processed:
                        msg += f"\n📄 Processed Documents:\n"
                        for doc_id in processed[:10]:
                            msg += f"   • {doc_id}\n"
                        if len(processed) > 10:
                            msg += f"   ... and {len(processed) - 10} more\n"
                else:
                    msg += f"⚠️  Error: {result.get('error', 'Unknown error')}\n"
                
                # Suggest next steps
                if not case_ref:
                    processed = result.get('processed_documents', [])
                    if processed:
                        msg += f"\n💡 Next: Link documents to a case using:\n"
                        msg += f"   'link document {processed[0]} to case KYC-2026-XXX'\n"
            else:
                msg += f"📋 Result: {result}\n"
            
            msg += f"\n💡 Use 'get_case_status_with_metadata' to see detailed results"
            
            return msg
            
        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return f"❌ Error processing documents: {str(e)}"
    
    @tool
    def process_document_by_id(document_id: str) -> str:
        """Resume processing for a document that already exists by its document ID.
        
        This tool:
        1. Loads the document's metadata from documents/intake/
        2. Checks which stages are pending
        3. Automatically resumes processing from the appropriate stage using pipeline agents
        
        Use this when a user provides a document ID like "DOC_20260127_190130_8A0B7".
        
        Args:
            document_id: The document ID (e.g., DOC_20260127_190130_8A0B7)
            
        Returns:
            Processing results with stage completion status.
        """
        try:
            from tools.classification_api_tools import classify_document
            from tools.extraction_api_tools import extract_document_data
            
            # Find document metadata in intake directory
            intake_dir = Path(settings.documents_dir) / "intake"
            metadata_path = intake_dir / f"{document_id}.metadata.json"
            
            if not metadata_path.exists():
                return f"❌ Document {document_id} not found in intake directory.\n   💡 Use submit_documents_for_processing to upload new documents."
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Check stages
            classification = metadata.get('classification', {})
            extraction = metadata.get('extraction', {})
            
            classification_status = classification.get('status', 'pending')
            extraction_status = extraction.get('status', 'pending')
            
            # Build status message
            msg = f"\n📄 Document: {fmt_id(document_id)}\n"
            msg += f"   📁 File: {metadata.get('original_filename', 'unknown')}\n\n"
            msg += f"Stage Status:\n"
            msg += f"   ✅ Intake: completed\n"
            msg += f"   {'✅' if classification_status == 'completed' else '⏳'} Classification: {classification_status}\n"
            msg += f"   {'✅' if extraction_status == 'completed' else '⏳'} Extraction: {extraction_status}\n\n"
            
            # Check if already complete
            if classification_status == 'completed' and extraction_status == 'completed':
                return msg + "✨ All stages completed! Document fully processed."
            
            # Get stored document path
            stored_path = metadata.get('stored_path')
            if not stored_path or not Path(stored_path).exists():
                return f"❌ Document file not found at: {stored_path}"
            
            # Resume processing with pipeline agents
            msg += "🚀 Resuming processing with Pipeline Agents...\n\n"
            
            doc_type = None
            
            # Classification if needed
            if classification_status != 'completed':
                msg += "📋 Running ClassificationAgent...\n"
                class_result = classify_document(stored_path)
                
                if class_result.get('success'):
                    doc_type = class_result.get('document_type')
                    confidence = class_result.get('confidence', 0)
                    msg += f"   ✅ Classified as: {doc_type} (confidence: {confidence:.1%})\n"
                else:
                    msg += f"   ❌ Classification failed: {class_result.get('error')}\n"
                    return msg
            else:
                doc_type = classification.get('document_type')
                msg += f"   ✅ Classification: already completed ({doc_type})\n"
            
            # Extraction if needed
            if extraction_status != 'completed':
                msg += "\n📊 Running ExtractionAgent...\n"
                extract_result = extract_document_data.run(document_id=document_id, document_type=doc_type)
                
                if extract_result.get('success'):
                    extracted_fields = extract_result.get('extracted_fields', {})
                    kyc_data = extract_result.get('kyc_data', {})
                    msg += f"   ✅ Extracted {len(extracted_fields)} field(s)\n"
                    
                    # Show KYC entities if available
                    if kyc_data.get('entities'):
                        msg += f"   📋 Found {kyc_data.get('entity_count', 0)} entities:\n"
                        for entity in kyc_data.get('entities', [])[:3]:
                            etype = entity.get('entity_type', 'unknown')
                            name = entity.get('full_name') or entity.get('company_name') or 'Unknown'
                            msg += f"      • {etype}: {name}\n"
                    elif extracted_fields:
                        # Show some fields
                        for field, value in list(extracted_fields.items())[:5]:
                            if field not in ['raw_text', 'word_count', 'char_count']:
                                msg += f"      • {field}: {value}\n"
                else:
                    msg += f"   ❌ Extraction failed: {extract_result.get('error')}\n"
                    return msg
            else:
                msg += f"   ✅ Extraction: already completed\n"
            
            msg += f"\n✨ Document {document_id} fully processed!"
            
            return msg
            
        except Exception as e:
            logger.error(f"Error processing document by ID: {e}", exc_info=True)
            return f"❌ Error processing document: {str(e)}"
    
    @tool
    def reset_document_stage(document_id: str, stage_name: str, reason: str = "Manual reset") -> str:
        """Reset a specific processing stage for a document to allow reprocessing.
        
        This tool allows you to reset a stage (classification or extraction) back to 'pending',
        which enables reprocessing of that stage. Useful when:
        - Classification result was incorrect and needs to be redone
        - Extraction failed and you want to retry
        - API was updated and you want to re-classify with new model
        - Manual review determined the result needs correction
        
        Args:
            document_id: The document ID (e.g., DOC_20260127_192803_A7EF0)
            stage_name: Stage to reset ('classification' or 'extraction')
            reason: Reason for resetting (for audit trail)
            
        Returns:
            Confirmation message with reset details.
        """
        try:
            # Find document metadata
            intake_dir = Path(settings.documents_dir) / "intake"
            metadata_path = intake_dir / f"{document_id}.metadata.json"
            
            if not metadata_path.exists():
                return f"❌ Document {document_id} not found."
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Validate stage name
            valid_stages = ['classification', 'extraction']
            if stage_name not in valid_stages:
                return f"❌ Invalid stage '{stage_name}'. Must be one of: {', '.join(valid_stages)}"
            
            # Check if stage exists
            if stage_name not in metadata:
                return f"❌ Stage '{stage_name}' not found in document metadata."
            
            # Save previous state for audit
            previous_state = metadata[stage_name].copy()
            
            # Reset the stage to pending
            metadata[stage_name] = {
                "status": "pending",
                "msg": "",
                "error": None,
                "trace": None,
                "timestamp": None
            }
            
            # Add reset history
            if 'processing_history' not in metadata:
                metadata['processing_history'] = []
            
            metadata['processing_history'].append({
                "action": "stage_reset",
                "stage": stage_name,
                "reason": reason,
                "previous_state": previous_state,
                "reset_at": datetime.now().isoformat()
            })
            
            # Update last_updated timestamp
            metadata["last_updated"] = datetime.now().isoformat()
            
            # Stage field is vestigial - status blocks handle progression
            
            # Save updated metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            msg = f"✅ Stage reset successfully!\n\n"
            msg += f"📄 Document: {fmt_id(document_id)}\n"
            msg += f"🔄 Stage Reset: {stage_name}\n"
            msg += f"📝 Reason: {reason}\n"
            msg += f"⏰ Reset at: {datetime.now().isoformat()}\n\n"
            msg += f"Previous state:\n"
            msg += f"  • Status: {previous_state.get('status', 'unknown')}\n"
            msg += f"  • Message: {previous_state.get('msg', 'N/A')}\n\n"
            msg += f"💡 Next: Use process_document_by_id('{document_id}') to reprocess"
            
            logger.info(f"Reset stage '{stage_name}' for document {document_id}. Reason: {reason}")
            
            return msg
            
        except Exception as e:
            logger.error(f"Error resetting document stage: {e}", exc_info=True)
            return f"❌ Error resetting stage: {str(e)}"
    
    @tool
    def link_document_to_case(document_id: str, case_id: str) -> str:
        """
        Link a document to a case by adding document ID to case metadata.
        
        Args:
            document_id: Document ID (e.g., DOC_20260127_143022_A3F8B)
            case_id: Case ID (e.g., KYC_2026_001)
            
        Returns:
            Status message indicating success or failure
        """
        try:
            case_dir = Path(settings.documents_dir) / "cases" / case_id
            case_metadata_path = case_dir / "case_metadata.json"
            
            if not case_metadata_path.exists():
                return f"❌ Case {case_id} not found. Create case first."
            
            with open(case_metadata_path, 'r') as f:
                case_metadata = json.load(f)
            
            if "documents" not in case_metadata:
                case_metadata["documents"] = []
            
            if document_id in case_metadata["documents"]:
                return f"ℹ️  Document {document_id} already linked to case {case_id}"
            
            case_metadata["documents"].append(document_id)
            case_metadata["last_updated"] = datetime.now().isoformat()
            
            with open(case_metadata_path, 'w') as f:
                json.dump(case_metadata, f, indent=2)
            
            logger.info(f"Linked document {document_id} to case {case_id}")
            return f"✅ Document {document_id} linked to case {case_id}"
                
        except Exception as e:
            logger.error(f"Failed to link document to case: {e}", exc_info=True)
            return f"❌ Error linking document: {str(e)}"
    
    @tool
    def view_queue_status() -> str:
        """View the current document processing queue status.
        
        Shows pending, processing, completed, and failed documents in the queue.
        Use this to check how many documents are waiting to be processed.
        
        Returns:
            Queue status with document counts and list of pending documents.
        """
        from tools.queue_tools import get_queue_status
        
        try:
            status = get_queue_status()
            
            msg = "\n📊 Queue Status\n"
            msg += "=" * 60 + "\n\n"
            msg += f"📋 Summary:\n"
            msg += f"   • Pending: {status.get('pending', 0)}\n"
            msg += f"   • Processing: {status.get('processing', 0)}\n"
            msg += f"   • Completed: {status.get('completed', 0)}\n"
            msg += f"   • Failed: {status.get('failed', 0)}\n"
            msg += f"   • Total: {status.get('total', 0)}\n\n"
            
            # Show pending documents if available
            pending_docs = status.get('pending_documents', [])
            if pending_docs:
                msg += f"📄 Pending Documents ({len(pending_docs)}):\n"
                for doc in pending_docs[:10]:
                    doc_id = doc.get('document_id', 'unknown')
                    filename = doc.get('original_filename', 'unknown')
                    msg += f"   • {doc_id}: {filename}\n"
                if len(pending_docs) > 10:
                    msg += f"   ... and {len(pending_docs) - 10} more\n"
            
            return msg
        except Exception as e:
            logger.error(f"Error viewing queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def process_next_from_queue() -> str:
        """Process the next document from the queue using pipeline agents.
        
        Takes the next pending document from the queue and processes it through
        the complete workflow (classification and extraction) using pipeline agents.
        
        Returns:
            Processing result for the document.
        """
        from tools.queue_tools import get_next_from_queue, mark_document_processed
        from tools.classification_api_tools import classify_document
        from tools.extraction_api_tools import extract_document_data
        
        try:
            # Get next document from queue
            next_doc = get_next_from_queue()
            
            if not next_doc.get('success') or not next_doc.get('document'):
                return "✅ Queue is empty - no more documents to process."
            
            doc = next_doc['document']
            doc_id = doc.get('document_id')
            file_path = doc.get('stored_path')
            
            msg = f"🚀 Processing: {doc_id}\n\n"
            
            # Classification
            msg += "📋 Running ClassificationAgent...\n"
            class_result = classify_document(file_path)
            
            if class_result.get('success'):
                doc_type = class_result.get('document_type')
                confidence = class_result.get('confidence', 0)
                msg += f"   ✅ Classified as: {doc_type} (confidence: {confidence:.1%})\n\n"
                
                # Extraction
                msg += "📊 Running ExtractionAgent...\n"
                extract_result = extract_document_data.run(document_id=doc_id, document_type=doc_type)
                
                if extract_result.get('success'):
                    extracted_fields = extract_result.get('extracted_fields', {})
                    msg += f"   ✅ Extracted {len(extracted_fields)} field(s)\n"
                    
                    # Mark as completed
                    mark_document_processed(doc_id, 'completed')
                    msg += f"\n✅ Document {doc_id} fully processed!"
                else:
                    mark_document_processed(doc_id, 'failed', extract_result.get('error'))
                    msg += f"   ❌ Extraction failed: {extract_result.get('error')}"
            else:
                mark_document_processed(doc_id, 'failed', class_result.get('error'))
                msg += f"   ❌ Classification failed: {class_result.get('error')}"
            
            return msg
            
        except Exception as e:
            logger.error(f"Error processing from queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def process_all_queued_documents(max_documents: Optional[int] = None) -> str:
        """Process all documents in the queue using pipeline agents.
        
        Processes all pending documents in the queue one by one until the queue
        is empty or the maximum number is reached.
        
        Args:
            max_documents: Maximum number of documents to process (optional)
            
        Returns:
            Summary of processing results for all documents.
        """
        from tools.queue_tools import get_next_from_queue, mark_document_processed, get_queue_status
        from tools.classification_api_tools import classify_document
        from tools.extraction_api_tools import extract_document_data
        
        try:
            processed_count = 0
            failed_count = 0
            
            msg = "\n🚀 Processing documents from queue with Pipeline Agents...\n"
            msg += "=" * 60 + "\n\n"
            
            while True:
                # Check if we've hit max documents limit
                if max_documents and processed_count >= max_documents:
                    msg += f"\n⏸️  Reached maximum of {max_documents} documents.\n"
                    break
                
                # Get next document
                next_doc = get_next_from_queue()
                
                if not next_doc.get('success') or not next_doc.get('document'):
                    msg += "\n✅ Queue is now empty.\n"
                    break
                
                doc = next_doc['document']
                doc_id = doc.get('document_id')
                file_path = doc.get('stored_path')
                
                # Classification
                class_result = classify_document(file_path)
                
                if class_result.get('success'):
                    doc_type = class_result.get('document_type')
                    
                    # Extraction
                    extract_result = extract_document_data.run(document_id=doc_id, document_type=doc_type)
                    
                    if extract_result.get('success'):
                        mark_document_processed(doc_id, 'completed')
                        processed_count += 1
                        msg += f"✅ Processed #{processed_count}: {doc_id} ({doc_type})\n"
                    else:
                        mark_document_processed(doc_id, 'failed', extract_result.get('error'))
                        failed_count += 1
                        msg += f"❌ Failed #{processed_count + failed_count}: {doc_id} (extraction)\n"
                else:
                    mark_document_processed(doc_id, 'failed', class_result.get('error'))
                    failed_count += 1
                    msg += f"❌ Failed #{processed_count + failed_count}: {doc_id} (classification)\n"
            
            # Summary
            msg += f"\n📊 Processing Complete\n"
            msg += "=" * 60 + "\n\n"
            msg += f"Results:\n"
            msg += f"   • Processed: {processed_count}\n"
            msg += f"   • Failed: {failed_count}\n"
            msg += f"   • Total: {processed_count + failed_count}\n"
            
            return msg
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def add_directory_to_queue(directory_path: str, priority: int = 1) -> str:
        """Add all documents from a directory to the processing queue.
        
        Scans a directory and adds all supported documents (PDF, JPG, PNG, etc.)
        to the queue for processing. Documents are not processed immediately,
        but queued for later processing.
        
        Args:
            directory_path: Path to directory containing documents
            priority: Priority level (1=high, 2=medium, 3=low), default=1
            
        Returns:
            Confirmation with count of added documents.
        """
        from tools.queue_tools import build_processing_queue, get_queue_status
        
        try:
            # Expand path
            dir_path = Path(directory_path).expanduser().resolve()
            
            if not dir_path.exists():
                return f"❌ Directory not found: {directory_path}"
            
            if not dir_path.is_dir():
                return f"❌ Path is not a directory: {directory_path}"
            
            # Build queue from directory
            result = build_processing_queue(str(dir_path))
            
            if result.get('success'):
                msg = f"✅ Added {result.get('queued_count', 0)} documents to queue\n\n"
                msg += f"📊 Queue Status:\n"
                status = get_queue_status()
                msg += f"   • Pending: {status.get('pending', 0)}\n"
                msg += f"   • Total: {status.get('total', 0)}\n"
                return msg
            else:
                return f"❌ {result.get('error', 'Failed to build queue')}"
        except Exception as e:
            logger.error(f"Error adding directory to queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def add_files_to_queue(file_paths: str, priority: int = 1) -> str:
        """Add specific files to the processing queue.
        
        Add one or more document files to the queue for processing.
        Provide file paths as comma-separated values.
        
        Args:
            file_paths: File paths separated by commas (e.g., "/path/file1.pdf,/path/file2.jpg")
            priority: Priority level (1=high, 2=medium, 3=low), default=1
            
        Returns:
            Confirmation with count of added documents.
        """
        from tools.queue_tools import build_processing_queue, get_queue_status
        
        try:
            # Parse comma-separated paths
            paths = [p.strip() for p in file_paths.split(',')]
            total_queued = 0
            
            for path in paths:
                # Expand path
                file_path = Path(path).expanduser().resolve()
                
                if file_path.exists():
                    result = build_processing_queue(str(file_path))
                    if result.get('success'):
                        total_queued += result.get('queued_count', 0)
            
            if total_queued > 0:
                msg = f"✅ Added {total_queued} document(s) to queue\n\n"
                msg += f"📊 Queue Status:\n"
                status = get_queue_status()
                msg += f"   • Pending: {status.get('pending', 0)}\n"
                msg += f"   • Total: {status.get('total', 0)}\n"
                return msg
            else:
                return f"❌ No valid documents found in provided paths"
        except Exception as e:
            logger.error(f"Error adding files to queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def run_document_pipeline(input_path: str) -> str:
        """Run the full document processing pipeline on a file or folder.
        
        This is the primary tool for processing documents through all 5 pipeline agents:
        1. QueueAgent: Scans path, expands folders, splits PDFs, builds queue
        2. ClassificationAgent: Classifies each document via REST API
        3. ExtractionAgent: Extracts data via REST API
        4. MetadataAgent: Tracks status and handles errors
        5. SummaryAgent: Generates processing report
        
        Args:
            input_path: Path to a file or folder to process
            
        Returns:
            Processing summary with statistics and results.
        """
        from pipeline_flow import run_pipeline_sync
        
        try:
            # Expand path
            path = Path(input_path).expanduser().resolve()
            
            if not path.exists():
                return f"❌ Path not found: {input_path}"
            
            msg = f"🚀 Running Pipeline Agents on: {path.name}\n"
            msg += "=" * 60 + "\n\n"
            
            # Run the pipeline
            result = run_pipeline_sync(str(path))
            
            if result.get('success'):
                summary = result.get('summary', {})
                stats = summary.get('statistics', {})
                
                msg += f"✅ Pipeline Complete!\n\n"
                msg += f"📊 Results:\n"
                msg += f"   • Total Documents: {stats.get('total_documents', 0)}\n"
                msg += f"   • Completed: {stats.get('completed', 0)}\n"
                msg += f"   • Failed: {stats.get('failed', 0)}\n"
                msg += f"   • Skipped: {stats.get('skipped', 0)}\n"
                
                # Show document types
                by_type = summary.get('by_document_type', {})
                if by_type:
                    msg += f"\n📋 Classification Results:\n"
                    for doc_type, count in by_type.items():
                        msg += f"   • {doc_type}: {count}\n"
                
                # Show processing time
                duration = result.get('duration_seconds', 0)
                if duration:
                    msg += f"\n⏱️  Processing Time: {duration:.1f} seconds\n"
            else:
                msg += f"❌ Pipeline failed: {result.get('error', 'Unknown error')}\n"
            
            return msg
            
        except Exception as e:
            logger.error(f"Error running pipeline: {e}")
            return f"❌ Error: {str(e)}"
    
    return [
        list_all_cases,
        list_all_documents,  # List documents with filtering
        get_current_status, 
        switch_case, 
        get_case_details, 
        get_case_status_with_metadata, 
        get_document_details,
        find_document_by_id,  # Find document by ID across all cases
        get_case_documents_with_extracted_data,  # Get all docs with extracted data for comparison
        summarize_case,  # LLM-powered intelligent case summary
        analyze_case_discrepancies,  # Analyze discrepancies across documents
        create_new_case,
        update_case_metadata,
        delete_case,
        delete_document,
        update_document_metadata,
        submit_documents_for_processing,
        process_document_by_id,
        reset_document_stage,
        link_document_to_case,
        run_document_pipeline,  # Full pipeline execution
        view_queue_status,
        process_next_from_queue,
        process_all_queued_documents,
        add_directory_to_queue,
        add_files_to_queue
    ]
