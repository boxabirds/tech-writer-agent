import os
import json
import glob
import re
from typing import Annotated, Sequence, TypedDict, List, Dict, Any, Optional, Union
import argparse
import datetime

from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Define the agent state
class CodeAnalysisState(TypedDict):
    """The state of the code analysis agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Define tools for code analysis
@tool
def list_files(path: str = ".") -> str:
    """
    List all files and directories in the specified path.
    If no path is provided, lists files in the current directory.
    """
    try:
        items = os.listdir(path)
        files = [f for f in items if os.path.isfile(os.path.join(path, f))]
        directories = [d for d in items if os.path.isdir(os.path.join(path, d))]
        
        result = {
            "files": files,
            "directories": directories,
            "current_path": os.path.abspath(path)
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """
    Read and return the contents of a file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        try:
            # Try with a different encoding if utf-8 fails
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading file with latin-1 encoding: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def search_in_files(pattern: str, file_pattern: str = "*", directory: str = ".") -> str:
    """
    Search for a regex pattern in files matching file_pattern in the specified directory.
    """
    try:
        results = {}
        for filepath in glob.glob(os.path.join(directory, "**", file_pattern), recursive=True):
            try:
                if os.path.isfile(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(pattern, content)
                        if matches:
                            relative_path = os.path.relpath(filepath, directory)
                            results[relative_path] = matches
            except Exception:
                # Skip files that can't be read
                continue
        
        if results:
            return json.dumps(results, indent=2)
        else:
            return f"No matches found for pattern '{pattern}' in {file_pattern} files."
    except Exception as e:
        return f"Error searching in files: {str(e)}"

@tool
def analyze_imports(file_path: str) -> str:
    """
    Analyze imports in a file to understand dependencies.
    The function will attempt to identify imports based on the file type.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return file content for the agent to analyze
        return json.dumps({
            "file": file_path,
            "content": content[:1000] if len(content) > 1000 else content,  # First 1000 chars for analysis
            "file_extension": os.path.splitext(file_path)[1].lower(),
            "file_size": os.path.getsize(file_path)
        }, indent=2)
    except Exception as e:
        return f"Error analyzing imports: {str(e)}"

@tool
def find_functions(file_path: str) -> str:
    """
    Find and list all function definitions in a file.
    Returns the file content for the agent to analyze and identify functions.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content[:5000] if len(content) > 5000 else content,  # First 5000 chars for analysis
            "file_extension": os.path.splitext(file_path)[1].lower(),
            "file_size": os.path.getsize(file_path)
        }, indent=2)
    except Exception as e:
        return f"Error finding functions: {str(e)}"

@tool
def find_classes(file_path: str) -> str:
    """
    Find and list all class definitions in a file.
    Returns the file content for the agent to analyze and identify classes.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return json.dumps({
            "file": file_path,
            "content": content[:5000] if len(content) > 5000 else content,  # First 5000 chars for analysis
            "file_extension": os.path.splitext(file_path)[1].lower(),
            "file_size": os.path.getsize(file_path)
        }, indent=2)
    except Exception as e:
        return f"Error finding classes: {str(e)}"

@tool
def count_lines_of_code(directory: str = ".", file_pattern: str = "*") -> str:
    """
    Count the total lines of code in files matching the pattern in the directory.
    """
    try:
        total_lines = 0
        file_count = 0
        file_stats = {}
        
        for filepath in glob.glob(os.path.join(directory, "**", file_pattern), recursive=True):
            try:
                if os.path.isfile(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        relative_path = os.path.relpath(filepath, directory)
                        file_stats[relative_path] = lines
                        total_lines += lines
                        file_count += 1
            except Exception:
                # Skip files that can't be read
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
    """
    Find TODO comments in the codebase.
    """
    try:
        todos = {}
        todo_pattern = r'(?://|#|/\*|\*|<!--)\s*TODO:?\s*(.*?)(?:\*/|-->|\n|$)'
        
        for filepath in glob.glob(os.path.join(directory, "**", file_pattern), recursive=True):
            try:
                if os.path.isfile(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = re.findall(todo_pattern, content)
                        if matches:
                            relative_path = os.path.relpath(filepath, directory)
                            todos[relative_path] = [match.strip() for match in matches if match.strip()]
            except Exception:
                # Skip files that can't be read
                continue
        
        if todos:
            return json.dumps(todos, indent=2)
        else:
            return "No TODOs found in the codebase."
    except Exception as e:
        return f"Error finding TODOs: {str(e)}"

@tool
def get_file_info(file_path: str) -> str:
    """
    Get detailed information about a file, including size, modification time, and other metadata.
    """
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        
        stat_info = os.stat(file_path)
        file_size = stat_info.st_size
        mod_time = stat_info.st_mtime
        
        # Return raw file information for the agent to interpret
        return json.dumps({
            "file": file_path,
            "size_bytes": file_size,
            "size_human": f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB",
            "modification_time": datetime.datetime.fromtimestamp(mod_time).isoformat(),
            "extension": os.path.splitext(file_path)[1].lower(),
            "is_binary": is_binary_file(file_path),
            "is_hidden": os.path.basename(file_path).startswith('.')
        }, indent=2)
    except Exception as e:
        return f"Error getting file info: {str(e)}"

def is_binary_file(file_path, sample_size=1024):
    """
    Check if a file is binary by reading a sample and looking for null bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(sample_size)
            # Check for null bytes which typically indicate binary content
            if b'\x00' in sample:
                return True
            
            # Try to decode as text
            try:
                sample.decode('utf-8')
                return False
            except UnicodeDecodeError:
                return True
    except Exception:
        # If we can't read the file, assume it's binary
        return True

