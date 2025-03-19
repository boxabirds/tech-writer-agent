import os
import mimetypes
from pathlib import Path

def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary."""
    # Get the file extension
    ext = os.path.splitext(file_path)[1].lower()
    
    # List of extensions that are always text files regardless of MIME type
    text_extensions = ['.json', '.md', '.txt', '.csv', '.tsv', '.yml', '.yaml', '.xml', '.html', '.css', '.js', '.ts', '.tsx', '.jsx']
    if ext in text_extensions:
        try:
            # Still try to read it to make sure it's valid text
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
            return False
        except UnicodeDecodeError:
            # If we can't decode it as UTF-8, it might still be binary
            pass
    
    # Check MIME type
    mime, _ = mimetypes.guess_type(file_path)
    
    # List of MIME types that are text-based but don't start with 'text/'
    text_mimes = [
        'application/json',
        'application/javascript',
        'application/xml',
        'application/xhtml+xml',
        'application/x-yaml',
        'application/x-typescript'
    ]
    
    if mime:
        if mime.startswith('text/'):
            return False
        if mime in text_mimes:
            return False
    
    # As a last resort, try to read the file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # Try to read a chunk of the file
        return False
    except UnicodeDecodeError:
        return True

# Test with package.json
package_json_path = "/Users/julian/expts/LandscapeHub/package.json"
print(f"Testing file: {package_json_path}")
print(f"File exists: {os.path.exists(package_json_path)}")
print(f"MIME type: {mimetypes.guess_type(package_json_path)}")
print(f"Extension: {os.path.splitext(package_json_path)[1].lower()}")
print(f"Is binary (new function): {is_binary_file(package_json_path)}")

# Test with the old logic for comparison
def old_is_binary_file(file_path: str) -> bool:
    mime, _ = mimetypes.guess_type(file_path)
    if mime and not mime.startswith('text/'):
        return True
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return False
    except UnicodeDecodeError:
        return True

print(f"Is binary (old function): {old_is_binary_file(package_json_path)}")
