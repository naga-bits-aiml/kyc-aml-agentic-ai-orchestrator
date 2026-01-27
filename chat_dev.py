#!/usr/bin/env python3
"""
Development mode chat interface with auto-reload on file changes.

This script watches Python files and automatically restarts the chat
interface when changes are detected.

Usage:
    python chat_dev.py
"""
import sys
import subprocess
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class CodeReloadHandler(FileSystemEventHandler):
    """Handler for file system events that triggers reload."""
    
    def __init__(self):
        self.process = None
        self.last_reload = 0
        self.reload_delay = 1  # seconds
        
    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return
        
        # Only reload for Python files
        if not event.src_path.endswith('.py'):
            return
        
        # Avoid duplicate reloads
        now = time.time()
        if now - self.last_reload < self.reload_delay:
            return
        
        self.last_reload = now
        
        file_path = Path(event.src_path)
        print(f"\n🔄 Detected change in: {file_path.name}")
        print("   Restarting chat interface...\n")
        
        self.restart_chat()
    
    def restart_chat(self):
        """Restart the chat interface process."""
        # Kill existing process if running
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                self.process.kill()
        
        # Start new process
        self.process = subprocess.Popen(
            [sys.executable, "chat_interface.py"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            stdin=sys.stdin
        )
    
    def stop(self):
        """Stop the chat process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                self.process.kill()


def main():
    """Run chat interface in development mode with auto-reload."""
    print("="*60)
    print("🛠️  KYC-AML Chat Interface - Development Mode")
    print("="*60)
    print("✨ Auto-reload enabled")
    print("📁 Watching: *.py files in current directory")
    print("🔄 Edit any Python file to trigger automatic reload")
    print("⌨️  Press Ctrl+C to exit")
    print("="*60 + "\n")
    
    # Setup file watcher
    handler = CodeReloadHandler()
    observer = Observer()
    
    # Watch current directory
    watch_path = Path.cwd()
    observer.schedule(handler, str(watch_path), recursive=True)
    
    try:
        # Start initial chat process
        handler.restart_chat()
        
        # Start watching for changes
        observer.start()
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
            # Check if process died
            if handler.process and handler.process.poll() is not None:
                # Process ended, restart it
                print("\n🔄 Chat process ended. Restarting...\n")
                handler.restart_chat()
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping development mode...")
        observer.stop()
        handler.stop()
    
    observer.join()
    print("👋 Goodbye!\n")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        if "watchdog" in str(e):
            print("\n❌ Error: watchdog package not installed")
            print("\n📦 Install it with:")
            print("   pip install watchdog")
            print("\nOr use manual reload:")
            print("   python chat_interface.py")
            print("   (type 'reload' to reload code)\n")
            sys.exit(1)
        else:
            raise
