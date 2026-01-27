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
        
        # Document summary
        doc_summary = case_metadata.get('document_summary', {})
        total = doc_summary.get('total', 0)
        
        if total > 0:
            msg += "📈 Document Summary:\n"
            msg += f"  • Total Documents: {total}\n"
            msg += f"  • Fully Completed: {doc_summary.get('fully_completed', 0)} ✅\n"
            msg += f"  • Partially Completed: {doc_summary.get('partially_completed', 0)} ⏳\n"
            msg += f"  • Pending Processing: {doc_summary.get('pending_processing', 0)} 🔵\n"
            msg += f"  • Pending Reprocessing: {doc_summary.get('pending_reprocessing', 0)} 🔄\n"
            msg += f"  • Failed: {doc_summary.get('failed', 0)} ❌\n\n"
        else:
            msg += "📄 No documents in this case yet.\n\n"
        
        # Individual document details
        documents = case_metadata.get('documents', [])
        
        if documents:
            msg += "📋 Document Details:\n"
            msg += "-" * 60 + "\n\n"
            
            for idx, doc in enumerate(documents, 1):
                doc_id = doc.get('document_id', 'unknown')
                filename = doc.get('filename', 'unknown')
                doc_status = doc.get('status', 'unknown')
                
                # Status emoji
                status_emoji = {
                    'fully_completed': '✅',
                    'partially_completed': '⏳',
                    'pending_processing': '🔵',
                    'pending_reprocessing': '🔄',
                    'failed': '❌'
                }.get(doc_status, '❓')
                
                msg += f"{idx}. {filename} {status_emoji}\n"
                msg += f"   ID: {doc_id}\n"
                
                # Classification results
                classification = doc.get('classification', {})
                if classification:
                    doc_type = classification.get('document_type', 'unknown')
                    confidence = classification.get('confidence', 0)
                    msg += f"   📝 Type: {doc_type} (confidence: {confidence:.0%})\n"
                
                # Extraction results
                extraction = doc.get('extraction', {})
                if extraction:
                    extracted_fields = extraction.get('extracted_data', {})
                    if extracted_fields:
                        msg += f"   📊 Extracted Fields: {len(extracted_fields)} fields\n"
                        # Show key fields
                        key_fields = ['name', 'document_number', 'date_of_birth', 'expiry_date', 'address']
                        for field in key_fields:
                            if field in extracted_fields:
                                value = extracted_fields[field]
                                if value and str(value).strip():
                                    msg += f"      • {field.replace('_', ' ').title()}: {value}\n"
                
                # Processing timestamps
                intake_date = doc.get('intake_date')
                if intake_date:
                    msg += f"   ⏰ Processed: {intake_date}\n"
                
                # Errors or warnings
                errors = doc.get('errors', [])
                if errors:
                    msg += f"   ⚠️  Errors: {', '.join(errors)}\n"
                
                msg += "\n"
        
        # Next steps recommendation
        pending = doc_summary.get('pending_processing', 0)
        failed = doc_summary.get('failed', 0)
        
        if pending > 0:
            msg += f"\n💡 Next Steps: {pending} document(s) pending processing\n"
        elif failed > 0:
            msg += f"\n💡 Next Steps: {failed} document(s) failed - review and reprocess\n"
        elif total > 0 and doc_summary.get('fully_completed', 0) == total:
            msg += "\n✨ All documents processed successfully! Case ready for review.\n"
        
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
                'document_summary': {
                    'total': 0,
                    'fully_completed': 0,
                    'partially_completed': 0,
                    'pending_processing': 0,
                    'pending_reprocessing': 0,
                    'failed': 0
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
            
            # Update case metadata
            metadata_manager = StagedCaseMetadataManager(case_ref)
            case_metadata = metadata_manager.load_metadata()
            
            # Remove document from documents list
            case_metadata['documents'] = [
                doc for doc in case_metadata.get('documents', [])
                if doc.get('filename') != filename
            ]
            
            # Recompute summary
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
        submit_documents_for_processing
    ]
