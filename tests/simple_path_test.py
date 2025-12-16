"""
Simple test to verify path extraction works.
"""
import re
from pathlib import Path

def extract_file_paths(text: str):
    """Extract file paths from text."""
    paths = []
    
    # First priority: Paths in quotes (supports spaces)
    quoted_paths = re.findall(r'["\']([^"\']+)["\']', text)
    for path in quoted_paths:
        path = path.strip()
        if Path(path).exists():
            paths.append(path)
    
    # Second priority: Windows paths with file extensions
    windows_file_paths = re.findall(
        r'[A-Za-z]:[\\\/](?:[^<>:"|?*\n\r]+?)\.(?:pdf|jpg|jpeg|png|doc|docx|txt|csv|xlsx)',
        text,
        re.IGNORECASE
    )
    paths.extend(windows_file_paths)
    
    # Third priority: Unix paths with file extensions
    unix_file_paths = re.findall(
        r'\/(?:[^<>:"|?*\n\r\s]+?)\.(?:pdf|jpg|jpeg|png|doc|docx|txt|csv|xlsx)',
        text,
        re.IGNORECASE
    )
    paths.extend(unix_file_paths)
    
    # Validate paths exist and deduplicate
    valid_paths = []
    seen = set()
    for p in paths:
        p = p.strip().rstrip('.,;:')
        p_normalized = str(Path(p).resolve()) if Path(p).exists() else p
        
        if p_normalized not in seen and Path(p).exists():
            valid_paths.append(p)
            seen.add(p_normalized)
            print(f"✓ Found valid file path: {p}")
        elif p not in seen:
            print(f"✗ Path not found: {p}")
            seen.add(p)
    
    return valid_paths

# Create a test file
test_dir = Path("test_documents")
test_dir.mkdir(exist_ok=True)

test_file = test_dir / "sample.txt"
test_file.write_text("Test document content")

print(f"Created test file: {test_file.absolute()}\n")

# Test path extraction
test_cases = [
    f"Please classify {test_file.absolute()}",
    f"I want to submit 'C:\\My Documents\\test.pdf'",
    str(test_file.absolute()),
]

for test_input in test_cases:
    print(f"\nInput: {test_input}")
    paths = extract_file_paths(test_input)
    print(f"Extracted: {paths}")
