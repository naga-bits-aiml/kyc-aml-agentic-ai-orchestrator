"""
Web-based chat interface using Streamlit.

Run with: streamlit run web_chat.py

Features:
- Multi-step command orchestration via SupervisorAgent
- Document processing pipeline (Queue → Classify → Extract)
- Case management with document linking
- Interactive case prompting
- Real-time processing status
"""
import streamlit as st
from pathlib import Path
import json
import os
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
import warnings
import logging
import threading
import signal as _signal_module

# Suppress CrewAI signal handler warnings BEFORE importing CrewAI
# These warnings occur because CrewAI telemetry tries to register signal handlers
# but Streamlit runs code outside the main thread - this is harmless

# Patch signal.signal to silently ignore calls from non-main threads
_original_signal = _signal_module.signal
def _safe_signal(signalnum, handler):
    """Wrapper that silently ignores signal registration from non-main threads."""
    if threading.current_thread() is not threading.main_thread():
        return _signal_module.SIG_DFL  # Return default handler silently
    return _original_signal(signalnum, handler)
_signal_module.signal = _safe_signal

# Also suppress any remaining log messages from crewai telemetry
logging.getLogger('crewai.telemetry.telemetry').setLevel(logging.CRITICAL)

# Core imports
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from utilities import config, settings, logger
from utilities.llm_factory import create_llm, get_model_info
from tools.chat_tools import create_chat_tools
from pipeline_flow import run_pipeline_sync
from agents.supervisor_agent import SupervisorAgent


