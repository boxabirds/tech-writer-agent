"""
File Tools for the Tech Writer multi-agent system.

This module provides tools for file operations used by the agents.
"""

import os
import glob
from typing import List, Dict, Any, Optional
from pathlib import Path
from binaryornot.check import is_binary

def is_text_file(file_path: str) -> bool:
    """Check if a file is a text file, handling special cases like TypeScript files."""
    # Check extension first - these are definitely text files
    ext = os.path.splitext(file_path)[1].lower()
    text_extensions = [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md', 
        '.yml', '.yaml', '.toml', '.txt', '.csv', '.sql', '.sh', '.bat', '.ps1',
        '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rb', '.php', '.swift'
    ]
    
    if ext in text_extensions:
        return True
    
    # Use binaryornot as a fallback
    return not is_binary(file_path)

def list_files(directory: str, pattern: str = "**/*") -> List[str]:
    """List all files in a directory matching a pattern."""
    files = []
    for file_path in glob.glob(os.path.join(directory, pattern), recursive=True):
        if os.path.isfile(file_path):
            files.append(file_path)
    return files

def list_directories(directory: str) -> List[str]:
    """List all subdirectories in a directory."""
    dirs = []
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            dirs.append(item_path)
    return dirs

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get information about a file."""
    try:
        stats = os.stat(file_path)
        return {
            "path": file_path,
            "size": stats.st_size,
            "modified": stats.st_mtime,
            "is_binary": not is_text_file(file_path),
            "extension": os.path.splitext(file_path)[1].lower()
        }
    except Exception as e:
        return {"path": file_path, "error": str(e)}

def read_file(file_path: str, max_size: int = 1000000) -> str:
    """Read the contents of a file if it's not binary and not too large."""
    try:
        if not is_text_file(file_path):
            return f"[Binary file: {file_path}]"
        
        stats = os.stat(file_path)
        if stats.st_size > max_size:
            return f"[File too large: {file_path}, size: {stats.st_size} bytes]"
        
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def get_directory_structure(directory: str, max_depth: int = 3) -> Dict[str, Any]:
    """Get the structure of a directory up to a maximum depth."""
    result = {"name": os.path.basename(directory), "type": "directory", "children": []}
    
    if max_depth <= 0:
        return result
    
    try:
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                result["children"].append(
                    get_directory_structure(item_path, max_depth - 1)
                )
            else:
                result["children"].append({
                    "name": item,
                    "type": "file",
                    "is_binary": not is_text_file(item_path),
                    "extension": os.path.splitext(item)[1].lower()
                })
    except Exception as e:
        result["error"] = str(e)
    
    return result

def find_files_by_extension(directory: str, extensions: List[str]) -> List[str]:
    """Find all files with specific extensions in a directory."""
    files = []
    for ext in extensions:
        # Ensure the extension starts with a dot
        if not ext.startswith("."):
            ext = f".{ext}"
        
        pattern = f"**/*{ext}"
        files.extend(list_files(directory, pattern))
    
    return files

def find_files_by_name(directory: str, name_pattern: str) -> List[str]:
    """Find all files matching a name pattern in a directory."""
    pattern = f"**/{name_pattern}"
    return list_files(directory, pattern)

def is_ignored_file(file_path: str, ignore_patterns: List[str]) -> bool:
    """Check if a file should be ignored based on patterns."""
    # Convert file path to a relative path for pattern matching
    rel_path = os.path.basename(file_path)
    
    for pattern in ignore_patterns:
        if pattern.endswith("/"):
            # Directory pattern
            if os.path.dirname(file_path).endswith(pattern[:-1]):
                return True
        elif "*" in pattern:
            # Glob pattern
            import fnmatch
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        else:
            # Exact match
            if rel_path == pattern:
                return True
    
    return False
