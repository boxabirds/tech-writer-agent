#!/usr/bin/env python3
"""
Comprehensive .gitignore pattern tester for directory traversal.
This tool helps debug issues with .gitignore pattern matching when traversing directories.
"""

import os
import sys
import pathspec
from pathlib import Path
import json
import argparse
import time

def test_gitignore_patterns(directory_path, max_depth=None, verbose=True, output_file=None):
    """
    Test how pathspec matches against .gitignore patterns with detailed output.
    
    Args:
        directory_path: Path to the directory to test
        max_depth: Maximum depth to traverse
        verbose: Whether to print detailed output
        output_file: File to save results to
    
    Returns:
        Dictionary with test results
    """
    start_time = time.time()
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
    gitignore_patterns = []
    if gitignore_path.exists():
        print(f"Found .gitignore at {gitignore_path}")
        try:
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore_patterns.append(line)
                        gitignore_patterns.append(line)
                        if verbose:
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
    
    # Helper function to check if a path should be excluded
    def should_exclude(rel_path, is_dir=False):
        # Normalize path with forward slashes for consistent matching
        norm_path = rel_path.replace(os.sep, '/')
        
        # Explicit check for node_modules
        if "node_modules" in norm_path:
            return True, "explicit node_modules check"
            
        # For directories, check both with and without trailing slash
        if is_dir:
            with_slash = norm_path if norm_path.endswith('/') else f"{norm_path}/"
            without_slash_match = spec.match_file(norm_path)
            with_slash_match = spec.match_file(with_slash)
            
            if without_slash_match:
                return True, f"matched pattern without slash: {norm_path}"
            elif with_slash_match:
                return True, f"matched pattern with slash: {with_slash}"
            else:
                return False, "no match"
        else:
            match = spec.match_file(norm_path)
            return match, "matched file pattern" if match else "no match"
    
    # Walk the directory tree
    dirs_traversed = 0
    files_checked = 0
    
    print("\nWalking directory to test pattern matching...")
    for root, dirs, files in os.walk(str(path_obj)):
        root_path = Path(root)
        dirs_traversed += 1
        
        # Check depth
        if max_depth is not None:
            rel_root = os.path.relpath(root, str(path_obj))
            depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1
            if depth >= max_depth:
                if verbose:
                    print(f"Reached max depth {max_depth} at {rel_root}, stopping recursion")
                dirs.clear()  # Clear dirs to prevent further recursion
                continue
        
        # Get relative path for testing
        if root_path == path_obj:
            rel_root = ""
        else:
            rel_root = str(root_path.relative_to(path_obj)).replace('\\', '/')
        
        # Test each directory
        i = 0
        while i < len(dirs):
            dir_name = dirs[i]
            files_checked += 1
            
            if rel_root:
                rel_dir_path = f"{rel_root}/{dir_name}"
            else:
                rel_dir_path = dir_name
            
            should_skip, reason = should_exclude(rel_dir_path, is_dir=True)
            
            if should_skip:
                excluded_dirs.append({"path": rel_dir_path, "reason": reason})
                dirs.pop(i)  # Remove to prevent recursion
                if verbose:
                    print(f"EXCLUDED DIR: {rel_dir_path} - {reason}")
            else:
                included_dirs.append(rel_dir_path)
                if verbose:
                    print(f"included dir: {rel_dir_path}")
                i += 1
        
        # Test each file
        for file_name in files:
            files_checked += 1
            
            if rel_root:
                rel_file_path = f"{rel_root}/{file_name}"
            else:
                rel_file_path = file_name
            
            should_skip, reason = should_exclude(rel_file_path)
            
            if should_skip:
                excluded_files.append({"path": rel_file_path, "reason": reason})
                if verbose:
                    print(f"EXCLUDED FILE: {rel_file_path} - {reason}")
            else:
                included_files.append(rel_file_path)
                if verbose:
                    print(f"included file: {rel_file_path}")
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total patterns: {len(ignore_patterns)} ({len(gitignore_patterns)} from .gitignore)")
    print(f"Directories traversed: {dirs_traversed}")
    print(f"Files/directories checked: {files_checked}")
    print(f"Included directories: {len(included_dirs)}")
    print(f"Excluded directories: {len(excluded_dirs)}")
    print(f"Included files: {len(included_files)}")
    print(f"Excluded files: {len(excluded_files)}")
    print(f"Execution time: {execution_time:.2f} seconds")
    
    # Print samples of excluded items
    print("\n=== EXCLUDED DIRECTORIES (sample) ===")
    for item in excluded_dirs[:10]:
        print(f"{item['path']} - {item['reason']}")
    
    print("\n=== EXCLUDED FILES (sample) ===")
    for item in excluded_files[:10]:
        print(f"{item['path']} - {item['reason']}")
    
    # Check specifically for node_modules
    node_modules_dirs = [d for d in excluded_dirs if "node_modules" in d["path"]]
    node_modules_files = [f for f in excluded_files if "node_modules" in f["path"]]
    
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
    
    # Results dictionary
    results = {
        "included_dirs": included_dirs,
        "excluded_dirs": [d["path"] for d in excluded_dirs],
        "excluded_dirs_reasons": excluded_dirs,
        "included_files": included_files,
        "excluded_files": [f["path"] for f in excluded_files],
        "excluded_files_reasons": excluded_files,
        "patterns": ignore_patterns,
        "gitignore_patterns": gitignore_patterns,
        "execution_stats": {
            "dirs_traversed": dirs_traversed,
            "files_checked": files_checked,
            "execution_time": execution_time
        }
    }
    
    # Save results to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to {output_file}")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test .gitignore pattern matching")
    parser.add_argument("directory", help="Directory to test")
    parser.add_argument("--max-depth", type=int, help="Maximum directory depth to traverse")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    parser.add_argument("--output", help="Output file for detailed results (JSON)")
    
    args = parser.parse_args()
    
    test_gitignore_patterns(
        args.directory, 
        max_depth=args.max_depth, 
        verbose=not args.quiet,
        output_file=args.output
    )
