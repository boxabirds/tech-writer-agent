"""
Tech Writer Agent (OpenRouter Version)
======================================

A standalone codebase analysis agent using OpenRouter's API for LLM calls, supporting model/cost benchmarking.
- Uses the same abstract base class architecture as the original
- Supports both ReAct and Reflexion agent patterns
- Reports token usage and actual cost using OpenRouter's pricing API
- Preserves UK English spelling and naming conventions
"""
import os
import json
import math
import time
import argparse
import logging
import requests
import textwrap
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import abc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODELS_ENDPOINT = f"{OPENROUTER_BASE_URL}/models"
OPENROUTER_PRICING_ENDPOINT = f"{OPENROUTER_BASE_URL}/pricing"
OPENROUTER_CHAT_ENDPOINT = f"{OPENROUTER_BASE_URL}/chat/completions"

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY environment variable is not set. Please set it to use the OpenRouter agent.")
    logger.warning("You can get an OpenRouter API key from https://openrouter.ai/keys")

# Model lists (use the same as in the original agent)
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-2.5-pro-preview-03-25", "gemini-2.5-flash-preview-04-17"]
OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o", "o3-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]
# Explicit mapping from short name to OpenRouter model id
MODEL_NAME_TO_OPENROUTER_ID = {
    # OpenAI
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4o": "openai/gpt-4o",
    "o3-mini": "openai/o3-mini",
    "gpt-4.1": "openai/gpt-4.1",
    "gpt-4.1-mini": "openai/gpt-4.1-mini",
    "gpt-4.1-nano": "openai/gpt-4.1-nano",
    # Gemini
    "gemini-2.0-flash": "google/gemini-2.0-flash-001",
    "gemini-2.5-pro-preview-03-25": "google/gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash-preview-04-17": "google/gemini-2.5-flash-preview-04-17"
}
OPENROUTER_MODELS = list(MODEL_NAME_TO_OPENROUTER_ID.keys())

# System prompt components for the tech writer agent (same as original)
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

REFLEXION_PLANNING_STRATEGY = textwrap.dedent("""
    You should follow the Reflexion pattern (an extension of ReAct):
    1. Thought: Reason about what you need to do next
    2. Action: Use one of the available tools
    3. Observation: Review the results of the tool
    4. Reflection: Analyze your approach, identify any mistakes or inefficiencies, and consider how to improve
    5. Repeat until you have enough information to provide a final answer
""")

QUALITY_REQUIREMENTS = textwrap.dedent("""
    When you've completed your analysis, provide a final answer in the form of a comprehensive Markdown document 
    that provides a mutually exclusive and collectively exhaustive (MECE) analysis of the codebase using the user prompt.

    Your analysis should be thorough, accurate, and helpful for someone trying to understand this codebase.
""")

# Utility functions (same as original)
def read_prompt_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def find_all_matching_files(directory: str, pattern: str = "*", include_hidden: bool = False, include_subdirs: bool = True) -> List[str]:
    base = Path(directory)
    if include_subdirs:
        files = base.rglob(pattern)
    else:
        files = base.glob(pattern)
    result = []
    for f in files:
        if not include_hidden and any(part.startswith('.') for part in f.parts):
            continue
        if f.is_file():
            result.append(str(f))
    return result

def read_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def calculate(expression: str) -> Dict[str, Any]:
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}

# Abstract base class (same pattern as original)
class Agent(abc.ABC):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is required.")
        if model_name not in MODEL_NAME_TO_OPENROUTER_ID:
            raise ValueError(f"Model '{model_name}' is not supported. Choose from: {list(MODEL_NAME_TO_OPENROUTER_ID.keys())}")
        
        self.model_name = model_name
        self.openrouter_model_id = MODEL_NAME_TO_OPENROUTER_ID[model_name]
        self.memory = []
        self.final_answer = None
        self.system_prompt = None
        self.tools = {
            "find_all_matching_files": find_all_matching_files,
            "read_file": read_file,
            "calculate": calculate
        }
        self.token_usage = 0
        self.cost_usd = 0.0

    def create_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func.__doc__ or name,
                    "parameters": {"type": "object", "properties": {}}
                }
            } for name, func in self.tools.items()
        ]

    def call_llm(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openrouter.ai/docs",
            "X-Title": "TechWriterAgent"
        }
        payload = {
            "model": self.openrouter_model_id,
            "messages": messages,
            "tools": self.create_tool_definitions(),
            "tool_choice": "auto",
            "usage": {"include": True}
        }
        response = requests.post(
            OPENROUTER_CHAT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()

    def check_llm_result(self, assistant_message: Dict[str, Any]) -> tuple:
        if "content" in assistant_message and assistant_message["content"]:
            return ("final_answer", assistant_message["content"])
        elif "tool_calls" in assistant_message and assistant_message["tool_calls"]:
            return ("tool_calls", assistant_message["tool_calls"])
        else:
            raise ValueError("LLM response contains neither content nor tool calls")

    def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
        
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        try:
            result = self.tools[tool_name](**tool_args)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @abc.abstractmethod
    def run(self, prompt: str, directory: str) -> str:
        pass

# ReAct Agent implementation
class ReActAgent(Agent):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        REACT_SYSTEM_PROMPT = f"{ROLE_AND_TASK}\n\n{GENERAL_ANALYSIS_GUIDELINES}\n\n{INPUT_PROCESSING_GUIDELINES}\n\n{CODE_ANALYSIS_STRATEGIES}\n\n{REACT_PLANNING_STRATEGY}\n\n{QUALITY_REQUIREMENTS}"
        
        super().__init__(model_name)
        self.system_prompt = REACT_SYSTEM_PROMPT

    def run(self, prompt: str, directory: str) -> str:
        self.memory = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Base directory: {directory}\n\n{prompt}"}
        ]
        
        while True:
            start_time = time.time()
            result = self.call_llm(self.memory)
            end_time = time.time()
            
            usage = result.get("usage", {})
            self.token_usage = usage.get("total_tokens", 0)
            self.cost_usd = float(usage.get("cost", 0.0) or 0.0)
            
            message = result["choices"][0]["message"]
            result_type, result_data = self.check_llm_result(message)
            
            if result_type == "final_answer":
                self.final_answer = result_data
                logger.info(f"Model: {self.model_name} | Tokens: {self.token_usage} | Cost: ${self.cost_usd:.6f} | Time: {end_time - start_time:.2f}s")
                return result_data
            
            # Handle tool calls
            tool_responses = []
            for tool_call in result_data:
                tool_result = self.execute_tool(tool_call)
                tool_responses.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": tool_call["function"]["name"],
                    "content": tool_result
                })
            
            self.memory.append({"role": "assistant", "content": None, "tool_calls": result_data})
            self.memory.extend(tool_responses)

