# Chat Interface Guide

The KYC-AML Orchestrator provides two interactive chat interfaces for users to interact with the agents.

## 🖥️ CLI Chat Interface

A terminal-based conversational interface.

### Start CLI Chat

```powershell
python chat_interface.py
```

### Features

- **Natural Language**: Ask questions in plain English
- **Document Processing**: Upload and process documents through chat
- **Command Support**: Special commands for quick actions
- **Chat History**: View and save conversation history
- **Status Tracking**: Monitor processing status

### Commands

| Command | Description |
|---------|-------------|
| `help`, `?` | Show help information |
| `exit`, `quit` | Exit the chat |
| `status` | Show processing status |
| `history` | View chat history |
| `clear` | Clear chat history |
| `health` | Check system health |
| `/process <file>` | Process specific document |

### Example Conversation

```
👤 You: What documents do I need for KYC verification?

🤖 Assistant: For KYC verification, you typically need:
1. Identity Proof: Passport, Driver's License, or National ID
2. Address Proof: Utility Bill, Bank Statement, or Lease Agreement
3. Financial Documents: Income Statement or Tax Return (if required)

Would you like to submit any documents?

👤 You: Process my passport at C:\Documents\passport.pdf

🤖 Assistant: 
🔄 Processing documents...
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
```

### Document Processing via Chat

You can process documents by:

1. **Direct path**:
   ```
   Process my document at C:\path\to\document.pdf
   ```

2. **Natural language**:
   ```
   I want to submit my utility bill: C:\bills\utility.pdf
   Can you classify this: C:\docs\statement.pdf
   ```

3. **Command**:
   ```
   /process C:\path\to\document.pdf
   ```

## 🌐 Web Chat Interface (Streamlit)

A modern web-based interface with file upload and interactive chat.

### Start Web Chat

```powershell
streamlit run web_chat.py
```

This will open your browser at `http://localhost:8501`

### Features

- **💬 Interactive Chat**: Chat with AI assistant
- **📁 File Upload**: Drag & drop document upload
- **📊 Real-time Status**: Live system health checks
- **💾 Export History**: Download chat history as JSON
- **🎨 Modern UI**: Clean, responsive interface
- **📈 Statistics**: View processing metrics

### Web Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│  📄 KYC-AML Document Processing Assistant               │
├───────────────────────┬─────────────────────────────────┤
│                       │  🎛️ Control Panel               │
│  Chat Area            │  ├─ System Status               │
│                       │  ├─ Statistics                  │
│  👤 You: Message      │  ├─ Upload Documents            │
│  🤖 Assistant: ...    │  ├─ Settings                    │
│                       │  └─ Clear Chat                  │
│                       │                                 │
│  [Type message...]    │                                 │
└───────────────────────┴─────────────────────────────────┘
```

### Upload Documents via Web

1. Click **"Upload Documents"** in sidebar
2. Select files (PDF, JPG, PNG, DOCX)
3. Click **"Process Documents"**
4. View results in sidebar and chat

### Web Interface Commands

- **🔍 Check Health**: Test system connectivity
- **📊 View Statistics**: See processing metrics
- **🗑️ Clear Chat**: Reset conversation
- **💾 Download Chat**: Export history

## 🤖 How the Chat Works

### Architecture

```
User Input
    ↓
Chat Interface
    ↓
Intent Detection ──→ Commands (status, help, etc.)
    ↓
Document Detection ──→ Process Documents
    ↓
General Query ──→ LLM (GPT-4)
    ↓
Response Generation
    ↓
Display to User
```

### Conversation Context

The chat maintains context across the conversation:
- Remembers previous questions
- Tracks processed documents
- Maintains chat history
- Understands follow-up questions

### Example Multi-turn Conversation

```
👤 You: What's the difference between KYC and AML?

🤖 Assistant: KYC (Know Your Customer) is the process of verifying 
customer identity, while AML (Anti-Money Laundering) focuses on 
preventing financial crimes. KYC is a component of AML compliance.

👤 You: What documents are required for each?

🤖 Assistant: For KYC, you need identity and address verification. 
For AML, additional financial documents may be required...

👤 You: Can you process my passport?

🤖 Assistant: Yes! Please provide the file path or upload your 
passport document. I'll validate and classify it for you.
```

## 💡 Tips for Best Experience

### CLI Chat
- Use absolute file paths
- Enable conversation save before exit
- Use commands for quick actions
- Check status regularly

### Web Chat
- Upload multiple files at once
- Use suggested prompts for ideas
- Monitor system health in sidebar
- Download history for records

## 🔧 Customization

### Change Chat Personality

Edit the system prompt in `chat_interface.py` or `web_chat.py`:

```python
system_prompt = """You are a friendly AI assistant for KYC-AML 
document processing. Be conversational and helpful..."""
```

### Adjust LLM Temperature

Higher temperature = more creative responses:

```python
# In chat_interface.py
self.orchestrator = KYCAMLOrchestrator(temperature=0.7)  # Default: 0.3
```

### Add Custom Commands

In `chat_interface.py`, add to `process_command()`:

```python
if user_input in ['mycommand', '/mycommand']:
    return self._my_custom_function()
```

## 🚨 Troubleshooting

### CLI Chat Issues

**Issue**: "Orchestrator not initialized"
```powershell
# Check .env configuration
notepad .env
# Ensure OPENAI_API_KEY is set
```

**Issue**: File not found
```powershell
# Use absolute paths
C:\full\path\to\document.pdf
# Not: document.pdf
```

### Web Chat Issues

**Issue**: Streamlit not starting
```powershell
# Install streamlit
pip install streamlit

# Or reinstall requirements
pip install -r requirements.txt
```

**Issue**: File upload fails
- Check file size (max 10MB by default)
- Verify file format is supported
- Check temp_uploads folder permissions

## 📊 Chat Analytics

Both interfaces track:
- Total messages sent
- Documents processed
- Success/failure rates
- Response times
- Error occurrences

### Save Analytics (CLI)

```
💾 Save conversation history? (y/N): y
💾 Conversation saved to chat_history.json
```

### Export Analytics (Web)

Click **"Download Chat"** in sidebar → Downloads JSON with:
- Full conversation history
- Timestamps
- Processing results
- System metrics

## 🔐 Security Considerations

### Best Practices

1. **Don't share API keys** in chat
2. **Sanitize file paths** before processing
3. **Use HTTPS** for web deployment
4. **Implement authentication** for production
5. **Log chat sessions** for audit trails
6. **Encrypt sensitive data** in transit

### Production Deployment

For web interface in production:

```python
# Add authentication
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(...)
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # Show chat interface
    main()
```

## 📱 Future Enhancements

Planned features:
- Voice input/output
- Real-time document preview
- Multi-language support
- Chat analytics dashboard
- Mobile-responsive design
- Slack/Teams integration

---

**Start chatting now!**

CLI: `python chat_interface.py`  
Web: `streamlit run web_chat.py`
