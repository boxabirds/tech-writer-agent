#!/bin/bash

# Exit on error
set -e

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install required packages if not already installed
echo "Checking dependencies..."
pip install -r requirements.txt

# Run the refinement process
echo "Starting prompt refinement process..."
python refine-tech-writer-prompt.py prompts/new-starter.prompt.txt landscapehub gpt-4o

# Deactivate virtual environment
deactivate

echo "Refinement process completed." 