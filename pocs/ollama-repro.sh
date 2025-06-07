#!/bin/bash

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install jq to run this script."
    echo "You can install it using:"
    echo "  - macOS: brew install jq"
    echo "  - Ubuntu/Debian: sudo apt-get install jq"
    echo "  - CentOS/RHEL: sudo yum install jq"
    exit 1
fi

# Get list of available models
MODELS=$(ollama list | awk 'NR>1 {print $1}')

# Function to test reproducibility for a specific model
test_model() {
    local model=$1
    local seed=42
    local temperature=0.0
    local top_k=1
    local stream=false
    local prompt="What's the capital of France"
    local num_runs=7
    
    echo "=========================================="
    echo "Testing model: $model"
    echo "Configuration:"
    echo "  Model: $model"
    echo "  Seed: $seed"
    echo "  Temperature: $temperature"
    echo "  Top K: $top_k"
    echo "  Stream: $stream"
    echo "  Prompt: $prompt"
    echo "=========================================="
    
    # Command to run Ollama API with fixed parameters
    CMD='curl -s http://localhost:11434/api/generate -d "{\"model\": \"'"$model"'\", \"prompt\": \"What'\''s the capital of France\", \"seed\": '"$seed"', \"temperature\": '"$temperature"', \"top_k\": '"$top_k"', \"stream\": '"$stream"'}"'
    
    # Function to extract concatenated response from JSON stream
    extract_response() {
        local file=$1
        # Use jq to select 'response' fields from each JSON object, concatenate them, and output raw text
        cat "$file" | jq -r '.response' | tr -d '\n' > "$file.parsed"
    }
    
    # Run the command multiple times and save outputs
    for i in $(seq 1 $num_runs); do
        echo "Running command ${i}th time..."
        eval "$CMD" > "output${i}_${model}.txt"
    done
    
    # Extract the full text from each run
    for i in $(seq 1 $num_runs); do
        extract_response "output${i}_${model}.txt"
    done
    
    # Compare all outputs
    echo "Comparing outputs..."
    all_identical=true
    for i in $(seq 1 $((num_runs-1))); do
        if ! diff "output${i}_${model}.txt.parsed" "output$((i+1))_${model}.txt.parsed" > /dev/null; then
            all_identical=false
            break
        fi
    done
    
    if [ "$all_identical" = true ]; then
        echo "✅ Success: All $num_runs outputs are identical with the above configuration."
        echo "Output: $(cat output1_${model}.txt.parsed)"
    else
        echo "❌ Failure: Outputs differ!"
        for i in $(seq 1 $num_runs); do
            echo "Run $i: $(cat output${i}_${model}.txt.parsed)"
        done
    fi
    
    # Clean up temporary files
    for i in $(seq 1 $num_runs); do
        rm -f "output${i}_${model}.txt" "output${i}_${model}.txt.parsed"
    done
    echo "=========================================="
    echo ""
}

# Test each model
for model in $MODELS; do
    test_model "$model"
done