# Reflexion Agent implementation
class ReflexionAgent(Agent):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        REFLEXION_SYSTEM_PROMPT = f"{ROLE_AND_TASK}\n\n{GENERAL_ANALYSIS_GUIDELINES}\n\n{INPUT_PROCESSING_GUIDELINES}\n\n{CODE_ANALYSIS_STRATEGIES}\n\n{REFLEXION_PLANNING_STRATEGY}\n\n{QUALITY_REQUIREMENTS}"
        
        super().__init__(model_name)
        self.system_prompt = REFLEXION_SYSTEM_PROMPT

    def run(self, prompt: str, directory: str) -> str:
        self.memory = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Base directory: {directory}\n\n{prompt}"}
        ]
        
        while True:
            start_time = time.time()
            result = self.call_llm(self.memory)
            end_time = time.time()
            
            usage = result.get("usage", {})
            self.token_usage = usage.get("total_tokens", 0)
            self.cost_usd = float(usage.get("cost", 0.0) or 0.0)
            
            message = result["choices"][0]["message"]
            result_type, result_data = self.check_llm_result(message)
            
            if result_type == "final_answer":
                self.final_answer = result_data
                logger.info(f"Model: {self.model_name} | Tokens: {self.token_usage} | Cost: ${self.cost_usd:.6f} | Time: {end_time - start_time:.2f}s")
                return result_data
            
            # Handle tool calls
            tool_responses = []
            for tool_call in result_data:
                tool_result = self.execute_tool(tool_call)
                tool_responses.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": tool_call["function"]["name"],
                    "content": tool_result
                })
            
            self.memory.append({"role": "assistant", "content": None, "tool_calls": result_data})
            self.memory.extend(tool_responses)
            
            # Add reflection step
            reflection_prompt = "Analyze your approach so far. What worked well? What could be improved?"
            self.memory.append({"role": "user", "content": reflection_prompt})

# Command-line interface with JSON output support
def main():
    parser = argparse.ArgumentParser(description="Tech Writer Agent (OpenRouter)")
    parser.add_argument("directory", type=str, help="Directory to analyse")
    parser.add_argument("prompt_file", type=str, help="Prompt file path")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="OpenRouter model name")
    parser.add_argument("--agent-type", type=str, default="react", choices=["react", "reflexion"], 
                       help="Agent type (react or reflexion)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    prompt = read_prompt_file(args.prompt_file)
    try:
        if args.agent_type == "react":
            agent = ReActAgent(model_name=args.model)
        else:
            agent = ReflexionAgent(model_name=args.model)
            
        start = time.time()
        result = agent.run(prompt, args.directory)
        runtime = time.time() - start
        success = True
    except Exception as e:
        runtime = 0.0
        success = False
        error_message = str(e)
        import traceback
        tb = traceback.format_exc()
    
    if args.json:
        if success:
            output = {
                "success": True,
                "result": result,
                "stats": {
                    "model": args.model,
                    "agent_type": args.agent_type,
                    "tokens": agent.token_usage,
                    "cost_usd": agent.cost_usd,
                    "runtime_seconds": runtime
                }
            }
        else:
            output = {
                "success": False,
                "error": error_message,
                "traceback": tb
            }
        print(json.dumps(output, indent=2))
    else:
        if success:
            print(result)
        else:
            print(f"Error: {error_message}")
            print(tb)

if __name__ == "__main__":
    main()