# Page configuration
st.set_page_config(
    page_title="KYC-AML Document Processing",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1f77b4, #2ecc71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .status-active {
        background-color: #d4edda;
        color: #155724;
    }
    .status-pending {
        background-color: #fff3cd;
        color: #856404;
    }
    .case-card {
        background-color: #f8f9fa;
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    .doc-card {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        padding: 0.75rem;
        margin: 0.25rem 0;
        border-radius: 0.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    code {
        background-color: #f1f3f4;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        font-family: 'SF Mono', 'Monaco', monospace;
    }
</style>
""", unsafe_allow_html=True)


class WebChatInterface:
    """Streamlit-based chat interface with full pipeline capabilities."""
    
    def __init__(self):
        """Initialize the web chat interface."""
        self.case_reference: Optional[str] = None
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize Streamlit session state."""
        # Core state
        if 'initialized' not in st.session_state:
            st.session_state.initialized = False
            st.session_state.llm = None
            st.session_state.supervisor = None
            st.session_state.tools = None
            st.session_state.llm_with_tools = None
        
        # Chat state
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []
        
        # Case state
        if 'case_reference' not in st.session_state:
            st.session_state.case_reference = None
        
        # Pending action state (for interactive prompts)
        if 'pending_action' not in st.session_state:
            st.session_state.pending_action = None
        
        if 'pending_data' not in st.session_state:
            st.session_state.pending_data = None
        
        # Processing state
        if 'processing' not in st.session_state:
            st.session_state.processing = False
        
        # Pending user message for quick actions
        if 'pending_user_message' not in st.session_state:
            st.session_state.pending_user_message = None
        
        # Sync case_reference
        self.case_reference = st.session_state.case_reference
    
    def initialize_system(self) -> bool:
        """Initialize LLM, supervisor, and tools."""
        if st.session_state.initialized:
            return True
        
        try:
            with st.spinner("🔄 Initializing AI system..."):
                # Create LLM
                st.session_state.llm = create_llm()
                
                # Create supervisor (pass self for case_reference access)
                st.session_state.supervisor = SupervisorAgent(chat_interface=self)
                
                # Create tools
                st.session_state.tools = create_chat_tools(self)
                st.session_state.llm_with_tools = st.session_state.llm.bind_tools(st.session_state.tools)
                
                st.session_state.initialized = True
                return True
                
        except Exception as e:
            st.error(f"❌ Failed to initialize system: {str(e)}")
            logger.error(f"Web chat initialization failed: {e}")
            return False
    
    @property
    def llm(self):
        """Access the LLM from session state for use in tools."""
        return st.session_state.get('llm')
    
    def set_case_reference(self, case_ref: str) -> str:
        """Set active case reference and create if new."""
        case_ref = case_ref.strip().upper().replace('-', '_')
        
        # Update both local and session state
        self.case_reference = case_ref
        st.session_state.case_reference = case_ref
        
        # Check if case exists
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        metadata_file = case_dir / "case_metadata.json"
        
        if metadata_file.exists():
            return f"✅ Switched to existing case: `{case_ref}`"
        else:
            # Create new case
            case_dir.mkdir(parents=True, exist_ok=True)
            metadata = {
                "case_reference": case_ref,
                "created_date": datetime.now().isoformat(),
                "status": "active",
                "workflow_stage": "document_intake",
                "description": "",
                "documents": []
            }
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            return f"✅ Created new case: `{case_ref}`"
    
    def _is_multi_step_command(self, user_message: str) -> bool:
        """Detect if user message contains multiple commands."""
        message_lower = user_message.lower()
        
        action_keywords = [
            'create', 'switch', 'process', 'classify', 'extract',
            'summarize', 'summary', 'list', 'status', 'add', 'upload'
        ]
        
        action_count = sum(1 for kw in action_keywords if kw in message_lower)
        chain_indicators = [' and ', ' then ', ', then', ' after ', ' finally ']
        has_chain = any(ind in message_lower for ind in chain_indicators)
        
        return action_count >= 2 or (has_chain and action_count >= 1)
    
    def get_response(self, user_message: str) -> str:
        """Get response from LLM or supervisor - matching CLI capabilities."""
        if not st.session_state.llm:
            return "❌ System not initialized. Please refresh the page."
        
        try:
            # First, check for quick commands (no LLM needed)
            quick_response = self._handle_quick_command(user_message)
            if quick_response:
                return quick_response
            
            # Check for multi-step command that needs orchestration
            if st.session_state.supervisor and self._is_multi_step_command(user_message):
                logger.info("Multi-step command detected, routing to supervisor")
                return st.session_state.supervisor.process_command(user_message)
            
            # Single-step: use LLM with tools
            context = f"\nCurrent case: {st.session_state.case_reference or 'Not set'}"
            st.session_state.conversation_history.append(
                HumanMessage(content=user_message + context)
            )
            
            # Build message list with system prompt (trim to last 20 messages)
            system_prompt = self._get_system_prompt()
            messages = [SystemMessage(content=system_prompt)] + st.session_state.conversation_history[-20:]
            
            # Get LLM response
            response = st.session_state.llm_with_tools.invoke(messages)
            
            # Handle tool calls in a loop (like CLI)
            if hasattr(response, 'tool_calls') and response.tool_calls:
                return self._execute_tools(response, messages)
            
            # Regular response - extract text from content
            if isinstance(response.content, list):
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
            
            st.session_state.conversation_history.append(
                AIMessage(content=assistant_message)
            )
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            return f"❌ Error: {str(e)}"
    
    def _get_system_prompt(self) -> str:
        """Get comprehensive system prompt for LLM - matching CLI capabilities."""
        return """You are an intelligent KYC-AML Document Processing Assistant powered by CrewAI pipeline agents.

Your Role:
- Assist with document processing, classification, and data extraction
- Support both case-based workflows (KYC/AML compliance) and general document processing
- Help manage customer onboarding cases when needed
- Process standalone documents without requiring case references
- Resume processing for documents that have pending stages

Your Pipeline Agents:
You have 5 specialized agents working together:
1. **QueueAgent**: Scans input paths, expands folders, splits PDFs into pages, builds the processing queue
2. **ClassificationAgent**: Classifies documents via REST API (passport, license, utility bill, PAN, Aadhaar, etc.)
3. **ExtractionAgent**: Extracts structured data from documents via REST API
4. **MetadataAgent**: Tracks status, handles errors, manages retries
5. **SummaryAgent**: Generates processing reports and statistics

Your Capabilities:
You have access to specialized tools to:
1. Process documents WITHOUT requiring a case reference - documents get globally unique IDs
2. Link processed documents to cases when needed (many-to-many relationships supported)
3. List and switch between customer cases (e.g., KYC_2026_001)
4. Check case status with detailed metadata (workflow stage, document types, extracted data)
5. Browse all documents in the system, filtered by stage or case
6. Retrieve specific documents by their unique ID
7. **Run the full pipeline** on files or folders
8. **Resume processing** for existing documents by their document ID
9. **Find documents by ID** across all cases

Document Processing Workflows:
A. CASE-AGNOSTIC: User provides document → Process immediately → Get unique document ID → Optionally link to case later
B. CASE-BASED: User provides case + document → Process and auto-link to case
C. **PIPELINE RUN**: User provides folder path → Queue all files → Classify → Extract → Generate summary
D. **RESUME PROCESSING**: User provides document ID (DOC_...) → Load metadata → Resume from pending stage

IMPORTANT: 
- When a user provides a document path without mentioning a case, process it immediately WITHOUT asking for a case reference
- When a user provides a document ID (starts with "DOC_"), use find_document_by_id or process_document_by_id
- When a user provides a folder, use run_document_pipeline to process all documents
- Documents can always be linked to cases later if needed
- Never block document processing by requiring a case upfront

Communication Style:
- Professional yet friendly - be helpful and efficient
- Clear and concise - users value quick results
- Proactive - suggest linking to cases AFTER processing, not before
- Transparent - explain what the pipeline agents are doing
- Use Markdown formatting for readability

Always prioritize efficiency and flexibility. Documents are first-class entities that can exist independently of cases."""
    
    def _execute_tools(self, response, messages: List) -> str:
        """Execute tool calls from LLM response in a loop until no more tool calls."""
        # Append initial response with tool calls
        messages.append(response)
        
        while hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_id = tool_call.get('id', tool_name)
                
                # Find and execute tool
                tool = next((t for t in st.session_state.tools if t.name == tool_name), None)
                if tool:
                    try:
                        result = tool.invoke(tool_args)
                        messages.append(
                            ToolMessage(content=str(result), tool_call_id=tool_id)
                        )
                    except Exception as e:
                        logger.error(f"Tool {tool_name} error: {e}")
                        messages.append(
                            ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id)
                        )
                else:
                    messages.append(
                        ToolMessage(content=f"Tool {tool_name} not found", tool_call_id=tool_id)
                    )
            
            # Get next response (may have more tool calls)
            response = st.session_state.llm_with_tools.invoke(messages)
            if hasattr(response, 'tool_calls') and response.tool_calls:
                messages.append(response)
        
        # Final response - extract text content
        if isinstance(response.content, list):
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
        
        # Add to conversation history
        st.session_state.conversation_history.append(AIMessage(content=assistant_message))
        
        return assistant_message
    
    def _handle_quick_command(self, user_input: str) -> Optional[str]:
        """Handle common quick commands without LLM."""
        cmd = user_input.strip().lower()
        
        # Exit commands (not applicable in web)
        if cmd in ['exit', 'quit', 'bye', '/exit']:
            return "👋 Use the browser to close this session."
        
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
            return self.set_case_reference(case_id)
        
        # Handle "summarize case" or "summarize case <case_id>"
        if cmd == 'summarize case' or cmd == 'summarize':
            if st.session_state.case_reference:
                return self._summarize_case(st.session_state.case_reference)
            else:
                return "❌ No case selected. Use 'select case <CASE_ID>' first or 'summarize case <CASE_ID>'"
        
        if cmd.startswith('summarize case '):
            case_id = cmd.split(' ', 2)[-1].strip().upper()
            return self._summarize_case(case_id)
        
        if cmd in ['help', '?', '/help']:
            return self._show_help()
        
        return None
    
    def _show_cases(self, limit: int = 10) -> str:
        """Show recent cases with metadata summary."""
        cases_dir = Path(settings.documents_dir) / "cases"
        
        if not cases_dir.exists():
            return "📋 No cases found. Create one with: 'create case KYC_2026_001'"
        
        case_dirs = sorted(
            [d for d in cases_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        if not case_dirs:
            return "📋 No cases found. Create one with: 'create case KYC_2026_001'"
        
        msg = f"📋 **Cases** (showing {len(case_dirs)}):\n\n"
        
        for case_dir in case_dirs:
            case_id = case_dir.name
            is_current = " ← **ACTIVE**" if case_id == st.session_state.case_reference else ""
            
            # Load case metadata if exists
            metadata_file = case_dir / "case_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    doc_count = len(metadata.get('documents', []))
                    status = metadata.get('status', 'unknown')
                    created = metadata.get('created_date', '')[:10]
                    msg += f"- 📁 `{case_id}`{is_current}\n"
                    msg += f"  - 📄 {doc_count} docs | 📅 {created} | 🏷️ {status}\n\n"
                except:
                    msg += f"- 📁 `{case_id}`{is_current}\n\n"
            else:
                doc_count = len(list(case_dir.glob("*.*"))) - len(list(case_dir.glob("*.json")))
                msg += f"- 📁 `{case_id}`{is_current}\n"
                msg += f"  - 📄 ~{max(0, doc_count)} files\n\n"
        
        msg += "\n💡 Commands: `select case <ID>` | `show docs` | `create case <ID>`"
        return msg
    
    def _show_documents(self, limit: int = 10) -> str:
        """Show recent documents from intake folder with status."""
        intake_dir = Path(settings.documents_dir) / "intake"
        
        if not intake_dir.exists():
            return "📄 No documents found. Process some documents first."
        
        metadata_files = sorted(
            intake_dir.glob("*.metadata.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        if not metadata_files:
            return "📄 No documents found in intake. Process some documents first."
        
        msg = f"📄 **Recent Documents** (showing {len(metadata_files)}):\n\n"
        
        for meta_file in metadata_files:
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                doc_id = metadata.get('document_id', 'unknown')
                doc_type = metadata.get('classification', {}).get('document_type', 'unclassified')
                queue_status = metadata.get('queue', {}).get('status', 'unknown')
                linked_cases = metadata.get('linked_cases', [])
                
                # Status emoji
                status_emoji = "✅" if queue_status == "completed" else "⏳" if queue_status == "pending" else "❌"
                
                msg += f"- {status_emoji} `{doc_id}`\n"
                msg += f"  - Type: {doc_type}\n"
                if linked_cases:
                    msg += f"  - 📁 Cases: {', '.join(linked_cases)}\n"
                msg += "\n"
            except Exception:
                continue
        
        msg += "\n💡 Commands: `find document <DOC_ID>` | `show cases`"
        return msg
    
    def _show_status(self) -> str:
        """Show current system status."""
        msg = "📊 **System Status**\n\n"
        msg += f"- 🤖 LLM: {'✅ Connected' if st.session_state.llm else '❌ Not connected'}\n"
        msg += f"- ⚙️ Supervisor: {'✅ Ready' if st.session_state.supervisor else '❌ Not initialized'}\n"
        msg += f"- 📁 Active Case: `{st.session_state.case_reference or 'None selected'}`\n\n"
        
        # Count documents in intake
        intake_dir = Path(settings.documents_dir) / "intake"
        if intake_dir.exists():
            doc_count = len(list(intake_dir.glob("*.metadata.json")))
            msg += f"- 📄 Documents in intake: {doc_count}\n"
        
        # Count cases
        cases_dir = Path(settings.documents_dir) / "cases"
        if cases_dir.exists():
            case_count = len([d for d in cases_dir.iterdir() if d.is_dir()])
            msg += f"- 📋 Total cases: {case_count}\n"
        
        msg += "\n💡 Commands: `show cases` | `show docs` | `help`"
        return msg
    
    def _summarize_case(self, case_id: str) -> str:
        """Generate comprehensive case summary using two-step LLM approach.
        
        Step 1: Generate/enhance case metadata JSON (stored)
        Step 2: Format stored metadata for display using LLM
        """
        from tools.case_tools import generate_comprehensive_case_summary_tool, format_case_summary_for_display_tool
        
        case_id = case_id.upper()
        case_dir = Path(settings.documents_dir) / "cases" / case_id
        
        if not case_dir.exists():
            return f"❌ Case {case_id} not found."
        
        msg = f"\n📊 Generating comprehensive summary for case {case_id}...\n"
        
        try:
            # Step 1: Generate/enhance case metadata and store as JSON
            msg += "   Step 1: Analyzing documents and generating metadata...\n"
            result = generate_comprehensive_case_summary_tool.run(case_id)
            
            if not result.get('success'):
                return msg + f"❌ Failed: {result.get('error', 'Unknown error')}"
            
            msg += "   ✅ Case metadata enhanced and stored\n"
            
            # Step 2: Format stored metadata for display using LLM
            msg += "   Step 2: Formatting summary for display...\n\n"
            display_result = format_case_summary_for_display_tool.run(case_id)
            
            if not display_result.get('success'):
                # Fallback: show raw summary if formatting fails
                summary = result['case_summary']
                msg += "=" * 60 + "\n\n"
                msg += f"📝 {summary.get('summary', 'No summary available')}\n\n"
                msg += f"📄 Documents analyzed: {summary.get('document_count', 0)}\n"
                return msg
            
            # Show LLM-formatted output
            msg += "=" * 60 + "\n\n"
            msg += display_result['formatted_summary']
            msg += "\n\n" + "=" * 60 + "\n"
            msg += "💡 Case metadata updated!\n"
            return msg
            
        except Exception as e:
            logger.error(f"Error summarizing case: {e}", exc_info=True)
            return msg + f"❌ Error: {str(e)}"
    
    def _show_help(self) -> str:
        """Show help message from config."""
        from utilities import get_capabilities_text, get_banner_text
        banner = get_banner_text('web')
        return f"# 📖 {banner['app_name']} - Help\n\n" + get_capabilities_text('web')
    
    def process_uploaded_files(self, uploaded_files, case_ref: Optional[str] = None) -> Dict[str, Any]:
        """Process uploaded files through the pipeline."""
        if not uploaded_files:
            return {"success": False, "error": "No files provided"}
        
        # Use provided case or current case
        case_ref = case_ref or st.session_state.case_reference
        
        # Save uploaded files to temp directory
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        
        file_paths = []
        for uploaded_file in uploaded_files:
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            file_paths.append(str(file_path))
        
        try:
            # Process each file through pipeline
            all_results = []
            for file_path in file_paths:
                result = run_pipeline_sync(input_path=file_path, case_reference=case_ref)
                all_results.append(result)
            
            # Aggregate results
            total_docs = sum(r.get('processed', 0) + r.get('succeeded', 0) for r in all_results)
            failed_docs = sum(r.get('failed', 0) for r in all_results)
            linked_docs = []
            for r in all_results:
                linked_docs.extend(r.get('linked_documents', []))
            
            return {
                "success": failed_docs == 0,
                "files_processed": len(file_paths),
                "documents_created": total_docs,
                "documents_linked": len(linked_docs),
                "case_reference": case_ref,
                "results": all_results
            }
            
        except Exception as e:
            logger.error(f"Error processing files: {e}")
            return {"success": False, "error": str(e)}
        
        finally:
            # Cleanup temp files
            for file_path in file_paths:
                try:
                    os.remove(file_path)
                except:
                    pass
    
    def get_cases(self) -> List[Dict[str, Any]]:
        """Get all cases with their metadata."""
        cases_dir = Path(settings.documents_dir) / "cases"
        if not cases_dir.exists():
            return []
        
        cases = []
        for case_dir in sorted(cases_dir.iterdir(), reverse=True):
            if not case_dir.is_dir():
                continue
            
            metadata_file = case_dir / "case_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, encoding='utf-8') as f:
                        metadata = json.load(f)
                    cases.append(metadata)
                except:
                    cases.append({
                        "case_reference": case_dir.name,
                        "status": "unknown",
                        "documents": []
                    })
            else:
                cases.append({
                    "case_reference": case_dir.name,
                    "status": "no_metadata",
                    "documents": []
                })
        
        return cases
    
    def get_case_details(self, case_ref: str) -> Optional[Dict[str, Any]]:
        """Get detailed case information."""
        case_dir = Path(settings.documents_dir) / "cases" / case_ref
        metadata_file = case_dir / "case_metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, encoding='utf-8') as f:
            return json.load(f)
    
    def get_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent documents from intake."""
        intake_dir = Path(settings.documents_dir) / "intake"
        if not intake_dir.exists():
            return []
        
        documents = []
        for metadata_file in sorted(intake_dir.glob("*.metadata.json"), reverse=True)[:limit]:
            try:
                with open(metadata_file, encoding='utf-8') as f:
                    metadata = json.load(f)
                documents.append(metadata)
            except:
                continue
        
        return documents


def render_sidebar(chat: WebChatInterface):
    """Render sidebar with controls and information."""
    with st.sidebar:
        st.markdown("## 🎛️ Control Panel")
        
        # System status
        model_name, provider = get_model_info() if st.session_state.initialized else ("Not initialized", "N/A")
        
        status_color = "🟢" if st.session_state.initialized else "🔴"
        st.markdown(f"**Status:** {status_color} {'Ready' if st.session_state.initialized else 'Not Ready'}")
        st.markdown(f"**Model:** `{model_name}`")
        
        st.markdown("---")
        
        # Case management
        st.markdown("### 📁 Case Management")
        
        # Current case display
        current_case = st.session_state.case_reference
        if current_case:
            st.success(f"**Active Case:** `{current_case}`")
        else:
            st.warning("No case selected")
        
        # Case selection/creation
        col1, col2 = st.columns(2)
        with col1:
            new_case = st.text_input(
                "Case ID",
                placeholder="KYC_2026_001",
                label_visibility="collapsed"
            )
        with col2:
            if st.button("Set Case", use_container_width=True):
                if new_case:
                    result = chat.set_case_reference(new_case)
                    st.success(result)
                    st.rerun()
        
        # Quick case list
        cases = chat.get_cases()[:5]
        if cases:
            st.markdown("**Recent Cases:**")
            for case in cases:
                case_ref = case.get('case_reference', 'Unknown')
                doc_count = len(case.get('documents', []))
                is_current = case_ref == current_case
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    if is_current:
                        st.markdown(f"📂 **`{case_ref}`** ← Current")
                    else:
                        if st.button(f"📁 `{case_ref}`", key=f"case_{case_ref}"):
                            chat.set_case_reference(case_ref)
                            st.rerun()
                with col2:
                    st.caption(f"{doc_count} docs")
        
        st.markdown("---")
        
        # Document upload
        st.markdown("### 📤 Upload Documents")
        
        uploaded_files = st.file_uploader(
            "Choose files",
            accept_multiple_files=True,
            type=['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'],
            label_visibility="collapsed"
        )
        
        if uploaded_files:
            st.info(f"📎 {len(uploaded_files)} file(s) selected")
            
            if st.button("🚀 Process Documents", use_container_width=True, type="primary"):
                with st.spinner("Processing documents..."):
                    results = chat.process_uploaded_files(uploaded_files)
                
                if results.get("success"):
                    case_ref = results.get('case_reference', 'Unlinked')
                    link_msg = f"Linked to: `{case_ref}`" if st.session_state.case_reference else "📌 *Not linked to a case yet*"
                    st.success(f"""
✅ **Processing Complete!**
- Files: {results.get('files_processed', 0)}
- Documents: {results.get('documents_created', 0)}
- {link_msg}
                    """)
                    
                    # Add to chat
                    file_names = [f.name for f in uploaded_files]
                    msg = f"Processed {len(file_names)} file(s): {', '.join(file_names)}"
                    chat_msg = f"✅ {msg}"
                    if st.session_state.case_reference:
                        chat_msg += f"\n\nDocuments linked to case `{case_ref}`"
                    else:
                        chat_msg += "\n\n📌 Documents processed but not linked to a case. Set a case to link them."
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": chat_msg
                    })
                else:
                    st.error(f"❌ Error: {results.get('error', 'Unknown error')}")
        
        st.markdown("---")
        
        # Statistics
        st.markdown("### 📊 Statistics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Cases", len(chat.get_cases()))
        with col2:
            st.metric("Messages", len(st.session_state.messages))
        
        # Actions
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_history = []
                st.rerun()
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()


def render_case_viewer(chat: WebChatInterface):
    """Render case details in an expander."""
    if not st.session_state.case_reference:
        return
    
    case_details = chat.get_case_details(st.session_state.case_reference)
    if not case_details:
        return
    
    with st.expander(f"📂 Case Details: `{st.session_state.case_reference}`", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Status:** {case_details.get('status', 'unknown')}")
        with col2:
            st.markdown(f"**Documents:** {len(case_details.get('documents', []))}")
        with col3:
            created = case_details.get('created_date', '')[:10]
            st.markdown(f"**Created:** {created}")
        
        # Case summary if available
        case_summary = case_details.get('case_summary', {})
        if case_summary:
            st.markdown("---")
            
            # Primary entity
            primary = case_summary.get('primary_entity', {})
            if primary:
                st.markdown(f"**Primary Entity:** {primary.get('name', 'Unknown')} ({primary.get('entity_type', 'unknown')})")
            
            # Persons
            persons = case_summary.get('persons', [])
            if persons:
                st.markdown("**Identified Persons:**")
                for person in persons:
                    name = person.get('name', 'Unknown')
                    pan = person.get('pan_number', '')
                    st.markdown(f"- {name}" + (f" (PAN: `{pan}`)" if pan else ""))
            
            # KYC status
            kyc = case_summary.get('kyc_verification', {})
            if kyc:
                identity = "✅" if kyc.get('identity_verified') else "❌"
                address = "✅" if kyc.get('address_verified') else "❌"
                st.markdown(f"**KYC Status:** Identity {identity} | Address {address}")
                
                missing = kyc.get('missing_documents', [])
                if missing:
                    st.warning(f"Missing: {', '.join(missing[:3])}")
        
        # Document list
        documents = case_details.get('documents', [])
        if documents:
            st.markdown("---")
            st.markdown("**Linked Documents:**")
            for doc_id in documents[:10]:
                st.markdown(f"- `{doc_id}`")
            if len(documents) > 10:
                st.caption(f"... and {len(documents) - 10} more")


def render_chat_messages():
    """Render chat message history."""
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                st.markdown(content)


def process_pending_message(chat: WebChatInterface):
    """Process any pending message that needs a response."""
    if 'pending_user_message' not in st.session_state:
        return
    
    pending = st.session_state.pending_user_message
    if not pending:
        return
    
    # Clear the pending message
    st.session_state.pending_user_message = None
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = chat.get_response(pending)
        st.markdown(response)
    
    # Add to messages
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


def handle_quick_action(chat: WebChatInterface, action: str):
    """Handle quick action button clicks - generate response directly."""
    # Add user message to history
    st.session_state.messages.append({
        "role": "user", 
        "content": action
    })
    
    # For quick commands like "list cases", use the quick handler directly
    quick_response = chat._handle_quick_command(action)
    
    if quick_response:
        # Add quick response directly
        st.session_state.messages.append({
            "role": "assistant",
            "content": quick_response
        })
    else:
        # Set pending for LLM response on next run
        st.session_state.pending_user_message = action


def render_main_content(chat: WebChatInterface):
    """Render main chat interface."""
    # Header from config
    from utilities import get_banner_text
    banner = get_banner_text('web')
    st.markdown(
        f'<div class="main-header">{banner["title"]}</div>',
        unsafe_allow_html=True
    )
    st.markdown(f'<p style="text-align: center; color: #666; margin-top: -10px;">{banner["subtitle"]}</p>', unsafe_allow_html=True)
    
    # Case viewer
    render_case_viewer(chat)
    
    # Process any pending message first
    process_pending_message(chat)
    
    # Chat messages
    render_chat_messages()
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about KYC-AML document processing..."):
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chat.get_response(prompt)
            st.markdown(response)
        
        # Add assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
    
    # Welcome suggestions (only if no messages)
    if not st.session_state.messages:
        st.markdown("---")
        st.markdown("### 💡 Get Started")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 List all cases", use_container_width=True):
                handle_quick_action(chat, "list cases")
                st.rerun()
        
        with col2:
            if st.button("📁 Create a new case", use_container_width=True):
                # Prompt user to enter case ID
                st.session_state.pending_user_message = "I want to create a new case. Please ask me for the case ID."
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Create a new case"
                })
                st.rerun()
        
        with col3:
            if st.button("❓ What can you do?", use_container_width=True):
                handle_quick_action(chat, "help")
                st.rerun()


def main():
    """Main application entry point."""
    # Create chat interface
    chat = WebChatInterface()
    
    # Initialize system
    if not st.session_state.initialized:
        chat.initialize_system()
    
    # Sync case reference from session state
    chat.case_reference = st.session_state.case_reference
    
    # Render UI
    render_sidebar(chat)
    render_main_content(chat)
    
    # Footer from config
    from utilities import get_banner_text
    banner = get_banner_text('web')
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #666;'>"
        f"{banner['app_name']} | {banner['footer']}"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
