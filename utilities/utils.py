"""Utility functions for the KYC-AML Agentic AI Orchestrator."""
import os
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
from datetime import datetime
import uuid


def generate_document_id() -> str:
    """
    Generate a globally unique document ID.
    Format: DOC_YYYYMMDD_HHMMSS_XXXXX
    Example: DOC_20260127_143022_A3F8B
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:5].upper()
    return f"DOC_{timestamp}_{unique_suffix}"


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """Validate if file has an allowed extension."""
    ext = Path(filename).suffix.lower()
    return ext in [e.lower() for e in allowed_extensions]


def validate_file_size(file_path: str, max_size_bytes: int) -> bool:
    """Validate if file size is within limits."""
    if not os.path.exists(file_path):
        return False
    return os.path.getsize(file_path) <= max_size_bytes


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def create_document_metadata(file_path: str) -> Dict[str, Any]:
    """Create metadata for a document."""
    file_path_obj = Path(file_path)
    return {
        "filename": file_path_obj.name,
        "extension": file_path_obj.suffix,
        "size_bytes": os.path.getsize(file_path),
        "hash": compute_file_hash(file_path),
        "uploaded_at": datetime.now().isoformat(),
        "absolute_path": str(file_path_obj.absolute())
    }


def ensure_directory(directory: str) -> None:
    """Ensure a directory exists."""
    Path(directory).mkdir(parents=True, exist_ok=True)


def load_ui_messages() -> Dict[str, Any]:
    """Load UI messages from config/ui_messages.json for consistent messaging across interfaces."""
    import json
    config_path = Path(__file__).parent.parent / "config" / "ui_messages.json"
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    
    # Fallback defaults
    return {
        "app": {"name": "KYC-AML Agentic AI Orchestrator", "tagline": "Intelligent Document Processing"},
        "banner": {"title": "🤖 KYC-AML Agentic AI Orchestrator"},
        "footer": {"text": "Powered by CrewAI & Google Gemini"}
    }


def get_banner_text(format: str = "cli") -> Dict[str, str]:
    """Get formatted banner text for CLI or web interfaces.
    
    Args:
        format: 'cli' for terminal output, 'web' for HTML/markdown
        
    Returns:
        Dict with 'title', 'subtitle', 'tagline' keys
    """
    ui = load_ui_messages()
    
    return {
        "title": ui.get("banner", {}).get("title", "🤖 KYC-AML Agentic AI Orchestrator"),
        "subtitle": ui.get("banner", {}).get("subtitle", "Intelligent Document Processing"),
        "description": ui.get("banner", {}).get("description", ""),
        "app_name": ui.get("app", {}).get("name", "KYC-AML Agentic AI Orchestrator"),
        "tagline": ui.get("app", {}).get("tagline", ""),
        "footer": ui.get("footer", {}).get("text", "Powered by CrewAI & Google Gemini"),
        "tip": ui.get("footer", {}).get("tip", "Just ask naturally!")
    }


def get_capabilities_text(format: str = "cli") -> str:
    """Get formatted capabilities text for help display.
    
    Args:
        format: 'cli' for terminal, 'web' for markdown
        
    Returns:
        Formatted string with capabilities
    """
    ui = load_ui_messages()
    capabilities = ui.get("capabilities", {}).get("items", [])
    agents = ui.get("agents", {}).get("items", [])
    commands = ui.get("quick_commands", {}).get("items", [])
    examples = ui.get("examples", {}).get("items", [])
    
    if format == "web":
        # Markdown format
        lines = [f"## 💡 {ui.get('capabilities', {}).get('headline', 'What I Can Do')}\n"]
        for cap in capabilities:
            lines.append(f"- {cap['icon']} **{cap['title']}**: {cap['description']}")
        
        lines.append(f"\n## 🤖 {ui.get('agents', {}).get('headline', 'Pipeline Agents')}\n")
        for agent in agents:
            lines.append(f"- **{agent['name']}** ({agent['role']}): {agent['description']}")
        
        lines.append(f"\n## ⚡ {ui.get('quick_commands', {}).get('headline', 'Quick Commands')}\n")
        for cmd in commands:
            lines.append(f"- `{cmd['command']}` - {cmd['description']}")
        
        lines.append(f"\n## ✨ {ui.get('examples', {}).get('headline', 'Try These')}\n")
        for ex in examples:
            lines.append(f"- \"{ex}\"")
        
        lines.append(f"\n💡 *{ui.get('footer', {}).get('tip', '')}*")
        
        return "\n".join(lines)
    
    else:
        # CLI format with box drawing
        app_name = ui.get('app', {}).get('name', 'KYC-AML Agentic AI Orchestrator')
        # Remove emoji for box centering (emoji width causes alignment issues)
        app_name_clean = app_name.replace('🤖 ', '')
        
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            f"║       🤖 {app_name_clean:^44}       ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"💡 {ui.get('capabilities', {}).get('headline', 'What I Can Do')}:",
        ]
        for cap in capabilities:
            lines.append(f"   {cap['icon']} {cap['title']}: {cap['description']}")
        
        lines.append(f"\n🤖 {ui.get('agents', {}).get('headline', 'Pipeline Agents')}:")
        for agent in agents:
            lines.append(f"   • {agent['name']}: {agent['description']}")
        
        lines.append(f"\n⚡ {ui.get('quick_commands', {}).get('headline', 'Quick Commands')}:")
        for cmd in commands:
            lines.append(f"   {cmd['command']:20} {cmd['description']}")
        
        lines.append(f"\n✨ {ui.get('examples', {}).get('headline', 'Try These')}:")
        for ex in examples:
            lines.append(f"   \"{ex}\"")
        
        lines.append(f"\n💬 {ui.get('footer', {}).get('tip', '')}")
        
        return "\n".join(lines)
