from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import re
import ast
import datetime
import mimetypes
import pathspec
import os
import argparse
from binaryornot.check import is_binary
import openai
import math
import fnmatch

# Helper function for binary file detection
def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary using binaryornot library."""
    return is_binary(file_path)

def get_gitignore_spec(directory: str) -> pathspec.PathSpec:
    """
    Get a PathSpec object from .gitignore in the specified directory.
    
    Args:
        directory: Directory to look for .gitignore
        
    Returns:
        PathSpec object with patterns from .gitignore
    """
    # Define common patterns to ignore (similar to .gitignore)
    # we do these because we should skip them anyway, they're just going to cause problems
    ignore_patterns = [
        "node_modules/",
        ".git/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".DS_Store",
        "*.egg-info/",
        ".idea/",
        ".vscode/"
    ]
    
    # Check if .gitignore exists and add its patterns
    gitignore_path = Path(directory) / ".gitignore"
    if gitignore_path.exists():
        try:
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.readlines()
                for line in gitignore_content:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore_patterns.append(line)
            print(f"Added {len(gitignore_content)} patterns from .gitignore")
        except Exception as e:
            print(f"Error reading .gitignore: {e}")
    
    # Create pathspec matcher
    return pathspec.PathSpec.from_lines(
        pathspec.patterns.GitWildMatchPattern, ignore_patterns
    )


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

# System prompt components for the tech writer agent
ROLE_AND_TASK = """
You are a code analysis expert that helps developers understand codebases. 
Your task is to analyse the local filesystem to understand the structure and functionality of a codebase.
"""

GENERAL_ANALYSIS_GUIDELINES = """
Follow these guidelines:
- Use the available tools to explore the filesystem, read files, and gather information.
- Make no assumptions about file types or formats - analyse each file based on its content and extension.
- Focus on providing a comprehensive, accurate, and well-structured analysis.
- Include code snippets and examples where relevant.
- Organize your response with clear headings and sections.
- Cite specific files and line numbers to support your observations.
"""

INPUT_PROCESSING_GUIDELINES = """
Important guidelines:
- The user's analysis prompt will be provided in the initial message, prefixed with the base directory of the codebase (e.g., "Base directory: /path/to/codebase").
- Analyse the codebase based on the instructions in the prompt, using the base directory as the root for all relative paths.
- Make no assumptions about file types or formats - analyse each file based on its content and extension.
- Adapt your analysis approach based on the codebase and the prompt's requirements.
- Be thorough but focus on the most important aspects as specified in the prompt.
- Provide clear, structured summaries of your findings in your final response.
- Use language-specific parsing for Python (.py) and JavaScript (.js) files where applicable (e.g., for analysing imports, functions, or classes).
- Handle errors gracefully and report them clearly if they occur.
"""

CODE_ANALYSIS_STRATEGIES = """
When analysing code:
- Start by exploring the directory structure to understand the project organisation.
- Identify key files like README, configuration files, or main entry points.
- Ignore temporary files and directories like node_modules, .git, etc.
- Analyse relationships between components (e.g., imports, function calls).
- Look for patterns in the code organisation (e.g., line counts, TODOs).
- Summarise your findings to help someone understand the codebase quickly, tailored to the prompt.
"""

PLANNING_STRATEGY = """
You should follow the ReAct pattern:
1. Thought: Reason about what you need to do next
2. Action: Use one of the available tools
3. Observation: Review the results of the tool
4. Repeat until you have enough information to provide a final answer
"""

QUALITY_REQUIREMENTS = """
When you've completed your analysis, provide a final answer in the form of a comprehensive Markdown document 
that provides a mutually exclusive and collectively exhaustive (MECE) analysis of the codebase using the user prompt.

