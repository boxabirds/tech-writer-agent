#!/bin/bash

# Setup script for Tech Writer Agent TypeScript port

echo "Setting up Tech Writer Agent (TypeScript)..."

# Install dependencies from package.json
echo "Installing dependencies..."
npm install

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
  echo "Creating .env file from example..."
  cp .env.example .env
  echo "Please edit the .env file to add your API keys."
fi

# Build the project
echo "Building the project..."
npm run build

echo "Setup complete! You can now run the Tech Writer Agent with:"
echo "npm start -- <directory> <prompt_file> [options]"
