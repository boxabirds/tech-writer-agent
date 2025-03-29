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
    
    # Temporary files to store outputs
    OUTPUT1="output1_${model}.txt"
    OUTPUT2="output2_${model}.txt"
    OUTPUT3="output3_${model}.txt"
    
    # Function to extract concatenated response from JSON stream
    extract_response() {
        local file=$1
        # Use jq to select 'response' fields from each JSON object, concatenate them, and output raw text
        cat "$file" | jq -r '.response' | tr -d '\n' > "$file.parsed"
    }
    
    # Run the command 3 times and save outputs
    echo "Running command 1st time..."
    eval "$CMD" > "$OUTPUT1"
    echo "Running command 2nd time..."
    eval "$CMD" > "$OUTPUT2"
    echo "Running command 3rd time..."
    eval "$CMD" > "$OUTPUT3"
    
    # Extract the full text from each run
    extract_response "$OUTPUT1"
    extract_response "$OUTPUT2"
    extract_response "$OUTPUT3"
    
    # Compare the parsed outputs
    echo "Comparing outputs..."
    if diff "$OUTPUT1.parsed" "$OUTPUT2.parsed" > /dev/null && diff "$OUTPUT2.parsed" "$OUTPUT3.parsed" > /dev/null; then
        echo "✅ Success: All three outputs are identical with the above configuration."
        echo "Output: $(cat $OUTPUT1.parsed)"
    else
        echo "❌ Failure: Outputs differ!"
        echo "Run 1: $(cat $OUTPUT1.parsed)"
        echo "Run 2: $(cat $OUTPUT2.parsed)"
        echo "Run 3: $(cat $OUTPUT3.parsed)"
    fi
    
    # Clean up temporary files
    rm -f "$OUTPUT1" "$OUTPUT2" "$OUTPUT3" "$OUTPUT1.parsed" "$OUTPUT2.parsed" "$OUTPUT3.parsed"
    echo "=========================================="
    echo ""
}

# Test each model
for model in $MODELS; do
    test_model "$model"
done