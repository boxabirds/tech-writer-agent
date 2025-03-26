# Tech Writer Agent - Go Implementation

This is a Go port of the Tech Writer Agent, a tool that uses LLMs to analyze codebases and generate documentation.

## Features

- Analyze codebases using LLMs (OpenAI GPT models)
- Generate comprehensive documentation
- Support for different agent types (ReAct and Reflexion)
- Configurable via command-line arguments
- Respects `.gitignore` patterns

## Setup

1. Clone the repository
2. Create a `.env` file based on `.env.example` with your API keys
3. Run the setup script:

```bash
./setup.sh
```

## Usage

Run the analysis with the provided script:

```bash
./run-analysis.sh [options]
```

Options:
- `--directory`, `-d`: Directory to analyze (default: ".")
- `--prompt`, `-p`: Path to prompt file (default: "../prompts/architecture.prompt.txt")
- `--model`, `-m`: Model to use (default: "gpt-4o-mini")
- `--agent-type`, `-a`: Agent type to use (default: "react")

Or run the binary directly:

```bash
./tech-writer-agent --directory <dir> --prompt <prompt-file> --model <model> --agent-type <agent-type>
```

## Development

The codebase follows a modular architecture with:

- Agent interfaces and implementations
- File handling utilities
- OpenAI API integration
- Command-line interface

To build the project:

```bash
go build -o tech-writer-agent ./src
```

## License

Same as the original Tech Writer Agent project.
