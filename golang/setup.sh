#!/bin/bash

# Exit on error
set -e

echo "Setting up Go Tech Writer Agent..."

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Error: Go is not installed. Please install Go before continuing."
    exit 1
fi

# Initialize Go module if not already initialized
if [ ! -f "go.mod" ]; then
    go mod init github.com/boxabirds/tech-writer-agent
fi

# Add dependencies to go.mod
echo "Adding dependencies..."
go get github.com/joho/godotenv
go get github.com/sashabaranov/go-openai
go get github.com/urfave/cli/v2
go get github.com/sabhiram/go-gitignore

# Tidy up dependencies
echo "Tidying dependencies..."
go mod tidy

# Create output directory if it doesn't exist
mkdir -p output

# Build the project
echo "Building the project..."
go build -o tech-writer-agent ./src

echo "Setup complete! You can now run the Tech Writer Agent with:"
echo "./tech-writer-agent <directory> <prompt-file> [options]"