@tool
def read_prompt_file(file_path: str) -> str:
    """
    Read a prompt file and return its contents.
    This is specifically for reading user prompts from external files.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        try:
            # Try with a different encoding if utf-8 fails
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading prompt file with latin-1 encoding: {str(e)}"
    except Exception as e:
        return f"Error reading prompt file: {str(e)}"

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
    read_prompt_file
]

# Define the ReAct system prompt
REACT_SYSTEM_PROMPT = """
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

# Create the LLM
def create_llm():
    return ChatOpenAI(model="gpt-4o", temperature=0)

# Define the agent node
def agent_node(state: CodeAnalysisState, config: RunnableConfig):
    llm = create_llm()
    messages = state["messages"]
    
    # Add the system message if it's not already there
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=REACT_SYSTEM_PROMPT)] + messages
    
    # Call the LLM
    response = llm.bind_tools(tools).invoke(messages, config)
    return {"messages": [response]}

# Define the tool node
def tool_node(state: CodeAnalysisState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}
    
    # Execute each tool call
    tool_outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        # Find the tool
        tool_to_call = next((t for t in tools if t.name == tool_name), None)
        if tool_to_call:
            try:
                # Call the tool
                result = tool_to_call.invoke(tool_args)
                # Create a tool message
                tool_outputs.append(
                    ToolMessage(
                        content=str(result),
                        name=tool_name,
                        tool_call_id=tool_id
                    )
                )
            except Exception as e:
                # Handle tool execution errors
                tool_outputs.append(
                    ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        name=tool_name,
                        tool_call_id=tool_id
                    )
                )
    
    return {"messages": tool_outputs}
    
# Define the conditional edge
def should_continue(state: CodeAnalysisState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message is from the agent and contains "Final Answer:", we're done
    if hasattr(last_message, "content") and "Final Answer:" in last_message.content:
        return "end"
    
    # If there are no tool calls, we're done
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "end"
    
    # Otherwise continue
    return "continue"

# Create the graph
def create_code_analysis_agent():
    workflow = StateGraph(CodeAnalysisState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    return workflow.compile()

# Function to run the code analysis agent
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
        # Create the agent
        agent = create_code_analysis_agent()
        
        # Set the initial state with instruction to read the prompt file
        initial_state = {
            "messages": [
                HumanMessage(content=f"Please read the prompt from the file: {prompt_file_path} and then analyze the codebase in directory: {directory_path}")
            ]
        }
        
        # Run the agent
        result = agent.invoke(initial_state)
        
        # Return the final response
        return result["messages"][-1].content
    except Exception as e:
        return f"Error running code analysis: {str(e)}"

# Main function
def main():
    """
    Main entry point for the code analysis tool.
    """
    parser = argparse.ArgumentParser(description="Analyze a codebase using a LangGraph ReAct agent")
    parser.add_argument("directory", help="Path to the codebase directory")
    parser.add_argument("prompt_file", help="Path to the file containing the analysis prompt")
    
    try:
        args = parser.parse_args()
        
        # Validate inputs
        if not os.path.exists(args.directory):
            raise ValueError(f"Directory not found: {args.directory}")
        if not os.path.exists(args.prompt_file):
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
    import sys
    sys.exit(main())
