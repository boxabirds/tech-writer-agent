import json
import requests
from datetime import datetime

# Custom Ollama base URL
OLLAMA_BASE_URL = "http://gruntus:11434/v1"

# Function to call Ollama API directly
def ollama_chat(model, messages, tools=None, tool_choice=None):
    url = f"{OLLAMA_BASE_URL}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    if tools:
        payload["tools"] = tools
    
    if tool_choice:
        payload["tool_choice"] = tool_choice
    
    response = requests.post(url, json=payload)
    return response.json()

# Define a simple function schema
function_schema = {
    "type": "function",
    "function": {
        "name": "get_weather",
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

# Mock function to simulate getting weather data
def get_weather(location, unit="celsius"):
    # In a real application, this would call a weather API
    mock_temps = {"New York": 22, "San Francisco": 18, "Miami": 30}
    temp = mock_temps.get(location, 25)
    
    if unit == "fahrenheit":
        temp = (temp * 9/5) + 32
    
    return {
        "location": location,
        "temperature": temp,
        "unit": unit,
        "condition": "sunny",
        "timestamp": datetime.now().isoformat()
    }

# Create a conversation
messages = [{"role": "user", "content": "What's the weather like in New York right now?"}]

# Call the model with function calling
response = ollama_chat(
    model="phi4-mini",
    messages=messages,
    tools=[function_schema],
    tool_choice="auto"
)

# Extract the message from the response
model_message = response.get("choices", [{}])[0].get("message", {})

# Add the response to the conversation
messages.append(model_message)

print("Initial model response:")
print(json.dumps(model_message, indent=2))

# Check if the model wants to call a function
if model_message.get("tool_calls"):
    for tool_call in model_message["tool_calls"]:
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])
        
        print(f"\nModel is calling function: {function_name}")
        print(f"With arguments: {function_args}")
        
        # Execute the function
        if function_name == "get_weather":
            result = get_weather(
                location=function_args.get("location"),
                unit=function_args.get("unit", "celsius")
            )
            
            # Add the function result to the conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": json.dumps(result)
            })
    
    # Get the final response from the model
    final_response = ollama_chat(
        model="phi4-mini",
        messages=messages
    )
    
    final_message = final_response.get("choices", [{}])[0].get("message", {})
    
    print("\nFinal response:")
    print(final_message.get("content", "No response content"))
else:
    print("\nModel response (no function call):")
    print(model_message.get("content", "No response content"))