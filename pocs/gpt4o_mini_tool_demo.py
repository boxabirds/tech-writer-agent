"""
GPT-4o Mini Tool Calling Demo

A simple demonstration of tool calling capabilities with OpenAI's GPT-4o Mini model.
This script shows how to define tools, process tool calls, and handle the results.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Initialize the OpenAI client
client = OpenAI()  # Uses OPENAI_API_KEY from environment

# Define a simple weather tool
weather_tool = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "The temperature unit to use"
                }
            },
            "required": ["location"]
        }
    }
}

# Define a file listing tool (similar to our chatbot's tool)
list_files_tool = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files in the specified directory",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "The directory path to list files from"
                }
            },
            "required": ["directory"]
        }
    }
}

# Mock function to get weather data
def get_current_weather(location, unit="celsius"):
    """Mock function to simulate getting weather data"""
    # In a real application, this would call a weather API
    weather_data = {
        "New York": {"temp": 22, "condition": "Sunny"},
        "San Francisco": {"temp": 18, "condition": "Foggy"},
        "Miami": {"temp": 30, "condition": "Clear"},
        "London": {"temp": 15, "condition": "Rainy"},
    }
    
    # Get temperature for the location or use a default
    weather = weather_data.get(location, {"temp": 25, "condition": "Clear"})
    temp = weather["temp"]
    
    # Convert to Fahrenheit if requested
    if unit == "fahrenheit":
        temp = (temp * 9/5) + 32
    
    return {
        "location": location,
        "temperature": temp,
        "unit": unit,
        "condition": weather["condition"],
        "timestamp": datetime.now().isoformat()
    }

# Function to list files in a directory
def list_files(directory):
    """List files in the specified directory"""
    try:
        # Expand user directory if needed (e.g., ~/)
        directory = os.path.expanduser(directory)
        
        # Check if directory exists
        if not os.path.exists(directory):
            return {"error": f"Directory '{directory}' does not exist"}
        
        # Check if it's a directory
        if not os.path.isdir(directory):
            return {"error": f"'{directory}' is not a directory"}
        
        # List files and directories
        items = os.listdir(directory)
        
        # Get file details
        file_details = []
        for item in items:
            item_path = os.path.join(directory, item)
            is_dir = os.path.isdir(item_path)
            size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
            
            file_details.append({
                "name": item,
                "is_directory": is_dir,
                "size_bytes": size
            })
        
        return {
            "directory": directory,
            "items": file_details,
            "count": len(file_details)
        }
    except Exception as e:
        return {"error": str(e)}

def run_conversation(user_input):
    """Run a conversation with GPT-4o Mini using tools"""
    print(f"User: {user_input}")
    print("\nSending request to GPT-4o Mini...\n")
    
    # Initial message from the user
    messages = [{"role": "user", "content": user_input}]
    
    # First API call with tools
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=[weather_tool, list_files_tool],
        tool_choice="auto"
    )
    
    # Get the model's response
    assistant_message = response.choices[0].message
    print(f"Assistant: {assistant_message.content or '[Tool call requested]'}")
    
    # Add the assistant's message to the conversation
    messages.append(assistant_message.model_dump())
    
    # Check if the model wants to use a tool
    if assistant_message.tool_calls:
        print("\nTool calls detected!")
        
        # Process each tool call
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"\nCalling function: {function_name}")
            print(f"With arguments: {json.dumps(function_args, indent=2)}")
            
            # Execute the appropriate function
            result = None
            if function_name == "get_current_weather":
                result = get_current_weather(
                    location=function_args.get("location"),
                    unit=function_args.get("unit", "celsius")
                )
            elif function_name == "list_files":
                result = list_files(
                    directory=function_args.get("directory", ".")
                )
            
            if result:
                print(f"\nFunction result: {json.dumps(result, indent=2)}")
                
                # Add the function result to the conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(result)
                })
        
        # Second API call to get the final response
        print("\nSending function results back to GPT-4o Mini...\n")
        second_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        final_message = second_response.choices[0].message
        print(f"Final response: {final_message.content}")
        return final_message.content
    else:
        print("\nNo tool calls needed. Model responded directly.")
        return assistant_message.content

def main():
    print("GPT-4o Mini Tool Calling Demo")
    print("=============================")
    
    # Example 1: Weather query
    print("\n--- Example 1: Weather Query ---")
    run_conversation("What's the weather like in San Francisco?")
    
    # Example 2: File listing
    print("\n\n--- Example 2: File Listing ---")
    run_conversation("Can you list the files in my current directory?")
    
    # Example 3: Combined query
    print("\n\n--- Example 3: Combined Query ---")
    run_conversation("I need to check the weather in New York and also see what files I have in my home directory.")

if __name__ == "__main__":
    main()
