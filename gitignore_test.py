#!/usr/bin/env python3
"""
Test program to understand how pathspec handles .gitignore patterns.
This will help us properly implement directory filtering in our main script.
"""

import os
import sys
import pathspec
from pathlib import Path
import json

def test_gitignore_matching(directory_path, verbose=True):
    """Test how pathspec matches against .gitignore patterns."""
    path_obj = Path(directory_path).resolve()
    
    if not path_obj.exists():
        print(f"Error: Path not found: {directory_path}")
        return
    
    # Default patterns to ignore
    ignore_patterns = [
        "node_modules/",
        "node_modules",
        ".git/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".DS_Store",
        "dist/",
        "build/",
        "*.egg-info/",
        "venv/",
        ".env/",
        ".venv/",
        "env/",
        ".idea/",
        ".vscode/"
    ]
    
    # Read .gitignore if it exists
    gitignore_path = path_obj / ".gitignore"
    if gitignore_path.exists():
        print(f"Found .gitignore at {gitignore_path}")
        try:
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore_patterns.append(line)
                        print(f"Added pattern: {line}")
        except Exception as e:
            print(f"Error reading .gitignore: {e}")
    
    # Create pathspec matcher
    spec = pathspec.PathSpec.from_lines(
        pathspec.patterns.GitWildMatchPattern, ignore_patterns
    )
    
    # Results containers
    included_files = []
    excluded_files = []
    included_dirs = []
    excluded_dirs = []
    
    # Test function to check if a path should be excluded
    def should_exclude(path_to_check, is_dir=False):
        # Get path relative to base directory
        if isinstance(path_to_check, Path):
            rel_path = path_to_check.relative_to(path_obj)
            rel_path_str = str(rel_path).replace('\\', '/')
        else:
            rel_path_str = path_to_check.replace('\\', '/')
        
        # For directories, also check with trailing slash
        if is_dir and not rel_path_str.endswith('/'):
            dir_path = f"{rel_path_str}/"
            result = spec.match_file(rel_path_str) or spec.match_file(dir_path)
        else:
            result = spec.match_file(rel_path_str)
        
        if verbose:
            print(f"Testing {'dir' if is_dir else 'file'}: {rel_path_str} -> {'EXCLUDED' if result else 'included'}")
        
        return result
    
    # Walk the directory and test each path
    print("\nWalking directory to test pattern matching...")
    for root, dirs, files in os.walk(str(path_obj)):
        root_path = Path(root)
        
        # Get relative path for testing
        if root_path == path_obj:
            rel_root = ""
        else:
            rel_root = str(root_path.relative_to(path_obj)).replace('\\', '/')
        
        # Test each directory
        for dir_name in list(dirs):  # Use list() to allow modification during iteration
            if rel_root:
                rel_dir_path = f"{rel_root}/{dir_name}"
            else:
                rel_dir_path = dir_name
            
            if should_exclude(rel_dir_path, is_dir=True):
                excluded_dirs.append(rel_dir_path)
                dirs.remove(dir_name)  # Remove to prevent recursion
            else:
                included_dirs.append(rel_dir_path)
        
        # Test each file
        for file_name in files:
            if rel_root:
                rel_file_path = f"{rel_root}/{file_name}"
            else:
                rel_file_path = file_name
            
            if should_exclude(rel_file_path):
                excluded_files.append(rel_file_path)
            else:
                included_files.append(rel_file_path)
    
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total patterns: {len(ignore_patterns)}")
    print(f"Included directories: {len(included_dirs)}")
    print(f"Excluded directories: {len(excluded_dirs)}")
    print(f"Included files: {len(included_files)}")
    print(f"Excluded files: {len(excluded_files)}")
    
    # Print samples of excluded items
    print("\n=== EXCLUDED DIRECTORIES (sample) ===")
    for path in excluded_dirs[:10]:
        print(path)
    
    print("\n=== EXCLUDED FILES (sample) ===")
    for path in excluded_files[:10]:
        print(path)
    
    # Check specifically for node_modules
    node_modules_dirs = [d for d in excluded_dirs if "node_modules" in d]
    node_modules_files = [f for f in excluded_files if "node_modules" in f]
    
    print("\n=== NODE_MODULES CHECK ===")
    print(f"node_modules directories excluded: {len(node_modules_dirs)}")
    print(f"node_modules files excluded: {len(node_modules_files)}")
    
    # Check if any node_modules were incorrectly included
    node_modules_included_dirs = [d for d in included_dirs if "node_modules" in d]
    node_modules_included_files = [f for f in included_files if "node_modules" in f]
    
    if node_modules_included_dirs:
        print("\nWARNING: Some node_modules directories were NOT excluded:")
        for d in node_modules_included_dirs[:10]:
            print(f"  {d}")
    
    if node_modules_included_files:
        print("\nWARNING: Some node_modules files were NOT excluded:")
        for f in node_modules_included_files[:10]:
            print(f"  {f}")
    
    # Return results as a dictionary
    return {
        "included_dirs": included_dirs,
        "excluded_dirs": excluded_dirs,
        "included_files": included_files,
        "excluded_files": excluded_files,
        "patterns": ignore_patterns
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gitignore_test.py <directory_path>")
        sys.exit(1)
    
    directory_path = sys.argv[1]
    results = test_gitignore_matching(directory_path)
    
    # Save detailed results to a JSON file for further analysis
    with open('gitignore_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to gitignore_test_results.json")
