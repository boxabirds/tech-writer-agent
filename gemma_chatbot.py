"""
A LangGraph chatbot using Phi-4 through OpenAI API.
Supports loading a system prompt from an external file and includes
file system tools for listing files, navigating directories, and reading files.
Can use either a local model through an OpenAI-compatible API or OpenAI's GPT-4o Mini.
"""
import os
import argparse
import json
from pathlib import Path
from typing import Annotated, Dict, List, Any, Optional
from typing_extensions import TypedDict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Load environment variables from .env file
load_dotenv()

# Define the base URL for the local model
LOCAL_BASE_URL = "http://gruntus:11434/v1"  # Using /v1 for OpenAI API compatibility

# Define the State schema
class State(TypedDict):
    # Messages will be appended rather than overwritten
    messages: Annotated[List[Dict[str, Any]], add_messages]
    # Current working directory
    current_dir: str


def load_prompt_from_file(file_path: str) -> str:
    """Load a prompt from a file."""
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Warning: Prompt file '{file_path}' not found. Using default prompt.")
        return "You are a helpful assistant."
    except Exception as e:
        print(f"Warning: Error reading prompt file: {str(e)}. Using default prompt.")
        return "You are a helpful assistant."


# File system tools
def list_directory(directory: str) -> str:
    """
    List files and directories in the specified directory.
    
    Args:
        directory: The directory path to list (relative to current_dir)
    
    Returns:
        A string containing the directory listing
    """
    try:
        # Get the full path
        full_path = Path(directory).expanduser().resolve()
        
        # Check if the directory exists
        if not full_path.exists():
            return f"Error: Directory '{directory}' does not exist."
        
        # Check if it's a directory
        if not full_path.is_dir():
            return f"Error: '{directory}' is not a directory."
        
        # List the directory contents
        items = list(full_path.iterdir())
        
        # Sort items (directories first, then files)
        dirs = sorted([item for item in items if item.is_dir()], key=lambda x: x.name.lower())
        files = sorted([item for item in items if item.is_file()], key=lambda x: x.name.lower())
        
        # Format the output
        result = f"Contents of {full_path}:\n\n"
        
        if dirs:
            result += "Directories:\n"
            for d in dirs:
                result += f"📁 {d.name}/\n"
            result += "\n"
        
        if files:
            result += "Files:\n"
            for f in files:
                # Get file size in a human-readable format
                size = f.stat().st_size
                if size < 1024:
                    size_str = f"{size} bytes"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                
                result += f"📄 {f.name} ({size_str})\n"
        
        if not dirs and not files:
            result += "Directory is empty."
        
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def change_directory(current_dir: str, new_dir: str) -> Dict[str, str]:
    """
    Change the current working directory.
    
    Args:
        current_dir: The current working directory
        new_dir: The directory to change to (can be relative or absolute)
    
    Returns:
        A dictionary with the new current directory and a status message
    """
    try:
        # Handle special cases
        if new_dir == "..":
            # Go up one level
            new_path = Path(current_dir).parent
        elif new_dir.startswith("/"):
            # Absolute path
            new_path = Path(new_dir)
        elif new_dir.startswith("~"):
            # Home directory
            new_path = Path(new_dir).expanduser()
        else:
            # Relative path
            new_path = Path(current_dir) / new_dir
        
        # Resolve to absolute path
        new_path = new_path.resolve()
        
        # Check if the directory exists
        if not new_path.exists():
            return {
                "current_dir": current_dir,
                "message": f"Error: Directory '{new_dir}' does not exist."
            }
        
        # Check if it's a directory
        if not new_path.is_dir():
            return {
                "current_dir": current_dir,
                "message": f"Error: '{new_dir}' is not a directory."
            }
        
        # Return the new directory
        return {
            "current_dir": str(new_path),
            "message": f"Changed directory to {new_path}"
        }
    except Exception as e:
        return {
            "current_dir": current_dir,
            "message": f"Error changing directory: {str(e)}"
        }


def read_file(current_dir: str, file_path: str, max_chars: Optional[int] = None) -> str:
    """
    Read the contents of a file.
    
    Args:
        current_dir: The current working directory
        file_path: The path to the file (can be relative or absolute)
        max_chars: Maximum number of characters to read (None for all)
    
    Returns:
        The contents of the file as a string
    """
    try:
        # Handle absolute and relative paths
        if file_path.startswith("/") or file_path.startswith("~"):
            full_path = Path(file_path).expanduser()
        else:
            full_path = Path(current_dir) / file_path
        
        # Resolve to absolute path
        full_path = full_path.resolve()
        
        # Check if the file exists
        if not full_path.exists():
            return f"Error: File '{file_path}' does not exist."
        
        # Check if it's a file
        if not full_path.is_file():
            return f"Error: '{file_path}' is not a file."
        
        # Check file size
        file_size = full_path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10 MB limit
            return f"Error: File '{file_path}' is too large ({file_size / (1024 * 1024):.1f} MB). Maximum size is 10 MB."
        
        # Read the file
        with open(full_path, 'r', errors='replace') as f:
            content = f.read()
        
        # Truncate if needed
        if max_chars and len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[Truncated. File is {len(content)} characters long, showing first {max_chars} characters.]"
        
        return f"Contents of {full_path}:\n\n{content}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


