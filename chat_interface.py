"""
Clean CLI chat interface for KYC-AML document processing using CrewAI Pipeline.

This interface integrates with the new pipeline agents:
- QueueAgent: Scans paths, expands folders, splits PDFs, builds queue
- ClassificationAgent: Classifies documents via REST API
- ExtractionAgent: Extracts data from documents via REST API  
- MetadataAgent: Tracks status and handles errors
- SummaryAgent: Generates processing reports
"""
import sys
import re
import json
from pathlib import Path
from typing import List, Optional
from pipeline_crew import DocumentProcessingCrew, create_pipeline_crew
from pipeline_flow import run_pipeline, run_pipeline_sync
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from utilities import config, settings, logger
from utilities.llm_factory import create_llm, get_model_info
from tools.chat_tools import create_chat_tools
from agents.supervisor_agent import SupervisorAgent

# Rich console for beautiful terminal output
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Global console for rich output
console = Console()


def print_markdown(text: str, title: str = None) -> None:
    """Render Markdown text beautifully in the terminal using rich."""
    md = Markdown(text)
    if title:
        console.print(Panel(md, title=title, border_style="blue"))
    else:
        console.print(md)


class ChatInterface:
    """Simple CLI chat interface for CrewAI document processing."""
    
    def __init__(self):
        """Initialize chat interface."""
        self.logger = logger
        self.crew = None
        self.llm = None
        self.supervisor = None  # Supervisor agent for multi-step commands
        self.case_reference: Optional[str] = None
        self.conversation_history = []
        
        self._initialize_system()
        
    def _initialize_system(self):
        """Initialize CrewAI pipeline crew and LLM."""
        try:
            # Create LLM using factory
            self.llm = create_llm()
            model_name, provider = get_model_info()
            
            print(f"✅ Model initialized: {model_name} ({provider})")
            self.logger.info(f"✅ LLM initialized: {model_name} ({provider})")
            
            # Initialize CrewAI pipeline crew with the same LLM
            self.crew = create_pipeline_crew()
            self.logger.info("✅ CrewAI pipeline crew initialized")
            
            # System prompt - KYC/AML Assistant Persona with Pipeline Agents
            system_prompt = """You are an intelligent KYC/AML Document Processing Assistant powered by CrewAI pipeline agents.

Your Role:
- Assist with document processing, classification, and data extraction
- Support both case-based workflows (KYC/AML compliance) and general document processing
- Help manage customer onboarding cases when needed
- Process standalone documents (policies, guidelines, general documents) without case requirements
- Resume processing for documents that have pending stages

Your Pipeline Agents:
You have 5 specialized agents working together:
1. **QueueAgent**: Scans input paths, expands folders, splits PDFs into pages, builds the processing queue
2. **ClassificationAgent**: Classifies documents via REST API (passport, license, utility bill, etc.)
3. **ExtractionAgent**: Extracts structured data from documents via REST API
4. **MetadataAgent**: Tracks status, handles errors, manages retries
5. **SummaryAgent**: Generates processing reports and statistics

Your Capabilities:
You have access to specialized tools to:
1. Process documents WITHOUT requiring a case reference - documents get globally unique IDs
2. Link processed documents to cases when needed (many-to-many relationships supported)
3. List and switch between customer cases (e.g., KYC-2026-001)
4. Check case status with detailed metadata (workflow stage, document types, extracted data)
5. Browse all documents in the system, filtered by stage or case
6. Retrieve specific documents by their unique ID
7. **Run the full pipeline** on files or folders
8. **Resume processing** for existing documents by their document ID

Document Processing Workflows:
A. CASE-AGNOSTIC: User provides document → Process immediately → Get unique document ID → Optionally link to case later
B. CASE-BASED: User provides case + document → Process and auto-link to case
C. **PIPELINE RUN**: User provides folder path → Queue all files → Classify → Extract → Generate summary
D. **RESUME PROCESSING**: User provides document ID (DOC_...) → Load metadata → Resume from pending stage

IMPORTANT: 
- When a user provides a document path without mentioning a case, process it immediately WITHOUT asking for a case reference
- When a user provides a document ID (starts with "DOC_"), use process_document_by_id to resume processing
- When a user provides a folder, use run_pipeline to process all documents
- Documents can always be linked to cases later if needed
- Never block document processing by requiring a case upfront

Communication Style:
- Professional yet friendly - be helpful and efficient
- Clear and concise - users value quick results
- Proactive - suggest linking to cases AFTER processing, not before
- Transparent - explain what the pipeline agents are doing

When users provide documents:
- Process them immediately with submit_documents_for_processing or run_document_pipeline
- Show the generated document IDs in the response
- Suggest linking to a case only AFTER successful processing
- If they provide a document ID, use process_document_by_id to resume

Always prioritize efficiency and flexibility. Documents are first-class entities that can exist independently of cases."""

            self.conversation_history.append(SystemMessage(content=system_prompt))
            
            # Setup tools
            self._setup_tools()
            
            # Initialize Supervisor Agent for multi-step command orchestration
            self.supervisor = SupervisorAgent(chat_interface=self)
            self.logger.info("✅ Supervisor agent initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize system: {e}")
            print(f"\n⚠️  Warning: System initialization failed: {e}")
            print(f"Some features may not work. Please check your configuration.\n")
            self.llm = None
            self.crew = None
            self.supervisor = None
    
    def _setup_tools(self):
        """Setup LLM tools for the chat interface."""
        if not self.llm:
            return
        
        # Create tools from modular chat_tools
        self.tools = create_chat_tools(self)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    def _is_multi_step_command(self, user_message: str) -> bool:
        """
        Detect if user message contains multiple commands that should be orchestrated.
        
        Multi-step indicators:
        - Multiple action keywords (create, process, summarize, etc.)
        - Conjunctions connecting actions (and, then, after that)
        - Comma-separated instructions
        """
        message_lower = user_message.lower()
        
        # Action keywords
        action_keywords = [
            'create', 'switch', 'process', 'classify', 'extract', 
            'summarize', 'summary', 'list', 'status', 'add', 'upload'
        ]
        
        # Count action keywords
        action_count = sum(1 for kw in action_keywords if kw in message_lower)
        
        # Check for chaining indicators
        chain_indicators = [' and ', ' then ', ', then', ' after ', ' finally ']
        has_chain = any(ind in message_lower for ind in chain_indicators)
        
        # Multi-step if: multiple actions OR chaining indicators with at least one action
        return action_count >= 2 or (has_chain and action_count >= 1)
    
    def get_llm_response(self, user_message: str) -> str:
        """Get response from LLM with tool calling support."""
        if not self.llm:
            return "❌ LLM not available. Use commands: help, exit"
        
        try:
            # Check if this is a multi-step command that needs orchestration
            if self.supervisor and self._is_multi_step_command(user_message):
                self.logger.info(f"Multi-step command detected, routing to supervisor")
                print("\n🎯 Multi-step command detected. Creating execution plan...")
                return self.supervisor.process_command(user_message)
            
            # Single-step command: use regular LLM with tools
            # Add user message with context
            context = f"\nCurrent case: {self.case_reference or 'Not set'}"
            self.conversation_history.append(HumanMessage(content=user_message + context))
            
            # Get response from LLM with tools
            response = self.llm_with_tools.invoke(self.conversation_history)
            
            # Handle tool calls
            while response.tool_calls:
                self.conversation_history.append(response)
                
                for tool_call in response.tool_calls:
                    # Find and execute the tool
                    tool_func = next((t for t in self.tools if t.name == tool_call["name"]), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_call["args"])
                        self.conversation_history.append(
                            ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"])
                        )
                
                # Get next response
                response = self.llm_with_tools.invoke(self.conversation_history)
            
            # Final text response - extract text from content
            if isinstance(response.content, list):
                # Content is a list of content blocks
                text_parts = []
                for block in response.content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                    elif isinstance(block, str):
                        text_parts.append(block)
                assistant_message = '\n'.join(text_parts)
            elif isinstance(response.content, str):
                assistant_message = response.content
            else:
                assistant_message = str(response.content)
            
            self.conversation_history.append(AIMessage(content=assistant_message))
            
            return assistant_message
            
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            return f"❌ Error: {str(e)}"
    
    def set_case_reference(self, case_ref: str) -> str:
        """Set active case reference and create metadata if new."""
        from datetime import datetime
        
        self.case_reference = case_ref.strip().upper()
        
        # Check if case exists
        case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
        metadata_file = case_dir / "case_metadata.json"
        
        if case_dir.exists() and metadata_file.exists():
            # Load existing case
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                doc_count = len(metadata.get('documents', []))
                return f"✅ Loaded existing case: {self.case_reference}\n   📁 {doc_count} documents linked"
            except:
                doc_count = len(list(case_dir.glob("*.pdf"))) + len(list(case_dir.glob("*.jpg")))
                return f"✅ Loaded existing case: {self.case_reference}\n   📁 {doc_count} documents found"
        else:
            # Create new case with metadata
            case_dir.mkdir(parents=True, exist_ok=True)
            
            # Create case metadata
            metadata = {
                "case_reference": self.case_reference,
                "created_date": datetime.now().isoformat(),
                "status": "active",
                "workflow_stage": "intake",
                "documents": [],
                "description": "",
                "last_updated": datetime.now().isoformat()
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Created new case with metadata: {self.case_reference}")
            return f"✅ Created new case: {self.case_reference}\n   📋 Case metadata initialized"
    
    def process_documents(self, file_paths: List[str]) -> str:
        """Process documents using CrewAI pipeline flow."""
        if not file_paths:
            return "❌ No valid file paths provided"
        
        # Validate paths
        valid_paths = []
        for path in file_paths:
            p = Path(path).expanduser().resolve()
            if p.exists():
                valid_paths.append(str(p))
            else:
                return f"❌ File not found: {path}"
        
        try:
            print(f"\n🚀 Processing {len(valid_paths)} document(s) with Pipeline Agents...")
            if self.case_reference:
                print(f"   Case: {self.case_reference}")
            
            # Use the new pipeline flow
            import asyncio
            result = asyncio.run(run_pipeline(valid_paths[0] if len(valid_paths) == 1 else valid_paths[0]))
            
            msg = f"\n✅ Processing Complete!\n\n"
            if self.case_reference:
                msg += f"📁 Case: {self.case_reference}\n"
            msg += f"📄 Documents: {len(valid_paths)}\n"
            
            if result:
                if isinstance(result, dict):
                    if result.get('success'):
                        stats = result.get('summary', {}).get('statistics', {})
                        msg += f"\n📊 Results:\n"
                        msg += f"   • Total: {stats.get('total_documents', 0)}\n"
                        msg += f"   • Completed: {stats.get('completed', 0)}\n"
                        msg += f"   • Failed: {stats.get('failed', 0)}\n"
                    else:
                        msg += f"\n⚠️  Error: {result.get('error', 'Unknown')}\n"
                else:
                    msg += f"\n🔄 Result:\n{result}"
            
            return msg
            
        except Exception as e:
            self.logger.error(f"Processing error: {e}")
            return f"❌ Error processing documents: {str(e)}"
    
    def add_directory_to_queue(self, directory_path: str, priority: int = 1) -> str:
        """Add all documents from a directory to the processing queue."""
        from tools.queue_tools import build_processing_queue, get_queue_status
        
        try:
            result = build_processing_queue(directory_path)
            
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
            self.logger.error(f"Error adding directory to queue: {e}")
            return f"❌ Error: {str(e)}"
    
    def add_files_to_queue(self, file_paths: List[str], priority: int = 1) -> str:
        """Add multiple files to the processing queue."""
        from tools.queue_tools import build_processing_queue
        
        try:
            # Process each file path
            total_queued = 0
            for file_path in file_paths:
                result = build_processing_queue(file_path)
                if result.get('success'):
                    total_queued += result.get('queued_count', 0)
            
            msg = f"✅ Added {total_queued} documents to queue\n"
            return msg
        except Exception as e:
            self.logger.error(f"Error adding files to queue: {e}")
            return f"❌ Error: {str(e)}"
    
    def view_queue_status(self) -> str:
        """View current queue status."""
        from tools.queue_tools import get_queue_status
        
        try:
            status = get_queue_status()
            
            msg = "📊 Queue Status\n"
            msg += "="*60 + "\n\n"
            msg += f"📋 Summary:\n"
            msg += f"   • Pending: {status.get('pending', 0)}\n"
            msg += f"   • Processing: {status.get('processing', 0)}\n"
            msg += f"   • Completed: {status.get('completed', 0)}\n"
            msg += f"   • Failed: {status.get('failed', 0)}\n"
            msg += f"   • Total: {status.get('total', 0)}\n\n"
            
            return msg
        except Exception as e:
            self.logger.error(f"Error viewing queue: {e}")
            return f"❌ Error: {str(e)}"
    
    def process_queue(self, max_documents: Optional[int] = None) -> str:
        """Process documents from queue using pipeline agents."""
        try:
            import asyncio
            from tools.queue_tools import get_next_from_queue, mark_document_processed
            from tools.classification_api_tools import classify_document
            from tools.extraction_api_tools import extract_document_data
            
            processed_count = 0
            failed_count = 0
            
            print("\n🚀 Processing documents from queue with Pipeline Agents...")
            print("="*60 + "\n")
            
            while True:
                if max_documents and processed_count >= max_documents:
                    break
                
                # Get next document
                next_doc = get_next_from_queue()
                if not next_doc.get('success') or not next_doc.get('document'):
                    break
                
                doc = next_doc['document']
                doc_id = doc.get('document_id')
                file_path = doc.get('stored_path')
                
                print(f"Processing: {doc_id}")
                
                try:
                    # Classification
                    class_result = classify_document(file_path)
                    if class_result.get('success'):
                        doc_type = class_result.get('document_type')
                        
                        # Extraction
                        extract_result = extract_document_data(file_path, doc_type)
                        
                        # Mark as processed
                        mark_document_processed(doc_id, 'completed')
                        processed_count += 1
                        print(f"✅ Completed: {doc_id}")
                    else:
                        mark_document_processed(doc_id, 'failed', class_result.get('error'))
                        failed_count += 1
                        print(f"❌ Failed: {doc_id}")
                        
                except Exception as e:
                    mark_document_processed(doc_id, 'failed', str(e))
                    failed_count += 1
            
            msg = f"\n📊 Queue Processing Complete\n"
            msg += "="*60 + "\n\n"
            msg += f"Results:\n"
            msg += f"   • Processed: {processed_count}\n"
            msg += f"   • Failed: {failed_count}\n"
            
            return msg
        except Exception as e:
            self.logger.error(f"Error processing queue: {e}")
            return f"❌ Error: {str(e)}"
    
    def process_next_from_queue(self) -> str:
        """Process just the next document from queue."""
        return self.process_queue(max_documents=1)
    
    def extract_file_paths(self, text: str) -> List[str]:
        """Extract file paths from user input."""
        paths = []
        
        # Pattern for ~/path or /absolute/path or quoted paths
        patterns = [
            r'["\']([^"\']+)["\']',  # Quoted paths
            r'(~[/\w.-]+(?:/[/\w.-]+)*)',  # Tilde paths
            r'(/[/\w.-]+(?:/[/\w.-]+)*)',  # Absolute paths
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            paths.extend(matches)
        
        # Validate and expand
        valid_paths = []
        for path in paths:
            p = Path(path).expanduser().resolve()
            if p.exists() and p.is_file():
                valid_paths.append(str(p))
        
        return valid_paths
    
    def extract_case_reference(self, text: str) -> Optional[str]:
        """Extract case reference from user input."""
        # Common patterns: KYC-2024-001, KYC-AML-001, etc.
        patterns = [
            r'\b([A-Z]{2,4}-\d{4}-\d{3})\b',
            r'\b([A-Z]{3,}-[A-Z]+-\d{3})\b',
            r'\b([A-Z]{3,}-\d{3,})\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None
    
    def handle_command(self, user_input: str) -> Optional[str]:
        """Handle quick commands (exit, help, reload, show cases, show docs, select case)."""
        cmd = user_input.strip().lower()
        
        if cmd in ['help', '/help', '?']:
            return self.show_help()
        
        if cmd in ['reload', '/reload', 'restart', '/restart']:
            return "reload"
        
        if cmd in ['exit', 'quit', 'bye', '/exit']:
            return "exit"
        
        # Quick commands for cases and documents
        if cmd in ['show cases', 'list cases', 'cases']:
            return self._show_cases()
        
        if cmd in ['show docs', 'list docs', 'docs', 'show documents', 'list documents']:
            return self._show_documents()
        
        if cmd in ['status', 'show status']:
            return self._show_status()
        
        # Handle "select case <case_id>" or "use case <case_id>"
        if cmd.startswith('select case ') or cmd.startswith('use case '):
            case_id = cmd.split(' ', 2)[-1].strip().upper()
            return self._select_case(case_id)
        
        # Handle "summarize case" or "summarize case <case_id>"
        if cmd == 'summarize case' or cmd == 'summarize':
            if self.case_reference:
                return self._summarize_case(self.case_reference)
            else:
                return "❌ No case selected. Use 'select case <CASE_ID>' first or 'summarize case <CASE_ID>'"
        
        if cmd.startswith('summarize case '):
            case_id = cmd.split(' ', 2)[-1].strip().upper()
            return self._summarize_case(case_id)
        
        return None
    
    def _show_cases(self, limit: int = 10) -> str:
        """Show recent cases with metadata summary."""
        cases_dir = Path(settings.documents_dir) / "cases"
        
        if not cases_dir.exists():
            return "📋 No cases found. Create one with: 'create case KYC-2026-001'"
        
        case_dirs = sorted(
            [d for d in cases_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        if not case_dirs:
            return "📋 No cases found. Create one with: 'create case KYC-2026-001'"
        
        msg = f"\n📋 Cases (showing {len(case_dirs)} of {len(list(cases_dir.iterdir()))}):\n"
        msg += "=" * 60 + "\n\n"
        
        for case_dir in case_dirs:
            case_id = case_dir.name
            is_current = " ← ACTIVE" if case_id == self.case_reference else ""
            
            # Load case metadata if exists
            metadata_file = case_dir / "case_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    doc_count = len(metadata.get('documents', []))
                    status = metadata.get('status', 'unknown')
                    created = metadata.get('created_date', '')[:10]  # Just the date part
                    msg += f"  📁 {case_id}{is_current}\n"
                    msg += f"     📄 {doc_count} docs | 📅 {created} | 🏷️ {status}\n\n"
                except:
                    msg += f"  📁 {case_id}{is_current}\n\n"
            else:
                # Count files directly
                doc_count = len(list(case_dir.glob("*.*"))) - len(list(case_dir.glob("*.json")))
                msg += f"  📁 {case_id}{is_current}\n"
                msg += f"     📄 ~{max(0, doc_count)} files\n\n"
        
        msg += "💡 Commands: 'select case <ID>' | 'show docs' | 'create case <ID>'\n"
        return msg
    
    def _show_documents(self, limit: int = 10) -> str:
        """Show recent documents from intake folder with status."""
        intake_dir = Path(settings.documents_dir) / "intake"
        
        if not intake_dir.exists():
            return "📄 No documents found. Process some documents first."
        
        # Get all metadata files (one per document)
        metadata_files = sorted(
            intake_dir.glob("*.metadata.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        if not metadata_files:
            return "📄 No documents found in intake. Process some documents first."
        
        msg = f"\n📄 Recent Documents (showing {len(metadata_files)}):\n"
        msg += "=" * 60 + "\n\n"
        
        for meta_file in metadata_files:
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                doc_id = metadata.get('document_id', 'unknown')
                doc_type = metadata.get('classification', {}).get('document_type', 'unclassified')
                queue_status = metadata.get('queue', {}).get('status', 'unknown')
                class_status = metadata.get('classification', {}).get('status', 'pending')
                extract_status = metadata.get('extraction', {}).get('status', 'pending')
                linked_cases = metadata.get('linked_cases', [])
                
                # Status emoji
                status_emoji = "✅" if queue_status == "completed" else "⏳" if queue_status == "pending" else "❌"
                
                msg += f"  {status_emoji} {doc_id}\n"
                msg += f"     Type: {doc_type} | Class: {class_status} | Extract: {extract_status}\n"
                if linked_cases:
                    msg += f"     📁 Cases: {', '.join(linked_cases)}\n"
                msg += "\n"
            except Exception as e:
                continue
        
        msg += "💡 Commands: 'link doc <DOC_ID> to case <CASE_ID>' | 'show cases'\n"
        return msg
    
    def _show_status(self) -> str:
        """Show current system status."""
        msg = "\n📊 System Status\n"
        msg += "=" * 60 + "\n\n"
        msg += f"  🤖 LLM: {'✅ Connected' if self.llm else '❌ Not connected'}\n"
        msg += f"  ⚙️  Crew: {'✅ Ready' if self.crew else '❌ Not initialized'}\n"
        msg += f"  📁 Active Case: {self.case_reference or 'None selected'}\n\n"
        
        # Count documents in intake
        intake_dir = Path(settings.documents_dir) / "intake"
        if intake_dir.exists():
            doc_count = len(list(intake_dir.glob("*.metadata.json")))
            msg += f"  📄 Documents in intake: {doc_count}\n"
        
        # Count cases
        cases_dir = Path(settings.documents_dir) / "cases"
        if cases_dir.exists():
            case_count = len([d for d in cases_dir.iterdir() if d.is_dir()])
            msg += f"  📋 Total cases: {case_count}\n"
        
        msg += "\n💡 Commands: 'show cases' | 'show docs' | 'help'\n"
        return msg
    
    def _select_case(self, case_id: str) -> str:
        """Select a case and load its context."""
        case_id = case_id.upper()
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        
        if not case_dir.exists():
            return f"❌ Case {case_id} not found.\n💡 Create it with: 'create case {case_id}'"
        
        self.case_reference = case_id
        
        # Load case metadata
        metadata_file = case_dir / "case_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                doc_count = len(metadata.get('documents', []))
                status = metadata.get('status', 'unknown')
                created = metadata.get('created_date', '')[:10]
                
                msg = f"✅ Selected case: {case_id}\n\n"
                msg += f"  📅 Created: {created}\n"
                msg += f"  🏷️  Status: {status}\n"
                msg += f"  📄 Documents: {doc_count}\n"
                
                # Show linked documents
                if metadata.get('documents'):
                    msg += f"\n  📋 Linked Documents:\n"
                    for doc_id in metadata.get('documents', [])[:5]:
                        msg += f"     • {doc_id}\n"
                    if len(metadata.get('documents', [])) > 5:
                        msg += f"     ... and {len(metadata.get('documents', [])) - 5} more\n"
                
                return msg
            except:
                pass
        
        return f"✅ Selected case: {case_id}"
    
    def _summarize_case(self, case_id: str) -> str:
        """Generate comprehensive case summary using LLM."""
        from tools.case_tools import generate_comprehensive_case_summary_tool
        
        case_id = case_id.upper()
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        
        if not case_dir.exists():
            return f"❌ Case {case_id} not found."
        
        msg = f"\n📊 Generating comprehensive summary for case {case_id}...\n"
        msg += "(Using LLM to analyze all documents)\n\n"
        
        try:
            # Generate comprehensive summary using LLM
            result = generate_comprehensive_case_summary_tool.run(case_id)
            
            if not result.get('success'):
                return msg + f"❌ Failed: {result.get('error', 'Unknown error')}"
            
            summary = result['case_summary']
            
            # Format output
            msg += "=" * 60 + "\n\n"
            
            # Primary Entity
            primary = summary.get('primary_entity', {})
            if primary:
                entity_type = primary.get('entity_type', 'unknown').upper()
                msg += f"🏢 PRIMARY ENTITY: {primary.get('name', 'Unknown')}\n"
                msg += f"   Type: {entity_type}\n"
                if primary.get('description'):
                    msg += f"   {primary.get('description')}\n"
                msg += "\n"
            
            # Companies (actual businesses being KYC'd, not document issuers)
            companies = summary.get('companies', [])
            if companies:
                msg += f"🏛️  COMPANIES ({len(companies)}):\n"
                for company in companies:
                    msg += f"   • {company.get('name', 'Unknown')}\n"
                    if company.get('cin'):
                        msg += f"     CIN: {company.get('cin')}\n"
                    if company.get('registered_address'):
                        msg += f"     Address: {company.get('registered_address')}\n"
                    if company.get('date_of_incorporation'):
                        msg += f"     Incorporated: {company.get('date_of_incorporation')}\n"
                    if company.get('paid_up_capital'):
                        msg += f"     Capital: ₹{company.get('paid_up_capital')}\n"
                    if company.get('gstin'):
                        msg += f"     GSTIN: {company.get('gstin')}\n"
                    if company.get('business_type'):
                        msg += f"     Business: {company.get('business_type')}\n"
                msg += "\n"
            
            # KYC Agencies (document issuers - government, banks, utilities)
            agencies = summary.get('kyc_agencies', [])
            if agencies:
                msg += f"🏦 KYC AGENCIES ({len(agencies)}):\n"
                msg += "   (Organizations that issued identity documents)\n"
                for agency in agencies:
                    agency_type = agency.get('agency_type', 'other')
                    type_emoji = {"government": "🏛️", "bank": "🏦", "utility": "⚡", "other": "📋"}.get(agency_type, "📋")
                    msg += f"   {type_emoji} {agency.get('name', 'Unknown')}\n"
                    docs = agency.get('documents_issued', [])
                    if docs:
                        msg += f"      Documents: {', '.join(docs)}\n"
                msg += "\n"
            
            # Persons
            persons = summary.get('persons', [])
            if persons:
                msg += f"👥 PERSONS ({len(persons)}):\n"
                for person in persons:
                    role = person.get('role', '')
                    role_str = f" ({role})" if role else ""
                    msg += f"   • {person.get('name', 'Unknown')}{role_str}\n"
                    if person.get('pan_number'):
                        msg += f"     PAN: {person.get('pan_number')}\n"
                    if person.get('date_of_birth'):
                        msg += f"     DOB: {person.get('date_of_birth')}\n"
                    if person.get('address'):
                        msg += f"     Address: {person.get('address')}\n"
                    if person.get('mobile'):
                        msg += f"     Mobile: {person.get('mobile')}\n"
                    if person.get('email'):
                        msg += f"     Email: {person.get('email')}\n"
                msg += "\n"
            
            # Relationships
            relationships = summary.get('relationships', [])
            if relationships:
                msg += f"🔗 RELATIONSHIPS:\n"
                for rel in relationships:
                    msg += f"   • {rel.get('person')} {rel.get('relationship')} {rel.get('entity')}\n"
                msg += "\n"
            
            # KYC Verification Status
            verification = summary.get('kyc_verification', {})
            if verification:
                msg += "📋 KYC VERIFICATION:\n"
                id_verified = "✅" if verification.get('identity_verified') else "❌"
                addr_verified = "✅" if verification.get('address_verified') else "❌"
                company_verified = "✅" if verification.get('company_verified') else "❌"
                
                msg += f"   {id_verified} Identity Verified\n"
                msg += f"   {addr_verified} Address Verified\n"
                msg += f"   {company_verified} Company Verified\n"
                
                missing_docs = verification.get('missing_documents', [])
                if missing_docs:
                    msg += f"\n   ⚠️  Missing Documents:\n"
                    for doc in missing_docs:
                        msg += f"      • {doc}\n"
                
                missing_info = verification.get('missing_information', [])
                if missing_info:
                    msg += f"\n   ⚠️  Missing Information:\n"
                    for info in missing_info:
                        msg += f"      • {info}\n"
                msg += "\n"
            
            # Summary
            if summary.get('summary'):
                msg += f"📝 SUMMARY:\n"
                msg += f"   {summary.get('summary')}\n\n"
            
            msg += f"📄 Documents analyzed: {summary.get('document_count', 0)}\n"
            msg += "💡 Case metadata updated!\n"
            return msg
            
        except Exception as e:
            logger.error(f"Error summarizing case: {e}", exc_info=True)
            return msg + f"❌ Error: {str(e)}"
    
    def show_help(self) -> str:
        """Show help information from config."""
        from utilities import get_capabilities_text
        return get_capabilities_text('cli')
    
    def handle_user_input(self, user_input: str) -> str:
        """Process user input and return response."""
        # Check for critical commands (exit, help)
        cmd_result = self.handle_command(user_input)
        if cmd_result:
            return cmd_result
        
        # Everything goes to LLM with tools - let it decide what to do
        if self.llm:
            return self.get_llm_response(user_input)
        else:
            return "💬 LLM chat is not available. Try: help or exit"
    
    def start(self):
        """Start interactive chat session."""
        if self.llm:
            model_name, provider = get_model_info()
            model_info = f" ({provider}: {model_name})"
        else:
            model_info = ""
        
        # Rich welcome banner from config
        from utilities import get_banner_text
        banner = get_banner_text('cli')
        
        console.print()
        console.rule(f"[bold blue]{banner['title']}[/bold blue]")
        console.print(f"[cyan]✨ {banner['tagline']}{model_info}[/cyan]", justify="center")
        console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]", justify="center")
        console.rule()
        console.print()
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Process input
                response = self.handle_user_input(user_input)
                
                # Check for exit
                if response == "exit":
                    print("\n👋 Goodbye!")
                    break
                
                # Check for reload
                if response == "reload":
                    print("\n🔄 Reloading system...")
                    print("   Restarting chat interface with latest code...\n")
                    # Return special code to trigger restart
                    return 2  # Exit code 2 signals reload
                
                # Print response with rich Markdown rendering
                console.print()  # Empty line
                
                # Check if response contains box drawing (help output) - print directly
                if response and ('╔' in response or '╚' in response):
                    console.print(response)
                else:
                    print_markdown(response, title="🤖 Assistant")
                
                console.print()  # Empty line
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                # Handle EOF gracefully (e.g., when stdin is closed or piped)
                self.logger.info("EOF received - exiting chat interface")
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}")
                console.print(f"\n[red]❌ Error: {str(e)}[/red]\n")


def main():
    """Main entry point with auto-reload support."""
    while True:
        chat = ChatInterface()
        
        try:
            exit_code = chat.start()
            
            # Exit code 2 means reload requested
            if exit_code == 2:
                continue  # Restart the loop
            else:
                break  # Normal exit
                
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
            logger.exception("Error traceback:")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