Your analysis should be thorough, accurate, and helpful for someone trying to understand this codebase.
"""

# Combine all components to form the complete system prompt
SYSTEM_PROMPT = f"{ROLE_AND_TASK}\n\n{GENERAL_ANALYSIS_GUIDELINES}\n\n{INPUT_PROCESSING_GUIDELINES}\n\n{CODE_ANALYSIS_STRATEGIES}\n\n{PLANNING_STRATEGY}\n\n{QUALITY_REQUIREMENTS}"

# Tool functions
def find_all_matching_files(
    directory: str, 
    pattern: str = "*", 
    respect_gitignore: bool = True, 
    include_hidden: bool = False,
    include_subdirs: bool = True
) -> List[Path]:
    """
    Find files matching a pattern while respecting .gitignore.
    
    Args:
        directory: Directory to search in
        pattern: File pattern to match (glob format)
        respect_gitignore: Whether to respect .gitignore patterns
        include_hidden: Whether to include hidden files and directories
        include_subdirs: Whether to include files in subdirectories
        
    Returns:
        List of Path objects for matching files
    """
    try:
        directory_path = Path(directory).resolve()
        if not directory_path.exists():
            print(f"Directory not found: {directory}")
            return []
        
        # Get gitignore spec if needed
        spec = get_gitignore_spec(str(directory_path)) if respect_gitignore else None
        
        result = []
        
        # Choose between recursive and non-recursive search
        if include_subdirs:
            paths = directory_path.rglob(pattern)
        else:
            paths = directory_path.glob(pattern)
            
        for path in paths:
            if path.is_file():
                # Skip hidden files if not explicitly included
                if not include_hidden and any(part.startswith('.') for part in path.parts):
                    continue
                
                # Skip if should be ignored
                if respect_gitignore and spec:
                    # Use pathlib to get relative path and convert to posix format
                    rel_path = path.relative_to(directory_path)
                    rel_path_posix = rel_path.as_posix()
                    if spec.match_file(rel_path_posix):
                        continue
                result.append(path)
        
        return result
    except Exception as e:
        print(f"Error finding files: {e}")
        return []

def read_file(file_path: str) -> str:
    """Read the contents of a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)
        
        if is_binary_file(file_path):
            return json.dumps({"error": f"Cannot read binary file: {file_path}"}, indent=2)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error reading file: {str(e)}"}, indent=2)

def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2 * 3")
        
    Returns:
        JSON string containing the expression and its result
    """
    try:
        # Create a safe environment for evaluating expressions
        # This uses Python's ast.literal_eval for safety instead of eval()
        def safe_eval(expr):
            # Replace common mathematical functions with their math module equivalents
            expr = expr.replace("^", "**")  # Support for exponentiation
            
            # Parse the expression into an AST
            parsed_expr = ast.parse(expr, mode='eval')
            
            # Check that the expression only contains safe operations
            for node in ast.walk(parsed_expr):
                # Allow names that are defined in the math module
                if isinstance(node, ast.Name) and node.id not in math.__dict__:
                    if node.id not in ['True', 'False', 'None']:
                        raise ValueError(f"Invalid name in expression: {node.id}")
                
                # Only allow safe operations
                elif isinstance(node, ast.Call):
                    if not (isinstance(node.func, ast.Name) and node.func.id in math.__dict__):
                        raise ValueError(f"Invalid function call in expression")
            
            # Evaluate the expression with the math module available
            return eval(compile(parsed_expr, '<string>', 'eval'), {"__builtins__": {}}, math.__dict__)
        
        # Evaluate the expression
        result = safe_eval(expression)
        
        return json.dumps({
            "expression": expression,
            "result": result
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"Error evaluating expression: {str(e)}",
            "expression": expression
        }, indent=2)

# Dictionary mapping tool names to their functions
TOOLS = {
    "find_all_matching_files": find_all_matching_files,
    "read_file": read_file,
    "calculate": calculate
}

class ReActAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        """Initialise the ReAct agent with the specified model."""
        self.model_name = model_name
        self.temperature = 0  # Always use temperature 0 for deterministic results
        self.memory = []
        self.final_answer = None
        
        # Format tools for OpenAI API
        self.openai_tools = self.create_openai_tool_definitions(TOOLS)
    
    def create_openai_tool_definitions(self, tools_dict):
        """
        Create OpenAI tool definitions from a dictionary of Python functions.
        
        Args:
            tools_dict: Dictionary mapping tool names to their function implementations
        
        Returns:
            List of tool definitions in the format required by OpenAI's API
        """
        import inspect
        openai_tools = []
        
        for name, func in tools_dict.items():
            # Extract parameter information from function signature
            sig = inspect.signature(func)
            parameters = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                param_type = "string"  # Default type
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == List[str]:
                    param_type = "array"
                
                param_info = {"type": param_type}
                if param_type == "array":
                    param_info["items"] = {"type": "string"}
                
                # Add description from docstring if available
                if func.__doc__:
                    param_info["description"] = f"Parameter for {name}"
                
                parameters[param_name] = param_info
                
                # Check if parameter is required
                if param.default == inspect.Parameter.empty and param_name != 'self':
                    required.append(param_name)
            
            # Create the tool definition
            tool_def = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func.__doc__ or f"Function {name}",
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required
                    }
                }
            }
            openai_tools.append(tool_def)
        
        return openai_tools

    def initialise_memory(self, prompt, directory):
        """Initialise the agent's memory with the prompt and directory."""
        self.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.memory.append({"role": "user", "content": f"Base directory: {directory}\n\n{prompt}"})
        self.final_answer = None
    
    def call_llm(self):
        """Call the LLM with the current memory and tools."""
        try:
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=self.memory,
                tools=self.openai_tools,
                temperature=self.temperature
            )
            return response.choices[0].message
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            # Return a simple error message in the expected format
            return {"content": f"Error: {str(e)}", "tool_calls": None}
    
    def check_llm_result(self, assistant_message):
        """Check the LLM result and return the appropriate action."""
        print(f"\nLLM Response:\n{assistant_message.content}\n")
        
        # Add the assistant's message to memory
        self.memory.append(assistant_message)
        
        # Check if this is a final answer (no tool calls)
        if not assistant_message.tool_calls:
            if "Final Answer:" in assistant_message.content:
                final_answer_match = re.search(r"Final Answer:(.+)", assistant_message.content, re.DOTALL)
                if final_answer_match:
                    return "final_answer", final_answer_match.group(1).strip()
            return "final_answer", assistant_message.content
        
        # Otherwise, it's a tool call
        return "tool_call", assistant_message.tool_calls[0]
    
    def execute_tool(self, tool_call):
        """Execute the requested tool and return the observation."""
        tool_name = tool_call.function.name
        
        try:
            # Parse arguments
            args = json.loads(tool_call.function.arguments)
            
            # Check if the tool exists
            if tool_name not in TOOLS:
                return f"Error: Tool '{tool_name}' not found."
            
            # Execute the tool
            print(f"Executing tool: {tool_name} with args: {args}")
            result = TOOLS[tool_name](**args)
            return result
        except json.JSONDecodeError:
            return f"Error: Invalid JSON in tool arguments: {tool_call.function.arguments}"
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"
    
    def run(self, prompt, directory):
        """Run the agent to analyse a codebase."""
        self.initialise_memory(prompt, directory)
        max_steps = 15
        
        for step in range(max_steps):
            print(f"\n--- Step {step + 1} ---")
            
            # Call the LLM
            assistant_message = self.call_llm()
            
            # Check the result
            result_type, result_data = self.check_llm_result(assistant_message)
            
            if result_type == "final_answer":
                self.final_answer = result_data
                break
            elif result_type == "tool_call":
                # Execute the tool
                observation = self.execute_tool(result_data)
                
                # Add the observation to memory
                self.memory.append({
                    "role": "tool",
                    "tool_call_id": result_data.id,
                    "name": result_data.function.name,
                    "content": observation
                })
            
            print(f"Memory length: {len(self.memory)} messages")
        
        if self.final_answer is None:
            self.final_answer = "Failed to complete the analysis within the step limit."
        
        return self.final_answer