# Define available tools
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in the specified directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory path to list. Can be absolute or relative to the current directory."
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "Change the current working directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_dir": {
                        "type": "string",
                        "description": "The directory to change to. Can be absolute or relative to the current directory. Use '..' to go up one level."
                    }
                },
                "required": ["new_dir"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file. Can be absolute or relative to the current directory."
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum number of characters to read. Default is to read the entire file."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]


def create_chatbot(system_prompt: str, model_type: str = "local", model_name: str = "llama3.2:3b"):
    """
    Create and return a LangGraph chatbot with the specified system prompt.
    
    Args:
        system_prompt: The system prompt to use
        model_type: The type of model to use ('local' or 'openai')
        model_name: The name of the model to use
    
    Returns:
        A compiled LangGraph
    """
    # Initialize the StateGraph with our State schema
    graph_builder = StateGraph(State)
    
    # Initialize the LLM based on the model type
    if model_type == "local":
        llm = ChatOpenAI(
            model=model_name,  # Model name
            base_url=LOCAL_BASE_URL,  # Custom API endpoint
            api_key="not-needed",  # API key is not needed for this endpoint
        )
    else:  # model_type == "openai"
        # Use OpenAI's API
        llm = ChatOpenAI(
            model=model_name,  # OpenAI model name
            # api_key will be loaded from OPENAI_API_KEY environment variable
        )
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # Define the chatbot node function
    def chatbot_node(state: State):
        """Process the current messages and return a response."""
        # Call the LLM with the current messages
        response = llm_with_tools.invoke(state["messages"])
        # Return the response to be added to the messages
        return {"messages": [response]}
    
    # Define the tool execution node
    def tool_executor(state: State):
        """Execute tools called by the LLM."""
        # Get the last message (from the assistant)
        last_message = state["messages"][-1]
        
        # Check if there are tool calls in the message
        if "tool_calls" not in last_message.additional_kwargs:
            # No tool calls, return unchanged state
            return {}
        
        tool_calls = last_message.additional_kwargs["tool_calls"]
        tool_results = []
        state_updates = {}
        
        # Process each tool call
        for tool_call in tool_calls:
            function_call = tool_call["function"]
            function_name = function_call["name"]
            
            # Parse arguments
            args = json.loads(function_call["arguments"])
            
            # Execute the appropriate tool
            if function_name == "list_directory":
                directory = args.get("directory", state["current_dir"])
                result = list_directory(directory)
            elif function_name == "change_directory":
                new_dir = args["new_dir"]
                cd_result = change_directory(state["current_dir"], new_dir)
                result = cd_result["message"]
                state_updates["current_dir"] = cd_result["current_dir"]
            elif function_name == "read_file":
                file_path = args["file_path"]
                max_chars = args.get("max_chars")
                result = read_file(state["current_dir"], file_path, max_chars)
            else:
                result = f"Error: Unknown tool '{function_name}'"
            
            # Create a tool result message
            tool_result = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result
            }
            tool_results.append(tool_result)
        
        # Return tool results and state updates
        updates = {"messages": tool_results}
        updates.update(state_updates)
        return updates
    
    # Define a router function to determine next steps
    def router(state: State):
        """Determine the next node based on the current state."""
        # Get the last message (from the assistant)
        last_message = state["messages"][-1]
        
        # Check if there are tool calls in the message
        if "tool_calls" in last_message.additional_kwargs:
            return "tool_executor"
        
        # No tool calls, we're done
        return "end"
    
    # Add nodes to the graph
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("tool_executor", tool_executor)
    
    # Define the edges
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", router, {
        "tool_executor": "tool_executor",
        "end": END
    })
    graph_builder.add_edge("tool_executor", "chatbot")
    
    # Compile the graph
    return graph_builder.compile()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run a LangGraph chatbot with file system tools')
    parser.add_argument('--prompt-file', type=str, default='prompt.txt',
                        help='Path to a file containing the system prompt (default: prompt.txt)')
    parser.add_argument('--start-dir', type=str, default=os.getcwd(),
                        help='Starting directory for file operations (default: current directory)')
    parser.add_argument('--model-type', type=str, choices=['local', 'openai'], default='local',
                        help='Type of model to use: local (Ollama) or openai (default: local)')
    parser.add_argument('--model-name', type=str, default='llama3.2:3b',
                        help='Name of the model to use (default: llama3.2:3b for local, gpt-4o-mini for openai)')
    return parser.parse_args()


def main():
    """Run the chatbot in a simple CLI loop."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set default model name based on model type if not specified
    if args.model_type == 'openai' and args.model_name == 'llama3.2:3b':
        args.model_name = 'gpt-4o-mini'
    
    # Load system prompt from file
    system_prompt = load_prompt_from_file(args.prompt_file)
    
    # Create the chatbot
    chatbot = create_chatbot(system_prompt, args.model_type, args.model_name)
    
    # Get the starting directory
    start_dir = str(Path(args.start_dir).expanduser().resolve())
    
    # Determine model display name
    if args.model_type == 'local':
        model_display = f"Local Model ({args.model_name})"
    else:
        model_display = f"OpenAI ({args.model_name})"
    
    print(f"File Browser Chatbot using {model_display} (type 'exit' to quit)")
    print("------------------------------------------------------")
    print(f"System prompt: {system_prompt}")
    print(f"Current directory: {start_dir}")
    
    # Initial state with system message
    state = {
        "messages": [
            {"role": "system", "content": system_prompt}
        ],
        "current_dir": start_dir
    }
    
    while True:
        # Get user input
        user_input = input("\nYou: ")
        
        # Check if user wants to exit
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Chatbot: Goodbye!")
            break
        
        # Add user message to state
        user_message = {"role": "user", "content": user_input}
        state["messages"].append(user_message)
        
        # Invoke the chatbot with the updated state
        state = chatbot.invoke(state)
        
        # Display the assistant's response
        for message in state["messages"]:
            if message["role"] == "assistant" and message not in state["messages"][:-len(state["messages"])]:
                print(f"\nChatbot: {message.content}")


if __name__ == "__main__":
    main()
