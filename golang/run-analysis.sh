#!/bin/bash

# Exit on error
set -e

# Check if the tech-writer-agent binary exists
if [ ! -f "tech-writer-agent" ]; then
    echo "Building tech-writer-agent..."
    go build -o tech-writer-agent ./src
fi

# Default values
DIRECTORY="."
PROMPT_FILE="../prompts/architecture.prompt.txt"
MODEL="gpt-4o-mini"
AGENT_TYPE="react"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --directory|-d)
            DIRECTORY="$2"
            shift 2
            ;;
        --prompt|-p)
            PROMPT_FILE="$2"
            shift 2
            ;;
        --model|-m)
            MODEL="$2"
            shift 2
            ;;
        --agent-type|-a)
            AGENT_TYPE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run the analysis
echo "Running analysis on directory: $DIRECTORY"
echo "Using prompt file: $PROMPT_FILE"
echo "Using model: $MODEL"
echo "Using agent type: $AGENT_TYPE"

./tech-writer-agent \
    --directory "$DIRECTORY" \
    --prompt "$PROMPT_FILE" \
    --model "$MODEL" \
    --agent-type "$AGENT_TYPE"
