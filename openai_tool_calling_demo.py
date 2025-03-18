"""
OpenAI GPT-4o Mini Tool Calling Demo

This script demonstrates how to use the OpenAI API to implement tool calling
(function calling) with the GPT-4o Mini model.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import time

# Load environment variables from .env file (create this file with your API key)
load_dotenv()

# Initialize the OpenAI client
client = OpenAI(
    # This will use the OPENAI_API_KEY environment variable by default
    # You can also set it explicitly: api_key="your-api-key"
)

# Define multiple tools (functions) that the model can call
tools = [
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_mortgage",
            "description": "Calculate monthly mortgage payment",
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {
                        "type": "number",
                        "description": "The loan amount in dollars"
                    },
                    "interest_rate": {
                        "type": "number",
                        "description": "Annual interest rate (percentage)"
                    },
                    "loan_term": {
                        "type": "integer",
                        "description": "Loan term in years"
                    }
                },
                "required": ["principal", "interest_rate", "loan_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products in a catalog",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for products"
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category to filter by",
                        "enum": ["electronics", "clothing", "home", "food", "all"]
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price filter"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by",
                        "enum": ["price_asc", "price_desc", "popularity", "rating"]
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Mock function to simulate getting weather data
def get_weather(location, unit="celsius"):
    """
    Mock function to simulate getting weather data.
    In a real application, this would call a weather API.
    """
    mock_temps = {"New York": 22, "San Francisco": 18, "Miami": 30, "London": 15}
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

# Mock function to calculate mortgage payments
def calculate_mortgage(principal, interest_rate, loan_term):
    """
    Calculate monthly mortgage payment using the formula:
    M = P[r(1+r)^n]/[(1+r)^n-1]
    """
    # Convert annual interest rate to monthly rate (decimal)
    monthly_rate = (interest_rate / 100) / 12
    # Convert loan term to months
    loan_term_months = loan_term * 12
    
    # Calculate monthly payment
    if monthly_rate == 0:
        monthly_payment = principal / loan_term_months
    else:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** loan_term_months) / ((1 + monthly_rate) ** loan_term_months - 1)
    
    return {
        "principal": principal,
        "interest_rate": interest_rate,
        "loan_term_years": loan_term,
        "monthly_payment": round(monthly_payment, 2),
        "total_payment": round(monthly_payment * loan_term_months, 2),
        "total_interest": round((monthly_payment * loan_term_months) - principal, 2)
    }

# Mock function to search products
def search_products(query, category="all", max_price=None, sort_by="popularity"):
    """
    Mock function to simulate searching for products.
    In a real application, this would query a database or API.
    """
    # Sample product database
    products = [
        {"id": 1, "name": "Smartphone X", "category": "electronics", "price": 799.99, "rating": 4.5, "popularity": 95},
        {"id": 2, "name": "Laptop Pro", "category": "electronics", "price": 1299.99, "rating": 4.8, "popularity": 90},
        {"id": 3, "name": "Cotton T-shirt", "category": "clothing", "price": 19.99, "rating": 4.2, "popularity": 85},
        {"id": 4, "name": "Designer Jeans", "category": "clothing", "price": 89.99, "rating": 4.0, "popularity": 80},
        {"id": 5, "name": "Coffee Table", "category": "home", "price": 249.99, "rating": 4.6, "popularity": 75},
        {"id": 6, "name": "Organic Apples", "category": "food", "price": 4.99, "rating": 4.7, "popularity": 70},
    ]
    
    # Filter by search query (case-insensitive)
    results = [p for p in products if query.lower() in p["name"].lower()]
    
    # Filter by category if not "all"
    if category != "all":
        results = [p for p in results if p["category"] == category]
    
    # Filter by max price if provided
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]
    
    # Sort results
    if sort_by == "price_asc":
        results.sort(key=lambda p: p["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda p: p["price"], reverse=True)
    elif sort_by == "rating":
        results.sort(key=lambda p: p["rating"], reverse=True)
    else:  # Default: sort by popularity
        results.sort(key=lambda p: p["popularity"], reverse=True)
    
    return {
        "query": query,
        "category": category,
        "max_price": max_price,
        "sort_by": sort_by,
        "result_count": len(results),
        "results": results
    }

def process_tool_calls(assistant_message, messages):
    """Process tool calls from the assistant message and add results to the conversation."""
    if not assistant_message.tool_calls:
        return messages
    
    print("\nTool calls detected!")
    
    # Process each tool call
    for tool_call in assistant_message.tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        print(f"\nModel is calling function: {function_name}")
        print(f"With arguments: {json.dumps(function_args, indent=2)}")
        
        # Execute the appropriate function based on the function name
        result = None
        if function_name == "get_weather":
            result = get_weather(
                location=function_args.get("location"),
                unit=function_args.get("unit", "celsius")
            )
        elif function_name == "calculate_mortgage":
            result = calculate_mortgage(
                principal=function_args.get("principal"),
                interest_rate=function_args.get("interest_rate"),
                loan_term=function_args.get("loan_term")
            )
        elif function_name == "search_products":
            result = search_products(
                query=function_args.get("query"),
                category=function_args.get("category", "all"),
                max_price=function_args.get("max_price"),
                sort_by=function_args.get("sort_by", "popularity")
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
    
    return messages

def run_conversation(user_input, tool_choice="auto"):
    """Run a complete conversation with the model, handling tool calls."""
    # Create a conversation with a user message
    messages = [{"role": "user", "content": user_input}]
    
    print(f"User: {user_input}")
    print("\nSending request to GPT-4o Mini...\n")
    
    # First call to the model with tool calling capability
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Specify the GPT-4o Mini model
        messages=messages,
        tools=tools,
        tool_choice=tool_choice
    )
    
    # Extract the assistant's message from the response
    assistant_message = response.choices[0].message
    
    # Add the assistant's response to the conversation
    messages.append(assistant_message.model_dump())
    
    print("Initial model response:")
    print(f"Assistant: {assistant_message.content if assistant_message.content else '[No content, tool call requested]'}")
    
    # Check if the model wants to call a function
    if assistant_message.tool_calls:
        # Process tool calls and add results to messages
        messages = process_tool_calls(assistant_message, messages)
        
        print("\nSending function results back to GPT-4o Mini...\n")
        
        # Get the final response from the model
        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        final_message = final_response.choices[0].message
        
        print("Final response:")
        print(f"Assistant: {final_message.content}")
        
        return final_message.content
    else:
        print("\nModel responded directly (no function call):")
        print(f"Assistant: {assistant_message.content}")
        
        return assistant_message.content

def main():
    print("OpenAI GPT-4o Mini Tool Calling Demo")
    print("====================================")
    print("This demo shows how GPT-4o Mini can use tools to answer questions.\n")
    
    # Example 1: Weather query (should trigger get_weather tool)
    print("\n--- Example 1: Weather Query ---")
    run_conversation("What's the weather like in San Francisco right now?")
    time.sleep(1)  # Add a small delay between examples
    
    # Example 2: Mortgage calculation (should trigger calculate_mortgage tool)
    print("\n\n--- Example 2: Mortgage Calculation ---")
    run_conversation("I want to buy a house for $350,000 with a 30-year mortgage at 4.5% interest. What would my monthly payment be?")
    time.sleep(1)  # Add a small delay between examples
    
    # Example 3: Product search (should trigger search_products tool)
    print("\n\n--- Example 3: Product Search ---")
    run_conversation("Can you find me some electronics under $1000?")
    time.sleep(1)  # Add a small delay between examples
    
    # Example 4: Forcing a specific tool
    print("\n\n--- Example 4: Forcing a Specific Tool ---")
    run_conversation(
        "Tell me about the weather.",
        tool_choice={"type": "function", "function": {"name": "get_weather"}}
    )
    
    print("\n\nDemo completed!")

if __name__ == "__main__":
    main()