def get_command_line_args():
    """
    Parse and return command-line arguments.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments
    """
    parser = argparse.ArgumentParser(description="Analyse a codebase using a ReAct agent")
    parser.add_argument("--directory", required=True, help="Path to the codebase directory")
    parser.add_argument("--prompt-file", required=True, help="Path to the file containing the analysis prompt")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name used for analysis")
    
    return parser.parse_args()

def analyse_codebase(directory_path: str, prompt_file_path: str, model_name: str) -> str:
    """Analyse a codebase using the ReAct agent with a prompt from an external file."""
    try:
        directory = Path(directory_path).resolve()
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Read the prompt
        prompt = read_prompt_file(prompt_file_path)
        
        # Create and run the agent
        agent = ReActAgent(model_name=model_name)
        result = agent.run(prompt, directory)
        
        return result
    except Exception as e:
        return f"Error running code analysis: {str(e)}"

def save_results(analysis_result: str, model_name: str) -> Path:
    """
    Save analysis results to a timestamped Markdown file in the output directory.
    
    Args:
        analysis_result: The analysis text to save
        model_name: The name of the model used for analysis
        
    Returns:
        Path to the saved file
    """
    # Create output directory if it doesn't exist
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}-{model_name}.md"
    output_path = output_dir / output_filename
    
    # Save results to markdown file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(analysis_result)
    
    print(f"Analysis complete. Results saved to {output_path}")
    
    return output_path

def main():

    try:
        args = get_command_line_args()
        analysis_result = analyse_codebase(args.directory, args.prompt_file, args.model)
        save_results(analysis_result, args.model)

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    main()