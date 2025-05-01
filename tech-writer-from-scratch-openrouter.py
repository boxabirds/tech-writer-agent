"""
Tech Writer Agent (OpenRouter Version)
======================================

A standalone codebase analysis agent using OpenRouter's API for LLM calls, supporting model/cost benchmarking.
- No shared code with other agents.
- Reports token usage and actual cost using OpenRouter's pricing API.
- Preserves UK English spelling and naming conventions.
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
    "gemini-2.0-flash": "google/gemini-2.0-flash",
    "gemini-2.5-pro-preview-03-25": "google/gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash-preview-04-17": "google/gemini-2.5-flash-preview-04-17"
}
OPENROUTER_MODELS = list(MODEL_NAME_TO_OPENROUTER_ID.keys())

# Utility: Read prompt file

def read_prompt_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# Utility: Find files matching pattern (minimal, standalone)
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

# Utility: Read file contents
def read_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# Utility: Evaluate an expression (for benchmarking)
def calculate(expression: str) -> Dict[str, Any]:
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}

# OpenRouter API Client (minimal, standalone)
class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str = OPENROUTER_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://openrouter.ai/docs",
            "X-Title": "TechWriterAgent"
        }

    def list_models(self) -> List[Dict[str, Any]]:
        resp = requests.get(f"{self.base_url}/models", headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_pricing(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/pricing", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def chat_completion(self, model: str, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        data = {"model": model, "messages": messages}
        if tools:
            data["tools"] = tools
        resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json()

# TechWriterAgent (OpenRouter)
class TechWriterAgentOpenRouter:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is required.")
        if model_name not in MODEL_NAME_TO_OPENROUTER_ID:
            raise ValueError(f"Model '{model_name}' is not supported. Choose from: {list(MODEL_NAME_TO_OPENROUTER_ID.keys())}")
        self.model_name = model_name
        self.openrouter_model_id = MODEL_NAME_TO_OPENROUTER_ID[model_name]
        self.client = OpenRouterClient(OPENROUTER_API_KEY)
        self.memory = []
        self.final_answer = None
        self.system_prompt = self._build_system_prompt()
        self.tools = {
            "find_all_matching_files": find_all_matching_files,
            "read_file": read_file,
            "calculate": calculate
        }
        self.token_usage = 0
        self.cost_usd = 0.0

    def _build_system_prompt(self) -> str:
        return textwrap.dedent("""
        You are an expert tech writer that helps teams understand codebases with accurate and concise supporting analysis and documentation.
        Your task is to analyse the local filesystem to understand the structure and functionality of a codebase. Use UK English spelling throughout.
        """)

    def create_tool_definitions(self) -> List[Dict[str, Any]]:
        # Minimal OpenAI-compatible tool schema
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func.__doc__ or name,
                    "parameters": {"type": "object", "properties": {}}  # Simplified
                }
            } for name, func in self.tools.items()
        ]

    def call_llm(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return self.client.chat_completion(self.openrouter_model_id, messages, tools=self.create_tool_definitions())

    def run(self, prompt: str, directory: str) -> str:
        self.memory = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        start_time = time.time()
        result = self.call_llm(self.memory)
        end_time = time.time()
        # Extract completion, usage, and cost
        completion = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        self.token_usage = usage.get("total_tokens", 0)
        self.cost_usd = self._calculate_cost(self.openrouter_model_id, self.token_usage)
        self.final_answer = completion
        logger.info(f"Model: {self.model_name} | Tokens: {self.token_usage} | Cost: ${self.cost_usd:.6f} | Time: {end_time - start_time:.2f}s")
        return completion

    def _calculate_cost(self, model: str, total_tokens: int) -> float:
        pricing = self.client.get_pricing()
        # Find model pricing info
        model_price = next((p for p in pricing.get("models", []) if p["id"] == model), None)
        if model_price:
            price_per_million = model_price.get("price_per_million_tokens", 0)
            return (total_tokens / 1_000_000) * price_per_million
        return 0.0

# Command-line interface
def main():
    parser = argparse.ArgumentParser(description="Tech Writer Agent (OpenRouter)")
    parser.add_argument("directory", type=str, help="Directory to analyse")
    parser.add_argument("prompt_file", type=str, help="Prompt file path")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="OpenRouter model name")
    parser.add_argument("--json", action="store_true", help="Output result as a single JSON object for programmatic use")
    args = parser.parse_args()

    prompt = read_prompt_file(args.prompt_file)
    agent = TechWriterAgentOpenRouter(model_name=args.model)
    start_time = time.time()
    try:
        result = agent.run(prompt, args.directory)
        success = True
    except Exception as e:
        result = f"Error: {str(e)}"
        success = False
    end_time = time.time()
    runtime = end_time - start_time

    if args.json:
        output = {
            "result": agent.final_answer if success else result,
            "model": agent.model_name,
            "tokens": agent.token_usage,
            "cost_usd": agent.cost_usd,
            "runtime": runtime,
            "success": success
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        print("\n=== Analysis Result ===\n")
        print(agent.final_answer if success else result)
        print("\n=== Token Usage ===\n")
        print(f"Tokens used: {agent.token_usage}")
        print(f"Cost (USD): ${agent.cost_usd:.6f}")

if __name__ == "__main__":
    main()
