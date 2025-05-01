# LangGraph Chatbot with File System Tools

A file browsing chatbot built with LangGraph that can use either:
- Local models through an OpenAI-compatible API endpoint (e.g., Ollama)
- OpenAI's models (including GPT-4o Mini)

## Prerequisites

- Python 3.8+
- `uv` package manager (https://github.com/astral-sh/uv)
- For local models: Access to an OpenAI-compatible API endpoint (e.g., http://gruntus:11434/v1)
- For OpenAI models: An OpenAI API key set as the `OPENAI_API_KEY` environment variable

## Installation

1. Clone this repository
2. Create a virtual environment and install dependencies using `uv`:

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

## Usage

Activate the virtual environment and run the chatbot:

```bash
# Activate the virtual environment (if not already activated)
source .venv/bin/activate

# Run the chatbot with the default local model (starts in the current directory)
python file_browser_agent.py

# Run the chatbot with OpenAI's GPT-4o Mini
python file_browser_agent.py --model-type openai --model-name gpt-4o-mini

# Run the chatbot with a specific starting directory
python file_browser_agent.py --start-dir ~/Documents

# Run the chatbot with a custom model name
python file_browser_agent.py --model-name llama3.2:70b
```

The chatbot will start in interactive mode. Type your messages and press Enter to get responses. Type 'exit' to quit.

### Command Line Arguments

The chatbot supports the following command line arguments:

- `--prompt-file`: Path to a file containing the system prompt (default: prompt.txt)
- `--start-dir`: Starting directory for file operations (default: current directory)
- `--model-type`: Type of model to use: `local` (Ollama) or `openai` (default: local)
- `--model-name`: Name of the model to use (default: llama3.2:3b for local, gpt-4o-mini for openai)

### File System Tools

The chatbot includes the following file system tools:

1. **List Directory**: View files and folders in the current or specified directory
   - Example: "List the files in the current directory" or "Show me what's in ~/Documents"

2. **Change Directory**: Navigate to a different directory
   - Example: "Change to the Documents folder" or "Go up one directory level"

3. **Read File**: View the contents of a file
   - Example: "Show me the contents of README.md" or "Read the first 500 characters of requirements.txt"

### Custom System Prompts

The chatbot supports loading a system prompt from an external file:

```bash
# Use the default prompt file (prompt.txt)
python file_browser_agent.py

# Use a custom prompt file
python file_browser_agent.py --prompt-file my_custom_prompt.txt
```

The default prompt file (`prompt.txt`) contains:
```
You are a file browsing assistant. you can list directories, navigate, and view the contents of files
```

You can create your own prompt files to customize the chatbot's behavior.

## Using with OpenAI Models

To use the chatbot with OpenAI models, you need to:

1. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY=your-api-key-here
   ```
   
   Or create a `.env` file in the project directory with:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

2. Run the chatbot with the `--model-type openai` flag:
   ```bash
   python file_browser_agent.py --model-type openai
   ```
   
   This will use the default OpenAI model (gpt-4o-mini). You can specify a different model with:
   ```bash
   python file_browser_agent.py --model-type openai --model-name gpt-4
   ```

## How It Works

This chatbot uses LangGraph to create a state machine with:
- A state schema that keeps track of the conversation messages and current directory
- A chatbot node that processes messages through the selected model
- A tool executor node that handles file system operations
- A router that determines whether to execute tools or return the final response

The model is accessed either through:
- A local OpenAI-compatible API endpoint (e.g., Ollama at http://gruntus:11434/v1)
- The official OpenAI API

---

## Tech Writer Agent (OpenRouter Version)

A standalone codebase analysis agent that uses OpenRouter's API for LLM calls, supporting model/cost benchmarking and quantitative comparison. This version is fully independent (no shared code with other agents) and preserves UK English spelling and naming conventions.

### Design Decisions
- **Standalone Implementation**: No shared code with the original agent, ensuring full independence for benchmarking and reproducibility.
- **OpenRouter API**: Uses OpenRouter's OpenAI-compatible API endpoints (https://openrouter.ai/docs) with the API key in the `Authorization: Bearer ...` header.
- **Model Support**: Supports OpenRouter equivalents of OpenAI and Google models (e.g., `openai/gpt-4o`, `google/gemini-pro`).
- **Cost Reporting**: Fetches pricing from OpenRouter's `/pricing` endpoint, reporting both token usage and actual cost for each run.
- **Benchmarking**: Includes a dedicated test script to benchmark performance, token usage, and cost across models.
- **No Shared Logic**: All logic is implemented within `tech-writer-from-scratch-openrouter.py` for strict reproducibility and isolation.

### Installation & Prerequisites
- Python 3.8+
- `uv` for package management
- OpenRouter API key (set as `OPENROUTER_API_KEY`)

### Usage

```bash
# Run the OpenRouter agent
python tech-writer-from-scratch-openrouter.py <directory> <prompt_file> --model <openrouter_model_name>

# Example:
python tech-writer-from-scratch-openrouter.py test-data/test-tools test-data/prompts/count-python-files.prompt.txt --model openai/gpt-4o
```

### Benchmarking

A test script `test_openrouter_agent.py` is provided to benchmark the agent across models:

```bash
python test_openrouter_agent.py
```

This will run the agent on sample prompts and directories, recording runtime, token usage, and cost, and output a summary table for comparison.

### Example Output

```
Model: openai/gpt-4o | Directory: test-data/test-tools | Prompt: test-data/prompts/count-python-files.prompt.txt
  Tokens: 1234 | Cost: $0.004321 | Runtime: 12.45s | Success: True

Summary Table:
Model                Tokens   Cost (USD)   Runtime (s)   Success
---------------------------------------------------------------
openai/gpt-4o         1234      0.004321        12.45     True
... (other models)
```

### Rationale
- **Cost Transparency**: OpenRouter exposes pricing information, allowing for actual cost calculation and quantitative comparison between models.
- **Model Diversity**: Supports a wide range of models from multiple providers via a single API.
- **Reproducibility**: Standalone implementation ensures results are not affected by changes in other agent versions.

### Caveats
- Ensure your OpenRouter API key is set as `OPENROUTER_API_KEY`.
- Model names and pricing may change; always verify with the latest OpenRouter documentation.

---
