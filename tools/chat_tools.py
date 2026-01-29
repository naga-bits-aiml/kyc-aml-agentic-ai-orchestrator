"""
Chat interface tools for LLM tool calling.
These tools enable the LLM to interact with the KYC-AML system.
"""
from pathlib import Path
from typing import Optional, Dict, Any
import json
import shutil
from datetime import datetime
from langchain_core.tools import tool
from utilities import settings, logger
from case_metadata_manager import StagedCaseMetadataManager


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
        """Get detailed information about a specific case.
        
        Args:
            case_reference: The case reference ID (e.g., KYC-2024-001)
            
        Returns:
            Detailed case information including document list.
        """
        case_dir = Path(settings.documents_dir) / "cases" / case_reference
        
        if not case_dir.exists():
            return f"❌ Case {case_reference} not found."
        
        documents = list(case_dir.glob("*.*"))
        
        msg = f"\n📁 Case: {case_reference}\n\n"
        msg += f"  • Location: {case_dir}\n"
        msg += f"  • Documents: {len(documents)}\n\n"
        
        if documents:
            msg += "  Documents:\n"
            for doc in sorted(documents):
                size_kb = doc.stat().st_size / 1024
                msg += f"    - {doc.name} ({size_kb:.1f} KB)\n"
        else:
            msg += "  No documents in this case yet.\n"
        
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
        msg = f"\n📊 Case Status: {case_ref}\n"
        msg += "=" * 60 + "\n\n"
        
        # Workflow stage
        workflow_stage = case_metadata.get('workflow_stage', 'unknown')
        status = case_metadata.get('status', 'unknown')
        created = case_metadata.get('created_date', 'N/A')
        
        msg += f"🔄 Workflow Stage: {workflow_stage.replace('_', ' ').title()}\n"
        msg += f"📅 Created: {created}\n"
        msg += f"🏷️  Status: {status.upper()}\n\n"
        
        # Document count
        documents = case_metadata.get('documents', [])
        total = len(documents)
        
        if total > 0:
            msg += f"📄 Documents: {total}\n\n"
        else:
            msg += "📄 No documents in this case yet.\n\n"
        
        # Individual document details
        if documents:
            msg += "📋 Documents:\n"
            msg += "-" * 60 + "\n"
            for idx, doc_id in enumerate(documents, 1):
                msg += f"{idx}. {doc_id}\n"
        
        return msg
    
    @tool
    def get_document_details(filename: str, case_reference: Optional[str] = None) -> str:
        """Get detailed metadata and processing results for a specific document.
        
        This tool retrieves comprehensive information about a document including:
        - Classification results (document type, confidence, reasoning)
        - All extracted fields and values
        - OCR quality and text content
        - Processing timestamps and status
        - File information and location
        
        Args:
            filename: Name of the document file (e.g., 'passport.pdf')
            case_reference: Case ID (optional, uses current case if not provided)
            
        Returns:
            Detailed document information with all metadata and processing results.
        """
        # Use current case if not specified
        case_ref = case_reference or chat_interface.case_reference
        
        if not case_ref:
            return "⚠️  No case selected. Please specify a case reference or switch to a case first."
        
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        
        if not case_dir.exists():
            return f"❌ Case {case_ref} not found."
        
        # Find the document file
        doc_path = case_dir / filename
        if not doc_path.exists():
            # Try to find similar files
            similar_files = [f.name for f in case_dir.glob("*") if filename.lower() in f.name.lower()]
            if similar_files:
                return f"❌ Document '{filename}' not found. Did you mean one of these?\n" + "\n".join(f"  • {f}" for f in similar_files)
            return f"❌ Document '{filename}' not found in case {case_ref}."
        
        # Load document metadata
        metadata_file = case_dir / f".{filename}.metadata.json"
        
        if not metadata_file.exists():
            return f"📄 Document: {filename}\n⚠️  No metadata found - document may not have been processed yet."
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            return f"❌ Error reading metadata: {str(e)}"
        
        # Build detailed report
        msg = f"\n📄 Document Details: {filename}\n"
        msg += "=" * 70 + "\n\n"
        
        # Basic info
        doc_id = metadata.get('document_id', 'unknown')
        status = metadata.get('status', 'unknown')
        file_size = doc_path.stat().st_size / 1024
        
        msg += "📋 Basic Information:\n"
        msg += f"  • Document ID: {doc_id}\n"
        msg += f"  • File Size: {file_size:.1f} KB\n"
        msg += f"  • Location: {doc_path}\n"
        msg += f"  • Status: {status.upper()}\n\n"
        
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
            extracted_data = extraction.get('extracted_data', {})
            ocr_text = extraction.get('ocr_text', '')
            
            msg += "📊 Extracted Data:\n"
            if extracted_data:
                for field, value in extracted_data.items():
                    if value and str(value).strip():
                        field_name = field.replace('_', ' ').title()
                        msg += f"  • {field_name}: {value}\n"
            else:
                msg += "  • No structured data extracted\n"
            
            msg += "\n"
            
            # OCR information
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
        """Submit documents for processing - NO CASE REQUIRED.
        
        Documents can be processed independently and linked to cases later if needed.
        Each document gets a globally unique ID (e.g., DOC_20260127_143022_A3F8B).
        
        This tool processes documents through the CrewAI pipeline for:
        - Document intake and validation (generates unique document ID)
        - Classification (passport, driver's license, utility bill, etc.)
        - Data extraction (names, dates, addresses, document numbers)
        
        Args:
            file_paths: Document path(s). Can be:
                - Single path: "~/Downloads/passport.pdf"
                - Multiple paths (comma-separated): "~/Downloads/passport.pdf, ~/Documents/bill.pdf"
                - With spaces: "~/My Documents/file.pdf"
            case_reference: OPTIONAL case ID. If not provided, documents are processed independently.
                           Use link_document_to_case later to associate with cases.
            
        Returns:
            Processing results with document IDs and extracted information.
            
        Examples:
            submit_documents_for_processing("~/Downloads/passport.pdf")  # No case needed
            submit_documents_for_processing("~/Downloads/policy.pdf", case_reference="KYC-2026-001")
        """
        from flows.document_processing_flow import kickoff_flow
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
                if path.exists() and path.is_file():
                    paths.append(str(path))
                else:
                    return f"❌ File not found: {raw_path}\n   (Expanded to: {path})"
            except Exception as e:
                return f"❌ Invalid path '{raw_path}': {str(e)}"
        
        if not paths:
            return "❌ No valid file paths provided"
        
        try:
            msg = f"🚀 Processing {len(paths)} document(s) through CrewAI pipeline...\n"
            if case_ref:
                msg += f"   📁 Case: {case_ref}\n"
            else:
                msg += f"   📁 No case set - documents will get unique IDs\n"
            
            for i, p in enumerate(paths, 1):
                msg += f"   {i}. {Path(p).name}\n"
            
            # Call CrewAI flow (case_id is optional now)
            result = kickoff_flow(
                file_paths=paths,
                case_id=case_ref,  # Can be None
                llm=chat_interface.llm
            )
            
            # Format results
            msg += f"\n✅ Processing Complete!\n\n"
            
            if isinstance(result, dict):
                # Check for errors first
                if result.get('errors'):
                    msg += f"⚠️  Errors encountered:\n"
                    for error in result['errors'][:5]:  # Show first 5 errors
                        msg += f"   • {error}\n"
                    if len(result['errors']) > 5:
                        msg += f"   ... and {len(result['errors']) - 5} more errors\n"
                    msg += f"\n"
                
                # Show status
                status = result.get('status', 'unknown')
                if status == 'failed':
                    msg += f"❌ Status: FAILED\n\n"
                elif status == 'partial':
                    msg += f"⚠️  Status: PARTIAL (some documents failed)\n\n"
                elif status == 'requires_review':
                    msg += f"⚠️  Status: REQUIRES REVIEW\n\n"
                else:
                    msg += f"✅ Status: {status.upper()}\n\n"
                
                # Show document IDs if available
                if 'validated_documents' in result and result['validated_documents']:
                    msg += f"📄 Documents Processed:\n"
                    for doc in result['validated_documents'][:10]:  # Show first 10
                        doc_id = doc.get('document_id', 'Unknown')
                        filename = doc.get('original_filename', 'Unknown')
                        msg += f"   • {doc_id}: {filename}\n"
                    if len(result['validated_documents']) > 10:
                        msg += f"   ... and {len(result['validated_documents']) - 10} more\n"
                elif status != 'failed':
                    msg += f"⚠️  No documents were validated\n"
                
                # Show document summary statistics
                if 'documents' in result and isinstance(result['documents'], dict):
                    doc_stats = result['documents']
                    msg += f"\n📊 Summary:\n"
                    msg += f"   • Total: {doc_stats.get('total', 0)}\n"
                    msg += f"   • Successful: {doc_stats.get('successful', 0)}\n"
                    msg += f"   • Failed: {doc_stats.get('failed', 0)}\n"
                
                # Check for child documents that need processing
                child_docs = result.get('child_documents_pending', [])
                if child_docs:
                    msg += f"\n👶 Child Documents Detected:\n"
                    msg += f"   Found {len(child_docs)} child document(s) that need processing.\n"
                    for child in child_docs[:5]:  # Show first 5
                        parent_id = child.get('parent_id', 'unknown')
                        msg += f"   • {child.get('document_id', 'unknown')} (from {parent_id})\n"
                    if len(child_docs) > 5:
                        msg += f"   ... and {len(child_docs) - 5} more\n"

                    msg += f"\n⏭️  Auto-processing child documents in a second run...\n"
                    child_result = kickoff_flow(
                        file_paths=[],
                        case_id=case_ref,
                        llm=chat_interface.llm,
                        processing_mode="process"
                    )
                    if isinstance(child_result, dict):
                        child_status = child_result.get('status', 'unknown')
                        msg += f"   Child run status: {child_status}\n"
                        child_docs_processed = child_result.get('documents', {})
                        msg += (
                            f"   Child docs processed: total={child_docs_processed.get('total', 0)}, "
                            f"successful={child_docs_processed.get('successful', 0)}, "
                            f"failed={child_docs_processed.get('failed', 0)}\n"
                        )
                    else:
                        msg += f"   Child run result: {child_result}\n"
                
                # Suggest next steps
                if not case_ref and result.get('validated_documents'):
                    doc_ids = [d.get('document_id') for d in result['validated_documents'] if d.get('document_id')]
                    if doc_ids:
                        msg += f"\n💡 Next: Link documents to a case using:\n"
                        msg += f"   'link document {doc_ids[0]} to case KYC-2026-XXX'\n"
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
        3. Automatically resumes processing from the appropriate stage
        
        Use this when a user provides a document ID like "DOC_20260127_190130_8A0B7".
        
        Args:
            document_id: The document ID (e.g., DOC_20260127_190130_8A0B7)
            
        Returns:
            Processing results with stage completion status.
        """
        try:
            # Find document metadata in intake directory
            intake_dir = Path(settings.documents_dir) / "intake"
            metadata_path = intake_dir / f"{document_id}.metadata.json"
            
            if not metadata_path.exists():
                return f"❌ Document {document_id} not found in intake directory.\n   💡 Use submit_documents_for_processing to upload new documents."
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Check if it has the new structure with stage blocks
            required_blocks = ['intake', 'classification', 'extraction']
            has_stage_blocks = all(stage in metadata for stage in required_blocks)
            
            if not has_stage_blocks:
                missing = [s for s in required_blocks if s not in metadata]
                return f"⚠️  Document {document_id} uses old metadata format.\n   Missing blocks: {', '.join(missing)}\n   Please re-upload the document for processing."
            
            # Check what needs to be processed
            intake_status = metadata.get('intake', {}).get('status', 'pending')
            classification_status = metadata.get('classification', {}).get('status', 'pending')
            extraction_status = metadata.get('extraction', {}).get('status', 'pending')
            
            if intake_status != 'success':
                return f"❌ Document {document_id} intake failed. Please re-upload the document."
            
            # Build status message
            msg = f"\n📄 Document: {document_id}\n"
            msg += f"   📁 File: {metadata.get('original_filename', 'unknown')}\n\n"
            msg += f"Stage Status:\n"
            msg += f"   ✅ Intake: {intake_status}\n"
            msg += f"   {'✅' if classification_status == 'success' else '⏳'} Classification: {classification_status}\n"
            msg += f"   {'✅' if extraction_status == 'success' else '⏳'} Extraction: {extraction_status}\n\n"
            
            # Determine what to do
            if classification_status == 'success' and extraction_status == 'success':
                return msg + "✨ All stages completed! Document fully processed."
            
            # Resume processing
            msg += "🚀 Resuming processing...\n\n"
            
            # Get stored document path
            stored_path = metadata.get('stored_path')
            if not stored_path or not Path(stored_path).exists():
                return f"❌ Document file not found at: {stored_path}"
            
            # Use flow to process from current state
            from flows.document_processing_flow import kickoff_flow
            
            result = kickoff_flow(
                file_paths=[stored_path],
                case_id=None,  # Case-agnostic processing
                llm=chat_interface.llm
            )
            
            if result:
                msg += f"✅ Processing completed!\n\n"
                
                # Show stage metadata from result
                if 'stage_metadata' in result:
                    stage_meta = result['stage_metadata']
                    for stage_name in ['intake', 'classification', 'extraction']:
                        stage_info = stage_meta.get(stage_name, {})
                        status = stage_info.get('status', 'unknown')
                        stage_msg = stage_info.get('msg', '')
                        icon = '✅' if status == 'success' else ('❌' if status == 'fail' else '⏳')
                        msg += f"   {icon} {stage_name.title()}: {status}\n"
                        if stage_msg:
                            msg += f"      {stage_msg}\n"
                
                # Show case readiness
                if 'case_readiness' in result:
                    readiness = result['case_readiness']
                    is_complete = readiness.get('is_complete', False)
                    msg += f"\n{'✨' if is_complete else '⚠️'}  Case Readiness: {'Complete' if is_complete else 'Incomplete'}\n"
                    
                    recommendations = readiness.get('recommendations', [])
                    if recommendations:
                        msg += "\n💡 Recommendations:\n"
                        for rec in recommendations:
                            msg += f"   • {rec}\n"
            
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
            msg += f"📄 Document: {document_id}\n"
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
        Manually link an existing document to a case.
        
        Note: Normally, documents are automatically linked when processed with a case_id.
        Use this tool only for:
        - Linking documents that were processed without a case
        - Moving documents between cases
        - Manual corrections
        
        Args:
            document_id: Document ID (e.g., DOC_20260127_143022_A3F8B)
            case_id: Case ID (e.g., KYC-2026-001)
            
        Returns:
            Status message indicating success or failure
        """
        try:
            # Find document metadata file in intake or other stages
            stages = ["intake", "classification", "extraction", "processed"]
            metadata_path = None
            current_stage = None
            
            for stage in stages:
                potential_path = Path(settings.documents_dir) / stage / f"{document_id}.metadata.json"
                if potential_path.exists():
                    metadata_path = potential_path
                    current_stage = stage
                    break
            
            if not metadata_path:
                return f"❌ Document {document_id} not found in any stage"
            
            # Load existing metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Add case to linked_cases if not already present
            if "linked_cases" not in metadata:
                metadata["linked_cases"] = []
            
            if case_id not in metadata["linked_cases"]:
                metadata["linked_cases"].append(case_id)
                metadata["last_updated"] = datetime.now().isoformat()
                
                # Save updated document metadata
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Now update the case metadata to include this document
                case_dir = Path(settings.documents_dir) / "cases" / case_id
                case_metadata_path = case_dir / "case_metadata.json"
                
                if case_metadata_path.exists():
                    with open(case_metadata_path, 'r') as f:
                        case_metadata = json.load(f)
                    
                    # Add document_id to case's documents list if not already present
                    if "documents" not in case_metadata:
                        case_metadata["documents"] = []
                    
                    if document_id not in case_metadata["documents"]:
                        case_metadata["documents"].append(document_id)
                        
                        # Save updated case metadata
                        with open(case_metadata_path, 'w') as f:
                            json.dump(case_metadata, f, indent=2)
                        
                        logger.info(f"Manually linked document {document_id} to case {case_id}")
                else:
                    logger.warning(f"Case metadata file not found: {case_metadata_path}")
                
                return f"✅ Document {document_id} successfully linked to case {case_id}\n   Stage: {current_stage}"
            else:
                return f"ℹ️  Document {document_id} already linked to case {case_id}"
                
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
        from utilities.queue_manager import DocumentQueue
        
        try:
            queue = DocumentQueue()
            result = {
                "status": queue.get_status(),
                "pending": queue.get_all_pending(),
                "failed": queue.get_all_failed()
            }
            status = result['status']
            pending = result['pending']
            failed = result['failed']
            
            msg = "\n📊 Queue Status\n"
            msg += "=" * 60 + "\n\n"
            msg += f"📋 Summary:\n"
            msg += f"   • Pending: {status['pending']}\n"
            msg += f"   • Processing: {status['processing']}\n"
            msg += f"   • Failed: {status['failed']}\n"
            msg += f"   • Total in queue: {status['total_queue']}\n"
            msg += f"   • Total processed: {status['total_processed']}\n\n"
            
            if pending:
                msg += f"📄 Pending Documents ({len(pending)}):\n"
                for entry in pending[:10]:  # Show first 10
                    file_name = Path(entry['source_path']).name
                    source = entry['source_type']
                    priority = entry.get('priority', 1)
                    msg += f"   • {file_name} (source: {source}, priority: {priority})\n"
                if len(pending) > 10:
                    msg += f"   ... and {len(pending) - 10} more\n"
                msg += "\n"
            
            if failed:
                msg += f"❌ Failed Documents ({len(failed)}):\n"
                for entry in failed[:5]:  # Show first 5
                    file_name = Path(entry['source_path']).name
                    error = entry.get('error', 'Unknown error')
                    msg += f"   • {file_name}: {error}\n"
                if len(failed) > 5:
                    msg += f"   ... and {len(failed) - 5} more\n"
            
            return msg
        except Exception as e:
            logger.error(f"Error viewing queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def process_next_from_queue() -> str:
        """Process the next document from the queue.
        
        Takes the next pending document from the queue and processes it through
        the complete workflow (classification and extraction).
        
        Returns:
            Processing result for the document.
        """
        from flows.document_processing_flow import process_next_document_from_queue
        
        try:
            result = process_next_document_from_queue(
                processing_mode='process',
                case_id=chat_interface.case_reference,
                llm=chat_interface.llm,
                auto_drain=False
            )
            
            if result['status'] == 'complete':
                return "✅ Queue is empty - no more documents to process."
            elif result['status'] == 'success':
                doc_id = result.get('document_id', 'UNKNOWN')
                stage_results = result.get('stage_results', {})
                msg = f"✅ Successfully processed: {doc_id}\n\n"
                msg += f"📊 Results:\n"
                for stage, stage_result in stage_results.items():
                    status = stage_result.get('status', 'unknown')
                    msg += f"   • {stage}: {status}\n"
                return msg
            elif result['status'] == 'failed':
                queue_id = result.get('queue_id', 'UNKNOWN')
                error = result.get('error', 'Unknown error')
                return f"❌ Failed to process: {queue_id}\n   Error: {error}"
            else:
                return f"⚠️  Unexpected result: {result.get('message', 'Unknown')}"
        except Exception as e:
            logger.error(f"Error processing from queue: {e}")
            return f"❌ Error: {str(e)}"
    
    @tool
    def process_all_queued_documents(max_documents: Optional[int] = None) -> str:
        """Process all documents in the queue.
        
        Processes all pending documents in the queue one by one until the queue
        is empty or the maximum number is reached.
        
        Args:
            max_documents: Maximum number of documents to process (optional)
            
        Returns:
            Summary of processing results for all documents.
        """
        from flows.document_processing_flow import process_next_document_from_queue
        
        try:
            processed_count = 0
            failed_count = 0
            skipped_count = 0
            
            msg = "\n🚀 Processing documents from queue...\n"
            msg += "=" * 60 + "\n\n"
            
            while True:
                # Check if we've hit max documents limit
                if max_documents and processed_count >= max_documents:
                    msg += f"\n⏸️  Reached maximum of {max_documents} documents.\n"
                    break
                
                # Process next document
                result = process_next_document_from_queue(
                    processing_mode='process',
                    case_id=chat_interface.case_reference,
                    llm=chat_interface.llm,
                    auto_drain=False
                )
                
                if result['status'] == 'complete':
                    msg += "\n✅ Queue is now empty.\n"
                    break
                elif result['status'] == 'success':
                    processed_count += 1
                    doc_id = result.get('document_id', 'UNKNOWN')
                    msg += f"✅ Processed #{processed_count}: {doc_id}\n"
                elif result['status'] == 'failed':
                    failed_count += 1
                    queue_id = result.get('queue_id', 'UNKNOWN')
                    error = result.get('error', 'Unknown error')
                    msg += f"❌ Failed #{failed_count}: {queue_id} - {error}\n"
                elif result['status'] == 'skipped':
                    skipped_count += 1
                    msg += f"⏭️  Skipped document #{skipped_count}\n"
            
            # Summary
            msg += f"\n📊 Processing Complete\n"
            msg += "=" * 60 + "\n\n"
            msg += f"Results:\n"
            msg += f"   • Processed: {processed_count}\n"
            msg += f"   • Failed: {failed_count}\n"
            msg += f"   • Skipped: {skipped_count}\n"
            msg += f"   • Total: {processed_count + failed_count + skipped_count}\n"
            
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
        from utilities.queue_manager import DocumentQueue
        
        try:
            queue = DocumentQueue()
            queue_ids = queue.add_directory(directory_path, priority=priority)
            if not queue_ids:
                result = {
                    "status": "failed",
                    "message": "No valid documents found in directory",
                    "queue_ids": []
                }
            else:
                result = {
                    "status": "success",
                    "message": f"Added {len(queue_ids)} documents to queue from {directory_path}",
                    "queue_ids": queue_ids,
                    "queue_status": queue.get_status()
                }
            
            if result['status'] == 'success':
                msg = f"✅ {result['message']}\n\n"
                msg += f"📊 Queue Status:\n"
                status = result['queue_status']
                msg += f"   • Pending: {status['pending']}\n"
                msg += f"   • Total in queue: {status['total_queue']}\n"
                msg += f"   • Processed: {status['total_processed']}\n"
                return msg
            else:
                return f"❌ {result['message']}"
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
        from flows.document_processing_flow import add_files_to_queue as add_files
        
        try:
            # Parse comma-separated paths
            paths = [p.strip() for p in file_paths.split(',')]
            
            result = add_files(paths, priority=priority)
            
            if result['status'] == 'success':
                msg = f"✅ {result['message']}\n\n"
                msg += f"📊 Queue Status:\n"
                status = result['queue_status']
                msg += f"   • Pending: {status['pending']}\n"
                msg += f"   • Total in queue: {status['total_queue']}\n"
                msg += f"   • Processed: {status['total_processed']}\n"
                return msg
            else:
                return f"❌ {result['message']}"
        except Exception as e:
            logger.error(f"Error adding files to queue: {e}")
            return f"❌ Error: {str(e)}"
    
    return [
        list_all_cases, 
        get_current_status, 
        switch_case, 
        get_case_details, 
        get_case_status_with_metadata, 
        get_document_details,
        create_new_case,
        update_case_metadata,
        delete_case,
        delete_document,
        update_document_metadata,
        submit_documents_for_processing,
        process_document_by_id,
        reset_document_stage,
        link_document_to_case,  # Manual document linking (fallback)
        view_queue_status,  # Queue management
        process_next_from_queue,
        process_all_queued_documents,
        add_directory_to_queue,
        add_files_to_queue
    ]
