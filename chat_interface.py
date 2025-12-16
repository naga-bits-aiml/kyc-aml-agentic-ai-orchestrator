"""
Interactive chat interface for KYC-AML Agentic AI Orchestrator.

This module provides a conversational interface where users can interact
with the agents through natural language, with guided workflow for case management.
"""
import sys
import re
import json
import shutil
import zipfile
import tarfile
from typing import List, Dict, Any, Optional
from pathlib import Path
from orchestrator import KYCAMLOrchestrator
from agents import DocumentIntakeAgent, DocumentClassifierAgent
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from utilities import config, settings, logger


class ChatInterface:
    """Interactive chat interface for the KYC-AML orchestrator with workflow guidance."""
    
    def __init__(self):
        """Initialize the chat interface."""
        self.logger = logger
        self.orchestrator = None
        self.llm = None
        self.chat_history: List[Dict[str, str]] = []
        self.conversation_context: List[Any] = []
        self.processed_documents: List[str] = []
        
        # Workflow state management
        self.workflow_state = "awaiting_case_reference"
        self.case_reference: Optional[str] = None
        self.pending_action: Optional[Dict[str, Any]] = None
        self.case_documents: Dict[str, List[str]] = {}
        
        self._initialize_orchestrator()
        self._initialize_system_prompt()
    
    def _initialize_orchestrator(self):
        """Initialize the orchestrator and LLM."""
        try:
            self.orchestrator = KYCAMLOrchestrator(temperature=0.3)
            if self.orchestrator and hasattr(self.orchestrator, 'llm'):
                self.llm = self.orchestrator.llm
            else:
                self._initialize_fallback_llm()
        except Exception as e:
            self.logger.warning(f"Could not initialize orchestrator: {str(e)}")
            self._initialize_fallback_llm()
    
    def _initialize_fallback_llm(self):
        """Initialize fallback LLM directly."""
        try:
            if config.llm_provider == "google":
                self.llm = ChatGoogleGenerativeAI(
                    model=config.google_model,
                    temperature=0.3,
                    google_api_key=config.google_api_key
                )
            else:
                self.llm = ChatOpenAI(
                    model=config.openai_model,
                    temperature=0.3,
                    openai_api_key=config.openai_api_key
                )
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM: {str(e)}")
    
    def _initialize_system_prompt(self):
        """Initialize the system prompt for the conversation."""
        system_prompt = """You are a helpful AI assistant for a KYC-AML (Know Your Customer - Anti Money Laundering) 
document processing system. You help users with:

1. Setting up case references for document processing
2. Submitting documents for processing (files, folders, or archives)
3. Understanding document requirements
4. Checking processing status
5. Interpreting classification results
6. Answering questions about KYC-AML compliance

You have access to two specialized agents:
- Document Intake Agent: Validates and processes incoming documents
- Document Classifier Agent: Classifies documents into categories

Be helpful, professional, and security-conscious. Guide users through the workflow step-by-step.
Always confirm case reference before processing documents.

Supported document types:
- Identity Proof: Passport, Driver's License, National ID
- Address Proof: Utility Bills, Bank Statements, Lease Agreements
- Financial Documents: Income Statements, Tax Returns
- Regulatory Forms: KYC Forms, AML Declarations"""

        self.conversation_context.append(SystemMessage(content=system_prompt))
    
    def add_message(self, role: str, content: str):
        """Add a message to chat history."""
        self.chat_history.append({"role": role, "content": content})
        
        if role == "user":
            self.conversation_context.append(HumanMessage(content=content))
        elif role == "assistant":
            self.conversation_context.append(AIMessage(content=content))
    
    def get_llm_response(self, user_message: str) -> str:
        """Get a response from the LLM."""
        if not self.llm:
            return "❌ Chat system not initialized. Please check your configuration."
        
        try:
            self.add_message("user", user_message)
            response = self.llm.invoke(self.conversation_context)
            assistant_message = response.content
            self.add_message("assistant", assistant_message)
            return assistant_message
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {str(e)}")
            return f"I apologize, but I encountered an error: {str(e)}"
    
    def set_case_reference(self, case_ref: str) -> str:
        """Set the active case reference."""
        self.case_reference = case_ref.strip().upper()
        self.workflow_state = "active"
        self.logger.info(f"Case reference set to: {self.case_reference}")
        
        # Create case directory
        case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
        case_dir.mkdir(parents=True, exist_ok=True)
        
        msg = f"✅ Case Reference Set: {self.case_reference}\n\n"
        msg += f"📁 Case directory created at: {case_dir}\n\n"
        msg += "You can now:\n"
        msg += "• Upload individual documents\n"
        msg += "• Provide a folder path containing multiple documents\n"
        msg += "• Upload archive files (.zip, .tar, .gz) for batch processing\n\n"
        msg += "How would you like to proceed?"
        
        return msg
    
    def confirm_pending_action(self, confirmed: bool) -> str:
        """Confirm or reject pending action."""
        if not self.pending_action:
            return "No pending action to confirm."
        
        action = self.pending_action
        self.pending_action = None
        self.workflow_state = "active"
        
        if not confirmed:
            return "❌ Action cancelled. What would you like to do next?"
        
        # Execute the confirmed action
        action_type = action.get("type")
        
        if action_type == "process_folder":
            return self._execute_folder_processing(action["folder_path"], action["files"])
        elif action_type == "process_archive":
            return self._execute_archive_processing(action["archive_path"])
        
        return "Unknown action type."
    
    def process_command(self, user_input: str) -> Optional[str]:
        """Process special commands."""
        user_input = user_input.strip().lower()
        
        # Help command
        if user_input in ['help', '/help', '?']:
            return self._show_help()
        
        # Exit commands
        if user_input in ['exit', 'quit', 'bye', '/exit', '/quit']:
            return "exit"
        
        # Status command
        if user_input in ['status', '/status']:
            return self._show_status()
        
        # History command
        if user_input in ['history', '/history']:
            return self._show_history()
        
        # Clear command
        if user_input in ['clear', '/clear']:
            self.chat_history = []
            self.conversation_context = [self.conversation_context[0]]  # Keep system prompt
            return "Chat history cleared."
        
        # Health check
        if user_input in ['health', '/health']:
            return self._check_health()
        
        # Process command with file path
        if user_input.startswith('/process '):
            file_path = user_input.replace('/process ', '').strip()
            return self._process_document_command(file_path)
        
        return None
    
    def _show_help(self) -> str:
        """Show help information."""
        msg = "\n╔════════════════════════════════════════════════════════════╗\n"
        msg += "║              KYC-AML Chat Interface - Help                 ║\n"
        msg += "╚════════════════════════════════════════════════════════════╝\n\n"
        msg += "📋 Workflow:\n"
        msg += "  1. Set Case Reference    - Provide your KYC/AML case reference\n"
        msg += "  2. Submit Documents       - Upload files, folders, or archives\n"
        msg += "  3. Review Results         - Check classification results\n\n"
        msg += "💬 Commands:\n"
        msg += "  help, /help, ?            Show this help message\n"
        msg += "  exit, quit, bye           Exit the chat\n"
        msg += "  status, /status           Show processing status\n"
        msg += "  history, /history         Show chat history\n"
        msg += "  clear, /clear             Clear chat history\n"
        msg += "  health, /health           Check system health\n\n"
        msg += "📄 Document Processing Options:\n\n"
        msg += "  Individual Files:\n"
        msg += "    - Provide file path: \"C:\\path\\to\\passport.pdf\"\n"
        msg += "    - Or describe: \"Process my passport document\"\n\n"
        msg += "  Folder Processing:\n"
        msg += "    - Provide folder path: \"C:\\path\\to\\documents\\\"\n"
        msg += "    - System will list all files and ask for confirmation\n\n"
        msg += "  Archive Processing:\n"
        msg += "    - Provide archive path: \"C:\\path\\to\\documents.zip\"\n"
        msg += "    - Supported: .zip, .tar, .gz, .tgz\n"
        msg += "    - System will extract and process all documents\n\n"
        msg += "✨ Features:\n"
        msg += "  • Automatic file organization by case reference\n"
        msg += "  • Internal document references (CASE-REF_DOC_001, etc.)\n"
        msg += "  • File mapping preservation (original name → internal ref)\n"
        msg += "  • Batch processing with confirmation prompts\n"
        msg += "  • Archive extraction and processing\n\n"
        msg += "💡 Tips:\n"
        msg += f"  • Supported formats: PDF, JPG, PNG, DOCX, DOC, TXT\n"
        msg += f"  • Max file size: {settings.max_document_size_mb}MB\n"
        msg += "  • Case reference is required before processing\n"
        msg += "  • You can provide folder paths for batch processing\n\n"
        msg += f"Current Case: {self.case_reference or 'Not set'}\n"
        
        return msg
    
    def _show_status(self) -> str:
        """Show current processing status."""
        total_docs = len(self.processed_documents)
        case_info = f"Active Case: {self.case_reference}" if self.case_reference else "No active case"
        
        case_doc_count = ""
        if self.case_reference and self.case_reference in self.case_documents:
            case_doc_count = f"\n  • Documents in current case: {len(self.case_documents[self.case_reference])}"
        
        msg = "\n📊 Processing Status:\n"
        msg += f"  • {case_info}\n"
        msg += f"  • Total documents processed: {total_docs}{case_doc_count}\n"
        msg += f"  • Workflow state: {self.workflow_state.replace('_', ' ').title()}\n"
        msg += f"  • Chat messages: {len(self.chat_history)}\n\n"
        msg += "Recent documents:\n"
        msg += self._format_document_list(self.processed_documents[-5:])
        
        return msg
    
    def _show_history(self) -> str:
        """Show chat history."""
        if not self.chat_history:
            return "No chat history yet."
        
        msg = "\n📜 Chat History:\n"
        for i, entry in enumerate(self.chat_history[-10:], 1):
            role = entry['role'].capitalize()
            content = entry['content'][:100] + "..." if len(entry['content']) > 100 else entry['content']
            msg += f"\n{i}. {role}: {content}\n"
        
        return msg
    
    def _check_health(self) -> str:
        """Check system health."""
        msg = "\n🏥 System Health Check:\n\n"
        
        # Check orchestrator
        if self.orchestrator:
            msg += "✅ Orchestrator: OK\n"
        else:
            msg += "❌ Orchestrator: Not initialized\n"
        
        # Check LLM
        if self.llm:
            msg += "✅ LLM: OK\n"
        else:
            msg += "❌ LLM: Not initialized\n"
        
        # Check case reference
        if self.case_reference:
            msg += f"✅ Case Reference: {self.case_reference}\n"
        else:
            msg += "⚠️  Case Reference: Not set\n"
        
        return msg
    
    def _format_document_list(self, documents: List[str]) -> str:
        """Format a list of documents for display."""
        if not documents:
            return "  (none)\n"
        
        msg = ""
        for doc in documents:
            msg += f"  • {Path(doc).name}\n"
        
        return msg
    
    def _process_document_command(self, file_path: str) -> str:
        """Process a document from a command."""
        return self._process_documents([file_path])
    
    def _extract_file_paths(self, text: str) -> List[str]:
        """Extract file paths from text."""
        paths = []
        
        # First priority: Paths in quotes (supports spaces)
        quoted_paths = re.findall(r'["\']([^"\']+)["\']', text)
        for path in quoted_paths:
            path = path.strip()
            if Path(path).exists():
                paths.append(path)
        
        # Second priority: Windows paths with file extensions
        windows_file_paths = re.findall(
            r'[A-Za-z]:[\\\/](?:[^<>:"|?*\n\r]+?)\.(?:pdf|jpg|jpeg|png|doc|docx|txt|csv|xlsx)',
            text,
            re.IGNORECASE
        )
        paths.extend(windows_file_paths)
        
        # Third priority: Unix paths with file extensions
        unix_file_paths = re.findall(
            r'\/(?:[^<>:"|?*\n\r\s]+?)\.(?:pdf|jpg|jpeg|png|doc|docx|txt|csv|xlsx)',
            text,
            re.IGNORECASE
        )
        paths.extend(unix_file_paths)
        
        # Validate paths exist and deduplicate
        valid_paths = []
        seen = set()
        for p in paths:
            p = p.strip().rstrip('.,;:')
            p_normalized = str(Path(p).resolve()) if Path(p).exists() else p
            
            if p_normalized not in seen and Path(p).exists():
                valid_paths.append(p)
                seen.add(p_normalized)
                self.logger.info(f"✓ Found valid file path: {p}")
            elif p not in seen:
                self.logger.debug(f"✗ Path not found: {p}")
                seen.add(p)
        
        return valid_paths
    
    def _extract_folder_path(self, text: str) -> Optional[str]:
        """Extract folder path from text."""
        # Look for directory patterns (paths without file extensions)
        # Windows folders
        windows_folders = re.findall(r'[A-Za-z]:[\\\/][^<>:"|?*\n\r]+?(?=[\\\/]?$|\s|$)', text)
        for folder in windows_folders:
            folder = folder.strip().rstrip('.,;:')
            if Path(folder).is_dir():
                self.logger.info(f"✓ Found folder path: {folder}")
                return folder
        
        # Quoted paths
        quoted_paths = re.findall(r'["\']([^"\']+)["\']', text)
        for path in quoted_paths:
            path = path.strip()
            if Path(path).is_dir():
                self.logger.info(f"✓ Found folder path: {path}")
                return path
        
        return None
    
    def _extract_archive_path(self, text: str) -> Optional[str]:
        """Extract archive file path from text."""
        # Look for archive files
        archive_patterns = re.findall(
            r'[A-Za-z]:[\\\/](?:[^<>:"|?*\n\r]+?)\.(?:zip|tar|gz|tgz|rar|7z)',
            text,
            re.IGNORECASE
        )
        
        for archive in archive_patterns:
            archive = archive.strip().rstrip('.,;:')
            if Path(archive).exists() and Path(archive).is_file():
                self.logger.info(f"✓ Found archive file: {archive}")
                return archive
        
        return None
    
    def _handle_case_reference_input(self, user_input: str) -> str:
        """Handle case reference input from user."""
        case_ref = user_input.strip()
        
        # Simple validation
        if len(case_ref) < 3:
            msg = "⚠️ Case reference seems too short.\n\n"
            msg += "Please provide a valid KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).\n"
            msg += "Or type 'skip' to proceed without a case reference."
            return msg
        
        if case_ref.lower() == 'skip':
            self.case_reference = f"CASE-{Path.cwd().name[:10]}"
            self.workflow_state = "active"
            return f"Proceeding without case reference. Using default: {self.case_reference}\n\nYou can now submit documents for processing."
        
        return self.set_case_reference(case_ref)
    
    def _handle_confirmation_input(self, user_input: str) -> str:
        """Handle confirmation input from user."""
        response = user_input.strip().lower()
        
        confirmed = response in ['yes', 'y', 'confirm', 'ok', 'proceed', 'sure']
        rejected = response in ['no', 'n', 'cancel', 'skip']
        
        if not confirmed and not rejected:
            return "Please confirm with 'yes' or 'no'."
        
        return self.confirm_pending_action(confirmed)
    
    def _handle_folder_input(self, folder_path: str) -> str:
        """Handle folder path input - list files and request confirmation."""
        folder = Path(folder_path)
        
        # Get all supported files in the folder
        supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt']
        files = []
        for ext in supported_extensions:
            files.extend(folder.glob(f'*{ext}'))
            files.extend(folder.glob(f'*{ext.upper()}'))
        
        if not files:
            return f"⚠️ No supported documents found in: {folder_path}\n\nSupported formats: PDF, JPG, PNG, DOC, DOCX, TXT"
        
        # Set pending action
        self.pending_action = {
            "type": "process_folder",
            "folder_path": folder_path,
            "files": [str(f) for f in files]
        }
        self.workflow_state = "awaiting_confirmation"
        
        file_list = "\n".join([f"  • {f.name}" for f in files[:10]])
        if len(files) > 10:
            file_list += f"\n  ... and {len(files) - 10} more files"
        
        msg = f"📁 Found {len(files)} document(s) in folder: {folder.name}\n\n"
        msg += file_list + "\n\n"
        msg += f"❓ Do you want to process all these documents for case {self.case_reference}?\n"
        msg += "Type 'yes' to confirm or 'no' to cancel."
        
        return msg
    
    def _handle_archive_input(self, archive_path: str) -> str:
        """Handle archive file input - extract and request confirmation."""
        archive = Path(archive_path)
        
        self.pending_action = {
            "type": "process_archive",
            "archive_path": archive_path
        }
        self.workflow_state = "awaiting_confirmation"
        
        msg = f"📦 Archive file detected: {archive.name}\n\n"
        msg += f"❓ Do you want to extract and process all documents from this archive for case {self.case_reference}?\n"
        msg += "Type 'yes' to confirm or 'no' to cancel."
        
        return msg
    
    def _execute_folder_processing(self, folder_path: str, files: List[str]) -> str:
        """Execute folder processing after confirmation."""
        self.logger.info(f"Processing {len(files)} files from folder: {folder_path}")
        return self._process_documents(files)
    
    def _execute_archive_processing(self, archive_path: str) -> str:
        """Execute archive processing after confirmation."""
        archive = Path(archive_path)
        extract_dir = Path(settings.documents_dir) / "temp_extract" / archive.stem
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract based on file type
            if archive.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive.suffix.lower() in ['.tar', '.gz', '.tgz']:
                with tarfile.open(archive, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                return f"❌ Unsupported archive format: {archive.suffix}"
            
            # Find all supported files
            supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt']
            files = []
            for ext in supported_extensions:
                files.extend(extract_dir.rglob(f'*{ext}'))
            
            if not files:
                return "⚠️ No supported documents found in archive."
            
            self.logger.info(f"Extracted {len(files)} files from archive")
            result = self._process_documents([str(f) for f in files])
            
            # Cleanup temp directory
            shutil.rmtree(extract_dir, ignore_errors=True)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting archive: {str(e)}")
            return f"❌ Error extracting archive: {str(e)}"
    
    def _process_documents(self, file_paths: List[str]) -> str:
        """Process documents through the orchestrator."""
        if not self.orchestrator:
            return "❌ Orchestrator not available. Please check configuration."
        
        if not file_paths:
            return "No valid file paths provided."
        
        # Check if case reference is set
        if not self.case_reference:
            self.workflow_state = "awaiting_case_reference"
            msg = "⚠️ No case reference set.\n\n"
            msg += "Please provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).\n"
            msg += "Or type 'skip' to proceed without a case reference."
            return msg
        
        # Validate paths
        valid_paths = []
        for path in file_paths:
            p = Path(path)
            if p.exists():
                valid_paths.append(str(p.absolute()))
            else:
                return f"❌ File not found: {path}"
        
        try:
            print(f"\n🔄 Processing {len(valid_paths)} document(s) for case {self.case_reference}...")
            
            # Copy files to case directory with internal references
            case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
            case_dir.mkdir(parents=True, exist_ok=True)
            
            file_mapping = {}
            processed_paths = []
            
            for idx, original_path in enumerate(valid_paths, 1):
                original_file = Path(original_path)
                # Create internal reference
                internal_ref = f"{self.case_reference}_DOC_{idx:03d}{original_file.suffix}"
                dest_path = case_dir / internal_ref
                
                # Copy file to case directory
                shutil.copy2(original_path, dest_path)
                
                file_mapping[internal_ref] = str(original_file)
                processed_paths.append(str(dest_path))
                
                self.logger.info(f"Stored: {original_file.name} -> {internal_ref}")
            
            # Save file mapping
            mapping_file = case_dir / "file_mapping.json"
            with open(mapping_file, 'w') as f:
                json.dump(file_mapping, f, indent=2)
            
            # Process documents through orchestrator
            results = self.orchestrator.process_documents(processed_paths)
            
            # Track processed documents
            self.processed_documents.extend(valid_paths)
            if self.case_reference not in self.case_documents:
                self.case_documents[self.case_reference] = []
            self.case_documents[self.case_reference].extend(processed_paths)
            
            # Generate summary
            summary = self.orchestrator.get_processing_summary(results)
            
            msg = f"\n✅ Processing complete for case {self.case_reference}!\n\n"
            msg += f"📁 Documents stored in: {case_dir}\n"
            msg += "🔗 File mapping saved\n\n"
            msg += summary
            
            return msg
            
        except Exception as e:
            self.logger.error(f"Error processing documents: {str(e)}")
            return f"❌ Error processing documents: {str(e)}"
    
    def handle_user_input(self, user_input: str) -> str:
        """Handle user input and generate response."""
        # Check for commands first
        command_result = self.process_command(user_input)
        if command_result == "exit":
            return "exit"
        if command_result:
            return command_result
        
        # Handle workflow states
        if self.workflow_state == "awaiting_case_reference":
            return self._handle_case_reference_input(user_input)
        
        if self.workflow_state == "awaiting_confirmation":
            return self._handle_confirmation_input(user_input)
        
        # Extract any file paths from the input
        file_paths = self._extract_file_paths(user_input)
        
        # Check if user is providing a folder path
        folder_path = self._extract_folder_path(user_input)
        if folder_path:
            return self._handle_folder_input(folder_path)
        
        # Check if user is providing an archive file
        archive_path = self._extract_archive_path(user_input)
        if archive_path:
            return self._handle_archive_input(archive_path)
        
        # If file paths found, process the documents automatically
        if file_paths:
            self.logger.info(f"Detected file paths in user input: {file_paths}")
            return self._process_documents(file_paths)
        
        # Get LLM response for general queries
        return self.get_llm_response(user_input)
    
    def start(self):
        """Start the interactive chat session."""
        print("\n")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║    KYC-AML Agentic AI Orchestrator - Chat Interface       ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("\n💬 Welcome! I'm your KYC-AML document processing assistant.")
        print("\n📋 Workflow Guidance:")
        print("   1. Provide your KYC/AML case reference")
        print("   2. Submit documents (files, folders, or archives)")
        print("   3. Documents will be stored and classified automatically")
        print("\n✨ Features:")
        print("   • Individual file processing")
        print("   • Folder batch processing")
        print("   • Archive extraction (.zip, .tar, .gz)")
        print("   • Automatic file organization with internal references")
        print("\n   Type 'help' for commands, or 'exit' to quit.\n")
        
        # Prompt for case reference
        if self.workflow_state == "awaiting_case_reference":
            print("🔍 Please provide your KYC/AML case reference to begin:")
            print("   Examples: KYC-2024-001, AML-CASE-123, CUSTOMER-456")
            print("   Or type 'skip' to use a default reference.\n")
        
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle input
                response = self.handle_user_input(user_input)
                
                # Check for exit
                if response == "exit":
                    print("\n👋 Thank you for using KYC-AML Orchestrator. Goodbye!")
                    break
                
                # Display response
                print(f"\n🤖 Assistant: {response}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Chat interrupted. Goodbye!")
                break
            except Exception as e:
                self.logger.error(f"Error in chat loop: {str(e)}")
                print(f"\n❌ Error: {str(e)}")
    
    def save_conversation(self, filename: str = "chat_history.json"):
        """Save conversation to file."""
        with open(filename, 'w') as f:
            json.dump({
                'chat_history': self.chat_history,
                'processed_documents': self.processed_documents,
                'case_reference': self.case_reference,
                'case_documents': self.case_documents
            }, f, indent=2)
        print(f"💾 Conversation saved to {filename}")


def main():
    """Main entry point for the chat interface."""
    chat = ChatInterface()
    
    try:
        chat.start()
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        return 1
    finally:
        # Optionally save conversation
        if chat.chat_history:
            save = input("\n💾 Save conversation history? (y/N): ").lower()
            if save == 'y':
                chat.save_conversation()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
