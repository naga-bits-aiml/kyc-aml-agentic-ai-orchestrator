"""
Fix multiline string syntax in chat_interface.py
"""

# Read the file
with open('chat_interface.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the multiline string issue - replace triple quotes with proper f-strings
content = content.replace(
    '            return """⚠️ No case reference set.\n\nPlease provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).\nOr type \'skip\' to proceed without a case reference."""',
    '            return ("⚠️ No case reference set.\\n\\n"'
    '\n                    "Please provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).\\n"'
    '\n                    "Or type \'skip\' to proceed without a case reference.")'
)

content = content.replace(
    '            return f"""\n✅ Processing complete for case {self.case_reference}!\n\n📁 Documents stored in: {case_dir}\n🔗 File mapping saved\n\n{summary}"""',
    '            return (f"\\n✅ Processing complete for case {self.case_reference}!\\n\\n"'
    '\n                    f"📁 Documents stored in: {case_dir}\\n"'
    '\n                    f"🔗 File mapping saved\\n\\n{summary}")'
)

# Write back
with open('chat_interface.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed multiline string syntax")
