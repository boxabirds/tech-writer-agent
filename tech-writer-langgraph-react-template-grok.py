from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re
import ast
from datetime import datetime
import mimetypes
import pathspec
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import argparse

# Create the model
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Define all tools
@tool
def list_files(path: str = ".", max_depth: Optional[int] = None) -> str:
    """List all files and directories in the specified path up to a maximum depth."""
    try:
        path = Path(path).resolve()
        if not path.exists():
            return json.dumps({"error": f"Path not found: {path}"}, indent=2)
        
        # Define common patterns to ignore (similar to .gitignore)
        ignore_patterns = [
            "node_modules/",
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
        
        # Check if .gitignore exists and add its patterns
        gitignore_path = path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r') as f:
                    ignore_patterns.extend(line.strip() for line in f if line.strip() and not line.startswith('#'))
            except Exception:
                pass  # If we can't read .gitignore, just use the default patterns
        
        # Create pathspec matcher
        spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, ignore_patterns
        )
        
        files, directories = [], []
        
        # Function to check if a path should be ignored
        def should_ignore(item_path):
            rel_to_base = str(item_path.relative_to(path))
            return spec.match_file(rel_to_base)
        
        # Use different approaches based on max_depth
        if max_depth is None:
            # For recursive search, we'll manually walk to respect ignore patterns
            for root, dirs, filenames in path.walk():
                root_path = Path(root)
                
                # Filter out ignored directories to avoid walking into them
                dirs[:] = [d for d in dirs if not should_ignore(root_path / d)]
                
                for filename in filenames:
                    file_path = root_path / filename
                    if not should_ignore(file_path):
                        files.append(str(file_path.relative_to(path)))
                
                for dirname in dirs:
                    dir_path = root_path / dirname
                    directories.append(str(dir_path.relative_to(path)))
        else:
            # For limited depth search
            pattern = "*/" * max_depth + "*"
            for item in path.glob(pattern):
                if not should_ignore(item):
                    rel_path = str(item.relative_to(path))
                    if item.is_file():
                        files.append(rel_path)
                    elif item.is_dir():
                        directories.append(rel_path)
        
        result = {
            "files": files,
            "directories": directories,
            "current_path": str(path)
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error listing files: {str(e)}"}, indent=2)

@tool
def read_file(file_path: str) -> str:
    """Read and return the contents of a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        if is_binary_file(file_path):
            return json.dumps({"error": "Cannot read binary file", "file": file_path}, indent=2)
        
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            return json.dumps({"error": f"Error reading file with latin-1 encoding: {str(e)}"}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error reading file: {str(e)}"}, indent=2)

@tool
def search_in_files(pattern: str, file_pattern: str = "*", directory: str = ".", file_types: Optional[List[str]] = None) -> str:
    """Search for a regex pattern in files matching file_pattern in the specified directory."""
    try:
        directory = Path(directory).resolve()
        results, skipped = {}, []
        
        if file_types:
            file_pattern = f"*.{{{','.join(file_types)}}}"
        
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file() and not is_binary_file(str(filepath)):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(pattern, content)
                        if matches:
                            relative_path = str(filepath.relative_to(directory))
                            results[relative_path] = matches
                except Exception:
                    skipped.append(str(filepath.relative_to(directory)))
        
        return json.dumps({
            "results": results,
            "skipped_files": skipped,
            "pattern": pattern,
            "file_pattern": file_pattern
        }, indent=2) if results else json.dumps({"message": "No matches found", "skipped_files": skipped}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error searching in files: {str(e)}"}, indent=2)

@tool
def analyze_imports(file_path: str) -> str:
    """Analyze imports in a file to understand dependencies."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        ext = path.suffix.lower()
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        imports = []
        if ext == '.py':
            tree = ast.parse(content)
            imports = [
                node.names[0].name for node in ast.walk(tree)
                if isinstance(node, ast.Import)
            ] + [
                node.module for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            ]
        elif ext == '.js':
            imports = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
        
        return json.dumps({
            "file": file_path,
            "imports": imports,
            "language": "python" if ext == '.py' else "javascript" if ext == '.js' else "unknown",
            "file_size": path.stat().st_size
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error analyzing imports: {str(e)}"}, indent=2)

@tool
def find_functions(file_path: str) -> str:
    """Find and list all function definitions in a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        ext = path.suffix.lower()
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        functions = []
        if ext == '.py':
            tree = ast.parse(content)
            functions = [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]
        elif ext == '.js':
            functions = re.findall(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)', content)
            functions = [f[0] or f[1] for f in functions]
        
        return json.dumps({
            "file": file_path,
            "functions": functions,
            "language": "python" if ext == '.py' else "javascript" if ext == '.js' else "unknown",
            "file_size": path.stat().st_size
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error finding functions: {str(e)}"}, indent=2)

@tool
def find_classes(file_path: str) -> str:
    """Find and list all class definitions in a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        ext = path.suffix.lower()
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        classes = []
        if ext == '.py':
            tree = ast.parse(content)
            classes = [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
            ]
        elif ext == '.js':
            classes = re.findall(r'class\s+(\w+)', content)
        
        seminal = json.dumps({
            "file": file_path,
            "classes": classes,
            "language": "python" if ext == '.py' else "javascript" if ext == '.js' else "unknown",
            "file_size": path.stat().st_size
        }, indent=2)
        return seminal
    except Exception as e:
        return json.dumps({"error": f"Error finding classes: {str(e)}"}, indent=2)

@tool
def count_lines_of_code(directory: str = ".", file_pattern: str = "*") -> str:
    """Count lines of code in files matching the pattern, excluding blanks and comments."""
    try:
        directory = Path(directory).resolve()
        total_lines, file_count, file_stats = 0, 0, {}
        
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file() and not is_binary_file(str(filepath)):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith(('#', '//', '/*', '*', '*/'))]
                        count = len(lines)
                        file_stats[str(filepath.relative_to(directory))] = count
                        total_lines += count
                        file_count += 1
                except Exception:
                    continue
        
        return json.dumps({
            "file_pattern": file_pattern,
            "file_count": file_count,
            "total_lines": total_lines,
            "average_lines_per_file": round(total_lines / file_count, 2) if file_count > 0 else 0,
            "files": file_stats
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error counting lines: {str(e)}"}, indent=2)

@tool
def find_todos(directory: str = ".", file_pattern: str = "*") -> str:
    """Find TODO comments in the codebase."""
    try:
        todos = {}
        todo_pattern = r'(?://|#|/\*|\*|<!--)\s*TODO:?\s*(.*?)(?:\*/|-->|\n|$)'
        directory = Path(directory).resolve()
        
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file() and not is_binary_file(str(filepath)):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(todo_pattern, content)
                        if matches:
                            todos[str(filepath.relative_to(directory))] = [match[1].strip() for match in matches if match[1].strip()]
                except Exception:
                    continue
        
        return json.dumps(todos, indent=2) if todos else json.dumps({"message": "No TODOs found"}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error finding TODOs: {str(e)}"}, indent=2)

@tool
def get_file_info(file_path: str) -> str:
    """Get detailed information about a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        stat_info = path.stat()
        return json.dumps({
            "file": str(path),
            "size_bytes": stat_info.st_size,
            "size_human": f"{stat_info.st_size / 1024:.2f} KB" if stat_info.st_size < 1024 * 1024 else f"{stat_info.st_size / (1024 * 1024):.2f} MB",
            "modification_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "extension": path.suffix.lower(),
            "is_binary": is_binary_file(file_path),
            "is_hidden": path.name.startswith('.')
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error getting file info: {str(e)}"}, indent=2)

@tool
def find_function_calls(file_path: str, function_name: str) -> str:
    """Find all calls to a specific function in a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        ext = path.suffix.lower()
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        calls = []
        if ext == '.py':
            tree = ast.parse(content)
            calls = [
                f"Line {node.lineno}" for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name
            ]
        elif ext == '.js':
            calls = re.findall(rf'{function_name}\s*\([^)]*\)', content)
        
        return json.dumps({
            "file": file_path,
            "function_name": function_name,
            "calls": calls,
            "language": "python" if ext == '.py' else "javascript" if ext == '.js' else "unknown"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error finding function calls: {str(e)}"}, indent=2)

# Helper function for binary file detection
def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary."""
    try:
        with open(file_path, 'rb') as f:
            return b'\0' in f.read(1024)
    except Exception:
        return True  # Treat unreadable files as binary

# Collect all tools
tools = [
    list_files,
    read_file,
    search_in_files,
    analyze_imports,
    find_functions,
    find_classes,
    count_lines_of_code,
    find_todos,
    get_file_info,
    find_function_calls
]

# Custom system prompt
system_prompt = """
You are a code analysis expert that helps developers understand codebases. Your task is to analyze the local filesystem to understand the structure and functionality of a codebase.

Important guidelines:
- The user's analysis prompt will be provided in the initial message, prefixed with the base directory of the codebase (e.g., "Base directory: /path/to/codebase").
- Analyze the codebase based on the instructions in the prompt, using the base directory as the root for all relative paths.
- Make no assumptions about file types or formats - analyze each file based on its content and extension.
- Adapt your analysis approach based on the codebase and the prompt's requirements.
- Be thorough but focus on the most important aspects as specified in the prompt.
- Provide clear, structured summaries of your findings in your final response.
- Use language-specific parsing for Python (.py) and JavaScript (.js) files where applicable (e.g., for analyzing imports, functions, or classes).
- Handle errors gracefully and report them clearly if they occur.

When analyzing code:
- Start by exploring the directory structure to understand the project organization.
- Identify key files like README, configuration files, or main entry points.
- ignore temporary files and directories like node_modules, .git, etc.
- ignore all files and folders in .gitignore
- Analyze relationships between components (e.g., imports, function calls).
- Look for patterns in the code organization (e.g., line counts, TODOs).
- Summarize your findings to help someone understand the codebase quickly, tailored to the prompt.
"""


# Create the agent

def read_prompt_file(file_path: str) -> str:
    """Read a prompt from an external file."""
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                return f.read().strip()
        except Exception as e:
            raise UnicodeDecodeError(f"Error reading prompt file with latin-1 encoding: {str(e)}")
    except Exception as e:
        raise Exception(f"Error reading prompt file: {str(e)}")

def analyze_codebase(directory_path: str, prompt_file_path: str) -> str:
    """Analyze a codebase using the ReAct agent with a prompt from an external file."""
    try:
        directory = Path(directory_path).resolve()
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Read the prompt and include the base directory
        prompt = read_prompt_file(prompt_file_path)
        initial_message = {
            "role": "user",
            "content": f"Base directory: {directory}\n\n{prompt}"
        }
        agent = create_react_agent(
            prompt=system_prompt + "\n\n" + prompt,
            model=model,
            tools=tools,
            debug=True
        )

        
        # Run the agent
        result = agent.invoke({"messages": [initial_message]})
        
        # Return the final response
        return result["messages"][-1].content
    except Exception as e:
        return json.dumps({"error": f"Error running code analysis: {str(e)}"}, indent=2)

def main():
    """Main entry point for the code analysis tool."""
    parser = argparse.ArgumentParser(description="Analyze a codebase using a LangGraph ReAct agent")
    parser.add_argument("--directory", required=True, help="Path to the codebase directory")
    parser.add_argument("--prompt-file", required=True, help="Path to the file containing the analysis prompt")
    
    try:
        args = parser.parse_args()
        analysis_result = analyze_codebase(args.directory, args.prompt_file)
        print(analysis_result)
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()