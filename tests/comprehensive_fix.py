"""
Comprehensive fix for chat_interface.py syntax issues
"""
import re

# Read original backup
with open('chat_interface.py.backup', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix problematic line around 671
# The issue is likely with unclosed multiline strings from our updates

fixed_content = []
in_multiline = False
multiline_delimiter = None

for i, line in enumerate(lines, 1):
    # Track multiline strings
    if '"""' in line:
        count = line.count('"""')
        if count % 2 == 1:  # Odd number means toggle state
            in_multiline = not in_multiline
    
    fixed_content.append(line)

# Write the fixed version
result = ''.join(fixed_content)

# Now make targeted replacements to avoid the multiline string issues
# Fix _process_documents case reference check
result = result.replace(
    '''            return """⚠️ No case reference set.

Please provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).
Or type 'skip' to proceed without a case reference."""\n''',
    '''            msg = "⚠️ No case reference set.\\n\\n"
            msg += "Please provide a KYC/AML case reference (e.g., KYC-2024-001, AML-CASE-123).\\n"
            msg += "Or type 'skip' to proceed without a case reference."
            return msg
'''
)

# Fix _process_documents success message
result = result.replace(
    '''            return f"""
✅ Processing complete for case {self.case_reference}!

📁 Documents stored in: {case_dir}
🔗 File mapping saved

{summary}"""\n''',
    '''            msg = f"\\n✅ Processing complete for case {self.case_reference}!\\n\\n"
            msg += f"📁 Documents stored in: {case_dir}\\n"
            msg += "🔗 File mapping saved\\n\\n"
            msg += summary
            return msg
'''
)

with open('chat_interface.py', 'w', encoding='utf-8') as f:
    f.write(result)

print("✓ Fixed syntax issues in chat_interface.py")
