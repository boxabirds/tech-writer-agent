from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import json
import re
import ast
import datetime
import pathspec
from pathspec.patterns import GitWildMatchPattern
import os
import argparse
from binaryornot.check import is_binary
from openai import OpenAI
import math
import inspect
import typing
import logging
import textwrap


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Check for API keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


# Warn if neither API key is set
if not GEMINI_API_KEY and not OPENAI_API_KEY:
    logger.warning("Neither GEMINI_API_KEY nor OPENAI_API_KEY environment variables are set.")
    logger.warning("Please set at least one of these environment variables to use the respective API.")
    logger.warning("You can get a Gemini API key from https://aistudio.google.com")
    logger.warning("You can get an OpenAI API key from https://platform.openai.com")

# Define model providers: check, high volume and fast. 
GEMINI_MODELS = ["gemini-2.0-flash"]
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"]


def get_gitignore_spec(directory: str) -> pathspec.PathSpec:
    """
    Get a PathSpec object from .gitignore in the specified directory.
    
    Args:
        directory: The directory containing .gitignore
        
    Returns:
        A PathSpec object for matching against .gitignore patterns
    """
    ignore_patterns = []
    
    # Try to read .gitignore file
    gitignore_path = Path(directory) / ".gitignore"
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        ignore_patterns.append(line)
                        
            logger.info(f"Added {len(ignore_patterns)} patterns from .gitignore")
        except (IOError, UnicodeDecodeError) as e:
            logger.error(f"Error reading .gitignore: {e}")
    
    # Create pathspec matcher
    return pathspec.PathSpec.from_lines(
        GitWildMatchPattern, ignore_patterns
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
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(f"Error reading prompt file with latin-1 encoding: {str(e)}")
    except (IOError, OSError) as e:
        raise IOError(f"Error reading prompt file: {str(e)}")

# System prompt components for the tech writer agent
ROLE_AND_TASK = textwrap.dedent("""
    You are an expert tech writer that helps teams understand codebases with accurate and concise supporting analysis and documentation. 
    Your task is to analyse the local filesystem to understand the structure and functionality of a codebase.
""")

GENERAL_ANALYSIS_GUIDELINES = textwrap.dedent("""
    Follow these guidelines:
    - Use the available tools to explore the filesystem, read files, and gather information.
    - Make no assumptions about file types or formats - analyse each file based on its content and extension.
    - Focus on providing a comprehensive, accurate, and well-structured analysis.
    - Include code snippets and examples where relevant.
    - Organize your response with clear headings and sections.
    - Cite specific files and line numbers to support your observations.
""")

INPUT_PROCESSING_GUIDELINES = textwrap.dedent("""
    Important guidelines:
    - The user's analysis prompt will be provided in the initial message, prefixed with the base directory of the codebase (e.g., "Base directory: /path/to/codebase").
    - Analyse the codebase based on the instructions in the prompt, using the base directory as the root for all relative paths.
    - Make no assumptions about file types or formats - analyse each file based on its content and extension.
    - Adapt your analysis approach based on the codebase and the prompt's requirements.
    - Be thorough but focus on the most important aspects as specified in the prompt.
    - Provide clear, structured summaries of your findings in your final response.
    - Handle errors gracefully and report them clearly if they occur but don't let them halt the rest of the analysis.
""")

CODE_ANALYSIS_STRATEGIES = textwrap.dedent("""
    When analysing code:
    - Start by exploring the directory structure to understand the project organisation.
    - Identify key files like README, configuration files, or main entry points.
    - Ignore temporary files and directories like node_modules, .git, etc.
    - Analyse relationships between components (e.g., imports, function calls).
    - Look for patterns in the code organisation (e.g., line counts, TODOs).
    - Summarise your findings to help someone understand the codebase quickly, tailored to the prompt.
""")

REACT_PLANNING_STRATEGY = textwrap.dedent("""
    You should follow the ReAct pattern:
    1. Thought: Reason about what you need to do next
    2. Action: Use one of the available tools
    3. Observation: Review the results of the tool
    4. Repeat until you have enough information to provide a final answer
""")

QUALITY_REQUIREMENTS = textwrap.dedent("""
    When you've completed your analysis, provide a final answer in the form of a comprehensive Markdown document 
    that provides a mutually exclusive and collectively exhaustive (MECE) analysis of the codebase using the user prompt.

    Your analysis should be thorough, accurate, and helpful for someone trying to understand this codebase.
""")

# Combine system prompt components
REACT_SYSTEM_PROMPT = f"{ROLE_AND_TASK}\n\n{GENERAL_ANALYSIS_GUIDELINES}\n\n{INPUT_PROCESSING_GUIDELINES}\n\n{CODE_ANALYSIS_STRATEGIES}\n\n{REACT_PLANNING_STRATEGY}\n\n{QUALITY_REQUIREMENTS}"

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
            logger.warning(f"Directory not found: {directory}")
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
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Error accessing files: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error finding files: {e}")
        return []

def read_file(file_path: str) -> Dict[str, Any]:
    """Read the contents of a file."""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        
        if is_binary(file_path):
            return {"error": f"Cannot read binary file: {file_path}"}
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "file": file_path,
            "content": content
        }
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except UnicodeDecodeError:
        return {"error": f"Cannot decode file as UTF-8: {file_path}"}
    except PermissionError:
        return {"error": f"Permission denied when reading file: {file_path}"}
    except IOError as e:
        return {"error": f"IO error reading file: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error reading file: {str(e)}"}

