from pathlib import Path
from typing import List, Dict, Any
import json
import re
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import argparse

# Create the model
model = ChatOpenAI(model="gpt-4o", temperature=0)

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
    get_file_info
]

# Create the ReAct agent with a custom system prompt
system_prompt = """
You are a code analysis expert that helps developers understand codebases. 
Your task is to analyze the local filesystem to understand the structure and functionality of a codebase.

You will follow the ReAct framework: Thought, Action, Observation.

For each step:
1. Thought: Think about what you need to do next based on your current understanding and goals.
2. Action: Choose a tool to execute, specifying the tool name and parameters.
3. Observation: Review the result of the tool execution.

Always structure your responses in this format:
Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <parameters for the tool>
Observation: <result from the tool>
... (repeat the Thought/Action/Observation cycle as needed)
Thought: I now have enough information to provide a final answer.
Final Answer: <your comprehensive analysis of the codebase>

Important guidelines:
- Make no assumptions about file types or formats - analyze each file based on its content and extension
- For user prompts, always read them from the specified file using the read_prompt_file tool
- Adapt your analysis approach based on the codebase you're examining
- Be thorough but focus on the most important aspects of the code
- Provide clear, structured summaries of your findings

When analyzing code:
- Start by exploring the directory structure to understand the project organization
- Identify key files like README, configuration files, or main entry points
- Analyze the relationships between different components
- Look for patterns in the code organization
- Summarize your findings in a way that would help someone understand the codebase quickly

Remember to read the user's prompt from the specified file before beginning your analysis.
"""

# Create the agent
agent = create_react_agent(
    model=model,
    tools=tools,
    system_message=system_prompt
)

def analyze_codebase(directory_path: str, prompt_file_path: str):
    """
    Analyze a codebase using the ReAct agent.
    
    Args:
        directory_path: Path to the codebase directory
        prompt_file_path: Path to the file containing the analysis prompt
        
    Returns:
        str: The final analysis result from the agent
    """
    try:
        # Create the initial message
        initial_message = {
            "role": "user",
            "content": f"Please analyze the codebase in directory: {directory_path}"
        }
        
        # Run the agent
        result = agent.invoke({
            "messages": [initial_message]
        })
        
        # Return the final response
        return result["messages"][-1].content
    except Exception as e:
        return f"Error running code analysis: {str(e)}"



@tool
def list_files(path: str = ".") -> str:
    """List all files and directories in the specified path."""
    try:
        path = Path(path)
        items = list(path.iterdir())
        files = [f.name for f in items if f.is_file()]
        directories = [d.name for d in items if d.is_dir()]
        
        result = {
            "files": files,
            "directories": directories,
            "current_path": str(path.absolute())
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """Read and return the contents of a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading file with latin-1 encoding: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def search_in_files(pattern: str, file_pattern: str = "*", directory: str = ".") -> str:
    """Search for a regex pattern in files matching file_pattern in the specified directory."""
    try:
        results = {}
        directory = Path(directory)
        
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(pattern, content)
                        if matches:
                            relative_path = str(filepath.relative_to(directory))
                            results[relative_path] = matches
                except Exception:
                    continue
        
        if results:
            return json.dumps(results, indent=2)
        else:
            return f"No matches found for pattern '{pattern}' in {file_pattern} files."
    except Exception as e:
        return f"Error searching in files: {str(e)}"

@tool
def analyze_imports(file_path: str) -> str:
    """Analyze imports in a file to understand dependencies."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content[:1000] if len(content) > 1000 else content,
            "file_extension": Path(file_path).suffix.lower(),
            "file_size": Path(file_path).stat().st_size
        }, indent=2)
    except Exception as e:
        return f"Error analyzing imports: {str(e)}"

@tool
def find_functions(file_path: str) -> str:
    """Find and list all function definitions in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content[:5000] if len(content) > 5000 else content,
            "file_extension": Path(file_path).suffix.lower(),
            "file_size": Path(file_path).stat().st_size
        }, indent=2)
    except Exception as e:
        return f"Error finding functions: {str(e)}"

@tool
def find_classes(file_path: str) -> str:
    """Find and list all class definitions in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content[:5000] if len(content) > 5000 else content,
            "file_extension": Path(file_path).suffix.lower(),
            "file_size": Path(file_path).stat().st_size
        }, indent=2)
    except Exception as e:
        return f"Error finding classes: {str(e)}"

