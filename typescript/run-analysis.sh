#!/bin/bash

# Script to run the tech writer agent analysis on a codebase

# Check if required arguments are provided
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <directory_to_analyze> <prompt_file> [options]"
  echo "Options:"
  echo "  --model <model_name>       Model to use (default: gpt-4o-mini)"
  echo "  --agent-type <agent_type>  Agent type to use (react or reflexion, default: react)"
  echo "  --base-url <url>           Base URL for API (optional)"
  exit 1
fi

# Ensure the TypeScript code is built
if [ ! -d "dist" ]; then
  echo "Building TypeScript project..."
  npm run build
fi

# Run the analysis
echo "Starting analysis..."
node dist/index.js "$@"

# Check if analysis was successful
if [ $? -eq 0 ]; then
  echo "Analysis completed successfully!"
  echo "Results are saved in the output directory."
else
  echo "Analysis failed. Check the error messages above."
fi
