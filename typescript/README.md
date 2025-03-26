# Tech Writer Agent - TypeScript Implementation

This is a TypeScript port of the original Python-based Tech Writer Agent. The agent analyzes codebases using LLMs (Large Language Models) to generate comprehensive documentation and architectural overviews.

## Features

- **Multiple Agent Types**: Choose between ReAct and Reflexion agent patterns
- **Multiple Model Support**: Compatible with OpenAI models (gpt-4o-mini, gpt-4o) and Gemini models
- **Filesystem Analysis**: Tools for exploring and analyzing codebases
- **Customizable Prompts**: Easily modify the system prompts for different analysis styles

## Prerequisites

- Node.js (v16 or higher)
- npm or yarn
- OpenAI API key and/or Gemini API key

## Installation

1. Clone the repository
2. Navigate to the typescript directory
3. Install dependencies:

```bash
cd typescript
npm install
```

## Configuration

Create a `.env` file in the typescript directory with your API keys:

```
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

At least one of these keys must be provided.

## Usage

### Building the Project

```bash
npm run build
```

### Running the Agent

```bash
npm start -- <directory> <prompt_file> [options]
```

#### Arguments:

- `directory`: Path to the codebase directory to analyze
- `prompt_file`: Path to a file containing the analysis prompt

#### Options:

- `--model <model>`: Model to use for analysis (default: gpt-4o-mini)
- `--agent-type <type>`: Type of agent to use (react or reflexion, default: react)
- `--base-url <url>`: Base URL for the API (optional)

### Example

```bash
npm start -- /path/to/codebase /path/to/prompts/architecture.prompt.txt --model gpt-4o --agent-type reflexion
```

## Output

The analysis results are saved as Markdown files in the `output` directory with timestamped filenames in the format:
`YYYYMMDD-HHMMSS-agenttype-modelname.md`

## Development

For development with hot reloading:

```bash
npm run dev -- /path/to/codebase /path/to/prompts/architecture.prompt.txt
```

## Agent Types

### ReAct Agent

The ReAct agent follows a simple pattern:
1. Thought: Reason about what to do next
2. Action: Use a tool
3. Observation: Review the results
4. Repeat until analysis is complete

### Reflexion Agent

The Reflexion agent extends the ReAct pattern with self-reflection:
1. Thought: Reason about what to do next
2. Action: Use a tool
3. Observation: Review the results
4. Reflection: Analyze approach and identify improvements
5. Repeat until analysis is complete

## License

Same as the original Python implementation.
