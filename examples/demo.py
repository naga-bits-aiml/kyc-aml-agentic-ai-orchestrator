"""
Demo script to showcase the chat interface capabilities.

This script simulates a user interaction with the chat interface.
"""
import time
import sys
from pathlib import Path


def print_slow(text: str, delay: float = 0.03):
    """Print text with typing effect."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def demo_cli_chat():
    """Demonstrate CLI chat interface features."""
    print_header("🖥️  CLI Chat Interface Demo")
    
    print_slow("Welcome to the KYC-AML Chat Interface!")
    time.sleep(1)
    
    print_slow("\n👤 You: help")
    time.sleep(0.5)
    print("\n🤖 Assistant:")
    print("""
╔════════════════════════════════════════════════════════════╗
║              KYC-AML Chat Interface - Help                 ║
╚════════════════════════════════════════════════════════════╝

💬 Chat Commands:
  help, /help, ?          Show this help message
  status                  Show processing status
  health                  Check system health
  /process <file>         Process a specific document
    """)
    time.sleep(2)
    
    print_slow("\n👤 You: What documents do I need for KYC verification?")
    time.sleep(0.5)
    print("\n🤖 Assistant:")
    print_slow("""
For KYC (Know Your Customer) verification, you typically need:

1. Identity Proof:
   • Passport
   • Driver's License
   • National ID Card

2. Address Proof:
   • Utility Bill (electricity, water, gas)
   • Bank Statement
   • Lease Agreement

3. Financial Documents (if required):
   • Income Statement
   • Tax Return

Would you like to submit any documents for processing?
    """, 0.02)
    time.sleep(2)
    
    print_slow("\n👤 You: Yes, process my passport at C:\\Documents\\passport.pdf")
    time.sleep(0.5)
    print("\n🤖 Assistant:")
    print_slow("🔄 Processing document...", 0.05)
    time.sleep(1)
    print("""
✅ Processing complete!

╔═══════════════════════════════════════════════════════════╗
║        KYC-AML Document Processing Summary                ║
╚═══════════════════════════════════════════════════════════╝

Status: COMPLETED

Documents:
  • Total Submitted: 1
  • Validated: 1

Classification Results:
  • Successfully Classified: 1
  • Success Rate: 100.0%

Document Types Identified:
  • Identity Proof: 1
    """)
    time.sleep(2)
    
    print_slow("\n👤 You: status")
    time.sleep(0.5)
    print("\n🤖 Assistant:")
    print("""
📊 Processing Status:
  • Total documents processed: 1
  • Documents in queue: 0
  • Chat messages: 6

Recent documents:
  • passport.pdf
    """)
    time.sleep(1)


def demo_web_chat():
    """Demonstrate web chat interface features."""
    print_header("🌐 Web Chat Interface Demo")
    
    print_slow("Starting Streamlit web interface...")
    time.sleep(1)
    
    print("""
┌─────────────────────────────────────────────────────────────┐
│  📄 KYC-AML Document Processing Assistant                   │
├───────────────────────┬─────────────────────────────────────┤
│                       │  🎛️ Control Panel                   │
│  Chat Area            │  ├─ System Status: ✅ Healthy       │
│                       │  ├─ Messages: 8                     │
│  👤 You:              │  ├─ Documents: 3                    │
│  What's the status?   │  │                                  │
│                       │  📁 Upload Documents                │
│  🤖 Assistant:        │  [Drag & drop files here]           │
│  All systems are      │  [ Browse Files ]                   │
│  operational! 3 docs  │                                     │
│  processed today.     │  ⚙️ Settings                        │
│                       │  Model: gpt-4-turbo                 │
│  💡 Suggested:        │  Max Size: 10MB                     │
│  [Upload Document]    │                                     │
│  [Check Health]       │  [🔍 Check Health]                  │
│  [View Stats]         │  [🗑️ Clear Chat]                    │
│                       │  [💾 Download Chat]                 │
│  [Type message...]    │                                     │
└───────────────────────┴─────────────────────────────────────┘
    """)
    time.sleep(2)
    
    print_slow("\nFeatures:")
    print("  ✅ Interactive chat with AI assistant")
    print("  ✅ Drag & drop file upload")
    print("  ✅ Real-time system status")
    print("  ✅ Processing statistics")
    print("  ✅ Export chat history")
    print("  ✅ Responsive UI")
    time.sleep(1)


def demo_document_processing():
    """Demonstrate document processing workflow."""
    print_header("📄 Document Processing Workflow")
    
    steps = [
        ("1️⃣  User uploads document", 1),
        ("2️⃣  Document Intake Agent validates", 1.5),
        ("    • Checks file format ✅", 0.5),
        ("    • Validates size ✅", 0.5),
        ("    • Creates hash ✅", 0.5),
        ("3️⃣  Document Classifier Agent processes", 1.5),
        ("    • Calls API ✅", 0.5),
        ("    • Receives classification ✅", 0.5),
        ("    • Document Type: Passport", 0.5),
        ("    • Confidence: 95%", 0.5),
        ("4️⃣  Results returned to user", 1),
        ("✅ Processing complete!", 0.5),
    ]
    
    for step, delay in steps:
        print_slow(step)
        time.sleep(delay)


def demo_features():
    """Demonstrate key features."""
    print_header("🌟 Key Features")
    
    features = [
        ("💬 Natural Language Chat", "Ask questions in plain English"),
        ("📁 Document Upload", "Upload PDF, JPG, PNG, DOCX files"),
        ("🤖 AI-Powered", "GPT-4 understands context and intent"),
        ("📊 Real-time Status", "Monitor processing in real-time"),
        ("🔍 Health Checks", "Verify system connectivity"),
        ("💾 History Export", "Download chat and results as JSON"),
        ("⚡ Batch Processing", "Process multiple documents at once"),
        ("🔐 Secure", "Enterprise-grade security features"),
    ]
    
    for feature, description in features:
        print(f"\n{feature}")
        print_slow(f"  → {description}", 0.02)
        time.sleep(0.5)


def main():
    """Run the demo."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║    KYC-AML Agentic AI Orchestrator - Interactive Demo     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")
    time.sleep(1)
    
    demos = [
        ("CLI Chat Interface", demo_cli_chat),
        ("Web Chat Interface", demo_web_chat),
        ("Document Processing", demo_document_processing),
        ("Key Features", demo_features),
    ]
    
    for idx, (name, func) in enumerate(demos, 1):
        try:
            func()
            
            if idx < len(demos):
                print("\n" + "-"*60)
                input("\nPress Enter to continue to next demo...")
        except KeyboardInterrupt:
            print("\n\n👋 Demo interrupted. Goodbye!")
            break
    
    print("\n" + "="*60)
    print("\n🎉 Demo complete!")
    print("\n📚 To try it yourself:")
    print("  • CLI Chat: python chat_interface.py")
    print("  • Web Chat: streamlit run web_chat.py")
    print("  • Documentation: See README.md and CHAT_GUIDE.md")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
