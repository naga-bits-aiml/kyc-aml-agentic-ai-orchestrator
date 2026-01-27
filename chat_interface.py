"""
Clean CLI chat interface for KYC-AML document processing using pure CrewAI.
"""
import sys
import re
from pathlib import Path
from typing import List, Optional
from crew import KYCAMLCrew
from flows.document_processing_flow import kickoff_flow
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from utilities import config, settings, logger
from utilities.llm_factory import create_llm, get_model_info
from tools.chat_tools import create_chat_tools


class ChatInterface:
    """Simple CLI chat interface for CrewAI document processing."""
    
    def __init__(self):
        """Initialize chat interface."""
        self.logger = logger
        self.crew = None
        self.llm = None
        self.case_reference: Optional[str] = None
        self.conversation_history = []
        
        self._initialize_system()
        
    def _initialize_system(self):
        """Initialize CrewAI crew and LLM."""
        try:
            # Create LLM using factory
            self.llm = create_llm()
            model_name, provider = get_model_info()
            
            print(f"✅ Model initialized: {model_name} ({provider})")
            self.logger.info(f"✅ LLM initialized: {model_name} ({provider})")
            
            # Initialize CrewAI crew with the same LLM
            self.crew = KYCAMLCrew(llm=self.llm)
            self.logger.info("✅ CrewAI crew initialized with shared LLM")
            
            # System prompt - KYC/AML Assistant Persona
            system_prompt = """You are an intelligent KYC/AML Document Processing Assistant powered by CrewAI agents.

Your Role:
- Assist with document processing, classification, and data extraction
- Support both case-based workflows (KYC/AML compliance) and general document processing
- Help manage customer onboarding cases when needed
- Process standalone documents (policies, guidelines, general documents) without case requirements
- Resume processing for documents that have pending stages

Your Capabilities:
You have access to specialized tools to:
1. Process documents WITHOUT requiring a case reference - documents get globally unique IDs
2. Link processed documents to cases when needed (many-to-many relationships supported)
3. List and switch between customer cases (e.g., KYC-2026-001)
4. Check case status with detailed metadata (workflow stage, document types, extracted data)
5. Browse all documents in the system, filtered by stage or case
6. Retrieve specific documents by their unique ID
7. **Resume processing for existing documents by their document ID**

Document Processing Workflows:
A. CASE-AGNOSTIC: User provides document → Process immediately → Get unique document ID → Optionally link to case later
B. CASE-BASED: User provides case + document → Process and auto-link to case
C. **RESUME PROCESSING**: User provides document ID (DOC_...) → Load metadata → Resume from pending stage

IMPORTANT: 
- When a user provides a document path without mentioning a case, process it immediately WITHOUT asking for a case reference
- When a user provides a document ID (starts with "DOC_"), use process_document_by_id to resume processing
- Documents can always be linked to cases later if needed
- Never block document processing by requiring a case upfront

Communication Style:
- Professional yet friendly - be helpful and efficient
- Clear and concise - users value quick results
- Proactive - suggest linking to cases AFTER processing, not before
- Transparent - explain what the system is doing

When users provide documents:
- Process them immediately with submit_documents_for_processing (case_reference is optional)
- Show the generated document IDs in the response
- Suggest linking to a case only AFTER successful processing
- If they provide a document ID, use process_document_by_id to resume

Always prioritize efficiency and flexibility. Documents are first-class entities that can exist independently of cases."""

            self.conversation_history.append(SystemMessage(content=system_prompt))
            
            # Setup tools
            self._setup_tools()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize system: {e}")
            print(f"\n⚠️  Warning: System initialization failed: {e}")
            print(f"Some features may not work. Please check your configuration.\n")
            self.llm = None
            self.crew = None
    
    def _setup_tools(self):
        """Setup LLM tools for the chat interface."""
        if not self.llm:
            return
        
        # Create tools from modular chat_tools
        self.tools = create_chat_tools(self)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    def get_llm_response(self, user_message: str) -> str:
        """Get response from LLM with tool calling support."""
        if not self.llm:
            return "❌ LLM not available. Use commands: help, exit"
        
        try:
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
        """Set active case reference."""
        self.case_reference = case_ref.strip().upper()
        
        # Check if case exists
        case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
        if case_dir.exists():
            doc_count = len(list(case_dir.glob("*.pdf"))) + len(list(case_dir.glob("*.jpg")))
            return f"✅ Loaded existing case: {self.case_reference}\n   📁 {doc_count} documents found"
        else:
            case_dir.mkdir(parents=True, exist_ok=True)
            return f"✅ Created new case: {self.case_reference}"
    
    def process_documents(self, file_paths: List[str]) -> str:
        """Process documents using CrewAI flow."""
        if not self.case_reference:
            return "⚠️  Please set a case reference first (e.g., KYC-2024-001)"
        
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
            print(f"\n🚀 Processing {len(valid_paths)} document(s) with CrewAI...")
            print(f"   Case: {self.case_reference}")
            
            # Use CrewAI flow
            result = kickoff_flow(
                case_reference=self.case_reference,
                document_paths=valid_paths
            )
            
            msg = f"\n✅ Processing Complete!\n\n"
            msg += f"📁 Case: {self.case_reference}\n"
            msg += f"📄 Documents: {len(valid_paths)}\n"
            
            if result:
                msg += f"\n🔄 Result:\n{result}"
            
            return msg
            
        except Exception as e:
            self.logger.error(f"Processing error: {e}")
            return f"❌ Error processing documents: {str(e)}"
    
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
        """Handle only critical system commands (exit, help, reload)."""
        cmd = user_input.strip().lower()
        
        if cmd in ['help', '/help', '?']:
            return self.show_help()
        
        if cmd in ['reload', '/reload', 'restart', '/restart']:
            return "reload"
        
        if cmd in ['exit', 'quit', 'bye', '/exit']:
            return "exit"
        
        return None
    
    def show_help(self) -> str:
        """Show help information."""
        return """
╔════════════════════════════════════════════════════╗
║         KYC-AML Chat Interface - Help              ║
╚════════════════════════════════════════════════════╝

📋 Quick Start:
   1. Ask: "List all cases" or "Show me the cases"
   2. Say: "Switch to case KYC-2024-001"
   3. Say: "What's the status?"
   4. Provide document path: "Process ~/Documents/passport.pdf"

💬 Natural Language:
   Just ask naturally! The AI assistant has tools to:
   • List all cases
   • Show current status  
   • Switch between cases
   • Process documents

🔧 Commands:
   help, ?          Show this help
   reload, restart  Reload code and restart interface
   exit, quit       Exit chat

📄 Document Processing:
   • Provide full file path: /path/to/document.pdf
   • Use ~ for home directory: ~/Documents/file.pdf
   • Quote paths with spaces: "~/My Documents/file.pdf"

✨ Examples:
   "Show me all cases"
   "Switch to case KYC-2024-001"
   "Process ~/Documents/passport.pdf"
   "What's the current status?"
"""
    
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
        
        print("\n" + "="*60)
        print("🤖 KYC-AML Chat Interface - Pure CrewAI")
        print(f"✨ LLM-Powered with Tool Calling{model_info}")
        print("="*60)
        print("Type 'help' for commands, 'exit' to quit\n")
        
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
                
                # Print response with robot emoji
                print(f"\n🤖 Assistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                self.logger.error(f"Error: {e}")
                print(f"\n❌ Error: {str(e)}\n")


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
            print(f"\n❌ Fatal error: {str(e)}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
