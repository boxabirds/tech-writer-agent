#!/bin/bash
set -e

# Activate virtual environment
source .venv/bin/activate

# Run the evaluation script
python tech-writer-agent-eval.py "$@"