def calculate(expression: str) -> Dict[str, Any]:
    """
    Evaluate a mathematical expression and return the result.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2 * 3")
        
    Returns:
        Dictionary containing the expression and its result
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
        
        return {
            "expression": expression,
            "result": result
        }
    except SyntaxError as e:
        return {
            "error": f"Syntax error in expression: {str(e)}",
            "expression": expression
        }
    except ValueError as e:
        return {
            "error": f"Value error in expression: {str(e)}",
            "expression": expression
        }
    except TypeError as e:
        return {
            "error": f"Type error in expression: {str(e)}",
            "expression": expression
        }
    except Exception as e:
        return {
            "error": f"Unexpected error evaluating expression: {str(e)}",
            "expression": expression
        }

# Dictionary mapping tool names to their functions
TOOLS = {
    "find_all_matching_files": find_all_matching_files,
    "read_file": read_file,
    "calculate": calculate
}

class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles Path objects from pathlib.
    
    This encoder is necessary for serializing results from tool functions
    that return Path objects, which are not JSON-serializable by default.
    Used primarily in the execute_tool method when converting tool results
    to JSON strings for the LLM.
    """
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

def create_openai_tool_definitions(tools_dict):
    """
    Create tool definitions from a dictionary of Python functions.
    
    Args:
        tools_dict: Dictionary mapping tool names to Python functions
        
    Returns:
        List of tool definitions formatted for the OpenAI API
    """
    tools = []
    
    for name, func in tools_dict.items():
        # Extract function signature
        sig = inspect.signature(func)
        
        # Get docstring and parse it
        docstring = inspect.getdoc(func) or ""
        description = docstring.split("\n\n")[0] if docstring else ""
        
        # Build parameters
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            # Get parameter type annotation
            param_type = param.annotation
            if param_type is inspect.Parameter.empty:
                param_type = str
            
            # Get origin and args for generic types
            origin = typing.get_origin(param_type)
            args = typing.get_args(param_type)
            
            # Convert Python types to JSON Schema types
            if param_type == str:
                json_type = "string"
            elif param_type == int:
                json_type = "integer"
            elif param_type == float or param_type == "number":
                json_type = "number"
            elif param_type == bool:
                json_type = "boolean"
            elif origin is list or param_type == list:
                json_type = "array"
            elif origin is dict or param_type == dict:
                json_type = "object"
            else:
                # For complex types, default to string
                json_type = "string"
            
            # Extract parameter description from docstring
            param_desc = ""
            if docstring:
                # Look for parameter in docstring (format: param_name: description)
                param_pattern = rf"{param_name}:\s*(.*?)(?:\n\s*\w+:|$)"
                param_match = re.search(param_pattern, docstring, re.DOTALL)
                if param_match:
                    param_desc = param_match.group(1).strip()
            
            # Add parameter to schema
            parameters["properties"][param_name] = {
                "type": json_type,
                "description": param_desc
            }
            
            # Mark required parameters
            if param.default is inspect.Parameter.empty:
                parameters["required"].append(param_name)
        
        # Create tool definition
        tool_def = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        
        tools.append(tool_def)
    
    return tools

