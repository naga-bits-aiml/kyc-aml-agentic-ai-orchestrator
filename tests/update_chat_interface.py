"""
Script to update _process_documents method in chat_interface.py
"""
import re

# Read the file
with open('chat_interface.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new _process_documents method
new_method = '''    def _process_documents(self, file_paths: List[str]) -> str:
        """Process documents through the orchestrator."""
        if not self.orchestrator:
            return "❌ Orchestrator not available. Please check configuration."
        
        if not file_paths:
            return "No valid file paths provided."
        
        # Check if case reference is set
        if not self.case_reference:
            self.workflow_state = "awaiting_case_reference"
            return """⚠️ No case reference set.

Please provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).
Or type 'skip' to proceed without a case reference."""
        
        # Validate paths
        valid_paths = []
        for path in file_paths:
            p = Path(path)
            if p.exists():
                valid_paths.append(str(p.absolute()))
            else:
                return f"❌ File not found: {path}"
        
        try:
            print(f"\\n🔄 Processing {len(valid_paths)} document(s) for case {self.case_reference}...")
            
            # Copy files to case directory with internal references
            case_dir = Path(settings.documents_dir) / "cases" / self.case_reference
            case_dir.mkdir(parents=True, exist_ok=True)
            
            file_mapping = {}  # internal_ref -> original_path
            processed_paths = []
            
            for idx, original_path in enumerate(valid_paths, 1):
                original_file = Path(original_path)
                # Create internal reference
                internal_ref = f"{self.case_reference}_DOC_{idx:03d}{original_file.suffix}"
                dest_path = case_dir / internal_ref
                
                # Copy file to case directory
                import shutil
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
            
            return f"""
✅ Processing complete for case {self.case_reference}!

📁 Documents stored in: {case_dir}
🔗 File mapping saved

{summary}"""
            
        except Exception as e:
            self.logger.error(f"Error processing documents: {str(e)}")
            return f"❌ Error processing documents: {str(e)}"'''

# Find and replace the _process_documents method
pattern = r'(    def _process_documents\(self, file_paths: List\[str\]\) -> str:.*?)(    def \w+|^class )'
replacement = new_method + '\n\n\\2'

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write back
with open('chat_interface.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated _process_documents method")
