"""
Web-based chat interface using Streamlit.

Run with: streamlit run web_chat.py
"""
import streamlit as st
from pathlib import Path
import json
from datetime import datetime
from orchestrator import KYCAMLOrchestrator
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from utilities import config, settings, logger
import os


# Page configuration
st.set_page_config(
    page_title="KYC-AML Document Processing",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 20%;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'orchestrator' not in st.session_state:
        try:
            st.session_state.orchestrator = KYCAMLOrchestrator(temperature=0.3)
            st.session_state.llm = st.session_state.orchestrator.llm
        except Exception as e:
            st.error(f"Failed to initialize orchestrator: {str(e)}")
            st.session_state.orchestrator = None
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'conversation_context' not in st.session_state:
        system_prompt = """You are an AI assistant for a KYC-AML document processing system. 
Help users with document submission, classification, and compliance questions. Be professional and helpful."""
        st.session_state.conversation_context = [SystemMessage(content=system_prompt)]
    
    if 'processed_documents' not in st.session_state:
        st.session_state.processed_documents = []


def display_chat_message(role: str, content: str):
    """Display a chat message."""
    if role == "user":
        st.markdown(f'<div class="chat-message user-message">👤 You: {content}</div>', 
                   unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-message assistant-message">🤖 Assistant: {content}</div>', 
                   unsafe_allow_html=True)


def get_llm_response(user_message: str) -> str:
    """Get response from LLM."""
    try:
        st.session_state.conversation_context.append(HumanMessage(content=user_message))
        response = st.session_state.llm.invoke(st.session_state.conversation_context)
        assistant_message = response.content
        st.session_state.conversation_context.append(AIMessage(content=assistant_message))
        return assistant_message
    except Exception as e:
        return f"Error: {str(e)}"


def process_uploaded_files(uploaded_files):
    """Process uploaded files."""
    if not st.session_state.orchestrator:
        return {"error": "Orchestrator not initialized"}
    
    # Save uploaded files temporarily
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    file_paths = []
    for uploaded_file in uploaded_files:
        file_path = temp_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        file_paths.append(str(file_path))
    
    try:
        # Process documents
        results = st.session_state.orchestrator.process_documents(file_paths)
        
        # Track processed documents
        st.session_state.processed_documents.extend(file_paths)
        
        return results
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Cleanup temp files
        for file_path in file_paths:
            try:
                os.remove(file_path)
            except:
                pass


def render_sidebar():
    """Render sidebar with controls and information."""
    with st.sidebar:
        st.markdown("## 🎛️ Control Panel")
        
        # Health check
        st.markdown("### System Status")
        if st.button("🔍 Check Health"):
            if st.session_state.orchestrator:
                is_healthy = st.session_state.orchestrator.check_classifier_health()
                if is_healthy:
                    st.success("✅ System is healthy")
                else:
                    st.error("❌ Classifier API not responding")
            else:
                st.error("❌ Orchestrator not initialized")
        
        # Statistics
        st.markdown("### 📊 Statistics")
        st.metric("Messages", len(st.session_state.messages))
        st.metric("Documents Processed", len(st.session_state.processed_documents))
        
        # Document upload
        st.markdown("### 📁 Upload Documents")
        uploaded_files = st.file_uploader(
            "Choose files",
            accept_multiple_files=True,
            type=['pdf', 'jpg', 'jpeg', 'png', 'docx', 'doc']
        )
        
        if uploaded_files:
            if st.button("🚀 Process Documents"):
                with st.spinner("Processing documents..."):
                    results = process_uploaded_files(uploaded_files)
                    
                    if "error" in results:
                        st.error(f"Error: {results['error']}")
                    else:
                        st.success("Documents processed successfully!")
                        
                        # Display summary
                        summary = results.get("summary", {})
                        st.json(summary)
                        
                        # Add to chat
                        file_names = [f.name for f in uploaded_files]
                        msg = f"Processed documents: {', '.join(file_names)}"
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": msg
                        })
        
        # Settings
        st.markdown("### ⚙️ Settings")
        st.info(f"""
**Model**: {settings.openai_model}  
**Max File Size**: {settings.max_document_size_mb}MB  
**Allowed Types**: {', '.join(settings.allowed_extensions[:3])}...
        """)
        
        # Clear chat
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.conversation_context = [st.session_state.conversation_context[0]]
            st.rerun()
        
        # Download history
        if st.session_state.messages:
            if st.button("💾 Download Chat"):
                chat_data = json.dumps(st.session_state.messages, indent=2)
                st.download_button(
                    "Download JSON",
                    chat_data,
                    file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )


def render_main_content():
    """Render main chat interface."""
    st.markdown('<div class="main-header">📄 KYC-AML Document Processing Assistant</div>', 
               unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Display chat messages
    for message in st.session_state.messages:
        display_chat_message(message["role"], message["content"])
    
    # Chat input
    st.markdown("---")
    
    col1, col2 = st.columns([6, 1])
    
    with col1:
        user_input = st.text_input(
            "Your message:",
            placeholder="Ask me anything about KYC-AML document processing...",
            key="user_input",
            label_visibility="collapsed"
        )
    
    with col2:
        send_button = st.button("📤 Send", use_container_width=True)
    
    if send_button and user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Get assistant response
        with st.spinner("Thinking..."):
            response = get_llm_response(user_input)
        
        # Add assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        
        # Rerun to display new messages
        st.rerun()
    
    # Suggested prompts
    if not st.session_state.messages:
        st.markdown("### 💡 Suggested Questions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 What documents do I need?"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What documents do I need for KYC verification?"
                })
                st.rerun()
        
        with col2:
            if st.button("❓ How does it work?"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "How does the document processing work?"
                })
                st.rerun()
        
        with col3:
            if st.button("📁 What formats are supported?"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What file formats can I upload?"
                })
                st.rerun()


def main():
    """Main application entry point."""
    initialize_session_state()
    render_sidebar()
    render_main_content()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>"
        "KYC-AML Agentic AI Orchestrator | Powered by CrewAI & GPT-4"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