def call_llm(model_name, memory, base_url=None):
    """
    Call the LLM with the current memory and tools.
    
    Args:
        model_name: Name of the model to use
        memory: List of message objects
        base_url: Optional base URL for the API
        
    Returns:
        The message from the assistant
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=base_url)
        response = client.chat.completions.create(
            model=model_name,
            messages=memory,
            tools=create_openai_tool_definitions(TOOLS),
            temperature=0
        )
        return response.choices[0].message
    except Exception as e:
        error_msg = f"Error calling API: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def check_llm_result(assistant_message, memory):
    """
    Check if the LLM result is a final answer or a tool call.
    
    Args:
        assistant_message: The message from the assistant
        memory: The memory list to update
        
    Returns:
        tuple: (result_type, result_data)
            result_type: "final_answer" or "tool_calls"
            result_data: The final answer string or list of tool calls
    """
    memory.append(assistant_message)
    
    if assistant_message.tool_calls:
        return "tool_calls", assistant_message.tool_calls
    else:
        return "final_answer", assistant_message.content

def execute_tool(tool_call):
    """
    Execute a tool call and return the result.
    
    Args:
        tool_call: The tool call object from the LLM
        
    Returns:
        str: The result of the tool execution
    """
    tool_name = tool_call.function.name
    
    if tool_name not in TOOLS:
        return f"Error: Unknown tool {tool_name}"
    
    try:
        # Parse the arguments
        args = json.loads(tool_call.function.arguments)
        
        # Call the tool function
        result = TOOLS[tool_name](**args)
        
        # Convert result to JSON string
        return json.dumps(result, cls=CustomEncoder, indent=2)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in tool arguments: {str(e)}"
    except TypeError as e:
        return f"Error: Invalid argument types: {str(e)}"
    except ValueError as e:
        return f"Error: Invalid argument values: {str(e)}"
    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"

def run_analysis(prompt, directory, model_name="gpt-4o-mini", base_url=None):
    """
    Run the agent to analyse a codebase using the ReAct pattern.
    
    Args:
        prompt: The analysis prompt
        directory: The directory containing the codebase to analyse
        model_name: The name of the model to use
        base_url: Optional base URL for the API
        
    Returns:
        The analysis result
    """
    # Initialize memory
    memory = [{"role": "system", "content": REACT_SYSTEM_PROMPT}]
    memory.append({"role": "user", "content": f"Base directory: {directory}\n\n{prompt}"})
    final_answer = None
    max_steps = 15
    
    for step in range(max_steps):
        logger.info(f"\n--- Step {step + 1} ---")
        
        # Call the LLM
        assistant_message = call_llm(model_name, memory, base_url)
        
        # Check the result
        result_type, result_data = check_llm_result(assistant_message, memory)
        
        if result_type == "final_answer":
            final_answer = result_data
            break
        elif result_type == "tool_calls":
            # Execute each tool call
            for tool_call in result_data:
                # Execute the tool
                observation = execute_tool(tool_call)
                
                # Add the observation to memory
                memory.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": observation
                })
        
        logger.info(f"Memory length: {len(memory)} messages")
    
    if final_answer is None:
        final_answer = "Failed to complete the analysis within the step limit."
    
    return final_answer

def get_command_line_args():
    """Get command line arguments."""
    parser = argparse.ArgumentParser(description="Analyse a codebase using an LLM agent.")
    parser.add_argument("directory", help="Directory containing the codebase to analyse")
    parser.add_argument("prompt_file", help="Path to a file containing the analysis prompt")
    
    # Define available models based on which API keys are set
    available_models = []
    if OPENAI_API_KEY:
        available_models.extend(OPENAI_MODELS)
    if GEMINI_API_KEY:
        available_models.extend(GEMINI_MODELS)
    
    parser.add_argument("--model", choices=available_models, default=available_models[0] if available_models else None,
                      help="Model to use for analysis")
    parser.add_argument("--base-url", default=None,
                      help="Base URL for the API (automatically set based on model if not provided)")
    
    args = parser.parse_args()
    
    # Validate that we have a model available
    if not available_models:
        parser.error("No API keys set. Please set OPENAI_API_KEY or GEMINI_API_KEY environment variables.")
    
    return args

def analyse_codebase(directory_path: str, prompt_file_path: str, model_name: str, base_url: str = None) -> str:
    """Analyse a codebase using the specified model with a prompt from an external file."""
    try:
        directory = Path(directory_path).resolve()
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Read the prompt
        prompt = read_prompt_file(prompt_file_path)
        
        # Set appropriate base URL based on the model
        if base_url is None:
            if model_name in GEMINI_MODELS:
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            else:
                base_url = None  # Use default OpenAI base URL for OpenAI models
        
        # Run the analysis
        logger.info("Using ReAct agent")
        result = run_analysis(prompt, directory, model_name, base_url)
        
        return result
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return f"Error running code analysis: {str(e)}"
    except IOError as e:
        logger.error(f"IO error: {e}")
        return f"Error running code analysis: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
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
    output_filename = f"{timestamp}-react-{model_name}.md"
    output_path = output_dir / output_filename
    
    # Save results to markdown file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(analysis_result)
        
        logger.info(f"Analysis complete. Results saved to {output_path}")
        
        return output_path
    except IOError as e:
        logger.error(f"Error saving results: {e}")
        raise IOError(f"Failed to save results: {str(e)}")

def main():
    try:
        args = get_command_line_args()
        analysis_result = analyse_codebase(args.directory, args.prompt_file, args.model, args.base_url)
        save_results(analysis_result, args.model)

    except (FileNotFoundError, IOError) as e:
        logger.error(f"File error: {str(e)}")
        return 1
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    main() 