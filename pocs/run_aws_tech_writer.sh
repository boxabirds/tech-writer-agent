#!/bin/bash
# Script to run the AWS tech writer agent with the existing virtual environment

# Default values
DEFAULT_DIRECTORY="."
DEFAULT_PROMPT="prompt.txt"
DEFAULT_MODEL="amazon.nova-pro-v1:0"
DEFAULT_AGENT_TYPE="react"
DEFAULT_OUTPUT=""

# Parse command line arguments
DIRECTORY=$DEFAULT_DIRECTORY
PROMPT_FILE=$DEFAULT_PROMPT
MODEL=$DEFAULT_MODEL
AGENT_TYPE=$DEFAULT_AGENT_TYPE
OUTPUT=$DEFAULT_OUTPUT

# Function to display usage information
function show_usage {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --dir DIR       Directory to analyze (default: current directory)"
    echo "  --prompt FILE   Path to prompt file (default: prompt.txt)"
    echo "  --model MODEL   AWS Bedrock model to use (default: amazon.nova-lite-v1:0)"
    echo "                  Available models: amazon.nova-lite-v1:0, amazon.nova-pro-v1:0"
    echo "  --agent-type TYPE    Agent type to use (default: react)"
    echo "                  Available types: react, reflexion"
    echo "  --output FILE   Path to save analysis results (default: auto-generated)"
    echo "  --help          Show this help message"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dir)
            DIRECTORY="$2"
            shift 2
            ;;
        --prompt)
            PROMPT_FILE="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --agent-type)
            AGENT_TYPE="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Check if directory exists
if [ ! -d "$DIRECTORY" ]; then
    echo "Error: Directory '$DIRECTORY' does not exist."
    exit 1
fi

# Check if prompt file exists
if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: Prompt file '$PROMPT_FILE' does not exist."
    echo "Using the default prompt.txt file..."
    
    # Create a default prompt file if it doesn't exist
    if [ ! -f "prompt.txt" ]; then
        cat > "prompt.txt" << EOL
Please analyze this codebase and provide a comprehensive overview of its structure, functionality, and key components.

Include the following in your analysis:
1. Overall architecture and design patterns
2. Key components and their relationships
3. Data flow and state management
4. External dependencies and integrations
5. Code organization and file structure
6. Technology stack and frameworks used
7. Potential areas for improvement or technical debt

Format your response as a well-structured markdown document with appropriate headings, lists, and code examples where relevant.
EOL
        echo "Created default prompt file: prompt.txt"
        PROMPT_FILE="prompt.txt"
    fi
fi

# Activate the existing virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check AWS credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Warning: AWS credentials not found in environment variables."
    echo "Please ensure AWS credentials are properly configured."
    echo "You can set them up in ~/.aws/credentials or as environment variables."
fi

# Build command
CMD="python aws-tech-writer-from-scratch.py \"$DIRECTORY\" \"$PROMPT_FILE\" --model \"$MODEL\" --agent-type \"$AGENT_TYPE\""

# Add output if specified
if [ -n "$OUTPUT" ]; then
    CMD="$CMD --output \"$OUTPUT\""
fi

# Run the tech writer agent
echo "Running AWS tech writer agent..."
echo "Command: $CMD"
eval $CMD

# Deactivate virtual environment
deactivate

echo "Analysis complete."