@tool
def count_lines_of_code(directory: str = ".", file_pattern: str = "*") -> str:
    """Count the total lines of code in files matching the pattern in the directory."""
    try:
        total_lines = 0
        file_count = 0
        file_stats = {}
        
        directory = Path(directory)
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        relative_path = str(filepath.relative_to(directory))
                        file_stats[relative_path] = lines
                        total_lines += lines
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
        return f"Error counting lines of code: {str(e)}"

@tool
def find_todos(directory: str = ".", file_pattern: str = "*") -> str:
    """Find TODO comments in the codebase."""
    try:
        todos = {}
        todo_pattern = r'(?://|#|/\*|\*|<!--)\s*TODO:?\s*(.*?)(?:\*/|-->|\n|$)'
        
        directory = Path(directory)
        for filepath in directory.rglob(file_pattern):
            if filepath.is_file():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(todo_pattern, content)
                        if matches:
                            relative_path = str(filepath.relative_to(directory))
                            todos[relative_path] = [match.strip() for match in matches if match.strip()]
                except Exception:
                    continue
        
        if todos:
            return json.dumps(todos, indent=2)
        else:
            return "No TODOs found in the codebase."
    except Exception as e:
        return f"Error finding TODOs: {str(e)}"

@tool
def get_file_info(file_path: str) -> str:
    """Get detailed information about a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        
        stat_info = path.stat()
        file_size = stat_info.st_size
        mod_time = stat_info.st_mtime
        
        return json.dumps({
            "file": str(path),
            "size_bytes": file_size,
            "size_human": f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB",
            "modification_time": datetime.datetime.fromtimestamp(mod_time).isoformat(),
            "extension": path.suffix.lower(),
            "is_binary": is_binary_file(str(path)),
            "is_hidden": path.name.startswith('.')
        }, indent=2)
    except Exception as e:
        return f"Error getting file info: {str(e)}"



from pathlib import Path
import argparse
import json
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

# ... (previous tool definitions remain the same)

def read_prompt_file(file_path: str) -> str:
    """
    Read a prompt from an external file.
    
    Args:
        file_path: Path to the file containing the prompt
        
    Returns:
        str: The contents of the prompt file
        
    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If unable to read the file
        UnicodeDecodeError: If the file encoding is invalid
    """
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read().strip()
                return content
        except Exception as e:
            raise UnicodeDecodeError(f"Error reading prompt file with latin-1 encoding: {str(e)}")
    except Exception as e:
        raise Exception(f"Error reading prompt file: {str(e)}")

def analyze_codebase(directory_path: str, prompt_file_path: str):
    """
    Analyze a codebase using the ReAct agent with a prompt from an external file.
    
    Args:
        directory_path: Path to the codebase directory
        prompt_file_path: Path to the file containing the analysis prompt
        
    Returns:
        str: The final analysis result from the agent
    """
    try:
        # Read the prompt from the external file
        prompt = read_prompt_file(prompt_file_path)
        
        # Create the initial message with the file contents
        initial_message = {
            "role": "user",
            "content": prompt
        }
        
        # Run the agent
        result = agent.invoke({
            "messages": [initial_message]
        })
        
        # Return the final response
        return result["messages"][-1].content
    except Exception as e:
        return f"Error running code analysis: {str(e)}"

def main():
    """
    Main entry point for the code analysis tool.
    """
    parser = argparse.ArgumentParser(description="Analyze a codebase using a LangGraph ReAct agent")
    parser.add_argument("--directory", help="Path to the codebase directory")
    parser.add_argument("--prompt-file", required=True, help="Path to the file containing the analysis prompt")
    
    try:
        args = parser.parse_args()
        
        # Validate inputs
        if not Path(args.directory).exists():
            raise ValueError(f"Directory not found: {args.directory}")
        if not Path(args.prompt_file).exists():
            raise ValueError(f"Prompt file not found: {args.prompt_file}")
        
        # Run the analysis
        analysis_result = analyze_codebase(args.directory, args.prompt_file)
        
        # Print the result
        print(analysis_result)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()